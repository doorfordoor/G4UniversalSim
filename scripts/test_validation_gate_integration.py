"""Exercise runner -> report -> formal gate, including downgrade attempts.

Uses one real, cheap static case, never Geant4. All mutations are copies of
the resulting report. Optimized children must reject the same invalid evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def exercise(root: Path) -> None:
    env = os.environ.copy()
    env.pop("PYTHONOPTIMIZE", None)
    # The nested runner owns its own evidence directory.
    env.pop("G4USIM_TEST_EVIDENCE_DIR", None)
    command = [sys.executable, "-B", str(ROOT / "scripts/run_m0_tests.py"),
               "--profile", "static", "--case", "agent_session", "--fail-on-skip",
               "--executable", str(root / "unused-backend"),
               "--merge-executable", str(root / "unused-merge"),
               "--report-root", str(root / "runner")]
    run = subprocess.run(command, env=env, capture_output=True, timeout=180)
    (root / "runner.stdout.log").write_bytes(run.stdout)
    (root / "runner.stderr.log").write_bytes(run.stderr)
    save(root / "runner-process.json", {"command": command, "exit_code": run.returncode})
    assert run.returncode == 0, (run.stdout, run.stderr)
    reports = list((root / "runner").glob("*/report.json"))
    assert len(reports) == 1
    original = reports[0]
    report = json.loads(original.read_text(encoding="utf-8"))
    assert report["candidate_identity"]["status"] == "stable"
    assert report["results"][0]["status"] == "pass"

    def drift(r):
        identity = r["candidate_identity"]
        current = identity["start"]["source_fingerprint"]
        identity["end"]["source_fingerprint"] = ("0" if current[0] != "0" else "1") + current[1:]
        identity.update(status="drifted", drift_fields=["source_fingerprint"])

    def unverifiable(r):
        identity = r["candidate_identity"]
        identity["end"]["source_fingerprint"] = None
        identity.update(status="unverifiable", drift_fields=["source_fingerprint"], errors=[
            {"phase": "end", "field": "source_fingerprint", "error": "controlled read failure"}])

    def inflate(r):
        r["results"][0]["assertions_executed"] += 1
        r["assertions_executed_total"] += 1

    controls = [
        ("stable", None, True, None),
        ("stable-compatible", None, False, None),
        ("deleted-extension", lambda r: r.pop("candidate_identity"), True, "candidate_identity missing"),
        ("legacy-compatible", lambda r: r.pop("candidate_identity"), False, None),
        ("null-extension", lambda r: r.update(candidate_identity=None), False, "must be an object"),
        ("drift-strict", drift, True, "formal evidence rejected"),
        ("drift-compatible", drift, False, "formal evidence rejected"),
        ("forged-stable", lambda r: (drift(r), r["candidate_identity"].update(status="stable")), True, "contradicts snapshots"),
        ("unverifiable", unverifiable, True, "formal evidence rejected"),
        ("top-level-mismatch", lambda r: r.update(git_head="f" * 40), True, "not bound"),
        ("bad-count", inflate, True, "assertion count mismatch"),
        ("bad-sha", lambda r: r["results"][0].update(log_sha256="0" * 64), True, "log digest mismatch"),
    ]
    receipts = []
    for name, mutate, strict, error in controls:
        directory = root / name
        shutil.copytree(original.parent, directory)
        payload = copy.deepcopy(report)
        if mutate:
            mutate(payload)
        path = directory / "report.json"
        save(path, payload)
        for mode in ("normal", "opt-flag", "opt-env"):
            child_env = env.copy()
            if mode == "opt-env":
                child_env["PYTHONOPTIMIZE"] = "1"
            argv = [sys.executable, "-B", *(["-O"] if mode == "opt-flag" else []),
                    str(ROOT / "scripts/check_report_evidence.py"), "--report", str(path),
                    *(["--require-candidate-identity"] if strict else [])]
            child = subprocess.run(argv, env=child_env, capture_output=True, timeout=30)
            (directory / f"{mode}.stdout.log").write_bytes(child.stdout)
            (directory / f"{mode}.stderr.log").write_bytes(child.stderr)
            receipts.append({"case": name, "mode": mode, "command": argv,
                             "exit_code": child.returncode, "expected_exit": 1 if error else 0,
                             "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            save(root / "gate-processes.json", receipts)
            output = child.stdout.decode("utf-8", errors="replace")
            assert child.returncode == (1 if error else 0), (name, mode, output, child.stderr)
            assert not child.stderr, (name, mode, child.stderr)
            if error:
                assert error in output, (name, mode, output)
            else:
                assert "report evidence: OK" in output
                assert ("legacy/unavailable" if name == "legacy-compatible" else "candidate identity: stable") in output
    # Actual release workflows must opt into the protocol; deleting the extension
    # can only enter explicit legacy review, never the formal CI route.
    for name in ("m0-static-gui.yml", "linux-geant4.yml"):
        lines = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8").splitlines()
        gates = [line for line in lines if "scripts/check_report_evidence.py" in line and not line.lstrip().startswith("#")]
        assert gates, name
        assert all("--require-candidate-identity" in line for line in gates), (name, gates)
    save(root / "summary.json", {"controls": len(controls), "gate_subprocesses": len(receipts),
                               "runner_exit": run.returncode, "status": "pass"})
    print(f"validation gate integration: OK ({len(receipts)} gate subprocesses)")


def main() -> None:
    if sys.flags.optimize:
        raise RuntimeError("run driver without optimization; children exercise optimized gates")
    evidence = os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
    if evidence:
        root = Path(evidence) / "integration"
        root.mkdir(parents=True, exist_ok=False)
        exercise(root)
    else:
        with tempfile.TemporaryDirectory(prefix="arv-integration-") as directory:
            exercise(Path(directory))


if __name__ == "__main__":
    main()
