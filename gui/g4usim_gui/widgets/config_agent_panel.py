"""Configuration-agent presentation and intent collection; the parent owns work.

No project, runner, provider client, credential storage or execution lives here.
Only explicit controller tokens enable actions or describe K1 evidence.
"""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QComboBox, QFormLayout, QFrame, QGridLayout,
    QHeaderView, QLabel, QLayout, QLineEdit, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from g4usim_gui.core.accessibility import decorate_accessibility, ensure_focus_visible
from g4usim_gui.core.i18n import ui_format, ui_text


ACTIONS = {
    'plan': 'Create plan', 'apply': 'Apply proposed changes',
    'continue': 'Continue with answer', 'run': 'Run authorized task', 'cancel': 'Cancel',
    'resume': 'Resume task', 'confirm': 'Confirm outcome',
    'export': 'Export agent bundle',
}
TASK_STATUS = {
    'idle': 'Task idle', 'planning': 'Planning changes',
    'awaiting_clarification': 'Waiting for clarification', 'planned': 'Plan ready',
    'applying': 'Applying changes', 'running': 'Task running',
    'paused': 'Task paused', 'awaiting_confirmation': 'Waiting for confirmation',
    'completed': 'Task completed', 'failed': 'Task failed',
    'cancelled': 'Task cancelled',
    'needs_clarification': 'Waiting for clarification',
    'awaiting_approval': 'Waiting for plan approval',
    'validating': 'Validating inputs', 'initializing': 'Checking initialization',
    'generating': 'Generating package', 'evaluating': 'Checking run completion',
    'exporting': 'Exporting bundle', 'interrupted': 'Task interrupted',
}
PERMISSIONS = {
    'plan': 'Allow planning', 'apply': 'Allow applying changes',
    'validate': 'Allow field validation', 'initialize': 'Allow initialization',
    'generate': 'Allow package generation', 'run': 'Allow a small run',
    'evaluate': 'Allow completion evaluation', 'export': 'Allow bundle export',
    'resume': 'Allow task continuation',
}
LEVELS = {
    'fields': 'Fields and dependencies', 'initialization': 'Backend initialization',
    'execution': 'Event completion', 'physics': 'Physics comparison',
}
EVIDENCE_STATUS = {
    'unverified': 'Unverified', 'passed': 'Passed', 'failed': 'Failed',
    'stale': 'Stale', 'unobserved': 'Unobserved', 'cancelled': 'Cancelled',
    'pending': 'In progress',
}
EVALUATION_NOTE = (
    'Default evaluation checks only completion of the small run for these inputs. '
    'Physics comparison requires an explicit existing K1 reference.'
)
AUTO_APPLY_TEXT = 'Automatically modify controlled fields in the current project'
AUTO_APPLY_NOTE = (
    'The controller derives the write scope from the actual current project, never from model text. '
    'Without an explicit scope the diff requires review. Physics-list changes always require review.'
)
CONTROLLED_FIELDS = (
    'Controlled fields: volume.material/size/position/rotation/sensitive; '
    'source.particle/energy/position/direction; run.beam_on/threads/seed; '
    'physics.reference_list/default_cut (review required); scoring.hits/event_edep/edep/dose/fluence.'
)
STATE_KEYS = frozenset((
    'task_id', 'status', 'goal', 'summary', 'diff', 'questions', 'budget',
    'steps', 'evidence', 'confirmation', 'allowed_actions', 'connection',
))
SECRET_KEYS = frozenset(('credential', 'api_key', 'apikey', 'password', 'secret', 'token'))


