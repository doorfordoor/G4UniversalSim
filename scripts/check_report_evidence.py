#!/usr/bin/env python3
"""Validate that a regression report carries self-consistent, tamper-evident evidence.

``scripts/run_m0_tests.py`` writes ``report.json`` (schema version 2) with per-case
assertion counts, per-case log digests, a compiled-source fingerprint and a
test/fixture content fingerprint. This gate exists so CI cannot go green on a report
that lost those fields, silently regressed to "one PASS per script process" evidence,
executed zero assertions, or was edited after the fact.

The gate checks, in order:

* schema/version, probe id, digest algorithm, fingerprints and provenance;
* every case record is complete, uniquely named and on a known layer;
* a release report has no failing or skipped case;
* every passing case executed at least one assertion and exists with ``exit_code 0``;
* per-case assertion counts sum to ``assertions_executed_total``;
* ``cases_with_assertion_counts`` / ``cases_with_zero_assertions`` match the records;
* every ``log_sha256`` matches the bytes of the log file on disk (resolved next to the
  report or under ``logs/``), not merely "is a string";
* optionally (``--baseline``) totals and per-case counts did not regress.

Archived reports written before the digest fix hashed the in-memory LF text while the
file was stored with CRLF, so they can only be verified with ``--allow-legacy-digest``
(which re-hashes the file after CRLF -> LF normalization) and are rejected by default.

Usage::

    python -B scripts/check_report_evidence.py [--report PATH] [--report-root DIR]
        [--baseline PATH] [--allow-legacy-digest] [--allow-legacy-probe]
        [--allow-incomplete]

Without ``--report`` the newest ``report.json`` under ``out/verification`` is used.
The check proves the report and its logs are internally consistent; it does not prove
physics and it does not re-run any case.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPORT_SCHEMA = "G4UniversalSimM0TestReport"
MIN_VERSION = 2
PROBE_ID = "settrace_assert_lines_v2"
LEGACY_PROBE_IDS = ("settrace_assert_lines_v1",)
LOG_DIGEST_ALGORITHM = "sha256_raw_bytes_lf_v2"
LAYERS = ("static", "gui", "backend", "integration")
PROFILES = ("all", "static", "gui", "backend", "integration")
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


def find_latest_report(report_root: Path) -> Path:
    candidates = sorted(report_root.glob("*/report.json"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        raise AssertionError(f"no report.json found under {report_root}")
    return candidates[-1]


def log_digest(path: Path, *, legacy: bool) -> str:
    """Digest of the bytes a reviewer reads from disk; ``legacy`` also tries CRLF->LF."""
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if legacy and path.read_bytes().find(b"\r\n") >= 0:
        canonical = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        return canonical
    return digest


def resolve_log(record: dict, report_path: Path) -> Path | None:
    """Find the log file for a case, allowing evidence copies to relocate it."""
    log = record.get("log")
    if not isinstance(log, str) or not log:
        return None
    candidates = [Path(log)]
    name = Path(log).name
    report_dir = report_path.parent
    candidates.extend([report_dir / name, report_dir / "logs" / name])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def validate_report(
    report: dict,
    *,
    report_path: Path | None = None,
    allow_legacy_digest: bool = False,
    allow_legacy_probe: bool = False,
    allow_incomplete: bool = False,
    baseline: dict | None = None,
) -> None:
    """Raise AssertionError when the report cannot support its own claims."""
    assert report.get("schema") == REPORT_SCHEMA, f"unexpected report schema: {report.get('schema')!r}"
    version = report.get("version")
    assert isinstance(version, int) and version >= MIN_VERSION, (
        f"report version {version!r} predates assertion-level evidence (need >= {MIN_VERSION})"
    )
    probe = report.get("assert_probe")
    assert probe != "disabled", "assert probe is disabled; a report without executed assertions is not evidence"
    allowed_probes = (PROBE_ID,) if not allow_legacy_probe else (PROBE_ID,) + LEGACY_PROBE_IDS
    assert probe in allowed_probes, (
        f"unknown assert probe: {probe!r} (current is {PROBE_ID!r}; "
        f"archived reports need --allow-legacy-probe)"
    )
    algorithm = report.get("log_digest_algorithm")
    if not allow_legacy_digest:
        assert algorithm == LOG_DIGEST_ALGORITHM, (
            f"log digest algorithm {algorithm!r} is not {LOG_DIGEST_ALGORITHM!r}; "
            f"archived reports need --allow-legacy-digest"
        )
    assert report.get("profile") in PROFILES, f"unknown test profile: {report.get('profile')!r}"
    for key in ("source_fingerprint", "tests_content_fingerprint"):
        value = report.get(key)
        assert isinstance(value, str) and HEX64.match(value), (
            f"{key} is missing or not a 64-character lowercase sha256: {value!r}"
        )
    assert report.get("backend_provenance"), "backend provenance is missing"

    results = report.get("results")
    assert isinstance(results, list) and results, "report contains no case results"

    names = []
    for record in results:
        assert isinstance(record, dict), f"case record is not an object: {record!r}"
        for key in ("name", "layer", "script", "status", "exit_code"):
            assert key in record, f"case record {record.get('name')!r} lacks {key!r}"
        assert isinstance(record["name"], str) and record["name"], f"case record has no usable name: {record!r}"
        assert isinstance(record["script"], str) and record["script"], f"case {record['name']!r} has no script"
        assert record["layer"] in LAYERS, f"case {record['name']!r} has unknown layer {record['layer']!r}"
        assert record["status"] in ("pass", "fail", "skip"), (
            f"case {record['name']!r} has unknown status {record['status']!r}"
        )
        names.append(record["name"])
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"duplicate case names: {duplicates}"

    non_pass = [record["name"] for record in results if record["status"] != "pass"]
    if non_pass and not allow_incomplete:
        assert not non_pass, (
            f"report is not release evidence: {len(non_pass)} case(s) did not pass ({non_pass[:5]}); "
            f"pass --allow-incomplete only for triage"
        )

    executed = [record for record in results if isinstance(record.get("assertions_executed"), int)]
    for record in results:
        if record["status"] != "pass":
            continue
        assert isinstance(record.get("exit_code"), int) and record["exit_code"] == 0, (
            f"passing case {record['name']!r} has exit_code {record.get('exit_code')!r}"
        )
        count = record.get("assertions_executed")
        assert isinstance(count, int), f"passing case {record['name']!r} has no assertion count"
        assert count >= 1, (
            f"passing case {record['name']!r} executed no assertions; a PASS without assertion evidence "
            f"is only an exit code"
        )
        sites = record.get("assert_sites")
        assert isinstance(sites, int) and sites >= 0, (
            f"passing case {record['name']!r} has a malformed assert site count: {sites!r}"
        )
        digest = record.get("log_sha256")
        assert isinstance(digest, str) and HEX64.match(digest), (
            f"passing case {record['name']!r} has no 64-character lowercase log digest"
        )
        if report_path is not None:
            log_path = resolve_log(record, report_path)
            assert log_path is not None, (
                f"log for passing case {record['name']!r} cannot be found next to {report_path}"
            )
            actual = log_digest(log_path, legacy=allow_legacy_digest)
            assert actual == digest, (
                f"log digest mismatch for case {record['name']!r}: report says {digest}, "
                f"file {log_path} hashes to {actual}"
            )
        else:
            log_path = resolve_log(record, Path("report.json"))
            if log_path is not None:
                actual = log_digest(log_path, legacy=allow_legacy_digest)
                assert actual == digest, (
                    f"log digest mismatch for case {record['name']!r}: report says {digest}, "
                    f"file {log_path} hashes to {actual}"
                )

    total = report.get("assertions_executed_total")
    assert isinstance(total, int) and total > 0, (
        "report executed no assertions; a green run without assertion evidence is not reviewable"
    )
    computed_total = sum(record["assertions_executed"] for record in executed)
    assert total == computed_total, (
        f"assertions_executed_total is {total} but the per-case counts sum to {computed_total}"
    )
    counted = report.get("cases_with_assertion_counts")
    assert isinstance(counted, int) and counted > 0, "no case reported an assertion count"
    assert counted == len(executed), (
        f"cases_with_assertion_counts is {counted} but {len(executed)} case record(s) carry a count"
    )
    declared_zero = report.get("cases_with_zero_assertions")
    assert isinstance(declared_zero, list), "cases_with_zero_assertions is not a list"
    computed_zero = [record["name"] for record in executed if record["assertions_executed"] == 0]
    assert declared_zero == computed_zero, (
        f"cases_with_zero_assertions is {declared_zero!r} but the report records zero-assertion cases "
        f"{computed_zero!r}"
    )

    if baseline is not None:
        assert baseline.get("schema") == REPORT_SCHEMA, "baseline report has an unexpected schema"
        base_total = baseline.get("assertions_executed_total")
        assert isinstance(base_total, int) and base_total > 0, "baseline report has no assertion total"
        assert total >= base_total, (
            f"assertion evidence regressed: {total} executed, baseline had {base_total}"
        )
        base_cases = {
            record["name"]: record["assertions_executed"]
            for record in baseline.get("results", [])
            if isinstance(record.get("assertions_executed"), int)
        }
        missing = sorted(set(base_cases) - set(names))
        assert not missing, f"cases present in the baseline are missing now: {missing}"
        current = {record["name"]: record["assertions_executed"] for record in executed}
        regressed = sorted(
            f"{name} ({current[name]} < {base_cases[name]})"
            for name, count in base_cases.items()
            if name in current and current[name] < count
        )
        assert not regressed, f"per-case assertion counts regressed: {regressed}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate assertion-level evidence in a regression report.")
    parser.add_argument("--report", type=Path, help="report.json to validate")
    parser.add_argument("--report-root", type=Path, help="root that contains timestamped report folders")
    parser.add_argument("--baseline", type=Path, help="earlier report this run must not regress against")
    parser.add_argument("--allow-legacy-digest", action="store_true",
                        help="accept archived reports whose log digests were taken over LF text")
    parser.add_argument("--allow-legacy-probe", action="store_true",
                        help="accept the pre-thread-tracing assertion probe id")
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="triage only: allow failing or skipped cases")
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
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
        validate_report(
            report,
            report_path=path,
            allow_legacy_digest=args.allow_legacy_digest,
            allow_legacy_probe=args.allow_legacy_probe,
            allow_incomplete=args.allow_incomplete,
            baseline=baseline,
        )
    except (AssertionError, json.JSONDecodeError, OSError) as error:
        print(f"report evidence: FAIL {path}\n  {error}")
        return 1
    delta = ""
    if baseline is not None:
        delta = f", baseline {baseline['assertions_executed_total']} assertions"
    print(
        f"report evidence: OK {path}\n"
        f"  version {report['version']}, profile {report['profile']}, {len(report['results'])} cases, "
        f"{report['assertions_executed_total']} assertions executed{delta}, "
        f"probe {report['assert_probe']}, digest {report.get('log_digest_algorithm') or 'legacy'}\n"
        f"  source {report['source_fingerprint'][:12]}..., tests {report['tests_content_fingerprint'][:12]}..."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
