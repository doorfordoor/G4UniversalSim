#!/usr/bin/env python3
"""Task-level N binding for the frozen F3 science comparator.

The frozen comparator file is never edited.  This wrapper imports it, guards its
SHA-256, sets ``EVENTS`` to the frozen N of this revision (2000) and delegates the
comparison.  A separate process must be used for every comparison so that the
CSV/ROOT caches are released when that child exits.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OLD_MODULE = ROOT / "out/collab/20261107-f3-baseline/preflight/science_compare.py"
OLD_MODULE_SHA256 = "c8195197b9bd7278f74d689edff83dda247af1b4c686f41b3bcd0e7fc982bd82"
DEFAULT_EVENTS = 2000
READINESS_BYTES = 6 * 1024 ** 3


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_old_module(events: int):
    """Import the frozen comparator and bind its event count for this task."""
    digest = sha256_of(OLD_MODULE)
    if digest != OLD_MODULE_SHA256:
        raise SystemExit(
            f"frozen comparator SHA mismatch: {digest} != {OLD_MODULE_SHA256}")
    spec = importlib.util.spec_from_file_location("frozen_science_compare", OLD_MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.EVENTS != 1000:
        raise SystemExit(f"frozen comparator default EVENTS is {module.EVENTS}, expected 1000")
    module.EVENTS = int(events)
    return module


def available_physical_bytes():
    """Return actual available physical memory, or None when the platform cannot report it."""
    try:
        if sys.platform == "win32":
            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return int(status.ullAvailPhys)
        import os

        return int(os.sysconf("SC_AVPHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))
    except Exception:
        return None


def readiness(min_bytes: int = READINESS_BYTES) -> dict:
    available = available_physical_bytes()
    if available is None:
        return {"status": "unknown", "available_bytes": None, "min_bytes": min_bytes,
                "ready": False,
                "note": "the platform cannot report available physical memory; treat as not ready"}
    return {"status": "ok", "available_bytes": available, "min_bytes": min_bytes,
            "ready": available >= min_bytes,
            "note": "actual available physical memory at this instant"}


def compare(baseline: Path, candidate: Path, workload: str, fmt: str, events: int,
            output: Path | None = None) -> tuple[int, dict]:
    module = load_old_module(events)
    try:
        report = module.compare_runs(baseline, candidate, workload, fmt)
    except module.CompareError as error:  # type: ignore[attr-defined]
        report = {"schema": "g4usim_f3_science_comparison_v1", "workload": workload,
                  "format": fmt, "status": "error", "error": str(error), "failures": [],
                  "baseline": str(baseline), "candidate": str(candidate)}
        code = 3
    else:
        code = 0 if report["status"] == "pass" else 2
    report["events_binding"] = {
        "events": int(events),
        "module": str(OLD_MODULE),
        "module_sha256": OLD_MODULE_SHA256,
        "task_level_override": True,
        "file_modified": False,
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return code, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--baseline", type=Path, required=True)
    compare_parser.add_argument("--candidate", type=Path, required=True)
    compare_parser.add_argument("--workload", choices=("hits", "mesh"), required=True)
    compare_parser.add_argument("--format", choices=("csv", "root"), required=True)
    compare_parser.add_argument("--events", type=int, default=DEFAULT_EVENTS)
    compare_parser.add_argument("--out", type=Path)
    readiness_parser = sub.add_parser("readiness")
    readiness_parser.add_argument("--min-bytes", type=int, default=READINESS_BYTES)
    arguments = parser.parse_args(argv)
    if arguments.command == "readiness":
        print(json.dumps(readiness(arguments.min_bytes)))
        return 0
    code, report = compare(arguments.baseline, arguments.candidate, arguments.workload,
                           arguments.format, arguments.events, arguments.out)
    print(json.dumps({"status": report.get("status"), "failures": len(report.get("failures") or []),
                      "events_binding": report["events_binding"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
