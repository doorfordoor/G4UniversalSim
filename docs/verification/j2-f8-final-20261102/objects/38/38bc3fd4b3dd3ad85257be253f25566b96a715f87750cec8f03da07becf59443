"""F8 offscreen keyboard, ownership, cancellation and layout component checks.

No installation, backend execution, formal desktop or stage acceptance is claimed.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gui'))
from PySide6.QtCore import QEvent, QSettings, QTimer, Qt, QPoint, QRect
from PySide6.QtGui import QFontDatabase, QFontMetrics
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QWizard, QWidget, QScrollArea, QLineEdit, QLabel, QPushButton
from g4usim_gui.core.accessibility import decorate_accessibility, ensure_focus_visible, _focus_control
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.core.i18n import ZH_CN, current_language, ui_text
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window


def pump(app, condition=lambda: True, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        QTest.qWait(5)
    assert condition(), 'GUI did not reach the expected state'


def shortcut(window, key, modifiers=Qt.ControlModifier | Qt.AltModifier):
    window.activateWindow()
    QTest.keyClick(window, key, modifiers)
    QApplication.processEvents()


def test_minimal_scroll(app):
    scroll = QScrollArea()
    scroll.resize(320, 180)
    content = QWidget()
    content.resize(1200, 150)
    button = QPushButton('readable', content)
    button.setGeometry(600, 20, 100, 30)
    label = QLabel('Label', content)
    label.setGeometry(580, 70, 120, 30)
    field = QLineEdit(content)
    field.setGeometry(710, 70, 450, 30)
    label.setBuddy(field)
    field._f8_accessible_label = label
    scroll.setWidget(content)
    scroll.show()
    pump(app)
    bar = scroll.horizontalScrollBar()
    bar.setValue(500)  # A deliberate, valid manual pan, not a test reset to zero.
    ensure_focus_visible(button)
    assert bar.value() == 500
    ensure_focus_visible(scroll)
    assert bar.value() == 500, 'A container must never pan its ancestors'
    bar.setValue(600)
    ensure_focus_visible(field)
    assert 0 < bar.value() < 600
    assert label.mapTo(scroll.viewport(), QPoint(0, 0)).x() >= 0
    assert field.mapTo(scroll.viewport(), QPoint(0, 0)).x() >= 0
    stable = bar.value()
    ensure_focus_visible(field)
    assert bar.value() == stable, 'Already readable context must not move'
    field.setGeometry(710, 70, 100, 30)
    label.setGeometry(580, 70, 120, 30)
    # Full union [580,810) fits a 318px viewport, but right edge starts 5px out.
    bar.setValue(810 - scroll.viewport().width() - 5)
    before = bar.value()
    ensure_focus_visible(field)
    assert bar.value() == before + 5
    whole = QRect(field.mapTo(scroll.viewport(), QPoint(0, 0)), field.size())
    assert scroll.viewport().rect().contains(whole)
    whole_label = QRect(label.mapTo(scroll.viewport(), QPoint(0, 0)), label.size())
    assert scroll.viewport().rect().contains(whole_label)
    scroll.close()
    scroll.deleteLater()
    pump(app)


def test_natural_navigation(app, window, output):
    # Start exactly like native125: natural show/focus, no scrollbar preparation.
    window.resize(1200, 800)
    pump(app)
    before = snapshot_fingerprint(window.capture_workspace())
    docks = dict(window.workspace_layout.docks)
    owners = {name: dock.parentWidget() for name, dock in docks.items()}
    observations = []
    for index in (0, 1, 2, 3, 4, 5, 6, 7, 8, 1, 0):
        shortcut(window, Qt.Key_1 + index)
        pump(app)
        focus = QApplication.focusWidget()
        assert not isinstance(focus, QScrollArea), (index, focus)
        assert focus is not None
        if index == 1:
            field = window.project_page.project_name
            label = field._f8_accessible_label
            viewport = window.content_scroll.viewport()
            assert label.mapTo(viewport, QPoint(0, 0)).x() >= 0
            assert field.mapTo(viewport, QPoint(0, 0)).x() >= 0
            offset = window.content_scroll.horizontalScrollBar().value()
            ensure_focus_visible(window.project_page.content_scroll)
            assert window.content_scroll.horizontalScrollBar().value() == offset
        if index == 0:
            headings = [label for label in window.start_page.findChildren(QLabel)
                        if label.text() == ui_text('Examples')]
            assert headings
            assert all(label.mapTo(window.content_scroll.viewport(), QPoint(0, 0)).x() >= 0 for label in headings)
        assert all(window.workspace_layout.docks[name] is dock and dock.parentWidget() is owners[name]
                   for name, dock in docks.items()), 'Navigation must not rebuild/reparent docks'
        observations.append({'page': index, 'focus': type(focus).__name__,
                             'content_x': window.content_scroll.horizontalScrollBar().value()})
    # Natural Tab after Configuration and all peer docks have been revealed.
    window.focus_page(1)
    for _ in range(12):
        QTest.keyClick(QApplication.focusWidget(), Qt.Key_Tab)
        pump(app)
        control = _focus_control(QApplication.focusWidget())
        if control is None:
            continue
        parent = control.parentWidget()
        label = getattr(control, '_f8_accessible_label', None)
        while parent is not None:
            if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(control):
                viewport = parent.viewport()
                whole = QRect(control.mapTo(viewport, QPoint(0, 0)), control.size())
                if label is not None and label.isVisible():
                    whole = whole.united(QRect(label.mapTo(viewport, QPoint(0, 0)), label.size()))
                if whole.width() <= viewport.width() and whole.height() <= viewport.height():
                    assert viewport.rect().contains(whole), (control.accessibleName(), whole, viewport.rect())
            parent = parent.parentWidget()
    window.focus_page(0)
    assert snapshot_fingerprint(window.capture_workspace()) == before
    if output:
        output.mkdir(parents=True, exist_ok=True)
        (output / 'natural-navigation.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')
        assert window.grab().save(str(output / 'natural-start.png'))


def test_navigation(app, window):
    before = snapshot_fingerprint(window.capture_workspace())
    for index in range(9):
        shortcut(window, Qt.Key_1 + index)
        assert window.page_stack.currentIndex() == index, index
        page = window.page_stack.currentWidget()
        focused = QApplication.focusWidget()
        assert focused is not None and (page is focused or page.isAncestorOf(focused)), (index, focused)
        assert window._nav_buttons[index].accessibleName()
        assert str(index + 1) in window._nav_buttons[index].accessibleDescription()
    window.focus_page(1)
    field = window.project_page.project_name
    assert field.accessibleName() == 'Project name', field.accessibleName()
    assert field._f8_accessible_label.buddy() is field
    assert window.project_page.executable.accessibleName() == 'G4UniversalSim executable'
    field.setFocus()
    shortcut(window, Qt.Key_F6, Qt.NoModifier)
    assert QApplication.focusWidget() is not field
    shortcut(window, Qt.Key_F6, Qt.ShiftModifier)
    assert QApplication.focusWidget() is field
    assert snapshot_fingerprint(window.capture_workspace()) == before
    window.focus_page(2)
    editor = window.config_builder_page.material_components
    assert editor.tabChangesFocus()
    editor.setFocus()
    text = editor.toPlainText()
    QTest.keyClick(editor, Qt.Key_Tab)
    assert QApplication.focusWidget() is not editor and editor.toPlainText() == text


def test_start(app, window):
    page = window.start_page
    window.focus_page(0)
    # Cancel the real file pickers: entry points must keep the complete draft.
    before = snapshot_fingerprint(window.capture_workspace())
    with patch.object(QFileDialog, 'getOpenFileName', return_value=('', '')) as opened:
        page.open_button.setFocus()
        QTest.keyClick(page.open_button, Qt.Key_Space)
        assert opened.call_count == 1
    with patch.object(QFileDialog, 'getExistingDirectory', return_value='') as imported:
        page.import_button.setFocus()
        QTest.keyClick(page.import_button, Qt.Key_Space)
        assert imported.call_count == 1
    assert snapshot_fingerprint(window.capture_workspace()) == before
    # The blank button reaches the existing action and its unsaved protection.
    from PySide6.QtWidgets import QMessageBox
    window.project_page.project_name.setText('F8 dirty draft')
    window._finish_history_merge()
    before = snapshot_fingerprint(window.capture_workspace())
    with patch.object(window, '_choose_unsaved_action', return_value=QMessageBox.Cancel) as choose:
        page.blank_button.setFocus()
        QTest.keyClick(page.blank_button, Qt.Key_Space)
        assert choose.called
    assert snapshot_fingerprint(window.capture_workspace()) == before
    assert window.project_page.project_name.text() == 'F8 dirty draft'


def test_wizard(app, window):
    window.project_page.seed.setText('invalid F8 seed draft')
    window._finish_history_merge()
    before = snapshot_fingerprint(window.capture_workspace())
    history = window._edit_session.can_undo
    visits = []
    failures = []
    def inside():
        try:
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, NewSimulationWizard), dialog
            visits.append(dialog)
            for language in ('en', 'zh_CN', 'en'):
                window._set_language(language, persist=False)
                for role, source in ((QWizard.NextButton, 'Next'), (QWizard.BackButton, 'Back'),
                                     (QWizard.FinishButton, 'Finish'), (QWizard.CancelButton, 'Cancel')):
                    assert dialog.buttonText(role) == ui_text(source), (language, source, dialog.buttonText(role), ui_text(source))
                    assert dialog.button(role).accessibleName() == ui_text(source), (language, source, dialog.button(role).accessibleName(), ui_text(source))
            dialog.scenario_page.name.setText('local wizard draft only')
            dialog.next()
            assert dialog.currentId() == 1
            dialog.geometry_page.thickness.setValue(7)
            dialog.next()
            dialog.back()
            assert dialog.geometry_page.thickness.value() == 7
            # Nested reentry must keep the exact existing dialog/spec.
            window.open_new_simulation_wizard()
            assert QApplication.activeModalWidget() is dialog
            assert dialog.geometry_page.thickness.value() == 7
            for which in (QWizard.CancelButton, QWizard.NextButton, QWizard.BackButton):
                button = dialog.button(which)
                assert button.isVisible() and dialog.rect().contains(button.geometry())
            dialog.reject()
        except BaseException as error:
            failures.append(error)
            modal = QApplication.activeModalWidget()
            if modal is not None:
                modal.reject()
    for _ in range(2):
        QTimer.singleShot(0, inside)
        window.open_new_simulation_wizard()
        assert not failures, failures
        assert snapshot_fingerprint(window.capture_workspace()) == before
        assert window._edit_session.can_undo == history
        assert window.project_page.seed.text() == 'invalid F8 seed draft'
    assert len(visits) == 2 and visits[0] is not visits[1]
    assert not window._f8_wizard_open


def test_environments(app, window):
    from g4usim_gui.widgets import environment_dialog as module
    facts = {'schema': 'g4usim_environment_discovery_v1', 'host': {'tools': {}}, 'sdk': [], 'environments': []}
    before = snapshot_fingerprint(window.capture_workspace())
    runner = window.runner
    service = window.experiment
    with patch.object(module, 'discover_environments', return_value=facts):
        window.start_page.environment_button.click()
        dialog = window._environment_dialog
        pump(app, lambda: dialog.facts is not None and not dialog.busy)
        assert dialog.isVisible() and dialog.select_button.isEnabled() is False
        window.show_environment_settings()
        assert window._environment_dialog is dialog
        window.show_environment_installer()
        installer = dialog._installation_dialog
        assert installer.isVisible() and installer.parentWidget() is dialog
        assert not installer.busy and installer.plan is None and installer.receipt is None
        assert installer.profile.accessibleName()
        installer.reject()
        dialog.reject()
        pump(app, lambda: not dialog.isVisible())
    assert window.runner is runner and window.experiment is service
    assert snapshot_fingerprint(window.capture_workspace()) == before


def test_layout(app, window, output):
    window.focus_page(0)
    page = window.start_page
    # Exercise the ordinary start layout after the earlier navigation test has
    # deliberately revealed all peer docks. Hiding is display-only J1 behavior.
    for dock in window.workspace_layout.docks.values():
        dock.hide()
    for width, height in [(1024, 700), (800, 540)]:
        window.resize(width, height)
        pump(app)
        assert window.width() <= width and window.height() <= height, (window.size(), width, height)
        for button in page.start_actions:
            button.setFocus(Qt.TabFocusReason)
            ensure_focus_visible(button)
            pump(app)
            assert button.isVisible() and button.isEnabled()
            viewport = page.start_scroll.viewport()
            from PySide6.QtCore import QRect, QPoint
            local = QRect(button.mapTo(viewport, QPoint(0, 0)), button.size())
            assert viewport.rect().contains(local), (button.text(), local, viewport.rect())
            outer = window.shell_scroll.viewport()
            external = QRect(button.mapTo(outer, QPoint(0, 0)), button.size())
            assert outer.rect().contains(external), (button.text(), external, outer.rect())
        assert page._action_columns <= 3
        for control in (window.project_context, window.run_context, window.theme_button, window.language_button):
            assert control.isVisible() and control.width() > 0
            assert window.page_header.rect().contains(control.geometry()), control
    # Larger font is an additional layout stressor; scale-factor runs are separate processes.
    font = app.font()
    larger = app.font()
    larger.setPointSizeF(max(9, larger.pointSizeF()) * 1.25)
    app.setFont(larger)
    page._adapt_start_layout()
    pump(app)
    for button in page.start_actions:
        button.setFocus()
        ensure_focus_visible(button)
        assert button.width() >= QFontMetrics(button.font()).horizontalAdvance(button.text()) + 12, button.text()
    app.setFont(font)
    if output:
        output.mkdir(parents=True, exist_ok=True)
        window.focus_page(0)
        window.resize(1024, 700)
        page.adapt_to_width(window.shell_scroll.viewport().width() - window.sidebar.width())
        page.start_scroll.verticalScrollBar().setValue(0)
        window.content_scroll.verticalScrollBar().setValue(0)
        window.shell_scroll.verticalScrollBar().setValue(0)
        pump(app)
        assert window.grab().save(str(output / 'start.png'))


def test_retained_dock_focus(app, output=None):
    """Native150 regression: reveal current focus after dock/central relayout.

    Uses production navigation and the real modal wizard, without preparing scroll
    positions. A separate window keeps the pre-existing smoke fixture untouched.
    """
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QVBoxLayout, QStackedWidget
    from shiboken6 import isValid
    from g4usim_gui.core.accessibility import owned_widget
    from g4usim_gui.core.i18n import set_application_language

    def settle():
        # Process posted QMainWindow layouts and queued focus work, never fix
        # geometry or scroll offsets from the test.
        for _ in range(8):
            app.processEvents()
        QTest.qWait(30)

    def key(window, key_code, modifiers=Qt.NoModifier):
        window.activateWindow()
        QTest.qWait(20)
        QTest.keyClick(window, key_code, modifiers)
        settle()

    observations = []
    with tempfile.TemporaryDirectory(prefix='f8-retained-docks-') as temp:
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, temp)
        apply_theme(app, 'light')
        set_application_language(app, 'zh_CN')
        window = MainWindow()
        project = window.project
        project.executable = os.environ.get('G4USIM_EXE', project.executable)
        project.pathSettings.executable = project.executable
        project.runsRoot = str(Path(temp) / 'runs')
        project.pathSettings.runs_root = project.runsRoot
        project.outputDir = str(Path(temp) / 'runs' / 'demo' / 'output')
        window._set_project(project)
        window._reset_edit_history()
        window.config_builder_page._backend_timer.stop()
        window.config_builder_page.schedule_backend_geometry = lambda *args, **kwargs: None
        window.resize(760, 640)
        docks = dict(window.workspace_layout.docks)
        owners = {name: dock.parentWidget() for name, dock in docks.items()}
        before = snapshot_fingerprint(window.capture_workspace())
        history = (window._edit_session.can_undo, window._edit_session.can_redo,
                   window._edit_session.is_modified)
        field = window.project_page.project_name
        label = field._f8_accessible_label
        foreign = None
        owned = None

        def observe(stage):
            settle()
            current = QStackedWidget.currentWidget(window.page_stack)
            ancestors = []
            parent = field.parentWidget()
            while parent is not None:
                if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(field):
                    viewport = parent.viewport()
                    whole = QRect(field.mapTo(viewport, QPoint(0, 0)), field.size())
                    union = whole.united(QRect(label.mapTo(viewport, QPoint(0, 0)), label.size()))
                    ancestors.append({'scroll': parent.objectName(),
                                      'viewport': list(viewport.rect().getRect()),
                                      'field': list(whole.getRect()), 'union': list(union.getRect()),
                                      'field_intersection': list(whole.intersected(viewport.rect()).getRect()),
                                      'h': parent.horizontalScrollBar().value(),
                                      'v': parent.verticalScrollBar().value()})
                parent = parent.parentWidget()
            observations.append({'stage': stage, 'page': window.page_stack.currentIndex(),
                                 'central': list(current.geometry().getRect()),
                                 'focus_is_project_name': QApplication.focusWidget() is field,
                                 'scrolls': ancestors})
            if output:
                output.mkdir(parents=True, exist_ok=True)
                assert window.grab().save(str(output / ('retained-' + stage + '.png')))

        def assert_project_visible():
            assert window.page_stack.currentIndex() == 1
            assert QApplication.focusWidget() is field
            parent = field.parentWidget()
            checked = []
            while parent is not None:
                if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(field):
                    viewport = parent.viewport()
                    whole = QRect(field.mapTo(viewport, QPoint(0, 0)), field.size())
                    assert viewport.rect().contains(whole), (parent.objectName(), whole, viewport.rect())
                    union = whole.united(QRect(label.mapTo(viewport, QPoint(0, 0)), label.size()))
                    if union.width() <= viewport.width():
                        assert union.left() >= 0 and union.right() < viewport.width(), (parent.objectName(), union)
                    if union.height() <= viewport.height():
                        assert union.top() >= 0 and union.bottom() < viewport.height(), (parent.objectName(), union)
                    checked.append(parent)
                parent = parent.parentWidget()
            assert window.content_scroll in checked and window.shell_scroll in checked

        try:
            window.show()
            window.activateWindow()
            settle()
            key(window, Qt.Key_2, Qt.ControlModifier | Qt.AltModifier)
            observe('01-project-initial')
            assert_project_visible()
            key(window, Qt.Key_3, Qt.ControlModifier | Qt.AltModifier)
            observe('02-config')
            assert docks['configuration'].isVisible() and docks['preview'].isVisible()
            key(window, Qt.Key_F6)
            observe('03-f6-preview')
            assert docks['preview'].isAncestorOf(QApplication.focusWidget())

            failures = []
            def cancel_wizard():
                dialog = QApplication.activeModalWidget()
                try:
                    assert isinstance(dialog, NewSimulationWizard), dialog
                    for expected in (1, 2, 3):
                        QTest.keyClick(dialog, Qt.Key_Return)
                        settle()
                        assert dialog.currentId() == expected
                    QTest.keyClick(dialog, Qt.Key_Left, Qt.AltModifier)
                    settle()
                    # Replay native AltLeft; Qt does not bind it to Back on
                    # every platform. Cancellation/retained layout is the contract.
                    QTest.keyClick(dialog, Qt.Key_Escape)
                except BaseException as error:
                    failures.append(error)
                finally:
                    if isinstance(dialog, QDialog) and dialog.isVisible():
                        dialog.reject()
            QTimer.singleShot(100, cancel_wizard)
            key(window, Qt.Key_N, Qt.ControlModifier)
            assert not failures, failures
            assert QApplication.activeModalWidget() is None
            observe('04-wizard-cancel')
            window._theme_actions['dark'].trigger()
            observe('05-dark')
            key(window, Qt.Key_2, Qt.ControlModifier | Qt.AltModifier)
            observe('06-project-return')
            assert_project_visible()
            QTest.qWait(100)
            observe('07-project-settled')
            assert_project_visible()
            assert docks['configuration'].isVisible() and docks['preview'].isVisible()

            for index in range(9):
                key(window, Qt.Key_1 + index, Qt.ControlModifier | Qt.AltModifier)
                assert window.page_stack.currentIndex() == index
                focus = QApplication.focusWidget()
                assert focus is not None and window.page_stack.currentWidget().isAncestorOf(focus)
                key(window, Qt.Key_F6)
                focus = QApplication.focusWidget()
                assert focus is not None and owned_widget(window, focus)
                assert all(window.workspace_layout.docks[name] is dock and dock.parentWidget() is owners[name]
                           for name, dock in docks.items())
            key(window, Qt.Key_2, Qt.ControlModifier | Qt.AltModifier)
            observe('08-ninepage-return')
            assert_project_visible()

            # First leave Project naturally and drain that navigation. Merely
            # focusing the already-current Project field would queue nothing.
            key(window, Qt.Key_1, Qt.ControlModifier | Qt.AltModifier)
            controller = window.accessibility_controller
            assert window.start_page.isAncestorOf(QApplication.focusWidget())
            assert controller._pending_focus is None
            # No event processing between these navigations: prove a real old
            # Project request exists, then prove Start replaces/cancels it.
            window.focus_page(1)
            assert QApplication.focusWidget() is field
            assert controller._pending_focus is not None
            assert controller._pending_focus() is field
            assert controller._reveal_timer.isActive()
            observations.append({'stage': 'stale-project-queued',
                                 'page': window.page_stack.currentIndex(),
                                 'pending_is_project': controller._pending_focus() is field,
                                 'timer_active': controller._reveal_timer.isActive()})
            window.focus_page(0)
            newest = QApplication.focusWidget()
            assert newest is not field and window.start_page.isAncestorOf(newest)
            pending = controller._pending_focus() if controller._pending_focus else None
            assert pending is not field
            assert pending is None or pending is newest
            observations.append({'stage': 'stale-start-supersedes',
                                 'page': window.page_stack.currentIndex(),
                                 'old_project_pending': pending is field,
                                 'pending_is_current_start': pending is newest,
                                 'pending_cancelled': pending is None})
            settle()
            assert controller._pending_focus is None
            assert window.page_stack.currentIndex() == 0
            assert QApplication.focusWidget() is newest and window.start_page.isAncestorOf(newest)
            parent = newest.parentWidget()
            while parent is not None:
                if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(newest):
                    viewport = parent.viewport()
                    target = QRect(newest.mapTo(viewport, QPoint(0, 0)), newest.size())
                    if target.width() <= viewport.width() and target.height() <= viewport.height():
                        assert viewport.rect().contains(target), (parent.objectName(), target)
                parent = parent.parentWidget()

            # A foreign QWidget focus cancels old owned work without panning the
            # main viewport or editing the foreign control.
            foreign = QDialog()
            foreign_field = QLineEdit()
            QVBoxLayout(foreign).addWidget(foreign_field)
            window.focus_page(1)
            offset = window.content_scroll.horizontalScrollBar().value()
            foreign.show()
            foreign.activateWindow()
            foreign_field.setFocus()
            settle()
            assert QApplication.focusWidget() is foreign_field
            assert not owned_widget(window, foreign_field)
            assert window.content_scroll.horizontalScrollBar().value() == offset
            assert foreign_field.text() == ''
            foreign.close()
            foreign.deleteLater()
            foreign = None
            window.activateWindow()
            settle()

            # Destroy an owned focus target with queued work outstanding. The
            # invalid C++ wrapper must never be dereferenced by the callback.
            owned = QDialog(window)
            doomed = QLineEdit()
            QVBoxLayout(owned).addWidget(doomed)
            owned.show()
            owned.activateWindow()
            settle()
            doomed.clearFocus()
            doomed.setFocus()
            assert QApplication.focusWidget() is doomed
            owned.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            assert not isValid(doomed)
            owned = None
            settle()
            key(window, Qt.Key_2, Qt.ControlModifier | Qt.AltModifier)
            assert_project_visible()
            assert snapshot_fingerprint(window.capture_workspace()) == before
            assert (window._edit_session.can_undo, window._edit_session.can_redo,
                    window._edit_session.is_modified) == history
        finally:
            if output:
                output.mkdir(parents=True, exist_ok=True)
                (output / 'retained-dock-focus.json').write_text(
                    json.dumps(observations, ensure_ascii=False, indent=2), encoding='utf-8')
            if foreign is not None and isValid(foreign):
                foreign.close()
                foreign.deleteLater()
            if owned is not None and isValid(owned):
                owned.reject()
                owned.deleteLater()
            close_window(app, window)


def test_history_directory_accessibility(app, output=None):
    """Bind the explicit History directory label without broad QHBox guessing."""
    from g4usim_gui.core.accessibility import _reading_anchor, readable_label
    from g4usim_gui.core.i18n import set_application_language

    def settle():
        for _ in range(8):
            app.processEvents()
        QTest.qWait(30)

    def key(window, code, modifiers=Qt.NoModifier):
        window.activateWindow()
        QTest.qWait(20)
        QTest.keyClick(window, code, modifiers)
        settle()

    observations = []
    with tempfile.TemporaryDirectory(prefix='f8-history-label-') as temp:
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, temp)
        apply_theme(app, 'light')
        set_application_language(app, 'en')
        window = MainWindow()
        runs = Path(temp) / 'long-runs-root-for-history-keyboard-and-accessibility' / 'preserved-run-packages'
        project = window.project
        project.runsRoot = str(runs)
        project.pathSettings.runs_root = project.runsRoot
        window._set_project(project)
        window._reset_edit_history()
        window.config_builder_page._backend_timer.stop()
        window.config_builder_page.schedule_backend_geometry = lambda *args, **kwargs: None
        window.resize(760, 640)
        before = snapshot_fingerprint(window.capture_workspace())
        history = (window._edit_session.can_undo, window._edit_session.can_redo,
                   window._edit_session.is_modified)
        field = window.run_history_page.runs_root
        label = window.run_history_page.layout().itemAt(0).layout().itemAt(0).widget()
        try:
            window.show()
            window.activateWindow()
            settle()
            assert label.buddy() is field
            assert getattr(field, '_f8_accessible_label', None) is label
            # Retain the real Config/Preview docks before entering History.
            key(window, Qt.Key_3, Qt.ControlModifier | Qt.AltModifier)
            key(window, Qt.Key_F6)
            docks = dict(window.workspace_layout.docks)
            assert docks['configuration'].isVisible() and docks['preview'].isVisible()
            for language in ('en', 'zh_CN', 'en'):
                window._set_language(language, persist=False)
                settle()
                key(window, Qt.Key_8, Qt.ControlModifier | Qt.AltModifier)
                assert window.page_stack.currentIndex() == 7
                assert QApplication.focusWidget() is field
                assert label.text() == ui_text('Runs root')
                assert field.accessibleName() == readable_label(label.text()) == ui_text('Runs root')
                assert label.buddy() is field and field._f8_accessible_label is label
                parent = field.parentWidget()
                inner_can_fit_union = True
                details = []
                while parent is not None:
                    if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(field):
                        viewport = parent.viewport()
                        full = QRect(field.mapTo(viewport, QPoint(0, 0)), field.size())
                        label_rect = QRect(label.mapTo(viewport, QPoint(0, 0)), label.size())
                        union = full.united(label_rect)
                        inner_can_fit_union = inner_can_fit_union and union.width() <= viewport.width()
                        # Once an inner viewport cannot fit the joint, preserve
                        # label + readable field prefix; do not promise a whole
                        # field through that narrower clipping ancestor.
                        prefix = QRect(full)
                        prefix.setWidth(min(prefix.width(), 128))
                        context = label_rect.united(prefix)
                        assert viewport.rect().contains(context), (language, parent.objectName(), context, viewport.rect())
                        if inner_can_fit_union:
                            assert viewport.rect().contains(union), (language, parent.objectName(), union)
                        details.append({'scroll': parent.objectName(), 'viewport': list(viewport.rect().getRect()),
                                        'field': list(full.getRect()), 'label': list(label_rect.getRect()),
                                        'joint': list(union.getRect()), 'anchor': list(_reading_anchor(field, viewport).getRect()),
                                        'h': parent.horizontalScrollBar().value()})
                    parent = parent.parentWidget()
                assert details
                assert field.text() == str(runs)
                assert not runs.exists()
                assert all(window.workspace_layout.docks[name] is dock for name, dock in docks.items())
                assert snapshot_fingerprint(window.capture_workspace()) == before
                assert (window._edit_session.can_undo, window._edit_session.can_redo,
                        window._edit_session.is_modified) == history
                observations.append({'language': language, 'name': field.accessibleName(),
                                     'label': label.text(), 'viewports': details})
            # The helper must be idempotent at the readable nonzero pan; the
            # test never supplies an offset or reveals the field itself.
            offset = window.content_scroll.horizontalScrollBar().value()
            assert offset > 0
            settle()
            assert window.content_scroll.horizontalScrollBar().value() == offset
            if output:
                output.mkdir(parents=True, exist_ok=True)
                assert window.grab().save(str(output / 'history-label.png'))
        finally:
            if output:
                output.mkdir(parents=True, exist_ok=True)
                (output / 'history-label.json').write_text(
                    json.dumps(observations, ensure_ascii=False, indent=2), encoding='utf-8')
            close_window(app, window)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--translations', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.translations:
        ZH_CN.update(json.loads(args.translations.read_text(encoding='utf-8')))
    app = QApplication.instance() or QApplication([])
    app.setApplicationName('F8-Accessibility-Smoke')
    app.setOrganizationName('G4UniversalSimSmoke')
    app.setStyle('Fusion')
    if os.name == 'nt':
        for name in ('segoeui.ttf', 'msyh.ttc'):
            QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR']) / 'Fonts' / name))
    apply_theme(app, 'light')
    app.setProperty('languageCode', 'en')
    with tempfile.TemporaryDirectory(prefix='f8-accessibility-') as temp:
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, temp)
        window = MainWindow()
        window.config_builder_page._backend_timer.stop()
        window.config_builder_page.schedule_backend_geometry = lambda *args, **kwargs: None
        try:
            window.show()
            window.activateWindow()
            pump(app)
            print('F8 window DPR:', window.devicePixelRatioF(), 'available:', window.screen().availableGeometry())
            test_minimal_scroll(app)
            window.activateWindow()
            test_natural_navigation(app, window, args.output)
            test_navigation(app, window)
            test_start(app, window)
            test_wizard(app, window)
            test_environments(app, window)
            test_layout(app, window, args.output)
            before = snapshot_fingerprint(window.capture_workspace())
            window._set_language('zh_CN', persist=False)
            assert window.start_page.environment_button.accessibleName() == ZH_CN.get('Environment setup...', 'Environment setup...')
            assert snapshot_fingerprint(window.capture_workspace()) == before
            if args.output:
                window.focus_page(0)
                window.start_page.start_scroll.verticalScrollBar().setValue(0)
                window.content_scroll.verticalScrollBar().setValue(0)
                pump(app)
                assert window.grab().save(str(args.output / 'start-zh.png'))
            window._set_language('en', persist=False)
        finally:
            close_window(app, window)
    test_retained_dock_focus(app, args.output)
    test_history_directory_accessibility(app, args.output)
    print('F8 keyboard/start/environment/wizard/layout offscreen checks passed')


if __name__ == '__main__':
    main()
