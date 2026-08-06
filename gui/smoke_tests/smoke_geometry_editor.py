from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.core.project import G4USimProject, project_from_dict, project_to_dict
from g4usim_gui.editors.geometry_editor_model import (
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
    assert document.round_trip_blockers
    document.round_trip_blockers = []  # Exercise writer separately from source round-trip protection.
    validate_geometry_document(document, material_names={"G4_AIR", "G4_Si", "G4_Cu", "G4_WATER"}, scoring_hits_enabled=True)
    assert not document.errors, document.errors
    text = generate_geometry_ini_text(document)
    assert "count = 3" in text
    assert "[layer.Cap]" in text


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


def test_offscreen_widget_instantiation() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
    except ImportError:
        return
    app = QApplication.instance() or QApplication([])
    page = ConfigBuilderPage()
    page.geometry_config.setText(str(ROOT / "config" / "geometry" / "simple_box.ini"))
    page.reload_geometry()
    assert page.geometry_document.mode == "simple_box"
    assert page.generated_geometry_raw.toPlainText()
    page.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    test_simple_box_model()
    test_layered_device_model()
    test_validation_errors()
    test_project_snapshot_roundtrip()
    test_package_writer_generates_geometry()
    test_offscreen_widget_instantiation()
    print("smoke_geometry_editor: OK")
