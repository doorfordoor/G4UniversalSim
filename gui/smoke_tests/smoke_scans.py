"""Parameter scans and batch runs (roadmap C3) without the backend.

Checks value expansion and its errors, the scannable parameters of a wizard-built
configuration, per-point changes in the generated packages (energy, particle,
material, thickness, seed, events), validation before anything is written,
manifest round trip, result collection from run_status.json / scorer_statistics.csv,
CSV export, the Parameter Scans page, and the scan runner's sequencing with an
executable that fails every point (the scan must finish, not hang).
"""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
GUI = Path(__file__).resolve().parents[1]
ROOT = GUI.parent
sys.path.insert(0, str(GUI))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from g4usim_gui.core import scan
from g4usim_gui.core import wizard as wz
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.widgets.scan_page import ScanPage


def make_base(runs_root: Path, scenario: str = "shielding") -> scan.ScanBase:
    result = wz.build(wz.default_spec(scenario))
    project = G4USimProject()
    paths = PathSettings(executable=sys.executable, workspace_root=str(ROOT), runs_root=str(runs_root),
                         materials_config=str(ROOT / "config/materials/material.ini"),
                         geometry_config=str(ROOT / "test/geometry/hierarchical_test.ini"))
    project.pathSettings = paths
    wz.apply_to_project(project, result)
    return scan.ScanBase(project=project, paths=paths, run=result.run, geometry_settings=project.geometrySettings,
                         geometry=result.geometry, source=result.source, physics=result.physics,
                         scoring=result.scoring)


def expect_error(function, text: str) -> None:
    try:
        function()
    except ValueError as error:
        assert text in str(error), (text, str(error))
    else:
        raise AssertionError(f"no error containing {text!r}")


