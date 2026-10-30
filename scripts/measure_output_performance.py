#!/usr/bin/env python3
"""Repeatable output-format measurements; engineering timing, not a physical benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def run(args):
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    executables = []
    for option in args.executable:
        label, filename = option.split("=", 1)
        assert label and label.replace("_", "").replace("-", "").isalnum()
        path = Path(filename).resolve()
        caps = subprocess.run([str(path), "--capabilities"], capture_output=True, check=True)
        executables.append((label, path))
        (destination / f"{label}-capabilities.json").write_bytes(caps.stdout)
    assert len({label for label, _ in executables}) == len(executables)
    result = {"schema": "g4usim_output_measurement_v1", "platform": platform.platform(),
              "python": platform.python_version(), "rounds": args.rounds,
              "scope": "Wall time includes startup and finalization. Python SHA timing is separate verification, not backend hashing CPU time. No physical or universal speed claim.",
              "executables": [{"label": label, "path": str(path), "sha256": digest(path)}
                              for label, path in executables], "samples": []}
    counts = {"hits": args.events, "events": args.events * 5, "mesh": args.events}
    workloads = args.workload or list(counts)
    formats = args.format or ["csv", "root", "both"]
    for repeat in range(args.rounds):
        for workload in workloads:
            for fmt in formats:
                # Alternate the pair order to reduce systematic warm-cache/order bias.
                order = executables if repeat % 2 == 0 else executables[::-1]
                for label, executable in order:
                    name = f"{label}-{workload}-{fmt}-{repeat}"
                    work = destination / name
                    work.mkdir()
                    config = work / "main.ini"
                    config.write_bytes(f'''[run]
threads = 2
seed = 4242
[output]
format = {fmt}
[geometry]
template = simple_box
config = {(ROOT / 'config/geometry/hit_smoke_box.ini').as_posix()}
[physics]
em = option4
default_cut = 10 um
[source]
particle = {"geantino" if workload == "events" else "e-"}
energy = 2 MeV
position_type = point
position = 0,0,-9 mm
direction = 0,0,1
[scoring]
enabled = true
hits = {str(workload == "hits").lower()}
event_edep = {str(workload != "mesh").lower()}
edep = true
auto_create_default_scorers = true
'''.encode("utf-8"))
                    macro = work / "run.mac"
                    mesh = "" if workload != "mesh" else '''/score/create/boxMesh benchmarkMesh
/score/mesh/boxSize 10 10 10 mm
/score/mesh/nBin 24 24 24
/score/quantity/energyDeposit edep MeV
/score/quantity/doseDeposit dose Gy
/score/quantity/cellFlux flux
/score/close
'''
                    macro.write_bytes((mesh + f"/run/initialize\n/run/beamOn {counts[workload]}\n").encode("utf-8"))
                    output = work / "output"
                    started = time.perf_counter()
                    with (work / "backend.log").open("wb") as log:
                        completed = subprocess.run([str(executable), "--config", str(config), "--macro",
                                                    str(macro), "--output", str(output)], cwd=ROOT,
                                                   stdout=log, stderr=subprocess.STDOUT, timeout=600)
                    elapsed = time.perf_counter() - started
                    assert completed.returncode == 0, f"{name}: see {work / 'backend.log'}"
                    metadata = json.loads((output / "run_metadata.json").read_bytes())
                    values = metadata["values"]
                    assert values["status"] == "completed" and values["output_failure_status"] == "none"
                    assert len(metadata["runs"]) == 1 and metadata["runs"][0]["completed_events"] == counts[workload]
                    registered = [output / Path(row["path"]).name for row in metadata["generated_files"]]
                    assert all(path.is_file() for path in registered)
                    verify_start = time.perf_counter()
                    hashes = {path.name: digest(path) for path in registered}
                    verify_seconds = time.perf_counter() - verify_start
                    sample = {"label": label, "workload": workload, "format": fmt, "repeat": repeat,
                              "events": counts[workload], "exit_code": completed.returncode,
                              "wall_seconds": elapsed, "python_verify_seconds": verify_seconds,
                              "registered_bytes": sum(path.stat().st_size for path in registered),
                              "registered_files": len(registered), "artifact_sha256": hashes,
                              "config_sha256": digest(config), "macro_sha256": digest(macro),
                              "log_sha256": digest(work / "backend.log")}
                    result["samples"].append(sample)
                    (destination / "report.json").write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
                    print(f"{name}: {elapsed:.3f}s, {sample['registered_bytes']} bytes", flush=True)
    result["medians"] = []
    for label, _ in executables:
        for workload in workloads:
            for fmt in formats:
                rows = [s for s in result["samples"] if (s["label"], s["workload"], s["format"]) == (label, workload, fmt)]
                result["medians"].append({"label": label, "workload": workload, "format": fmt,
                    **{key: statistics.median(s[key] for s in rows)
                       for key in ("wall_seconds", "registered_bytes", "python_verify_seconds")}})
    (destination / "report.json").write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--output", type=Path, required=True, help="new measurement directory")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--events", type=int, default=4000)
    parser.add_argument("--workload", action="append", choices=("hits", "events", "mesh"))
    parser.add_argument("--format", action="append", choices=("csv", "root", "both"))
    arguments = parser.parse_args()
    assert arguments.rounds > 0 and arguments.events > 0
    run(arguments)
