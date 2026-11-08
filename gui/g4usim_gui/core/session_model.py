"""Data model for the controlled multi-round session panel.

The backend protocol is documented in ``docs/会话协议.md``. This module holds
only state and verification helpers so it can be tested without Qt or a
backend process; :mod:`g4usim_gui.core.session_client` owns the process.

Nothing in this module may claim that a configuration is physically applied.
A configuration is *accepted* by the source manager; kernel consumption is a
separate, per-round fact and comes only from the round receipt/artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import math
import re
from typing import Any, Iterable

PROTOCOL = "g4usim-session-v1"
MAX_EVENTS = 100_000_000

# Fields the GUI may edit through ``set_source``. ``plane_beam`` is a source
# shape, not a plain field: it needs its own editor before it may be offered.
EDITABLE_FIELDS = ("particle", "energy", "position", "direction")

# Why a session cannot be started / edited for the current project.
ELIGIBILITY_KEYS = {
    "multiple_sources": "The configured source has several named sources; the session edits a single source.",
    "phase_space_source": "A phase-space source is replayed from a file; start a new session to change it.",
    "deferred_source": "The source still has deferred configuration; initialize it with a single run first.",
    "advanced_source": "This project uses advanced GPS source fields; use a new session to change them.",
    "ion_source": "Ion sources are defined with a particle name and charge; use a new session to change them.",
    "unsupported": "The current source configuration cannot be edited from a session.",
}

DRAFT_KEYS = ("draft", "pending", "accepted", "rejected", "needs_restart")
DRAFT_TEXT = {
    "draft": "Draft changes are not sent to the backend yet.",
    "pending": "Waiting for the backend to confirm this change.",
    "accepted": "The backend accepted the change for the next round. Kernel consumption is reported per run.",
    "rejected": "The backend rejected the change; nothing was applied and no round was started.",
    "needs_restart": "This change needs a new session; the running session keeps its configuration.",
}


def session_eligibility(state: dict[str, Any] | None) -> tuple[bool, str]:
    """Return (editable, reason-key) for the source snapshot of the session."""
    if not isinstance(state, dict):
        return False, "unsupported"
    source = state.get("source")
    if not isinstance(source, dict):
        return False, "unsupported"
    if int(source.get("source_count") or 0) != 1:
        return False, "multiple_sources"
    if source.get("phase_space"):
        return False, "phase_space_source"
    if source.get("advanced"):
        return False, "advanced_source"
    if source.get("ion"):
        return False, "ion_source"
    return True, ""


def format_energy(value: Any) -> str:
    """Format a mono energy in MeV with a stable, locale-independent form."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if number >= 1000.0:
        return f"{number / 1000.0:.6g} GeV"
    if number >= 1.0:
        return f"{number:.6g} MeV"
    if number >= 1e-3:
        return f"{number * 1e3:.6g} keV"
    if number > 0.0:
        return f"{number * 1e6:.6g} eV"
    return "0 MeV"


#: Human-readable energy validation messages keyed by the parser error code.
ENERGY_ERROR_TEXT = {
    "energy_empty": "Enter an energy value.",
    "energy_number": "The energy value is not a valid number.",
    "energy_unit": "The energy unit must be exactly eV, keV, MeV, GeV or TeV.",
    "energy_range": "The energy must be finite and greater than zero after conversion.",
}

#: Energy unit spelling -> MeV factor.  Units are case sensitive on purpose:
#: ``meV`` (milli-eV) is not ``MeV`` (mega-eV), so ambiguous spellings are
#: rejected instead of being silently reinterpreted.
ENERGY_UNIT_FACTORS = {
    "eV": 1e-6,
    "keV": 1e-3,
    "MeV": 1.0,
    "GeV": 1e3,
    "TeV": 1e6,
}


def parse_energy_text(text: str) -> tuple[float | None, str]:
    """Parse ``100 MeV``/``50keV``/``1.5e2 MeV`` into MeV; return (None, key) on error.

    The unit spelling must be exactly one of ``eV``/``keV``/``MeV``/``GeV``/``TeV``;
    a bare number keeps the historical MeV default.  The converted value must be
    finite and positive: overflow (``inf``) and underflow (``0``) are rejected in
    the GUI so no invalid energy is ever sent to the backend.
    """
    raw = (text or "").strip()
    if not raw:
        return None, "energy_empty"
    match = re.match(
        r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-z]*)$",
        raw,
    )
    if not match:
        return None, "energy_number"
    number_text = match.group(1)
    unit_text = match.group(2) or ""
    factor = 1.0 if not unit_text else ENERGY_UNIT_FACTORS.get(unit_text)
    if factor is None:
        return None, "energy_unit"
    try:
        number = float(number_text)
    except ValueError:
        return None, "energy_number"
    if not math.isfinite(number) or number <= 0.0:
        return None, "energy_range" if math.isfinite(number) else "energy_number"
    mev = number * factor
    if not math.isfinite(mev) or mev <= 0.0:
        return None, "energy_range"
    return mev, ""


