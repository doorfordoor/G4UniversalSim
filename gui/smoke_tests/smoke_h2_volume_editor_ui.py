"""H2-3 Run Config editor UI smoke for volume filters and spectra.

The optional sections are edited inside the existing Configuration page's
Scoring tab. This smoke proves the existing editing entry (widgets -> editor
model -> main.ini writer -> project serializer) carries them without adding a
parallel panel; the C++ consumer is covered by the backend regression.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from g4usim_gui.core.project import G4USimProject, load_project, project_to_dict, save_project  # noqa: E402
from g4usim_gui.models.package_model import GeometrySettings, RunPackage  # noqa: E402
from g4usim_gui.models.physics_model import PhysicsSettings  # noqa: E402
from g4usim_gui.models.run_model import RunSettings  # noqa: E402
from g4usim_gui.models.scoring_model import ScoringSettings  # noqa: E402
from g4usim_gui.models.source_model import SourceSettings  # noqa: E402
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage  # noqa: E402
from g4usim_gui.editors.source_physics_scoring_model import validate_scoring_model  # noqa: E402
from g4usim_gui.writers.main_ini_writer import build_main_ini_text  # noqa: E402


def _package() -> RunPackage:
    return RunPackage(
        package_dir="<package>",
        config_dir="<package>/config",
        macro_dir="<package>/macros",
        logs_dir="<package>/logs",
        output_dir="<package>/output",
        main_ini_path="<package>/config/main.ini",
        run_macro_path="<package>/macros/run.mac",
        validation_report_path="<package>/validation_report.txt",
        project_snapshot_path="<package>/project_snapshot.json",
        materials_ini_path="<package>/config/materials/material.ini",
        geometry_ini_path="<package>/config/geometry/geometry.ini",
    )


def _main_ini(model) -> str:
    return build_main_ini_text(
        package=_package(),
        run=RunSettings(run_name="h2_ui", threads=1),
        geometry=GeometrySettings(template="simple_box", config_path="<package>/config/geometry/geometry.ini"),
        source=SourceSettings(),
        physics=PhysicsSettings(),
        scoring=ScoringSettings(),
        scoring_model=model,
    )


def main() -> int:
    app = QApplication.instance() or QApplication([])

    page = ConfigBuilderPage()
    page._populate_sps_editors()
    assert sorted(page.scoring_editor_filter_widgets) == ["dose", "fluence", "let"]
    assert sorted(page.scoring_editor_spectrum_widgets) == ["dose", "fluence"]
    print("ok: existing Scoring tab exposes volume filter and spectrum rows")

    # Edit through the existing widgets; the page's normal handler collects.
    dose_enabled, dose_particles, dose_min, dose_max = page.scoring_editor_filter_widgets["dose"]
    page.scoring_editor_dose.setChecked(True)
    dose_enabled.setChecked(True)
    dose_particles.setText("e-,gamma")
    dose_min.setText("1 MeV")
    dose_max.setText("10 MeV")
    fluence_enabled, fluence_bins, fluence_min, fluence_max = page.scoring_editor_spectrum_widgets["fluence"]
    page.scoring_editor_fluence.setChecked(True)
    fluence_enabled.setChecked(True)
    fluence_bins.setValue(10)
    fluence_min.setText("0.5 MeV")
    fluence_max.setText("1.5 MeV")
    page._update_sps_from_widgets()
    assert page.scoring_editor.volume_filters["dose"] == {
        "enabled": True, "particles": "e-,gamma", "energy_min": "1 MeV", "energy_max": "10 MeV",
    }, page.scoring_editor.volume_filters["dose"]
    assert page.scoring_editor.volume_spectra["fluence"] == {
        "enabled": True, "bins": 10, "min": "0.5 MeV", "max": "1.5 MeV",
    }, page.scoring_editor.volume_spectra["fluence"]
    assert page.scoring_editor.is_dirty
    print("ok: widget edits collect into the scoring model")

    # Model -> widget round-trip keeps the same values.
    page.scoring_editor.volume_filters["dose"]["particles"] = "proton"
    page.scoring_editor.volume_spectra["fluence"]["max"] = "2 MeV"
    page._populate_sps_editors()
    assert dose_particles.text() == "proton"
    assert fluence_max.text() == "2 MeV"
    assert dose_enabled.isChecked() and fluence_enabled.isChecked()
    print("ok: model repopulates the same widgets")

    # The writer emits the exact optional sections from the edited model.
    text = _main_ini(page.scoring_editor)
    assert "[scoring.filter.dose]" in text and "particles = proton" in text
    assert "[scoring.spectrum.fluence]" in text and "max = 2 MeV" in text
    print("ok: writer emits the edited optional sections")

    # The bins spin box and the model share the backend limit 1..1000000, and
    # the model refuses non-integers/overflow instead of truncating them.
    for scorer, widgets in page.scoring_editor_spectrum_widgets.items():
        _enabled, bins_spin, _low, _high = widgets
        assert bins_spin.minimum() == 1 and bins_spin.maximum() == 1_000_000, (
            scorer, bins_spin.minimum(), bins_spin.maximum())
    fluence_bins.setValue(1_000_000)
    page._update_sps_from_widgets()
    page._validate_sps_editors()
    assert not page.scoring_editor.errors, page.scoring_editor.errors
    edge_text = _main_ini(page.scoring_editor)
    assert "bins = 1000000" in edge_text, edge_text
    fluence_bins.setValue(1_000_001)  # QSpinBox clamps to its maximum
    assert fluence_bins.value() == 1_000_000, fluence_bins.value()
    for bad in (1_000_001, 2.5):
        page.scoring_editor.volume_spectra["fluence"]["bins"] = bad
        validate_scoring_model(page.scoring_editor)
        assert any("spectrum bins must be an integer in 1..1000000" in error
                   for error in page.scoring_editor.errors), (bad, page.scoring_editor.errors)
        try:
            _main_ini(page.scoring_editor)
        except ValueError:
            pass
        else:
            raise AssertionError(f"writer accepted invalid spectrum bins {bad!r}")
    page.scoring_editor.volume_spectra["fluence"]["bins"] = 10
    validate_scoring_model(page.scoring_editor)
    print("ok: bins stay within the backend 1..1000000 integer bound")

    # Invalid rows surface through the existing editor diagnostics.
    page.scoring_editor_fluence.setChecked(False)
    page._update_sps_from_widgets()
    page._validate_sps_editors()
    message = page.scoring_editor_messages.toPlainText()
    assert "fluence spectrum requires" in message, message
    print("ok: invalid configuration is diagnosed through the existing messages panel")

    # Project save/load keeps the edited rows (undo/redo rides the same model).
    project = G4USimProject(projectName="h2_ui_roundtrip")
    project.scoringEditor = page.scoring_editor
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "project.json"
        save_project(project, path)
        loaded = load_project(path)
    assert loaded.scoringEditor.volume_filters["dose"]["particles"] == "proton"
    assert loaded.scoringEditor.volume_spectra["fluence"]["max"] == "2 MeV"
    assert "volume_filters" in project_to_dict(loaded)["scoringEditor"]
    print("ok: project serialization keeps the volume configuration")

    # An untouched project adds no optional section.
    fresh = ConfigBuilderPage()
    fresh._populate_sps_editors()
    assert "[scoring.filter." not in _main_ini(fresh.scoring_editor)
    assert "[scoring.spectrum." not in _main_ini(fresh.scoring_editor)
    print("ok: an untouched project adds no optional sections")

    app.processEvents()
    print("PASS: H2-3 Configuration page volume filter/spectrum UI smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
