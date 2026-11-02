"""Desktop connection and display adapter for the L1 configuration agent."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import time

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtWidgets import QFileDialog, QInputDialog

from g4usim_gui.agent.actions import FIELDS, PlanError, planning_context
from g4usim_gui.agent.controller import AgentController, TERMINAL
from g4usim_gui.agent.credentials import CredentialStore
from g4usim_gui.agent.provider import ProviderClient, ProviderConfig
from g4usim_gui.core.i18n import ui_text


class ConfigAgentMixin:
    def _setup_config_agent(self):
        self._agent_credentials = CredentialStore()
        self._agent_connection = {}
        self._agent_last_request = None
        root = self._recovery_root or QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
        self.agent_controller = AgentController(self.experiment, tasks_root=Path(root) / 'config-agent-tasks', parent=self)
        self.agent_controller.stateChanged.connect(self._render_agent_state)
        self.agent_controller.errorRaised.connect(self._agent_error)
        self.experiment.stateChanged.connect(lambda _: self._render_agent_state())
        panel = self.config_agent_panel
        panel.providerChanged.connect(self._set_agent_provider)
        panel.submitRequested.connect(self._start_agent_task)
        panel.actionRequested.connect(self._agent_action)
        for box in panel.permission_boxes.values():
            box.toggled.connect(lambda _: self._render_agent_state())
        settings = QSettings()
        connection = {key: str(settings.value('configAgent/' + key, ''))
                      for key in ('provider', 'url', 'model', 'auth_mode', 'credential_id')}
        if connection['url'] and connection['model']:
            self._set_agent_provider(connection)
        self._render_agent_state()

    def _agent_error(self, reason):
        self.statusBar().showMessage(ui_text('Agent action could not continue. Review the task record.') + ' ' + reason, 8000)

    def _set_agent_provider(self, values):
        try:
            if self.agent_controller.busy:
                raise PlanError('agent.busy')
            connection = {key: values.get(key, '') for key in ('provider', 'url', 'model', 'auth_mode', 'credential_id')}
            mode = connection['auth_mode'] or ('session' if values.get('credential') else 'none')
            identifier = connection['credential_id'] or ('l1-default' if mode != 'none' else '')
            config = ProviderConfig(base_url=connection['url'], model=connection['model'], auth_mode=mode,
                                    credential_id=identifier, timeout_s=60, connect_timeout_s=10,
                                    max_response_bytes=65536, max_output_tokens=4096)
            secret = values.get('credential', '')
            if secret:
                if any(secret in value for value in connection.values() if type(value) is str):
                    raise PlanError('agent.credential_in_connection')
                if mode == 'none':
                    raise PlanError('agent.credential_storage_required')
                self._agent_credentials.put(identifier, secret, storage=mode)
            client = ProviderClient(config, credentials=self._agent_credentials)
            self.agent_controller.set_provider(client.complete)
            connection.update(auth_mode=mode, credential_id=identifier)
            self._agent_connection = connection
            settings = QSettings()
            for key, value in connection.items():
                settings.setValue('configAgent/' + key, value)
            dock = self.workspace_layout.docks['ai']
            dock.setProperty('workspaceTitle', 'Configuration Agent')
            dock.setWindowTitle(ui_text('Configuration Agent'))
            self._render_agent_state()
        except Exception as error:
            reason = str(error) if str(error).startswith(('agent.', 'provider.', 'credential.')) else 'agent.connection_invalid'
            self._agent_error(reason)

    def _agent_write_scope(self, snapshot):
        context = planning_context(snapshot)
        scope = []
        for domain, collection in (('volume', 'volumes'), ('source', 'sources')):
            for row in context[collection]:
                fields = list(FIELDS[domain])
                if row.get('world'):
                    fields = ['material', 'size']
                scope.append({'domain': domain, 'target': row['name'], 'fields': fields})
        scope.extend({'domain': domain, 'target': '', 'fields': list(FIELDS[domain])}
                     for domain in ('run', 'physics', 'scoring'))
        return scope

    def _start_agent_task(self, request):
        try:
            if not self.can_mutate_workspace('Configuration Agent'):
                return
            self.flush_pending_edit()
            if request.get('evaluation_scope') != 'input_run_completion':
                raise PlanError('agent.explicit_reference_required')
            scope = self._agent_write_scope(self._edit_session.current()) if request.get('auto_apply') else None
            self.agent_controller.start(request['prompt'], request['authorization'],
                                        auto_apply=request.get('auto_apply', False),
                                        auto_run=request.get('auto_run', False), write_scope=scope)
            self._agent_last_request = copy.deepcopy(request)
        except Exception as error:
            self._agent_error(str(error) if str(error).startswith('agent.') else 'agent.request_rejected')
        self._render_agent_state()

    def _agent_current_request(self, prompt=None):
        panel = self.config_agent_panel
        return {'prompt': prompt if prompt is not None else panel.prompt_edit.toPlainText(),
                'authorization': {'allowed_actions': [token for token, box in panel.permission_boxes.items() if box.isChecked()],
                                  'max_calls': panel.max_calls.value(), 'max_events': panel.max_events.value(),
                                  'timeout_seconds': panel.timeout.value()},
                'auto_apply': panel.auto_apply.isChecked() and panel.allow_apply.isChecked(),
                'auto_run': panel.auto_run.isChecked() and panel.allow_run.isChecked(),
                'evaluation_scope': 'input_run_completion'}

    def _agent_action(self, action):
        controller = self.agent_controller
        try:
            if action == 'cancel':
                controller.cancel()
            elif action == 'apply':
                if not self.can_mutate_workspace('Configuration Agent'):
                    return
                self.flush_pending_edit()
                request = self._agent_current_request()
                controller.approve_with_authorization(request['authorization'], auto_run=request['auto_run'])
            elif action == 'run':
                self.flush_pending_edit()
                controller.continue_run()
            elif action == 'confirm':
                self.flush_pending_edit()
                controller.confirm()
            elif action == 'export':
                directory = QFileDialog.getExistingDirectory(self, ui_text('Select export parent directory'))
                if not directory:
                    return
                name, accepted = QInputDialog.getText(self, ui_text('Export bundle'), ui_text('New bundle directory name'))
                if not accepted:
                    return
                if not name or name in {'.', '..'} or any(char in name for char in '/\\:'):
                    raise PlanError('agent.export_name_invalid')
                self.flush_pending_edit()
                controller.confirm(Path(directory) / name)
            elif action == 'resume':
                filename, _ = QFileDialog.getOpenFileName(self, ui_text('Open agent task'), '', 'JSON (*.json)')
                if filename:
                    controller.recover(filename)
            elif action in {'plan', 'continue'}:
                prompt = self.config_agent_panel.prompt_edit.toPlainText()
                if action == 'continue':
                    response = self.config_agent_panel.clarification_response()
                    if not response.strip():
                        raise PlanError('agent.clarification_required')
                    prompt += '\n\n' + response
                if (controller.journal is not None and controller.journal.state not in TERMINAL
                        and not controller._recovered):
                    controller.cancel()
                self._start_agent_task(self._agent_current_request(prompt))
        except Exception as error:
            self._agent_error(str(error) if str(error).startswith('agent.') else 'agent.action_failed')
        self._render_agent_state()

    def _render_agent_state(self, state=None):
        controller = getattr(self, 'agent_controller', None)
        if controller is None:
            return
        state = state if isinstance(state, dict) and 'task' in state else controller.state()
        task, plan = state.get('task', {}), state.get('plan') or {}
        auth, usage = task.get('authorization', {}), task.get('usage', {})
        operations = task.get('operations', [])
        records = {r['record_id']: r for r in self.experiment.records()}
        steps, evidence = [], {}
        for index, op in enumerate(operations):
            result, binding = op.get('result') or {}, op['binding']
            record = records.get(binding.get('record_id'), {})
            steps.append({'step': index + 1, 'action': op['action'], 'status': result.get('status', 'pending'),
                          'record_id': binding.get('record_id', ''), 'run_id': binding.get('run_id', ''),
                          'detail': result.get('reason', '')})
            if record:
                status = 'stale' if record.get('stale') else record.get('status', 'unobserved')
                if status == 'passed' and state['experiment'].get('qualification') == 'checking':
                    status = 'pending'
                evidence[record['level']] = {'status': status, 'record_id': record['record_id'],
                                            'detail': record.get('reason', '')}
        diff = [dict(change, reason=plan.get('summary', '')) for change in state.get('diff', [])]
        status = state['state']
        allowed = ['resume', 'plan'] if not state['busy'] and status in TERMINAL | {'idle'} else []
        if task and status not in TERMINAL:
            allowed.append('cancel')
        if status == 'needs_clarification':
            allowed.append('continue')
        if status == 'awaiting_approval':
            if controller._steps and controller._steps[0] == 'run':
                if 'run' in auth.get('allowed_actions', []):
                    allowed.append('run')
            elif (not controller._steps and not self.experiment.busy
                  and self.config_agent_panel.allow_apply.isChecked()):
                allowed.append('apply')
        if status == 'awaiting_confirmation':
            allowed.append('confirm')
            if 'export' in auth.get('allowed_actions', []):
                allowed.append('export')
        message = state.get('reason', '')
        if state.get('recovery') is not None:
            message = ui_text('Recovered tasks are read-only. Submit a new authorized request to continue.')
            message += '\n' + json.dumps(state['recovery'].get('queries', []), ensure_ascii=False)
        display = {'task_id': state['task_id'], 'status': status, 'goal': task.get('prompt', ''),
                   'summary': plan.get('summary', ''), 'diff': diff, 'questions': plan.get('clarifications', []),
                   'budget': dict(auth, calls_used=usage.get('calls'), events_used=usage.get('events'),
                                  elapsed_seconds=round(max(0, time.time() - task['created_at']), 1) if task else None),
                   'steps': steps, 'evidence': evidence,
                   'confirmation': {'message': message},
                   'allowed_actions': allowed, 'connection': self._agent_connection}
        self.config_agent_panel.set_state(display)
        self.config_agent_panel.set_busy(state['busy'])

    def _close_config_agent(self):
        controller = getattr(self, 'agent_controller', None)
        if controller is not None:
            controller.close()
        credentials = getattr(self, '_agent_credentials', None)
        if credentials is not None:
            credentials.clear_session()
