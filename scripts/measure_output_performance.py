#!/usr/bin/env python3
"""Repeatable output-format measurements; engineering timing, not a physical benchmark."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x10

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_config(workload, fmt, events):
    """Exact main.ini bytes; shared by the timing and optional memory phases."""
    return f'''[run]
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
'''.encode("utf-8")


def render_macro(workload, events):
    """Exact run.mac bytes; shared by the timing and optional memory phases."""
    counts = {"hits": events, "events": events * 5, "mesh": events}
    mesh = "" if workload != "mesh" else '''/score/create/boxMesh benchmarkMesh
/score/mesh/boxSize 10 10 10 mm
/score/mesh/nBin 24 24 24
/score/quantity/energyDeposit edep MeV
/score/quantity/doseDeposit dose Gy
/score/quantity/cellFlux flux
/score/close
'''
    return (mesh + f"/run/initialize\n/run/beamOn {counts[workload]}\n").encode("utf-8")


def registered_files(output, metadata):
    return [output / Path(row["path"]).name for row in metadata["generated_files"]]


def read_run_wall(output, metadata):
    """Backend's own run-wall timer (BeginOfRun -> mesh CSV export); secondary only."""
    values = set()
    files = 0
    for path in registered_files(output, metadata):
        if not (path.name.startswith("scorer_statistics") and path.name.endswith(".csv")):
            continue
        files += 1
        with path.open(newline="", encoding="utf-8") as handle:
            import csv as _csv
            for row in _csv.DictReader(handle):
                text = row.get("run_wall_time_s")
                if text not in (None, ""):
                    values.add(float(text))
    return {"values": sorted(values), "max": max(values) if values else None, "files": files}


