from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.core.project import G4USimProject, project_from_dict, project_to_dict
from g4usim_gui.editors.geometry_editor_model import (
    BooleanOperationRow,
    LayerRow,
    geometry_document_from_summary,
    validate_geometry_document,
)
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials
from g4usim_gui.validators.config_validator import validate_config_builder
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.writers.package_writer import create_run_package


ROOT = Path(__file__).resolve().parents[2]


def test_simple_box_model() -> None:
    summary = parse_geometry(str(ROOT / "config" / "geometry" / "simple_box.ini"))
    document = geometry_document_from_summary(summary, "simple_box")
    document.simple_box.target_size = "2 cm, 2 cm, 1 mm"
    document.is_dirty = True
    validate_geometry_document(document, material_names={"G4_AIR", "G4_Si"}, scoring_hits_enabled=True)
    assert document.round_trip_blockers
    assert any("Round-trip blocker" in item for item in document.errors)
    document.round_trip_blockers = []  # Exercise writer with a new editor-authored document state.
    validate_geometry_document(document, material_names={"G4_AIR", "G4_Si"}, scoring_hits_enabled=True)
    assert not document.errors, document.errors
    text = generate_geometry_ini_text(document)
    assert "[target]" in text
    assert "size = 2 cm, 2 cm, 1 mm" in text


def test_layered_device_model() -> None:
    summary = parse_geometry(str(ROOT / "config" / "geometry" / "layered_device.ini"))
    document = geometry_document_from_summary(summary, "layered_device")
    document.layered_device.layers.append(
        LayerRow(name="Cap", material="G4_Si", thickness="1 um", xy="10 mm, 10 mm", sensitive=True, region="CapRegion")
    )
    document.layered_device.layers[0].enabled = False
    document.is_dirty = True
    validate_geometry_document(document, material_names={"G4_AIR", "G4_Si", "G4_Cu", "G4_WATER"}, scoring_hits_enabled=True)
    assert not document.round_trip_blockers, document.round_trip_blockers
    validate_geometry_document(document, material_names={"G4_AIR", "G4_Si", "G4_Cu", "G4_WATER"}, scoring_hits_enabled=True)
    assert not document.errors, document.errors
    text = generate_geometry_ini_text(document)
    assert "count = 3" in text
    assert "[layer.Cap]" in text
    assert "cut.e- = 100 nm" in text


def test_layered_manual_position_roundtrip() -> None:
    source = (ROOT / "scripts" / "fixtures" / "layered_gui_roundtrip.ini").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "source.ini"
        path.write_text(source, encoding="utf-8")
        parsed = parse_geometry(path, "layered_device")
        assert not parsed.errors and not parsed.round_trip_blockers, parsed.errors + parsed.round_trip_blockers
        document = geometry_document_from_summary(parsed, "layered_device")
        assert document.layered_device.auto_stack is False
        project = G4USimProject(projectName="manual_layers")
        project.geometryEditor = document
        restored = project_from_dict(project_to_dict(project)).geometryEditor
        assert restored.layered_device.auto_stack is False
        assert restored.layered_device.layers[0].metadata == "metadata.Label = readout"
        text = generate_geometry_ini_text(restored)
        assert "auto_stack = false" in text
        assert "position = 0 mm, 0 mm, 1 cm" in text
        assert "metadata.Label = readout" in text
        generated = Path(tmp) / "generated.ini"
        generated.write_text(text, encoding="utf-8")
        reparsed = geometry_document_from_summary(parse_geometry(generated, "layered_device"), "layered_device")
        assert reparsed.layered_device == document.layered_device
        restored.layered_device.layers[0].position = ""
        validate_geometry_document(restored, material_names={"G4_AIR", "G4_Si"})
        assert any("requires position" in item for item in restored.errors)