def main() -> None:
    app = QApplication.instance() or QApplication([])
    print("values")
    assert scan.expand_values("50, 100, 150 MeV") == ["50 MeV", "100 MeV", "150 MeV"]
    assert scan.expand_values("1 keV, 2 MeV") == ["1 keV", "2 MeV"]
    assert scan.expand_values("lin(10, 50, 5) mm") == ["10 mm", "20 mm", "30 mm", "40 mm", "50 mm"]
    assert scan.expand_values("log(1, 1000, 4) MeV") == ["1 MeV", "10 MeV", "100 MeV", "1000 MeV"]
    assert scan.expand_values("proton, e-, gamma") == ["proton", "e-", "gamma"]
    expect_error(lambda: scan.expand_values(""), "no scan values")
    expect_error(lambda: scan.expand_values("1, 1 MeV"), "distinct")
    expect_error(lambda: scan.expand_values("log(0, 10, 3) MeV"), "positive")
    expect_error(lambda: scan.expand_values("lin(1, 2, 1) MeV"), "at least 2")
    expect_error(lambda: scan.expand_values("lin(1, 2, 500) MeV"), "at most")

    with tempfile.TemporaryDirectory(prefix="g4usim-scans-") as temp:
        runs = Path(temp)
        base = make_base(runs)
        keys = {p.key: p for p in scan.parameters(base)}
        for key in ("source.energy", "source.particle", "physics.reference", "run.seed", "run.beam_on",
                    "geometry.Shield.material", "geometry.Shield.thickness", "geometry.Detector.thickness"):
            assert key in keys, (key, sorted(keys))
        assert "geometry.world.thickness" not in keys

        print("points")
        point = scan.apply_value(base, keys["geometry.Shield.thickness"], "7 mm")
        assert next(v for v in point.geometry.volumes if v.name == "Shield").size.endswith(", 7 mm")
        assert next(v for v in base.geometry.volumes if v.name == "Shield").size.endswith(", 5 mm"), "base untouched"
        expect_error(lambda: scan.apply_value(base, keys["source.energy"], "100"), "unit")
        expect_error(lambda: scan.apply_value(base, keys["geometry.Shield.thickness"], "-1 mm"), "positive")
        expect_error(lambda: scan.apply_value(base, keys["run.beam_on"], "0"), "valid integer")
        problems = scan.validate_scan(base, keys["source.energy"], ["10 MeV", "lots"])
        assert len(problems) == 1 and problems[0].startswith("lots:"), problems
        expect_error(lambda: scan.create_scan(base, keys["source.energy"], ["10 MeV", "lots"], "bad", runs), "lots")
        assert not list(runs.iterdir()), "nothing written for an invalid scan"

        manifest = scan.create_scan(base, keys["source.energy"], scan.expand_values("50, 100, 200 MeV"), "energy", runs)
        assert len(manifest.points) == 3 and manifest.path.is_file()
        for point, energy in zip(manifest.points, ("50", "100", "200")):
            main_ini = Path(point.main_ini).read_text(encoding="utf-8")
            assert f"energy = {energy} MeV" in main_ini, main_ini
            assert Path(point.package_dir).parent == Path(manifest.scan_dir)
        seeds = scan.create_scan(base, keys["run.seed"], ["11", "22"], "seeds", runs)
        assert [p.seed for p in seeds.points] == [11, 22]
        assert "seed = 22" in Path(seeds.points[1].main_ini).read_text(encoding="utf-8")
        thick = scan.create_scan(base, keys["geometry.Shield.thickness"], ["1 mm", "9 mm"], "thick", runs)
        geometry = (Path(thick.points[1].package_dir) / "config/geometry/geometry.ini").read_text(encoding="utf-8")
        assert "size = 100 mm, 100 mm, 9 mm" in geometry, geometry

        loaded = scan.load_manifest(manifest.scan_dir)
        assert loaded.parameter == "source.energy" and [p.value for p in loaded.points] == manifest.values

        print("results")
        results = scan.collect(manifest)
        assert [r.state for r in results] == ["not_run"] * 3
        header = ["runID", "scorer", "quantity", "key", "name", "unit", "estimator", "n_events", "entries", "value",
                  "mean_per_event", "std_error", "rel_error", "fom_per_s", "run_wall_time_s", "sum", "sum_sq"]
        for i, point in enumerate(manifest.points[:2]):
            output = Path(point.output_dir)
            (output / "run_summary.txt").write_text(
                "status = completed\nplanned_event_count = 10\nactual_completed_event_count = 10\n"
                "simulation_executed = true\n", encoding="utf-8")
            with (output / "run_summary.txt").open("a", encoding="utf-8") as summary:
                summary.write("program_exit_code = 0\nsummary_write_status = completed\n"
                              "macro_execution_status = completed\nrun_count = 1\nrun_0_id = 0\n"
                              "run_0_planned_events = 10\nrun_0_completed_events = 10\n")
            with (output / "scorer_statistics.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerow([0, "dose", "weighted_dose", "/world_PV#0/Detector_PV#0", "Detector_PV", "Gy",
                                 "total", 10, 10, 2.0 * (i + 1), 0, 0, 0.1, 0, 0, 0, 0])
        (Path(manifest.points[1].package_dir) / "logs").mkdir(exist_ok=True)
        (Path(manifest.points[1].package_dir) / "logs/run_status.json").write_text(
            json.dumps({"state": "failed", "resultReason": "Process exited with nonzero code."}), encoding="utf-8")
        results = scan.collect(manifest)
        assert [r.state for r in results] == ["success", "failed", "not_run"], [r.state for r in results]
        metric = ("dose", "weighted_dose", "/world_PV#0/Detector_PV#0")
        assert scan.metric_keys(results) == [metric]
        assert results[1].metrics[metric] == (4.0, 0.1, "Gy") and results[1].reason.startswith("Process exited")
        export = runs / "results.csv"
        scan.write_results_csv(manifest, results, export, metric)
        with export.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert [r["dose/weighted_dose"] for r in rows] == ["2", "4", ""] and rows[0]["source.energy"] == "50 MeV"

        print("page")
        page = ScanPage()
        page.set_base_provider(lambda: (make_base(runs), str(runs), sys.executable, str(ROOT)))
        assert page.refresh_base() and page.select_parameter("geometry.Detector.material")
        page.values.setText("G4_Si, G4_Ge")
        page.name.setText("materials")
        assert page.create_scan(), page.status.text()
        assert page.manifest().parameter == "geometry.Detector.material" and page.table.rowCount() == 2
        page.load_scan(manifest.scan_dir)
        assert page.table.rowCount() == 3 and page.current_metric() == metric
        xs, ys, es = page.plotted()
        assert xs == [50.0, 100.0] and ys == [2.0, 4.0] and all(abs(e - t) < 1e-12 for e, t in zip(es, [0.2, 0.4]))
        page.per_event.setChecked(True)
        assert all(abs(y - t) < 1e-12 for y, t in zip(page.plotted()[1], [0.2, 0.4])), page.plotted()
        normalized_export = runs / "normalized_scan.csv"
        page.export_results(str(normalized_export))
        with normalized_export.open(encoding="utf-8") as stream:
            exported = list(csv.DictReader(stream))
        assert all(row["unit"].endswith(" / event") for row in exported if row["unit"])
        assert page.figure.axes[0].get_ylabel().endswith(" / event]")
        saved_events = page._results[0].completed_events
        page._results[0].completed_events = None
        try:
            page.plotted()
        except ValueError as error:
            assert "event" in str(error)
        else:
            assert False, "missing scan event count accepted"
        page._results[0].completed_events = saved_events
        page.set_base_provider(lambda: (_ for _ in ()).throw(ValueError("external mode")))
        assert not page.refresh_base() and "external mode" in page.status.text()

        print("runner")
        page.set_base_provider(lambda: (make_base(runs), str(runs), sys.executable, str(ROOT)))
        page.refresh_base()
        page.load_scan(seeds.scan_dir)
        finished: list[tuple[int, str]] = []
        page.runner.pointFinished.connect(lambda index, state: finished.append((index, state)))
        loop = QEventLoop()
        page.runner.allFinished.connect(loop.quit)
        timeout = QTimer()            # a stoppable timer: a pending singleShot would outlive the loop
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        timeout.start(120000)
        assert page.run_scan(all_points=False)
        assert not page.run_button.isEnabled() and page.stop_button.isEnabled()
        loop.exec()
        timeout.stop()
        # python.exe is not the backend: every point fails, and the scan still finishes
        assert [i for i, _ in finished] == [0, 1] and all(state != "success" for _, state in finished), finished
        assert not page.runner.is_running() and page.run_button.isEnabled()
        states = [r.state for r in scan.collect(seeds)]
        assert all(state in {"failed", "incomplete"} for state in states), states
        # Destroy the page (and its QProcess) while the QApplication still exists.
        page.close()
        page.deleteLater()
        app.processEvents()
        del page
    print("smoke_scans: OK")


if __name__ == "__main__":
    main()
