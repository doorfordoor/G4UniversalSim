"""Q1: representable tally transactions and real transport overflow failures."""
from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))


def summary(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line)


def finite_outputs(output: Path) -> None:
    for path in output.glob("*.csv"):
        for row in csv.DictReader(path.open(encoding="utf-8")):
            for text in row.values():
                try:
                    value = float(text)
                except (TypeError, ValueError):
                    assert not (text and any(x in text.lower() for x in ("nan(ind)", "#inf", "#qnan"))), (path, text)
                    continue
                assert math.isfinite(value), (path, text)
    import numpy as np
    import uproot
    for path in output.glob("*.root"):
        with uproot.open(path) as handle:
            for obj in handle.values():
                if hasattr(obj, "arrays"):
                    for array in obj.arrays(library="np").values():
                        if array.dtype.kind in "fci":
                            assert np.isfinite(array).all(), path


def run_case(work: Path, fmt: str, threads: int, weight: float, events: int,
             fail: bool, expected_stage: str | None = None, runs: int = 1, mesh: bool = False,
             particles_per_event: tuple[int, ...] | None = None, scorer: str = "edep",
             niel_value: float = 1.0) -> None:
    name = f"{fmt}-{threads}-{weight}-{events}-{runs}-mesh{mesh}-{scorer}"
    folder = work / name
    folder.mkdir()
    geometry = folder / "geometry.ini"
    geometry.write_text("""[world]
shape = box
size = 100 mm,100 mm,100 mm
material = G4_Galactic
[volume.Target]
parent = world
shape = box
size = 10 mm,10 mm,10 mm
material = G4_WATER
sensitive = true
""", encoding="utf-8")
    phase = folder / "phase.csv"
    counts = particles_per_event or (1,) * events
    phase.write_text(
        "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight\n" +
        "".join(f"0,{i},{track+1},0,proton,2212,0,0,0,0,0,1,2,0,{weight/count}\n"
                for i, count in enumerate(counts) for track in range(count)), encoding="utf-8")
    config = folder / "main.ini"
    niel = folder / "niel.csv"
    niel.write_text(f"# Numerical stress fixture, not physical reference data\nenergy_MeV,niel_MeV_cm2_g\n0.000001,{niel_value}\n10,{niel_value}\n",
                    encoding="utf-8")
    config.write_text(f"""[run]
threads = {threads}
seed = 12345
[output]
format = {fmt}
[geometry]
template = hierarchical
config = {geometry.as_posix()}
check_overlaps = true
[physics]
reference =
modules = G4EmStandardPhysics_option4
[scoring]
enabled = {'false' if mesh else 'true'}
hits = false
event_edep = true
edep = {str(scorer == 'edep').lower()}
let = {str(scorer == 'let').lower()}
displacement = {str(scorer == 'displacement').lower()}
dose = false
fluence = false
auto_create_default_scorers = true
[source]
phase_space_file = {phase.as_posix()}
""" + (f"[scoring.displacement]\nproton = {niel.as_posix()}\n" if scorer == "displacement" else ""), encoding="utf-8")
    macro = folder / "run.mac"
    mesh_commands = ("/score/create/boxMesh numericMesh\n/score/mesh/boxSize 5 5 5 mm\n"
                     "/score/mesh/nBin 1 1 1\n/score/quantity/energyDeposit eDep MeV\n/score/close\n") if mesh else ""
    macro.write_text(mesh_commands + "/run/initialize\n" + f"/run/beamOn {events}\n" * runs, encoding="utf-8")
    output = folder / "output"
    process = subprocess.run([str(EXE), "--config", str(config), "--macro", str(macro), "--output", str(output)],
                             cwd=folder, capture_output=True, timeout=180)
    (folder / "stdout.log").write_bytes(process.stdout)
    (folder / "stderr.log").write_bytes(process.stderr)
    assert (output / "run_summary.txt").is_file(), (name, process.returncode, process.stderr[-2000:])
    values = {k.strip(): v.strip() for k, v in summary(output / "run_summary.txt").items()}
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata, name
    if fail:
        assert process.returncode != 0, name
        assert values["status"] == "failed", values
        assert values["output_failure_status"] != "none", values
        assert "finite" in values["output_failure_message"].lower(), values
        if expected_stage:
            assert values["output_failure_stage"] == expected_stage, values
        assert not (output / "scorer_statistics.csv").exists(), name
    else:
        assert process.returncode == 0, (name, process.stderr[-2000:])
        assert values["status"] == "completed", values
        assert int(values["actual_completed_event_count"]) == events * runs, values
        for run in range(runs):
            path = output / ("scorer_statistics.csv" if run == 0 else f"scorer_statistics_r{run}.csv")
            rows = list(csv.DictReader(path.open(encoding="utf-8")))
            quantity = {"edep": "weighted_edep", "let": "let_t", "displacement": "ddd_total"}[scorer]
            weighted = next(r for r in rows if r["scorer"] == scorer and r["quantity"] == quantity)
            assert int(weighted["n_events"]) == events, weighted
            assert weighted["uncertainty_estimator"] == ("uncorrected_delta_ratio_v1" if scorer == "let" else "uncorrected_event_moments_v1"), weighted
            assert weighted["uncertainty_status"] == ("approximate" if events >= 2 else "insufficient_events"), weighted
            if scorer == "edep":
                assert math.isclose(float(weighted["value"]), 2 * weight * events, rel_tol=1e-9), weighted
            else:
                assert float(weighted["value"]) > 0.0, weighted
    finite_outputs(output)
    print(f"{name}: {'rejected with failed summary' if fail else 'finite results verified'}")


