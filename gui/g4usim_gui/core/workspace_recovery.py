"""Process-isolated, atomic recovery copies of the shared project edit payload.

Recovery is not project saving and never writes a recorded origin path. A live
OS lease (also tracked in-process) excludes all other windows, including ones
in the same Python process. PID and timestamps are informational only.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
from typing import Any, Iterator
import uuid

from g4usim_gui.core.config_migration import load_json_strict
from g4usim_gui.core.edit_snapshot import SNAPSHOT_SCHEMA, SNAPSHOT_VERSION, snapshot_from_dict


SCHEMA = "g4usim_workspace_recovery_v1"
MAX_BYTES = 32 * 1024 * 1024
_ID = re.compile(r"[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_HELD: set[str] = set()
_HELD_MUTEX = threading.Lock()
_FIELDS = {"schema", "session_id", "revision", "created_utc", "updated_utc",
           "disposition", "origin_path", "origin_sha256", "saved_digest",
           "payload", "payload_sha256"}


class RecoveryBusyError(OSError):
    """The copy is owned by a live editor or another recovery action."""


class RecoveryChangedError(ValueError):
    """The candidate no longer contains the bytes shown to the user."""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def payload_digest(payload: dict) -> str:
    """Identity of a detached edit payload; it is not a semantic validation."""
    return _digest(_json_bytes(payload))


def _check_regular(path: Path, *, missing_ok: bool = False) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return
        raise
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Recovery path must be a regular non-link file: {path}")


class _Lease:
    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None
        self.key = os.path.normcase(str(path.absolute()))
        with _HELD_MUTEX:
            if self.key in _HELD:
                raise RecoveryBusyError("Recovery session is active in another window")
            _HELD.add(self.key)
        try:
            _check_regular(path, missing_ok=True)
            flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            self.fd = os.open(path, flags, 0o600)
            opened, named = os.fstat(self.fd), path.lstat()
            if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
                raise RecoveryChangedError("Recovery lease path changed while opening")
            _check_regular(path)
            if opened.st_size == 0:
                os.write(self.fd, b"\0")
            os.lseek(self.fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as exc:
            self.close()
            if isinstance(exc, (BlockingIOError, PermissionError)):
                raise RecoveryBusyError("Recovery session is active in another process") from exc
            if isinstance(exc, OSError) and getattr(exc, "winerror", None) in {33, 36}:
                raise RecoveryBusyError("Recovery session is active in another process") from exc
            raise

    def close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)  # Closing releases the OS lease, even after process death.
            finally:
                self.fd = None
        with _HELD_MUTEX:
            _HELD.discard(self.key)


def _read_bytes(path: Path) -> bytes:
    _check_regular(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Recovery copy exceeds the supported size limit")
    return raw


def _atomic_publish(path: Path, raw: bytes) -> str:
    if len(raw) > MAX_BYTES:
        raise ValueError("Recovery copy exceeds the supported size limit")
    _check_regular(path, missing_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    cleanup_warning = ""
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        _check_regular(path, missing_ok=True)
        os.replace(temporary, path)
    finally:
        # Publication is the commit point. A leftover temp must not turn a
        # completed publication into a reported failure or erase its target.
        try:
            temporary.unlink(missing_ok=True)
        except OSError as exc:
            cleanup_warning = str(exc)
    return cleanup_warning


@dataclass(frozen=True)
class RecoveryRecord:
    session_id: str
    revision: int
    created_utc: str
    updated_utc: str
    disposition: str
    origin_path: str
    origin_sha256: str | None
    saved_digest: str | None
    payload: dict[str, Any]
    payload_sha256: str


@dataclass(frozen=True)
class RecoveryCandidate:
    session_id: str
    path: Path
    raw_sha256: str
    project_name: str = ""
    updated_utc: str = ""
    origin_path: str = ""
    disposition: str = "active"
    error: str = ""


@dataclass(frozen=True)
class RecoveryReceipt:
    path: Path
    raw_sha256: str
    revision: int
    updated_utc: str
    cleanup_warning: str = ""


def origin_status(record: RecoveryRecord) -> str:
    """Fresh observation only; never invent or replace the recorded identity."""
    if not record.origin_path:
        return "unsaved"
    path = Path(record.origin_path)
    try:
        if not path.is_file():
            return "missing"
        if record.origin_sha256 is None:
            return "unobserved"
        if path.stat().st_size > MAX_BYTES:
            return "unavailable"
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return "unavailable"
        return "matches" if _digest(raw) == record.origin_sha256 else "changed"
    except (OSError, ValueError):
        return "unavailable"


def _decode(raw: bytes, session_id: str) -> tuple[dict, RecoveryRecord]:
    data = load_json_strict(raw)
    if type(data) is not dict or set(data) != _FIELDS:
        raise ValueError("Unsupported or incomplete recovery fields")
    if data["schema"] != SCHEMA:
        raise ValueError("Unsupported recovery schema")
    if data["session_id"] != session_id or not _ID.fullmatch(session_id):
        raise ValueError("Recovery session identity does not match its filename")
    if type(data["revision"]) is not int or data["revision"] < 0:
        raise ValueError("Recovery revision must be a nonnegative integer")
    for name in ("created_utc", "updated_utc", "origin_path", "disposition"):
        if type(data[name]) is not str:
            raise ValueError(f"Invalid recovery field type: {name}")
    for name in ("created_utc", "updated_utc"):
        parsed = datetime.fromisoformat(data[name])
        if parsed.tzinfo is None:
            raise ValueError(f"Recovery timestamp must have a timezone: {name}")
    if data["disposition"] not in {"active", "retained", "saved", "discarded"}:
        raise ValueError("Unsupported recovery disposition")
    for name in ("origin_sha256", "saved_digest"):
        value = data[name]
        if value is not None and (type(value) is not str or not _SHA.fullmatch(value)):
            raise ValueError(f"Invalid recovery digest: {name}")
    if data["origin_sha256"] is not None and not data["origin_path"]:
        raise ValueError("A recovery origin digest requires its observed path")
    payload = data["payload"]
    if type(payload) is not dict:
        raise ValueError("Recovery project payload must be an object")
    if payload.get("editingState") is None or payload.get("materialEditor") is None:
        raise ValueError("Recovery payload requires the complete editing state and material document")
    # Use the shared strict snapshot codec, including complete dataclass fields.
    # A recovery envelope never falls back to legacy partial-project defaults.
    project_part = dict(payload, editingState=None)
    snapshot_from_dict(dict(schema=SNAPSHOT_SCHEMA, version=SNAPSHOT_VERSION,
                            project=project_part, state=payload["editingState"]))
    if type(data["payload_sha256"]) is not str or _digest(_json_bytes(payload)) != data["payload_sha256"]:
        raise ValueError("Recovery project payload digest does not match")
    return data, RecoveryRecord(**{key: value for key, value in data.items() if key != "schema"})


class RecoveryStore:
    def __init__(self, root: str | Path | None = None):
        if root is None:
            from g4usim_gui.core.install_layout import default_recovery_root
            root = default_recovery_root()
        self.root = Path(root).expanduser().absolute()
        self.root.mkdir(parents=True, exist_ok=True)
        self.root = self.root.resolve()

    def _path(self, session_id: str) -> Path:
        if type(session_id) is not str or not _ID.fullmatch(session_id):
            raise ValueError("Invalid recovery candidate identity")
        return self.root / f"{session_id}.json"

    def _lease(self, session_id: str) -> _Lease:
        self._path(session_id)
        return _Lease(self.root / f"{session_id}.lock")

    def open_session(self) -> "RecoverySession":
        for _ in range(4):
            session_id = uuid.uuid4().hex
            if not self._path(session_id).exists():
                return RecoverySession(self, session_id, self._lease(session_id))
        raise FileExistsError("Could not allocate a unique recovery session")

    def discover(self) -> tuple[RecoveryCandidate, ...]:
        candidates = []
        for path in sorted(self.root.glob("*.json")):
            session_id = path.stem
            if not _ID.fullmatch(session_id):
                continue
            try:
                lease = self._lease(session_id)
            except RecoveryBusyError:
                continue
            except (OSError, ValueError):
                # Never offer a copy whose ownership cannot be established.
                continue
            try:
                try:
                    raw = _read_bytes(path)
                    raw_sha = _digest(raw)
                except (OSError, ValueError) as exc:
                    candidates.append(RecoveryCandidate(session_id, path, "", error=str(exc)))
                    continue
                try:
                    _, record = _decode(raw, session_id)
                    if record.disposition in {"saved", "discarded"}:
                        continue
                    candidates.append(RecoveryCandidate(
                        session_id, path, raw_sha, record.payload.get("projectName", ""),
                        record.updated_utc, record.origin_path, record.disposition))
                except (ValueError, TypeError, RecursionError) as exc:
                    candidates.append(RecoveryCandidate(session_id, path, raw_sha, error=str(exc)))
            finally:
                lease.close()
        return tuple(sorted(candidates, key=lambda item: (item.updated_utc, item.session_id), reverse=True))

    @contextmanager
    def claim(self, candidate: RecoveryCandidate) -> Iterator["RecoveryClaim"]:
        path = self._path(candidate.session_id)
        if candidate.path != path:
            raise ValueError("Recovery candidate does not belong to this store")
        lease = self._lease(candidate.session_id)
        claim = None
        try:
            claim = RecoveryClaim(self, candidate)
            claim._check_bytes()
            yield claim
        finally:
            if claim is not None:
                claim._closed = True
            lease.close()


class RecoverySession:
    def __init__(self, store: RecoveryStore, session_id: str, lease: _Lease):
        self.store, self.session_id, self._lease = store, session_id, lease
        self.path = store._path(session_id)
        self.created_utc = _utc()
        self._revision = -1
        self._payload_sha256 = None
        self._retired_revision = -1
        self._closed = False
        self._mutex = threading.RLock()

    def publish(self, payload: dict, revision: int, *, origin_path: str = "",
                origin_sha256: str | None = None, saved_digest: str | None = None) -> RecoveryReceipt:
        with self._mutex:
            if self._closed:
                raise RuntimeError("Recovery session is closed")
            if type(revision) is not int or revision < 0 or revision < self._revision:
                raise ValueError("Recovery revision cannot go backwards")
            if revision <= self._retired_revision:
                raise ValueError("Retired recovery revisions cannot become active again")
            fingerprint = payload_digest(payload)
            if revision == self._revision:
                if fingerprint != self._payload_sha256:
                    raise ValueError("One recovery revision cannot describe different payloads")
                # Idempotent retries do not rewrite identity/timestamp/origin.
                raw = _read_bytes(self.path)
                _, record = _decode(raw, self.session_id)
                if record.revision != revision or record.payload_sha256 != fingerprint or record.disposition != "active":
                    raise RecoveryChangedError("Recovery copy changed before an idempotent retry")
                return RecoveryReceipt(self.path, _digest(raw), revision, record.updated_utc)
            data = dict(schema=SCHEMA, session_id=self.session_id, revision=revision,
                        created_utc=self.created_utc, updated_utc=_utc(), disposition="active",
                        origin_path=origin_path, origin_sha256=origin_sha256,
                        saved_digest=saved_digest, payload=payload,
                        payload_sha256=fingerprint)
            raw = _json_bytes(data)
            _decode(raw, self.session_id)
            warning = _atomic_publish(self.path, raw)
            self._revision = revision
            self._payload_sha256 = fingerprint
            return RecoveryReceipt(self.path, _digest(raw), revision, data["updated_utc"], warning)

    def retain(self) -> None:
        with self._mutex:
            self._set_disposition("retained")

    def _set_disposition(self, value: str) -> RecoveryReceipt | None:
        if self._closed:
            raise RuntimeError("Recovery session is closed")
        if not self.path.exists():
            return None
        data, record = _decode(_read_bytes(self.path), self.session_id)
        data["disposition"] = value
        raw = _json_bytes(data)
        warning = _atomic_publish(self.path, raw)
        return RecoveryReceipt(self.path, _digest(raw), record.revision, record.updated_utc, warning)

    def retire(self, reason: str = "saved") -> RecoveryReceipt | None:
        if reason not in {"saved", "discarded"}:
            raise ValueError("Recovery retirement must be saved or discarded")
        with self._mutex:
            receipt = self._set_disposition(reason)
            self._retired_revision = max(self._retired_revision, self._revision)
            if receipt is None:
                return None
            try:
                self.path.unlink()
                return receipt
            except OSError as exc:
                return RecoveryReceipt(receipt.path, receipt.raw_sha256, receipt.revision,
                                       receipt.updated_utc, str(exc))

    def close(self) -> None:
        with self._mutex:
            if not self._closed:
                self._closed = True
                self._lease.close()


class RecoveryClaim:
    def __init__(self, store: RecoveryStore, candidate: RecoveryCandidate):
        self.store, self.candidate = store, candidate
        self._closed = False

    def _check_bytes(self) -> bytes:
        if self._closed:
            raise RuntimeError("Recovery claim is closed")
        raw = _read_bytes(self.candidate.path)
        if not self.candidate.raw_sha256 or _digest(raw) != self.candidate.raw_sha256:
            raise RecoveryChangedError("Recovery copy changed; refresh the candidate list")
        return raw

    def read(self) -> RecoveryRecord:
        return _decode(self._check_bytes(), self.candidate.session_id)[1]

    def retain(self) -> None:
        # Keeping a damaged file must remain possible without rewriting it.
        raw = self._check_bytes()
        if self.candidate.error:
            return
        data, _ = _decode(raw, self.candidate.session_id)
        data["disposition"] = "retained"
        _atomic_publish(self.candidate.path, _json_bytes(data))

    def discard(self) -> None:
        self._check_bytes()
        # Only explicit discard may remove even an invalid envelope. The path
        # has already been restricted to a regular file under this store.
        self.candidate.path.unlink()
