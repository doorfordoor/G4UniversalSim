"""Permanent static regression for report v2/candidate_identity v1 semantics.

No compiler, Geant4, network, registration edits or existing evidence are needed.
Use --evidence-dir NEW_DIRECTORY to retain all controls and process receipts;
G4USIM_TEST_EVIDENCE_DIR is also supported for the standard regression runner.
"""

from __future__ import annotations

from dataclasses import asdict
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from validation_identity_contract import IdentityContractError, validate_candidate_identity

HELPER = Path(__file__).with_name("validation_identity_contract.py")


def fixture() -> dict:
    start = {
        "git_head": "a" * 40, "source_fingerprint": "b" * 64,
        "tests_content_fingerprint": "c" * 64, "merge_source_fingerprint": "d" * 64,
        "backend_executable": {"path": str(Path(tempfile.gettempdir()).resolve() / "candidate with spaces" / "backend.exe"), "state": "file", "sha256": "e" * 64},
        "merge_executable": {"path": "/candidate with spaces/merge", "state": "missing", "sha256": None},
    }
    return {
        "schema": "G4UniversalSimM0TestReport", "version": 2,
        **{key: value["path"] if isinstance(value, dict) else value for key, value in start.items()},
        "candidate_identity": {"version": 1, "binding_strategy": "start_end_content_snapshots",
            "start": start, "end": copy.deepcopy(start), "status": "stable", "drift_fields": [], "errors": []},
    }


