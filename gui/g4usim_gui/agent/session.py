"""Bounded task evidence, never a process owner or a recovered authorization.

An intent ID is returned only after same-directory atomic replacement succeeds.
The caller still owns action validation, live identity checks and execution. A
loaded journal is query-only: a new explicit user request creates a new task.
SHA256 detects accidental damage; anybody able to rewrite JSON can recompute it.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
import time
import uuid


SCHEMA = "g4usim_agent_task_journal"
VERSION = 1
MAX_BYTES = 1024 * 1024
MAX_RECORDS = 512
STATES = frozenset(("planned", "needs_clarification", "awaiting_approval", "applying",
                    "validating", "initializing", "generating", "running", "evaluating",
                    "awaiting_confirmation", "exporting", "completed", "failed",
                    "cancelled", "interrupted"))
TERMINAL_STATES = frozenset(("completed", "failed", "cancelled", "interrupted"))
ACTIONS = frozenset(("plan", "apply", "validate", "initialize", "generate", "run",
                     "evaluate", "export", "resume"))
_PHASE = dict(plan="planned", apply="applying", validate="validating",
              initialize="initializing", generate="generating", run="running",
              evaluate="evaluating", export="exporting", resume="planned")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[0-9a-f]{32}\Z")
_SECRET_KEYS = frozenset(("apikey", "accesstoken", "password", "secret", "clientsecret",
                          "credentials", "credential", "provider", "providerconfig",
                          "authorization", "bearertoken", "secretkey", "token", "key"))
_PAYLOAD_FIELDS = frozenset(("task_id", "created_at", "updated_at", "state", "reason", "prompt",
                            "authorization", "project_identity", "plan", "limits", "usage",
                            "operations", "records", "first_failure"))
_BINDING_FIELDS = frozenset(("run_id", "record_id", "events", "revision",
                            "snapshot_fingerprint", "action"))
_EVIDENCE_FIELDS = frozenset(("status", "reason", "run_id", "record_id", "revision",
                             "stale", "events", "level"))
_RESERVE_BYTES = 1024


class JournalError(ValueError):
    """A stable diagnostic code; no provider credentials or arbitrary repr."""


class JournalIOError(JournalError):
    pass


class JournalConflict(JournalError):
    pass


class JournalLimitError(JournalError):
    pass


def _need(ok, code="agent.journal.invalid"):
    if not ok:
        raise JournalError(code)


def _fields(obj, required, optional=()):
    _need(type(obj) is dict and set(required) <= obj.keys()
          and obj.keys() <= set(required) | set(optional), "agent.journal.fields")


def _integer(value, maximum=2**63 - 1, minimum=0):
    _need(type(value) is int and minimum <= value <= maximum, "agent.journal.integer")


def _number(value):
    _need(type(value) in (int, float) and 0 <= value <= 2**63 - 1 and math.isfinite(value),
          "agent.journal.number")


def _text(value, maximum=16384, *, empty=False):
    _need(type(value) is str and len(value) <= maximum and (empty or bool(value)),
          "agent.journal.text")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise JournalError("agent.journal.encoding") from exc


def _value(value, depth=0, counter=None):
    """Only detached finite JSON; reject objects and credential-bearing fields."""
    counter = [0] if counter is None else counter
    counter[0] += 1
    _need(depth <= 24 and counter[0] <= 12000, "agent.journal.structure_limit")
    if value is None or type(value) in (bool, int):
        if type(value) is int:
            _need(abs(value) <= 2**63 - 1, "agent.journal.integer")
    elif type(value) is float:
        _need(math.isfinite(value), "agent.journal.nonfinite")
    elif type(value) is str:
        _text(value, 65536, empty=True)
    elif type(value) is list:
        for item in value:
            _value(item, depth + 1, counter)
    elif type(value) is dict:
        for key, item in value.items():
            _text(key, 128)
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            _need(normalized not in _SECRET_KEYS, "agent.journal.secret_field")
            _value(item, depth + 1, counter)
    else:
        raise JournalError("agent.journal.json_only")


def _authorization(obj):
    _fields(obj, ("allowed_actions", "max_calls", "max_events", "timeout_seconds"))
    actions = obj["allowed_actions"]
    _need(type(actions) is list and all(type(a) is str and a in ACTIONS for a in actions)
          and len(actions) == len(set(actions)), "agent.journal.actions")
    _integer(obj["max_calls"], 32, 1)
    _integer(obj["max_events"], 100000)
    _number(obj["timeout_seconds"])
    _need(0 < obj["timeout_seconds"] <= 3600, "agent.journal.timeout")


def _identity(obj):
    _fields(obj, ("snapshot_fingerprint", "revision", "session_id"))
    _need(type(obj["snapshot_fingerprint"]) is str and _SHA.fullmatch(obj["snapshot_fingerprint"]),
          "agent.journal.fingerprint")
    _integer(obj["revision"])
    _text(obj["session_id"], 128)


def _binding(obj):
    _fields(obj, (), _BINDING_FIELDS)
    for key, value in obj.items():
        if key in ("events", "revision"):
            _integer(value, 100000 if key == "events" else 2**63 - 1)
        elif key == "snapshot_fingerprint":
            _need(type(value) is str and _SHA.fullmatch(value), "agent.journal.fingerprint")
        elif key == "action":
            _need(type(value) is str and value in ACTIONS, "agent.journal.action")
        else:
            _text(value, 128)


def _evidence(obj):
    _fields(obj, ("status",), _EVIDENCE_FIELDS - {"status"})
    _value(obj)
    _need(type(obj["status"]) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", obj["status"])
          and obj["status"] != "pending", "agent.journal.result_status")
    if "reason" in obj:
        _text(obj["reason"], 4096, empty=True)
    if "level" in obj:
        _text(obj["level"], 128)
    if "stale" in obj:
        _need(type(obj["stale"]) is bool, "agent.journal.stale")
    _binding({k: v for k, v in obj.items() if k in _BINDING_FIELDS})


def _canonical(obj):
    try:
        return json.dumps(obj, ensure_ascii=False, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise JournalError("agent.journal.encoding") from exc


def _encode(data):
    raw = _canonical(data)
    return _canonical(dict(schema=SCHEMA, version=VERSION, payload=data,
                           checksum=hashlib.sha256(raw).hexdigest())) + b"\n"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "agent.journal.duplicate_key")
        result[key] = value
    return result


def _validate(data):
    _fields(data, _PAYLOAD_FIELDS)
    _need(type(data["task_id"]) is str and _ID.fullmatch(data["task_id"]), "agent.journal.id")
    for key in ("created_at", "updated_at"):
        _number(data[key])
    _need(data["updated_at"] >= data["created_at"], "agent.journal.time_order")
    _need(type(data["state"]) is str and data["state"] in STATES, "agent.journal.state")
    if data["reason"] is not None:
        _text(data["reason"], 4096, empty=True)
    _text(data["prompt"])
    _authorization(data["authorization"])
    _identity(data["project_identity"])
    if data["plan"] is not None:
        _need(type(data["plan"]) is dict, "agent.journal.plan")
        _value(data["plan"])
    _fields(data["limits"], ("max_records", "max_bytes"))
    _integer(data["limits"]["max_records"], MAX_RECORDS, 8)
    _integer(data["limits"]["max_bytes"], MAX_BYTES, 4096)
    _fields(data["usage"], ("calls", "events"))
    _integer(data["usage"]["calls"], data["authorization"]["max_calls"])
    _integer(data["usage"]["events"], data["authorization"]["max_events"])
    ops = data["operations"]
    _need(type(ops) is list and len(ops) == data["usage"]["calls"], "agent.journal.operation_count")
    ids = set()
    bound_ids = set()
    for op in ops:
        _fields(op, ("operation_id", "action", "binding", "intent_at", "result", "result_at"))
        oid = op["operation_id"]
        _need(type(oid) is str and _ID.fullmatch(oid) and oid not in ids, "agent.journal.operation_id")
        ids.add(oid)
        _need(op["action"] in data["authorization"]["allowed_actions"], "agent.journal.action")
        _binding(op["binding"])
        for key in ("run_id", "record_id"):
            if key in op["binding"]:
                marker = (op["action"], key, op["binding"][key])
                _need(marker not in bound_ids, "agent.journal.duplicate_binding")
                bound_ids.add(marker)
        _need(op["binding"].get("action", op["action"]) == op["action"], "agent.journal.binding_action")
        if op["action"] == "run":
            _integer(op["binding"].get("events"), 100000, 1)
        _number(op["intent_at"])
        if op["result"] is None:
            _need(op["result_at"] is None, "agent.journal.result_time")
        else:
            _evidence(op["result"])
            _number(op["result_at"])
            _need(op["result_at"] >= op["intent_at"], "agent.journal.result_time")
            for key in ("run_id", "record_id"):
                if key in op["result"]:
                    _need(op["binding"].get(key) == op["result"][key], "agent.journal.result_binding")
            if "events" in op["result"]:
                _need(op["result"]["events"] <= op["binding"].get("events", 0),
                      "agent.journal.unreserved_events")
    _need(sum(o["binding"].get("events", 0) for o in ops) == data["usage"]["events"],
          "agent.journal.event_count")
    _need(sum(o["result"] is None for o in ops) <= 1, "agent.journal.in_flight")
    if data["state"] == "completed":
        _need(all(o["result"] is not None for o in ops), "agent.journal.in_flight")
    rows = data["records"]
    _need(type(rows) is list and 1 <= len(rows) <= data["limits"]["max_records"],
          "agent.journal.record_count")
    for index, row in enumerate(rows, 1):
        _fields(row, ("sequence", "kind", "at", "operation_id", "reason"))
        _need(type(row["sequence"]) is int and row["sequence"] == index, "agent.journal.sequence")
        _need(row["kind"] in ("created", "plan", "state", "intent", "binding", "result", "limit"),
              "agent.journal.record_kind")
        _number(row["at"])
        _need(row["operation_id"] is None or row["operation_id"] in ids, "agent.journal.record_operation")
        if row["reason"] is not None:
            _text(row["reason"], 4096, empty=True)
    first = data["first_failure"]
    if first is not None:
        _fields(first, ("at", "reason", "operation_id"))
        _number(first["at"])
        _text(first["reason"], 4096, empty=True)
        _need(first["operation_id"] is None or first["operation_id"] in ids, "agent.journal.first_failure")
    _need(len(_encode(data)) <= data["limits"]["max_bytes"], "agent.journal.byte_count")


def _path(path, *, file=False):
    """Inspect original spelling, including Windows 3.11 junction ancestors."""
    try:
        raw = os.fspath(path)
        _need(type(raw) is str and "\0" not in raw and ".." not in Path(raw).parts,
              "agent.journal.path")
        p = Path(os.path.abspath(raw))
    except (TypeError, ValueError) as exc:
        if isinstance(exc, JournalError):
            raise
        raise JournalError("agent.journal.path") from exc
    for entry in (p, *p.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise JournalIOError("agent.journal.path_unavailable") from exc
        _need(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400),
              "agent.journal.link_path")
        if entry == p and file:
            _need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "agent.journal.regular_file")
    return p


def _read(path):
    path = _path(path, file=True)
    try:
        with path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            named = path.lstat()
            _need((info.st_dev, info.st_ino) == (named.st_dev, named.st_ino), "agent.journal.path_changed")
            _need(info.st_size <= MAX_BYTES, "agent.journal.size")
            raw = stream.read(MAX_BYTES + 1)
        _need(len(raw) <= MAX_BYTES, "agent.journal.size")
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                         parse_constant=lambda _: _need(False, "agent.journal.nonfinite"))
        _fields(obj, ("schema", "version", "payload", "checksum"))
        _need(obj["schema"] == SCHEMA and type(obj["version"]) is int and obj["version"] == VERSION,
              "agent.journal.version")
        _need(type(obj["checksum"]) is str and _SHA.fullmatch(obj["checksum"])
              and obj["checksum"] == hashlib.sha256(_canonical(obj["payload"])).hexdigest(),
              "agent.journal.checksum")
        _validate(obj["payload"])
        return obj["payload"], hashlib.sha256(raw).hexdigest()
    except JournalError:
        raise
    except (OSError, ValueError, UnicodeError, RecursionError, TypeError, KeyError, OverflowError) as exc:
        raise JournalIOError("agent.journal.read_failed") from exc


@contextmanager
def _lease(path):
    lock = _path(path.with_suffix(".lock"), file=True)
    fd = None
    try:
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
        os.lseek(fd, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except OSError as exc:
        raise JournalIOError("agent.journal.storage_failed") from exc
    finally:
        if fd is not None:
            os.close(fd)


class TaskJournal:
    def __init__(self, path, data, digest, *, recovered):
        self._path = path
        self._data = data
        self._digest = digest
        self._recovered = recovered
        self._mutex = threading.RLock()
        self._owner = None
        self._closed_owner = False
        self._start = time.monotonic()
        self._age = max(0, time.time() - data["created_at"])

    @classmethod
    def create(cls, root, prompt, authorization, project_identity, *, limits=None):
        _text(prompt)
        _authorization(authorization)
        _identity(project_identity)
        caps = {"max_records": MAX_RECORDS, "max_bytes": MAX_BYTES} if limits is None else deepcopy(limits)
        now = time.time()
        tid = uuid.uuid4().hex
        data = dict(task_id=tid, created_at=now, updated_at=now, state="planned", reason=None,
                    prompt=prompt, authorization=deepcopy(authorization), project_identity=deepcopy(project_identity),
                    plan=None, limits=caps, usage=dict(calls=0, events=0), operations=[],
                    records=[dict(sequence=1, kind="created", at=now, operation_id=None, reason=None)],
                    first_failure=None)
        _validate(data)
        _need(len(_encode(data)) <= caps["max_bytes"] - _RESERVE_BYTES, "agent.journal.initial_size")
        folder = _path(root) / tid
        try:
            _path(root).mkdir(parents=True, exist_ok=True)
            _path(root)
            folder.mkdir()
        except OSError as exc:
            raise JournalIOError("agent.journal.create_failed") from exc
        journal = cls(folder / "journal.json", data, None, recovered=False)
        journal._owner = _lease(journal.path)
        try:
            journal._owner.__enter__()
            journal._publish(data)
        except BaseException:
            journal.close()
            raise
        return journal

    @classmethod
    def load(cls, path):
        data, digest = _read(path)
        return cls(_path(path, file=True), data, digest, recovered=True)

    @property
    def path(self):
        return self._path

    @property
    def state(self):
        return self._data["state"]

    @property
    def task_id(self):
        return self._data["task_id"]

    def to_dict(self):
        with self._mutex:
            return deepcopy(self._data)

    def close(self):
        """Release task ownership after the controller has drained its own work.

        This never stops a process, retries an operation or changes disk state.
        """
        with self._mutex:
            self._closed_owner = True
            owner, self._owner = self._owner, None
            if owner is not None:
                try:
                    owner.__exit__(None, None, None)
                except OSError as exc:
                    raise JournalIOError("agent.journal.lease_close_failed") from exc

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass  # OS also releases the lease if the owning process exits.

    @contextmanager
    def _guard(self):
        if self._owner is not None:
            yield
        else:
            with _lease(self.path):
                yield

    def _release_if_finished(self):
        if self.state in TERMINAL_STATES and all(o["result"] is not None for o in self._data["operations"]):
            self.close()

    def _publish(self, candidate):
        raw = _encode(candidate)
        tmp = None
        fd = None
        try:
            _path(self.path, file=True)
            if self._digest is None:
                _need(not self.path.exists(), "agent.journal.already_exists")
            else:
                _, current = _read(self.path)
                if current != self._digest:
                    raise JournalConflict("agent.journal.changed")
            fd, name = tempfile.mkstemp(prefix=".journal-", suffix=".tmp", dir=self.path.parent)
            tmp = Path(name)
            stream = os.fdopen(fd, "wb")
            fd = None  # fdopen owns it only after a successful return.
            with stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            _path(self.path, file=True)
            if self._digest is None:
                _need(not self.path.exists(), "agent.journal.already_exists")
            else:
                _, current = _read(self.path)
                if current != self._digest:
                    raise JournalConflict("agent.journal.changed")
            os.replace(tmp, self.path)
            tmp = None  # Commit point: no fallible cleanup after replacement.
            self._data = candidate
            self._digest = hashlib.sha256(raw).hexdigest()
        except JournalError:
            raise
        except OSError as exc:
            raise JournalIOError("agent.journal.storage_failed") from exc
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp is not None:
                try:
                    tmp.unlink()
                except OSError:
                    pass

    @staticmethod
    def _event(data, kind, operation_id=None, reason=None):
        now = max(time.time(), data["updated_at"])
        data["updated_at"] = now
        data["records"].append(dict(sequence=len(data["records"]) + 1, kind=kind, at=now,
                                    operation_id=operation_id, reason=reason))

    @staticmethod
    def _first(data, reason, operation_id=None):
        if data["first_failure"] is None:
            data["first_failure"] = dict(at=data["updated_at"], reason=reason, operation_id=operation_id)

    def _limit(self, reason):
        if self.state in TERMINAL_STATES:
            raise JournalLimitError(reason)
        data = deepcopy(self._data)
        data["state"], data["reason"] = "failed", reason
        self._event(data, "limit", reason=reason)
        self._first(data, reason)
        _validate(data)
        self._publish(data)
        self._release_if_finished()
        raise JournalLimitError(reason)

    def _update(self, change, *, executing=False):
        with self._mutex, self._guard():
            _, digest = _read(self.path)
            if digest != self._digest:
                raise JournalConflict("agent.journal.changed")
            if executing:
                _need(not self._recovered, "agent.journal.recovered_query_only")
                _need(self.state not in TERMINAL_STATES, "agent.journal.terminal")
                _need(not self._closed_owner, "agent.journal.closed")
                self._check_time()
            candidate = deepcopy(self._data)
            result = change(candidate)
            if candidate == self._data:
                return result
            if len(candidate["records"]) >= candidate["limits"]["max_records"]:
                self._limit("agent.limit.records")
            if len(_encode(candidate)) > candidate["limits"]["max_bytes"] - _RESERVE_BYTES:
                self._limit("agent.limit.bytes")
            _validate(candidate)
            self._publish(candidate)
            self._release_if_finished()
            return result

    def _check_time(self):
        elapsed = max(time.time() - self._data["created_at"],
                      self._age + time.monotonic() - self._start)
        if elapsed >= self._data["authorization"]["timeout_seconds"]:
            self._limit("agent.limit.time")

    def set_plan(self, plan):
        _need(type(plan) is dict, "agent.journal.plan")
        _value(plan)
        def change(data):
            data["plan"] = deepcopy(plan)
            self._event(data, "plan")
        self._update(change, executing=True)

    def transition(self, state, reason=None):
        _need(type(state) is str and state in STATES, "agent.journal.state")
        if reason is not None:
            _text(reason, 4096, empty=True)
        def change(data):
            _need(not self._recovered or state in ("interrupted", "cancelled"),
                  "agent.journal.recovered_query_only")
            if data["state"] == state:
                return
            _need(data["state"] not in TERMINAL_STATES, "agent.journal.terminal")
            if state not in ("failed", "cancelled", "interrupted"):
                self._check_time()
            if state == "completed":
                _need(all(o["result"] is not None for o in data["operations"]), "agent.journal.in_flight")
            data["state"], data["reason"] = state, reason
            self._event(data, "state", reason=reason)
            if state in ("failed", "cancelled", "interrupted"):
                self._first(data, reason or "agent.task." + state)
        self._update(change)

    def record_intent(self, action, binding):
        _need(type(action) is str and action in ACTIONS, "agent.journal.action")
        _binding(binding)
        _need(binding.get("action", action) == action, "agent.journal.binding_action")
        if action == "run":
            _integer(binding.get("events"), 100000, 1)
        def change(data):
            _need(action in data["authorization"]["allowed_actions"], "agent.journal.unauthorized")
            _need(not any(o["result"] is None for o in data["operations"]), "agent.journal.in_flight")
            for op in data["operations"]:
                for key in ("run_id", "record_id"):
                    _need(not (key in binding and op["binding"].get(key) == binding[key]
                               and op["action"] == action), "agent.journal.duplicate_binding")
            if data["usage"]["calls"] >= data["authorization"]["max_calls"]:
                self._limit("agent.limit.calls")
            events = binding.get("events", 0)
            if data["usage"]["events"] + events > data["authorization"]["max_events"]:
                self._limit("agent.limit.events")
            oid = uuid.uuid4().hex
            self._event(data, "intent", oid)
            data["operations"].append(dict(operation_id=oid, action=action, binding=deepcopy(binding),
                                            intent_at=data["updated_at"], result=None, result_at=None))
            data["usage"]["calls"] += 1
            data["usage"]["events"] += events
            data["state"] = _PHASE[action]
            return oid
        return self._update(change, executing=True)

    @staticmethod
    def _operation(data, operation_id):
        _need(type(operation_id) is str, "agent.journal.operation_id")
        for op in data["operations"]:
            if op["operation_id"] == operation_id:
                return op
        raise JournalError("agent.journal.unknown_operation")

    @staticmethod
    def _merge(op, binding):
        for key, value in binding.items():
            if key in op["binding"]:
                _need(op["binding"][key] == value, "agent.journal.binding_conflict")
            elif key == "events":
                _need(value == 0, "agent.journal.unreserved_events")
            elif key == "action":
                _need(value == op["action"], "agent.journal.binding_action")
            op["binding"][key] = value

    def record_binding(self, operation_id, binding):
        _binding(binding)
        def change(data):
            op = self._operation(data, operation_id)
            before = deepcopy(op["binding"])
            self._merge(op, binding)
            if before != op["binding"]:
                _need(op["result"] is None, "agent.journal.result_already_recorded")
                self._event(data, "binding", operation_id)
        self._update(change)

    bind_operation = record_binding

    def record_result(self, operation_id, evidence):
        _evidence(evidence)
        def change(data):
            op = self._operation(data, operation_id)
            if op["result"] is not None:
                _need(op["result"] == evidence, "agent.journal.result_conflict")
                return
            # Result revision is the observed post-action revision; binding keeps
            # the original expected pre-action revision, especially for apply.
            self._merge(op, {k: v for k, v in evidence.items() if k in ("run_id", "record_id")})
            if "events" in evidence:
                _need(evidence["events"] <= op["binding"].get("events", 0),
                      "agent.journal.unreserved_events")
            self._event(data, "result", operation_id)
            op["result"], op["result_at"] = deepcopy(evidence), data["updated_at"]
            if evidence["status"] in ("failed", "rejected", "cancelled", "interrupted"):
                self._first(data, evidence.get("reason") or "agent.operation." + evidence["status"], operation_id)
        self._update(change)

    def cancel(self):
        if self.state in TERMINAL_STATES:
            return
        self.transition("cancelled", reason="agent.task.cancelled")

    def resume_policy(self):
        """A query plan, never authority to replay an old intent."""
        with self._mutex:
            pending = [deepcopy(o) for o in self._data["operations"] if o["result"] is None]
            return dict(mode="query_only" if pending else "new_task_required", can_replay=False,
                        requires_new_user_request=True, requires_live_identity_check=True,
                        persisted_state=self.state, recovered=self._recovered,
                        suggested_state="interrupted" if pending and self.state not in TERMINAL_STATES else self.state,
                        task_id=self.task_id, project_identity=deepcopy(self._data["project_identity"]),
                        in_flight=pending)
