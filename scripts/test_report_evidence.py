"""Contract checks for the assertion-level evidence gate on regression reports."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from check_report_evidence import find_latest_report, validate_report

ROOT = Path(__file__).resolve().parents[1]


def sample_report() -> dict:
    return {
        "schema": "G4UniversalSimM0TestReport",
        "version": 2,
        "assert_probe": "settrace_assert_lines_v2",
        "source_fingerprint": "a" * 64,
        "tests_content_fingerprint": "b" * 64,
        "backend_provenance": "source_sha256_manifest_matches_executable",
        "assertions_executed_total": 12,
        "cases_with_assertion_counts": 2,
        "cases_with_zero_assertions": [],
        "results": [
            {"name": "one", "layer": "static", "script": "scripts/one.py", "status": "pass",
             "assertions_executed": 7, "assert_sites": 5, "log_sha256": "c" * 64},
            {"name": "two", "layer": "backend", "script": "scripts/two.py", "status": "pass",
             "assertions_executed": 5, "assert_sites": 5, "log_sha256": "d" * 64},
        ],
    }


def expect_rejected(report: dict, needle: str) -> None:
    try:
        validate_report(report)
    except AssertionError as error:
        assert needle in str(error), f"unexpected rejection message: {error}"
    else:
        raise AssertionError(f"report should have been rejected because of {needle!r}")


def main() -> int:
    good = sample_report()
    validate_report(good)

    legacy = sample_report()
    legacy["version"] = 1
    expect_rejected(legacy, "predates assertion-level evidence")

    empty = sample_report()
    empty["assertions_executed_total"] = 0
    expect_rejected(empty, "executed no assertions")

    missing_digest = sample_report()
    missing_digest["tests_content_fingerprint"] = "short"
    expect_rejected(missing_digest, "tests_content_fingerprint")

    missing_count = sample_report()
    del missing_count["results"][0]["assertions_executed"]
    expect_rejected(missing_count, "no assertion count")

    missing_log = sample_report()
    del missing_log["results"][1]["log_sha256"]
    expect_rejected(missing_log, "no log digest")

    no_provenance = sample_report()
    no_provenance["backend_provenance"] = ""
    expect_rejected(no_provenance, "backend provenance is missing")

    with tempfile.TemporaryDirectory(prefix="g4usim-report-") as directory:
        root = Path(directory)
        older = root / "20260101-000000-aaaaaaaa"
        newer = root / "20260102-000000-bbbbbbbb"
        older.mkdir()
        newer.mkdir()
        (older / "report.json").write_text(json.dumps(sample_report()), encoding="utf-8")
        older.touch()
        latest = newer / "report.json"
        latest.write_text(json.dumps(sample_report()), encoding="utf-8")
        assert find_latest_report(root) == latest, "newest report folder must win"
        cli = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/check_report_evidence.py"), "--report", str(latest)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        assert cli.returncode == 0, cli.stdout + cli.stderr
        assert "report evidence: OK" in cli.stdout
        rejected = newer / "bad.json"
        legacy_doc = sample_report()
        legacy_doc["version"] = 1
        rejected.write_text(json.dumps(legacy_doc), encoding="utf-8")
        cli = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/check_report_evidence.py"), "--report", str(rejected)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        assert cli.returncode == 1
        assert "FAIL" in cli.stdout
        empty_root = root / "empty"
        empty_root.mkdir()
        cli = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/check_report_evidence.py"), "--report-root", str(empty_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        assert cli.returncode == 1
        assert "no report.json found" in cli.stdout
    print("test_report_evidence: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