def process_creation_filetime(pid):
    """Creation FILETIME of the real backend child, bound by the observer."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                         ctypes.POINTER(wintypes.FILETIME),
                                         ctypes.POINTER(wintypes.FILETIME),
                                         ctypes.POINTER(wintypes.FILETIME))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
    assert handle, f"OpenProcess({pid}) failed: {ctypes.get_last_error()}"
    try:
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        assert kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                        ctypes.byref(kernel), ctypes.byref(user)), "GetProcessTimes failed"
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        kernel32.CloseHandle(handle)


def launch_identity(executable, creation_filetime):
    return {"executable": str(executable), "executable_sha256": digest(executable),
            "creation_filetime": creation_filetime,
            "started_utc": utc_now(), "python_pid": os.getpid()}


def validate_memory(name, memory, launch, pid):
    assert memory.get("schema") == "g4usim_pid_observer_v1", f"{name}: observer schema"
    assert memory.get("status") == "completed", f"{name}: observer status {memory.get('status')!r}"
    assert memory.get("identity_ok") is True, f"{name}: observer identity mismatch"
    assert memory.get("identity_bound") is True, f"{name}: observer identity was not bound"
    assert memory.get("pid") == pid, f"{name}: observer bound PID {memory.get('pid')} != {pid}"
    assert memory.get("expected_creation_filetime") == launch["creation_filetime"], f"{name}: creation time"
    assert memory.get("observed_creation_filetime") == launch["creation_filetime"], f"{name}: observed creation time"
    expected_sha = launch["executable_sha256"].lower()
    assert str(memory.get("expected_exe_sha256", "")).lower() == expected_sha, f"{name}: expected SHA"
    assert str(memory.get("observed_exe_sha256", "")).lower() == expected_sha, f"{name}: observed SHA"
    samples = memory.get("samples") or []
    assert memory.get("sample_count") == len(samples) >= 5, f"{name}: observer samples {len(samples)}"
    peak = memory.get("peak_working_set_bytes")
    os_peak = memory.get("os_peak_working_set_bytes")
    assert isinstance(peak, int) and isinstance(os_peak, int), f"{name}: observer maxima missing"
    assert peak > 0 and os_peak >= peak, f"{name}: observer peak {peak}/{os_peak}"
    assert peak >= max(sample["working_set_bytes"] for sample in samples), f"{name}: peak not maximal"
    assert "final_working_set_bytes" in memory and "final_query_ok" in memory, f"{name}: final query fields"
    assert memory.get("interval_target_s") == 0.1, f"{name}: observer interval"


def check_output(output, expected_events, name):
    metadata = json.loads((output / "run_metadata.json").read_bytes())
    values = metadata["values"]
    assert values["status"] == "completed" and values["output_failure_status"] == "none", name
    assert len(metadata["runs"]) == 1 and metadata["runs"][0]["completed_events"] == expected_events, name
    registered = registered_files(output, metadata)
    assert all(path.is_file() for path in registered), name
    return metadata, registered


def ordered_combos(combos, mode, repeat):
    """Return the combo order for one repeat.

    legacy: combos in CLI order for every repeat (old behaviour).
    blocked: rotate the combo list by the repeat index; with 5 repeats and 4
    combos every combo occupies every position at least once.
    """
    if mode == "legacy":
        return list(combos)
    if not combos:
        return []
    shift = repeat % len(combos)
    return list(combos[shift:]) + list(combos[:shift])


def order_fields(combos, workload, fmt, position, mode):
    """Report fields for one executed combo.

    execution_position is the position in this repeat's schedule.
    base_combo_index is the combo's fixed index in the CLI order.
    legacy reports keep their old shape (no extra fields).
    """
    if mode != "blocked":
        return {}
    return {"execution_position": position,
            "base_combo_index": combos.index((workload, fmt))}


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
    combos = [(workload, fmt) for workload in workloads for fmt in formats]
    if args.order == "blocked":
        result["order"] = {
            "mode": "blocked",
            "rule": "repeat index rotates the combo list; every combo visits every position",
            "base_order": [{"workload": workload, "format": fmt} for workload, fmt in combos],
        }
    for repeat in range(args.rounds):
        for position, (workload, fmt) in enumerate(
                ordered_combos(combos, args.order, repeat)):
                # Alternate the pair order to reduce systematic warm-cache/order bias.
                order = executables if repeat % 2 == 0 else executables[::-1]
                for label, executable in order:
                    name = f"{label}-{workload}-{fmt}-{repeat}"
                    work = destination / name
                    work.mkdir()
                    config = work / "main.ini"
                    config.write_bytes(render_config(workload, fmt, args.events))
                    macro = work / "run.mac"
                    macro.write_bytes(render_macro(workload, args.events))
                    output = work / "output"
                    started = time.perf_counter()
                    with (work / "backend.log").open("wb") as log:
                        completed = subprocess.run([str(executable), "--config", str(config), "--macro",
                                                    str(macro), "--output", str(output)], cwd=ROOT,
                                                   stdout=log, stderr=subprocess.STDOUT, timeout=600)
                    elapsed = time.perf_counter() - started
                    assert completed.returncode == 0, f"{name}: see {work / 'backend.log'}"
                    metadata, registered = check_output(output, counts[workload], name)
                    verify_start = time.perf_counter()
                    hashes = {path.name: digest(path) for path in registered}
                    verify_seconds = time.perf_counter() - verify_start
                    sample = {"label": label, "workload": workload, "format": fmt, "repeat": repeat,
                              "events": counts[workload], "exit_code": completed.returncode,
                              "wall_seconds": elapsed, "total_elapsed_s": elapsed,
                              "run_wall": read_run_wall(output, metadata),
                              "python_verify_seconds": verify_seconds,
                              "registered_bytes": sum(path.stat().st_size for path in registered),
                              "registered_files": len(registered), "artifact_sha256": hashes,
                              "config_sha256": digest(config), "macro_sha256": digest(macro),
                              "log_sha256": digest(work / "backend.log")}
                    sample.update(order_fields(combos, workload, fmt, position, args.order))
                    result["samples"].append(sample)
                    (destination / "report.json").write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
                    print(f"{name}: {elapsed:.3f}s, {sample['registered_bytes']} bytes", flush=True)
    if args.memory_repeats:
        # F3-2 optional memory phase: independent runs, real Geant4 child PID bound,
        # ordinary Python observer at 100 ms.  Never merged into timing samples.
        assert args.observer, "--memory-repeats requires --observer"
        memory_dir = destination / "memory"
        memory_dir.mkdir()
        memory_samples = []
        for repeat in range(args.memory_repeats):
            for position, (workload, fmt) in enumerate(
                    ordered_combos(combos, args.order, repeat)):
                    for label, executable in executables:
                        name = f"memory-{label}-{workload}-{fmt}-{repeat}"
                        work = memory_dir / name
                        work.mkdir()
                        config = work / "main.ini"
                        config.write_bytes(render_config(workload, fmt, args.events))
                        macro = work / "run.mac"
                        macro.write_bytes(render_macro(workload, args.events))
                        output = work / "output"
                        memory_path = work / "memory.json"
                        observer_log = work / "observer.log"
                        process = None
                        observer = None
                        try:
                            started = time.perf_counter()
                            with (work / "backend.log").open("wb") as log, observer_log.open("wb") as obs_log:
                                process = subprocess.Popen([str(executable), "--config", str(config),
                                                            "--macro", str(macro), "--output", str(output)],
                                                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                                creation = process_creation_filetime(process.pid)
                                launch = launch_identity(executable, creation)
                                observer = subprocess.Popen([sys.executable, str(args.observer),
                                                             "--pid", str(process.pid),
                                                             "--expected-exe", str(executable),
                                                             "--expected-creation-filetime", str(creation),
                                                             "--expected-exe-sha256",
                                                             launch["executable_sha256"],
                                                             "--interval", "0.1",
                                                             "--output", str(memory_path)],
                                                            stdout=obs_log, stderr=subprocess.STDOUT)
                                try:
                                    exit_code = process.wait(timeout=600)
                                except subprocess.TimeoutExpired:
                                    process.kill()
                                    process.wait()
                                    raise AssertionError(
                                        f"{name}: backend exceeded 600 s; see {work / 'backend.log'}")
                            elapsed = time.perf_counter() - started
                            observer.wait(timeout=60)
                            assert observer.returncode == 0, f"{name}: see {observer_log}"
                            assert exit_code == 0, f"{name}: see {work / 'backend.log'}"
                            metadata, registered = check_output(output, counts[workload], name)
                            memory = json.loads(memory_path.read_bytes())
                            validate_memory(name, memory, launch, process.pid)
                        except BaseException:
                            for child in (observer, process):
                                if child is not None and child.poll() is None:
                                    try:
                                        child.kill()
                                    except OSError:
                                        pass
                                    child.wait()
                            raise
                        sample = {"label": label, "workload": workload, "format": fmt, "repeat": repeat,
                                  "events": counts[workload], "exit_code": exit_code,
                                  "wall_seconds": elapsed, "total_elapsed_s": elapsed,
                                  "run_wall": read_run_wall(output, metadata),
                                  "registered_bytes": sum(path.stat().st_size for path in registered),
                                  "registered_files": len(registered),
                                  "artifact_sha256": {path.name: digest(path) for path in registered},
                                  "config_sha256": digest(config), "macro_sha256": digest(macro),
                                  "log_sha256": digest(work / "backend.log"),
                                  "launch": launch, "memory": memory}
                        sample.update(order_fields(combos, workload, fmt, position, args.order))
                        memory_samples.append(sample)
                        result["memory_samples"] = memory_samples
                        (destination / "report.json").write_bytes(
                            (json.dumps(result, indent=2) + "\n").encode("utf-8"))
                        print(f"{name}: {elapsed:.3f}s, ws_peak={memory.get('peak_working_set_bytes')}",
                              flush=True)
    result["medians"] = []
    for label, _ in executables:
        for workload in workloads:
            for fmt in formats:
                rows = [s for s in result["samples"] if (s["label"], s["workload"], s["format"]) == (label, workload, fmt)]
                if not rows:
                    continue
                median = {"label": label, "workload": workload, "format": fmt,
                          "wall_seconds": statistics.median(s["wall_seconds"] for s in rows),
                          "total_elapsed_s": statistics.median(s["total_elapsed_s"] for s in rows),
                          "registered_bytes": statistics.median(s["registered_bytes"] for s in rows),
                          "sample_count": len(rows)}
                verify = [s["python_verify_seconds"] for s in rows if "python_verify_seconds" in s]
                if verify:
                    median["python_verify_seconds"] = statistics.median(verify)
                result["medians"].append(median)
    (destination / "report.json").write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--output", type=Path, required=True, help="new measurement directory")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--memory-repeats", type=int, default=0,
                        help="optional independent PID-bound RSS runs (requires --observer)")
    parser.add_argument("--observer", type=Path,
                        help="path to the preflight PID observer (only with --memory-repeats)")
    parser.add_argument("--events", type=int, default=4000)
    parser.add_argument("--order", choices=("legacy", "blocked"), default="legacy",
                        help="legacy keeps the old CLI combo order; blocked rotates the combo "
                             "list by the repeat index and records the order")
    parser.add_argument("--workload", action="append", choices=("hits", "events", "mesh"))
    parser.add_argument("--format", action="append", choices=("csv", "root", "both"))
    arguments = parser.parse_args()
    assert arguments.rounds >= 0 and arguments.events > 0
    assert arguments.rounds > 0 or arguments.memory_repeats > 0
    run(arguments)
