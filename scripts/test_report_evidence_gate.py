"""R2-06/07 black-box controls; run the real gate in three interpreter modes.

Usage: python -B scripts/test_report_evidence_gate.py [--evidence-dir NEW_DIRECTORY]
The optional directory preserves every input, command, stdout, stderr and exit code.
This is author regression evidence, not independent acceptance.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/check_report_evidence.py"
PROBE = "settrace_assert_lines_v3"
ALGORITHM = "sha256_raw_bytes_lf_v2"


def save_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def run_controls(root: Path) -> None:
    env = os.environ.copy()
    env.pop("PYTHONOPTIMIZE", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    report = {
        "schema": "G4UniversalSimM0TestReport", "version": 2, "profile": "static",
        "assert_probe": PROBE, "log_digest_algorithm": ALGORITHM,
        "source_fingerprint": "a" * 64, "tests_content_fingerprint": "b" * 64,
        "backend_provenance": "isolated_test_fixture_not_backend_validation",
        "assertions_executed_total": 12, "cases_with_assertion_counts": 2,
        "cases_with_zero_assertions": [], "results": [],
    }
    logs = []
    launches = []
    # Positive logs are emitted by actual assertion-probe subprocesses.
    for name, count in (("one", 7), ("two", 5)):
        source = root / f"fixture_{name}.py"
        source.write_text(f"for value in range({count}):\n    assert value >= 0\n", encoding="utf-8")
        command = [sys.executable, "-B", str(ROOT / "tools/test_assert_probe.py"), str(source)]
        result = subprocess.run(command, env=env, capture_output=True, timeout=30)
        (root / f"probe_{name}.stdout.log").write_bytes(result.stdout)
        (root / f"probe_{name}.stderr.log").write_bytes(result.stderr)
        launches.append({"command": command, "exit_code": result.returncode})
        save_json(root / "probe-launches.json", launches)
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == [f"G4USIM_ASSERTS={count}".encode()], result.stdout
        logs.append(result.stdout)
        report["results"].append({
            "name": name, "script": str(source), "layer": "static", "status": "pass",
            "exit_code": 0, "assertions_executed": count, "assert_sites": 1,
            "assert_probe": PROBE, "log_digest_algorithm": ALGORITHM,
            "log": f"{name}.log", "log_sha256": hashlib.sha256(result.stdout).hexdigest(),
        })

    # Definitions are independent of the gate's parser and validation helpers.
    controls = []

    def add(name, *, change=None, first_log=None, baseline=None, flags=(), error=None,
            crlf=False, legacy_digest=False):
        payload = copy.deepcopy(report)
        contents = list(logs)
        if first_log is not None:
            contents[0] = first_log
        if crlf:
            contents = [data.replace(b"\n", b"\r\n") for data in contents]
        for record, data in zip(payload["results"], contents):
            hashed = data.replace(b"\r\n", b"\n") if legacy_digest else data
            record["log_sha256"] = hashlib.sha256(hashed).hexdigest()
        if change:
            change(payload)
        controls.append((name, payload, contents, baseline, list(flags), error))

    def inflate(payload):
        payload["results"][0]["assertions_executed"] += 100
        payload["assertions_executed_total"] += 100

    add("valid")
    add("valid-crlf", crlf=True)
    add("valid-baseline", baseline=report)
    add("bad-count-synchronized", change=inflate, error="case 'one' assertion count mismatch")
    add("bad-second-count", change=lambda r: (r["results"][1].update(assertions_executed=6),
        r.update(assertions_executed_total=13)), error="case 'two' assertion count mismatch")
    add("bad-sha", change=lambda r: r["results"][0].update(log_sha256="0" * 64),
        error="log digest mismatch for case 'one'")
    add("bad-total", change=lambda r: r.update(assertions_executed_total=13), error="per-case counts sum to")
    add("missing-marker", first_log=b"ordinary output only\n", error="found 0")
    for name, value in (("text", b"no"), ("negative", b"-7"), ("signed", b"+7"),
                        ("float", b"7.0"), ("empty", b""), ("space", b"7 "),
                        ("unicode", "７".encode()), ("huge", b"7" * 5000)):
        add(f"invalid-{name}", first_log=b"G4USIM_ASSERTS=" + value + b"\n", error="malformed G4USIM_ASSERTS")
    add("indented-marker", first_log=b" G4USIM_ASSERTS=7\n", error="malformed G4USIM_ASSERTS")
    add("damaged-marker", first_log=b"G4USIM_ASSERTS:7\n", error="malformed G4USIM_ASSERTS")
    for name, extra in (("identical", b"G4USIM_ASSERTS=7\n"), ("different", b"G4USIM_ASSERTS=8\n"),
                        ("malformed", b"G4USIM_ASSERTS=bad\n")):
        add(f"duplicate-{name}", first_log=logs[0] + extra, error="found 2")
    add("wrong-schema", change=lambda r: r.update(schema="other"), error="unexpected report schema")
    add("old-version", change=lambda r: r.update(version=1), error="predates assertion-level evidence")
    add("bad-fingerprint", change=lambda r: r.update(source_fingerprint="bad"), error="source_fingerprint")
    add("disabled-probe", change=lambda r: r.update(assert_probe="disabled"), error="assert probe is disabled")
    for status in ("fail", "skip"):
        change = lambda r, status=status: r["results"][1].update(status=status, exit_code=1)
        add(f"{status}-release", change=change, error="did not pass")
        add(f"{status}-triage", change=change, flags=("--allow-incomplete",))
    def skip_missing(payload):
        record = payload["results"][1]
        record.update(status="skip", reason="controlled missing prerequisite")
        record.pop("exit_code")
        record.pop("assertions_executed")
        payload.update(assertions_executed_total=7, cases_with_assertion_counts=1)
    add("skip-without-count-triage", change=skip_missing, flags=("--allow-incomplete",))
    add("bad-count-triage", change=inflate, flags=("--allow-incomplete",), error="assertion count mismatch")
    baseline = copy.deepcopy(report)
    baseline.update(assertions_executed_total=13)
    baseline["results"][0].update(assertions_executed=8)
    add("baseline-total-regression", baseline=baseline, error="assertion evidence regressed")
    baseline = copy.deepcopy(report)
    baseline["results"][0].update(assertions_executed=8)
    baseline["results"][1].update(assertions_executed=4)
    add("baseline-case-regression", baseline=baseline, error="per-case assertion counts regressed")
    baseline = copy.deepcopy(report)
    baseline["results"].append(dict(report["results"][0], name="missing", assertions_executed=0))
    add("baseline-missing-case", baseline=baseline, error="missing now")
    baseline = dict(report, schema="other")
    add("baseline-wrong-schema", baseline=baseline, error="baseline report has an unexpected schema")
    baseline = dict(report, assert_probe="settrace_assert_lines_v2")
    add("baseline-wrong-probe", baseline=baseline, error="cross-probe baseline")
    for probe in ("settrace_assert_lines_v1", "settrace_assert_lines_v2"):
        def legacy_probe(payload, probe=probe):
            payload["assert_probe"] = probe
            for record in payload["results"]:
                record["assert_probe"] = probe
        add(f"{probe}-default", change=legacy_probe, error="--allow-legacy-probe")
        add(f"{probe}-explicit", change=legacy_probe, flags=("--allow-legacy-probe",))
        add(f"{probe}-missing-marker", change=legacy_probe, first_log=b"no marker\n",
            flags=("--allow-legacy-probe",), error="found 0")
    legacy = lambda r: r.pop("log_digest_algorithm")
    add("legacy-digest-default", change=legacy, crlf=True, legacy_digest=True, error="--allow-legacy-digest")
    add("legacy-digest-explicit", change=legacy, crlf=True, legacy_digest=True, flags=("--allow-legacy-digest",))
    add("legacy-digest-missing-marker", change=legacy, first_log=b"no marker\n", crlf=True,
        legacy_digest=True, flags=("--allow-legacy-digest",), error="found 0")

    receipts = []
    for name, payload, contents, baseline, flags, error in controls:
        directory = root / name
        directory.mkdir()
        path = directory / "report.json"
        save_json(path, payload)
        for record, data in zip(payload["results"], contents):
            (directory / record["log"]).write_bytes(data)
        options = ["--report", str(path), *flags]
        if baseline is not None:
            baseline_path = directory / "baseline.json"
            save_json(baseline_path, baseline)
            options += ["--baseline", str(baseline_path)]
        for mode in ("ordinary", "-O", "PYTHONOPTIMIZE=1"):
            mode_env = env.copy()
            if mode == "PYTHONOPTIMIZE=1":
                mode_env["PYTHONOPTIMIZE"] = "1"
            command = [sys.executable, "-B", *(["-O"] if mode == "-O" else []), str(GATE), *options]
            completed = subprocess.run(command, env=mode_env, capture_output=True, timeout=30)
            (directory / f"{mode}.stdout.log").write_bytes(completed.stdout)
            (directory / f"{mode}.stderr.log").write_bytes(completed.stderr)
            output = completed.stdout.decode("utf-8", errors="replace")
            expected_exit = 1 if error else 0
            receipts.append({"case": name, "mode": mode, "command": command,
                "pythonoptimize": mode_env.get("PYTHONOPTIMIZE"), "exit_code": completed.returncode,
                "expected_exit_code": expected_exit, "expected_diagnostic": error,
                "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            save_json(root / "subprocess-receipt.json", receipts)
            assert completed.returncode == expected_exit, (name, mode, completed.stdout, completed.stderr)
            assert ("report evidence: FAIL" if error else "report evidence: OK") in output, (name, mode, output)
            assert error is None or error in output, (name, mode, error, output)
            assert not completed.stderr, (name, mode, completed.stderr)
    # Static check supplements (never substitutes for) the real optimized children.
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(ast.parse(GATE.read_text(encoding="utf-8"))))
    save_json(root / "summary.json", {"controls": len(controls), "subprocesses": len(receipts),
        "passed": len(receipts), "gate_sha256": hashlib.sha256(GATE.read_bytes()).hexdigest(),
        "boundary": "author self-test only; independent review and identity-field integration pending"})
    print(f"test_report_evidence_gate: OK ({len(controls)} controls, {len(receipts)} real gate subprocesses)")


def main() -> int:
    if sys.flags.optimize:
        raise RuntimeError("run this test driver without optimization; it tests optimized gate subprocesses itself")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, help="new directory for retained subprocess evidence")
    args = parser.parse_args()
    if args.evidence_dir:
        root = args.evidence_dir.resolve()
        root.mkdir(parents=True, exist_ok=False)
        run_controls(root)
    else:
        with tempfile.TemporaryDirectory(prefix="g4usim-evidence-gate-") as directory:
            run_controls(Path(directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
