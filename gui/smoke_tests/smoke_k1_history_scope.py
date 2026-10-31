"""K1 scope: default backend-free GUI components; --mode backend runs real 3/3.

Components use explicit observed-state fixtures and the real GUI interfaces,
never a service validation receipt. Backend mode requires --executable/G4USIM_EXE.
No window.show(), no physical accuracy claim. --counterexample seed is backend-only.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch
from types import SimpleNamespace

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(os.environ.get('K1_WORKSPACE_ROOT', Path(__file__).resolve().parents[2]))
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'gui/smoke_tests'), str(ROOT / 'scripts')]


def wait(app, predicate, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(.005)
    assert predicate(), 'K1 history display deadline'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture_scope(app, window, root, stem):
    """Render the actual hidden widgets; never show a native window."""
    page = window.run_page
    page.resize(1150, 900)
    page.ensurePolished()
    page.layout().activate()
    page.content_scroll.widget().layout().activate()
    app.processEvents()
    page.content_scroll.ensureWidgetVisible(page.result_label, 0, 80)
    assert page.grab().save(str(root / (stem + '-page.png')))
    window.run_context.resize(window.run_context.sizeHint())
    assert window.run_context.grab().save(str(root / (stem + '-chip.png')))


def require_history(window):
    page = window.run_page
    assert 'Previous run (configuration changed)' in window.run_context.text(), window.run_context.text()
    assert window.run_context.property('statusRole') == ''
    assert 'Previous run (configuration changed)' in page.result_label.text(), page.result_label.text()
    assert 'Previous run (configuration changed)' in page.progress_label.text(), page.progress_label.text()
    assert 'Previous run (configuration changed)' in page.progress_bar.format()
    assert page.progress_bar.value() == 1000
    assert '3/3' in page.progress_label.text()
    assert 'Simulation succeeded' in page.result_label.text() or 'success' in page.result_label.text().lower()


def components():
    """Exercise actual view projection using synthetic observations, no backend.

    The fixture is a public state/records/busy boundary, not an alternative
    workflow, eligibility algorithm, process controller or persisted history.
    """
    from PySide6.QtCore import QCoreApplication, QEvent, QProcess
    from PySide6.QtWidgets import QApplication, QLabel
    from g4usim_gui.core.i18n import set_application_language
    from g4usim_gui.core.runner import G4USimRunner
    from g4usim_gui.widgets.run_page import RunPage
    from g4usim_gui.window.experiment import ExperimentMixin
    from g4usim_gui.window.shell import ShellMixin

    class ObservedView(ExperimentMixin, ShellMixin):
        pass

    app = QApplication.instance() or QApplication([])
    set_application_language(app, 'en')
    page = RunPage()
    chip = QLabel()
    window = ObservedView()
    window.run_page = page
    window.run_context = chip
    window._run_chip = ('Running', 'running')
    window._run_display_observed = False
    window._displayed_run_binding = None
    observed = {'revision': 7, 'qualification': 'as_observed', 'history': [
        {'record_id': 'fixture-record-A', 'run_id': 'fixture-run-A', 'revision': 7,
         'action': 'run', 'level': 'execution', 'status': 'pending', 'stale': False,
         'requested_run_name': 'same-label', 'output_dir': '/same/path'}]}
    active = False
    window.runner = SimpleNamespace(is_running=lambda: active)
    window.experiment = SimpleNamespace(busy=True, records=lambda: deepcopy(observed['history']))
    original = deepcopy(observed)
    try:
        # Guard both entry points: a components invocation must never silently
        # turn into integration when a runner injects G4USIM_EXE into the GUI profile.
        with patch.object(G4USimRunner, 'start', side_effect=AssertionError('No backend in components')) as runner_start, \
                patch.object(QProcess, 'start', side_effect=AssertionError('No process in components')) as process_start:
            window._bind_started_run_display()
            assert window._displayed_run_binding == ('fixture-record-A', 'fixture-run-A', 7)
            page.set_state('Running')
            page.set_progress_state('starting')
            page.set_progress({'run_id': 0, 'completed_events': 3, 'planned_events': 3, 'phase': 'end'})
            page.set_progress_state('success')
            page.set_exit_code(0)
            page.set_result('success')
            page.append_stdout('component observed log\n')
            page.retain_run_display()
            window._set_run_chip('success', 'success')

            window._project_experiment_run_display(observed)
            assert page._run_display_scope == 'checking'
            assert 'verification in progress' in chip.text()
            assert chip.property('statusRole') == ''
            assert 'verification in progress' in page.progress_bar.format()
            assert page.progress_bar.value() == 1000

            observed['history'][0]['status'] = 'passed'  # Explicit view fixture, not a validation result.
            window.experiment.busy = False
            window._project_experiment_run_display(observed)
            assert page._run_display_scope == 'current'
            assert chip.property('statusRole') == 'success'
            immutable_fixture = deepcopy(observed)
            changed = deepcopy(observed)
            changed['history'][0]['stale'] = True
            window._project_experiment_run_display(changed)
            require_history(window)
            assert observed == immutable_fixture

            # Preserve F5 reset sentinels, but retain the historical display.
            page.set_result('Not run yet')
            page._progress_data = None
            page.set_progress_state('idle')
            window._set_run_chip('Needs validation', 'warning')
            assert page._result_state == 'Not run yet' and page._progress_data is None
            require_history(window)
            assert 'component observed log' in page.stdout_view.toPlainText()

            changed['revision'] = 8
            changed['history'][0]['stale'] = False
            window._project_experiment_run_display(changed)
            require_history(window)
            # A return to the old semantic value at a later revision does not
            # change which record/revision is displayed or confer new eligibility.
            changed['revision'] = 9
            window._project_experiment_run_display(changed)
            require_history(window)

            set_application_language(app, 'zh_CN')
            page.refresh_language()
            window._render_run_chip()
            assert '上次运行（配置已变更）' in chip.text()
            assert '上次运行（配置已变更）' in page.result_label.text()
            assert '上次运行（配置已变更）' in page.progress_bar.format()
            set_application_language(app, 'en')
            page.refresh_language()
            window._render_run_chip()
            require_history(window)

            # A same-label, same-path, same-count fixture with a different run
            # identity cannot qualify the selected result.
            wrong = deepcopy(observed)
            wrong['history'][0]['run_id'] = 'fixture-foreign-run'
            window._project_experiment_run_display(wrong)
            assert page._run_display_scope == 'unverified'
            assert chip.property('statusRole') == ''
            assert 'current inputs unverified' in page.result_label.text()

            newer = deepcopy(observed)
            newer['history'].append(dict(observed['history'][0], record_id='fixture-record-B', run_id='fixture-run-B'))
            window._project_experiment_run_display(newer)
            assert page._run_display_scope == 'historical'
            assert 'Previous run:' in chip.text()
            assert chip.property('statusRole') == ''
            for terminal in ('failed', 'cancelled'):
                rejected = deepcopy(observed)
                rejected['history'][0]['status'] = terminal
                window._project_experiment_run_display(rejected)
                assert page._run_display_scope == 'unverified'
                assert chip.property('statusRole') == ''
                assert page._retained_run_view['result'] == 'success'

            # New GUI process lifecycle binds the sole pending authoritative ID
            # and drops retained 100%; no real process is launched in this mode.
            observed['history'] = [dict(original['history'][0], record_id='fixture-record-C', run_id='fixture-run-C')]
            window.experiment.busy = True
            active = True
            page.set_progress_state('starting')
            window._bind_started_run_display()
            page.set_state('Starting')
            window._set_run_chip('Starting', 'running')
            window._project_experiment_run_display(observed)
            assert window._displayed_run_binding == ('fixture-record-C', 'fixture-run-C', 7)
            assert page._run_display_scope == 'running'
            assert page._retained_run_view is None and page._progress_data is None
            assert page.progress_bar.maximum() == 0
            assert 'Previous run' not in page.progress_label.text()
            assert 'fixture-run-C' in page.result_label.toolTip()

            # Ambiguous pending records remain explicitly unidentified.
            active = False
            observed['history'].append(dict(original['history'][0], record_id='fixture-record-D'))
            window._bind_started_run_display()
            window._project_experiment_run_display(observed)
            assert window._displayed_run_binding is None
            assert page._run_display_scope == 'unverified'
            assert chip.property('statusRole') == ''
            assert not page.isVisible() and not chip.isVisible()
            assert not runner_start.called and not process_start.called
        print('smoke_k1_history_scope: components OK; synthetic observed-state fixtures, no backend/validation receipts')
    finally:
        page.close()
        chip.close()
        page.deleteLater()
        chip.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def backend(args):
    assert args.executable and Path(args.executable).is_file(), 'Real backend is required'
    root = Path(args.evidence_root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / 'inputs'
    inputs.mkdir()
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QMessageBox
    from gui_test_window import MainWindow
    from g4usim_gui.core.i18n import set_application_language
    from g4usim_gui.core.theme import apply_theme
    from test_f5_transactions_backend import initial_state
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setFont(QFont('Microsoft YaHei UI', 10))
    apply_theme(app, 'light')
    set_application_language(app, 'en')
    window = MainWindow(recovery_root=root / 'recovery')
    gates = []
    records = []
    messages = []
    try:
        with patch.object(QMessageBox, 'warning', side_effect=lambda *a: messages.append(a[-1])):
            snapshot, (_, geometry) = initial_state(inputs, Path(args.executable).resolve())
            snapshot.project.runSettings.run_name = 'same-label-3-events'
            window._edit_session.reset(snapshot, saved=True, apply=window.apply_workspace)
            window.history_changed()
            window._set_language('en', persist=False)
            window.experiment.completed.connect(records.append)
            window.experiment._refresh_timer.stop()
            page = window.run_page

            # Hold only the post-process evidence worker. The actual runner and
            # backend run normally; no production state or record is fabricated.
            original_work = window.experiment._work
            entered, release = threading.Event(), threading.Event()
            gates.append(release)
            def work_with_verify_gate(work, done):
                if window.runner.last_result is not None and window.experiment._active['phase'] == 'run':
                    def held():
                        entered.set()
                        assert release.wait(45), 'Verification gate was not released'
                        return work()
                    return original_work(held, done)
                return original_work(work, done)
            with patch.object(window.experiment, '_work', side_effect=work_with_verify_gate):
                first_pending = window.experiment.run()
                wait(app, entered.is_set)
                assert window.runner.last_result.state == 'success'
                assert window.runner.last_result.completed_events == 3
                assert window.experiment.busy
                if not args.counterexample:
                    assert 'verification in progress' in window.run_context.text(), window.run_context.text()
                    assert window.run_context.property('statusRole') == ''
                    assert 'verification in progress' in page.result_label.text()
                    assert 'verification in progress' in page.progress_label.text()
                    assert page.progress_bar.value() == 1000
                release.set()
                wait(app, lambda: bool(records) and not window.experiment.busy)
            first = records[-1]
            assert first['record_id'] == first_pending['record_id']
            assert first['status'] == 'passed', first['reason']
            assert first['result']['completed_events'] == first['result']['planned_events'] == 3
            if not args.counterexample:
                wait(app, lambda: page._run_display_scope == 'current')
                assert window.run_context.property('statusRole') == 'success'
                assert window._displayed_run_binding == (first['record_id'], first['run_id'], first['revision'])
            summary = Path(first['output_dir']) / 'run_summary.txt'
            record_path = Path(first['record_dir']) / 'record.json'
            original_hashes = {str(p): sha(p) for p in (summary, record_path)}
            original_result = deepcopy(first['result'])
            original_logs = page.stdout_view.toPlainText()
            window.config_builder_page.seed.setText('4343')
            window._finish_history_merge()
            assert next(r for r in window.experiment.records() if r['record_id'] == first['record_id'])['stale']
            print('seed counterexample: chip=', window.run_context.text(), flush=True)
            print('seed counterexample: result=', page.result_label.text(), flush=True)
            print('seed counterexample: progress=', page.progress_label.text(), flush=True)
            require_history(window)
            assert original_hashes == {p: sha(p) for p in original_hashes}
            assert first['result'] == original_result
            assert page.stdout_view.toPlainText() == original_logs
            if args.counterexample:
                return

            # Undo and Redo use real F5 revisions and projection reset. Retain
            # historical display while preserving original F5 internal sentinels.
            revision = window._edit_session.revision
            window.undo_edit()
            assert window._edit_session.revision > revision
            assert page._result_state == 'Not run yet' and page._progress_data is None
            require_history(window)
            assert page.stdout_view.toPlainText() == original_logs
            window.redo_edit()
            require_history(window)
            window.config_builder_page.seed.setText('not-an-integer')
            # Raw draft invalidation is immediate, before history commit.
            require_history(window)
            window._finish_history_merge()
            require_history(window)
            window.undo_edit()
            require_history(window)
            window.apply_workspace(window._edit_session.current())
            window.history_changed()
            require_history(window)

            window._set_language('zh_CN', persist=False)
            assert '上次运行（配置已变更）' in window.run_context.text()
            assert '上次运行（配置已变更）' in page.result_label.text()
            assert '上次运行（配置已变更）' in page.progress_label.text()
            assert '上次运行（配置已变更）' in page.progress_bar.format()
            assert first['run_id'] in page.result_label.toolTip()
            capture_scope(app, window, root, 'changed-zh')
            window._set_language('en', persist=False)
            require_history(window)

            # A new actual run owns a new record even with identical label/N.
            count = len(records)
            second_pending = window.experiment.run()
            wait(app, lambda: len(records) > count and not window.experiment.busy)
            second = records[-1]
            assert second['status'] == 'passed', second['reason']
            assert first['run_id'] != second['run_id']
            assert first['requested_run_name'] == second['requested_run_name']
            assert second['result']['completed_events'] == 3
            assert window._displayed_run_binding[0] == second_pending['record_id']
            wait(app, lambda: page._run_display_scope == 'current')
            assert window.run_context.property('statusRole') == 'success'
            capture_scope(app, window, root, 'current-en')

            # View-only counterexamples use copies of public state. Keep real
            # service records untouched; do not promote the selected old result.
            state = window.experiment._state()
            binding = window._displayed_run_binding
            wrong_identity = deepcopy(state)
            selected = next(r for r in wrong_identity['history'] if r['record_id'] == binding[0])
            selected['run_id'] = 'different-run-with-identical-label-count-and-path'
            window._project_experiment_run_display(wrong_identity)
            assert page._run_display_scope == 'unverified'
            assert window.run_context.property('statusRole') == ''
            window._displayed_run_binding = (first['record_id'], first['run_id'], first['revision'])
            window._project_experiment_run_display(state)
            require_history(window)
            window._displayed_run_binding = binding
            # Two verified runs at the same revision can both remain valid.
            # Selecting the older identity must still label it as historical.
            same_revision = deepcopy(state)
            old = next(r for r in same_revision['history'] if r['record_id'] == first['record_id'])
            old.update(stale=False, revision=state['revision'])
            window._displayed_run_binding = (old['record_id'], old['run_id'], old['revision'])
            window._project_experiment_run_display(same_revision)
            assert page._run_display_scope == 'historical'
            assert window.run_context.property('statusRole') == ''
            assert window._displayed_run_binding[0] != second['record_id']
            window._displayed_run_binding = binding
            for status in ('failed', 'cancelled', 'unobserved'):
                rejected = deepcopy(state)
                selected = next(r for r in rejected['history'] if r['record_id'] == binding[0])
                selected['status'] = status
                window._project_experiment_run_display(rejected)
                assert page._run_display_scope == 'unverified'
                assert window.run_context.property('statusRole') == ''
                assert second['result']['state'] == 'success'
            checking = deepcopy(state)
            checking['qualification'] = 'checking'
            window._project_experiment_run_display(checking)
            assert page._run_display_scope == 'checking'
            assert window.run_context.property('statusRole') == ''

            # Real service terminal failure before a new process starts keeps
            # the selected older 3/3 result historical, without relabelling it.
            count = len(records)
            with patch.object(window.experiment, '_factory', side_effect=ValueError('scope_test_prepare_failure')):
                window.experiment.run()
                wait(app, lambda: len(records) > count and not window.experiment.busy)
            assert records[-1]['status'] == 'failed', records[-1]
            assert window._displayed_run_binding == binding
            assert page._run_display_scope == 'historical'
            assert page.progress_bar.value() == 1000
            assert window.run_context.property('statusRole') == ''

            # Cancel a real pending preparation, holding its existing worker;
            # no extra process or owner and no synthetic completed receipt.
            entered, release = threading.Event(), threading.Event()
            gates.append(release)
            def preparing_gate(work, done):
                def held():
                    entered.set()
                    assert release.wait(45), 'Preparation gate was not released'
                    return work()
                return original_work(held, done)
            count = len(records)
            with patch.object(window.experiment, '_work', side_effect=preparing_gate):
                window.experiment.run()
                wait(app, entered.is_set)
                assert page._run_display_scope == 'historical'
                window.experiment.cancel()
                release.set()
                wait(app, lambda: len(records) > count and not window.experiment.busy)
            assert records[-1]['status'] == 'cancelled'
            assert window._displayed_run_binding == binding
            assert page._run_display_scope == 'historical'
            assert window.run_context.property('statusRole') == ''

            # External bytes changed: use the existing service watcher/refresh.
            # No edit-session revision change is used to manufacture staleness.
            revision = window._edit_session.revision
            geometry.write_text(geometry.read_text(encoding='utf-8') + '\n# external change\n', encoding='utf-8')
            window.experiment.refresh()
            wait(app, lambda: next(r for r in window.experiment.records() if r['record_id'] == second['record_id']).get('stale'))
            assert window._edit_session.revision == revision
            require_history(window)
            assert original_hashes == {p: sha(p) for p in original_hashes}
            assert not messages, messages
            (root / 'receipt.json').write_text(json.dumps({
                'backend': str(Path(args.executable).resolve()), 'backend_sha256': sha(args.executable),
                'record_ids': [first['record_id'], second['record_id']],
                'run_ids': [first['run_id'], second['run_id']],
                'completed_events': [first['result']['completed_events'], second['result']['completed_events']],
                'unchanged_original_evidence_sha256': original_hashes,
                'offscreen': True, 'native_window_shown': False, 'physics_accuracy_validated': False,
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print('smoke_k1_history_scope: OK; real 3/3 twice, synthetic identity/status projections separated')
    finally:
        for gate in gates:
            gate.set()
        if window.experiment.busy:
            window.experiment.cancel(force=True)
        wait(app, lambda: not window.experiment.busy)
        window.experiment.close()
        wait(app, lambda: window.experiment._closed)
        assert not window.runner.is_running()
        assert not window._bundle_job.pending
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['components', 'backend'], default='components')
    parser.add_argument('--executable', default=os.environ.get('G4USIM_EXE'))
    parser.add_argument('--evidence-root', default=os.environ.get('G4USIM_TEST_EVIDENCE_DIR'))
    parser.add_argument('--counterexample', choices=['seed'])
    args = parser.parse_args()
    if args.mode == 'components':
        assert args.counterexample is None, '--counterexample is backend-only'
        components()
    else:
        assert args.evidence_root, '--evidence-root is required for backend mode'
        backend(args)


if __name__ == '__main__':
    main()
