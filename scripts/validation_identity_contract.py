"""Pure semantic checks for the optional candidate_identity v1 in report v2.

This validates recorded snapshots, not the current filesystem or executable
provenance. Stable missing optional binaries are representable, as in the runner;
stable identity alone does not establish a successful test or simulation.

Call validate_candidate_identity(report, require_identity=True) for new formal
evidence. Compatibility mode returns an explicit unavailable result only when the
extension key is absent. Null/malformed extensions never downgrade to legacy.
Drifted and unverifiable identities are rejected in both modes.

CLI exit codes: 0 stable identity, 1 rejection, 2 legacy/unavailable (never OK).
The report evidence gate calls this validator in its formal identity mode.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys

SNAPSHOT_FIELDS = (
    "git_head", "source_fingerprint", "tests_content_fingerprint",
    "merge_source_fingerprint", "backend_executable", "merge_executable",
)
BINARY_FIELDS = ("backend_executable", "merge_executable")
IDENTITY_KEYS = {"version", "binding_strategy", "start", "end", "status", "drift_fields", "errors"}
HEX64 = re.compile(r"[0-9a-f]{64}")
GIT_HASH = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


class IdentityContractError(ValueError):
    """Recorded identity cannot support formal acceptance."""


@dataclass(frozen=True)
class IdentityValidationResult:
    status: str
    available: bool
    stable: bool
    reason: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IdentityContractError(message)


def _keys(value: object, required: set[str], label: str) -> None:
    _require(isinstance(value, dict), f"{label} must be an object")
    _require(set(value) == required, f"{label} fields must be exactly {sorted(required)}")


def _snapshot(snapshot: object, phase: str) -> None:
    _keys(snapshot, set(SNAPSHOT_FIELDS), f"candidate_identity.{phase}")
    for field in SNAPSHOT_FIELDS:
        value = snapshot[field]
        label = f"candidate_identity.{phase}.{field}"
        # A capture failure is represented by null plus a matching error record.
        if value is None:
            continue
        if field in BINARY_FIELDS:
            _keys(value, {"path", "state", "sha256"}, label)
            path = value["path"]
            _require(isinstance(path, str) and bool(path) and "\x00" not in path,
                     f"{label}.path must be a nonempty path string")
            _require(PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute(),
                     f"{label}.path must be absolute")
            state, digest = value["state"], value["sha256"]
            _require(state in ("file", "missing"), f"{label}.state must be file or missing")
            if state == "file":
                _require(isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
                         f"{label}.sha256 must be a lowercase SHA256 for state=file")
            else:
                _require(digest is None, f"{label}.sha256 must be null for state=missing")
        else:
            pattern = GIT_HASH if field == "git_head" else HEX64
            _require(isinstance(value, str) and pattern.fullmatch(value) is not None,
                     f"{label} must be a lowercase {'Git object hash' if field == 'git_head' else 'SHA256'}")


def validate_candidate_identity(
    report: object, *, require_identity: bool = False,
) -> IdentityValidationResult:
    """Return stable/unavailable explicitly; raise on malformed or failed identity.

    v1 uses closed identity/snapshot/binary/error shapes. Top-level report fields
    remain extensible. Top-level identity values bind exactly to start, including
    original path strings; this function never normalizes or reopens those paths.
    """
    _require(type(require_identity) is bool, "require_identity must be bool")
    _require(isinstance(report, dict), "report must be an object")
    _require(report.get("schema") == "G4UniversalSimM0TestReport", "unexpected report schema")
    _require(type(report.get("version")) is int and report["version"] == 2, "identity contract requires report v2")
    if "candidate_identity" not in report:
        _require(not require_identity, "candidate_identity missing: strict mode requires start/end identity evidence")
        return IdentityValidationResult(
            "legacy/unavailable", False, False, "report v2 has no candidate_identity; start/end stability unavailable",
        )
    identity = report["candidate_identity"]
    _keys(identity, IDENTITY_KEYS, "candidate_identity")
    _require(type(identity["version"]) is int and identity["version"] == 1,
             "unknown candidate_identity version (expected integer 1)")
    _require(identity["binding_strategy"] == "start_end_content_snapshots",
             "unknown candidate_identity binding_strategy")
    start, end = identity["start"], identity["end"]
    _snapshot(start, "start")
    _snapshot(end, "end")

    errors = identity["errors"]
    _require(isinstance(errors, list), "candidate_identity.errors must be a list")
    capture_errors = set()
    for error in errors:
        _keys(error, {"phase", "field", "error"}, "candidate_identity.errors record")
        phase, field, message = error["phase"], error["field"], error["error"]
        _require(phase in ("start", "end", "preflight"), "identity error has unknown phase")
        _require(field in SNAPSHOT_FIELDS, "identity error has unknown field")
        _require(isinstance(message, str) and bool(message.strip()), "identity error must have a nonempty error message")
        key = (phase, field)
        _require(key not in capture_errors, "duplicate identity error phase/field")
        capture_errors.add(key)
        if phase == "preflight":
            _require(field == "backend_executable", "v1 preflight error must identify backend_executable")
        else:
            snapshot = start if phase == "start" else end
            _require(snapshot[field] is None, f"identity {phase}/{field} error requires a null snapshot value")
    for phase, snapshot in (("start", start), ("end", end)):
        for field, value in snapshot.items():
            _require(value is not None or (phase, field) in capture_errors,
                     f"identity {phase}/{field} null value requires a matching capture error")

    declared = identity["drift_fields"]
    _require(isinstance(declared, list) and all(isinstance(field, str) for field in declared),
             "candidate_identity.drift_fields must be a list of field names")
    actual = sorted(field for field in SNAPSHOT_FIELDS if start[field] != end[field])
    _require(declared == actual, f"candidate_identity.drift_fields mismatch: declared {declared!r}, actual {actual!r}")
    status = identity["status"]
    _require(status in ("stable", "drifted", "unverifiable"), "unknown candidate_identity status")
    expected = "unverifiable" if errors else "drifted" if actual else "stable"
    _require(status == expected, f"candidate_identity status {status!r} contradicts snapshots/errors (expected {expected!r})")

    for field in SNAPSHOT_FIELDS:
        _require(field in report, f"top-level report missing identity field {field}")
        value = start[field]
        expected_value = (value["path"] if value is not None else None) if field in BINARY_FIELDS else value
        _require(report[field] == expected_value, f"top-level {field} is not bound to candidate_identity.start")
    _require(status == "stable", f"candidate_identity {status}: formal evidence rejected; drift_fields={actual!r}")
    return IdentityValidationResult("stable", True, True, "recorded start/end snapshots match with no capture errors")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--require-identity", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        result = validate_candidate_identity(report, require_identity=args.require_identity)
    except (IdentityContractError, OSError, ValueError) as error:
        print(f"identity contract: REJECT {error}")
        return 1
    print("identity contract: " + json.dumps(asdict(result), sort_keys=True))
    return 0 if result.stable else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