def _copy_display(value: Any) -> Any:
    """Copy only display primitives; never retain a credential field or owner."""
    if isinstance(value, dict):
        return {k: _copy_display(v) for k, v in value.items()
                if isinstance(k, str) and k.lower() not in SECRET_KEYS}
    if isinstance(value, (list, tuple)):
        return [_copy_display(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def _text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _evidence_status(value: Any) -> str:
    return ui_text(EVIDENCE_STATUS.get(value, 'Unobserved') if isinstance(value, str) else 'Unobserved')


class ConfigAgentPanel(QWidget):
    """Render controller snapshots and emit intent; no action implies execution.

    submitRequested: prompt, authorization={allowed_actions,max_calls,max_events,
      timeout_seconds}, auto_apply/auto_run, evaluation_scope='input_run_completion'.
    providerChanged: provider/url/model/auth_mode/credential_id/credential, only on explicit Apply;
      the Password field is cleared BEFORE emission and is never in _state.
    actionRequested: plan/apply/continue/run/cancel/resume/confirm/export.
      For continue the controller reads clarification_response().
    set_state replaces all display sections; allowed_actions defaults to empty.
    """

    submitRequested = Signal(dict)
    actionRequested = Signal(str)
    providerChanged = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: dict[str, Any] = {}
        self._busy = False
        self._labels: list[tuple[QLabel, str]] = []
        self._names: list[tuple[QWidget, str]] = []
        self._columns = 0
        self._build_ui()
        self.retranslate_ui()

    def _label(self, source: str, parent: QWidget | None = None) -> QLabel:
        label = QLabel(parent or self)
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._labels.append((label, source))
        return label

    def _name(self, field: QWidget, source: str) -> None:
        self._names.append((field, source))

    def _field(self, form: QFormLayout, source: str, field: QWidget) -> None:
        label = self._label(source)
        label.setBuddy(field)
        self._name(field, source)
        form.addRow(label, field)

    def _readout(self, source: str) -> QPlainTextEdit:
        field = QPlainTextEdit(self)
        field.setReadOnly(True)
        field.setTabChangesFocus(True)
        field.setMinimumWidth(0)
        self._name(field, source)
        return field

    def _table(self, source: str, columns: int) -> QTableWidget:
        table = QTableWidget(0, columns, self)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.setMinimumWidth(0)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().hide()
        self._name(table, source)
        return table

    def _build_ui(self) -> None:
        self.setObjectName('configAgentPanel')
        self._name(self, 'Configuration Agent')
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        # A previous wide button grid must not pin the dock's next minimum width.
        # Resize reflows the fixed action bar; the details already scroll.
        root.setSizeConstraint(QLayout.SetNoConstraint)
        self.title_label = self._label('Configuration Agent')
        self.status_label = self._label('Unobserved')
        self._name(self.status_label, 'Agent task status')
        root.addWidget(self.title_label)
        root.addWidget(self.status_label)
        self.evaluation_note = self._label(EVALUATION_NOTE)
        root.addWidget(self.evaluation_note)

        self.content_scroll = QScrollArea(self)
        self.content_scroll.setFrameShape(QFrame.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setMinimumWidth(0)
        content = QWidget()
        self.content_scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        root.addWidget(self.content_scroll, 1)

        goal_form = QFormLayout()
        goal_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.prompt_edit = QPlainTextEdit(content)
        self.prompt_edit.setObjectName('agentPrompt')
        self.prompt_edit.setTabChangesFocus(True)
        self.prompt_edit.setMinimumHeight(70)
        self.prompt_edit.setMaximumHeight(110)
        self._field(goal_form, 'Natural-language goal', self.prompt_edit)
        layout.addLayout(goal_form)

        layout.addWidget(self._label('Permissions apply only to a newly submitted task; they do not authorize an existing journal.'))
        self._grant_grid = QGridLayout()
        self.permission_boxes = {token: QCheckBox(content) for token in PERMISSIONS}
        self.permission_boxes['plan'].setChecked(True)
        self.allow_apply = self.permission_boxes['apply']
        self.allow_run = self.permission_boxes['run']
        self.allow_export = self.permission_boxes['export']
        self._grant_boxes = tuple((self.permission_boxes[token], source) for token, source in PERMISSIONS.items())
        for box, source in self._grant_boxes:
            self._name(box, source)
            box.toggled.connect(self._update_enabled)
        layout.addLayout(self._grant_grid)
        self.auto_apply = QCheckBox(content)
        self.auto_run = QCheckBox(content)
        self._name(self.auto_apply, AUTO_APPLY_TEXT)
        self._name(self.auto_run, 'Run immediately after review (within authorization)')
        layout.addWidget(self.auto_apply)
        layout.addWidget(self.auto_run)
        budgets = QFormLayout()
        budgets.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.max_calls = QSpinBox(content)
        self.max_events = QSpinBox(content)
        self.timeout = QSpinBox(content)
        for field, value, source in (
            (self.max_calls, 16, 'Maximum action calls'),
            (self.max_events, 100, 'Maximum run events'),
            (self.timeout, 300, 'Task timeout (seconds)'),
        ):
            field.setRange(0 if field is self.max_events else 1,
                           32 if field is self.max_calls else 100000 if field is self.max_events else 3600)
            field.setValue(value)
            self._field(budgets, source, field)
        layout.addLayout(budgets)

        self.provider_toggle = QToolButton(content)
        self.provider_toggle.setCheckable(True)
        self.provider_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.provider_toggle.setArrowType(Qt.RightArrow)
        self._name(self.provider_toggle, 'Connection settings')
        layout.addWidget(self.provider_toggle)
        self.provider_fields = QWidget(content)
        provider_form = QFormLayout(self.provider_fields)
        provider_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.provider_edit = QComboBox(self.provider_fields)
        self.provider_edit.addItem('', 'openai_compatible')
        self.provider_edit.addItem('', 'local')
        self.url_edit = QLineEdit(self.provider_fields)
        self.model_edit = QLineEdit(self.provider_fields)
        self.auth_mode_edit = QComboBox(self.provider_fields)
        for token in ('none', 'session', 'system'):
            self.auth_mode_edit.addItem('', token)
        self.credential_id_edit = QLineEdit('l1-default', self.provider_fields)
        self.credential_edit = QLineEdit(self.provider_fields)
        self.credential_edit.setObjectName('agentEphemeralCredential')
        self.credential_edit.setEchoMode(QLineEdit.Password)
        self.credential_edit.setInputMethodHints(Qt.ImhHiddenText | Qt.ImhNoPredictiveText)
        for source, field in (
            ('Provider', self.provider_edit), ('API endpoint URL', self.url_edit),
            ('Model ID', self.model_edit), ('Credential storage', self.auth_mode_edit),
            ('Credential reference ID', self.credential_id_edit),
            ('Credential (this transfer only)', self.credential_edit),
        ):
            self._field(provider_form, source, field)
        self.provider_apply_button = QPushButton(self.provider_fields)
        self._name(self.provider_apply_button, 'Use connection settings')
        provider_form.addRow(self.provider_apply_button)
        provider_form.addRow(self._label('The credential is cleared before transfer and is never restored by this panel.'))
        provider_form.addRow(self._label('System storage is managed by the controller. If unavailable, report failure; never fall back to a credential file.'))
        self.provider_fields.hide()
        layout.addWidget(self.provider_fields)

        self.tabs = QTabWidget(content)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setMinimumHeight(230)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._name(self.tabs, 'Agent task details')
        self.summary_view = self._readout('Controller goal and budget')
        self.diff_table = self._table('Proposed configuration changes', 6)
        self.steps_table = self._table('Agent step records', 6)
        self.evidence_table = self._table('Original K1 evidence', 4)
        self.confirmation_view = self._readout('Confirmation and export details')
        self.questions_view = self._readout('Clarification questions')
        self.response_edit = QPlainTextEdit(content)
        self.response_edit.setTabChangesFocus(True)
        self.response_edit.setMaximumHeight(90)
        self._name(self.response_edit, 'Clarification answer')
        questions_page = QWidget(content)
        qlayout = QFormLayout(questions_page)
        qlayout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        qlayout.addRow(self.questions_view)
        self._field(qlayout, 'Clarification answer', self.response_edit)
        self._tab_sources = (
            (self.summary_view, 'Goal and budget'), (self.diff_table, 'Proposed changes'),
            (questions_page, 'Clarification'), (self.steps_table, 'Step records'),
            (self.evidence_table, 'K1 evidence'), (self.confirmation_view, 'Confirmation and export'),
        )
        for page, _ in self._tab_sources:
            self.tabs.addTab(page, '')
        layout.addWidget(self.tabs, 1)

        # The action bar is outside the scroll area: long details cannot push it away.
        self._actions_layout = QGridLayout()
        root.addLayout(self._actions_layout)
        self.submit_button = QPushButton(self)
        self._name(self.submit_button, 'Submit goal')
        self.action_buttons: dict[str, QPushButton] = {}
        for token, source in ACTIONS.items():
            button = QPushButton(self)
            button.setObjectName('agentAction_'+token)
            self._name(button, source)
            button.clicked.connect(lambda _checked=False, t=token: self._request_action(t))
            self.action_buttons[token] = button
        self.keyboard_note = self._label('Ctrl+Enter submits. Use Tab and Space for actions.')
        root.addWidget(self.keyboard_note)

        self.submit_button.clicked.connect(self._submit)
        self.prompt_edit.textChanged.connect(self._update_enabled)
        self.provider_apply_button.clicked.connect(self._provider_changed)
        self.provider_toggle.toggled.connect(self._toggle_provider)
        self.auth_mode_edit.currentIndexChanged.connect(self._credential_mode_changed)
        self.submit_shortcut = QShortcut(QKeySequence('Ctrl+Return'), self)
        self.submit_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.submit_shortcut.activated.connect(self._submit)
        QApplication.instance().focusChanged.connect(self._focus_changed)

    def _focus_changed(self, _old, current) -> None:
        if current is not None and self.isAncestorOf(current):
            ensure_focus_visible(current)

    def _toggle_provider(self, checked: bool) -> None:
        self.provider_fields.setVisible(checked)
        self.provider_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        if not checked:
            self.credential_edit.clear()

    def _submit(self) -> None:
        if self._busy or not self.prompt_edit.toPlainText().strip():
            return
        self.submitRequested.emit({
            'prompt': self.prompt_edit.toPlainText(),
            'authorization': {
                'allowed_actions': [token for token, box in self.permission_boxes.items() if box.isChecked()],
                'max_calls': self.max_calls.value(), 'max_events': self.max_events.value(),
                'timeout_seconds': self.timeout.value(),
            },
            'auto_apply': self.allow_apply.isChecked() and self.auto_apply.isChecked(),
            'auto_run': self.allow_run.isChecked() and self.auto_run.isChecked(),
            'evaluation_scope': 'input_run_completion',
        })

    def _provider_changed(self) -> None:
        if self._busy:
            return
        settings = {'provider': self.provider_edit.currentData(),
                    'url': self.url_edit.text(), 'model': self.model_edit.text(),
                    'auth_mode': self.auth_mode_edit.currentData(),
                    'credential_id': self.credential_id_edit.text(),
                    'credential': self.credential_edit.text() if self.auth_mode_edit.currentData() != 'none' else ''}
        self.credential_edit.clear()
        self.providerChanged.emit(settings)

    def _credential_mode_changed(self, _index: int = -1) -> None:
        authenticated = self.auth_mode_edit.currentData() in ('session', 'system')
        if not authenticated:
            self.credential_edit.clear()
        self.credential_edit.setEnabled(not self._busy and authenticated)

    def _request_action(self, token: str) -> None:
        if self._action_enabled(token):
            self.actionRequested.emit(token)

    def _action_enabled(self, token: str) -> bool:
        allowed = self._state.get('allowed_actions', [])
        return token in ACTIONS and isinstance(allowed, list) and token in allowed and (not self._busy or token == 'cancel')

    def _update_enabled(self) -> None:
        self.submit_button.setEnabled(not self._busy and bool(self.prompt_edit.toPlainText().strip()))
        for token, button in self.action_buttons.items():
            button.setEnabled(self._action_enabled(token))
        for widget in (self.prompt_edit, *self.permission_boxes.values(),
                       self.max_calls, self.max_events, self.timeout, self.provider_fields,
                       self.response_edit):
            widget.setEnabled(not self._busy)
        self.auto_apply.setEnabled(not self._busy and self.allow_apply.isChecked())
        self.auto_run.setEnabled(not self._busy and self.allow_run.isChecked())
        self._credential_mode_changed()

    def clarification_response(self) -> str:
        return self.response_edit.toPlainText()

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        if self._busy:
            self.credential_edit.clear()
        self._update_enabled()

    def set_state(self, state: dict) -> None:
        previous_questions = self._state.get('questions')
        self._state = {key: _copy_display(value) for key, value in state.items() if key in STATE_KEYS} if isinstance(state, dict) else {}
        if previous_questions != self._state.get('questions'):
            self.response_edit.clear()
        connection = self._state.get('connection')
        if isinstance(connection, dict):
            token = connection.get('provider')
            index = self.provider_edit.findData(token)
            if index >= 0:
                self.provider_edit.setCurrentIndex(index)
            auth_index = self.auth_mode_edit.findData(connection.get('auth_mode'))
            if auth_index >= 0:
                self.auth_mode_edit.setCurrentIndex(auth_index)
            for field, key in ((self.url_edit, 'url'), (self.model_edit, 'model'),
                               (self.credential_id_edit, 'credential_id')):
                if key in connection:
                    field.setText(_text(connection[key]))
        self._render_state()
        self._update_enabled()

    def _rows(self, table: QTableWidget, rows: list[list[Any]]) -> None:
        table.setRowCount(len(rows))
        for r, cells in enumerate(rows):
            for c, value in enumerate(cells):
                item = QTableWidgetItem(_text(value))
                item.setToolTip(_text(value))
                table.setItem(r, c, item)

    def _render_state(self) -> None:
        state = self._state
        status = state.get('status')
        self.status_label.setText(ui_text(TASK_STATUS.get(status, 'Unobserved') if isinstance(status, str) else 'Unobserved'))
        budget = state.get('budget') if isinstance(state.get('budget'), dict) else {}
        unknown = ui_text('Unobserved')
        self.summary_view.setPlainText('\n'.join((
            ui_format('Task ID: {value}', value=_text(state.get('task_id')) or unknown),
            ui_format('Controller goal: {value}', value=_text(state.get('goal'))),
            ui_format('Plan summary: {value}', value=_text(state.get('summary'))),
            ui_format('Action calls: {used} / {limit}', used=_text(budget.get('calls_used')) or unknown, limit=_text(budget.get('max_calls')) or unknown),
            ui_format('Run events: {used} / {limit}', used=_text(budget.get('events_used')) or unknown, limit=_text(budget.get('max_events')) or unknown),
            ui_format('Elapsed seconds: {used} / {limit}', used=_text(budget.get('elapsed_seconds')) or unknown, limit=_text(budget.get('timeout_seconds')) or unknown),
        )))
        changes = state.get('diff') if isinstance(state.get('diff'), list) else []
        self._rows(self.diff_table, [[x.get('domain'), x.get('target'), x.get('field'), x.get('before'), x.get('after'), x.get('reason')]
                                    for x in changes if isinstance(x, dict)])
        questions = state.get('questions') if isinstance(state.get('questions'), list) else []
        self.questions_view.setPlainText('\n\n'.join(_text(x.get('question')) if isinstance(x, dict) else _text(x) for x in questions) or ui_text('No clarification supplied by the controller.'))
        steps = state.get('steps') if isinstance(state.get('steps'), list) else []
        self._rows(self.steps_table, [[x.get('step'), x.get('action'), _evidence_status(x.get('status')), x.get('record_id'), x.get('run_id'), x.get('detail')]
                                     for x in steps if isinstance(x, dict)])
        evidence = state.get('evidence') if isinstance(state.get('evidence'), dict) else {}
        rows = []
        for level, source in LEVELS.items():
            entry = evidence.get(level) if isinstance(evidence.get(level), dict) else {}
            rows.append([ui_text(source), _evidence_status(entry.get('status')), entry.get('record_id'), entry.get('detail')])
        self._rows(self.evidence_table, rows)
        confirmation = state.get('confirmation')
        if isinstance(confirmation, dict):
            text = '\n'.join(_text(confirmation.get(key)) for key in ('message', 'export_path') if confirmation.get(key))
        else:
            text = _text(confirmation)
        self.confirmation_view.setPlainText(text or ui_text('No confirmation or export supplied by the controller.'))

    def _reflow(self) -> None:
        if not hasattr(self, '_actions_layout'):
            return
        buttons = [self.submit_button, *self.action_buttons.values()]
        hint = max(button.sizeHint().width() for button in buttons) + self._actions_layout.spacing()
        columns = max(1, min(4, max(1, self.width()-16) // max(1, hint)))
        if columns != self._columns:
            while self._actions_layout.count():
                self._actions_layout.takeAt(0)
            for i, button in enumerate(buttons):
                self._actions_layout.addWidget(button, i//columns, i%columns)
            self._columns = columns
        while self._grant_grid.count():
            self._grant_grid.takeAt(0)
        grant_columns = 3 if self.width() >= 620 else 1
        for i, (box, _) in enumerate(self._grant_boxes):
            self._grant_grid.addWidget(box, i//grant_columns, i%grant_columns)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(0, max(0, hint.height()))

    def hideEvent(self, event) -> None:
        self.credential_edit.clear()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self.credential_edit.clear()
        super().closeEvent(event)

    def retranslate_ui(self) -> None:
        self.setAccessibleDescription(ui_text(EVALUATION_NOTE))
        for label, source in self._labels:
            label.setText(ui_text(source))
        for widget, source in self._names:
            widget.setAccessibleName(ui_text(source))
        for box, source in self._grant_boxes:
            box.setText(ui_text(source))
        self.auto_apply.setText(ui_text(AUTO_APPLY_TEXT))
        self.auto_apply.setToolTip(ui_text(AUTO_APPLY_NOTE)+'\n'+ui_text(CONTROLLED_FIELDS))
        self.auto_run.setText(ui_text('Run immediately after review (within authorization)'))
        self.submit_button.setText(ui_text('Submit goal'))
        for token, button in self.action_buttons.items():
            button.setText(ui_text(ACTIONS[token]))
            button.setToolTip(ui_text('Only the controller enables this action for the active task.'))
        self.provider_toggle.setText(ui_text('Connection settings'))
        self.provider_edit.setItemText(0, ui_text('OpenAI-compatible API'))
        self.provider_edit.setItemText(1, ui_text('Local endpoint'))
        for i, source in enumerate(('No authentication', 'This session only', 'System credential store')):
            self.auth_mode_edit.setItemText(i, ui_text(source))
        self.provider_apply_button.setText(ui_text('Use connection settings'))
        for i, (_, source) in enumerate(self._tab_sources):
            self.tabs.setTabText(i, ui_text(source))
        for table, headers in (
            (self.diff_table, ('Domain', 'Target', 'Field', 'Before', 'After', 'Reason')),
            (self.steps_table, ('Step', 'Action', 'Status', 'Record ID', 'Run ID', 'Detail')),
            (self.evidence_table, ('Evidence layer', 'Status', 'Record ID', 'Detail')),
        ):
            table.setHorizontalHeaderLabels([ui_text(x) for x in headers])
        self.prompt_edit.setPlaceholderText(ui_text('Describe the configuration goal; identify the target and units.'))
        self.response_edit.setPlaceholderText(ui_text('Answer the controller clarification, then continue.'))
        self._render_state()
        decorate_accessibility(self)
        self._reflow()
        self._update_enabled()
