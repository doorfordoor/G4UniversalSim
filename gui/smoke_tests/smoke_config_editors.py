"""The Configuration page split by editor (roadmap E5).

- every editor widget (setup column, Materials, Geometry, 3D Preview, Run Config,
  Messages and files) builds on its own with its controls and tabs;
- the page is composed of exactly those widgets as its tabs, adopts their controls as
  attributes without clashes, and mixes in each editor's logic;
- the main window's behaviour comes from the window/ modules;
- regression: the Geometry tab's "Add Volume" and the Materials tab's
  "Add volume_fraction" are separate buttons with one handler each (one shared
  attribute used to add a hierarchical volume and a volume-fraction material at once).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import SIGNAL, QSettings   # noqa: E402
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QTabWidget   # noqa: E402

from g4usim_gui.widgets.config.details import DetailsPanel   # noqa: E402
from g4usim_gui.widgets.config.geometry import GeometryEditor   # noqa: E402
from g4usim_gui.widgets.config.materials import MaterialsEditor   # noqa: E402
from g4usim_gui.widgets.config.preview3d import Preview3DPanel   # noqa: E402
from g4usim_gui.widgets.config.run_config import RunConfigEditor   # noqa: E402
from g4usim_gui.widgets.config.setup_panel import SetupPanel   # noqa: E402


def tab_texts(tabs: QTabWidget) -> list[str]:
    return [tabs.tabText(i) for i in range(tabs.count())]


def main() -> int:
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("ConfigEditors")
    QSettings().clear()

    materials = MaterialsEditor()
    assert materials.materials_table.columnCount() == 6 and materials.add_volume_fraction_button.text() == "Add volume_fraction"
    geometry = GeometryEditor()
    assert tab_texts(geometry.geometry_editor_tabs) == ["Simple Box", "Layered Device", "Hierarchical Volumes",
                                                        "Boolean Operations", "Preview / Unsupported Template"]
    assert geometry.add_volume_button.text() == "Add Volume" and geometry.geometry_table.columnCount() == 17
    preview = Preview3DPanel()
    assert preview.preview3d_auto_backend.isChecked() and preview.preview3d_widget is not None
    run = RunConfigEditor()
    assert tab_texts(run.run_config_tabs) == ["Source", "Physics", "Scoring"]
    setup = SetupPanel(lambda: None, lambda: None)
    assert [section.toggle.text() for section in setup.setup_sections] == ["Run", "Input files", "Source", "Physics",
                                                                           "Scoring"]
    details = DetailsPanel(QPlainTextEdit())
    assert tab_texts(details) == ["Messages", "Raw Files", "NIST Quick List"]
    print("each editor widget builds on its own")

    from gui_test_window import MainWindow   # noqa: PLC0415
    from g4usim_gui.window.content import ContentMixin   # noqa: PLC0415
    from g4usim_gui.window.project import ProjectMixin   # noqa: PLC0415
    from g4usim_gui.window.run import RunMixin   # noqa: PLC0415
    from g4usim_gui.window.shell import ShellMixin   # noqa: PLC0415
    window = MainWindow()
    assert all(issubclass(MainWindow, mixin) for mixin in (ShellMixin, ProjectMixin, RunMixin, ContentMixin))
    page = window.config_builder_page
    tabs = page.workspace_tabs
    assert tab_texts(tabs) == ["Materials", "Geometry", "Boolean Ops", "3D Preview", "Run Config", "Messages and files"]
    shown = [tabs.widget(i) for i in range(tabs.count())]
    shown = [w.widget() for w in shown]           # every tab is a scroll area (it scrolls instead of overlapping)
    assert shown == [page.materials_editor, page.geometry_editor, page.boolean_tab, page.preview3d_panel,
                     page.run_config_editor, page.details_tabs], shown
    assert page.materials_table is page.materials_editor.materials_table
    assert page.geometry_table is page.geometry_editor.geometry_table
    assert page.preview3d_widget is page.preview3d_panel.preview3d_widget
    assert page.boolean_table.parentWidget() is page.boolean_tab   # shown in the Boolean Ops tab, as always

    # nothing overlaps: every tab's content gets at least its minimum size, or scrolls (window 1280 x 800)
    window.resize(1280, 800)
    window.show()
    window.page_stack.setCurrentWidget(page)
    for index in range(tabs.count()):
        tabs.setCurrentIndex(index)
        app.processEvents()
        content = shown[index]
        assert content.height() >= content.minimumSizeHint().height() - 1, (tabs.tabText(index), content.height())
        assert content.width() >= content.minimumSizeHint().width() - 1, (tabs.tabText(index), content.width())
    print("layout: at 1280 x 800 every tab's content has its minimum size (scrolling where needed)")
    assert page.preview3d_messages.window() is window
    print("page: composed of the editor widgets, controls adopted")

    clicked = SIGNAL("clicked()")
    assert page.add_volume_button.receivers(clicked) == 1
    assert page.add_volume_fraction_button.receivers(clicked) == 1
    volumes = len(page.geometry_document.volumes)
    materials_before = len(page.material_document.rows)
    page.add_volume_button.click()
    assert len(page.geometry_document.volumes) == volumes + 1 and len(page.material_document.rows) == materials_before
    page.add_volume_fraction_button.click()
    assert len(page.material_document.rows) == materials_before + 1
    assert page.material_document.rows[-1].mode == "volume_fraction"
    assert len(page.geometry_document.volumes) == volumes + 1
    print("Add Volume adds a volume only; Add volume_fraction adds a material only")

    window.close()
    for widget in (materials, geometry, preview, run, setup, details, window):
        widget.deleteLater()
    app.processEvents()
    QSettings().clear()
    print("smoke_config_editors: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