def main() -> None:
    assert EXE.is_file(), EXE
    model = EXE.with_name("scoringNumericCheck" + EXE.suffix)
    assert model.is_file(), f"build the BUILD_TESTING scoringNumericCheck target: {model}"
    result = subprocess.run([str(model)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "checks=38" in result.stdout, result.stdout
    with tempfile.TemporaryDirectory(prefix="g4usim_numeric_") as temp:
        work = Path(temp)
        for fmt in ("csv", "root", "both"):
            for threads in (1, 2):
                run_case(work, fmt, threads, 0.5, 4, False, runs=2)
                run_case(work, fmt, threads, 1e308, 2, True, "scoring_event_accumulate")
                run_case(work, fmt, threads, 1e200, 2, True, "scoring_end_event")
        # Finite per-event squares overflow only when histories are combined.
        run_case(work, "both", 2, 4e153, 4, True)
        run_case(work, "both", 1, 0.5, 1, False)
        # Q1's MT matrix also includes four workers and repeated runs.
        run_case(work, "both", 4, 0.5, 8, False, runs=2)
        run_case(work, "root", 4, 4e153, 8, True)
        for fmt in ("csv", "root", "both"):
            run_case(work, fmt, 2, 1e200, 2, True, mesh=True)
        # Equal event moments, but one long history ensures both workers receive
        # a history. Each worker's square is finite; only the master merge overflows.
        run_case(work, "root", 2, 6e153, 2, True, "scoring_mesh_csv", mesh=True,
                 particles_per_event=(100, 1))
        for threads in (1, 2):
            for scorer in ("let", "displacement"):
                run_case(work, "both", threads, 0.5, 3, False, scorer=scorer)
                run_case(work, "both", threads, 1e200, 2, True, "scoring_end_event", scorer=scorer)
            run_case(work, "both", threads, 1e308, 2, True, "scoring_let", scorer="let")
            run_case(work, "both", threads, 1e150, 2, True, "scoring_displacement",
                     scorer="displacement", niel_value=1e200)
    print("scoring numeric: model checks and real worker failures passed")


if __name__ == "__main__":
    main()
