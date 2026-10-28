"""Contract checks for the assertion-level evidence gate on regression reports.

The gate is only useful if it rejects the failure modes it claims to catch, so every
check below is exercised as a negative case: a tampered report must fail, with the
matching diagnostic, instead of passing because "the totals looked plausible".
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from check_report_evidence import (
    LOG_DIGEST_ALGORITHM,
    PROBE_ID,
    find_latest_report,
    log_digest,
    resolve_log,
    validate_report,
)

ROOT = Path(__file__).resolve().parents[1]


def case_payload(name: str, layer: str, count: int, status: str = "pass") -> dict:
    return {
        "name": name,
        "layer": layer,
        "script": f"scripts/test_{name}.py",
        "status": status,
        "exit_code": 0 if status == "pass" else 1,
        "assertions_executed": count,
        "assert_sites": count,
        "assert_probe": PROBE_ID,
        "log_digest_algorithm": LOG_DIGEST_ALGORITHM,
        # ``write_logs`` replaces both once real log bytes exist. An empty path means
        # "no file next to the report", which the gate then only format-checks.
        "log": "",
        "log_sha256": "e" * 64,
    }


def sample_report() -> dict:
    return {
        "schema": "G4UniversalSimM0TestReport",
        "version": 2,
        "profile": "all",
        "assert_probe": PROBE_ID,
        "log_digest_algorithm": LOG_DIGEST_ALGORITHM,
        "source_fingerprint": "a" * 64,
        "tests_content_fingerprint": "b" * 64,
        "backend_provenance": "source_sha256_manifest_matches_executable",
        "assertions_executed_total": 12,
        "cases_with_assertion_counts": 2,
        "cases_with_zero_assertions": [],
        "results": [
            case_payload("one", "static", 7),
            case_payload("two", "backend", 5),
        ],
    }


def write_logs(report: dict, directory: Path) -> None:
    """Create log files whose bytes match the digests in ``report``."""
    for index, record in enumerate(report["results"]):
        text = f"{record['name']} log\nassertions executed {record['assertions_executed']}\n"
        data = text.encode("utf-8")
        target = directory / (
            Path(f"{record['name']}.log") if index % 2 == 0 else Path("logs") / f"{record['name']}.log"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        record["log"] = str(directory / f"{record['name']}.log")
        record["log_sha256"] = hashlib.sha256(data).hexdigest()


def expect_rejected(report: dict, needle: str, *, report_path: Path | None = None, **options) -> None:
    try:
        validate_report(report, report_path=report_path, **options)
    except AssertionError as error:
        assert needle in str(error), f"expected {needle!r} in rejection message, got: {error}"
    else:
        raise AssertionError(f"report should have been rejected because of {needle!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="g4usim-evidence-") as directory:
        root = Path(directory)
        report_path = root / "run" / "report.json"
        report_path.parent.mkdir(parents=True)
        report = sample_report()
        write_logs(report, report_path.parent)
        validate_report(report, report_path=report_path)
        assert resolve_log(report["results"][0], report_path) is not None
        assert resolve_log(report["results"][1], report_path) is not None, "logs/ fallback must resolve"
        assert log_digest(report_path.parent / "one.log", legacy=False)

        version_one = sample_report()
        version_one["version"] = 1
        expect_rejected(version_one, "predates assertion-level evidence")

        no_probe = sample_report()
        no_probe["assert_probe"] = "disabled"
        expect_rejected(no_probe, "assert probe is disabled")

        legacy_probe = sample_report()
        legacy_probe["assert_probe"] = "settrace_assert_lines_v1"
        expect_rejected(legacy_probe, "archived reports need --allow-legacy-probe")
        validate_report(legacy_probe, allow_legacy_probe=True)

        missing_algorithm = sample_report()
        missing_algorithm.pop("log_digest_algorithm")
        expect_rejected(missing_algorithm, "archived reports need --allow-legacy-digest")

        # The historical defect: digest taken over LF text while the file had CRLF.
        legacy = sample_report()
        legacy.pop("log_digest_algorithm")
        for record in legacy["results"]:
            target = report_path.parent / f"{record['name']}.log"
            raw = f"legacy log for {record['name']}\n".encode("utf-8")
            target.write_bytes(raw.replace(b"\n", b"\r\n"))
            record["log"] = str(target)
            record["log_sha256"] = hashlib.sha256(raw).hexdigest()
        expect_rejected(legacy, "archived reports need --allow-legacy-digest", report_path=report_path)
        validate_report(legacy, report_path=report_path, allow_legacy_digest=True)

        bad_fingerprint = sample_report()
        bad_fingerprint["tests_content_fingerprint"] = "short"
        expect_rejected(bad_fingerprint, "tests_content_fingerprint")

        no_provenance = sample_report()
        no_provenance["backend_provenance"] = ""
        expect_rejected(no_provenance, "backend provenance is missing")

        bad_profile = sample_report()
        bad_profile["profile"] = "nightly"
        expect_rejected(bad_profile, "unknown test profile")

        # Per-case count 0 on a passing case (the exact tamper Astra demonstrated).
        zero_case = sample_report()
        zero_case["results"][0]["assertions_executed"] = 0
        zero_case["assertions_executed_total"] = sum(
            record["assertions_executed"] for record in zero_case["results"]
        )
        zero_case["cases_with_zero_assertions"] = ["one"]
        expect_rejected(zero_case, "executed no assertions")

        sum_mismatch = sample_report()
        sum_mismatch["assertions_executed_total"] = 999999
        expect_rejected(sum_mismatch, "per-case counts sum to")

        count_mismatch = sample_report()
        count_mismatch["cases_with_assertion_counts"] = 1
        expect_rejected(count_mismatch, "case record(s) carry a count")

        zero_list_mismatch = sample_report()
        zero_list_mismatch["cases_with_zero_assertions"] = ["one"]
        expect_rejected(zero_list_mismatch, "cases_with_zero_assertions is")

        no_count = sample_report()
        del no_count["results"][0]["assertions_executed"]
        no_count["assertions_executed_total"] = 5
        no_count["cases_with_assertion_counts"] = 1
        expect_rejected(no_count, "has no assertion count")

        no_sites = sample_report()
        no_sites["results"][0]["assert_sites"] = "many"
        expect_rejected(no_sites, "malformed assert site count")

        zero_exit = sample_report()
        zero_exit["results"][0]["exit_code"] = 3
        expect_rejected(zero_exit, "has exit_code 3")

        tampered_digest = sample_report()
        write_logs(tampered_digest, report_path.parent)
        tampered_digest["results"][0]["log_sha256"] = "0" * 64
        expect_rejected(tampered_digest, "log digest mismatch", report_path=report_path)

        missing_digest = sample_report()
        missing_digest["results"][1]["log_sha256"] = "not-a-digest"
        expect_rejected(missing_digest, "no 64-character lowercase log digest")

        missing_log = sample_report()
        write_logs(missing_log, report_path.parent)
        (report_path.parent / "two.log").unlink(missing_ok=True)
        (report_path.parent / "logs" / "two.log").unlink(missing_ok=True)
        expect_rejected(missing_log, "cannot be found", report_path=report_path)

        failing = sample_report()
        write_logs(failing, report_path.parent)
        failing["results"][1]["status"] = "fail"
        expect_rejected(failing, "did not pass", report_path=report_path)
        validate_report(failing, report_path=report_path, allow_incomplete=True)

        skipped = sample_report()
        write_logs(skipped, report_path.parent)
        skipped["results"][1]["status"] = "skip"
        expect_rejected(skipped, "did not pass", report_path=report_path)

        duplicate = sample_report()
        duplicate["results"][1]["name"] = "one"
        expect_rejected(duplicate, "duplicate case names")

        bad_layer = sample_report()
        bad_layer["results"][1]["layer"] = "unit"
        expect_rejected(bad_layer, "unknown layer")

        # Baseline: total regression, missing case, and per-case regression.
        baseline = sample_report()
        regressed_total = sample_report()
        write_logs(regressed_total, report_path.parent)
        regressed_total["results"][0]["assertions_executed"] = 4
        regressed_total["assertions_executed_total"] = 9
        expect_rejected(regressed_total, "assertion evidence regressed", report_path=report_path,
                        baseline=baseline)

        # Total rose, one case fell: only the per-case floor can catch this.
        regressed_case = sample_report()
        write_logs(regressed_case, report_path.parent)
        regressed_case["results"][0]["assertions_executed"] = 1
        regressed_case["results"][1]["assertions_executed"] = 20
        regressed_case["assertions_executed_total"] = 21
        expect_rejected(regressed_case, "per-case assertion counts regressed", report_path=report_path,
                        baseline=baseline)

        dropped_case = sample_report()
        write_logs(dropped_case, report_path.parent)
        dropped = {"schema": baseline["schema"], "assertions_executed_total": 12,
                   "results": baseline["results"] + [case_payload("three", "gui", 0)]}
        expect_rejected(dropped_case, "missing now", report_path=report_path, baseline=dropped)

        # CLI surface: OK, rejection, latest-report discovery, baseline pass, missing report.
        cli_report = report_path
        cli_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        command = [sys.executable, "-B", str(ROOT / "scripts/check_report_evidence.py")]
        completed = subprocess.run(command + ["--report", str(cli_report)], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", check=False)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "report evidence: OK" in completed.stdout
        assert "digest sha256_raw_bytes_lf_v2" in completed.stdout, completed.stdout

        baseline_path = root / "baseline.json"
        baseline_path.write_text(json.dumps(sample_report(), indent=2), encoding="utf-8")
        completed = subprocess.run(command + ["--report", str(cli_report), "--baseline", str(baseline_path)],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   check=False)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "baseline 12 assertions" in completed.stdout

        bad_path = root / "bad.json"
        bad_path.write_text(json.dumps(version_one, indent=2), encoding="utf-8")
        completed = subprocess.run(command + ["--report", str(bad_path)], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", check=False)
        assert completed.returncode == 1
        assert "report evidence: FAIL" in completed.stdout

        newer = root / "20260102-000000-bbbbbbbb"
        older = root / "20260101-000000-aaaaaaaa"
        newer.mkdir()
        older.mkdir()
        (older / "report.json").write_text(json.dumps(sample_report()), encoding="utf-8")
        newer_report = newer / "report.json"
        newer_report.write_text(json.dumps(sample_report()), encoding="utf-8")
        assert find_latest_report(root) == newer_report, "newest report folder must win"

        empty_root = root / "empty"
        empty_root.mkdir()
        completed = subprocess.run(command + ["--report-root", str(empty_root)], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", check=False)
        assert completed.returncode == 1
        assert "no report.json found" in completed.stdout

    print("test_report_evidence: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
