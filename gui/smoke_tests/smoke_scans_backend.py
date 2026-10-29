"""A real parameter scan (roadmap C3) through the Parameter Scans page and the backend.

The wizard's silicon detector (300 um Si pad) is scanned in proton energy (50, 100,
200 MeV). The page creates one package per point, the ScanRunner runs them with the
normal G4USimRunner, and the results table must show three successful points whose
energy deposit per event (edep / weighted_edep total) follows the NIST PSTAR silicon
electronic stopping power x areal density (within 6 %: delta electrons below the
0.7 mm production cut deposit locally, nuclear secondaries add a little). A seed scan
checks that each point's own seed reaches the backend.
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
GUI = Path(__file__).resolve().parents[1]
ROOT = GUI.parent
sys.path.insert(0, str(GUI))
sys.path.insert(0, str(ROOT / "scenarios" / "benchmarks" / "shielding_range"))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import make_reference as nist   # noqa: E402  (PSTAR table reader)
from g4usim_gui.core import scan
from g4usim_gui.core import wizard as wz
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.output.run_summary_parser import parse_run_summary
from g4usim_gui.widgets.scan_page import ScanPage

EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))


def provider(runs: Path):
    spec = wz.default_spec("silicon_detector")
    spec.events, spec.threads = 400, 2
    result = wz.build(spec)
    project = G4USimProject()
    paths = PathSettings(executable=str(EXE), workspace_root=str(ROOT), runs_root=str(runs),
                         materials_config=str(ROOT / "config/materials/material.ini"),
                         geometry_config=str(ROOT / "test/geometry/hierarchical_test.ini"))
    project.pathSettings = paths
    wz.apply_to_project(project, result)
    base = scan.ScanBase(project=project, paths=paths, run=result.run, geometry_settings=project.geometrySettings,
                         geometry=result.geometry, source=result.source, physics=result.physics,
                         scoring=result.scoring)
    return lambda: (base, str(runs), str(EXE), str(ROOT))


def run_all(app: QApplication, page: ScanPage) -> None:
    loop = QEventLoop()
    page.runner.allFinished.connect(loop.quit)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    timeout.start(900000)
    assert page.run_scan(all_points=True)
    loop.exec()
    timeout.stop()
    page.runner.allFinished.disconnect(loop.quit)
    assert not page.runner.is_running(), "scan did not finish"


def main() -> None:
    if not EXE.is_file():
        print(f"SKIP: backend executable missing: {EXE}")
        return
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="g4usim-scans-backend-") as temp:
        runs = Path(temp)
        page = ScanPage()
        page.set_base_provider(provider(runs))
        assert page.refresh_base() and page.select_parameter("source.energy")
        page.values.setText("50, 100, 200 MeV")
        page.name.setText("energy")
        assert page.create_scan(), page.status.text()
        run_all(app, page)
        results = page.results()
        assert [r.state for r in results] == ["success"] * 3, [(r.state, r.reason) for r in results]
        assert all(r.completed_events == 400 for r in results)
        metric = ("edep", "weighted_edep", "total")
        assert page.quantity.findData("|".join(metric)) >= 0
        page.quantity.setCurrentIndex(page.quantity.findData("|".join(metric)))
        page.per_event.setChecked(True)
        xs, ys, es = page.plotted()
        assert xs == [50.0, 100.0, 200.0], xs
        table = nist.pstar("G4_Si")
        energies, stopping = [r[0] for r in table], [r[1] for r in table]
        areal = 2.33 * 0.03   # g/cm2 of the 300 um pad
        for energy, deposit, error in zip(xs, ys, es):
            expected = nist.loglog(energy, energies, stopping) * areal
            print(f"  {energy:g} MeV: {deposit:.4f} +- {error:.4f} MeV per event, S x rho t = {expected:.4f}")
            assert abs(deposit - expected) <= 0.06 * expected + 3 * error, (energy, deposit, expected)
        assert ys[0] > ys[1] > ys[2], "deposit falls with energy"
        export = runs / "results.csv"
        page.export_results(str(export))
        assert export.read_text(encoding="utf-8").count("\n") == 4

        print("seed scan")
        page.select_parameter("run.seed")
        page.values.setText("101, 202")
        page.name.setText("seeds")
        assert page.create_scan(), page.status.text()
        run_all(app, page)
        seeds = []
        for point in page.manifest().points:
            facts = parse_run_summary(Path(point.output_dir) / "run_summary.txt").key_values
            seeds.append(facts.get("configured_seed") or facts.get("seed"))
        assert [r.state for r in page.results()] == ["success", "success"], page.results()
        print(f"  backend seeds: {seeds}")
        assert seeds == ["101", "202"], seeds
        page.close()
        page.deleteLater()
        app.processEvents()
        del page
    print("smoke_scans_backend: OK")


if __name__ == "__main__":
    main()