def controls() -> list[tuple]:
    cases = []

    def add(name, change=None, *, strict=False, error=None, status="stable"):
        report = fixture()
        if change:
            change(report)
        cases.append((name, report, strict, error, status))

    def drift(report):
        identity = report["candidate_identity"]
        identity["end"]["source_fingerprint"] = "f" * 64
        identity.update(status="drifted", drift_fields=["source_fingerprint"])

    def capture_failure(report):
        identity = report["candidate_identity"]
        identity["end"]["source_fingerprint"] = None
        identity.update(status="unverifiable", drift_fields=["source_fingerprint"],
            errors=[{"phase": "end", "field": "source_fingerprint", "error": "OSError: controlled capture failure"}])

    add("stable")
    add("stable-strict", strict=True)
    add("legacy-compatible", lambda r: r.pop("candidate_identity"), status="legacy/unavailable")
    add("deleted-extension-strict", lambda r: r.pop("candidate_identity"), strict=True, error="candidate_identity missing")
    add("null-extension-compatible", lambda r: r.update(candidate_identity=None), error="candidate_identity must be an object")
    add("null-extension-strict", lambda r: r.update(candidate_identity=None), strict=True, error="candidate_identity must be an object")
    add("unknown-version", lambda r: r["candidate_identity"].update(version=2), error="unknown candidate_identity version")
    add("boolean-version", lambda r: r["candidate_identity"].update(version=True), error="unknown candidate_identity version")
    add("unknown-binding", lambda r: r["candidate_identity"].update(binding_strategy="end_only"), error="binding_strategy")
    add("unknown-status", lambda r: r["candidate_identity"].update(status="passed"), error="unknown candidate_identity status")
    add("claimed-stable-different-ends", lambda r: r["candidate_identity"]["end"].update(source_fingerprint="f" * 64),
        error="drift_fields mismatch")
    add("claimed-stable-recorded-drift", lambda r: (drift(r), r["candidate_identity"].update(status="stable")),
        error="contradicts snapshots/errors")
    add("claimed-stable-with-errors", lambda r: r["candidate_identity"].update(errors=[
        {"phase": "preflight", "field": "backend_executable", "error": "controlled capabilities failure"}]),
        error="contradicts snapshots/errors")
    add("drifted-formal-rejected", drift, strict=True, error="candidate_identity drifted: formal evidence rejected")
    add("drifted-compatible-rejected", drift, error="candidate_identity drifted: formal evidence rejected")
    add("unverifiable-rejected", capture_failure, error="candidate_identity unverifiable: formal evidence rejected")
    add("preflight-unverifiable", lambda r: r["candidate_identity"].update(status="unverifiable", errors=[
        {"phase": "preflight", "field": "backend_executable", "error": "controlled failure"}]),
        error="candidate_identity unverifiable: formal evidence rejected")
    for field in fixture()["candidate_identity"]:
        add(f"missing-extension-{field}", lambda r, field=field: r["candidate_identity"].pop(field),
            error="candidate_identity fields must be exactly")
    for field in fixture()["candidate_identity"]["start"]:
        add(f"top-binding-{field}", lambda r, field=field: r.update({field: "wrong binding"}), error=f"top-level {field} is not bound")
        add(f"top-missing-{field}", lambda r, field=field: r.pop(field), error=f"top-level report missing identity field {field}")
        add(f"start-missing-{field}", lambda r, field=field: r["candidate_identity"]["start"].pop(field),
            error="candidate_identity.start fields must be exactly")
    for phase in ("start", "end"):
        add(f"{phase}-bad-binary-sha", lambda r, phase=phase: r["candidate_identity"][phase]["backend_executable"].update(sha256="short"),
            error=f"{phase}.backend_executable.sha256")
        add(f"{phase}-missing-binary-with-hash", lambda r, phase=phase: r["candidate_identity"][phase]["merge_executable"].update(sha256="a" * 64),
            error="sha256 must be null for state=missing")
        add(f"{phase}-binary-missing-state", lambda r, phase=phase: r["candidate_identity"][phase]["backend_executable"].pop("state"),
            error="fields must be exactly")
        add(f"{phase}-null-without-error", lambda r, phase=phase: r["candidate_identity"][phase].update(source_fingerprint=None),
            error="null value requires a matching capture error")
    add("binary-unknown-state", lambda r: r["candidate_identity"]["start"]["backend_executable"].update(state="unknown"), error="state must be")
    add("binary-relative-path", lambda r: r["candidate_identity"]["start"]["backend_executable"].update(path="relative.exe"), error="path must be absolute")
    add("extra-snapshot-field", lambda r: r["candidate_identity"]["start"].update(ignored="extra"), error="fields must be exactly")
    add("bad-git-hash", lambda r: r["candidate_identity"]["start"].update(git_head="unavailable"), error="Git object hash")
    add("errors-wrong-type", lambda r: r["candidate_identity"].update(errors={}), error="errors must be a list")
    add("bad-error-shape", lambda r: r["candidate_identity"].update(errors=[{"phase": "end"}]), error="errors record fields")
    add("error-with-nonnull-value", lambda r: r["candidate_identity"].update(errors=[
        {"phase": "end", "field": "source_fingerprint", "error": "controlled failure"}]), error="requires a null snapshot value")
    add("unverifiable-with-no-errors", lambda r: r["candidate_identity"].update(status="unverifiable"), error="contradicts snapshots/errors")
    add("drifted-with-no-drift", lambda r: r["candidate_identity"].update(status="drifted"), error="contradicts snapshots/errors")
    add("fake-drift-field", lambda r: r["candidate_identity"].update(drift_fields=["unknown"]), error="drift_fields mismatch")
    add("duplicate-drift-field", lambda r: (drift(r), r["candidate_identity"].update(drift_fields=["source_fingerprint"] * 2)), error="drift_fields mismatch")
    add("report-unknown-version", lambda r: r.update(version=3), error="requires report v2")
    return cases


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def exercise(root: Path) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONOPTIMIZE", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    receipts, function_receipts = [], []
    for name, report, strict, error, expected_status in controls():
        directory = root / name
        directory.mkdir()
        path = directory / "report.json"
        save(path, report)
        try:
            result = validate_candidate_identity(report, require_identity=strict)
        except IdentityContractError as failure:
            function_receipts.append({"case": name, "rejected": True, "diagnostic": str(failure)})
            assert error and error in str(failure), (name, error, str(failure))
        else:
            function_receipts.append({"case": name, "result": asdict(result)})
            assert error is None, (name, error, result)
            assert result.status == expected_status, (name, result)
            assert result.stable == result.available == (expected_status == "stable"), (name, result)
        save(root / "function-receipt.json", function_receipts)
        for mode in ("ordinary", "-O", "PYTHONOPTIMIZE=1"):
            env = environment.copy()
            if mode == "PYTHONOPTIMIZE=1":
                env["PYTHONOPTIMIZE"] = "1"
            command = [sys.executable, "-B", *(["-O"] if mode == "-O" else []), str(HELPER), "--report", str(path)]
            if strict:
                command.append("--require-identity")
            completed = subprocess.run(command, env=env, capture_output=True, timeout=30)
            (directory / f"{mode}.stdout.log").write_bytes(completed.stdout)
            (directory / f"{mode}.stderr.log").write_bytes(completed.stderr)
            expected_exit = 1 if error else 0 if expected_status == "stable" else 2
            output = completed.stdout.decode("utf-8", errors="replace")
            receipts.append({"case": name, "mode": mode, "command": command,
                "pythonoptimize": env.get("PYTHONOPTIMIZE"), "expected_exit": expected_exit,
                "actual_exit": completed.returncode, "expected_diagnostic": error})
            save(root / "subprocess-receipt.json", receipts)
            assert completed.returncode == expected_exit, (name, mode, output, completed.stderr)
            assert not completed.stderr, (name, mode, completed.stderr)
            if error:
                assert "identity contract: REJECT" in output and error in output, (name, mode, output)
            else:
                assert json.loads(output.removeprefix("identity contract: "))["status"] == expected_status
    save(root / "summary.json", {"function_cases": len(function_receipts), "subprocesses": len(receipts),
        "helper_sha256": hashlib.sha256(HELPER.read_bytes()).hexdigest(), "status": "author-self-test-passed"})
    print(f"test_validation_identity_contract: OK ({len(function_receipts)} function controls, {len(receipts)} subprocesses)")


def main() -> int:
    if sys.flags.optimize:
        raise RuntimeError("run the test driver without optimization; its children exercise all three modes")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    requested = args.evidence_dir or os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
    if requested:
        root = Path(requested).resolve()
        if root.is_dir():
            # A runner creates the per-case directory before launching this test.
            root = root / "identity-contract"
        root.mkdir(parents=True, exist_ok=False)
        exercise(root)
    else:
        with tempfile.TemporaryDirectory(prefix="g4usim-identity-contract-") as directory:
            exercise(Path(directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