def test_unrepresented_geometry_source_is_blocked() -> None:
    source = (ROOT / "scripts" / "fixtures" / "layered_gui_roundtrip.ini").read_text(encoding="utf-8")
    cases = {
        "orphan_layer": source + "\n[layer.Orphan]\nmaterial = G4_Si\n",
        "empty_unknown_section": source + "\n[unrecognized]\n",
        "duplicate_section": source + "\n[layer.Sensor]\nvis.color = red\n",
        "duplicate_key": source.replace("thickness = 1 mm", "thickness = 1 mm\nThickness = 2 mm"),
    }
    with tempfile.TemporaryDirectory() as tmp:
        for label, text in cases.items():
            path = Path(tmp) / f"{label}.ini"
            path.write_text(text, encoding="utf-8")
            parsed = parse_geometry(path, "layered_device")
            assert parsed.round_trip_blockers, label
            document = geometry_document_from_summary(parsed, "layered_device")
            try:
                generate_geometry_ini_text(document)
            except ValueError as error:
                assert "round-trip is blocked" in str(error), (label, error)
            else:
                raise AssertionError(f"{label}: unsafe editable generation succeeded")

        hierarchical = (ROOT / "scripts" / "fixtures" / "hierarchical_gui_roundtrip.ini").read_text(encoding="utf-8")
        path = Path(tmp) / "boolean.ini"
        path.write_text(hierarchical, encoding="utf-8")
        parsed = parse_geometry(path, "hierarchical_boolean")
        assert not parsed.round_trip_blockers, parsed.round_trip_blockers


def test_validation_errors() -> None:
    summary = parse_geometry(str(ROOT / "config" / "geometry" / "simple_box.ini"))
    document = geometry_document_from_summary(summary, "simple_box")
    document.simple_box.target_material = "MissingCustom"
    document.is_dirty = True
    validate_geometry_document(document, material_names={"G4_AIR"})
    assert document.errors


def test_project_snapshot_roundtrip() -> None:
    summary = parse_geometry(str(ROOT / "config" / "geometry" / "simple_box.ini"))
    document = geometry_document_from_summary(summary, "simple_box")
    document.simple_box.target_name = "EditedTarget"
    document.is_dirty = True
    project = G4USimProject(projectName="geometry_smoke")
    project.geometryEditor = document
    loaded = project_from_dict(project_to_dict(project))
    assert loaded.geometryEditor.simple_box.target_name == "EditedTarget"
    assert loaded.geometryEditor.is_dirty


def test_hierarchical_visual_and_cut_roundtrip() -> None:
    complex_summary = parse_geometry(ROOT / "test" / "geometry" / "hierarchical_test.ini", "hierarchical")
    assert not complex_summary.round_trip_blockers, complex_summary.round_trip_blockers
    complex_document = geometry_document_from_summary(complex_summary, "hierarchical")
    validate_geometry_document(complex_document, material_names={"G4_AIR", "G4_Al", "G4_Pb", "G4_WATER", "silicon", "iron", "water"})
    assert not complex_document.errors, complex_document.errors
    with tempfile.TemporaryDirectory() as tmp:
        generated_complex = Path(tmp) / "complex.ini"
        generated_complex.write_text(generate_geometry_ini_text(complex_document), encoding="utf-8")
        reparsed_complex = parse_geometry(generated_complex, "hierarchical")
        assert not reparsed_complex.round_trip_blockers, reparsed_complex.round_trip_blockers
        assert _geometry_semantics(complex_summary) == _geometry_semantics(reparsed_complex)
        stand = next(row for row in complex_document.volumes if row.name == "iron_stand")
        assert stand.shape_properties == {"dx1": "8 cm", "dx2": "10 cm", "dy1": "8 cm", "dy2": "10 cm", "dz": "2 cm"}
        stand.shape_properties["dx1"] = "9 cm"
        assert "dx1 = 9 cm" in generate_geometry_ini_text(complex_document)
        stand.shape_properties["dx1"] = "-1 cm"
        validate_geometry_document(complex_document, material_names={"G4_AIR", "G4_Al", "G4_Pb", "G4_WATER", "silicon", "iron", "water"})
        assert any("trd dx1 must be a positive length" in item for item in complex_document.errors)
        stand.shape_properties["dx1"] = "8 cm"
        stand.shape = "box"
        validate_geometry_document(complex_document, material_names={"G4_AIR", "G4_Al", "G4_Pb", "G4_WATER", "silicon", "iron", "water"})
        assert any("selected shape is not trd" in item for item in complex_document.errors)
        stand.shape = "trd"
        complex_document.boolean_ops.append(BooleanOperationRow(target_volume="main_chamber", operation="subtraction", tool_shape="trd"))
        validate_geometry_document(complex_document, material_names={"G4_AIR", "G4_Al", "G4_Pb", "G4_WATER", "silicon", "iron", "water"})
        assert any("Unsupported boolean tool shape 'trd'" in item for item in complex_document.errors)
    source = (ROOT / "scripts" / "fixtures" / "hierarchical_gui_roundtrip.ini").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        first = Path(tmp) / "source.ini"
        first.write_text(source, encoding="utf-8")
        summary = parse_geometry(first, "hierarchical")
        assert not summary.round_trip_blockers, summary.round_trip_blockers
        document = geometry_document_from_summary(summary, "hierarchical")
        validate_geometry_document(document, material_names={"G4_AIR", "G4_Si"})
        assert not document.errors, document.errors
        generated = generate_geometry_ini_text(document)
        second = Path(tmp) / "generated.ini"
        second.write_text(generated, encoding="utf-8")
        reparsed = parse_geometry(second, "hierarchical")
        assert not reparsed.round_trip_blockers, reparsed.round_trip_blockers
        assert [(row.name, row.visual, row.production_cuts) for row in summary.volumes] == [
            (row.name, row.visual, row.production_cuts) for row in reparsed.volumes
        ]

        project = G4USimProject(projectName="geometry_fields")
        project.geometryEditor = document
        restored = project_from_dict(project_to_dict(project)).geometryEditor
        assert restored.volumes[1].visual == {"vis.color": "lime", "vis.alpha": "0.7", "vis.visible": "true", "vis.wireframe": "false"}
        assert restored.volumes[1].production_cuts == {"cut.gamma": "0.5 mm", "cut.e-": "50 um"}
        restored.volumes[1].production_cuts["cut.gamma"] = "0.8 mm"
        edited = generate_geometry_ini_text(restored)
        assert "cut.gamma = 0.8 mm" in edited

        restored.volumes[1].region = ""
        validate_geometry_document(restored, material_names={"G4_AIR", "G4_Si"})
        assert any("cut.gamma requires a non-empty region" in item for item in restored.errors)

        unknown = Path(tmp) / "unknown.ini"
        unknown.write_text(source.replace("vis.color = lime", "vis.palette = lime"), encoding="utf-8")
        assert any("vis.palette" in item for item in parse_geometry(unknown, "hierarchical").round_trip_blockers)


