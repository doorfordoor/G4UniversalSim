"""Command palette and shell chrome: filtering, keyboard, navigation and appearance wiring."""
from __future__ import annotations

from pathlib import Path
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'gui/smoke_tests')]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from g4usim_gui.core.theme import apply_theme, skin as skin_for  # noqa: E402
from g4usim_gui.history import run_history_store  # noqa: E402
from g4usim_gui.main_window import MainWindow  # noqa: E402
from g4usim_gui.widgets.command_palette import CommandPalette  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='g4-palette-') as directory:
        work = Path(directory)
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(work / 'settings'))
        app = QApplication.instance() or QApplication([])
        app.setOrganizationName('G4USimPaletteTest')
        app.setApplicationName('Command palette')
        app.setStyle('Fusion')
        if sys.platform == 'win32' and app.platformName() == 'offscreen':
            font_root = Path(os.environ['SystemRoot']) / 'Fonts'
            for name in ('segoeui.ttf', 'msyh.ttc'):
                if (font_root / name).is_file():
                    assert QFontDatabase.addApplicationFont(str(font_root / name)) >= 0
        run_history_store.STATE_PATH = work / 'history.json'
        os.environ['G4USIM_RECOVERY_DIR'] = str(work / 'recovery')
        apply_theme(app, 'light', 'B')
        window = MainWindow(recovery_root=work / 'recovery', offer_recovery=False)
        try:
            window.show()
            for _ in range(3):
                app.processEvents()

            # --- shell chrome -------------------------------------------------
            assert [label.text() for label in window._nav_section_labels] == [
                'WORKFLOW', 'RUN & ANALYZE',
            ], [label.text() for label in window._nav_section_labels]
            assert window._nav_group.button(0).text() == 'Start'
            assert window.page_stack.count() == 9
            window.focus_page(0)
            app.processEvents()
            assert window.page_crumb.text() == 'Workflow'
            window.focus_page(6)
            app.processEvents()
            assert window.page_crumb.text() == 'Run & analyze'
            assert 'Paper & Ink' in window.appearance_status.text() or window.appearance_status.text()
            window.focus_page(0)
            app.processEvents()

            # --- entries ------------------------------------------------------
            entries = window._command_palette_entries()
            categories = [entry.category for entry in entries]
            assert categories.count('Page') == 9, categories.count('Page')
            assert categories.count('Action') == 7, categories.count('Action')
            assert categories.count('Appearance') == 15, categories.count('Appearance')
            labels = [entry.label for entry in entries]
            assert 'Results' in labels
            assert 'Paper & Ink' in labels
            assert all(callable(entry.callback) for entry in entries)

            # --- filtering and keyboard --------------------------------------
            def selectable_labels(dialog):
                labels = []
                for row in range(dialog.list.count()):
                    item = dialog.list.item(row)
                    if item.data(Qt.UserRole) is not None:
                        labels.append(item.text().strip())
                return labels

            dialog = CommandPalette(window)
            dialog.set_entries(entries)
            # three group headers (Pages, Actions, Appearances) precede their rows
            assert dialog.list.count() == len(entries) + 3, dialog.list.count()
            assert selectable_labels(dialog) == [entry.label for entry in entries]
            dialog.search.setText('results')
            assert selectable_labels(dialog) == ['Results'], selectable_labels(dialog)
            assert dialog.current_entry().label == 'Results'
            dialog.run_current()
            assert dialog.result() == QDialog.Accepted
            assert dialog.chosen is not None
            dialog.chosen()
            app.processEvents()
            assert window.page_stack.currentIndex() == 6, window.page_stack.currentIndex()

            dialog = CommandPalette(window)
            dialog.set_entries(entries)
            dialog.search.setText('pa')
            shown = selectable_labels(dialog)
            assert 'Paper & Ink' in shown, shown
            assert 'Parameter Scans' in shown, shown
            assert all('pa' in label.lower() for label in shown), shown
            dialog.search.setText('no-such-command-anywhere')
            assert dialog.list.count() == 0
            assert dialog.current_entry() is None
            dialog.run_current()
            assert dialog.result() != QDialog.Accepted
            dialog.close()

            dialog = CommandPalette(window)
            dialog.set_entries(window._command_palette_entries())
            dialog.show()
            app.processEvents()
            dialog.search.setText('paper')
            assert dialog.current_entry() is not None
            assert dialog.current_entry().label == 'Paper & Ink'
            QTest.keyClick(dialog.search, Qt.Key_Return)
            app.processEvents()
            assert dialog.chosen is not None
            dialog.chosen()
            app.processEvents()
            assert app.property('resolvedSkin') == 'paper', app.property('resolvedSkin')
            assert app.property('resolvedTheme') == 'light'
            assert 'Paper & Ink' in window.appearance_status.text(), window.appearance_status.text()

            dialog = CommandPalette(window)
            dialog.set_entries(window._command_palette_entries())
            dialog.show()
            app.processEvents()
            QTest.keyClick(dialog.search, Qt.Key_Escape)
            app.processEvents()
            assert dialog.result() == QDialog.Rejected
            assert dialog.chosen is None

            # a dark appearance row switches to the dark group that shows it
            window._set_skin('midnight')
            app.processEvents()
            assert app.property('resolvedSkin') == 'midnight', app.property('resolvedSkin')
            assert app.property('resolvedTheme') == 'dark', app.property('resolvedTheme')
            assert 'Midnight Blue' in window.appearance_status.text()
            window._set_skin('paper')
            app.processEvents()
            assert app.property('resolvedTheme') == 'light'

            # the launcher must not mutate the project or the current page
            window.close()
        finally:
            assert window.page_stack.count() == 9
    print('smoke_command_palette: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
