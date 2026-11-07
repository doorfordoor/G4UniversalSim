#!/usr/bin/env python3
"""Offline science verification batch for the F3 measurement (no Geant4 launch).

The batch compares 32 formal samples against the timing repeat 0 of the same
combination through the unchanged comparator in separate Python processes:

* 4 x timing repeat 0 self-qualification (metadata, roles, registered files),
* 16 x timing repeat 1..4 compared with that repeat 0,
* 12 x independent memory samples compared with the same repeat 0.

Every comparison is executed in its own process so the read_csv caches of one
sample are released before the next sample starts.  A 6 GiB available-memory
readiness gate runs before the first comparison; when it is not met the batch
writes an incomplete result and starts nothing.  This driver never launches the
Geant4 backend, never edits the frozen comparator and never creates a
measurement directory.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

AUTHOR = Path(__file__).resolve().parent
ROOT = AUTHOR.parents[3]
COMPARE_N = AUTHOR / "compare_n.py"
TIMING_DIR = ROOT / "out/collab/f3-noise-r3/measurement/timing"
MEMORY_DIR = ROOT / "out/collab/f3-noise-r3/measurement/memory"
DEFAULT_COMBOS = [("hits", "csv"), ("hits", "root"), ("mesh", "csv"), ("mesh", "root")]
DEFAULT_EVENTS = 2000
DEFAULT_READINESS_BYTES = 6 * 1024 ** 3
DEFAULT_REPEATS = 5
DEFAULT_MEMORY_REPEATS = 3


def sample_dir(base: Path, label: str, workload: str, fmt: str, repeat: int) -> str:
    """Output directory of one measurement sample (see measure_output_performance.py)."""
    return str(Path(base) / f"{label}-{workload}-{fmt}-{repeat}" / "output")


def comparison_plan(
    timing_dir: Path,
    memory_dir: Path,
    label: str,
    combos=DEFAULT_COMBOS,
    repeats: int = DEFAULT_REPEATS,
    memory_repeats: int = DEFAULT_MEMORY_REPEATS,
) -> list[dict]:
    """Return the 32 formal science comparisons (4 + 16 + 12)."""
    plan: list[dict] = []
    for workload, fmt in combos:
        baseline = sample_dir(timing_dir, label, workload, fmt, 0)
        plan.append({
            "name": f"timing-r0-{workload}-{fmt}",
            "kind": "timing_r0_selfcheck",
            "workload": workload,
            "format": fmt,
            "repeat": 0,
            "baseline": baseline,
            "candidate": baseline,
        })
        for repeat in range(1, repeats):
            plan.append({
                "name": f"timing-{workload}-{fmt}-{repeat}",
                "kind": "timing_pair",
                "workload": workload,
                "format": fmt,
                "repeat": repeat,
                "baseline": baseline,
                "candidate": sample_dir(timing_dir, label, workload, fmt, repeat),
            })
        for repeat in range(memory_repeats):
            plan.append({
                "name": f"memory-{workload}-{fmt}-{repeat}",
                "kind": "memory_sample",
                "workload": workload,
                "format": fmt,
                "repeat": repeat,
                "baseline": baseline,
                "candidate": sample_dir(memory_dir, f"memory-{label}", workload, fmt, repeat),
            })
    return plan


def discover(plan: list[dict]) -> list[str]:
    """Return the paths the plan needs but that do not exist."""
    missing: list[str] = []
    for entry in plan:
        for key in ("baseline", "candidate"):
            path = entry[key]
            if path not in missing and not Path(path).is_dir():
                missing.append(path)
    return missing


def load_readiness(min_bytes: int = DEFAULT_READINESS_BYTES) -> dict:
    """Readiness gate through compare_n so the boundary is defined once."""
    sys.path.insert(0, str(AUTHOR))
    import compare_n  # noqa: PLC0415

    return compare_n.readiness(min_bytes)


def run_comparison(entry: dict, events: int, out_dir: Path) -> dict:
    """Run one comparison in its own process and return its receipt."""
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt = out_dir / f"{entry['name']}.json"
    command = [
        sys.executable, "-B", str(COMPARE_N), "compare",
        "--baseline", entry["baseline"],
        "--candidate", entry["candidate"],
        "--workload", entry["workload"],
        "--format", entry["format"],
        "--events", str(events),
        "--out", str(receipt),
    ]
    completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                               timeout=6 * 60 * 60, check=False)
    record = {
        "name": entry["name"],
        "kind": entry["kind"],
        "workload": entry["workload"],
        "format": entry["format"],
        "repeat": entry["repeat"],
        "baseline": entry["baseline"],
        "candidate": entry["candidate"],
        "exit_code": completed.returncode,
        "receipt": str(receipt) if receipt.is_file() else None,
        "stdout_tail": completed.stdout.strip().splitlines()[-5:],
        "stderr_tail": completed.stderr.strip().splitlines()[-5:],
    }
    if completed.returncode != 0:
        record["failure"] = "comparison_failed"
    return record


def run_batch(plan: list[dict], out_dir: Path, events: int,
              readiness_bytes: int = DEFAULT_READINESS_BYTES) -> int:
    """Execute the plan after the readiness gate; return a process exit code."""
    report_path = out_dir / "science-batch.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    readiness = load_readiness(readiness_bytes)
    coverage = {kind: sum(1 for entry in plan if entry["kind"] == kind)
                for kind in ("timing_r0_selfcheck", "timing_pair", "memory_sample")}
    report = {
        "schema": "g4usim_f3_science_batch_v1",
        "events": events,
        "comparisons": len(plan),
        "coverage": coverage,
        "each_compared_with": "same-combination timing repeat 0",
        "readiness": readiness,
        "status": "not_started",
        "geant4_launched": False,
        "records": [],
    }
    if not readiness.get("ready"):
        report["status"] = "resource_not_ready"
        report["reason"] = "available memory below the 6 GiB execution boundary"
        report_path.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        return 5
    missing = discover(plan)
    if missing:
        report["status"] = "measurement_incomplete"
        report["missing"] = missing
        report_path.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        return 6
    records = [run_comparison(entry, events, out_dir) for entry in plan]
    report["records"] = records
    failed = [record for record in records if record["exit_code"] != 0]
    report["status"] = "pass" if not failed else "failed"
    report_path.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return 0 if not failed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timing-dir", type=Path, default=TIMING_DIR)
    parser.add_argument("--memory-dir", type=Path, default=MEMORY_DIR)
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--events", type=int, default=DEFAULT_EVENTS)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--readiness-bytes", type=int, default=DEFAULT_READINESS_BYTES)
    parser.add_argument("--combo", action="append", default=None,
                        help="workload:format, repeatable; defaults to the four frozen combinations")
    parser.add_argument("--plan-only", action="store_true",
                        help="print the plan and the readiness gate, then exit without comparing")
    arguments = parser.parse_args(argv)
    combos = DEFAULT_COMBOS
    if arguments.combo:
        combos = []
        for item in arguments.combo:
            workload, _, fmt = item.partition(":")
            combos.append((workload, fmt))
    plan = comparison_plan(arguments.timing_dir, arguments.memory_dir, arguments.label, combos)
    out_dir = arguments.out or (arguments.timing_dir.parent / "science")
    if arguments.plan_only:
        print(json.dumps({"comparisons": len(plan),
                          "coverage": {kind: sum(1 for entry in plan if entry["kind"] == kind)
                                       for kind in ("timing_r0_selfcheck", "timing_pair", "memory_sample")},
                          "readiness": load_readiness(arguments.readiness_bytes),
                          "plan": plan}, indent=2, ensure_ascii=False))
        return 0
    return run_batch(plan, out_dir, arguments.events, arguments.readiness_bytes)


if __name__ == "__main__":
    raise SystemExit(main())