def _geometry_semantics(summary) -> list[tuple]:
    return [
        (row.name, row.parent, row.shape, row.size, row.parameters, row.material,
         row.position, row.rotation, row.sensitive, row.bias, row.region, row.copy_no,
         row.metadata, row.shape_properties, row.visual, row.production_cuts)
        for row in summary.volumes
    ]


def test_package_writer_generates_geometry() -> None:
    summary = parse_geometry(str(ROOT / "config" / "geometry" / "simple_box.ini"))
    document = geometry_document_from_summary(summary, "simple_box")
    document.simple_box.target_name = "GeneratedTarget"
    document.is_dirty = True
    document.round_trip_blockers = []  # New editor-authored output, not a source round-trip.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        exe = tmp_path / "G4UniversalSim.exe"
        exe.write_text("", encoding="utf-8")
        package, report = create_run_package(
            project=G4USimProject(projectName="geometry_smoke"),
            paths=PathSettings(
                executable=str(exe),
                workspace_root=str(ROOT),
                runs_root=str(tmp_path / "runs"),
                materials_config=str(ROOT / "config" / "materials" / "material.ini"),
                geometry_config=str(ROOT / "config" / "geometry" / "simple_box.ini"),
            ),
            run=RunSettings(run_name="geometry_smoke", beam_on=1),
            geometry=GeometrySettings(template="simple_box", config_path=str(ROOT / "config" / "geometry" / "simple_box.ini")),
            source=SourceSettings(),
            physics=PhysicsSettings(),
            scoring=ScoringSettings(),
            geometry_document=document,
        )
        generated = Path(package.geometry_ini_path).read_text(encoding="utf-8")
        assert "name = GeneratedTarget" in generated
        assert "geometry_source_mode = generated by Geometry Editor" in report


