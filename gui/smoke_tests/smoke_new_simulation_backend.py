"""Every new-simulation wizard scenario (roadmap C2) runs on the real backend.

For each scenario the wizard spec goes through the GUI's generated-package path
(core.wizard.build -> create_run_package, the same validation and writers as the
editors), the package runs in Geant4, and a physics sanity check confirms the
geometry and source mean what the wizard says:
  depth_dose          150 MeV protons, 40 x 5 mm water slabs: the dose peaks in the
                      slab containing the Bragg peak (~157 mm)
  shielding           100 MeV protons through 5 mm Al: track-length fluence in the
                      detector ~ N / detector face area (broad beam inside the face)
  gamma_spectrometer  662 keV photons on NaI: full-energy events in event_edep
  silicon_detector    100 MeV protons in 300 um Si: median deposit near S x t
  single_target       completes with dose in the target
and the Results / Plots data sets are found for the output.
"""

from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
GUI = Path(__file__).resolve().parents[1]
ROOT = GUI.parent
sys.path.insert(0, str(GUI))

from g4usim_gui.core import wizard as wz
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.output import plot_data
from g4usim_gui.writers.package_writer import create_run_package

EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))


def run_scenario(spec: wz.WizardSpec, runs_root: Path) -> Path:
    result = wz.build(spec)
    project = G4USimProject()
    project.pathSettings = PathSettings(executable=str(EXE), workspace_root=str(ROOT), runs_root=str(runs_root),
                                        materials_config=str(ROOT / "config/materials/material.ini"),
                                        geometry_config=str(ROOT / "test/geometry/hierarchical_test.ini"))
    wz.apply_to_project(project, result)
    package, _ = create_run_package(
        project=project, paths=project.pathSettings, run=result.run, geometry=project.geometrySettings,
        source=project.sourceSettings, physics=project.physicsSettings, scoring=project.scoringSettings,
        geometry_document=result.geometry, source_model=result.source, physics_model=result.physics,
        scoring_model=result.scoring)
    process = subprocess.run([str(EXE), "--config", package.main_ini_path, "--macro", package.run_macro_path,
                              "--output", package.output_dir], cwd=package.package_dir, capture_output=True,
                             text=True, errors="replace", timeout=1800)
    assert process.returncode == 0, (process.stdout + process.stderr)[-3000:]
    output = Path(package.output_dir)
    summary = (output / "run_summary.txt").read_text(encoding="utf-8")
    assert "status = completed" in summary and f"actual_completed_event_count = {spec.events}" in summary
    return output


def statistics(output: Path, scorer: str, quantity: str) -> dict[str, float]:
    with (output / "scorer_statistics.csv").open(newline="", encoding="utf-8") as handle:
        return {r["key"]: float(r["value"]) for r in csv.DictReader(handle)
                if r["scorer"] == scorer and r["quantity"] == quantity}


def deposits(output: Path) -> list[float]:
    values = []
    for path in output.glob("event_edep_t*.csv"):
        if re.fullmatch(r"event_edep_t\d+\.csv", path.name):
            with path.open(newline="", encoding="utf-8") as handle:
                values += [float(r["raw_edep_MeV"]) for r in csv.DictReader(handle)]
    return values


def main() -> None:
    if not EXE.is_file():
        print(f"SKIP: backend executable missing: {EXE}")
        return
    with tempfile.TemporaryDirectory(prefix="g4usim-wizard-backend-") as temp:
        runs = Path(temp)
        print("depth_dose")
        spec = wz.default_spec("depth_dose")
        spec.events = 400
        output = run_scenario(spec, runs)
        dose = statistics(output, "dose", "weighted_dose")
        by_slab = [dose.get(f"/world_PV#0/Slab{i:03d}_PV#0", 0.0) for i in range(spec.slabs)]
        peak = max(range(spec.slabs), key=lambda i: by_slab[i])
        print(f"  dose peaks in slab {peak} ({peak * 5}-{peak * 5 + 5} mm)")
        assert peak in (30, 31), by_slab
        keys = {d.key for d in plot_data.discover(output)}
        assert "scorer/dose/weighted_dose/r0" in keys and "event_edep/r0" in keys, keys

        print("shielding")
        spec = wz.default_spec("shielding")
        spec.events = 2000
        output = run_scenario(spec, runs)
        fluence = statistics(output, "fluence", "weighted_fluence")["/world_PV#0/Detector_PV#0"]
        # track-length fluence averages over the detector volume: every primary crosses it once,
        # so Phi = N / (detector face area); secondaries and scattering add a few per cent
        expected = spec.events / spec.lateral_mm ** 2
        print(f"  detector fluence {fluence:.5g} mm-2, N / A_detector = {expected:.5g} mm-2")
        assert 0.95 * expected < fluence < 1.15 * expected, (fluence, expected)
        assert statistics(output, "dose", "weighted_dose")["/world_PV#0/Detector_PV#0"] > 0

        print("gamma_spectrometer")
        spec = wz.default_spec("gamma_spectrometer")
        spec.events = 20000
        output = run_scenario(spec, runs)
        values = deposits(output)
        full = sum(1 for v in values if abs(v - 0.662) <= 1e-3)
        print(f"  {full} full-energy events of {len(values)}")
        assert len(values) == spec.events and full > 50 and max(values) <= 0.663, (full, max(values))

        print("silicon_detector")
        spec = wz.default_spec("silicon_detector")
        spec.events = 2000
        output = run_scenario(spec, runs)
        positive = sorted(v for v in deposits(output) if v > 0)
        median = positive[len(positive) // 2]
        # S(100 MeV protons, Si) ~ 5.8 MeV cm2/g: mean loss in 300 um ~ 0.41 MeV, median below it
        print(f"  median deposit {median:.4f} MeV")
        assert 0.30 < median < 0.45, median

        print("single_target")
        spec = wz.default_spec("single_target")
        spec.events = 200
        output = run_scenario(spec, runs)
        assert statistics(output, "dose", "weighted_dose")["/world_PV#0/Target_PV#0"] > 0
    print("smoke_new_simulation_backend: OK")


if __name__ == "__main__":
    main()
