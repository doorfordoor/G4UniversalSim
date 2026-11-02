"""Model tree of the geometry editor: hierarchy rows, selection sync with the 3D view."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gui"), str(ROOT / "gui/smoke_tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from g4usim_gui.core.theme import apply_theme  # noqa: E402
from g4usim_gui.editors.geometry_editor_model import (  # noqa: E402
    GeometryDocument,
    HierarchicalVolumeRow,
    LayerRow,
    SimpleBoxGeometryModel,
)
from g4usim_gui.history import run_history_store  # noqa: E402
from g4usim_gui.main_window import MainWindow  # noqa: E402
from g4usim_gui.preview3d.model_tree import build_model_tree, flatten  # noqa: E402


def test_hierarchical_tree() -> None:
    document = GeometryDocument()
    document.mode = "hierarchical"
    document.volumes = [
        HierarchicalVolumeRow(name="Shield", parent="world", material="G4_Pb"),
        HierarchicalVolumeRow(name="Inner", parent="Shield", material="G4_Si", sensitive=True),
        HierarchicalVolumeRow(name="Orphan", parent="missing_mother", material="G4_Al"),
        HierarchicalVolumeRow(name="Disabled", parent="world", enabled=False),
    ]
    root = build_model_tree(document)
    assert root.label == "World", root.label
    keys = [child.key for child in root.children]
    assert keys == ["Shield", "Orphan"], keys
    shield = root.children[0]
    assert shield.material == "G4_Pb"
    assert [child.key for child in shield.children] == ["Inner"], shield.children
    assert shield.children[0].sensitive is True
    assert flatten(root)[0] is root
    assert len(flatten(root)) == 4, len(flatten(root))
    assert "Disabled" not in [node.key for node in flatten(root)]

    # a mother cycle must not recurse forever and must not break the tree
    cycle = GeometryDocument()
    cycle.mode = "hierarchical"
    cycle.volumes = [
        HierarchicalVolumeRow(name="A", parent="B"),
        HierarchicalVolumeRow(name="B", parent="A"),
    ]
    cycle_root = build_model_tree(cycle)
    assert cycle_root.label == "World"
    assert len(flatten(cycle_root)) == 4, len(flatten(cycle_root))


def test_simple_box_tree() -> None:
    document = GeometryDocument()
    document.mode = "simple_box"
    document.simple_box = SimpleBoxGeometryModel(
        world_material="G4_AIR", target_name="Target", target_material="G4_Si",
        target_sensitive=True)
    root = build_model_tree(document)
    assert root.label == "World"
    assert root.material == "G4_AIR"
    assert [child.key for child in root.children] == ["Target"], root.children
    target = root.children[0]
    assert target.material == "G4_Si"
    assert target.sensitive is True


def test_layered_tree() -> None:
    document = GeometryDocument()
    document.mode = "layered_device"
    document.layered_device.layers = [
        LayerRow(name="Substrate", material="G4_Si", thickness="500 um"),
        LayerRow(name="Sensitive", material="G4_Si", sensitive=True),
        LayerRow(name="Skipped", material="G4_Al", enabled=False),
    ]
    root = build_model_tree(document)
    keys = [child.key for child in root.children]
    assert keys == ["Substrate", "Sensitive"], keys
    assert root.children[1].sensitive is True

    empty = GeometryDocument()
    empty.mode = "preview_only"
    empty.volumes = []
    assert build_model_tree(empty).label == "World"
    assert build_model_tree(empty).children == ()


def test_widget_sync(window: MainWindow, app: QApplication) -> None:
    page = window.config_builder_page
    page.refresh_3d_preview()
    for _ in range(3):
        app.processEvents()
    widget = page.preview3d_widget
    if not hasattr(widget, "model_tree"):
        print("SKIP widget part: the 3D preview falls back in this environment")
        return
    tree = widget.model_tree
    assert tree.topLevelItemCount() == 1, tree.topLevelItemCount()
    world = tree.topLevelItem(0)
    assert world.text(0) == "World", world.text(0)
    assert world.childCount() > 0, "the demo geometry has volumes"

    first = world.child(0)
    key = first.data(0, Qt.UserRole)
    assert key, key
    tree.setCurrentItem(first)
    for _ in range(2):
        app.processEvents()
    assert widget.state.selected == key, (widget.state.selected, key)

    # selecting through the viewport API moves the tree emphasis back
    widget.select_volume("")
    app.processEvents()
    second = world.child(0)
    widget.select_volume(str(second.data(0, Qt.UserRole)))
    for _ in range(2):
        app.processEvents()
    assert tree.currentItem() is not None
    assert tree.currentItem().data(0, Qt.UserRole) == second.data(0, Qt.UserRole)

    # an empty document hides the tree instead of showing a lonely World row
    widget.set_model_tree(None)
    assert tree.isHidden()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="g4-model-tree-") as directory:
        work = Path(directory)
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(work / "settings"))
        app = QApplication.instance() or QApplication([])
        app.setOrganizationName("G4USimModelTreeTest")
        app.setApplicationName("Model tree")
        app.setStyle("Fusion")
        if sys.platform == "win32" and app.platformName() == "offscreen":
            font_root = Path(os.environ["SystemRoot"]) / "Fonts"
            for name in ("segoeui.ttf", "msyh.ttc"):
                if (font_root / name).is_file():
                    assert QFontDatabase.addApplicationFont(str(font_root / name)) >= 0
        run_history_store.STATE_PATH = work / "history.json"
        os.environ["G4USIM_RECOVERY_DIR"] = str(work / "recovery")
        apply_theme(app, "light", "B")

        test_hierarchical_tree()
        test_simple_box_tree()
        test_layered_tree()
        window = MainWindow(recovery_root=work / "recovery", offer_recovery=False)
        try:
            window.show()
            for _ in range(3):
                app.processEvents()
            test_widget_sync(window, app)
        finally:
            widget = getattr(window.config_builder_page, "preview3d_widget", None)
            plotter = getattr(widget, "_plotter", None)
            if plotter is not None:
                try:
                    plotter.close()
                except Exception:  # noqa: BLE001 - teardown must not mask the test result
                    pass
            window.close()
            window.deleteLater()
            app.processEvents()
    print("smoke_model_tree: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
