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
* each passing case's verified log contains exactly one standalone ASCII
  ``G4USIM_ASSERTS=<nonnegative decimal integer>`` line, matching its reported count;
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

Validation uses explicit exceptions and remains active under ``-O`` and
``PYTHONOPTIMIZE``. Legacy switches change only digest/probe compatibility;
they do not waive the log marker protocol. The Python API without ``report_path``
retains metadata-only checks for records whose logs cannot be located; the CLI
always supplies a report path and requires every passing case's log.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from validation_identity_contract import IdentityContractError, validate_candidate_identity

REPORT_SCHEMA = "G4UniversalSimM0TestReport"
MIN_VERSION = 2
PROBE_ID = "settrace_assert_lines_v3"
LEGACY_PROBE_IDS = ("settrace_assert_lines_v1", "settrace_assert_lines_v2")
LOG_DIGEST_ALGORITHM = "sha256_raw_bytes_lf_v2"
LAYERS = ("static", "gui", "backend", "integration")
PROFILES = ("all", "static", "gui", "backend", "integration")
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


def find_latest_report(report_root: Path) -> Path:
    """Newest report under a run layout, or the archived report at the root.

    A fresh run writes ``<report-root>/<run-id>/report.json``. The copies under
    ``docs/verification/`` keep ``report.json`` at the top of the directory, so a
    reviewer can point either kind of root at this function.
    """
    candidates = sorted(report_root.glob("*/report.json"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        archived = report_root / "report.json"
        if archived.is_file():
            return archived
        raise AssertionError(f"no report.json found under {report_root}")
    return candidates[-1]


def log_digest(path: Path, *, legacy: bool) -> str:
    """Digest of the bytes a reviewer reads from disk; ``legacy`` also tries CRLF->LF."""
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if legacy and data.find(b"\r\n") >= 0:
        canonical = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        return canonical
    return digest


def resolve_log(record: dict, report_path: Path) -> Path | None:
    """Find the log file for a case, allowing evidence copies to relocate it.

    The report directory wins over the recorded absolute path: an evidence copy is
    self-contained, and validating the copy must not silently read the log that
    still sits next to the original report (that would hide a tampered copy).
    """
    log = record.get("log")
    if not isinstance(log, str) or not log:
        return None
    name = Path(log).name
    report_dir = report_path.parent
    candidates = [report_dir / name, report_dir / "logs" / name, Path(log)]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def validate_log_evidence(record: dict, log_path: Path, *, legacy: bool) -> None:
    """Hash and parse one byte snapshot; reject missing, malformed or repeated markers.

    The marker namespace is reserved at the start of a line (including indentation).
    Only an unindented, complete ASCII decimal marker is legal. Even two identical
    markers are ambiguous and rejected. LF and CRLF line endings are accepted.
    """
    data = log_path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    accepted = {actual}
    if legacy:
        accepted.add(hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest())
    if record["log_sha256"] not in accepted:
        raise AssertionError(
            f"log digest mismatch for case {record['name']!r}: report says {record['log_sha256']}, "
            f"file {log_path} hashes to {actual}"
        )
    markers = [line for line in data.splitlines() if line.lstrip().startswith(b"G4USIM_ASSERTS")]
    if len(markers) != 1:
        raise AssertionError(
            f"case {record['name']!r} log {log_path} must contain exactly one G4USIM_ASSERTS marker; "
            f"found {len(markers)}"
        )
    match = re.fullmatch(rb"G4USIM_ASSERTS=([0-9]+)", markers[0])
    if match is None:
        raise AssertionError(f"case {record['name']!r} log {log_path} has a malformed G4USIM_ASSERTS marker")
    try:
        count = int(match.group(1))
    except ValueError as error:
        raise AssertionError(
            f"case {record['name']!r} log {log_path} has a malformed G4USIM_ASSERTS count"
        ) from error
    if count != record["assertions_executed"]:
        raise AssertionError(
            f"case {record['name']!r} assertion count mismatch: report says "
            f"{record['assertions_executed']}, log {log_path} G4USIM_ASSERTS={count}"
        )


def validate_report(
    report: dict,
    *,
    report_path: Path | None = None,
    allow_legacy_digest: bool = False,
    allow_legacy_probe: bool = False,
    allow_incomplete: bool = False,
    baseline: dict | None = None,
    require_candidate_identity: bool = False,
) -> None:
    """Raise AssertionError when the report cannot support its own claims."""
    if not (report.get("schema") == REPORT_SCHEMA):
        raise AssertionError(f"unexpected report schema: {report.get('schema')!r}")
    version = report.get("version")
    if not (isinstance(version, int) and version >= MIN_VERSION):
        raise AssertionError(f"report version {version!r} predates assertion-level evidence (need >= {MIN_VERSION})")
    try:
        validate_candidate_identity(report, require_identity=require_candidate_identity)
    except IdentityContractError as error:
        raise AssertionError(f"candidate identity: {error}") from error
    probe = report.get("assert_probe")
    if probe == "disabled":
        raise AssertionError("assert probe is disabled; a report without executed assertions is not evidence")
    allowed_probes = (PROBE_ID,) if not allow_legacy_probe else (PROBE_ID,) + LEGACY_PROBE_IDS
    if not (probe in allowed_probes):
        raise AssertionError(f"unknown assert probe: {probe!r} (current is {PROBE_ID!r}; "
        f"archived reports need --allow-legacy-probe)")
    algorithm = report.get("log_digest_algorithm")
    if not allow_legacy_digest:
        if not (algorithm == LOG_DIGEST_ALGORITHM):
            raise AssertionError(f"log digest algorithm {algorithm!r} is not {LOG_DIGEST_ALGORITHM!r}; "
            f"archived reports need --allow-legacy-digest")
    if not (report.get("profile") in PROFILES):
        raise AssertionError(f"unknown test profile: {report.get('profile')!r}")
    for key in ("source_fingerprint", "tests_content_fingerprint"):
        value = report.get(key)
        if not (isinstance(value, str) and HEX64.match(value)):
            raise AssertionError(f"{key} is missing or not a 64-character lowercase sha256: {value!r}")
    if not (report.get("backend_provenance")):
        raise AssertionError("backend provenance is missing")

    results = report.get("results")
    if not (isinstance(results, list) and results):
        raise AssertionError("report contains no case results")

    names = []
    for record in results:
        if not (isinstance(record, dict)):
            raise AssertionError(f"case record is not an object: {record!r}")
        for key in ("name", "layer", "script", "status"):
            if not (key in record):
                raise AssertionError(f"case record {record.get('name')!r} lacks {key!r}")
        if record["status"] != "skip":
            # A case that could not run has no exit status; the runner records the
            # reason instead. Cases that did run must carry their exit code.
            if not (isinstance(record.get("exit_code"), int)):
                raise AssertionError(f"case {record['name']!r} has no usable exit_code: {record.get('exit_code')!r}")
        if not (isinstance(record["name"], str) and record["name"]):
            raise AssertionError(f"case record has no usable name: {record!r}")
        if not (isinstance(record["script"], str) and record["script"]):
            raise AssertionError(f"case {record['name']!r} has no script")
        if not (record["layer"] in LAYERS):
            raise AssertionError(f"case {record['name']!r} has unknown layer {record['layer']!r}")
        if not (record["status"] in ("pass", "fail", "skip")):
            raise AssertionError(f"case {record['name']!r} has unknown status {record['status']!r}")
        names.append(record["name"])
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise AssertionError(f"duplicate case names: {duplicates}")

    non_pass = [record["name"] for record in results if record["status"] != "pass"]
    if non_pass and not allow_incomplete:
        raise AssertionError(f"report is not release evidence: {len(non_pass)} case(s) did not pass ({non_pass[:5]}); "
            f"pass --allow-incomplete only for triage")

    executed = [record for record in results if isinstance(record.get("assertions_executed"), int)]
    for record in results:
        if record["status"] != "pass":
            continue
        if not (isinstance(record.get("exit_code"), int) and record["exit_code"] == 0):
            raise AssertionError(f"passing case {record['name']!r} has exit_code {record.get('exit_code')!r}")
        count = record.get("assertions_executed")
        if not (isinstance(count, int)):
            raise AssertionError(f"passing case {record['name']!r} has no assertion count")
        if not (record.get("assert_probe") == probe):
            raise AssertionError(f"case {record['name']!r} probe {record.get('assert_probe')!r} differs from report probe {probe!r}")
        if not (count >= 1):
            raise AssertionError(f"passing case {record['name']!r} executed no assertions; a PASS without assertion evidence "
            f"is only an exit code")
        sites = record.get("assert_sites")
        if not (isinstance(sites, int) and sites >= 0):
            raise AssertionError(f"passing case {record['name']!r} has a malformed assert site count: {sites!r}")
        digest = record.get("log_sha256")
        if not (isinstance(digest, str) and HEX64.match(digest)):
            raise AssertionError(f"passing case {record['name']!r} has no 64-character lowercase log digest")
        if report_path is not None:
            log_path = resolve_log(record, report_path)
            if not (log_path is not None):
                raise AssertionError(f"log for passing case {record['name']!r} cannot be found next to {report_path}")
        else:
            log_path = resolve_log(record, Path("report.json"))
        if log_path is not None:
            validate_log_evidence(record, log_path, legacy=allow_legacy_digest)

    total = report.get("assertions_executed_total")
    if not (isinstance(total, int) and total > 0):
        raise AssertionError("report executed no assertions; a green run without assertion evidence is not reviewable")
    computed_total = sum(record["assertions_executed"] for record in executed)
    if not (total == computed_total):
        raise AssertionError(f"assertions_executed_total is {total} but the per-case counts sum to {computed_total}")
    counted = report.get("cases_with_assertion_counts")
    if not (isinstance(counted, int) and counted > 0):
        raise AssertionError("no case reported an assertion count")
    if not (counted == len(executed)):
        raise AssertionError(f"cases_with_assertion_counts is {counted} but {len(executed)} case record(s) carry a count")
    declared_zero = report.get("cases_with_zero_assertions")
    if not (isinstance(declared_zero, list)):
        raise AssertionError("cases_with_zero_assertions is not a list")
    computed_zero = [record["name"] for record in executed if record["assertions_executed"] == 0]
    if not (declared_zero == computed_zero):
        raise AssertionError(f"cases_with_zero_assertions is {declared_zero!r} but the report records zero-assertion cases "
        f"{computed_zero!r}")

    if baseline is not None:
        if not (baseline.get("schema") == REPORT_SCHEMA):
            raise AssertionError("baseline report has an unexpected schema")
        if not (baseline.get("assert_probe") == probe):
            raise AssertionError(f"cross-probe baseline comparison is not valid: current {probe!r}, baseline {baseline.get('assert_probe')!r}; "
            "rebuild the baseline with the same probe, never reinterpret archived assertion totals")
        if not (all(record.get("assert_probe") == probe for record in baseline.get("results", [])
                   if isinstance(record.get("assertions_executed"), int))):
            raise AssertionError("baseline case probe differs from its report probe")
        base_total = baseline.get("assertions_executed_total")
        if not (isinstance(base_total, int) and base_total > 0):
            raise AssertionError("baseline report has no assertion total")
        if not (total >= base_total):
            raise AssertionError(f"assertion evidence regressed: {total} executed, baseline had {base_total}")
        base_cases = {
            record["name"]: record["assertions_executed"]
            for record in baseline.get("results", [])
            if isinstance(record.get("assertions_executed"), int)
        }
        missing = sorted(set(base_cases) - set(names))
        if missing:
            raise AssertionError(f"cases present in the baseline are missing now: {missing}")
        current = {record["name"]: record["assertions_executed"] for record in executed}
        regressed = sorted(
            f"{name} ({current[name]} < {base_cases[name]})"
            for name, count in base_cases.items()
            if name in current and current[name] < count
        )
        if regressed:
            raise AssertionError(f"per-case assertion counts regressed: {regressed}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate assertion-level evidence in a regression report.")
    parser.add_argument("--report", type=Path, help="report.json to validate")
    parser.add_argument("--report-root", type=Path, help="root that contains timestamped report folders")
    parser.add_argument("--baseline", type=Path, help="earlier report this run must not regress against")
    parser.add_argument("--require-candidate-identity", action="store_true",
                        help="require stable recorded start/end identity for new formal evidence")
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
            require_candidate_identity=args.require_candidate_identity,
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
        f"  source {report['source_fingerprint'][:12]}..., tests {report['tests_content_fingerprint'][:12]}...\n"
        f"  candidate identity: {'stable' if 'candidate_identity' in report else 'legacy/unavailable (start/end not verified)'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
