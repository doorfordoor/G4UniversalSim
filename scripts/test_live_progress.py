"""F6 real-backend progress: counts, runs, failure, cancellation and optional baseline."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import queue
import statistics
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "[G4USimProgress] "


def messages(log: str) -> list[dict]:
    result = []
    for line in log.splitlines():
        if PREFIX in line:
            item = json.loads(line.split(PREFIX, 1)[1])
            assert item["schema"] == "g4usim_progress_v1", item
            result.append(item)
    return result


def facts(output: Path) -> dict[str, str]:
    path = output / "run_summary.txt"
    if not path.is_file():
        return {}
    return dict(line.split(" = ", 1) for line in path.read_text(encoding="utf-8").splitlines()
                if " = " in line)


def fixture(work: Path, events: tuple[int, ...], threads: int = 2) -> tuple[Path, Path]:
    work.mkdir(parents=True, exist_ok=True)
    geometry = work / "geometry.ini"
    geometry.write_text("""[world]
size = 10 cm,10 cm,10 cm
material = G4_Galactic
[target]
name = Target
shape = box
size = 1 cm,1 cm,1 mm
material = G4_Si
position = 0,0,0 mm
sensitive = true
""", encoding="utf-8")
    ini = work / "main.ini"
    ini.write_text(f"""[run]
