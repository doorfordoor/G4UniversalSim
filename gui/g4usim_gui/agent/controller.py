"""L1 owner-thread orchestration over the existing K1 service and F5 session."""
from __future__ import annotations

import copy
from pathlib import Path
import threading
import time
from uuid import uuid4

from PySide6.QtCore import QObject, QTimer, Signal, Qt

from g4usim_gui.agent.actions import (
    PlanError, build_candidate, describe_changes, enforce_scope, parse_plan, planner_messages, requires_review,
)
from g4usim_gui.agent.session import TaskJournal
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint

TERMINAL = {'completed', 'cancelled', 'failed', 'interrupted'}
STAGES = {'apply': 'applying', 'validate': 'validating', 'initialize': 'initializing',
          'generate': 'generating', 'run': 'running', 'evaluate': 'evaluating', 'export': 'exporting'}


class AgentController(QObject):
    stateChanged = Signal(object)
    errorRaised = Signal(str)
    _providerDelivered = Signal(int, object, object)

    def __init__(self, workflow, *, tasks_root, parent=None):
        super().__init__(parent)
        self.workflow = workflow
        self.tasks_root = Path(tasks_root)
        self.provider = None
        self.journal = None
        self.plan = None
        self._snapshot = None
        self._fingerprint = None
        self._revision = None
        self._authorization = {}
        self._owner_id = uuid4().hex
        self._thread = None
        self._event = threading.Event()
        self._serial = 0
        self._operation = None
        self._bound_record = None
        self._steps = []
        self._auto_run = False
        self._closed = False
        self._fatal_reason = None
        self._started = 0.0
        self._destination = None
        self._write_scope = None
        self._scheduled_serial = None
        self._recovered = False
        self._recovery_policy = None
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._deadline)
        self._cancel_binding = None
        self._cancel_timer = QTimer(self)
        self._cancel_timer.setSingleShot(True)
        self._cancel_timer.setInterval(3000)
        self._cancel_timer.timeout.connect(self._force_cancel_owned)
        self._providerDelivered.connect(self._planned, Qt.QueuedConnection)
        self.workflow.completed.connect(self._completed, Qt.QueuedConnection)

    @property
    def provider_alive(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def busy(self):
        return self._thread is not None or self._bound_record is not None

    def state(self):
        record = self.journal.to_dict() if self.journal else {}
        return {'task_id': self.journal.task_id if self.journal else '',
                'state': ('failed' if self._fatal_reason else 'interrupted' if self._recovered
                          else 'planning' if self._thread is not None
                          else self.journal.state if self.journal else 'idle'),
                'reason': self._fatal_reason or record.get('reason', ''),
                'plan': copy.deepcopy(self.plan), 'task': record,
                'diff': describe_changes(self._snapshot, self.plan) if self.plan else [],
                'busy': self.busy, 'provider_alive': self.provider_alive,
                'journal_path': str(self.journal.path) if self.journal else '',
                'experiment': self.workflow.state(),
                'recovery': copy.deepcopy(self._recovery_policy),
                'evaluation_scope': 'execution_completion_only_not_physics_validation'}

    def _notify(self):
        if not self._closed:
            self.stateChanged.emit(self.state())

    def set_provider(self, provider):
        if self.busy:
            raise PlanError('agent.busy')
        self.provider = provider

    def _identity(self):
        return {'snapshot_fingerprint': snapshot_fingerprint(self.workflow.session.current()),
                'revision': self.workflow.session.revision, 'session_id': self._owner_id}

    def _assert_current(self):
        if (self.workflow.session.revision != self._revision or
                snapshot_fingerprint(self.workflow.session.current()) != self._fingerprint):
            raise PlanError('agent.inputs_changed')

    def start(self, prompt, authorization, *, auto_apply=False, auto_run=False, write_scope=None):
        if self._closed or self.busy or self.workflow.busy:
            raise PlanError('agent.busy')
        if self.journal is not None and self.journal.state not in TERMINAL and not self._recovered:
            raise PlanError('agent.cancel_or_finish_current_task')
        if self.provider is None:
            raise PlanError('agent.provider_required')
        if 'plan' not in authorization.get('allowed_actions', []):
            raise PlanError('agent.action_not_authorized')
        if self.journal is not None:
            self.journal.close()
        snapshot = self.workflow.session.current()
        # Only a data-only projection leaves the workstation.
        messages = planner_messages(prompt, snapshot, max_events=authorization['max_events'])
        identity = self._identity()
        journal = TaskJournal.create(self.tasks_root, prompt, authorization, identity)
        try:
            operation = journal.record_intent('plan', {'revision': identity['revision'],
                                                      'snapshot_fingerprint': identity['snapshot_fingerprint']})
        except Exception:
            journal.close()
            raise
        self.journal, self._snapshot = journal, snapshot
        self._fingerprint, self._revision = identity['snapshot_fingerprint'], identity['revision']
        self._authorization = copy.deepcopy(authorization)
        self._recovered, self._recovery_policy = False, None
        self._auto_run, self._auto_apply = bool(auto_run), bool(auto_apply)
        self._write_scope = copy.deepcopy(write_scope)
        self.plan = None
        self._fatal_reason = None
        self._operation, self._bound_record = operation, None
        self._steps, self._destination = [], None
        self._serial += 1
        self._scheduled_serial = None
        serial = self._serial
        self._event = threading.Event()
        event, provider = self._event, self.provider
        self._started = time.monotonic()
        self._timer.start()

        def work():
            try:
                reply, error = provider(messages, cancel_event=event), None
            except Exception as caught:
                reply, error = None, caught
            try:
                self._providerDelivered.emit(serial, reply, error)
            except RuntimeError:
                pass  # Closed QObject; never touch the workspace from this thread.

        self._thread = threading.Thread(target=work, name='g4usim-agent-provider', daemon=True)
        self._thread.start()
        self._notify()

    def _planned(self, serial, reply, error):
        if serial != self._serial:
            return
        self._thread = None  # Provider work is finished; only queued owner publication remains.
        try:
            if self.journal.state in TERMINAL or self._fatal_reason:
                self.journal.record_result(self._operation, {'status': 'cancelled', 'reason': 'agent.cancelled'})
                self._operation = None
                self._notify()
                self._release_closed_journal()
                return
            if error is not None:
                raise error
            self._assert_current()
            content = reply if type(reply) is str else reply.text
            plan = parse_plan(content, self._snapshot, max_events=self._authorization['max_events'])
            if self._write_scope is not None:
                enforce_scope(plan, self._write_scope)
            self.journal.set_plan(plan)
            self.journal.record_result(self._operation, {'status': 'passed', 'reason': 'agent.plan_received'})
            self._operation = None
            self.plan = plan
            if plan['clarifications']:
                self.journal.transition('needs_clarification', reason='agent.clarification_required')
            elif (not self._auto_apply or self._write_scope is None or requires_review(plan)
                  or 'apply' not in self._authorization['allowed_actions']):
                self.journal.transition('awaiting_approval', reason='agent.review_difference')
            else:
                self.approve_plan()
            self._notify()
        except Exception as caught:
            self._fail(caught)

    def approve_plan(self):
        if self._steps or self._scheduled_serial == self._serial:
            return False  # The displayed approval has already been consumed.
        if self.workflow.busy:
            raise PlanError('agent.busy')
        if (self.plan is None or self.plan['clarifications'] or self.busy or self._closed or self._fatal_reason
                or self.journal is None or self.journal.state not in {'planned', 'awaiting_approval'}):
            raise PlanError('agent.review_difference')
        self._assert_current()
        if 'apply' not in self._authorization['allowed_actions']:
            raise PlanError('agent.action_not_authorized')
        self._steps = ['apply', 'validate', 'initialize', 'generate', 'run', 'evaluate']
        self._queue_next()
        return True

    def approve_with_authorization(self, authorization, *, auto_run=False, write_scope=None):
        """A new user grant for this exact reviewed plan, without another model call."""
        if self._steps or self._scheduled_serial == self._serial:
            return False
        if self.workflow.busy:
            raise PlanError('agent.busy')
        if (self._closed or self._recovered or self._fatal_reason or self.busy or self.plan is None or self.plan['clarifications']
                or self.journal.state != 'awaiting_approval'):
            raise PlanError('agent.review_difference')
        self._assert_current()
        if 'apply' not in authorization.get('allowed_actions', []):
            raise PlanError('agent.action_not_authorized')
        if write_scope is not None:
            enforce_scope(self.plan, write_scope)
        build_candidate(self._snapshot, self.plan, max_events=authorization['max_events'])
        old = self.journal
        journal = TaskJournal.create(self.tasks_root, old.to_dict()['prompt'], authorization, self._identity())
        try:
            journal.set_plan(self.plan)
            journal.transition('awaiting_approval', reason='agent.reviewed_from:' + old.task_id)
            old.cancel()
        except Exception:
            journal.close()
            raise
        old.close()
        self._timer.stop()
        self.journal = journal
        self._authorization = copy.deepcopy(authorization)
        self._write_scope = copy.deepcopy(write_scope)
        self._auto_run = bool(auto_run)
        self._serial += 1
        self._scheduled_serial = None
        self._event = threading.Event()
        self._started = time.monotonic()
        self._timer.start()
        self.approve_plan()
        self._notify()
        return True

    def continue_run(self):
        if (self._fatal_reason or self.journal is None or self.journal.state != 'awaiting_approval'
                or not self._steps or self._steps[0] != 'run'):
            raise PlanError('agent.run_not_waiting')
        if 'run' not in self._authorization['allowed_actions']:
            raise PlanError('agent.action_not_authorized')
        self._auto_run = True
        self._queue_next()

    def _queue_next(self):
        serial = self._serial
        if self._scheduled_serial == serial:
            return
        self._scheduled_serial = serial
        def dispatch():
            if self._scheduled_serial == serial:
                self._scheduled_serial = None
            self._next(serial)
        QTimer.singleShot(0, dispatch)

    def _next(self, serial):
        if (self._closed or self._recovered or serial != self._serial or
                self.journal.state in TERMINAL or self._fatal_reason):
            return
        try:
            self._assert_current()
            if not self._steps:
                self._timer.stop()
                self.journal.transition('awaiting_confirmation', reason='agent.review_evidence')
                self._notify()
                return
            action = self._steps[0]
            if action not in self._authorization['allowed_actions'] or action == 'run' and not self._auto_run:
                self.journal.transition('awaiting_approval', reason='agent.action_not_authorized')
                self._notify()
                return
            if self.workflow.busy:
                raise PlanError('agent.experiment_busy')
            binding = {'revision': self._revision, 'snapshot_fingerprint': self._fingerprint}
            if action == 'run':
                binding['events'] = self.workflow.session.current().project.runSettings.beam_on
            if action == 'evaluate':
                self._evaluate_completion(binding)
                return
            operation = self.journal.record_intent(action, binding)
            self._operation = operation
            self.journal.transition(STAGES[action])
            if action == 'apply':
                candidate = build_candidate(self._snapshot, self.plan, max_events=self._authorization['max_events'])
                record = self.workflow.apply(candidate, label='Apply agent configuration', expected_revision=self._revision)
            elif action == 'validate':
                record = self.workflow.validate('fields', expected_revision=self._revision)
            elif action == 'initialize':
                record = self.workflow.validate('initialization', expected_revision=self._revision)
            elif action == 'export':
                record = self.workflow.export(self._destination, expected_revision=self._revision)
            else:
                record = getattr(self.workflow, action)(expected_revision=self._revision)
            self._bound_record = record['record_id']
            self.journal.record_binding(operation, {'record_id': record['record_id'], 'run_id': record['run_id']})
            self._notify()
        except Exception as caught:
            self._fail(caught)

    def _evaluate_completion(self, binding):
        """Read the bound K1 outcome, without creating a physics comparison."""
        operations = self.journal.to_dict()['operations']
        run = next((op for op in reversed(operations) if op['action'] == 'run'), None)
        if run is None:
            raise PlanError('agent.current_run_required')
        identifier = run['binding'].get('record_id')
        record = next((r for r in self.workflow.records() if r.get('record_id') == identifier), None)
        if (record is None or record.get('status') != 'passed' or record.get('stale') or
                record.get('revision') != self._revision or record.get('run_id') != run['binding'].get('run_id')):
            raise PlanError('agent.current_run_required')
        binding.update(record_id=record['record_id'], run_id=record['run_id'])
        operation = self.journal.record_intent('evaluate', binding)
        self.journal.record_result(operation, {'status': 'passed', 'reason': 'agent.execution_completion_only',
                                             'record_id': record['record_id'], 'run_id': record['run_id'],
                                             'revision': self._revision, 'level': 'execution'})
        self._steps.pop(0)
        self._notify()
        self._queue_next()

    def _completed(self, record):
        if record.get('record_id') != self._bound_record:
            return
        self._cancel_timer.stop()
        self._cancel_binding = None
        try:
            action = self._steps[0]
            facts = {key: record[key] for key in ('status', 'reason', 'run_id', 'record_id', 'revision', 'stale', 'level')
                     if key in record}
            if action == 'run':
                result = record.get('result')
                observed = result.get('completed_events') if type(result) is dict else None
                if type(observed) is int and observed >= 0:
                    facts['events'] = observed
            operation = self._operation
            # The observed owner is drained even if recording that fact fails.
            self._operation, self._bound_record = None, None
            self.journal.record_result(operation, facts)
            if self.journal.state in TERMINAL or self._fatal_reason:
                self._notify()
                self._release_closed_journal()
                return
            if record.get('status') != 'passed' or record.get('stale'):
                self._fail(PlanError('agent.experiment_action_failed'))
                return
            if action == 'apply':
                self._revision = self.workflow.session.revision
                self._fingerprint = snapshot_fingerprint(self.workflow.session.current())
                expected = build_candidate(self._snapshot, self.plan, max_events=self._authorization['max_events'])
                if self._fingerprint != snapshot_fingerprint(expected):
                    raise PlanError('agent.applied_projection_changed')
            else:
                self._assert_current()
            self._steps.pop(0)
            if action == 'export':
                self.journal.transition('completed', reason='agent.confirmed_export')
                self._timer.stop()
                self._notify()
            else:
                self._queue_next()
        except Exception as caught:
            self._fail(caught)

    def confirm(self, destination=None):
        if self._scheduled_serial == self._serial:
            return False
        if (self._recovered or self._fatal_reason or self.journal is None
                or self.journal.state != 'awaiting_confirmation' or self.busy):
            raise PlanError('agent.confirmation_not_waiting')
        self._assert_current()
        if destination is None:
            self.journal.transition('completed', reason='agent.confirmed')
            self._timer.stop()
            self._notify()
            return
        if 'export' not in self._authorization['allowed_actions']:
            raise PlanError('agent.action_not_authorized')
        self._destination = Path(destination)
        self._steps = ['export']
        self._queue_next()

    def recover(self, path):
        if self.busy or self.workflow.busy:
            raise PlanError('agent.busy')
        if self.journal is not None:
            if self.journal.state not in TERMINAL and not self._recovered:
                raise PlanError('agent.cancel_or_finish_current_task')
            self.journal.close()
        self._serial += 1
        self._scheduled_serial = None
        journal = TaskJournal.load(path)
        self.journal = journal
        self.plan = None
        self._fatal_reason = None
        self._operation, self._bound_record, self._steps = None, None, []
        self._authorization = {}  # A saved authorization never grants new execution.
        policy = journal.resume_policy()
        self._timer.stop()
        self._recovered = True
        policy['queries'] = []
        records = self.workflow.records()
        for operation in policy['in_flight']:
            binding = operation['binding']
            expected_action = {'initialize': 'validate', 'evaluate': 'run'}.get(operation['action'], operation['action'])
            matches = [r for r in records if binding.get('record_id') == r.get('record_id') and
                       binding.get('run_id') == r.get('run_id') and r.get('action') == expected_action]
            query = {'operation_id': operation['operation_id'], 'status': 'unobserved'}
            if len(matches) == 1:
                record = matches[0]
                query.update(status='in_progress' if record.get('status') == 'pending' else 'historical',
                             record_id=record['record_id'], run_id=record['run_id'],
                             record_status=record.get('status'), current_qualification=False)
                if record.get('status') != 'pending':
                    facts = {k: record[k] for k in ('status', 'reason', 'run_id', 'record_id', 'revision', 'stale', 'level') if k in record}
                    observed = (record.get('result') or {}).get('completed_events')
                    if operation['action'] == 'run' and type(observed) is int and observed >= 0:
                        facts['events'] = observed
                    try:
                        journal.record_result(operation['operation_id'], facts)
                        query['query_result_persisted'] = True
                    except Exception:
                        # An active owner's OS lease is never taken over by recovery.
                        query['query_result_persisted'] = False
            policy['queries'].append(query)
        self._recovery_policy = policy
        self._notify()
        return policy

    def _deadline(self):
        if self.journal is None or self.journal.state in TERMINAL:
            self._timer.stop()
            return
        if time.monotonic() - self._started >= self._authorization.get('timeout_seconds', 0):
            self._fail(PlanError('agent.task_timeout'))

    def _cancel_owned(self):
        binding = (self._serial, self._bound_record)
        if binding[1] is None:
            return
        try:
            self.workflow.cancel()
        finally:
            # Repeated Cancel must not postpone escalation indefinitely.
            if self._cancel_binding != binding:
                self._cancel_binding = binding
                self._cancel_timer.start()

    def _force_cancel_owned(self):
        binding, self._cancel_binding = self._cancel_binding, None
        if (binding is None or binding != (self._serial, self._bound_record)
                or not self.workflow.busy):
            return
        pending = [r.get('record_id') for r in self.workflow.records() if r.get('status') == 'pending']
        # Loaded history may retain older pending rows; only the newest owner
        # may still correspond to the currently active K1 operation.
        if pending[-1:] != [binding[1]]:
            return
        try:
            self.workflow.cancel(force=True)
        except Exception:
            if self._fatal_reason is None:
                self._fatal_reason = 'agent.owner_cancel_failed'
            self._notify()

    def _fail(self, error):
        self._event.set()
        self._timer.stop()
        reason = str(error) if str(error).startswith(('agent.', 'provider.', 'journal.')) else 'agent.operation_failed'
        self._fatal_reason = reason
        cancel_error = None
        if self._bound_record is not None:
            try:
                self._cancel_owned()
            except Exception as caught:
                cancel_error = caught
        try:
            if self.journal is not None and self.journal.state not in TERMINAL:
                self.journal.transition('failed', reason=reason)
        except Exception:
            self._fatal_reason = 'agent.journal_write_failed'
        if cancel_error is not None and self._fatal_reason is None:
            self._fatal_reason = 'agent.owner_cancel_failed'
        if not self._closed:
            self.errorRaised.emit(self._fatal_reason)
            self._notify()
        self._release_closed_journal()

    def cancel(self):
        self._event.set()
        self._timer.stop()
        journal_error = None
        try:
            if self.journal is not None and self.journal.state not in TERMINAL:
                self.journal.cancel()
        except Exception as caught:
            journal_error = caught
            self._fatal_reason = 'agent.journal_write_failed'
        finally:
            if self._bound_record is not None:
                try:
                    self._cancel_owned()
                except Exception:
                    if journal_error is None:
                        self._fatal_reason = 'agent.owner_cancel_failed'
        self._steps = [] if self._bound_record is None else self._steps
        self._notify()
        if self._fatal_reason and not self._closed:
            self.errorRaised.emit(self._fatal_reason)

    def close(self):
        if self._closed:
            return
        try:
            self.cancel()
        finally:
            self._closed = True
            self._event.set()
            self._timer.stop()
            self._release_closed_journal()

    def _release_closed_journal(self):
        if self._closed and not self.busy and self.journal is not None:
            self.journal.close()
