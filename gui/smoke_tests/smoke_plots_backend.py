"""Results / Plots (roadmap C1) on real Geant4 output.

Runs the backend twice in one process (two runs, format = both) for 150 MeV protons
in water with a dose mesh, Dose/Fluence/Edep scorers, per-event deposits and a
phase-space plane, plus a ROOT-only run, and checks that the Plots tab finds every
data set, that the CSV and ROOT mesh readers give identical arrays, that the depth
profile peaks at the Bragg peak (~157 mm), that scorer bars equal the merged
scorer_statistics.csv, and that run overlay and directory comparison draw.
"""

from __future__ import annotations
from async_wait import wait_for_idle

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
GUI = Path(__file__).resolve().parents[1]
ROOT = GUI.parent
sys.path.insert(0, str(GUI))

import numpy as np
from PySide6.QtWidgets import QApplication

from g4usim_gui.output import plot_data
from g4usim_gui.widgets.plot_panel import PlotPanel

EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))

GEOMETRY = """
[world]
shape = box
size = 1 m, 1 m, 1 m
material = G4_Galactic
[volume.Phantom]
parent = world
shape = box
size = 60 mm, 60 mm, 200 mm
material = G4_WATER
position = 0 mm, 0 mm, 100 mm
sensitive = true
[volume.Plane]
parent = world
shape = box
size = 200 mm, 200 mm, 1 mm
material = G4_Galactic
position = 0 mm, 0 mm, 210 mm
"""

MAIN = """
[run]
threads = 2
seed = 3
[output]
format = {format}
[materials]
file = {root}/config/materials/material.ini
[geometry]
template = hierarchical
config = {geometry}
[physics]
reference = QGSP_BIC_EMZ
[scoring]
enabled = true
hits = false
event_edep = true
edep = true
dose = true
fluence = true
[source]
particle = proton
energy = 150 MeV
position_type = point
position = 0,0,-10 mm
direction = +z
[phase_space]
volume = Plane_PV
particles = all
kill = true
[scoring.mesh.depth]
shape = box
size = 30 mm, 30 mm, 100 mm
bins = 20, 1, 100
center = 0 mm, 0 mm, 100 mm
[scoring.mesh.depth.dose]
type = doseDeposit
unit = Gy
"""


def run(work: Path, name: str, fmt: str) -> Path:
    (work / "geometry.ini").write_text(GEOMETRY, encoding="utf-8")
    ini = work / f"{name}.ini"
    ini.write_text(MAIN.format(format=fmt, root=ROOT.as_posix(), geometry=(work / "geometry.ini").as_posix()),
                   encoding="utf-8")
    mac = work / "run.mac"
    mac.write_text("/run/initialize\n/run/beamOn 300\n/run/beamOn 200\n", encoding="utf-8")
    output = work / name
    result = subprocess.run([str(EXE), "--config", str(ini), "--macro", str(mac), "--output", str(output)],
                            cwd=work, capture_output=True, text=True, errors="replace", timeout=900)
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    return output


def main() -> None:
    if not EXE.is_file():
        print(f"SKIP: backend executable missing: {EXE}")
        return
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="g4usim-plots-backend-") as temp:
        work = Path(temp)
        both = run(work, "both", "both")
        root_only = run(work, "root_only", "root")
        datasets = {d.key: d for d in plot_data.discover(both)}
        for key in ("scorer/dose/weighted_dose/r0", "scorer/fluence/weighted_fluence/r1", "mesh/depth/dose/r0",
                    "mesh/depth/dose/r1", "hist_edep_raw/r0", "event_edep/r1", "phase_space/r0"):
            assert key in datasets, (key, sorted(datasets))

        csv_mesh = plot_data.load_mesh(both, datasets["mesh/depth/dose/r0"])
        root_set = plot_data.DataSet("mesh", "mesh/depth/dose/r0", "", 0, ("depth", "dose", "root"))
        root_mesh = plot_data.load_mesh(both, root_set)
        assert csv_mesh.bins == root_mesh.bins == (20, 1, 100)
        assert np.allclose(csv_mesh.value, root_mesh.value, rtol=1e-9, atol=0), "CSV and ROOT meshes differ"
        assert np.allclose(csv_mesh.error, root_mesh.error, rtol=1e-6, atol=1e-30)
        profile = plot_data.mesh_profile(csv_mesh, 2)
        peak = float(profile.series[0].x[np.argmax(profile.series[0].y)])
        print(f"  depth-dose peak at {peak} mm")
        assert 150.0 <= peak <= 162.0, peak

        with (both / "scorer_statistics.csv").open(newline="", encoding="utf-8") as handle:
            rows = [r for r in csv.DictReader(handle) if r["scorer"] == "dose" and r["quantity"] == "weighted_dose"]
        bars = plot_data.build_plot(both, datasets["scorer/dose/weighted_dose/r0"])
        assert np.allclose(bars.series[0].y, [float(r["value"]) for r in rows])
        assert np.allclose(bars.series[0].yerr, [float(r["std_error"]) for r in rows])

        panel = PlotPanel()
        panel.set_output_dir(str(both))
        wait_for_idle(panel)
        assert panel.select("mesh/depth/dose/r0")
        wait_for_idle(panel)
        assert panel.select_view("profile:2")
        wait_for_idle(panel)
        panel.all_runs.setChecked(True)
        wait_for_idle(panel)
        assert len(panel.current_plot().series) == 2, "run overlay"
        totals = [s.y.sum() for s in panel.current_plot().series]
        panel.per_event.setChecked(True)
        wait_for_idle(panel)
        per_event = [s.y.sum() for s in panel.current_plot().series]
        assert np.allclose(per_event, [totals[0] / 300, totals[1] / 200]), (totals, per_event)
        # per event, the two runs agree within their statistics (same beam, 300 vs 200 events)
        assert abs(per_event[0] / per_event[1] - 1) < 0.1, per_event
        panel.per_event.setChecked(False)
        wait_for_idle(panel)
        panel.all_runs.setChecked(False)
        wait_for_idle(panel)
        panel.add_comparison(str(root_only))
        wait_for_idle(panel)
        compared = panel.current_plot().series
        assert len(compared) == 2 and compared[1].label == "root_only", [s.label for s in compared]
        assert panel.select_view("map:2:0")
        wait_for_idle(panel)
        assert panel.current_plot().image.shape == (20, 100)
        for key in ("hist_edep_raw/r0", "event_edep/r1", "phase_space/r0", "scorer/fluence/weighted_fluence/r1"):
            assert panel.select(key), key
            wait_for_idle(panel)
            assert panel.current_plot() is not None, key
        png = work / "plot.png"
        panel.export_png(str(png))
        assert png.stat().st_size > 1000

        # Destroy the widget tree (matplotlib canvas included) while the
        # QApplication still exists. PySide's cleanup at interpreter exit walks
        # every object it still owns and can double-delete a canvas/child pair,
        # which is a SIGSEGV in QObject::~QObject on Linux (offscreen platform).
        panel.close()
        panel.deleteLater()
        app.processEvents()
        del panel
    print("smoke_plots_backend: OK")


if __name__ == "__main__":
    main()
