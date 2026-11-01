"""Native layout persistence, actual controls and side-effect boundaries."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QDockWidget, QMessageBox
from gui_test_window import MainWindow
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.window.workspace_layout import STATE_KEY, PRESETS


def settle(app):
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def rewrite_payload(settings, mutate):
    envelope = json.loads(settings.value(STATE_KEY))
    mutate(envelope["payload"])
    body = json.dumps(envelope["payload"], sort_keys=True, separators=(",", ":"))
    envelope["sha256"] = hashlib.sha256(body.encode()).hexdigest()
    settings.setValue(STATE_KEY, json.dumps(envelope))


def default_start_lifecycle():
    """Fresh process: actual default-root discovery, hidden docks, shown Start."""
    from g4usim_gui.main_window import MainWindow as ProductMainWindow
    from g4usim_gui.core.i18n import set_application_language, ui_text
    from g4usim_gui.core.evidence_job import EvidenceJob
    from g4usim_gui.app import _close_self_test_window
    from PySide6.QtCore import QTimer
    from shiboken6 import isValid
    app = QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("WorkspaceDefaultStartLifecycle")
    app.setStyle("Fusion")
    settings = QSettings()
    settings.clear()
    apply_theme(app, "light")
    gate = threading.Event()
    original_submit = EvidenceJob.submit
    def gated_submit(job, work, done):
        if getattr(done, '__name__', '') == '_history_loaded':
            def history_work():
                assert gate.wait(30), 'History drain test gate was not released.'
                return work()
            return original_submit(job, history_work, done)
        return original_submit(job, work, done)
    with patch.object(EvidenceJob, 'submit', gated_submit):
        window = ProductMainWindow(offer_recovery=False)
    window.show()
    app.processEvents()
    assert window.page_stack.currentIndex() == 0
    assert window.workspace_layout.docks['configuration'].isHidden()
    assert window.workspace_layout.docks['preview'].isHidden()
    assert window.workspace_layout.docks['results'].isHidden()
    assert window._recovery_root is None
    assert window.experiment.records_root == (Path(window.project.runsRoot) / 'experiment-records').absolute()
    assert window.experiment._history_job.pending
    if os.environ.get('G4USIM_RECOVERY_DIR'):
        assert window._recovery.store.root == Path(os.environ['G4USIM_RECOVERY_DIR']).resolve()
    try:
        import pyvista  # noqa: F401 - same optional import boundary as package self-test
    except ImportError:
        pass
    set_application_language(app, 'zh_CN')
    assert ui_text('Parameter Scans') == '参数扫描'
    destroyed = QSignalSpy(window.destroyed)
    try:
        # Force the actual K1 history worker to remain pending across timeout.
        # No deletion is allowed while the shown default-Start close is ignored.
        assert not _close_self_test_window(window, app, timeout=0.03)
        assert isValid(window) and destroyed.count() == 0
        assert window.isVisible()
        assert window._experiment_close_pending or window._experiment_service_waiting
        QTimer.singleShot(20, gate.set)
        assert _close_self_test_window(window, app, timeout=10)
        assert not isValid(window) and destroyed.count() == 1
    finally:
        gate.set()
        if isValid(window):
            _close_self_test_window(window, app, timeout=10)
    settings.clear()
    print('default_start_lifecycle: ok; default-root entry; env_override=' +
          str(bool(os.environ.get('G4USIM_RECOVERY_DIR'))) +
          '; hidden docks, zh_CN, real history pending, refused-close retention, deferred deletion')


def preview_activation_cases(app):
    """Explicit preview intent schedules once; pure layout never collects."""
    from g4usim_gui.app import _close_self_test_window
    settings = QSettings()
    settings.clear()
    window = MainWindow()
    try:
        page = window.config_builder_page
        dock = window.workspace_layout.docks['preview']
        controller = window.geometry_controller
        process = controller.process
        window.show()
        settle(app)
        assert not page._backend_timer.isActive()
        assert page.preview3d_auto_backend.isChecked()
        # A real invalid draft must survive the automatic activation export.
        page.seed.setText(' invalid activation draft ')
        window._finish_history_merge()
        baseline = (asdict(window.project), deepcopy(window._capture_drafts()),
                    window._edit_session.revision, deepcopy(window.experiment.state()['levels']),
                    deepcopy(window.experiment.records()), asdict(page.geometry_document),
                    asdict(page.material_document))
        signals = QSignalSpy(page.autoBackendGeometryRequested)
        changed = QSignalSpy(page.settingsChanged)
        with ExitStack() as stack:
            for target, method in ((window, '_update_project_from_page_without_preview'),
                                   (page, 'set_run_defaults'), (page, 'update_project'),
                                   (window, 'save_project'), (window.runner, 'start'),
                                   (window.runner, 'terminate'), (window.runner, 'kill')):
                stack.enter_context(patch.object(target, method,
                                                side_effect=AssertionError('activation collected: ' + method)))
            request = stack.enter_context(patch.object(controller, 'request'))
            # Construction/readiness and hidden views do not schedule exports.
            page._preview_activation_ready = False
            page.preview3d_user_activated()
            assert not page._backend_timer.isActive()
            page._preview_activation_ready = True
            assert request.call_count == 0
            window.page_stack.setCurrentIndex(2)
            assert dock.isVisible() and page._backend_timer.isActive()
            QTest.qWait(1350)  # Existing preview debounce resets its timer to 1.2 s.
            assert signals.count() == 1 and request.call_count == 1, (signals.count(), request.call_count)
            assert request.call_args.args[0].geometry_path == page.geometry_config.text().strip()
            assert controller.process is process and not controller.is_running()

            dock.hide()
            page.preview3d_user_activated()
            assert not page._backend_timer.isActive()
            QTest.qWait(150)
            assert request.call_count == 1
            dock.toggleViewAction().trigger()
            QTest.qWait(1350)
            assert request.call_count == 2, 'Explicit Show 3D reuses the existing timer/controller.'

            # Disabling auto and hiding before timeout each cancel queued work.
            page.preview3d_auto_backend.setChecked(False)
            dock.hide()
            dock.toggleViewAction().trigger()
            QTest.qWait(150)
            assert request.call_count == 2 and not page._backend_timer.isActive()
            page.preview3d_auto_backend.setChecked(True)
            assert page._backend_timer.isActive()
            dock.hide()
            QTest.qWait(150)
            assert request.call_count == 2

            # Native visibility notifications from these layout actions are not
            # an explicit backend-preview activation, even with auto enabled.
            layout = window.workspace_layout
            for preset in PRESETS:
                layout.apply_preset(preset)
                QTest.qWait(150)
                assert request.call_count == 2 and not page._backend_timer.isActive()
            layout.apply_preset('configuration')
            assert layout.save()
            dock.hide()
            assert layout.restore()
            dock.setFloating(True)
            dock.setFloating(False)
            QTest.qWait(150)
            assert request.call_count == 2 and not page._backend_timer.isActive()

            # The original explicit 3D-tab activation still follows the same
            # timer; it now uses detached inputs through the shared auto branch.
            page.workspace_tabs.setCurrentIndex(page.preview3d_tab_index())
            QTest.qWait(1350)
            assert request.call_count == 3 and signals.count() == 3
        assert changed.count() == 0
        assert baseline == (asdict(window.project), deepcopy(window._capture_drafts()),
                            window._edit_session.revision, deepcopy(window.experiment.state()['levels']),
                            deepcopy(window.experiment.records()), asdict(page.geometry_document),
                            asdict(page.material_document))
        assert page.seed.text() == ' invalid activation draft '
    finally:
        assert _close_self_test_window(window, app)
        settings.clear()
        settings.sync()


def main():
    child_env = dict(os.environ)
    child_env.pop('G4USIM_RECOVERY_DIR', None)
    child = subprocess.run([sys.executable, '-X', 'faulthandler', str(Path(__file__).resolve()),
                            '--default-start-lifecycle'], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=90, env=child_env)
    assert child.returncode == 0, (child.returncode, child.stdout, child.stderr)
    assert 'default_start_lifecycle: ok' in child.stdout
    print(child.stdout.strip())
    with tempfile.TemporaryDirectory(prefix='g4usim-j1-default-recovery-') as recovery_dir:
        child_env['G4USIM_RECOVERY_DIR'] = recovery_dir
        child = subprocess.run([sys.executable, '-X', 'faulthandler', str(Path(__file__).resolve()),
                                '--default-start-lifecycle'], capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=90, env=child_env)
        assert child.returncode == 0, (child.returncode, child.stdout, child.stderr)
        assert 'default_start_lifecycle: ok' in child.stdout and 'env_override=True' in child.stdout
        print(child.stdout.strip())
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("WorkspaceLayout")
    settings = QSettings()
    settings.clear()
    apply_theme(app, "light")
    preview_activation_cases(app)
    settings = QSettings()
    settings.clear()
    settings.sync()
    from g4usim_gui.app import _close_self_test_window
    from shiboken6 import isValid
    window = MainWindow()
    try:
        window.show()
        initial_layout = window.workspace_layout
        assert window.page_stack.currentIndex() == 0
        assert initial_layout.save()
        assert json.loads(settings.value(STATE_KEY))['payload']['initial_configuration_preview'] is True
        window.page_stack._first_navigation_docks.clear()
        assert initial_layout.restore()
        window.page_stack.setCurrentIndex(2)
        page = window.config_builder_page
        page.preview3d_auto_backend.setChecked(False)
        page._backend_timer.stop()
        settle(app)
        layout = window.workspace_layout
        assert layout.docks['preview'].isVisible(), 'First configuration navigation reveals the current default preset.'
        layout.docks['preview'].hide()
        window.page_stack.setCurrentIndex(0)
        window.page_stack.setCurrentIndex(2)
        assert layout.docks['preview'].isHidden(), 'Manual hide survives later configuration navigation.'
        assert window.page_stack.count() == 9
        assert len(layout.hosts) == 1 and len(layout.docks) == 5
        assert layout.docks["configuration"].widget() is page
        assert page.isAncestorOf(page.setup_panel)
        assert layout.docks["preview"].isAncestorOf(page.preview3d_widget)
        assert layout.docks["results"].widget().widget() is window.output_page
        assert window.output_page.isAncestorOf(window.output_page.file_tree)
        assert layout.docks["logs"].isAncestorOf(window.run_page.stdout_view)
        assert layout.docks["logs"].widget().isAncestorOf(window.run_page.stdout_view)
        assert not layout.docks["ai"].isVisible()
        assert "not connected" in layout.docks["ai"].windowTitle().lower()
        for dock in layout.docks.values():
            assert dock.features() & QDockWidget.DockWidgetMovable
            assert dock.features() & QDockWidget.DockWidgetFloatable
            assert dock.features() & QDockWidget.DockWidgetClosable

        # Keep an invalid raw draft and observed run state. Layout has no reason
        # to collect, validate, save or control any business operation.
        page.seed.setText(" invalid seed draft ")
        window._finish_history_merge()
        window.run_page.set_state("running")
        window.run_page.set_progress_state("starting")
        window.run_page.set_progress({"run_id": 7, "planned_events": 10, "completed_events": 3,
                                     "phase": "running", "rate_eps": None, "eta_s": None})
        window.run_page.append_stdout("existing log\n")
        snapshot = (asdict(window.project), deepcopy(window._capture_drafts()),
                    window._edit_session.revision, window.run_page._run_display_view(),
                    window.run_page.stdout_view.toPlainText())
        changed = QSignalSpy(page.settingsChanged)
        pages = tuple(window.page_stack.widget(i) for i in range(9))
        controls = (page.setup_panel, page.preview3d_widget, window.output_page.splitter,
                    window.run_page.stdout_view)
        current_page = window.page_stack.currentIndex()
        current_tab = page.workspace_tabs.currentIndex()
        with ExitStack() as stack:
            for target, method in ((window, "_update_project_from_page_without_preview"),
                                   (page, "update_project"), (window, "save_project"),
                                   (window, "start_run"), (window, "stop_run"),
                                   (window.runner, "start"), (window.runner, "terminate"),
                                   (window.runner, "kill")):
                stack.enter_context(patch.object(target, method,
                                                side_effect=AssertionError("layout called " + method)))
            for preset in PRESETS:
                layout.preset_actions[preset].trigger()
                settle(app)
                assert layout.preset == preset
                assert window.page_stack.currentIndex() == current_page
                assert page.workspace_tabs.currentIndex() == current_tab
            layout.apply_preset("configuration")
            config_dock = layout.docks["configuration"]
            native_float = QSignalSpy(config_dock.topLevelChanged)
            native_visibility = QSignalSpy(config_dock.visibilityChanged)
            config_dock.setFloating(True)
            config_dock.resize(480, 540)
            settle(app)
            assert config_dock.isFloating() and native_float.count() > 0
            assert config_dock.width() >= 480 and config_dock.height() == 540
            config_dock.close()
            settle(app)
            assert config_dock.isHidden() and native_visibility.count() > 0
            config_dock.toggleViewAction().trigger()
            settle(app)
            assert config_dock.isVisible()
            config_dock.setFloating(False)
            layout.hosts["workspace"].addDockWidget(Qt.RightDockWidgetArea, config_dock)
            settle(app)
            assert layout.hosts["workspace"].dockWidgetArea(config_dock) == Qt.RightDockWidgetArea
            config_dock.setFloating(True)
            assert layout.save()
            layout.apply_preset("analysis")
            assert not config_dock.isFloating()
            assert layout.restore() and layout.last_restore == "restored"
            assert config_dock.isFloating()
            # Theme and palette actions have the same side-effect boundary.
            window._set_theme("dark")
            window._set_palette("K")
            assert app.property("themeMode") == "dark"
            assert app.property("lightThemePalette") == "K"
            window._set_theme("light")
            assert app.property("resolvedPalette") == "K"
            settle(app)
        assert changed.count() == 0
        assert snapshot == (asdict(window.project), deepcopy(window._capture_drafts()),
                            window._edit_session.revision, window.run_page._run_display_view(),
                            window.run_page.stdout_view.toPlainText())
        assert pages == tuple(window.page_stack.widget(i) for i in range(9))
        assert controls == (page.setup_panel, page.preview3d_widget, window.output_page.splitter,
                            window.run_page.stdout_view)

        # Real keystrokes immediately adjacent to docking must remain captured.
        # The focus adapter keys off queued edits, never a timing grace period.
        revision = window._edit_session.revision
        page.seed.setFocus()
        page.seed.selectAll()
        QTest.keyClicks(page.seed, " adjacent-before ")
        config_dock.setFloating(False)
        settle(app)
        assert page.seed.text() == " adjacent-before "
        assert window._edit_session.current().state['drafts']['config.seed'] == " adjacent-before "
        assert window._edit_session.revision > revision
        window._finish_history_merge()
        config_dock.setFloating(True)
        page.seed.setFocus()
        page.seed.selectAll()
        QTest.keyClicks(page.seed, " adjacent-after ")
        settle(app)
        assert page.seed.text() == " adjacent-after "
        assert window._edit_session.current().state['drafts']['config.seed'] == " adjacent-after "
        window.undo_edit()
        assert page.seed.text() == " adjacent-before "
        window.redo_edit()
        assert page.seed.text() == " adjacent-after "

        # All four actual views share one native host and can be visible at once.
        window.resize(1900, 1080)
        layout.apply_preset("running")
        layout.docks['results'].show()
        settle(app)
        for name in ('configuration', 'preview', 'results', 'logs'):
            dock = layout.docks[name]
            assert dock.parentWidget() is layout.hosts['workspace']
            assert dock.isVisible() and not dock.isFloating()
            assert not dock.visibleRegion().isEmpty()
            assert dock.width() > 50 and dock.height() > 50
            assert layout.hosts['workspace'].rect().contains(dock.geometry())
        from itertools import combinations
        for left, right in combinations(('configuration', 'preview', 'results', 'logs'), 2):
            assert not layout.docks[left].geometry().intersects(layout.docks[right].geometry())
        assert page.preview3d_tab_visible()
        assert page.preview3d_tab_index() == 3
        # A hidden native dock remains an explicit diagnostic reveal path, while
        # an individually hidden control continues to be refused.
        from g4usim_gui.widgets.diagnostic_navigation import can_reveal_widget, reveal_widget
        config_dock.hide()
        assert can_reveal_widget(page.seed).ok
        assert reveal_widget(page.seed).ok
        settle(app)
        assert config_dock.isVisible()
        page.seed.hide()
        assert not can_reveal_widget(page.seed).ok
        page.seed.show()
        # Floating makes dock the page's Qt window, but late-error suppression
        # must still read the one main-window closing flag.
        results_dock = layout.docks['results']
        results_dock.setFloating(True)
        assert window.output_page.window() is results_dock
        window._closing = True
        try:
            with patch.object(QMessageBox, 'warning') as warning:
                window.output_page._merge_runner.errorOccurred.emit('late merge error')
                assert warning.call_count == 0
        finally:
            window._closing = False
            results_dock.setFloating(False)

        # A valid screen change must redock floats; corrupt settings must never
        # lose controls. Re-sign malformed Qt data to exercise Qt's own rejection.
        rewrite_payload(settings, lambda payload: payload.update(screens=[{"name": "unplugged"}]))
        assert layout.restore() and layout.last_restore == "screen_fallback"
        assert all(not dock.isFloating() for dock in layout.docks.values())
        assert layout.save()
        rewrite_payload(settings, lambda payload: payload.update(version=2))
        assert not layout.restore() and layout.last_restore == "invalid_fallback"
        assert layout.save()
        rewrite_payload(settings, lambda payload: payload["hosts"].update(workspace="bm90LXEtc3RhdGU="))
        assert not layout.restore() and layout.last_restore == "invalid_fallback"
        assert page.seed.text() == " adjacent-after "
        for raw in ("not json", "[]", '{"payload":null}', "x" * (1024 * 1024 + 1)):
            settings.setValue(STATE_KEY, raw)
            assert not layout.restore() and layout.last_restore == "invalid_fallback"
        layout.reset()
        assert settings.value(STATE_KEY) is None
        assert layout.preset == "configuration"
        assert layout.last_restore == "reset"
        assert layout.save()
        assert "workspaceDock" not in json.dumps(asdict(window.project))
        assert _close_self_test_window(window, app)
        assert not isValid(window)
        # Fresh window consumes the same saved local layout and palette.
        second = MainWindow()
        try:
            second.show()
            settle(app)
            assert second.workspace_layout.last_restore == "restored"
            assert app.property("lightThemePalette") == "K"
            assert second.page_stack.count() == 9
        finally:
            assert _close_self_test_window(second, app)
    finally:
        if isValid(window):
            assert _close_self_test_window(window, app)
        settings.clear()
    print("smoke_workspace_layout: ok")


if __name__ == "__main__":
    if '--default-start-lifecycle' in sys.argv:
        default_start_lifecycle()
    else:
        main()
