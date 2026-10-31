"""K1 real Qt/service adapter smoke; fixtures do not claim backend physics."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gui'))


def wait_workflow(app, window, predicate=None, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        ready = predicate() if predicate is not None else not window.experiment.busy
        if ready and not getattr(window, '_experiment_loading', False):
            app.processEvents()
            return
        time.sleep(.005)
    assert False, ('workflow deadline', window.experiment.state())


def close_window(app, window, timeout=45):
    """Honor the service's public drain protocol before destroying Qt owners."""
    window.close()
    deadline = time.monotonic() + timeout
    while window.experiment.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    app.processEvents()
    assert not window.experiment.busy, 'experiment close did not drain'
    assert window.experiment.close(), 'closed service was not drained'
    window.close()
    app.processEvents()


def check_execution_command_preview(window, record, root):
    """Actual completed Generate + planner receipts; no simulation is launched."""
    from copy import deepcopy
    from g4usim_gui.core import backend_launch as launch
    from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
    from g4usim_gui.core.i18n import current_language, set_application_language
    from PySide6.QtWidgets import QApplication

    editor_cwd = window.project.workspaceRoot
    editor_path_cwd = window.project.pathSettings.workspace_root
    editor_text = window.project_page.workspace_root.text()
    before = snapshot_fingerprint(window.capture_workspace())
    command = [sys.executable, '--config', 'relative-input.ini']
    # Keep the complete old pre-dispatch preview contract, not just a substring.
    assert window._format_command_preview(command) == [
        'program:', '  ' + command[0], 'arguments:', '  --config', '  relative-input.ini',
        'working directory:', '  ' + (editor_cwd or '<not set>'), '',
        'human-readable:', '  ' + ' '.join(command)]
    assert window._format_command_preview([]) == []
    # This is the real service's completed Generate record, before fixture receipt rendering.
    assert record['action'] == 'generate' and record['status'] == 'passed'
    execution_cwd = record['execution_bundle']['path']
    assert Path(execution_cwd).resolve() != Path(editor_cwd).resolve()
    assert '\n  ' + execution_cwd + '\n' in window.run_page.command_preview.toPlainText()
    original_record = deepcopy(record)
    short = root / 'preview-observed-cwd'
    short.mkdir()
    deep = root / 'preview-logical-cwd'
    deep.mkdir()
    while launch.utf16_units(str(deep.resolve())) <= 270:
        deep /= 'logical-中文😀-segment'
        deep.mkdir()
    app = QApplication.instance()
    previous_language = current_language()
    try:
        for directory in (short, deep):
            # Windows route planning is exercised on both hosts; Python is never started.
            with patch.object(launch, 'WINDOWS', True):
                receipt = launch.prepare_backend_launch([sys.executable, '-c', "print('preview only')"], directory)
            assert receipt.requires_working_directory == (directory == deep)
            observed = deepcopy(record)
            observed['launch'] = receipt.to_dict()
            untouched_observation = deepcopy(observed)
            for language, logical_label, physical_label in (
                    ('en', 'Logical working directory:', 'Process launch directory:'),
                    ('zh_CN', '逻辑工作目录：', '进程启动目录：')):
                set_application_language(app, language)
                window._bind_experiment_package(observed)
                text = window.run_page.command_preview.toPlainText()
                assert logical_label + '\n  ' + str(directory.resolve()) + '\n' in text
                if directory == deep:
                    assert physical_label + '\n  ' + receipt.launch_cwd + '\n' in text
                else:
                    assert physical_label not in text
                assert 'human-readable:\n  ' + ' '.join(receipt.command) in text
                assert observed == untouched_observation
                assert window.project.workspaceRoot == editor_cwd
                assert window.project.pathSettings.workspace_root == editor_path_cwd
                assert window.project_page.workspace_root.text() == editor_text
                assert snapshot_fingerprint(window.capture_workspace()) == before
        # A legacy/incomplete display record cannot fabricate an observed editor cwd.
        missing = deepcopy(record)
        missing.pop('launch', None)
        missing.pop('execution_bundle', None)
        set_application_language(app, 'en')
        window._bind_experiment_package(missing)
        assert 'Logical working directory:\n  Unknown\n' in window.run_page.command_preview.toPlainText()
        assert record == original_record
        assert snapshot_fingerprint(window.capture_workspace()) == before
    finally:
        set_application_language(app, previous_language)
        window._bind_experiment_package(record)