def test_source_diagnostics_are_counted_once() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        exe = tmp_path / "G4UniversalSim.exe"
        exe.write_text("", encoding="utf-8")
        source = tmp_path / "geometry.ini"
        source.write_text(
            "[world]\nshape = box\nsize = 10 cm, 10 cm, 10 cm\nmaterial = G4_AIR\ninvalid_line\n",
            encoding="utf-8",
        )
        summary = parse_geometry(source, "hierarchical")
        assert len(summary.errors) == 1, summary.errors
        document = geometry_document_from_summary(summary, "hierarchical")
        document.is_dirty = True
        paths = PathSettings(
            executable=str(exe), workspace_root=str(ROOT), runs_root=str(tmp_path / "runs"),
            materials_config=str(ROOT / "config" / "materials" / "material.ini"), geometry_config=str(source),
        )
        kwargs = dict(
            paths=paths, run=RunSettings(run_name="diagnostic", beam_on=1),
            geometry=GeometrySettings(template="hierarchical", config_path=str(source)),
            source=SourceSettings(), physics=PhysicsSettings(), scoring=ScoringSettings(),
            geometry_document=document,
        )
        report = validate_config_builder(**kwargs)
        assert sum("invalid INI line" in error for error in report.errors) == 1, report.errors
        assert sum("invalid INI line" in error for error in validate_config_builder(**kwargs).errors) == 1

        source.write_text(source.read_text(encoding="utf-8") + "# changed on disk\n", encoding="utf-8")
        stale_report = validate_config_builder(**kwargs)
        assert any("Geometry source changed since" in error for error in stale_report.errors), stale_report.errors

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage

        app = QApplication.instance() or QApplication([])
        page = ConfigBuilderPage()
        page.geometry_summary = summary
        page.geometry_document = geometry_document_from_summary(summary, "hierarchical")
        page._update_workspace_summary()
        assert "Messages: 1 errors" in page.workspace_summary.text(), page.workspace_summary.text()
        empty_materials = tmp_path / "empty-materials.ini"
        empty_materials.write_text("# empty\n", encoding="utf-8")
        page.materials_summary = parse_materials(empty_materials)
        assert len(page.materials_summary.warnings) == 1
        page._update_workspace_summary()
        assert "1 warnings" in page.workspace_summary.text(), page.workspace_summary.text()
        page.deleteLater()
        app.processEvents()


def test_offscreen_widget_instantiation() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from g4usim_gui.core.i18n import set_application_language
        from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
    except ImportError:
        return
    app = QApplication.instance() or QApplication([])
    page = ConfigBuilderPage()
    assert page.geometry_template.currentData() == "hierarchical"
    assert page.geometry_template.count() == 3
    page._set_geometry_template_token("simple_box")
    assert page.geometry_template.currentData() == "simple_box"
    assert page.geometry_template.currentText() == "Single Target Preset (Legacy)"
    page.geometry_config.setText(str(ROOT / "config" / "geometry" / "simple_box.ini"))
    page.reload_geometry()
    assert page.geometry_document.mode == "simple_box"
    assert page.generated_geometry_raw.toPlainText()
    page._set_geometry_template_token("hierarchical")
    page.materials_config.setText(str(ROOT / "test" / "materials" / "test_materials.ini"))
    page.reload_materials()
    page.geometry_config.setText(str(ROOT / "test" / "geometry" / "hierarchical_test.ini"))
    page.reload_geometry()
    stand_row = next(index for index, row in enumerate(page.geometry_document.volumes) if row.name == "iron_stand")
    assert page.geometry_table.columnCount() == 17
    assert page.geometry_table.item(stand_row, 11).text() == "8 cm"
    page.geometry_table.item(stand_row, 11).setText("9 cm")
    assert page.geometry_document.volumes[stand_row].shape_properties["dx1"] == "9 cm"
    assert "dx1 = 9 cm" in page.generated_geometry_raw.toPlainText()
    page.deleteLater()
    app.processEvents()

    translated = geometry_document_from_summary(
        parse_geometry(ROOT / "scripts" / "fixtures" / "hierarchical_gui_roundtrip.ini", "hierarchical"),
        "hierarchical",
    )
    translated.volumes[1].production_cuts["cut.gamma"] = "-1 mm"
    set_application_language(app, "zh_CN")
    validate_geometry_document(translated, material_names={"G4_AIR", "G4_Si"})
    assert any("必须是正长度" in error for error in translated.errors), translated.errors
    set_application_language(app, "en")


if __name__ == "__main__":
    test_simple_box_model()
    test_layered_device_model()
    test_layered_manual_position_roundtrip()
    test_unrepresented_geometry_source_is_blocked()
    test_validation_errors()
    test_project_snapshot_roundtrip()
    test_hierarchical_visual_and_cut_roundtrip()
    test_package_writer_generates_geometry()
    test_source_diagnostics_are_counted_once()
    test_offscreen_widget_instantiation()
    print("smoke_geometry_editor: OK")
