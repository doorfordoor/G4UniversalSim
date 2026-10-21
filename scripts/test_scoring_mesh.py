"""Real Geant4 regression for command-based scoring meshes (/score/) and their export.

One 2-thread, 2-run job (format=both) on the 20 mm silicon target with
  * a 1x1x20 box mesh exactly covering the target: energyDeposit, doseDeposit, cellFlux,
    and energyDeposit with an electron-only particle filter;
  * a cylinder mesh inscribed in the target: energyDeposit.
Checks:
  1. ROOT per-worker rows merged by scripts/g4usim_io.py equal the master's merged CSV
     (values and relative errors);
  2. box-mesh energy deposit equals the event total (same volume, independent path);
  3. native doseDeposit / cellFlux validate the DoseScorer / FluenceScorer prototypes;
  4. filtered and cylinder results are bounded by the unfiltered box total;
  5. mesh layout is recorded in run_metadata.json; meshes reset between runs.
Requires uproot.
"""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import uproot  # noqa: F401
    import g4usim_io
except ImportError:
    print("SKIP: uproot is not installed")
    sys.exit(2)

CONFIG = f"""
[run]
threads = 2
seed = 2718
[output]
format = both
[materials]
file = {ROOT.as_posix()}/config/materials/material.ini
[geometry]
template = simple_box
config = {ROOT.as_posix()}/config/geometry/hit_smoke_box.ini
[physics]
reference = FTFP_BERT_EMZ
default_cut = 10 um
[source]
particle = e-
energy = 2 MeV
position_type = point
position = 0,0,-9 mm
direction = 0,0,1
[scoring]
enabled = true
hits = false
event_edep = true
edep = true
dose = true
fluence = true
auto_create_default_scorers = true
"""

MACRO = """
/score/create/boxMesh depthMesh
/score/mesh/boxSize 10. 10. 10. mm
/score/mesh/nBin 1 1 20
/score/quantity/energyDeposit eDep MeV
/score/quantity/doseDeposit dose Gy
/score/quantity/cellFlux flux
/score/quantity/energyDeposit eDepElectron MeV
/score/filter/particle electronOnly e-
/score/quantity/energyDeposit eDepGamma MeV
/score/filter/particle gammaOnly gamma
/score/close
/score/create/cylinderMesh tube
/score/mesh/cylinderSize 10. 10. mm
/score/mesh/nBin 5 4 1
/score/quantity/energyDeposit eDep MeV
/score/close
/run/initialize
/run/beamOn 80
/run/beamOn 30
"""


INI_MESHES = """
[scoring.mesh.depthMesh]
shape = box
size = 10 mm, 10 mm, 1 cm
bins = 1, 1, 20
[scoring.mesh.depthMesh.eDep]
type = energyDeposit
unit = MeV
[scoring.mesh.depthMesh.dose]
type = doseDeposit
unit = Gy
[scoring.mesh.depthMesh.flux]
type = cellFlux
[scoring.mesh.depthMesh.eDepElectron]
type = energyDeposit
unit = MeV
particles = e-
[scoring.mesh.depthMesh.eDepGamma]
type = energyDeposit
unit = MeV
particles = gamma
[scoring.mesh.tube]
shape = cylinder
size = 10 mm, 10 mm
bins = 5, 4, 1
[scoring.mesh.tube.eDep]
type = energyDeposit
unit = MeV
"""

BAD_INI_CASES = {
    "bad_type": ("[scoring.mesh.m]\nshape = box\nsize = 1 mm, 1 mm, 1 mm\nbins = 1, 1, 1\n"
                 "[scoring.mesh.m.q]\ntype = noSuchScorer\n", "generated command failed"),
    "missing_bins": ("[scoring.mesh.m]\nshape = box\nsize = 1 mm, 1 mm, 1 mm\n[scoring.mesh.m.q]\ntype = energyDeposit\n",
                     "shape, size and bins are required"),
    "orphan_quantity": ("[scoring.mesh.other.q]\ntype = energyDeposit\n", "no matching [scoring.mesh.other]"),
    "bad_shape": ("[scoring.mesh.m]\nshape = sphere\nsize = 1 mm, 1 mm, 1 mm\nbins = 1, 1, 1\n"
                  "[scoring.mesh.m.q]\ntype = energyDeposit\n", "expected box or cylinder"),
}


