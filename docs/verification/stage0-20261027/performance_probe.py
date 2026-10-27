"""F6 progress-overhead probe: paired, drift-controlled comparison.

The first version of this probe took five alternating samples and compared medians of the
two groups. On this machine the wall time drifts upward over the first minutes (later samples
were consistently ~7 % slower regardless of the binary), so the group-median ratio reported
1.068 for a difference the paired ratios do not support. This version therefore:

* warms both binaries once (not recorded),
* runs 12 paired iterations in alternating order,
* reports the per-pair ratio (candidate / baseline) and its median, plus the first/last
  third medians as an explicit drift check,
* keeps the same workload (300000 protons, 2 workers) and asserts the event count and that
  the candidate still emits running progress updates.

The scope field states exactly what the numbers cover; they are not a universal overhead
bound and they include initialization and IO.
"""

import json
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
from test_live_progress import execute  # noqa: E402

root = Path.cwd()
exe = root / "build_vs2026/Release/G4UniversalSim.exe"
baseline = root / "build_vs2026/Release/G4UniversalSim_f6_baseline.exe"
ITERATIONS = 12
EVENTS = (300000,)
THREADS = 2

for binary in (exe, baseline):
    if not binary.is_file():
        raise SystemExit(f"missing binary: {binary}")


def one_run(binary: Path, output: Path):
    result, progress, summary, elapsed = execute(binary, output, events=EVENTS, threads=THREADS)
    assert result.returncode == 0, f"exit code {result.returncode} for {binary.name}"
    assert summary["actual_completed_event_count"] == "300000", summary.get("actual_completed_event_count")
    running_updates = sum(1 for item in progress if item["phase"] == "running")
    return elapsed, running_updates


pairs = []
with tempfile.TemporaryDirectory(prefix="f6-perf-") as directory:
    work = Path(directory)
    # Warm-up: the first run of each binary pays process start and file-cache population.
    for label, binary in (("baseline", baseline), ("candidate", exe)):
        one_run(binary, work / f"warmup-{label}")

    for iteration in range(ITERATIONS):
        order = [("baseline", baseline), ("candidate", exe)]
        if iteration % 2:
            order.reverse()
        timings = {}
        updates = {}
        for label, binary in order:
            elapsed, running_updates = one_run(binary, work / f"{label}-{iteration}")
            timings[label] = elapsed
            updates[label] = running_updates
        pairs.append(
            {
                "iteration": iteration,
                "order": [label for label, _ in order],
                "baseline_seconds": timings["baseline"],
                "candidate_seconds": timings["candidate"],
                "ratio": timings["candidate"] / timings["baseline"],
                "candidate_running_updates": updates["candidate"],
            }
        )

ratios = [pair["ratio"] for pair in pairs]
assert all(pair["candidate_running_updates"] >= 2 for pair in pairs), "candidate emitted too few progress updates"
third = max(1, ITERATIONS // 3)
report = {
    "pairs": pairs,
    "median_ratio": statistics.median(ratios),
    "min_ratio": min(ratios),
    "max_ratio": max(ratios),
    "median_seconds": {
        "baseline": statistics.median(pair["baseline_seconds"] for pair in pairs),
        "candidate": statistics.median(pair["candidate_seconds"] for pair in pairs),
    },
    "drift_check": {
        "note": "median per-pair ratio of the first third vs the last third; a large difference means "
        "machine drift dominates and the single median ratio must not be read as binary overhead",
        "first_third_median_ratio": statistics.median(ratios[:third]),
        "last_third_median_ratio": statistics.median(ratios[-third:]),
    },
    "candidate_running_updates": [pair["candidate_running_updates"] for pair in pairs],
    "scope": (
        f"{ITERATIONS} paired alternating process wall-time samples after one warm-up run per binary, "
        "300000 protons, 2 workers; paired ratio controls monotonic machine drift; includes "
        "initialization and IO; measured with no other project test job running; not a universal "
        "overhead bound"
    ),
}
(root / "out/verification/f6-20261027/performance-final.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report, indent=2))
