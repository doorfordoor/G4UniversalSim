from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.editors.geometry_editor_model import GeometryDocument, LayerRow
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from g4usim_gui.preview3d.scene_builder import build_preview_scene
from g4usim_gui.preview3d.units import parse_direction, parse_length_to_mm, parse_vec3_deg, parse_vec3_to_mm


def test_units() -> None:
    assert parse_length_to_mm("10 mm") == 10.0
    assert parse_length_to_mm("1 cm") == 10.0
    assert parse_length_to_mm("100 um") == 0.1
    assert parse_length_to_mm("0.001 m") == 1.0
    assert parse_vec3_to_mm("0,0,-5 mm") == (0.0, 0.0, -5.0)
    assert parse_vec3_to_mm("0 mm, 0 mm, -5 mm") == (0.0, 0.0, -5.0)
    assert parse_direction("0,0,1") == (0.0, 0.0, 1.0)
    assert parse_direction("0,0,0") is None
    assert parse_vec3_deg("0 deg, 0 deg, 45 deg") == (0.0, 0.0, 45.0)


def test_simple_scene() -> None:
    geometry = GeometryDocument(mode="simple_box", is_dirty=True)
    geometry.simple_box.target_size = "10 mm, 10 mm, 1 mm"
    geometry.simple_box.target_position = "0,0,0 mm"
    source = SourceEditableModel(position="0,0,-5 mm", direction="0,0,1")
    scene = build_preview_scene(geometry, source)
    assert len(scene.volumes) == 2
    assert scene.volumes[0].role == "world"
    assert scene.volumes[1].role == "target"
    assert scene.source.direction == (0.0, 0.0, 1.0)
    assert scene.bounds_mm is not None


def test_layered_scene() -> None:
    geometry = GeometryDocument(mode="layered_device", is_dirty=True)
    geometry.layered_device.layers = [
        LayerRow(name="A", material="G4_Al", thickness="1 mm", xy="10 mm, 10 mm"),
        LayerRow(name="B", material="G4_Si", thickness="0.5 mm", xy="10 mm, 10 mm", sensitive=True),
        LayerRow(name="Disabled", enabled=False),
    ]
    scene = build_preview_scene(geometry, SourceEditableModel(position="0,0,-5 mm", direction="0,0,1"))
    assert len(scene.volumes) == 3
    assert [volume.role for volume in scene.volumes] == ["world", "layer", "layer"]
    assert scene.volumes[2].sensitive


def test_unsupported_scene() -> None:
    geometry = GeometryDocument(mode="preview_only")
    source = SourceEditableModel(direction="0,0,0")
    scene = build_preview_scene(geometry, source)
    assert scene.warnings
    assert scene.source.direction is None


def test_config_builder_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication, QTabWidget
        from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
    except ImportError:
        return
    app = QApplication.instance() or QApplication([])
    page = ConfigBuilderPage()
    tabs = []
    for widget in page.findChildren(QTabWidget):
        tabs.extend(widget.tabText(index) for index in range(widget.count()))
    assert "3D Preview" in tabs
    page.refresh_3d_preview()
    assert "3D Preview:" in page.preview3d_status.text()
    assert page.preview3d_messages.toPlainText()
    page.deleteLater()
    app.processEvents()


def test_optional_pyvista_widget() -> None:
    try:
        from PySide6.QtWidgets import QApplication
        from g4usim_gui.preview3d.pyvista_preview_widget import PyVistaPreviewWidget, pyvista_available
    except ImportError:
        return
    available, _ = pyvista_available()
    if not available:
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    widget = PyVistaPreviewWidget()
    widget.render_scene(build_preview_scene(GeometryDocument(mode="simple_box"), SourceEditableModel()))
    widget.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    test_units()
    test_simple_scene()
    test_layered_scene()
    test_unsupported_scene()
    test_config_builder_offscreen()
    test_optional_pyvista_widget()
    print("smoke_preview3d: OK")
