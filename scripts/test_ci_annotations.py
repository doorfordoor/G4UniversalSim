#!/usr/bin/env python3
"""Regression for scripts/ci_annotate_failures.py.

The Actions job log of a public repository needs authentication, so the failing
cases are surfaced through ``::error`` annotations on the run page instead. That
only helps when the helper really emits one annotation per failing case, with
the case name, its layer and the tail of its log, and when it stays tolerant of
a missing report (it runs only after the test step already failed).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "ci_annotate_failures.py"


def write_report(root: Path, records: list[dict]) -> Path:
    run_dir = root / "20261028-000000-fixture"
    run_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "G4UniversalSimM0TestReport",
        "version": 2,
        "profile": "all",
        "results": records,
    }
    path = run_dir / "report.json"
    path.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return path


def case(name: str, layer: str, script: str, status: str, log: str) -> dict:
    return {
        "name": name,
        "layer": layer,
        "script": script,
        "status": status,
        "log": log,
    }


def run_helper(report_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(HELPER), "--report-root", str(report_root)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="g4usim-ci-annotate-"))
    try:
        run_dir = workdir / "20261028-000000-fixture"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "pass_case.log").write_bytes(b"PASS pass_case: asserts=3/3\n")
        (run_dir / "fail_case.log").write_bytes(
            b"line one\nqt.qpa.plugin: Could not find the Qt platform plugin\nFAIL fail_case\n"
        )
        (run_dir / "skip_case.log").write_bytes(b"skipped: backend executable is missing\n")
        records = [
            case("pass_case", "static", "scripts/test_a.py", "pass", "pass_case.log"),
            case("fail_case", "integration", "gui/smoke_tests/smoke_b.py", "fail", "fail_case.log"),
            case("skip_case", "backend", "scripts/test_c.py", "skip", "skip_case.log"),
        ]
        write_report(workdir, records)
        result = run_helper(workdir)
        assert result.returncode == 0, f"helper must not fail the build: {result.stderr}"
        assert (
            "annotating 1 failed and 1 skipped case(s)" in result.stdout
        ), result.stdout
        assert "::error title=fail_case::" in result.stdout, result.stdout
        assert "::warning title=skip_case::" in result.stdout, result.stdout
        assert "gui/smoke_tests/smoke_b.py" in result.stdout, result.stdout
        assert "Could not find the Qt platform plugin" in result.stdout, result.stdout
        assert "PASS pass_case" not in result.stdout, "passing cases must stay silent"
        # A missing log is reported inside the annotation, not as a crash.
        (run_dir / "fail_case.log").unlink(missing_ok=True)
        result = run_helper(workdir)
        assert result.returncode == 0, result.stderr
        assert "no log file recorded for this case" in result.stdout, result.stdout

        # No report at all (the step failed before the runner wrote one).
        empty = workdir / "empty"
        empty.mkdir()
        result = run_helper(empty)
        assert result.returncode == 0, result.stderr
        assert "::error::no report.json found under" in result.stdout, result.stdout

        # An archived copy directly inside the root (docs/verification style).
        archived = workdir / "archived"
        archived.mkdir()
        shutil.copy(workdir / "20261028-000000-fixture" / "report.json", archived / "report.json")
        result = run_helper(archived)
        assert result.returncode == 0, result.stderr
        assert "::error title=fail_case::" in result.stdout, result.stdout
        print("test_ci_annotations: OK")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
