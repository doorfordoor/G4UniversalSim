#!/usr/bin/env python3
"""Validate that a regression report carries assertion-level, fingerprint-tied evidence.

``scripts/run_m0_tests.py`` writes ``report.json`` (schema version 2) with per-case
assertion counts, a compiled-source fingerprint and a test/fixture content
fingerprint. This gate exists so CI cannot go green on a report that lost those
fields, silently regressed to "one PASS per script process" evidence, or ran zero
assertions in total.

Usage::

    python -B scripts/check_report_evidence.py [--report PATH] [--report-root DIR]

Without ``--report`` the newest ``report.json`` under ``out/verification`` is used.
The check only proves the report is *self-describing*; it does not prove physics,
and it does not re-run any case.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPORT_SCHEMA = "G4UniversalSimM0TestReport"
MIN_VERSION = 2


def find_latest_report(report_root: Path) -> Path:
    candidates = sorted(report_root.glob("*/report.json"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        raise AssertionError(f"no report.json found under {report_root}")
    return candidates[-1]


def validate_report(report: dict) -> None:
    """Raise AssertionError when the report cannot support its own claims."""
    assert report.get("schema") == REPORT_SCHEMA, f"unexpected report schema: {report.get('schema')!r}"
    assert int(report.get("version", 0)) >= MIN_VERSION, (
        f"report version {report.get('version')!r} predates assertion-level evidence (need >= {MIN_VERSION})"
    )
    assert report.get("assert_probe") in ("settrace_assert_lines_v1", "settrace_assert_lines_v2", "disabled"), (
        f"unknown assert probe: {report.get('assert_probe')!r}"
    )
    total = report.get("assertions_executed_total")
    assert isinstance(total, int) and total > 0, (
        "report executed no assertions; a green run without assertion evidence is not reviewable"
    )
    counted = report.get("cases_with_assertion_counts")
    assert isinstance(counted, int) and counted > 0, "no case reported an assertion count"
    for key in ("source_fingerprint", "tests_content_fingerprint"):
        value = report.get(key)
        assert isinstance(value, str) and len(value) == 64, f"{key} is missing or malformed: {value!r}"
    results = report.get("results")
    assert isinstance(results, list) and results, "report contains no case results"
    for record in results:
        for key in ("name", "layer", "script", "status"):
            assert key in record, f"case record {record.get('name')!r} lacks {key!r}"
        assert record["status"] in ("pass", "fail", "skip"), record
        if record["status"] == "pass":
            assert "assertions_executed" in record or report.get("assert_probe") == "disabled", (
                f"passing case {record['name']!r} has no assertion count"
            )
            assert record.get("log_sha256"), f"passing case {record['name']!r} has no log digest"
    assert report.get("backend_provenance"), "backend provenance is missing"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate assertion-level evidence in a regression report.")
    parser.add_argument("--report", type=Path, help="report.json to validate")
    parser.add_argument("--report-root", type=Path, help="root that contains timestamped report folders")
    args = parser.parse_args(argv)
    if args.report:
        path = args.report
    else:
        root = args.report_root or Path(__file__).resolve().parents[1] / "out" / "verification"
        try:
            path = find_latest_report(root)
        except AssertionError as error:
            print(f"report evidence: {error}")
            return 1
    report = json.loads(path.read_text(encoding="utf-8"))
    try:
        validate_report(report)
    except AssertionError as error:
        print(f"report evidence: FAIL {path}\n  {error}")
        return 1
    print(
        f"report evidence: OK {path}\n"
        f"  version {report['version']}, {len(report['results'])} cases, "
        f"{report['assertions_executed_total']} assertions executed, "
        f"source {report['source_fingerprint'][:12]}..., tests {report['tests_content_fingerprint'][:12]}..."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
