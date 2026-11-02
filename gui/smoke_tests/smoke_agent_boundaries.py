"""QCore controller boundaries, not backend execution or independent acceptance.

The workflow below controls scheduling/ownership only. TaskJournal and EditSession
are real product objects; IO faults use patch. Independent review evidence stays
separate: this permanent author regression imports only current product code.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gui'))

from PySide6.QtCore import QCoreApplication, QObject, QProcess, Signal

from g4usim_gui.agent.actions import SCHEMA, PlanError
from g4usim_gui.agent.controller import AgentController
from g4usim_gui.agent.session import JournalIOError, TaskJournal
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_fingerprint
from g4usim_gui.core.edit_transactions import EditSession
from g4usim_gui.core.project import G4USimProject


def authorization(actions):
    return dict(allowed_actions=list(actions), max_calls=8, max_events=4, timeout_seconds=30)


class ControlledWorkflow(QObject):
    """No runner/process/validation: count requests and deliver owned facts."""

    completed = Signal(object)

    def __init__(self):
        super().__init__()
        project = G4USimProject()
        project.runSettings.beam_on = 4
        self.session = EditSession(WorkspaceSnapshot(project))
        self.active = None
        self.rows = []
        self.calls = []
        self.cancel_count = 0
        self.force_count = 0

    @property
    def busy(self):
        return self.active is not None

    def state(self):
        return {'controlled_ownership_only': True}

    def records(self):
        return deepcopy(self.rows)

    def issue(self, action, **facts):
        assert not self.busy, 'Controlled owner cannot overlap requests'
        identifier = uuid4().hex
        record = dict(record_id=identifier, run_id=identifier, action=action,
                      status='pending', revision=self.session.revision, stale=False)
        record.update(facts)
        self.rows.append(record)
        self.calls.append(action)
        self.active = identifier
        return deepcopy(record)

    def apply(self, candidate, **kwargs):
        # Accept a real F5 value; no UI projection or K1/backend validation claim.
        self.session.replace(kwargs['label'], candidate, expected_revision=kwargs['expected_revision'])
        return self.issue('apply')

    def export(self, destination, **kwargs):
        return self.issue('export', destination=str(destination))

    def cancel(self, force=False):
        self.cancel_count += 1
        self.force_count += int(force)

    def finish(self, record_id, status='cancelled', **facts):
        record = next(row for row in self.rows if row['record_id'] == record_id)
        record.update(status=status, reason='controlled.terminal', **facts)
        if self.active == record_id:
            self.active = None
        self.completed.emit(deepcopy(record))


def pump_until(app, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.002)
    assert predicate(), 'Controlled queued delivery did not drain'


def pump(app):
    for _ in range(5):
        app.processEvents()


@contextmanager
def controller_fixture(app, root):
    workflow = ControlledWorkflow()
    controller = AgentController(workflow, tasks_root=root)
    try:
        yield workflow, controller
    finally:
        if controller._recovered and not controller.busy:
            # A query handle owns no work: release it without cancelling history.
            if controller.journal is not None:
                controller.journal.close()
        else:
            controller.close()
            if controller._bound_record is not None:
                workflow.finish(controller._bound_record)
            pump_until(app, lambda: not controller.busy)
        controller._timer.stop()


def empty_reply(messages, cancel_event=None):
    context = json.loads(messages[1]['content'])['context']
    return json.dumps(dict(schema=SCHEMA, base_fingerprint=context['base_fingerprint'],
                           summary='Controlled response, no runtime claim', changes=[], clarifications=[]))


def begin_review(app, controller):
    controller.set_provider(empty_reply)
    controller.start('Review this configuration', authorization(['plan', 'apply']))
    pump_until(app, lambda: not controller.busy)
    assert controller.journal.state == 'awaiting_approval'


def owned_run(controller, workflow):
    """Seed the post-dispatch seam; this never invokes an actual run service."""
    controller.journal = TaskJournal.create(controller.tasks_root, 'Controlled in-flight run',
                                             authorization(['run']), controller._identity())
    operation = controller.journal.record_intent('run', dict(events=4, revision=workflow.session.revision))
    record = workflow.issue('run')
    controller.journal.record_binding(operation, dict(record_id=record['record_id'], run_id=record['run_id']))
    controller._operation = operation
    controller._bound_record = record['record_id']
    controller._steps = ['run']
    return controller.journal, record


def test_cancel_write_failure_drains(app, root):
    with controller_fixture(app, root) as (workflow, controller):
        journal, record = owned_run(controller, workflow)
        with patch.object(journal, 'cancel', side_effect=JournalIOError('agent.journal.controlled_io')):
            controller.close()
        assert workflow.cancel_count == 1
        assert controller.busy and journal._owner is not None
        assert controller.state()['reason'] == 'agent.journal_write_failed'
        # Another owner's completion cannot release this lease.
        workflow.completed.emit(dict(record_id='f' * 32, status='passed'))
        pump(app)
        assert controller.busy and journal._owner is not None
        workflow.finish(record['record_id'], result=dict(completed_events=2))
        pump_until(app, lambda: not controller.busy)
        assert journal._owner is None
        disk = TaskJournal.load(journal.path).to_dict()
        assert disk['operations'][0]['result']['events'] == 2
        assert controller.state()['state'] == 'failed'


def test_result_write_failure_releases_only_old_owner(app, root):
    with controller_fixture(app, root) as (workflow, controller):
        journal, record = owned_run(controller, workflow)
        controller.close()
        assert workflow.cancel_count == 1
        # Queue completion, then hand the fake workflow to somebody else before
        # controller delivery. The late callback must not cancel that new owner.
        workflow.finish(record['record_id'], 'passed', result=dict(completed_events=3))
        other = workflow.issue('unrelated-manual-owner')
        with patch.object(journal, 'record_result', side_effect=JournalIOError('agent.journal.controlled_io')):
            pump_until(app, lambda: not controller.busy)
        assert workflow.cancel_count == 1
        assert workflow.active == other['record_id'] and workflow.busy
        assert journal._owner is None
        assert controller.state()['state'] == 'failed'
        assert controller.state()['reason'] == 'agent.journal.controlled_io'
        assert journal.to_dict()['operations'][0]['result'] is None
        assert TaskJournal.load(journal.path).to_dict()['operations'][0]['result'] is None


def test_approve_dispatch_once(app, root):
    with controller_fixture(app, root) as (workflow, controller):
        begin_review(app, controller)
        assert controller.approve_plan() is True
        assert controller.approve_plan() is False
        controller._queue_next()
        controller._queue_next()
        pump(app)
        assert workflow.calls == ['apply']
        assert workflow.cancel_count == 0
        assert controller.journal.state == 'applying' and controller.busy
        assert len(controller.journal.to_dict()['operations']) == 2


def test_confirm_dispatch_once(app, root):
    with controller_fixture(app, root) as (workflow, controller):
        controller._revision = workflow.session.revision
        controller._fingerprint = snapshot_fingerprint(workflow.session.current())
        controller._authorization = authorization(['export'])
        controller.journal = TaskJournal.create(root, 'Controlled confirmation', controller._authorization,
                                                 controller._identity())
        controller.journal.transition('awaiting_confirmation')
        first = root / 'first-bundle'
        controller.confirm(first)
        assert controller.confirm(root / 'second-bundle') is False
        pump(app)
        assert workflow.calls == ['export']
        assert workflow.cancel_count == 0
        assert controller._destination == first
        assert workflow.records()[0]['destination'] == str(first)
        assert len(controller.journal.to_dict()['operations']) == 1


def pending_journal(root, identity):
    journal = TaskJournal.create(root, 'Controlled interrupted run', authorization(['run']), identity)
    operation = journal.record_intent('run', dict(events=4, revision=0, record_id='a' * 32, run_id='b' * 32))
    path = journal.path
    journal.close()
    return path, operation


def historical_record(**changes):
    record = dict(record_id='a' * 32, run_id='b' * 32, action='run', status='passed',
                  reason='controlled.historical', revision=99, stale=True, level='execution',
                  result=dict(completed_events=3))
    record.update(changes)
    return record


def test_recovery_binding_and_history(app, root):
    cases = [([], 'unobserved'),
             ([historical_record(record_id='c' * 32)], 'unobserved'),
             ([historical_record(run_id='c' * 32)], 'unobserved'),
             ([historical_record(action='generate')], 'unobserved'),
             ([historical_record(), historical_record()], 'unobserved'),
             ([historical_record(status='pending')], 'in_progress'),
             ([historical_record()], 'historical')]
    for index, (rows, status) in enumerate(cases):
        with controller_fixture(app, root / str(index)) as (workflow, controller):
            path, operation = pending_journal(root / str(index) / 'interrupted', controller._identity())
            before = path.read_bytes()
            workflow.rows = rows
            policy = controller.recover(path)
            query = policy['queries'][0]
            assert query['operation_id'] == operation and query['status'] == status
            assert policy['can_replay'] is False
            assert controller.state()['state'] == 'interrupted'
            assert controller._authorization == {} and controller.plan is None
            assert not controller.busy and workflow.calls == [] and workflow.cancel_count == 0
            result = TaskJournal.load(path).to_dict()['operations'][0]['result']
            if status == 'historical':
                assert query['current_qualification'] is False and query['query_result_persisted'] is True
                assert result['status'] == 'passed' and result['stale'] is True
                assert result['revision'] == 99 and result['events'] == 3
            else:
                assert path.read_bytes() == before
                assert result is None
            for action in (controller.approve_plan, controller.continue_run, controller.confirm):
                try:
                    action()
                except PlanError:
                    assert workflow.calls == []
                else:
                    assert False, 'Recovered authorization must not execute'


def test_old_queue_cannot_enter_recovery(app, root):
    with controller_fixture(app, root) as (workflow, controller):
        begin_review(app, controller)
        assert controller.approve_plan() is True
        serial = controller._serial
        assert controller._scheduled_serial == serial
        controller.cancel()
        path, _ = pending_journal(root / 'interrupted', controller._identity())
        before = path.read_bytes()
        policy = controller.recover(path)  # No pump since approval queued its work.
        assert controller._serial != serial and controller._scheduled_serial is None
        count = len(workflow.records())
        pump(app)
        assert controller.state()['state'] == 'interrupted'
        assert controller._fatal_reason is None and controller._authorization == {}
        assert len(workflow.records()) == count and workflow.calls == []
        assert workflow.cancel_count == 0 and path.read_bytes() == before
        assert policy['can_replay'] is False
        # Exercise the second guard independently of the retired callback serial.
        controller._next(controller._serial)
        assert controller.state()['state'] == 'interrupted'
        assert path.read_bytes() == before and workflow.calls == []


def test_cancel_keeps_late_facts_without_advancing(app, root):
    with controller_fixture(app, root / 'owned') as (workflow, controller):
        journal, record = owned_run(controller, workflow)
        controller.cancel()
        assert workflow.cancel_count == 1 and journal.state == 'cancelled'
        assert controller.busy and journal._owner is not None
        workflow.finish(record['record_id'], 'passed', result=dict(completed_events=2))
        pump_until(app, lambda: not controller.busy)
        disk = TaskJournal.load(journal.path).to_dict()
        assert disk['state'] == 'cancelled'
        assert disk['operations'][0]['result']['status'] == 'passed'
        assert disk['operations'][0]['result']['events'] == 2
        assert len(disk['operations']) == 1 and workflow.calls == ['run']
        assert journal._owner is None
        before = journal.path.read_bytes()
        workflow.completed.emit(deepcopy(workflow.rows[0]))
        pump(app)
        assert journal.path.read_bytes() == before and workflow.cancel_count == 1
    with controller_fixture(app, root / 'provider') as (workflow, controller):
        entered, release = threading.Event(), threading.Event()

        def delayed(messages, cancel_event=None):
            entered.set()
            if not release.wait(5):
                raise TimeoutError('Controlled provider was not released')
            return empty_reply(messages)

        controller.set_provider(delayed)
        before = snapshot_fingerprint(workflow.session.current())
        try:
            controller.start('Will be cancelled', authorization(['plan', 'apply']), auto_apply=True, write_scope=[])
            pump_until(app, entered.is_set)
            controller.cancel()
            assert controller.busy
            release.set()
            pump_until(app, lambda: not controller.busy)
            assert not controller.provider_alive
            task = controller.journal.to_dict()
            assert task['state'] == 'cancelled'
            assert len(task['operations']) == 1
            assert task['operations'][0]['result']['status'] == 'cancelled'
            assert task['operations'][0]['result']['reason'] == 'agent.cancelled'
            assert snapshot_fingerprint(workflow.session.current()) == before
            assert workflow.calls == [] and workflow.cancel_count == 0
        finally:
            release.set()
            pump_until(app, lambda: not controller.busy)


def test_cancel_escalation_preserves_owner(app, root):
    with controller_fixture(app, root / 'guards') as (workflow, controller):
        journal, record = owned_run(controller, workflow)
        controller.cancel()
        timer_id = controller._cancel_timer.timerId()
        assert controller._cancel_timer.isActive() and controller._cancel_timer.interval() == 3000
        controller.cancel()
        assert controller._cancel_timer.timerId() == timer_id
        assert controller._cancel_binding == (controller._serial, record['record_id'])
        # Another owner has started before this owner's queued completion delivery.
        workflow.rows[0]['status'] = 'cancelled'
        workflow.active = None
        other = workflow.issue('run')
        controller._force_cancel_owned()
        assert workflow.force_count == 0 and workflow.active == other['record_id']
        workflow.finish(other['record_id'])
        workflow.finish(record['record_id'])
        pump_until(app, lambda: not controller.busy)
        assert not controller._cancel_timer.isActive() and controller._cancel_binding is None
        assert journal.state == 'cancelled'
    with controller_fixture(app, root / 'deadline') as (workflow, controller):
        journal, record = owned_run(controller, workflow)
        controller._authorization = authorization(['run'])
        controller._started = time.monotonic() - 60
        controller._deadline()
        assert controller._fatal_reason == 'agent.task_timeout'
        assert controller._cancel_timer.isActive() and workflow.cancel_count == 1
        workflow.rows.insert(0, dict(record_id='older-interrupted-history', status='pending', stale=True))
        controller._force_cancel_owned()
        assert workflow.force_count == 1 and journal.state == 'failed'
        workflow.finish(record['record_id'], result=dict(completed_events=1))
        pump_until(app, lambda: not controller.busy)
        assert journal.to_dict()['operations'][0]['result']['events'] == 1


def test_cancel_escalation_real_child(app, root):
    # A local Python child deliberately ignores soft termination on Unix and has
    # no Windows GUI window. This verifies QProcess cleanup, not a Geant4 run.
    process = QProcess()
    process.setProgram(sys.executable)
    process.setArguments(['-u', '-c',
                          'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);'
                          'print("ready",flush=True);time.sleep(40)'])
    workflow = ControlledWorkflow()
    controller = AgentController(workflow, tasks_root=root)
    original_cancel = workflow.cancel

    def cancel_child(force=False):
        original_cancel(force)
        (process.kill if force else process.terminate)()

    workflow.cancel = cancel_child
    try:
        process.start()
        assert process.waitForStarted(3000)
        pump_until(app, lambda: process.bytesAvailable() > 0)
        assert bytes(process.readAllStandardOutput()).strip() == b'ready'
        journal, record = owned_run(controller, workflow)
        process.finished.connect(lambda *_: workflow.finish(record['record_id'], result=dict(completed_events=0)))
        controller.cancel()
        assert controller.busy and journal._owner is not None
        pump_until(app, lambda: process.state() == QProcess.NotRunning and not controller.busy, timeout=8)
        assert workflow.force_count == 1
        assert journal.to_dict()['operations'][0]['result']['events'] == 0
        assert journal.state == 'cancelled' and journal._owner is None
    finally:
        if process.state() != QProcess.NotRunning:
            process.kill()
            process.waitForFinished(3000)
        controller.close()
        if controller._bound_record is not None:
            workflow.finish(controller._bound_record)
        pump(app)
        assert process.state() == QProcess.NotRunning and not controller.busy


def main():
    app = QCoreApplication.instance() or QCoreApplication([])
    tests = (test_cancel_write_failure_drains, test_result_write_failure_releases_only_old_owner,
             test_approve_dispatch_once, test_confirm_dispatch_once, test_recovery_binding_and_history,
             test_old_queue_cannot_enter_recovery, test_cancel_keeps_late_facts_without_advancing,
             test_cancel_escalation_preserves_owner, test_cancel_escalation_real_child)
    with tempfile.TemporaryDirectory(prefix='agent-boundaries-') as directory:
        for test in tests:
            test(app, Path(directory) / test.__name__)
            print('PASS ' + test.__name__)
    print('Agent boundaries: QCore/controlled ownership/real journal and F5; no backend validation claim')


if __name__ == '__main__':
    main()
