"""Help menu: the shortcut sheet and the About text are discoverable and complete (GUI only)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
sys.path.insert(0, str(ROOT / "gui" / "smoke_tests"))

from PySide6.QtCore import QSettings  # noqa: E402

_settings_dir = tempfile.mkdtemp(prefix="g4usim-help-menu-")
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _settings_dir)
QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, _settings_dir)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([sys.argv[0]])
app.setStyle("Fusion")

from g4usim_gui.core import theme  # noqa: E402
from gui_test_window import MainWindow  # noqa: E402

theme.apply_theme(app, "light")

window = MainWindow(recovery_root=Path(_settings_dir) / "recovery", offer_recovery=False)
window.show()
app.processEvents()

menus = {action.text(): action.menu() for action in window.menuBar().actions() if action.menu() is not None}
assert "Help" in menus, sorted(menus)
help_menu = menus["Help"]
help_texts = [action.text() for action in help_menu.actions() if not action.isSeparator()]
assert help_texts == ["Keyboard shortcuts", "About G4UniversalSim"], help_texts
assert window.shortcuts_action.shortcut().toString() == "F1", window.shortcuts_action.shortcut().toString()

rows = window.shortcut_rows()
keys = [row[0] for row in rows]
assert "F1" in keys and "Ctrl+K" in keys and "Ctrl+Shift+L" in keys, keys
assert "F6 / Shift+F6" in keys, keys
for index in range(9):
    assert f"Ctrl+Alt+{index + 1}" in keys, keys
assert len(rows) >= 20, len(rows)
assert len({key for key, _description in rows}) == len(rows), "shortcut keys must be unique"

about = window.about_text()
for fragment in ("G4UniversalSim", "PySide6", "Qt ", "Application root", "Backend executable"):
    assert fragment in about, (fragment, about)

assert window.shortcuts_action.isEnabled() and window.about_action.isEnabled()
for button in window._nav_buttons:
    assert button.toolTip().startswith("Open "), button.toolTip()

window._set_language("zh_CN")
app.processEvents()
assert window.shortcuts_action.text() == "键盘快捷键", window.shortcuts_action.text()
assert window.about_action.text() == "关于 G4UniversalSim", window.about_action.text()

window._set_language("en")
app.processEvents()
assert window.shortcuts_action.text() == "Keyboard shortcuts"

window.close()
print("smoke_help_menu: OK")