def next_revision(current: Any, candidate: Any) -> int:
    """Return the session revision after ``candidate``; the current value never regresses.

    A session's ``state_revision`` is monotonic: acks for older requests may
    arrive after a newer state snapshot, and their cached revision must not pull
    the client back.  Non-integer, boolean and negative candidates are ignored.
    """
    accepted = current if isinstance(current, int) and not isinstance(current, bool) and current >= 0 else 0
    if not isinstance(candidate, int) or isinstance(candidate, bool) or candidate < 0:
        return accepted
    return candidate if candidate > accepted else accepted


@dataclass(frozen=True)
class ReceiptCheck:
    """Verification of the receipt payload that accompanies a run_finished event."""

    ok: bool
    reason: str
    path: str = ""
    size_bytes: int | None = None
    sha256: str = ""
    receipt: dict[str, Any] | None = field(default=None, compare=False)


def _receipt_identity_reason(receipt: dict[str, Any], *, run_id: Any = None,
                             request_id: Any = None, status: str = "",
                             require_expected: bool = False) -> str:
    """One semantic contract for inline and integrity-checked file receipts."""
    if receipt.get("schema") != "g4usim_session_run_receipt_v1":
        return "unknown_schema"
    if type(receipt.get("run_id")) is not int or receipt["run_id"] < 0:
        return "run_mismatch"
    if type(receipt.get("run_request_id")) is not str or not receipt["run_request_id"]:
        return "request_mismatch"
    terminal_states = ("completed", "failed", "aborted", "cancelled")
    if type(receipt.get("status")) is not str or receipt["status"] not in terminal_states:
        return "status_mismatch"
    if receipt["status"] == "completed":
        artifacts = receipt.get("artifacts", [])
        if receipt.get("output_failed") is True or (isinstance(artifacts, list) and any(
                isinstance(item, dict) and item.get("integrity_status") == "unavailable"
                for item in artifacts)):
            return "artifact_unavailable"
    if require_expected or run_id is not None:
        if type(run_id) is not int or run_id < 0:
            return "run_mismatch"
    if require_expected or request_id is not None:
        if type(request_id) is not str or not request_id:
            return "request_mismatch"
    if require_expected or status:
        if type(status) is not str or status not in terminal_states:
            return "status_mismatch"
    if run_id is not None and receipt.get("run_id") != run_id:
        return "run_mismatch"
    if request_id is not None and receipt["run_request_id"] != request_id:
        return "request_mismatch"
    if status and receipt["status"] != status:
        return "status_mismatch"
    return ""


def verify_receipt_reference(reference: Any, *, expected_run_id: Any = None,
                             expected_run_request_id: Any = None,
                             expected_status: str = "") -> ReceiptCheck:
    """Verify ``{path,size_bytes,sha256}`` and load the closed receipt file.

    ``run_finished`` may carry the full receipt inline (``receipt``) or a
    bounded reference (``receipt_ref``). The reference is only usable after the
    path, byte size and SHA-256 have been checked. The loaded receipt must also
    belong to the reported run: a receipt file for another run never verifies a
    round. A path that exists but cannot be read (a directory, a locked file)
    is unavailable, not a success.
    """
    if not isinstance(reference, dict):
        return ReceiptCheck(False, "missing_reference")
    path_text = str(reference.get("path") or "")
    expected_size = reference.get("size_bytes")
    expected_sha = str(reference.get("sha256") or "").lower()
    if not path_text:
        return ReceiptCheck(False, "missing_path")
    if not isinstance(expected_size, int) or expected_size < 0:
        return ReceiptCheck(False, "missing_size")
    if len(expected_sha) != 64:
        return ReceiptCheck(False, "missing_sha")
    path = Path(path_text)
    try:
        data = path.read_bytes()
    except OSError:
        return ReceiptCheck(False, "unreadable", path=path_text)
    actual = hashlib.sha256(data).hexdigest()
    if len(data) != expected_size:
        return ReceiptCheck(False, "size_mismatch", path=path_text,
                            size_bytes=len(data), sha256=actual)
    if actual != expected_sha:
        return ReceiptCheck(False, "sha_mismatch", path=path_text,
                            size_bytes=len(data), sha256=actual)
    try:
        receipt = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ReceiptCheck(False, "invalid_json", path=path_text,
                            size_bytes=len(data), sha256=actual)
    if not isinstance(receipt, dict):
        return ReceiptCheck(False, "invalid_receipt", path=path_text,
                            size_bytes=len(data), sha256=actual)
    reason = _receipt_identity_reason(receipt, run_id=expected_run_id,
                                      request_id=expected_run_request_id,
                                      status=expected_status)
    if reason:
        return ReceiptCheck(False, reason, path=path_text,
                            size_bytes=len(data), sha256=actual)
    return ReceiptCheck(True, "", path=path_text, size_bytes=len(data),
                        sha256=actual, receipt=receipt)


