"""The setup column must not reset the Source editor's geometry or angular mode.

Regression for a P0 defect: `RunConfigMixin._update_sps_from_summary_widgets` used to
force

    source_editor.position_mode = "point"
    source_editor.position_type = "point"
    source_editor.source_shape = "point"
    source_editor.angular_mode = "fixed"

while the setup column only mirrors the scalar source fields (preset/particle/energy/
position/direction) plus physics/scoring fields. Because `writers/main_ini_writer.py`
derives `position_type`, `center`, `halfx`/`halfy` and `isotropic` from those model
fields, editing e.g. the source energy in the setup column silently turned a configured
plane/rectangle isotropic source into a point source with a fixed direction. The run
still "succeeded", with the wrong physics and no warning.

The test drives the real page (setup column + Run Config editor), triggers every signal
that used to reach the resetting slot, and renders the real writer output to a temporary
main.ini. The preserved fields must still be there, and point-only keys must not be
written.

Run: gui/.venv/Scripts/python.exe -B gui/smoke_tests/smoke_source_field_preservation.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QSettings   # noqa: E402
from PySide6.QtWidgets import QApplication   # noqa: E402

from g4usim_gui.models.package_model import RunPackage   # noqa: E402
from g4usim_gui.parsers.ini_light_parser import parse_ini_light   # noqa: E402
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage   # noqa: E402
from g4usim_gui.writers.main_ini_writer import write_main_ini   # noqa: E402

# Same placeholder package as the page's own main.ini preview; no real files are needed.
PACKAGE = RunPackage(
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

CENTER = "1 mm, -2 mm, 3 mm"
HALFX = "4 mm"
HALFY = "5 mm"


def _edit(widget, text: str) -> None:
    """Type into a QLineEdit as the user would (setText alone does not emit textEdited)."""
    widget.setText(text)
    widget.textEdited.emit(text)


def _write_source_ini(page: ConfigBuilderPage, path: Path) -> dict[str, str]:
    """Render the page through the real writer and return the parsed [source] section."""
    write_main_ini(
        path,
        package=PACKAGE,
        run=page.run_settings(),
        geometry=page.geometry_settings(),
        source=page.source_settings(),
        physics=page.physics_settings(),
        scoring=page.scoring_settings(),
        source_model=page.source_editor,
        physics_model=page.physics_editor,
        scoring_model=page.scoring_editor,
    )
    document = parse_ini_light(path)
    assert not document.errors, document.errors
    sections = document.section_map()
    assert "source" in sections, f"generated main.ini has no [source] section: {document.raw_text}"
    return sections["source"].values


def _expect_plane_rectangle_isotropic(
    page: ConfigBuilderPage, ini_path: Path, label: str, center: str = CENTER
) -> None:
    source = page.source_editor
    detail = (
        f"{label}: model is position_mode={source.position_mode!r} "
        f"position_type={source.position_type!r} source_shape={source.source_shape!r} "
        f"angular_mode={source.angular_mode!r} position={source.position!r} "
        f"halfx={source.halfx!r} halfy={source.halfy!r} errors={source.errors}"
    )
    assert source.position_mode == "plane", detail
    assert source.position_type == "plane", detail
    assert source.source_shape == "rectangle", detail
    assert source.angular_mode == "isotropic", detail
    assert source.position == center, detail
    assert source.halfx == HALFX and source.halfy == HALFY, detail
    assert not source.errors, detail

    # The Run Config editor widgets must show what the model holds, not a reset point source.
    widgets = (
        f"{label}: widgets position_type={page.source_editor_position_type.currentText()!r} "
        f"shape={page.source_editor_shape.currentText()!r} "
        f"angular_mode={page.source_editor_angular_mode.currentText()!r} "
        f"position={page.source_editor_position.text()!r}"
    )
    assert page.source_editor_position_type.currentText() == "plane", widgets
    assert page.source_editor_shape.currentText() == "rectangle", widgets
    assert page.source_editor_angular_mode.currentText() == "isotropic", widgets
    assert page.source_editor_position.text() == center, widgets

    # The live preview in "Messages and files" uses the same writer and must agree.
    preview = page.generated_main_ini_raw.toPlainText()
    assert "position_type = plane" in preview, f"{label}: {preview}"
    assert f"center = {center}" in preview, f"{label}: {preview}"
    assert "shape = rectangle" in preview, f"{label}: {preview}"
    assert f"halfx = {HALFX}" in preview, f"{label}: {preview}"
    assert f"halfy = {HALFY}" in preview, f"{label}: {preview}"
    assert "isotropic = true" in preview, f"{label}: {preview}"
    assert "position_type = point" not in preview, f"{label}: {preview}"

    # The writer output parsed from disk carries the plane geometry and no point-only keys.
    values = _write_source_ini(page, ini_path)
    assert values.get("position_type") == "plane", f"{label}: {values}"
    assert values.get("center") == center, f"{label}: {values}"
    assert values.get("shape") == "rectangle", f"{label}: {values}"
    assert values.get("halfx") == HALFX, f"{label}: {values}"
    assert values.get("halfy") == HALFY, f"{label}: {values}"
    assert values.get("isotropic") == "true", f"{label}: {values}"
    # Point-only and non-rectangle keys must not be mixed in.
    assert "position" not in values, f"{label}: point-only key written: {values}"
    assert "direction" not in values, f"{label}: isotropic must not write direction: {values}"
    assert "radius" not in values, f"{label}: rectangle must not write radius: {values}"
    print(f"{label}: OK ({values['position_type']}, center={values['center']}, isotropic)")


def _configure_plane_rectangle_isotropic(page: ConfigBuilderPage) -> None:
    source = page.source_editor
    source.preset = "proton_beam"
    source.particle = "proton"
    source.energy = "100 MeV"
    source.position_mode = "plane"
    source.position_type = "plane"
    source.source_shape = "rectangle"
    source.position = CENTER
    source.radius = ""
    source.inner_radius = ""
    source.halfx = HALFX
    source.halfy = HALFY
    source.normal = "0,0,1"
    source.angular_mode = "isotropic"
    source.direction = "0,0,1"
    page._populate_sps_editors()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("SourceFieldPreservation")
    QSettings().clear()

    page = ConfigBuilderPage()
    _configure_plane_rectangle_isotropic(page)

    with tempfile.TemporaryDirectory() as directory:
        ini_path = Path(directory) / "main.ini"
        _expect_plane_rectangle_isotropic(page, ini_path, "baseline")

        # 1) setup column: source energy (the reported trigger)
        _edit(page.source_energy, "150 MeV")
        assert page.source_editor.energy == "150 MeV", page.source_editor.energy
        _expect_plane_rectangle_isotropic(page, ini_path, "setup energy")

        # 2) setup column: source particle
        _edit(page.source_particle, "neutron")
        assert page.source_editor.particle == "neutron", page.source_editor.particle
        _expect_plane_rectangle_isotropic(page, ini_path, "setup particle")

        # 3) setup column: source preset
        page.source_preset.setCurrentText("neutron_beam")
        assert page.source_editor.preset == "neutron_beam", page.source_editor.preset
        _expect_plane_rectangle_isotropic(page, ini_path, "setup preset")

        # 4) setup column: scoring checkbox (hits is enabled by default, so toggle it)
        page.scoring_hits.setChecked(False)
        assert page.scoring_editor.hits is False
        _expect_plane_rectangle_isotropic(page, ini_path, "setup scoring checkbox (off)")
        page.scoring_hits.setChecked(True)
        _expect_plane_rectangle_isotropic(page, ini_path, "setup scoring checkbox (on)")

        # 5) setup column: histogram bins
        page.hist_bins.setValue(321)
        assert page.scoring_editor.hist_bins == 321, page.scoring_editor.hist_bins
        _expect_plane_rectangle_isotropic(page, ini_path, "setup hist bins")

        # 6) setup column: histogram minimum (another textEdited trigger)
        _edit(page.hist_min, "0.1 MeV")
        assert page.scoring_editor.hist_min == "0.1 MeV", page.scoring_editor.hist_min
        _expect_plane_rectangle_isotropic(page, ini_path, "setup hist min")

        # 7) setup column: biasing hook. The GUI cannot generate biasing rules, so the
        #    physics model is temporarily invalid (writer must refuse) - the source
        #    geometry must survive that too, and the geometry must still render after
        #    the hook is disabled again.
        page.enable_biasing.setChecked(True)
        source = page.source_editor
        assert source.position_mode == "plane" and source.source_shape == "rectangle", (
            "biasing trigger reset source geometry: "
            f"{source.position_mode}/{source.source_shape}/{source.angular_mode}"
        )
        assert source.angular_mode == "isotropic", source.angular_mode
        page.enable_biasing.setChecked(False)
        assert page.generated_main_ini_raw.toPlainText(), "preview is empty after the biasing trigger"
        _expect_plane_rectangle_isotropic(page, ini_path, "setup biasing hook")

        # 8) Run Config editor trigger: editing the editor field must not reset anything.
        _edit(page.source_editor_energy, "160 MeV")
        assert page.source_editor.energy == "160 MeV", page.source_editor.energy
        _expect_plane_rectangle_isotropic(page, ini_path, "Run Config editor energy")

        # 9) setup column: position. For a plane source this is the plane center, so the
        #    value must change while the plane/rectangle/isotropic geometry stays.
        moved_center = "7 mm, 8 mm, 9 mm"
        _edit(page.source_position, moved_center)
        assert page.source_editor.position == moved_center, page.source_editor.position
        _expect_plane_rectangle_isotropic(page, ini_path, "setup position (plane center)", moved_center)

        # Sanity check: the writer still writes point geometry when the model says point,
        # so the assertions above cannot pass because the writer ignores the model.
        page.source_editor_position_type.setCurrentText("point")
        assert page.source_editor.position_mode == "point", page.source_editor.position_mode
        values = _write_source_ini(page, ini_path)
        assert values.get("position_type") == "point", values
        assert values.get("position") == moved_center, values
        assert "center" not in values, values
        assert "halfx" not in values and "halfy" not in values, values
        print("writer still follows point geometry when the model is a point source: OK")

        assert not page.source_editor.errors, page.source_editor.errors
        assert not page.physics_editor.errors, page.physics_editor.errors
        assert not page.scoring_editor.errors, page.scoring_editor.errors

    page.deleteLater()
    app.processEvents()
    QSettings().clear()
    print("PASS: setup-column edits preserve plane/rectangle/isotropic source fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
