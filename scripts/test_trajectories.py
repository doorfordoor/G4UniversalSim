"""Trajectory export (roadmap H1): [output] trajectories = N.

Real Geant4 runs (two threads):
  1. 100 MeV protons into a water box that holds a 20 mm silicon slab (QGSP_BIC,
     0.02 mm cut, so delta electrons and nuclear products are tracked), 120 events
     with trajectories = 40:
     - one file per worker, schema g4usim_trajectories_v1, valid JSON; events 0..39
       recorded exactly once across the files and no later event;
     - every segment lies in the volume it is labelled with: both ends inside or on
       that box (1 um), and no segment labelled water passes through the slab;
     - the primary starts at 100 MeV as "primary", its energy never rises, and its
       path length equals the hits file's summed step lengths of track 1 (1e-6);
     - the mean primary path length agrees with the NIST PSTAR CSDA range of
       100 MeV protons in water, 7.718 g/cm2, within 1.5 % + 3 sigma (the CSDA
       benchmark's tolerance; Geant4 water has I = 78 eV against PSTAR's 75 eV);
  2. trajectory_min_energy = 1 MeV: only primaries start below it;
  3. trajectory_max_points = 300: at most 300 points per file and the file is
     marked truncated;
  4. two runs in one process: the second run writes trajectories_tN_r1.json with
     "run": 1, and run_summary.txt lists the trajectory files;
  5. trajectories = -1 and trajectory_min_energy = abc are rejected before any event.
"""

from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
CSDA_WATER_100MEV_CM = 7.718      # NIST PSTAR, g/cm2 = cm in water
TOLERANCE = 0.015
BOXES = {   # half sizes and centres in mm, as in GEOMETRY
    "Water_PV": ((0.0, 0.0, 200.0), (400.0, 400.0, 200.0)),
    "Slab_PV": ((0.0, 0.0, -150.0), (100.0, 100.0, 10.0)),    # inside Water: world z = 50 mm
}
GEOMETRY = """[world]
shape = box
size = 2 m, 2 m, 2 m
material = G4_Galactic

[volume.Water]
parent = world
shape = box
size = 80 cm, 80 cm, 40 cm
material = G4_WATER
position = 0 mm, 0 mm, 200 mm
sensitive = true

[volume.Slab]
parent = Water
shape = box
size = 20 cm, 20 cm, 2 cm
material = G4_Si
position = 0 mm, 0 mm, -150 mm
sensitive = true
"""
SLAB_WORLD = ((0.0, 0.0, 50.0), (100.0, 100.0, 10.0))


EM_ONLY = "em = option4\ndefault_cut = 0.7 mm"           # the CSDA benchmark's physics
WITH_SECONDARIES = "reference = QGSP_BIC\ndefault_cut = 0.02 mm"   # delta electrons and nuclear products


def main_ini(work: Path, output_lines: str, threads: int = 2, physics: str = WITH_SECONDARIES) -> Path:
    (work / "geometry.ini").write_text(GEOMETRY, encoding="utf-8")
    ini = work / "main.ini"
    ini.write_text(f"""[run]
threads = {threads}
seed = 4242
[output]
format = csv
{output_lines}
[materials]
file = {(ROOT / 'config/materials/material.ini').as_posix()}
[geometry]
template = hierarchical
config = {(work / 'geometry.ini').as_posix()}
check_overlaps = false
[physics]
{physics}
[scoring]
enabled = true
hits = true
event_edep = false
edep = false
[source]
particle = proton
energy = 100 MeV
position_type = point
position = 0,0,-10 mm
direction = +z
""", encoding="utf-8")
    return ini


def run(work: Path, output_lines: str, beam_on=(120,), threads: int = 2,
        physics: str = WITH_SECONDARIES) -> tuple[subprocess.CompletedProcess, Path]:
    work.mkdir(parents=True, exist_ok=True)
    ini = main_ini(work, output_lines, threads, physics)
    macro = work / "run.mac"
    macro.write_text("/run/initialize\n" + "".join(f"/run/beamOn {n}\n" for n in beam_on), encoding="utf-8")
    output = work / "output"
    result = subprocess.run([str(EXE), "--config", str(ini), "--macro", str(macro), "--output", str(output)],
                            cwd=work, capture_output=True, text=True, errors="replace", timeout=1800)
    return result, output


