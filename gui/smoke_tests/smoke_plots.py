"""Results / Plots (roadmap C1) with synthetic output fixtures and exact numbers.

Checks that every plotted number is the stored one: scorer bars and errors, mesh
profiles (sum over axes, quadrature errors, cell centres from run_metadata.json),
map orientation, Edep histograms summed over workers (binning mismatch rejected),
per-event pulse spectra, weighted phase-space spectra, run overlay and directory
comparison, CSV export, PNG export, translated notes, and the empty-directory state.
"""

from __future__ import annotations
from async_wait import wait_for_idle

import csv
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PySide6.QtWidgets import QApplication

from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.output import plot_data
from g4usim_gui.widgets.output_page import OutputPage
from g4usim_gui.widgets.plot_panel import PlotPanel


def write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


STATS = ["runID", "scorer", "quantity", "key", "name", "unit", "estimator", "n_events", "entries", "value",
         "mean_per_event", "std_error", "rel_error", "fom_per_s", "run_wall_time_s", "sum", "sum_sq"]
MESH = ["runID", "mesh", "quantity", "unit", "i0", "i1", "i2", "sum", "sum_sq", "entries", "n_events", "rel_error"]
HIST = ["bin", "low_edge_MeV", "high_edge_MeV", "center_MeV", "count"]
PHASE = ["runID", "eventID", "trackID", "parentID", "particle", "pdg", "x_mm", "y_mm", "z_mm", "u", "v", "w",
         "kineticEnergy_MeV", "time_ns", "weight"]


def fixture(root: Path, scale: float = 1.0) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for run in (0, 1):
        suffix = "" if run == 0 else f"_r{run}"
        write(root / f"scorer_statistics{suffix}.csv", STATS, [
            [run, "dose", "weighted_dose", "/world_PV#0/A_PV#0", "A_PV", "Gy", "total", 10, 10,
             2.0 * scale * (run + 1), 0, 0.1, 0.05, 0, 0, 0, 0],
            [run, "dose", "weighted_dose", "/world_PV#0/B_PV#0", "B_PV", "Gy", "total", 10, 10,
             4.0 * scale, 0, 0.2, 0.05, 0, 0, 0, 0],
        ])
    # 2 x 1 x 3 box mesh: cell (i0, 0, i2) value = 10 i0 + i2 + 1, rel error 0.1
    rows = [[0, "m", "dose", "Gy", i0, 0, i2, (10 * i0 + i2 + 1) * scale, 0, 5, 10, 0.1]
            for i0 in range(2) for i2 in range(3)]
    write(root / "scoring_mesh.csv", MESH, rows)
    (root / "run_metadata.json").write_text(json.dumps({"values": {
        "scoring_mesh_m_shape": "box", "scoring_mesh_m_bins": "2,1,3", "scoring_mesh_m_axes": "X,Y,Z",
        "scoring_mesh_m_size_mm": "10,5,30", "scoring_mesh_m_center_mm": "0,0,100"}}), encoding="utf-8")
    for thread, counts in ((0, [1, 2, 3]), (1, [10, 20, 30])):
        write(root / f"hist_edep_raw_t{thread}.csv", HIST,
              [[i, i * 0.5, (i + 1) * 0.5, i * 0.5 + 0.25, c * scale] for i, c in enumerate(counts)])
    write(root / "event_edep_t0.csv", ["runID", "eventID", "raw_edep_MeV", "weighted_edep_MeV"],
          [[0, i, v, v] for i, v in enumerate([0.0, 0.1, 0.2, 0.2, 0.4])])
    write(root / "phase_space_t0.csv", PHASE,
          [[0, 0, 1, 0, "gamma", 22, 0, 0, 0, 0, 0, 1, 1.0, 0, 2.0],
           [0, 1, 1, 0, "gamma", 22, 0, 0, 0, 0, 0, 1, 1.0, 0, 1.0],
           [0, 2, 2, 1, "e-", 11, 0, 0, 0, 0, 0, 1, 0.01, 0, 1.0]])


    (root / "run_summary.txt").write_text(
        "status = completed\nsummary_write_status = completed\noutput_failure_status = none\n"
        "run_count = 2\nplanned_event_count = 15\nactual_completed_event_count = 15\n"
        "run_0_id = 0\nrun_0_planned_events = 5\nrun_0_completed_events = 5\n"
        "run_1_id = 1\nrun_1_planned_events = 10\nrun_1_completed_events = 10\n", encoding="utf-8")
    meta_path = root / "run_metadata.json"
    meta = json.loads(meta_path.read_text())
    meta.update(schema="run_metadata_json_v1", runs=[{"run_id":0,"completed_events":5},{"run_id":1,"completed_events":10}],
                generated_files=[{"path":p.name,"schema":"fixture"} for p in root.iterdir() if p.is_file()])
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


