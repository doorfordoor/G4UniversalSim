"""Actual MainWindow colour refresh boundaries; no simulation is started."""
from __future__ import annotations

from dataclasses import asdict
from copy import deepcopy
from pathlib import Path
import os
import sys
import tempfile
import json

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'gui/smoke_tests')]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPoint, QSettings, QThreadPool
from PySide6.QtGui import QColor, QFontDatabase, QFontMetrics, QPalette
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QWidget
from g4usim_gui.app import _close_self_test_window
from g4usim_gui.core.theme import (SKIN_IDS, apply_appearance, apply_theme,
                                  contrast_ratio, current_colors, skin,
                                  status_combinations)
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from smoke_plots import fixture
from async_wait import wait_for_idle


def main():
    with tempfile.TemporaryDirectory(prefix='g4-theme-shell-') as directory:
        work = Path(directory)
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(work / 'settings'))
        app = QApplication.instance() or QApplication([])
        app.setOrganizationName('G4USimThemeShellTest')
        app.setApplicationName('Theme refresh boundaries')
        app.setStyle('Fusion')
        # The Windows offscreen plugin may not enumerate native fonts. Read the
        # same existing files used by the I1 GUI test; do not install any font.
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
            app.processEvents()
            assert window._painted_theme_colors == current_colors()
            assert not window.theme_button.icon().isNull()
            fixture(work / 'results')
            window.output_page.set_output_dir(str(work / 'results'))
            wait_for_idle(window.output_page.plot_panel)
            window.page_stack.setCurrentWidget(window.output_page)
            app.processEvents()
            assert window.output_page.plot_panel.datasets()
            font_families = app.font().families()
            style_name = app.style().objectName()
            window.output_page.plot_panel.dataset_combo.setFocus()
            app.processEvents()
            focus = app.focusWidget()
            assert focus is window.output_page.plot_panel.dataset_combo
            before = (asdict(window.project), deepcopy(window._capture_drafts()),
                      window._edit_session.revision, window.page_stack.currentIndex(),
                      window.run_page.stdout_view.toPlainText(),
                      window.output_page.plot_panel.current_dataset().key)
            changed = QSignalSpy(window.config_builder_page.settingsChanged)
            pages = (window.start_page, window.config_builder_page, window.output_page,
                     window.scenario_page, window.effective_config_page, window.scan_page)
            calls = []
            for page in pages:
                method = getattr(page, 'refresh_theme', None)
                if method is not None:
                    def observed(method=method, page=page):
                        calls.append(page)
                        return method()
                    page.refresh_theme = observed
            window._set_theme('light', palette='B')
            assert calls == [], 'same colours must not redraw plots or repeat evidence reads'
            window._set_theme('dark')
            assert len(calls) == sum(hasattr(page, 'refresh_theme') for page in pages)
            assert all(calls.count(page) == 1 for page in pages if hasattr(page, 'refresh_theme'))
            assert app.property('resolvedPalette') == 'C'
            assert not window.theme_button.icon().isNull()
            calls.clear()
            window._set_theme('dark')
            window._set_palette('K')
            assert calls == [], 'remembered light preference does not repaint dark views'
            assert app.property('lightThemePalette') == 'K'
            assert window._palette_actions['K'].isChecked()
            assert QSettings().value('appearance/light_palette') == 'K'
            window._set_theme('light')
            assert app.property('resolvedPalette') == 'K'
            assert len(calls) == sum(hasattr(page, 'refresh_theme') for page in pages)
            calls.clear()
            window._set_theme('light')
            assert calls == []
            window._set_theme('light', palette='B')
            assert app.property('resolvedPalette') == 'B'
            assert len(calls) == sum(hasattr(page, 'refresh_theme') for page in pages)
            wait_for_idle(window.output_page.plot_panel)
            assert changed.count() == 0
            assert before == (asdict(window.project), window._capture_drafts(),
                              window._edit_session.revision, window.page_stack.currentIndex(),
                              window.run_page.stdout_view.toPlainText(),
                              window.output_page.plot_panel.current_dataset().key)
            assert window._painted_theme_colors == current_colors()
            before_invalid = window._painted_theme_colors
            try:
                window._set_theme('light', palette='invalid')
            except ValueError:
                pass
            else:
                assert False, 'invalid palette must still be rejected'
            assert window._painted_theme_colors == before_invalid
            assert QSettings().value('appearance/theme') == 'light'
            assert app.focusWidget() is focus

            # Raster checks exercise the real application stylesheet, not only
            # the palette object (Qt can cache palette(role) render rules).
            canvas = QWidget(window)
            canvas.setObjectName('contentHost')
            canvas.setGeometry(5, 5, 36, 36)
            canvas.show()
            popup = QDialog(window)
            popup.resize(120, 90)
            popup.show()
            raster = []
            evidence = Path(os.environ.get('G4USIM_TEST_EVIDENCE_DIR', str(work / 'evidence')))
            evidence.mkdir(parents=True, exist_ok=True)
            for mode, palette in (('dark', None), ('light', 'K'), ('light', 'B')):
                window._set_theme(mode, palette=palette)
                app.processEvents()
                colors = current_colors()
                actual = canvas.grab().toImage().pixelColor(18, 18)
                dialog_color = popup.grab().toImage().pixelColor(60, 60)
                assert actual == QColor(colors.canvas), (mode, palette, actual.name(), colors.canvas)
                assert dialog_color == QColor(colors.canvas), (mode, dialog_color.name(), colors.canvas)
                assert app.font().families() == font_families
                assert QFontMetrics(app.font()).inFont('中')
                assert app.style().objectName() == style_name
                assert not window.theme_button.icon().isNull()
                assert window.theme_button.icon().pixmap(20, 20).toImage().hasAlphaChannel()
                window.grab().save(str(evidence / ('main-' + str(app.property('resolvedPalette')) + '.png')))
                raster.append({'palette': app.property('resolvedPalette'), 'canvas': actual.name(),
                               'dialog': dialog_color.name(), 'font_families': font_families})
            popup.close()
            canvas.hide()
            # Status chips are the only place a semantic colour becomes small text on
            # a tinted background. The independent J3 review measured the final widget
            # pixels and found B/K/botanical success text below 4.5:1, so this pass
            # checks every skin's polished text colour against the rendered background.
            chip_rows = []
            for skin_id in SKIN_IDS:
                item = skin(skin_id)
                apply_appearance(app, item.mode,
                                 skin_id if item.mode == 'light' else 'B',
                                 skin_id if item.mode == 'dark' else 'C')
                app.processEvents()
                combinations = status_combinations(current_colors())
                # The shell only paints running/success/failed (see window/run.py);
                # the neutral chip is the no-statusRole default.
                product = {role: combinations[role]
                           for role in ('running', 'success', 'failed')}
                for role, (expected_fg, expected_bg) in product.items():
                    chip = QLabel('Completed / 本轮已完成')
                    chip.setProperty('uiRole', 'statusChip')
                    chip.setProperty('statusRole', role)
                    chip.resize(300, 40)
                    chip.show()
                    app.processEvents()
                    frame = chip.grab().toImage()
                    background = frame.pixelColor(5, 20).name()
                    foreground = chip.palette().color(QPalette.WindowText).name()
                    assert background == expected_bg.lower(), (
                        skin_id, role, background, expected_bg)
                    assert foreground == expected_fg.lower(), (
                        skin_id, role, foreground, expected_fg)
                    ratio = contrast_ratio(foreground, background)
                    assert ratio >= 4.5, (skin_id, role, ratio)
                    chip_rows.append({'skin': skin_id, 'role': role,
                                      'foreground': foreground,
                                      'background': background,
                                      'contrast': round(ratio, 4)})
                    chip.close()
                    chip.deleteLater()
                    app.processEvents()
                neutral = QLabel('Idle')
                neutral.setProperty('uiRole', 'statusChip')
                neutral.resize(300, 40)
                neutral.show()
                app.processEvents()
                frame = neutral.grab().toImage()
                background = frame.pixelColor(5, 20).name()
                foreground = neutral.palette().color(QPalette.WindowText).name()
                colors = current_colors()
                assert background == colors.canvas_alt.lower(), (skin_id, background)
                assert foreground == colors.text_muted.lower(), (skin_id, foreground)
                assert contrast_ratio(foreground, background) >= 4.5, (skin_id, 'neutral')
                chip_rows.append({'skin': skin_id, 'role': 'neutral',
                                  'foreground': foreground,
                                  'background': background,
                                  'contrast': round(contrast_ratio(foreground, background), 4)})
                neutral.close()
                neutral.deleteLater()
                app.processEvents()
            (evidence / 'status-chips.json').write_text(
                json.dumps(chip_rows, indent=2), encoding='utf-8')
            window._set_theme('light', palette='B')
            app.processEvents()
            menu = window.theme_button.menu()
            menu.popup(window.theme_button.mapToGlobal(QPoint(0, window.theme_button.height())))
            app.processEvents()
            assert menu.isVisible()
            for mode, palette in (('dark', None), ('light', 'K'), ('light', 'B')):
                window._set_theme(mode, palette=palette)
                app.processEvents()
                assert menu.isVisible(), 'theme replacement must not dismiss an open menu'
                actual = menu.grab().toImage().pixelColor(5, 5)
                assert actual == QColor(current_colors().surface), (mode, actual.name(), current_colors().surface)
            menu.hide()
            (evidence / 'rendered-colours.json').write_text(json.dumps(raster, indent=2), encoding='utf-8')
        finally:
            assert _close_self_test_window(window, app, timeout=45), 'normal owned close did not drain'
            QThreadPool.globalInstance().waitForDone(45000)
            app.processEvents()
    print('theme shell: same colours do not refresh; real palette transitions refresh all custom views and preserve state')


if __name__ == '__main__':
    main()