def load(output: Path, run_id: int = 0) -> list[dict]:
    suffix = "" if run_id == 0 else f"_r{run_id}"
    files = sorted(p for p in output.glob(f"trajectories_t*{suffix}.json")
                   if (run_id == 0 and "_r" not in p.stem) or (run_id and p.stem.endswith(suffix)))
    assert files, f"no trajectory files for run {run_id} in {output}"
    documents = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    for doc in documents:
        assert doc["schema"] == "g4usim_trajectories_v1" and doc["length_unit"] == "mm" and doc["run"] == run_id
    return documents


def inside(point, box, tol=1e-3) -> bool:
    centre, half = box
    return all(abs(point[a] - centre[a]) <= half[a] + tol for a in range(3))


def world_box(name):
    if name == "Water_PV":
        return BOXES["Water_PV"]
    if name == "Slab_PV":
        return SLAB_WORLD
    return None


def check_main(work: Path) -> None:
    result, output = run(work / "main", "trajectories = 40")
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    documents = load(output)
    assert len(documents) == 2, "one file per worker"
    events = [event for doc in documents for event in doc["events"]]
    ids = sorted(event["event"] for event in events)
    assert ids == list(range(40)), ids
    assert not any(doc["truncated"] or e["truncated"] for doc in documents for e in doc["events"])

    segments = points = 0
    lengths = []
    for event in events:
        tracks = {t["track"]: t for t in event["tracks"]}
        primary = tracks[1]
        assert primary["parent"] == 0 and primary["particle"] == "proton" and primary["creator"] == "primary"
        assert abs(primary["initial_energy"] - 100.0) < 1e-9
        energies = [p[3] for p in primary["points"]]
        assert all(b <= a + 1e-9 for a, b in zip(energies, energies[1:])), "primary energy must not rise"
        lengths.append(primary["length"])
        for track in event["tracks"]:
            assert track["parent"] == 0 or track["parent"] in tracks, "every parent recorded without a filter"
            pts = track["points"]
            names = event["volumes"]
            start_box = world_box(names[pts[0][4]])
            if start_box:
                assert inside(pts[0], start_box), (track["track"], pts[0], names[pts[0][4]])
            for a, b in zip(pts, pts[1:]):
                name = names[b[4]]
                box = world_box(name)
                points += 1
                if box is None:
                    continue
                assert inside(a, box) and inside(b, box), (event["event"], track["track"], name, a, b)
                if name == "Water_PV":
                    mid = [(a[i] + b[i]) / 2 for i in range(3)]
                    assert not inside(mid, SLAB_WORLD, tol=-1e-3), ("water segment inside the slab", a, b)
                segments += 1
    print(f"geometry: {segments} segments in {sum(len(e['tracks']) for e in events)} tracks lie in their volumes")

    hits_length = defaultdict(float)
    for path in sorted(output.glob("hits_t*.csv")):
        if "_r" in path.stem:
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["trackID"] == "1" and int(row["eventID"]) < 40:
                    hits_length[int(row["eventID"])] += float(row["stepLength_mm"])
    for event in events:
        primary = next(t for t in event["tracks"] if t["track"] == 1)
        sensitive = hits_length[event["event"]]
        # the primary starts 10 mm upstream in vacuum (not sensitive): 10 mm more than the hits
        assert abs(primary["length"] - 10.0 - sensitive) <= 1e-6 * primary["length"] + 1e-6, \
            (event["event"], primary["length"], sensitive)
    print("primary path length equals the hits file's step lengths (+10 mm in vacuum)")

    secondaries = [t for e in events for t in e["tracks"] if t["parent"] != 0]
    assert len(secondaries) > 100 and any(t["particle"] == "e-" for t in secondaries), len(secondaries)
    print(f"{len(secondaries)} secondary tracks recorded, every parent present")


