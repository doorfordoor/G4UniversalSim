"""Theme switching must not mutate editor, results or navigation state."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "gui"), str(ROOT / "gui" / "smoke_tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from g4usim_gui.core import theme  # noqa: E402
from gui_test_window import MainWindow  # noqa: E402

_settings_dir = Path(tempfile.mkdtemp(prefix="g4usim-theme-state-settings-"))
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(_settings_dir))
QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, str(_settings_dir))


def main() -> int:
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    settings = QSettings()

    window = MainWindow()
    window.resize(1400, 900)
    window.show()
    app.processEvents()

    for _ in range(4):
        app.processEvents()

    output_page = window.output_page
    rows = output_page.file_tree.topLevelItemCount()
    assert rows > 0, rows

    window.page_stack.setCurrentIndex(2)
    window._on_page_changed(2)
    app.processEvents()

    setup = window.config_builder_page.setup_panel
    setup.run_name.setText("draft_kept_9")
    app.processEvents()

    tree = output_page.file_tree
    tree.setCurrentItem(tree.topLevelItem(2))
    app.processEvents()
    selected = tree.currentItem().text(0) if tree.currentItem() is not None else None
    assert selected, "the output file selection was not recorded"

    workspace_tab = window.config_builder_page.workspace_tabs.currentIndex()
    page_index = window.page_stack.currentIndex()

    for skin_id in ("paper", "midnight", "B"):
        window._set_skin(skin_id)
        app.processEvents()

    assert setup.run_name.text() == "draft_kept_9", setup.run_name.text()
    assert output_page.file_tree.topLevelItemCount() == rows
    current = output_page.file_tree.currentItem()
    assert current is not None and current.text(0) == selected, (current, selected)
    assert window.page_stack.currentIndex() == page_index
    assert window.config_builder_page.workspace_tabs.currentIndex() == workspace_tab

    settings.sync()
    assert settings.value("appearance/light_skin", "") == "B", settings.value("appearance/light_skin")
    assert settings.value("appearance/dark_skin", "") == "midnight", settings.value("appearance/dark_skin")
    assert theme.current_skin().id == "B"
    assert window.appearance_status.text().startswith("Appearance:"), window.appearance_status.text()

    window.close()
    for _ in range(4):
        app.processEvents()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
