from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from g4usim_gui.core.theme import apply_theme
from g4usim_gui.main_window import MainWindow


def main() -> None:
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("MainWindowUI")
    QSettings().clear()

    apply_theme(app, "light")
    window = MainWindow()
    window.resize(1200, 760)
    window.show()
    app.processEvents()

    expected_titles = ["Project", "Configuration", "Run Console", "Results", "Run History", "Parameter Scans"]
    assert window.page_stack.count() == len(expected_titles)
    for index, title in enumerate(expected_titles):
        window.page_stack.setCurrentIndex(index)
        app.processEvents()
        assert window.page_title.text() == title
        assert window._nav_buttons[index].isChecked()

    window._set_theme("dark")
    assert app.property("themeMode") == "dark"
    assert app.property("resolvedTheme") == "dark"
    assert QSettings().value("appearance/theme") == "dark"
    combo = window.config_builder_page.material_mode
    combo.showPopup()
    app.processEvents()
    popup_palette = combo.view().palette()
    assert popup_palette.color(QPalette.Base).lightness() < popup_palette.color(QPalette.Text).lightness()
    combo.hidePopup()

    window._set_theme("system")
    assert app.property("themeMode") == "system"
    assert app.property("resolvedTheme") in {"light", "dark"}

    assert window.config_builder_page.generate_run_button.property("buttonRole") == "primary"
    assert window.run_page.run_button.property("buttonRole") == "primary"
    assert window.run_page.kill_button.property("buttonRole") == "danger"

    window.page_stack.setCurrentIndex(1)
    window._set_language("zh_CN")
    app.processEvents()
    assert window.page_title.text() == "配置"
    assert window._nav_buttons[0].text() == "项目"
    assert window._nav_buttons[5].text() == "参数扫描"
    assert window.config_builder_page.workspace_tabs.tabText(0) == "材料"
    assert window.config_builder_page.geometry_template.currentData() == "hierarchical"
    assert window.config_builder_page.geometry_template.currentText() == "通用层级模型"
    assert window.config_builder_page.geometry_config.text().endswith("test\\geometry\\hierarchical_test.ini")
    assert window.config_builder_page.material_mode.currentText() == "nist"
    assert QSettings().value("appearance/language") == "zh_CN"

    page = window.config_builder_page
    window.resize(1024, 1024)
    page.workspace_tabs.setCurrentIndex(4)
    page.run_config_tabs.setCurrentIndex(0)
    app.processEvents()
    source_rows = [
        page.source_editor_position_type,
        page.source_editor_position,
        page.source_editor_shape,
        page.source_editor_radius,
        page.source_editor_inner_radius,
        page.source_editor_halfx,
        page.source_editor_halfy,
        page.source_editor_normal,
        page.source_editor_confine_volume,
        page.source_editor_angular_mode,
        page.source_editor_direction,
        page.source_editor_theta_min,
        page.source_editor_theta_max,
        page.source_editor_phi_min,
        page.source_editor_phi_max,
        page.source_editor_cone_half_angle,
        page.source_editor_focus_point,
        page.source_editor_preview_rays,
        page.source_editor_preview_seed,
    ]
    row_rects = [widget.geometry() for widget in source_rows]
    assert all(30 <= rect.height() <= 40 for rect in row_rects)
    assert page.source_editor_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.source_editor_scroll.verticalScrollBar().maximum() > 0

    window._set_language("en")
    app.processEvents()
    assert window.page_title.text() == "Configuration"
    assert window._nav_buttons[0].text() == "Project"
    assert window.config_builder_page.workspace_tabs.tabText(0) == "Materials"
    assert window.config_builder_page.geometry_template.currentData() == "hierarchical"
    assert window.config_builder_page.geometry_template.currentText() == "Hierarchical Model"
    assert QSettings().value("appearance/language") == "en"

    window.close()
    QSettings().clear()
    print("smoke_main_window_ui: ok")


if __name__ == "__main__":
    main()