def run_job(work: Path, name: str, config: str, macro: str, expect_ok: bool = True) -> tuple[Path, str]:
    (work / f"{name}.ini").write_text(config, encoding="utf-8")
    (work / f"{name}.mac").write_text(macro, encoding="utf-8")
    output = work / name
    result = subprocess.run([str(EXE), "--config", str(work / f"{name}.ini"), "--macro", str(work / f"{name}.mac"),
                             "--output", str(output)], cwd=ROOT, capture_output=True, text=True,
                            errors="replace", timeout=600)
    log = result.stdout + result.stderr
    if expect_ok:
        assert result.returncode == 0, f"{name}:\n{log[-2500:]}"
    else:
        assert result.returncode != 0, f"{name}: expected failure"
    return output, log


def check_ini_equivalence(work: Path, macro_output: Path) -> None:
    """The same meshes defined in INI reproduce the macro-defined results cell by cell."""
    run_macro = MACRO[MACRO.index("/run/initialize"):]
    output, _ = run_job(work, "ini_mesh", CONFIG + INI_MESHES, run_macro)
    values = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))["values"]
    assert values["scoring_mesh_ini_command_count"] != "0", values["scoring_mesh_ini_command_count"]
    assert values["config_warning_count"] == "0", values["config_warning_count"]
    for suffix in ("", "_r1"):
        def cells(path: Path) -> dict:
            return {(r["mesh"], r["quantity"], r["i0"], r["i1"], r["i2"]): float(r["sum"])
                    for r in csv.DictReader(path.open(encoding="utf-8"))}
        from_ini = cells(output / f"scoring_mesh{suffix}.csv")
        from_macro = cells(macro_output / f"scoring_mesh{suffix}.csv")
        assert from_ini.keys() == from_macro.keys(), sorted(set(from_ini) ^ set(from_macro))[:5]
        for key, value in from_macro.items():
            rel_close(from_ini[key], value, 1e-9, f"INI vs macro {key}")
    print(f"INI meshes reproduce macro meshes cell by cell ({len(from_macro)} cells in last run)")

    for name, (section, message) in BAD_INI_CASES.items():
        _, log = run_job(work, name, CONFIG + section, "/run/initialize\n/run/beamOn 1\n", expect_ok=False)
        assert message in log, f"{name}: '{message}' not in log\n{log[-1500:]}"
    print(f"invalid [scoring.mesh.*] rejected: {', '.join(BAD_INI_CASES)}")


def rel_close(a: float, b: float, tol: float, label: str) -> None:
    assert math.isclose(a, b, rel_tol=tol, abs_tol=1e-300), f"{label}: {a!r} vs {b!r}"


