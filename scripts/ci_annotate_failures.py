#!/usr/bin/env python3
"""Publish failing test cases as GitHub Actions annotations.

The test report and the per-case logs are uploaded as artifacts, but the
Actions job log itself requires authentication on a public repository, which
makes a red CI job hard to diagnose from outside. This helper re-emits the
failing cases as ``::error`` workflow commands, so the run page's
"Annotations" section (public) carries the case name, the script and the tail
of its log.

It never changes the exit code by itself: the test step already failed, and
this step only adds diagnostics. It is deliberately tolerant: a missing report
becomes a single annotation instead of another failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_report_evidence import find_latest_report, resolve_log  # noqa: E402

# GitHub truncates a workflow command at 64 KiB of total annotation text; keep
# every single annotation far below that so a chatty failure cannot hide the
# following cases.
MAX_MESSAGE = 3000
DEFAULT_TAIL_LINES = 12


def escape(message: str) -> str:
    """Escape a workflow-command message (see `actions/toolkit`)."""
    return (
        message.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def read_tail(path: Path | None, lines: int) -> str:
    if path is None:
        return "no log file recorded for this case"
    if not path.is_file():
        return f"log file is missing: {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    tail = text.splitlines()[-lines:]
    return " | ".join(line.strip() for line in tail if line.strip())


def locate_report(report_root: Path) -> Path | None:
    """Find the report of the newest run, or an archived copy next to it."""
    try:
        return find_latest_report(report_root)
    except AssertionError:
        archived = report_root / "report.json"
        return archived if archived.is_file() else None


def annotate(report_root: Path, tail_lines: int) -> int:
    report_path = locate_report(report_root)
    if report_path is None:
        print(f"::error::no report.json found under {report_root}")
        return 0
    import json

    report = json.loads(report_path.read_text(encoding="utf-8"))
    failures = [c for c in report.get("results", []) if c.get("status") == "fail"]
    skips = [c for c in report.get("results", []) if c.get("status") == "skip"]
    print(
        f"annotating {len(failures)} failed and {len(skips)} skipped case(s) "
        f"from {report_path}"
    )
    for case in report.get("results", []):
        status = case.get("status")
        if status not in ("fail", "skip"):
            continue
        log_path = resolve_log(case, report_path)
        detail = read_tail(log_path, tail_lines)
        message = (
            f"{case.get('name')} ({case.get('layer')}, {case.get('script')}): {detail}"
        )
        if len(message) > MAX_MESSAGE:
            message = message[:MAX_MESSAGE] + " [truncated]"
        kind = "error" if status == "fail" else "warning"
        print(f"::{kind} title={case.get('name')}::{escape(message)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-root",
        action="append",
        required=True,
        help="directory containing <run>/report.json (repeatable)",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=DEFAULT_TAIL_LINES,
        help="lines taken from the end of each failing case log",
    )
    args = parser.parse_args(argv)
    for root in args.report_root:
        annotate(Path(root), args.tail_lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
