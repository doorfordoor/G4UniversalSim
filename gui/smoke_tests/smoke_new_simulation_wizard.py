"""Guided new-simulation wizard (roadmap C2) without the backend.

Checks the wizard model (defaults, validation, geometry rows, source mapping, in-place
project update), drives the QWizard pages, and applies a wizard result in the main
window: the Configuration page shows the generated geometry/source/physics/scoring,
validation passes, and a generated package contains the wizard's volumes.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from g4usim_gui.core import wizard as wz
from g4usim_gui.core.i18n import set_application_language, ui_format
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.main_window import MainWindow
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard


def mm(text: str) -> list[float]:
    return [float(part.strip().split()[0]) for part in text.split(",")]


def main() -> None:
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("NewSimulationWizard")
    QSettings().clear()

    print("model")
    for scenario in wz.SCENARIOS:
        spec = wz.default_spec(scenario)
        assert not wz.validate_spec(spec), (scenario, wz.validate_spec(spec))
        result = wz.build(spec)
        assert result.geometry.mode == "hierarchical" and result.geometry.is_dirty
        assert result.geometry.volumes[0].name == "world" and result.sensitive_volumes
        assert not result.source.errors and not result.physics.errors and not result.scoring.errors
        assert all(ui_format(t, **v) for t, v in wz.summary(spec))

    spec = wz.default_spec("depth_dose")
    spec.slabs, spec.thickness_mm = 8, 40.0
    result = wz.build(spec)
    slabs = result.geometry.volumes[1:]
    assert len(slabs) == 8 and all(v.sensitive for v in slabs)
    edges = [(mm(v.position)[2] - mm(v.size)[2] / 2, mm(v.position)[2] + mm(v.size)[2] / 2) for v in slabs]
    assert abs(edges[0][0]) < 1e-9 and abs(edges[-1][1] - 40.0) < 1e-9
    assert all(abs(a[1] - b[0]) < 1e-9 for a, b in zip(edges, edges[1:])), "slabs are contiguous"
    assert result.source.position_mode == "plane" and result.source.source_shape == "rectangle"

    gamma = wz.build(wz.default_spec("gamma_spectrometer"))
    assert gamma.geometry.volumes[1].shape == "tubs" and gamma.source.angular_mode == "isotropic"
    shield = wz.build(wz.default_spec("shielding"))
    assert [v.name for v in shield.geometry.volumes] == ["world", "Shield", "Detector"]
    assert shield.sensitive_volumes == ["Detector"]

    bad = wz.default_spec("single_target")
    bad.thickness_mm, bad.target_material, bad.events = -1.0, "Unobtainium", 0
    bad.hits = bad.event_edep = bad.dose = bad.fluence = False
    messages = [t for t, _ in wz.validate_spec(bad)]
    for expected in ("{field} must be a finite positive number.", "{field} {value} is not offered by the wizard.",
                     "At least one event is required.", "Choose at least one output."):
        assert expected in messages, (expected, messages)
    try:
        wz.build(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid spec built")

    project = G4USimProject()
    project.pathSettings.geometry_config = "geometry.ini"
    original = project
    wz.apply_to_project(project, wz.build(wz.default_spec("silicon_detector")))
    assert project is original and project.runInputMode == "generated" and project.configPath == ""
    assert project.geometryEditor.volumes[1].name == "Pad" and project.geometrySettings.config_path == "geometry.ini"
    assert project.runSettings.beam_on == 1000 and project.sourceEditor.energy == "100 MeV"

    print("dialog")
    set_application_language(app, "zh_CN")
    wizard = NewSimulationWizard()
    wizard.show()
    page = wizard.scenario_page
    page.list.setCurrentRow(wz.SCENARIOS.index("shielding"))
    assert wizard.spec.scenario == "shielding" and page.name.text() == "shielding"
    assert "屏蔽" in page.description.text()
    wizard.next()
    geometry = wizard.geometry_page
    assert geometry.detector_material.isVisibleTo(geometry) and not geometry.slabs.isVisibleTo(geometry)
    geometry.target_material.setCurrentIndex(geometry.target_material.findData("G4_Pb"))
    geometry.thickness.setValue(2.0)
    wizard.next()
    wizard.source_page.particle.setCurrentIndex(wizard.source_page.particle.findData("e-"))
    wizard.source_page.energy.setValue(5.0)
    wizard.next()
    run = wizard.run_page
    assert run.isComplete(), run.summary.toPlainText()
    assert "屏蔽层：G4_Pb，2 mm" in run.summary.toPlainText(), run.summary.toPlainText()
    run.seed.setText("abc")
    assert not run.isComplete() and "随机种子必须是整数" in run.summary.toPlainText()
    run.seed.setText("7")
    run.events.setValue(321)
    assert run.isComplete()
    final = wizard.spec
    assert (final.scenario, final.target_material, final.thickness_mm, final.particle, final.energy_MeV,
            final.events, final.seed) == ("shielding", "G4_Pb", 2.0, "e-", 5.0, 321, 7), final
    set_application_language(app, "en")

    print("main window")
    # Modal boxes would block the offscreen run: record them instead.
    boxes: list[str] = []
    QMessageBox.warning = staticmethod(lambda _parent, _title, message, *a: boxes.append(f"warning: {message}"))
    QMessageBox.information = staticmethod(lambda _parent, _title, message, *a: boxes.append(f"info: {message}"))
    window = MainWindow()
    with tempfile.TemporaryDirectory(prefix="g4usim-wizard-") as temp:
        window.project.runsRoot = temp
        window.project.executable = sys.executable          # any existing file passes the path check
        window.project.pathSettings.executable = sys.executable
        window.project_page.set_project(window.project)
        project_before = window.project
        assert window.apply_simulation_wizard(final, run_after=False)
        assert window.project is project_before, "project updated in place"
        page = window.config_builder_page
        assert window.page_stack.currentWidget() is page
        assert [v.name for v in page.geometry_document.volumes] == ["world", "Shield", "Detector"]
        assert page.source_editor.particle == "e-" and page.run_settings().beam_on == 321
        # materials are validated against the wizard geometry, not the source geometry file
        assert not page.material_document.errors, page.material_document.errors
        assert "Geometry: 3 volumes" in page.workspace_summary.text(), page.workspace_summary.text()
        report = page.validate_current(window.project)
        assert report.can_run, report.to_text()
        window.generate_package(run_after_generate=False)
        assert not any(box.startswith("warning") for box in boxes), boxes
        packages = list(Path(temp).glob("*shielding*"))
        assert len(packages) == 1, list(Path(temp).iterdir())
        geometry_text = (packages[0] / "config" / "geometry" / "geometry.ini").read_text(encoding="utf-8")
        assert "[volume.Shield]" in geometry_text and "material = G4_Pb" in geometry_text
        main_text = (packages[0] / "config" / "main.ini").read_text(encoding="utf-8")
        assert "particle = e-" in main_text and "energy = 5 MeV" in main_text, main_text
        assert "/run/beamOn 321" in (packages[0] / "macros" / "run.mac").read_text(encoding="utf-8")
    window.close()
    print("smoke_new_simulation_wizard: OK")


if __name__ == "__main__":
    main()
