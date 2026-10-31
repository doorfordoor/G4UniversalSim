from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QGroupBox, QHeaderView,
    QLabel, QLayout, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text


ACTION_TOKENS = (
    "inspect", "validate", "initialize", "generate", "run", "evaluate",
    "export", "import", "environment", "cancel",
)
LEVEL_TOKENS = ("fields", "initialization", "execution", "physics")
VALID_LEVEL_STATUS_TOKENS = (
    "unverified", "passed", "failed", "stale", "unobserved", "cancelled",
)
# These are source messages for the existing central i18n dictionary, not translations.
ACTION_TEXT = {
    "inspect": "Inspect inputs", "validate": "Validate fields",
    "initialize": "Check initialization", "generate": "Generate package",
    "run": "Run", "evaluate": "Compare physics", "export": "Export bundle",
    "import": "Load bundle", "environment": "Environment", "cancel": "Cancel",
}
LEVEL_TEXT = {
    "fields": "Fields and dependencies", "initialization": "Backend initialization",
    "execution": "Event completion", "physics": "Physics comparison",
}
STATUS_TEXT = {
    "unverified": "Unverified", "passed": "Passed", "failed": "Failed",
    "stale": "Stale", "unobserved": "Unobserved", "cancelled": "Cancelled",
}
EXPORT_NOTE = "Export includes configuration, resources and evidence; excludes C++ projects, secrets and machine settings."