def main() -> int:
    assert EXE.is_file(), f"backend executable missing: {EXE}"
    work = Path(tempfile.mkdtemp(prefix="g4usim_mesh_"))
    try:
        (work / "mesh.ini").write_text(CONFIG, encoding="utf-8")
        (work / "mesh.mac").write_text(MACRO, encoding="utf-8")
        output = work / "out"
        result = subprocess.run([str(EXE), "--config", str(work / "mesh.ini"), "--macro", str(work / "mesh.mac"),
                                 "--output", str(output)], cwd=ROOT, capture_output=True, text=True,
                                errors="replace", timeout=600)
        log = result.stdout + result.stderr
        assert result.returncode == 0, log[-2500:]
        assert "does not exist" not in log, "analysis manager reported a missing object"

        metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))["values"]
        assert metadata["scoring_mesh_count"] == "2", metadata.get("scoring_mesh_count")
        assert metadata["scoring_mesh_depthMesh_shape"] == "box"
        assert metadata["scoring_mesh_depthMesh_bins"] == "1,1,20"
        assert metadata["scoring_mesh_tube_shape"] == "cylinder"
        assert metadata["output_root_schema_version"] == "4"

        for run_id, events_expected in ((0, 80), (1, 30)):
            suffix = "" if run_id == 0 else f"_r{run_id}"
            root_path = output / f"g4usim{suffix}.root"
            with uproot.open(root_path) as root:
                events = root["events"].arrays(library="np")
                dose = root["dose"].arrays(library="np")
                fluence = root["fluence"].arrays(library="np")
            assert len(events["eventID"]) == events_expected
            event_total = float(events["raw_edep_MeV"].sum())
            assert event_total > 0

            rows = list(csv.DictReader((output / f"scoring_mesh{suffix}.csv").open(encoding="utf-8")))
            assert {r["runID"] for r in rows} == {str(run_id)}
            merged = {}
            for mesh, quantity in (("depthMesh", "eDep"), ("depthMesh", "dose"), ("depthMesh", "flux"),
                                   ("depthMesh", "eDepElectron"), ("depthMesh", "eDepGamma"),
                                   ("tube", "eDep")):
                m = g4usim_io.load_mesh(root_path, mesh, quantity)
                assert m.n_events == events_expected, (mesh, quantity, m.n_events)
                merged[(mesh, quantity)] = m
                csv_rows = [r for r in rows if r["mesh"] == mesh and r["quantity"] == quantity]
                assert csv_rows, (mesh, quantity)
                for r in csv_rows:
                    index = (int(r["i0"]), int(r["i1"]), int(r["i2"]))
                    rel_close(m.value[index], float(r["sum"]), 1e-9, f"{mesh}/{quantity}{index} sum")
                    assert abs(m.rel_error[index] - float(r["rel_error"])) < 1e-9, (mesh, quantity, index)
                    assert 0.0 < float(r["rel_error"]) <= 1.0 or int(r["entries"]) == events_expected
                    assert int(r["n_events"]) == events_expected
                assert int(m.entries.sum()) == sum(int(r["entries"]) for r in csv_rows)

            box_total = float(merged[("depthMesh", "eDep")].value.sum())
            rel_close(box_total, event_total, 1e-9, f"run {run_id} box-mesh eDep vs event total")
            rel_close(float(merged[("depthMesh", "dose")].value.mean()), float(dose["raw_dose_Gy"].sum()),
                      1e-9, f"run {run_id} native dose vs DoseScorer")
            rel_close(float(merged[("depthMesh", "flux")].value.mean()) / 100.0,
                      float(fluence["raw_fluence_mm-2"].sum()), 1e-9,
                      f"run {run_id} native cellFlux [cm-2 -> mm-2] vs FluenceScorer")
            electron = float(merged[("depthMesh", "eDepElectron")].value.sum())
            gamma = float(merged[("depthMesh", "eDepGamma")].value.sum())
            # The filters partition the deposit: e- and gamma steps carry (almost) all of it.
            assert 0.0 < gamma < 0.05 * box_total, (gamma, box_total)
            assert abs(electron + gamma - box_total) < 1e-3 * box_total, (electron, gamma, box_total)
            tube = float(merged[("tube", "eDep")].value.sum())
            assert 0.5 * box_total < electron <= box_total * (1 + 1e-12), (electron, box_total)
            assert 0.5 * box_total < tube <= box_total * (1 + 1e-12), (tube, box_total)
            # Geant4 stores cylinder bins in its own axis order (reported in metadata).
            tube_bins = tuple(int(v) for v in metadata["scoring_mesh_tube_bins"].split(","))
            assert sorted(tube_bins) == [1, 4, 5], tube_bins
            assert merged[("tube", "eDep")].bins == tube_bins, (merged[("tube", "eDep")].bins, tube_bins)
            assert len(metadata["scoring_mesh_tube_axes"].split(",")) == 3
            print(f"run {run_id}: events={events_expected} edep={event_total:.6g} MeV; box mesh == events; "
                  f"native dose/flux == DoseScorer/FluenceScorer; e- share {electron / box_total:.4f}, "
                  f"gamma share {gamma / box_total:.2e}; "
                  f"cylinder share {tube / box_total:.3f}")
        check_ini_equivalence(work, output)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_scoring_mesh: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
