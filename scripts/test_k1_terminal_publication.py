"""Component signal ordering and terminal publication; no simulation is run."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

# This draft remains under out until the main owner authorizes transfer.
OUT = Path(__file__).resolve().parents[1]
ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / 'gui/g4usim_gui/core/evidence_job.py').is_file())
sys.path.insert(0, str(ROOT / 'gui'))
from PySide6.QtCore import QCoreApplication, QThread
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_fingerprint
from g4usim_gui.core.edit_transactions import EditSession
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.run_result import RunResult
from g4usim_gui.core.runner import G4USimRunner

def wait_for(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(.002)
    assert predicate(), 'component deadline'

def exercise(module, root, mode):
    root.mkdir(parents=True)
    project = G4USimProject(executable=sys.executable, workspaceRoot=str(root),
                           outputDir=str(root / 'output'), runsRoot=str(root / 'runs'))
    runner = G4USimRunner()
    session = EditSession(WorkspaceSnapshot(project))
    service = module.ExperimentWorkflow(session, runner, records_root=root / 'records')
    wait_for(lambda: not service._history_job.pending)
    received, callback_facts = [], []
    def completed(record):
        received.append(record)
        callback_facts.append({'busy': service.busy, 'owner_thread': QThread.currentThread() == service.thread()})
    service.completed.connect(completed)
    service._begin('run', 'execution')
    service._active.update(phase='initialization' if mode.startswith('init_') else 'run', project=project)
    context = service._active
    path = Path(context['record']['record_dir']) / 'record.json'
    writes, verification_calls = [], []
    entered, release = threading.Event(), threading.Event()
    verify_entered, verify_release = threading.Event(), threading.Event()
    real_persist = module._persist
    expected = 'cancelled' if 'cancel' in mode else ('stale' if mode == 'late_edit' else 'failed')
    def persist(record):
        if mode == 'persistence_failure':
            entered.set()
            if not release.wait(30):
                raise TimeoutError('test barrier')
            raise OSError('controlled component persistence failure')
        result = real_persist(record)
        writes.append(record['status'])
        if len(writes) == 1:
            entered.set()
            if not release.wait(30):
                raise TimeoutError('test barrier')
        return result
    def unavailable(*args, **kwargs):
        verification_calls.append(True)
        if mode == 'finished_before_error':
            verify_entered.set()
            if not verify_release.wait(30):
                raise TimeoutError('verification barrier')
        return SimpleNamespace(status='unverified')
    try:
        with patch.object(module, '_persist', persist), patch.object(module, 'output_evidence', unavailable):
            if mode in ('late_cancel', 'late_edit'):
                # A lifecycle-only fixture exercises a late cancellation/edit;
                # this record has no scientific evidence and is never qualified.
                service._finish('passed', 'component_terminal_race_only')
            elif mode == 'finished_before_error':
                runner.last_result = RunResult('killed', 'controlled component termination')
                runner.finished.emit(9)
                wait_for(verify_entered.is_set)
                runner.errorOccurred.emit('QProcess error: Crashed')
            else:
                if 'cancel' in mode:
                    service.cancel()
                runner.errorOccurred.emit('QProcess error: Crashed')
            wait_for(entered.is_set)
            assert service.busy and not received
            assert context['finishing'] is True
            initial_saved = json.loads(path.read_bytes()) if path.is_file() else None
            serial = service._job._serial
            if mode == 'late_cancel':
                service.cancel(force=True)
            elif mode == 'late_edit':
                service.invalidate('component_edit_during_terminal_write')
            runner.last_result = RunResult('killed', 'controlled component termination')
            # These real QObject signals reproduce error->finished->duplicates.
            runner.finished.emit(9)
            runner.errorOccurred.emit('QProcess error: Crashed')
            runner.finished.emit(9)
            if mode == 'late_work':
                service._work(lambda: verification_calls.append(True), lambda result: None)
            service.refresh()
            assert not received, 'Disk existence is not a completed receipt'
            release.set()
            verify_release.set()
            wait_for(lambda: not service._job.pending)
            QCoreApplication.processEvents()
            observed = {'mode': mode, 'busy': service.busy, 'completed_count': len(received),
                'finishing': bool(service._active and service._active.get('finishing')),
                'verification_calls': len(verification_calls), 'writes': writes,
                'serial_before_late_signals': serial, 'serial_after': service._job._serial,
                'saved_status': json.loads(path.read_bytes()).get('status') if path.is_file() else None}
            print(json.dumps(observed), flush=True)
            (root / 'observed.json').write_text(json.dumps(observed, indent=2) + '\n', encoding='utf-8')
            assert len(received) == 1, observed
            assert not service.busy and service._active is None
            assert callback_facts == [{'busy': False, 'owner_thread': True}]
            assert received[0]['status'] == expected
            assert received[0]['exit_code'] == 9
            assert received[0]['output_dir'] == project.outputDir
            assert received[0]['result']['state'] == 'killed'
            assert received[0]['result']['reason'] == 'controlled component termination'
            assert len(verification_calls) == (1 if mode == 'finished_before_error' else 0)
            if mode == 'persistence_failure':
                assert 'record_persistence_failed' in received[0]['reason']
                assert not path.exists()
            else:
                saved = json.loads(path.read_bytes())
                assert saved == received[0], 'Persisted final facts must equal the callback'
                assert saved['status'] == expected
                assert saved['exit_code'] == 9 and saved['result']['state'] == 'killed'
                assert initial_saved is not None
                if mode not in ('finished_before_error',):
                    assert initial_saved.get('exit_code') is None
                    assert len(writes) == 2, 'Late observed facts must trigger a second terminal write'
            assert service.state()['status'] == expected
            runner.finished.emit(9)
            runner.errorOccurred.emit('duplicate after completed')
            service.cancel(force=True)
            QCoreApplication.processEvents()
            assert len(received) == 1 and not service.busy
        service._begin('validate', 'fields')
        service._finish('failed', 'component_next_action_only')
        wait_for(lambda: len(received) == 2)
        assert not service.busy, 'The next action must remain usable'
    finally:
        release.set()
        verify_release.set()
        wait_for(lambda: not service._job.pending)
        if service._active is not None:
            # Failed OLD-code reproduction only, after assertions/observed.json.
            # Discard this isolated fixture to drain it; never a product remedy.
            print('FAILED-FIXTURE CLEANUP ONLY: discarding stuck context', flush=True)
            service._active = None
        service.close()
        wait_for(lambda: service._closed)
        assert not service._watcher.files() and not service._watcher.directories()
        assert all(not job.pending for job in (service._job, service._history_job, service._refresh_job))

def exercise_delivery_reason(module, root, mode):
    """Observe public terminal reasons after real queued work and an owner action."""
    root.mkdir(parents=True)
    project = G4USimProject(executable=sys.executable, workspaceRoot=str(root),
                           outputDir=str(root / 'output'), runsRoot=str(root / 'runs'))
    session = EditSession(WorkspaceSnapshot(project))
    service = module.ExperimentWorkflow(session, G4USimRunner(), records_root=root / 'records')
    wait_for(lambda: not service._history_job.pending)
    received, accepted = [], []
    service.completed.connect(received.append)
    entered, release = threading.Event(), threading.Event()
    before = snapshot_fingerprint(session.current())
    revision = session.revision

    def work():
        entered.set()
        if not release.wait(30):
            raise TimeoutError('component delivery barrier')
        return 'completed component work'

    def accept(result):
        accepted.append(result)
        service._finish('passed', 'component_delivery_only')

    try:
        service._begin('validate', 'fields')
        record_path = Path(service._active['record']['record_dir']) / 'record.json'
        service._work(work, accept)
        wait_for(entered.is_set)
        assert service.busy and not received
        if mode == 'cancel_work_delivery':
            service.cancel()
            assert session.revision == revision
            assert snapshot_fingerprint(session.current()) == before
            expected_status, expected_reason = 'cancelled', 'experiment.cancelled'
        else:
            candidate = session.current()
            candidate.project.projectName = 'Changed while work was in flight'
            session.replace('component actual workspace edit', candidate)
            assert session.revision > revision
            assert snapshot_fingerprint(session.current()) != before
            expected_status, expected_reason = 'stale', 'experiment.inputs_changed'
        release.set()
        wait_for(lambda: len(received) == 1)
        assert not accepted, 'Neither cancelled nor stale work may publish a passing result'
        assert not service.busy and service._active is None
        saved = json.loads(record_path.read_bytes())
        observed = {'mode': mode, 'status': received[0]['status'], 'reason': received[0]['reason'],
                    'revision_before': revision, 'revision_after': session.revision,
                    'snapshot_changed': before != snapshot_fingerprint(session.current()),
                    'completed_count': len(received), 'disk_matches_callback': saved == received[0]}
        (root / 'observed.json').write_text(json.dumps(observed, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(observed), flush=True)
        assert saved == received[0]
        assert saved['status'] == expected_status
        assert saved['reason'] == expected_reason, observed
        assert 'result' not in saved, 'Component work has no observed simulation result'
        service._begin('validate', 'fields')
        service._finish('failed', 'component_next_action_only')
        wait_for(lambda: len(received) == 2)
        assert not service.busy
    finally:
        release.set()
        wait_for(lambda: not service._job.pending)
        service.close()
        wait_for(lambda: service._closed)
        assert all(not job.pending for job in (service._job, service._history_job, service._refresh_job))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workflow', default=str(ROOT / 'gui/g4usim_gui/core/experiment_workflow.py'))
    parser.add_argument('--report-root', default='')
    parser.add_argument('--only', default='')
    args = parser.parse_args()
    if args.report_root:
        report_root = Path(args.report_root).expanduser().resolve()
    else:
        evidence_base = Path(os.environ.get('G4USIM_TEST_EVIDENCE_DIR') or
                             ROOT / 'out/collab/k1-terminal-publication').expanduser().resolve()
        report_root = evidence_base / ('terminal-' + uuid4().hex)
    report_root.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('isolated_workflow_under_test', args.workflow)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    app = QCoreApplication.instance() or QCoreApplication([])
    modes = [args.only] if args.only else ['cancel_error_finished', 'error_finished', 'init_cancel_error_finished',
        'init_error_finished', 'late_cancel', 'late_edit', 'persistence_failure', 'late_work', 'finished_before_error',
        'cancel_work_delivery', 'edit_work_delivery']
    results = []
    for mode in modes:
        try:
            if mode in ('cancel_work_delivery', 'edit_work_delivery'):
                exercise_delivery_reason(module, report_root / mode, mode)
            else:
                exercise(module, report_root / mode, mode)
        except Exception as error:
            results.append({'mode': mode, 'status': 'failed', 'error': str(error),
                            'traceback': traceback.format_exc()})
        else:
            results.append({'mode': mode, 'status': 'passed'})
        (report_root / 'case-results.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    report = {'scope': 'component_terminal_lifecycle_only', 'cases': len(results),
              'simulation': 'not_executed', 'workflow': str(Path(args.workflow).resolve()),
              'report_root': str(report_root), 'results': results}
    (report_root / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report), flush=True)
    assert all(row['status'] == 'passed' for row in results), 'terminal lifecycle case failed; see ' + str(report_root)

if __name__ == '__main__':
    main()