threads = {threads}
seed = 4242
check_overlaps = false
[output]
format = csv
[materials]
file = {(ROOT / 'config/materials/material.ini').as_posix()}
[geometry]
template = simple_box
config = {geometry.as_posix()}
check_overlaps = false
[physics]
em = option4
default_cut = 0.1 mm
[source]
particle = proton
energy = 10 MeV
position_type = point
position = 0,0,-1 mm
direction = 0,0,1
[scoring]
enabled = true
hits = false
event_edep = true
edep = true
""", encoding="utf-8")
    macro = work / "run.mac"
    macro.write_text("/run/initialize\n" + "".join(f"/run/beamOn {n}\n" for n in events), encoding="utf-8")
    return ini, macro


def execute(exe: Path, work: Path, events=(200, 137), threads=2, fault=None, noise=False, invalid=False, hits=False):
    ini, macro = fixture(work, events, threads)
    if noise:
        macro.write_text(macro.read_text(encoding="utf-8").replace(
            "/run/initialize\n", "/run/initialize\n/event/verbose 1\n/tracking/verbose 1\n"), encoding="utf-8")
    if invalid:
        ini.write_text(ini.read_text(encoding="utf-8").replace("energy = 10 MeV", "energy = NaN MeV"), encoding="utf-8")
    if hits:
        ini.write_text(ini.read_text(encoding="utf-8").replace("hits = false", "hits = true"), encoding="utf-8")
    output = work / "output"
    env = os.environ.copy()
    env.pop("G4USIM_TEST_OUTPUT_FAULT", None)
    if fault:
        env["G4USIM_TEST_OUTPUT_FAULT"] = fault
    started = time.perf_counter()
    run = subprocess.run([str(exe), "--config", str(ini), "--macro", str(macro),
                          "--output", str(output)], cwd=ROOT, env=env,
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    duration = time.perf_counter() - started
    (work / "stdout.log").write_text(run.stdout, encoding="utf-8")
    (work / "stderr.log").write_text(run.stderr, encoding="utf-8")
    return run, messages(run.stdout), facts(output), duration


def validate(items: list[dict], summary: dict[str, str], expected: tuple[int, ...]) -> None:
    for run_id, planned in enumerate(expected):
        group = [x for x in items if x["run_id"] == run_id]
        assert group and group[0]["phase"] == "begin", group
        assert group[-1]["phase"] == "end", group
        counts = [x["completed_events"] for x in group]
        assert counts == sorted(counts) and counts[0] == 0 and counts[-1] == planned, counts
        assert all(x["planned_events"] == planned for x in group), group
        assert int(summary[f"run_{run_id}_completed_events"]) == counts[-1], summary
        assert int(summary[f"run_{run_id}_planned_events"]) == planned, summary
        running = [x for x in group if x["phase"] == "running"]
        assert len(running) <= int(group[-1]["elapsed_s"] / 0.5) + 2, group
        assert all(x["elapsed_s"] >= 0 for x in group), group
    sequences = [x.get("sequence") for x in items]
    assert all(type(seq) is int and seq >= 0 for seq in sequences), sequences
    assert sequences == sorted(sequences), sequences
    assert len(set(sequences)) == len(sequences), sequences
    assert sequences[-1] > sequences[0], sequences


def event_rows(work: Path, pattern="event_edep_t*.csv"):
    rows = []
    for path in (work / "output").glob(pattern):
        with path.open(encoding="utf-8") as stream:
            rows.extend(tuple(sorted(row.items())) for row in csv.DictReader(stream))
    assert rows, work
    return sorted(rows)


def cancellation(exe: Path, work: Path):
    ini, macro = fixture(work, (10000000,), 2)
    proc = subprocess.Popen([str(exe), "--config", str(ini), "--macro", str(macro),
                             "--output", str(work / "output")], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    lines: queue.Queue[str | None] = queue.Queue()
    def reader():
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)
    worker = threading.Thread(target=reader, daemon=True)
    worker.start()
    log = []
    seen = None
    deadline = time.monotonic() + 90
    try:
        while time.monotonic() < deadline:
            line = lines.get(timeout=max(0.1, deadline - time.monotonic()))
            if line is None:
                break
            log.append(line)
            found = messages(line)
            if found and found[0]["phase"] == "running" and found[0]["completed_events"] > 0:
                seen = found[0]
                proc.kill()
                break
        assert seen is not None, "No live progress before cancellation"
        proc.wait(timeout=15)
        worker.join(timeout=5)
        while not lines.empty():
            line = lines.get_nowait()
            if line is not None:
                log.append(line)
        assert proc.returncode != 0
        assert not any(x["phase"] == "end" for x in messages("".join(log)))
        (work / "cancel.log").write_text("".join(log), encoding="utf-8")
        return seen
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    exe = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe")).resolve()
    report = {"backend": str(exe), "checks": [], "performance": {}}
    with tempfile.TemporaryDirectory(prefix="g4usim-f6-") as directory:
        work = Path(directory)
        for threads in (1, 2, 4):
            run, progress, summary, _ = execute(exe, work / f"mt{threads}", threads=threads)
            assert run.returncode == 0, run.stderr[-3000:]
            validate(progress, summary, (200, 137))
            report["checks"].append(f"{threads} workers, two runs: counts match summary")
        run, progress, summary, _ = execute(exe, work / "zero", events=(0,))
        assert run.returncode == 0, run.stderr[-3000:]
        assert not any(x["phase"] == "end" and x["planned_events"] == 0 for x in progress)
        assert summary and int(summary["actual_completed_event_count"]) == 0, summary
        assert int(summary["run_count"]) == 0, summary
        report["checks"].append("zero requested events: no fabricated completed run")
        run, progress, summary, _ = execute(exe, work / "bad_config", invalid=True)
        assert run.returncode != 0 and not progress
        report["checks"].append("configuration failure: no fabricated run progress")
        run, progress, summary, _ = execute(exe, work / "noisy", events=(50,), threads=4, noise=True)
        assert run.returncode == 0, run.stderr[-2000:]
        validate(progress, summary, (50,))
        report["checks"].append("4 workers with event/tracking log noise: valid progress messages")
        for fault, threads in (("event_row_t0", 1), ("event_row_any_worker", 2),
                               ("begin_scoring_t0", 2), ("final_close_master", 2)):
            run, progress, summary, _ = execute(exe, work / fault, events=(200, 137), threads=threads, fault=fault)
            assert run.returncode != 0 and summary["status"] == "failed", (fault, run.stderr[-3000:])
            if fault.startswith("event_row_"):
                assert summary["output_failure_stage"] == "event_edep_write", summary
                failure_thread = int(summary["output_failure_thread_id"])
                assert 0 <= failure_thread < threads, summary
                report["checks"].append(f"{fault}: actual failure worker={failure_thread}")
            for item in progress:
                if item["phase"] in ("end", "aborted"):
                    key = f"run_{item['run_id']}_completed_events"
                    assert key in summary, (item, summary)
                    assert item["completed_events"] == int(summary[key]), (item, summary)
            if fault != "final_close_master":
                assert any(x["phase"] == "aborted" for x in progress), progress
            report["checks"].append(f"{fault}: nonzero failed summary; terminal counts agree")
        report["cancel_last_progress"] = cancellation(exe, work / "cancel")
        report["checks"].append("real process killed after receiving live completed-event update")
        if args.baseline:
            for threads in (1, 2):
                before = work / f"before{threads}"
                after = work / f"after{threads}"
                old = execute(args.baseline.resolve(), before, events=(1000, 317), threads=threads, hits=True)
                new = execute(exe, after, events=(1000, 317), threads=threads, hits=True)
                assert old[0].returncode == new[0].returncode == 0
                assert event_rows(before) == event_rows(after), f"physical event records changed ({threads} threads)"
                assert event_rows(before, "hits_t*.csv") == event_rows(after, "hits_t*.csv"), f"physical hit records changed ({threads} threads)"
                report["checks"].append(f"baseline {threads} workers: sorted event energy and hit records exactly equal")
            timings = {"baseline": [], "candidate": []}
            for i in range(3):
                order = [("baseline", args.baseline.resolve()), ("candidate", exe)]
                if i % 2:
                    order.reverse()
                for label, binary in order:
                    run, progress, _, elapsed = execute(binary, work / f"perf-{label}-{i}", events=(200000,), threads=2)
                    assert run.returncode == 0
                    if label == "candidate":
                        assert any(x["phase"] == "running" for x in progress), "performance sample must include live emissions"
                    timings[label].append(elapsed)
            report["performance"] = {"wall_seconds": timings,
                "median_ratio": statistics.median(timings["candidate"]) / statistics.median(timings["baseline"]),
                "scope": "3 alternating process wall-time samples, 200000 protons, 2 workers; includes initialization and IO; candidate emits running updates; not a universal overhead bound"}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("test_live_progress: OK")


if __name__ == "__main__":
    main()
