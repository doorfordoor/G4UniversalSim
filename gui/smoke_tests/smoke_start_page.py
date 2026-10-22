"""Start page, examples gallery and the refreshed shell (GUI refresh after roadmap D).

Checks, offscreen:
  - every gallery example has bundled results and a thumbnail, and the bundled numbers
    say what its card says (Bragg peak near 158 mm, NaI photopeak at 662 keV with the
    Compton edge below it, a Landau peak with a high-energy tail, deposit falling with
    proton energy in the scan);
  - core.scan.load_manifest resolves relative point paths (bundled scans) and rebases
    the absolute paths of a scan folder that was moved;
  - the main window opens with the Start page, its cards open each example: the wizard
    spec goes into the project (package stale, outputs still go to the runs folder),
    Results / Plots shows the bundled data set, the bundled scan opens read-only with
    its quantity selected; no bundled file is written to;
  - header Theme/Language buttons are icon-only with tooltips, navigation icons are
    re-rendered on a theme change, the plot toolbar's pan/zoom buttons follow
    matplotlib's mode, the status chip and Start page follow the language.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
GUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GUI))

import numpy as np   # noqa: E402
from PySide6.QtCore import QSettings, Qt   # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox   # noqa: E402

from g4usim_gui.core import examples, scan   # noqa: E402
from g4usim_gui.core.theme import apply_theme   # noqa: E402
from g4usim_gui.output import plot_data   # noqa: E402


def check_bundles() -> None:
    assert [e.id for e in examples.EXAMPLES] == ["bragg_peak", "shielding_slab", "silicon_landau", "nai_gamma",
                                                 "energy_scan"]
    for example in examples.EXAMPLES:
        assert example.has_results(), example.id
        assert example.thumbnail().is_file(), example.id
        assert not any(p.name.startswith("hits_") or p.suffix == ".root" for p in example.folder().rglob("*"))
        example.spec()   # the overrides are valid WizardSpec fields

    bragg = examples.find("bragg_peak")
    plot = plot_data.build_plot(bragg.output_dir(), plot_data.matching(plot_data.discover(bragg.output_dir()),
                                                                       bragg.plot))
    dose = plot.series[0].y
    peak_mm = (int(np.argmax(dose)) + 0.5) * bragg.spec().thickness_mm / bragg.spec().slabs
    behind = dose[int(np.argmax(dose)) + 2:]   # secondary neutrons and photons only
    assert 150 <= peak_mm <= 165 and behind.max() < 0.01 * dose.max() and dose.max() > 3 * dose[0], (peak_mm, dose)

    def deposits(example: examples.Example) -> np.ndarray:
        values = []
        for path in sorted(example.output_dir().glob("event_edep_t*.csv")):
            values += [float(r["raw_edep_MeV"]) for r in plot_data._read_csv(path)]
        assert len(values) == example.spec().events, (example.id, len(values))
        return np.array(values)

    nai = deposits(examples.find("nai_gamma"))
    photopeak = np.sum(np.abs(nai - 0.662) < 0.002)
    edge = 0.662 * (2 * 0.662 / 0.511) / (1 + 2 * 0.662 / 0.511)   # Compton edge 0.477 MeV
    assert photopeak > 0.1 * np.sum(nai > 0) and not np.any(nai > 0.663), photopeak
    assert np.sum((nai > edge - 0.03) & (nai < edge)) > np.sum((nai > edge + 0.03) & (nai < edge + 0.06))
    for example_id in ("silicon_landau",):
        values = deposits(examples.find(example_id))
        positive = values[values > 0]
        p10, median, p90, p99 = np.percentile(positive, [10, 50, 90, 99])
        # Landau: skewed to high deposits (long tail above the peak, steep edge below it)
        assert positive.mean() > median and p90 - median > median - p10 and p99 > 1.5 * median, example_id
    # behind 10 mm Al the slower protons deposit more in the same 300 um of silicon
    shielded = deposits(examples.find("shielding_slab"))
    assert np.median(shielded[shielded > 0]) > 1.4 * np.median(positive)

    energy = examples.find("energy_scan")
    manifest = scan.load_manifest(energy.scan_dir())
    results = scan.collect(manifest)
    assert all(r.state == "success" and r.completed_events == energy.spec().events for r in results), results
    per_primary = [next(v for k, v in r.metrics.items() if k[:2] == energy.scan_quantity)[0] / r.completed_events
                   for r in results]
    assert all(a > b for a, b in zip(per_primary, per_primary[1:])), per_primary
    assert all(Path(p.output_dir).is_dir() and Path(p.output_dir).is_relative_to(energy.scan_dir())
               for p in manifest.points)


def check_moved_scan() -> None:
    with tempfile.TemporaryDirectory(prefix="g4usim-moved-scan-") as temp:
        old, new = Path(temp) / "old_scan", Path(temp) / "new_scan"
        (old / "p000" / "output").mkdir(parents=True)
        data = {"schema": scan.SCHEMA, "version": scan.VERSION, "name": "s", "parameter": "run.seed",
                "parameter_label": "seed", "values": ["1"], "scan_dir": str(old), "created": "",
                "points": [{"index": 0, "value": "1", "package_dir": str(old / "p000"),
                            "output_dir": str(old / "p000" / "output"), "main_ini": str(old / "p000" / "main.ini"),
                            "macro": "", "seed": 1}]}
        (old / "scan.json").write_text(json.dumps(data), encoding="utf-8")
        shutil.move(str(old), str(new))
        point = scan.load_manifest(new).points[0]
        assert Path(point.output_dir) == new / "p000" / "output" and Path(point.main_ini) == new / "p000" / "main.ini"
        assert point.macro == ""


def main() -> None:
    check_bundles()
    check_moved_scan()

    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("StartPage")
    QSettings().clear()
    QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    apply_theme(app, "light")
    from g4usim_gui.main_window import MainWindow   # noqa: PLC0415 - after the application exists

    stamps = {p: p.stat().st_mtime_ns for p in examples.gallery_root().rglob("*") if p.is_file()}
    window = MainWindow()
    window.resize(1400, 900)
    window.show()
    app.processEvents()
    start = window.start_page
    assert window.page_stack.currentWidget() is start and window.page_title.text() == "Start"
    assert len(start.cards) == len(examples.EXAMPLES)
    assert all(card.thumbnail.pixmap() is not None and not card.thumbnail.pixmap().isNull() for card in start.cards)

    for button in (window.theme_button, window.language_button):
        assert button.toolButtonStyle() == Qt.ToolButtonIconOnly and button.toolTip() and not button.icon().isNull()
    assert all(not b.icon().isNull() for b in window._nav_buttons)
    before = window._nav_buttons[1].icon().pixmap(18, 18).toImage()
    window._set_theme("dark")
    assert window._nav_buttons[1].icon().pixmap(18, 18).toImage() != before   # recoloured for the dark theme
    window._set_theme("light")

    for card in start.cards[:4]:
        example = card.example
        card.open_button.click()
        app.processEvents()
        assert window.project.projectName == example.id and window._generated_package_stale
        assert not Path(window.project.outputDir).resolve().is_relative_to(examples.gallery_root().resolve())
        assert window.page_stack.currentWidget() is window.output_page
        panel = window.output_page.plot_panel
        assert Path(panel._output_dir) == example.output_dir() and panel.current_dataset().key == example.plot
        assert panel.current_plot() is not None, panel.message.text()
        assert window.config_builder_page.geometry_document.volumes
    names = [v.name for v in window.config_builder_page.geometry_document.volumes]
    assert names == ["world", "Crystal"], names   # the last card opened: NaI

    start.cards[4].clicked.emit("energy_scan")
    app.processEvents()
    page = window.scan_page
    assert window.page_stack.currentWidget() is page and page.is_read_only()
    assert not page.run_button.isEnabled() and not page.rerun_button.isEnabled() and page.export_button.isEnabled()
    assert page.current_metric()[:2] == ("edep", "raw_edep") and len(page.plotted()[0]) == 5
    assert page.values.text() == examples.find("energy_scan").scan_values and page.name.text() == "energy_scan"

    panel = window.output_page.plot_panel
    panel.tool_buttons["zoom"].click()
    assert panel.tool_buttons["zoom"].isChecked() and not panel.tool_buttons["pan"].isChecked()
    panel.tool_buttons["pan"].click()
    assert panel.tool_buttons["pan"].isChecked() and not panel.tool_buttons["zoom"].isChecked()
    panel.tool_buttons["pan"].click()
    assert not panel.tool_buttons["pan"].isChecked()

    opened: list[str] = []
    start.recentProjectRequested.connect(opened.append)
    start.set_recent_projects([str(GUI / "demo_project.json")])
    buttons = [start.recent_list.itemAt(i).widget() for i in range(start.recent_list.count())]
    buttons[0].click()
    assert opened == [str(GUI / "demo_project.json")]

    window._set_language("zh_CN", persist=False)
    app.processEvents()
    assert start.cards[0].title.text() == "质子布拉格峰" and window.run_context.text().endswith("空闲")
    assert window._nav_buttons[0].text() == "开始"
    window._set_language("en", persist=False)
    assert start.cards[0].title.text() == "Proton Bragg peak" and window.run_context.text().endswith("Idle")

    after = {p: p.stat().st_mtime_ns for p in examples.gallery_root().rglob("*") if p.is_file()}
    assert after == stamps, "bundled example files were modified"
    window.close()
    window.deleteLater()
    app.processEvents()
    QSettings().clear()
    print("smoke_start_page: ok")


if __name__ == "__main__":
    main()