def check_csda(work: Path) -> None:
    """Pure water (no slab) for the CSDA comparison."""
    global GEOMETRY
    saved = GEOMETRY
    GEOMETRY = saved.split("[volume.Slab]")[0]
    try:
        result, output = run(work / "csda", "trajectories = 300", beam_on=(300,), physics=EM_ONLY)
    finally:
        GEOMETRY = saved
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    lengths = []
    for doc in load(output):
        for event in doc["events"]:
            primary = next(t for t in event["tracks"] if t["track"] == 1)
            lengths.append((primary["length"] - 10.0) / 10.0)     # cm of water after 10 mm of vacuum
    mean = sum(lengths) / len(lengths)
    sigma = math.sqrt(sum((v - mean) ** 2 for v in lengths) / (len(lengths) - 1) / len(lengths))
    allowed = TOLERANCE * CSDA_WATER_100MEV_CM + 3 * sigma
    deviation = mean - CSDA_WATER_100MEV_CM
    print(f"CSDA: mean primary path {mean:.4f} cm +- {sigma:.4f} (n={len(lengths)}) vs PSTAR "
          f"{CSDA_WATER_100MEV_CM} cm: {100 * deviation / CSDA_WATER_100MEV_CM:+.2f} % (allowed {allowed:.4f} cm)")
    assert abs(deviation) <= allowed


def check_filters(work: Path) -> None:
    result, output = run(work / "min_energy", "trajectories = 10\ntrajectory_min_energy = 1 MeV", beam_on=(10,))
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    tracks = [t for doc in load(output) for e in doc["events"] for t in e["tracks"]]
    assert all(t["parent"] == 0 or t["initial_energy"] >= 1.0 for t in tracks)
    assert any(t["parent"] != 0 for t in tracks), "some secondaries above 1 MeV (nuclear products) expected"
    result, output = run(work / "no_filter", "trajectories = 10", beam_on=(10,))
    unfiltered = [t for doc in load(output) for e in doc["events"] for t in e["tracks"]]
    assert sum(1 for t in unfiltered if t["parent"] != 0 and t["initial_energy"] < 1.0) > 0
    print(f"min energy: {len(tracks)} tracks kept, every secondary starts at >= 1 MeV "
          f"(without the filter {len(unfiltered)} tracks)")

    result, output = run(work / "cap", "trajectories = 20\ntrajectory_max_points = 300", beam_on=(20,))
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    for doc in load(output):
        total = sum(len(t["points"]) for e in doc["events"] for t in e["tracks"])
        assert total <= 300, total
        assert doc["truncated"] and any(e["truncated"] for e in doc["events"]), "cap reached must be marked"
    print("max points: files capped at 300 points and marked truncated")

    result, output = run(work / "two_runs", "trajectories = 3", beam_on=(5, 5))
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    first = sorted(e["event"] for doc in load(output, 0) for e in doc["events"])
    second = sorted(e["event"] for doc in load(output, 1) for e in doc["events"])
    assert first == second == [0, 1, 2], (first, second)
    summary = (output / "run_summary.txt").read_text(encoding="utf-8")
    assert "trajectories_t0.json" in summary and "trajectories_t0_r1.json" in summary or \
           "trajectories_t1_r1.json" in summary, "trajectory files must be listed as generated"
    print("two runs: run 0 and run 1 files, listed in run_summary.txt")


def check_errors(work: Path) -> None:
    for name, lines, needle in (("negative", "trajectories = -1", "trajectories"),
                                ("bad_energy", "trajectories = 2\ntrajectory_min_energy = abc", "")):
        result, output = run(work / name, lines, beam_on=(2,))
        assert result.returncode != 0, f"{name} must be rejected"
        assert not list(output.glob("trajectories_*.json")) if output.exists() else True
        if needle:
            assert needle in result.stdout + result.stderr
    print("invalid settings are rejected before any event")


def main() -> int:
    if not EXE.is_file():
        print(f"SKIP: backend executable missing: {EXE}")
        return 0
    with tempfile.TemporaryDirectory(prefix="g4usim-trajectories-") as temp:
        work = Path(temp)
        check_main(work)
        check_csda(work)
        check_filters(work)
        check_errors(work)
    print("test_trajectories: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