def main():
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
    from g4usim_gui.core.wizard import default_spec
    from g4usim_gui.core.experiment_bundle import export_bundle
    from g4usim_gui.validators.config_validator import ValidationReport
    from g4usim_gui.window.experiment import experiment_reason
    from gui_test_window import MainWindow
    app = QApplication.instance() or QApplication([])
    messages = []
    with tempfile.TemporaryDirectory(prefix='k1-gui-') as directory, \
            patch.object(QMessageBox, 'warning', side_effect=lambda *a: messages.append(a[-1])), \
            patch.object(QMessageBox, 'information', return_value=QMessageBox.Ok):
        root = Path(directory)
        window = MainWindow()
        try:
            window.show()
            report = ValidationReport()
            diagnostic = report.add('k1.adapter.transport_fixture', 'error', 'Fixture input is invalid.',
                                    origin='k1.smoke', editor='source', field='energy')
            failed = dict(record_id='transport-fixture', action='validate', status='failed',
                          reason='experiment.fields_rejected', report=report)
            window._experiment_completed(failed)
            assert any(item.identity == diagnostic.identity for item in window.run_page.diagnostics_panel.records)
            assert any(item.identity == diagnostic.identity for item in window.config_builder_page.diagnostic_panel.records)
            assert all(item.code != 'experiment.action_failed' for item in window.run_page.diagnostics_panel.records)
            assert messages[-1].startswith(experiment_reason(failed))
            before_messages = len(messages)
            window._experiment_completed(failed)
            assert len(messages) == before_messages
            messages.clear()
            assert window.apply_simulation_wizard(default_spec('single_target'), run_after=False)
            window.project_page.executable.setText(sys.executable)
            window.project_page.runs_root.setText(str(root / 'runs'))
            window._finish_history_merge()
            assert window.experiment.runner is window.runner
            assert window.experiment._inspect is window._macro_inspection
            assert window.experiment.session is window._edit_session
            results = []
            window.experiment.completed.connect(results.append)
            before = snapshot_fingerprint(window.capture_workspace())
            assert window._generate_current_package() is None
            assert window.experiment.busy and not window.project_page.isEnabled()
            wait_workflow(app, window)
            assert results[-1]['status'] == 'passed', (results[-1]['reason'], getattr(results[-1].get('report'), 'errors', None))
            assert Path(window._generated_package_dir).is_dir()
            assert Path(window.project.configPath).is_file()
            assert snapshot_fingerprint(window.capture_workspace()) == before
            assert not window._generated_package_stale
            assert window.project_page.isEnabled()
            check_execution_command_preview(window, results[-1], root)
            count = len(results)
            window._experiment_completed(results[-1])
            assert len(results) == count
            old = results[-1]['record_id']
            window.config_builder_page.source_energy.setText('9 MeV')
            window._finish_history_merge()
            assert next(r for r in window.experiment.records() if r['record_id'] == old)['stale']
            window.undo_edit()
            assert next(r for r in window.experiment.records() if r['record_id'] == old)['stale']
            candidate = window._edit_session.current()
            candidate.project.projectName = 'K1 applied'
            candidate.state['drafts']['project.project_name'] = 'K1 applied'
            window.experiment.apply(candidate, expected_revision=window._edit_session.revision)
            wait_workflow(app, window)
            assert results[-1]['status'] == 'passed', (results[-1]['reason'], getattr(results[-1].get('report'), 'errors', None))
            assert window.project_page.project_name.text() == 'K1 applied'
            assert window.capture_workspace().project.projectName == 'K1 applied'
            assert window._edit_session.can_undo
            assert not window._workspace_fault
            bundle = root / 'bundle'
            export_bundle(window._edit_session.current(), bundle,
                          validation_records=[{'action': 'run', 'status': 'passed', 'run_id': 'historic'}])
            source_snapshot = window._edit_session.current()
            selected_runs = root / 'selected-runs'
            selected_runs.mkdir()
            with patch.object(QFileDialog, 'getExistingDirectory', side_effect=[str(bundle), str(selected_runs)]), \
                    patch.object(QFileDialog, 'getOpenFileName', return_value=(sys.executable, '')):
                window._load_experiment_bundle()
            assert window._experiment_loading
            wait_workflow(app, window)
            imported = window.experiment.records()
            assert any(r.get('stale') and r.get('stale_reason') == 'imported_history_requires_revalidation' for r in imported)
            assert window.project.executable == sys.executable
            assert Path(window.project.runsRoot) == selected_runs
            assert window.config_builder_page.source_editor.energy == source_snapshot.project.sourceEditor.energy
            assert window.project_file is None and window._edit_session.is_modified
            assert not messages, messages
            from g4usim_gui.core import experiment_bundle
            actual_export = experiment_bundle.export_bundle
            entered, release = threading.Event(), threading.Event()
            def delayed_export(*args, **kwargs):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('test export worker was not released')
                return actual_export(*args, **kwargs)
            with patch.object(experiment_bundle, 'export_bundle', side_effect=delayed_export):
                window.experiment.export(root / 'close-export')
                wait_workflow(app, window, predicate=entered.is_set)
                began = time.perf_counter()
                window.close()
                assert time.perf_counter() - began < 1
                assert window._experiment_close_pending and window.isVisible()
                release.set()
                wait_workflow(app, window)
                app.processEvents()
                assert results[-1]['status'] == 'cancelled', results[-1]['reason']
                assert not window.isVisible()
        finally:
            window._choose_unsaved_action = lambda: QMessageBox.Discard
            close_window(app, window)
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            app.processEvents()
    print('smoke_k1_workflow: OK (real service/Qt; no backend or physics claim)')


if __name__ == '__main__':
    main()