class ExperimentPanel(QWidget):
    """Render a supplied snapshot and emit requests; the controller owns execution.

    State: revision/fingerprint/run_id/status, levels=[{level, status, detail}],
    history=[{level, status, record_id}]. No layer implies any other layer passed.
    """

    action_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._busy = False
        self._state: dict[str, Any] = {}
        self._history_items: list[dict[str, Any]] = []
        self._actions: dict[str, QPushButton] = {}
        self._level_labels: dict[str, QLabel] = {}
        self._level_names: dict[str, QLabel] = {}
        self._build_ui()
        self.retranslate_ui()
        self._apply_busy(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.setMaximumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Unusual fonts/heights remain reachable instead of clipping scientific state.
        self._scroll = QScrollArea(self)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(self._scroll)
        content = QWidget()
        self._scroll.setWidget(content)
        layout = QVBoxLayout(content)
        # Publish changing content constraints to QScrollArea when translated
        # buttons change the grid's column count.
        layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        self._summary_group = QGroupBox(content)
        summary_layout = QVBoxLayout(self._summary_group)
        summary_layout.setContentsMargins(6, 4, 6, 4)
        summary_layout.setSpacing(2)
        self._summary_toggle = self._disclosure(self._summary_group)
        self._summary_label = self._label(self._summary_group)
        self._summary_label.setWordWrap(True)
        self._summary_label.hide()
        self._summary_toggle.toggled.connect(self._summary_label.setVisible)
        summary_layout.addWidget(self._summary_toggle)
        summary_layout.addWidget(self._summary_label)
        self._levels_group = QWidget(self._summary_group)
        levels_layout = QGridLayout(self._levels_group)
        levels_layout.setContentsMargins(0, 0, 0, 0)
        levels_layout.setVerticalSpacing(1)
        for row, level in enumerate(LEVEL_TOKENS):
            name = self._label(self._levels_group)
            name.setObjectName(f"level_name_{level}")
            name.setWordWrap(True)
            value = self._label(self._levels_group)
            value.setObjectName(f"level_value_{level}")
            levels_layout.addWidget(name, row, 0)
            levels_layout.addWidget(value, row, 1)
            self._level_names[level] = name
            self._level_labels[level] = value
        levels_layout.setColumnStretch(0, 1)
        summary_layout.addWidget(self._levels_group)
        layout.addWidget(self._summary_group)

        self._actions_group = QWidget(content)
        self._actions_layout = QGridLayout(self._actions_group)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(3)
        self._action_columns = 0
        for token in ACTION_TOKENS:
            button = QPushButton(self._actions_group)
            button.setObjectName(f"action_{token}")
            button.clicked.connect(lambda _checked=False, t=token: self._emit_action(t))
            self._actions[token] = button
        self._cancel_button = self._actions["cancel"]
        self._reflow_actions()
        layout.addWidget(self._actions_group)

        self._history_toggle = self._disclosure(content)
        layout.addWidget(self._history_toggle)
        self._history_group = QWidget(content)
        history_layout = QVBoxLayout(self._history_group)
        history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_table = QTableWidget(0, 3, self._history_group)
        self._history_table.setObjectName("experiment_history_table")
        self._history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._history_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._history_table.verticalHeader().hide()
        self._history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._history_table.setMinimumHeight(65)
        self._history_table.setMaximumHeight(90)
        history_layout.addWidget(self._history_table)
        self._history_group.hide()
        self._history_toggle.toggled.connect(self._history_group.setVisible)
        layout.addWidget(self._history_group)
        layout.addStretch(1)

    @staticmethod
    def _label(parent: QWidget) -> QLabel:
        label = QLabel(parent)
        label.setTextFormat(Qt.PlainText)
        label.setFocusPolicy(Qt.StrongFocus)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        return label

    @staticmethod
    def _disclosure(parent: QWidget) -> QToolButton:
        button = QToolButton(parent)
        button.setCheckable(True)
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.setArrowType(Qt.RightArrow)
        button.toggled.connect(lambda checked: button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow))
        return button

    def _reflow_actions(self) -> None:
        button_width = max(button.sizeHint().width() for button in self._actions.values())
        columns = max(1, min(5, (self.width() - 32) // (button_width + 3)))
        if columns == self._action_columns:
            return
        while self._actions_layout.count():
            self._actions_layout.takeAt(0)
        for column in range(5):
            self._actions_layout.setColumnStretch(column, int(column < columns))
        for index, token in enumerate(ACTION_TOKENS):
            self._actions_layout.addWidget(self._actions[token], index // columns, index % columns)
        self._action_columns = columns
        # Reflow during resize/language changes before QScrollArea can keep the
        # previous (wider) minimum width until another queued layout request.
        self._actions_layout.activate()
        self._scroll.widget().layout().activate()

    def _emit_action(self, token: str) -> None:
        if token not in ACTION_TOKENS or (self._busy and token != "cancel"):
            return
        self.action_requested.emit(token)

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        self._apply_busy(self._busy)

    def _apply_busy(self, busy: bool) -> None:
        for token, button in self._actions.items():
            button.setEnabled(token == "cancel" or not busy)

    def set_state(self, data: dict[str, Any]) -> None:
        self._state = deepcopy(data) if isinstance(data, dict) else {}
        history = self._state.get("history", [])
        self._history_items = [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []
        self._render_state()

    def retranslate_ui(self) -> None:
        self._summary_group.setTitle(ui_text("Trusted experiment"))
        self._summary_toggle.setText(ui_text("Snapshot details"))
        self._history_toggle.setText(ui_text("Validation history"))
        for token, button in self._actions.items():
            button.setText(ui_text(ACTION_TEXT[token]))
            button.setToolTip(ui_text(ACTION_TEXT[token]))
        self._actions["export"].setToolTip(ui_text(EXPORT_NOTE))
        self._history_table.setHorizontalHeaderLabels([ui_text("Level"), ui_text("Status"), ui_text("Record")])
        for level, label in self._level_names.items():
            label.setText(ui_text(LEVEL_TEXT[level]))
        self._render_state()
        self._reflow_actions()

    def _render_state(self) -> None:
        self._render_summary()
        self._render_levels()
        self._render_history()

    @staticmethod
    def _display_value(value: Any) -> str:
        return ui_text("Unknown") if value is None or value == "" else str(value)

    @staticmethod
    def _status_text(value: Any) -> str:
        token = value if isinstance(value, str) and value in STATUS_TEXT else "unobserved"
        return ui_text(STATUS_TEXT[token])

    def _render_summary(self) -> None:
        fingerprint = self._display_value(self._state.get("fingerprint"))
        text = ui_format(
            "Revision: {revision} | Hash: {fingerprint} | Run: {run_id} | Status: {status}",
            revision=self._display_value(self._state.get("revision")),
            fingerprint=fingerprint[:12] + "…" if len(fingerprint) > 12 else fingerprint,
            run_id=self._display_value(self._state.get("run_id")),
            status=self._status_text(self._state.get("status")),
        )
        self._summary_label.setText(text)
        self._summary_label.setToolTip(ui_format("Configuration identity: {fingerprint}", fingerprint=fingerprint))
        self._summary_toggle.setToolTip(text)

    def _render_levels(self) -> None:
        levels = self._state.get("levels", [])
        entries = {item["level"]: item for item in levels if isinstance(item, dict) and isinstance(item.get("level"), str)} if isinstance(levels, list) else {}
        for level, label in self._level_labels.items():
            entry = entries.get(level, {})
            status = self._status_text(entry.get("status", "unverified"))
            detail = entry.get("detail")
            detail = "" if detail is None else str(detail)
            name = ui_text(LEVEL_TEXT[level])
            label.setText(status)
            description = ui_format("{level}: {status}", level=name, status=status)
            if detail:
                description = ui_format("{status} — {detail}", status=description, detail=detail)
            label.setToolTip(description)
            label.setAccessibleName(ui_format("{level}: {status}", level=name, status=status))
            label.setAccessibleDescription(description)
            self._level_names[level].setToolTip(description)

    def _render_history(self) -> None:
        self._history_table.setRowCount(0)
        for entry in self._history_items:
            row = self._history_table.rowCount()
            self._history_table.insertRow(row)
            level = entry.get("level")
            name = ui_text(LEVEL_TEXT[level]) if isinstance(level, str) and level in LEVEL_TEXT else ui_text("Unknown")
            values = [name, self._status_text(entry.get("status")), self._display_value(entry.get("record_id"))]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self._history_table.setItem(row, column, item)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._reflow_actions()