def main() -> None:
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="g4usim-plots-") as temp:
        root, other = Path(temp) / "main", Path(temp) / "other"
        fixture(root)
        fixture(other, scale=2.0)
        datasets = {d.key: d for d in plot_data.discover(root)}
        expected = {"scorer/dose/weighted_dose/r0", "scorer/dose/weighted_dose/r1", "mesh/m/dose/r0",
                    "hist_edep_raw/r0", "event_edep/r0", "phase_space/r0"}
        assert set(datasets) == expected, sorted(datasets)

        bar = plot_data.build_plot(root, datasets["scorer/dose/weighted_dose/r0"])
        assert bar.categories == ["/world_PV#0/A_PV#0", "/world_PV#0/B_PV#0"]
        assert np.allclose(bar.series[0].y, [2.0, 4.0]) and np.allclose(bar.series[0].yerr, [0.1, 0.2])

        mesh = plot_data.load_mesh(root, datasets["mesh/m/dose/r0"])
        assert mesh.bins == (2, 1, 3) and mesh.coordinate_unit == "mm"
        assert np.allclose(mesh.centres[0], [-5, 5]) and np.allclose(mesh.centres[2], [80, 100, 120])
        profile = plot_data.mesh_profile(mesh, 2)
        assert np.allclose(profile.series[0].y, [12, 14, 16]), profile.series[0].y
        assert profile.series[0].yerr is None  # cross-cell covariance is not stored
        image = plot_data.mesh_map(mesh, 2, 0)   # x axis = Z (3 cells), y axis = X (2 cells)
        assert image.image.shape == (2, 3) and image.image[1, 0] == 11 and image.image[0, 2] == 3
        assert image.extent == (70.0, 130.0, -10.0, 10.0), image.extent

        edep = plot_data.build_plot(root, datasets["hist_edep_raw/r0"])
        assert np.allclose(edep.series[0].y, [11, 22, 33]) and np.allclose(edep.series[0].x, [0, 0.5, 1, 1.5])
        write(root / "hist_edep_raw_t2.csv", HIST, [[0, 0, 1, 0.5, 1]])
        assert np.allclose(plot_data.build_plot(root, datasets["hist_edep_raw/r0"]).series[0].y, [11, 22, 33])
        manifest = json.loads((root / "run_metadata.json").read_text())
        manifest["generated_files"].append({"path":"hist_edep_raw_t2.csv","schema":"fixture"})
        (root / "run_metadata.json").write_text(json.dumps(manifest))
        try:
            plot_data.build_plot(root, datasets["hist_edep_raw/r0"])
        except ValueError as error:
            assert "binning differs" in str(error)
        else:
            raise AssertionError("binning mismatch accepted")
        (root / "hist_edep_raw_t2.csv").unlink()
        manifest["generated_files"].pop()
        (root / "run_metadata.json").write_text(json.dumps(manifest))

        pulse = plot_data.build_plot(root, datasets["event_edep/r0"], bins=4, top=0.4)
        assert np.allclose(pulse.series[0].y * 5, [0, 1, 2, 1]), pulse.series[0].y
        phase = plot_data.build_plot(root, datasets["phase_space/r0"])
        gamma = next(s for s in phase.series if s.label == "gamma")
        assert gamma.y.sum() == 3.0 and abs(gamma.yerr.max() - np.sqrt(5.0)) < 1e-12

        export = Path(temp) / "plot.csv"
        plot_data.write_plot_csv(profile, export)
        with export.open(encoding="utf-8") as handle:
            assert [float(r["value"]) for r in csv.DictReader(handle)] == [12, 14, 16]

        print("panel")
        panel = PlotPanel()
        panel.set_output_dir(str(root))
        wait_for_idle(panel)
        assert {d.key for d in panel.datasets()} == expected
        assert panel.select("mesh/m/dose/r0")
        wait_for_idle(panel)
        assert panel.select_view("profile:2")
        wait_for_idle(panel)
        assert panel.current_plot() is not None and np.allclose(panel.current_plot().series[0].y, [12, 14, 16])
        panel.add_comparison(str(other))
        wait_for_idle(panel)
        series = panel.current_plot().series
        assert len(series) == 2 and np.allclose(series[1].y, [24, 28, 32]), [s.y for s in series]
        assert panel.select_view("map:2:0")
        wait_for_idle(panel)
        assert panel.current_plot().kind == "image"
        assert panel.select("scorer/dose/weighted_dose/r0")
        wait_for_idle(panel)
        assert len(panel.current_plot().series) == 2
        (root / "run_summary.txt").write_text("run_0_completed_events = 4\n", encoding="utf-8")
        (other / "run_summary.txt").write_text("run_0_completed_events = 4\n", encoding="utf-8")
        panel.per_event.setChecked(True)
        wait_for_idle(panel)
        assert panel.current_plot().normalization == "per_event"
        assert panel.current_plot().ylabel.endswith(" / event")
        assert panel.select("mesh/m/dose/r0")
        wait_for_idle(panel)
        assert panel.select_view("map:2:0")
        wait_for_idle(panel)
        assert panel.current_plot().value_label.endswith(" / event")
        assert panel.figure.axes[-1].get_ylabel().endswith(" / event")
        panel.per_event.setChecked(False)
        wait_for_idle(panel)
        assert panel.select("scorer/dose/weighted_dose/r0")
        wait_for_idle(panel)
        panel.clear_comparisons()
        wait_for_idle(panel)
        panel.all_runs.setChecked(True)
        wait_for_idle(panel)
        values = sorted(float(s.y[0]) for s in panel.current_plot().series)
        assert values == [2.0, 4.0], values   # A_PV in run 0 and run 1
        panel.all_runs.setChecked(False)
        wait_for_idle(panel)
        png = Path(temp) / "plot.png"
        panel.export_png(str(png))
        assert png.stat().st_size > 1000
        set_application_language(app, "zh_CN")
        panel.select("hist_edep_raw/r0")
        wait_for_idle(panel)
        assert "泊松" in panel.message.text(), panel.message.text()
        set_application_language(app, "en")
        panel.set_output_dir(str(Path(temp) / "missing"))
        wait_for_idle(panel)
        assert panel.current_plot() is None and not panel.export_png_button.isEnabled()

        page = OutputPage()
        page.set_output_dir(str(root))
        wait_for_idle(page)
        assert page.plot_panel is not None and len(page.plot_panel.datasets()) == len(expected)
        assert "Plots" in [page.tabs.tabText(i) for i in range(page.tabs.count())]

        # Destroy the widget tree (matplotlib canvas included) while the
        # QApplication still exists. PySide's cleanup at interpreter exit walks
        # every object it still owns and can double-delete a canvas/child pair,
        # which is a SIGSEGV in QObject::~QObject on Linux (offscreen platform).
        panel.close()
        panel.deleteLater()
        app.processEvents()
        del panel
    print("smoke_plots: OK")


if __name__ == "__main__":
    main()