def receipt_check_for_event(event: dict[str, Any]) -> ReceiptCheck:
    """Verify the receipt carried by a ``run_finished`` event or its reference.

    A round may have really produced events while its record was not written
    (for example the receipt file could not be opened). In that case the
    backend reports ``receipt_integrity=unavailable`` and no path: the event is
    a *completed run fact* but not a verified record, so the round must not be
    presented as a complete success.
    """
    integrity = str(event.get("receipt_integrity") or "")
    if integrity == "unavailable":
        return ReceiptCheck(False, "receipt_unavailable")
    if integrity and integrity != "written":
        return ReceiptCheck(False, "receipt_integrity_unknown")
    run_id = event.get("run_id")
    run_request_id = event.get("run_request_id")
    status = event.get("status")
    inline = event.get("receipt")
    if isinstance(inline, dict):
        reason = _receipt_identity_reason(inline, run_id=run_id,
                                          request_id=run_request_id, status=status,
                                          require_expected=True)
        if reason:
            return ReceiptCheck(False, reason)
        return ReceiptCheck(True, "", receipt=inline)
    reference = event.get("receipt_ref")
    if isinstance(reference, dict):
        check = verify_receipt_reference(reference)
        if not check.ok:
            return check
        reason = _receipt_identity_reason(check.receipt, run_id=run_id,
                                          request_id=run_request_id, status=status,
                                          require_expected=True)
        if reason:
            return ReceiptCheck(False, reason, path=check.path, size_bytes=check.size_bytes,
                                sha256=check.sha256)
        return check
    return ReceiptCheck(False, "missing_receipt")


def round_status_text(event: dict[str, Any]) -> str:
    status = str(event.get("status") or "")
    completed = event.get("completed_events")
    planned = event.get("planned_events")
    if status not in {"completed", "cancelled", "aborted", "failed"}:
        return "unknown"
    if status == "completed":
        return f"{completed}/{planned} events"
    if status == "cancelled":
        return f"cancelled after {completed}/{planned} events"
    if status == "aborted":
        return f"aborted after {completed}/{planned} events"
    return f"failed after {completed}/{planned} events"


def summarize_round(event: dict[str, Any], particle: str, energy_mev: Any) -> dict[str, Any]:
    """Build the immutable per-round record the panel keeps after run_finished."""
    receipt = event.get("receipt")
    receipts: dict[str, Any] = receipt if isinstance(receipt, dict) else {}
    check = receipt_check_for_event(event)
    return {
        "run_id": event.get("run_id"),
        "run_request_id": str(event.get("run_request_id") or ""),
        "planned_events": event.get("planned_events"),
        "completed_events": event.get("completed_events"),
        "aborted_events": event.get("aborted_events"),
        "status": str(event.get("status") or ""),
        "cancel_requested": bool(event.get("cancel_requested")),
        "particle": particle,
        "energy_mev": energy_mev,
        "seed": (receipts.get("source") or {}).get("seed") if isinstance(receipts.get("source"), dict) else None,
        "receipt_ok": check.ok,
        "receipt_reason": check.reason,
        "receipt_reference": ({"path": check.path, "size_bytes": check.size_bytes,
                               "sha256": check.sha256}
                              if check.ok and not isinstance(receipt, dict) and check.path else None),
        "receipt_path": check.path or str(event.get("receipt_path") or ""),
        "receipt_sha256": check.sha256 or str(event.get("receipt_sha256") or ""),
        "artifacts_truncated": bool(event.get("artifacts_truncated")),
        "artifact_count": event.get("artifact_count"),
    }


def describe_rejection(response: dict[str, Any]) -> str:
    reason = str(response.get("reason") or "rejected")
    message = str(response.get("message") or "")
    return f"{reason}: {message}" if message else reason


def empty_view() -> dict[str, Any]:
    return {
        "phase": "not_started",
        "session": {},
        "state_revision": 0,
        "draft_revision": 0,
        "kernel": "pre_init",
        "source": {},
        "run": {},
        "rounds": [],
        "draft": {"status": "draft", "message": DRAFT_TEXT["draft"]},
        "last_rejection": {},
        "message": "",
    }


def merge_round(rounds: Iterable[dict[str, Any]], record: dict[str, Any]) -> list[dict[str, Any]]:
    """Append a round record unless an identical run_request_id is already stored."""
    kept = [item for item in rounds if item.get("run_request_id") != record.get("run_request_id")]
    kept.append(dict(record))
    return kept
