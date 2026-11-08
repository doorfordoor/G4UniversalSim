"""Read-only process-record judgement shared by persistent result consumers.

Version-1 process records bind mtime/size, not a cryptographic run identity.
Output provenance verification remains separate. No missing process record is
converted into an observed exit code, even when the summary claims completion.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path

from g4usim_gui.core.run_result import RunResult, evaluate_run_result
from g4usim_gui.output.run_summary_parser import parse_run_summary_text


@dataclass(frozen=True)
class PersistedRunEvidence:
    result: RunResult
    trust_level: str
    exit_code: int | None = None
    summary_claimed_status: str = ""
    summary_warnings: tuple[str, ...] = ()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate status key: {key}")
        result[key] = value
    return result


def read_persisted_run_evidence(summary_path: Path, status_path: Path) -> PersistedRunEvidence:
    summary_path, status_path = Path(summary_path), Path(status_path)
    try:
        with summary_path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            raw = stream.read()
            after = os.fstat(stream.fileno())
        current = summary_path.stat()
        stable = ((before.st_mtime_ns, before.st_size, before.st_ino, before.st_dev) ==
                  (after.st_mtime_ns, after.st_size, after.st_ino, after.st_dev) ==
                  (current.st_mtime_ns, current.st_size, current.st_ino, current.st_dev)
                  and len(raw) == after.st_size)
        summary = parse_run_summary_text(raw.decode("utf-8"), path=str(summary_path))
    except (OSError, UnicodeError):
        summary = None
        stable = False
    claimed = summary.key_values.get("status", "") if summary else ""
    warnings = tuple(summary.warnings) if summary else ("Run summary is missing or unreadable.",)
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(status, dict):
            raise ValueError("process record is not an object")
    except FileNotFoundError:
        return PersistedRunEvidence(RunResult("incomplete", "No process record; summary evidence only."),
                                    "summary_only" if summary else "unavailable", None, claimed, warnings)
    except (OSError, UnicodeError, ValueError):
        return PersistedRunEvidence(RunResult("incomplete", "Process record is unreadable or malformed."),
                                    "invalid_process_record", None, claimed, warnings)
    exit_code = status.get("exitCode")
    exit_code = exit_code if type(exit_code) is int else None
    recorded_state = status.get("state")
    recorded_state = recorded_state if isinstance(recorded_state, str) else ""
    fingerprint = status.get("summaryFingerprint")
    fresh = (stable and type(status.get("resultVersion")) is int and status["resultVersion"] == 1
             and status.get("summaryFresh") is True and isinstance(fingerprint, list)
             and len(fingerprint) == 2 and all(type(v) is int for v in fingerprint)
             and fingerprint == [after.st_mtime_ns, after.st_size])
    result = evaluate_run_result(summary_path, exit_code=exit_code,
        crashed=status.get("exitStatus") == "crashed" or recorded_state == "error",
        requested_state=recorded_state if recorded_state in {"stopped", "killed"} else "",
        summary_fresh=fresh, summary=summary)
    if result.state == "success" and status.get("exitStatus") != "normal":
        result = RunResult("incomplete", "Normal process exit is not confirmed.")
    if result.state == "success" and recorded_state not in {"success", "finished", "session_closed"}:
        result = RunResult("incomplete", "Stored workflow state conflicts with completed summary.")
    return PersistedRunEvidence(result, "process_record_v1_mtime_size" if fresh else "unverified_process_record",
                                exit_code, claimed, warnings)
