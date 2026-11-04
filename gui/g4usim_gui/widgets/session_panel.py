"""Continuous-run session panel for the Run Console.

The panel is a pure view: it renders the session client's state snapshots and
emits user intents.  It never starts processes, never blocks the Qt main thread
and never claims that a configured value reached the kernel.  Rounds, drafts and
receipts all come from backend responses; a rejected request leaves the previous
draft and results untouched.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.session_model import MAX_EVENTS, format_energy, round_status_text

PARTICLES = (
    ("proton", "proton"),
    ("e-", "electron (e-)"),
    ("gamma", "gamma"),
    ("neutron", "neutron"),
    ("alpha", "alpha"),
)

_STATUS_ROLES = {
    "starting": "running",
    "initializing": "running",
    "ready": "success",
    "running": "running",
    "stopping": "warning",
    "closed": "muted",
    "failed": "failed",
    "rejected": "failed",
    "error": "failed",
    "draft": "muted",
}


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sessionMutedLabel")
    label.setProperty("uiRole", "hint")
    label.setWordWrap(True)
    return label


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sessionFieldLabel")
    return label


class SessionPanel(QWidget):
    """One visible entry for the controlled A/B/A session."""

    startSessionRequested = Signal()
    closeSessionRequested = Signal()
    submitRoundRequested = Signal()
    cancelRoundRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sessionPanel")
        self._records: list[dict] = []
        self._expanded = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        header = QHBoxLayout()
        self.toggle_button = QToolButton(self)
        self.toggle_button.setObjectName("sessionToggle")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.clicked.connect(self._toggle_expanded)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = QLabel(self)
        self.title_label.setObjectName("sessionTitle")
        self.title_label.setProperty("uiRole", "sectionTitle")
        self.subtitle_label = QLabel(self)
        self.subtitle_label.setObjectName("sessionSubtitle")
        self.subtitle_label.setProperty("uiRole", "hint")
        self.subtitle_label.setWordWrap(True)
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)
        header.addLayout(title_box, 1)

        self.status_chip = QLabel(self)
        self.status_chip.setObjectName("sessionStatusChip")
        self.status_chip.setProperty("uiRole", "statusChip")
        self.status_chip.setProperty("statusRole", "muted")
        header.addWidget(self.status_chip)

        self.start_button = QPushButton(self)
        self.start_button.setObjectName("sessionStartButton")
        self.start_button.setProperty("buttonRole", "primary")
        self.start_button.clicked.connect(self.startSessionRequested)
        header.addWidget(self.start_button)

        self.close_button = QPushButton(self)
        self.close_button.setObjectName("sessionCloseButton")
        self.close_button.setProperty("buttonRole", "danger")
        self.close_button.clicked.connect(self.closeSessionRequested)
        header.addWidget(self.close_button)

        self.toggle_button.setToolTip(ui_text("Collapse session"))
        header.addWidget(self.toggle_button)

        outer.addLayout(header)

        self.body = QWidget(self)
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        outer.addWidget(self.body)

        cards = QHBoxLayout()
        cards.setSpacing(8)
        cards.addWidget(self._build_current_card(), 1)
        cards.addWidget(self._build_next_card(), 1)
        body_layout.addLayout(cards)
        body_layout.addWidget(self._build_rounds_card())

        bottom = QSplitter(Qt.Horizontal, self)
        bottom.setObjectName("sessionBottomSplit")
        bottom.addWidget(self._build_log_card())
        bottom.addWidget(self._build_feedback_card())
        bottom.setStretchFactor(0, 3)
        bottom.setStretchFactor(1, 2)
        bottom.setChildrenCollapsible(False)
        bottom.setSizes([720, 420])
        body_layout.addWidget(bottom, 1)

        self.refresh_language()
        self.set_view({})

    # ------------------------------------------------------------------ cards
    def _build_current_card(self) -> QWidget:
        self.current_group = QGroupBox(self)
        self.current_group.setObjectName("sessionCurrentGroup")
        self.current_group.setProperty("uiRole", "panel")
        layout = QVBoxLayout(self.current_group)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.session_id_label = _muted("—")
        self.kernel_label = _muted("—")
        self.revision_label = _muted("—")
        self.backend_label = _muted("—")
        self.output_label = _muted("—")
        form.addRow(_field_label(""), self.session_id_label)
        form.addRow(_field_label(""), self.kernel_label)
        form.addRow(_field_label(""), self.revision_label)
        form.addRow(_field_label(""), self.backend_label)
        form.addRow(_field_label(""), self.output_label)
        self._current_form = form
        layout.addLayout(form)

        self.round_state_label = QLabel("—", self)
        self.round_state_label.setObjectName("sessionRoundState")
        self.round_state_label.setWordWrap(True)
        layout.addWidget(self.round_state_label)

        buttons = QHBoxLayout()
        self.cancel_button = QPushButton(self)
        self.cancel_button.setObjectName("sessionCancelButton")
        self.cancel_button.setProperty("buttonRole", "danger")
        self.cancel_button.clicked.connect(self.cancelRoundRequested)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return self.current_group

    def _build_next_card(self) -> QWidget:
        self.next_group = QGroupBox(self)
        self.next_group.setObjectName("sessionNextGroup")
        self.next_group.setProperty("uiRole", "panel")
        layout = QVBoxLayout(self.next_group)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.particle_combo = QComboBox(self)
        for key, label in PARTICLES:
            self.particle_combo.addItem(label, key)
        self.energy_edit = QLineEdit(self)
        self.energy_edit.setObjectName("sessionEnergyEdit")
        self.events_spin = QSpinBox(self)
        self.events_spin.setRange(1, MAX_EVENTS)
        self.events_spin.setSingleStep(100)
        self.events_spin.setValue(1000)
        self.position_edit = QLineEdit(self)
        self.position_edit.setObjectName("sessionPositionEdit")
        self.direction_edit = QLineEdit(self)
        self.direction_edit.setObjectName("sessionDirectionEdit")

        self._particle_label = _field_label("")
        self._energy_label = _field_label("")
        self._events_label = _field_label("")
        self._position_label = _field_label("")
        self._direction_label = _field_label("")
        form.addRow(self._particle_label, self.particle_combo)
        form.addRow(self._energy_label, self.energy_edit)
        form.addRow(self._events_label, self.events_spin)
        form.addRow(self._position_label, self.position_edit)
        form.addRow(self._direction_label, self.direction_edit)
        layout.addLayout(form)

        self.whitelist_hint = _muted("")
        self.whitelist_hint.setObjectName("sessionWhitelistHint")
        layout.addWidget(self.whitelist_hint)
        layout.addStretch(1)

        self.submit_button = QPushButton(self)
        self.submit_button.setObjectName("sessionSubmitButton")
        self.submit_button.setProperty("buttonRole", "primary")
        self.submit_button.clicked.connect(self.submitRoundRequested)
        layout.addWidget(self.submit_button)
        return self.next_group

    def _build_rounds_card(self) -> QWidget:
        self.rounds_group = QGroupBox(self)
        self.rounds_group.setObjectName("sessionRoundsGroup")
        self.rounds_group.setProperty("uiRole", "panel")
        layout = QVBoxLayout(self.rounds_group)
        self.rounds_table = QTableWidget(0, 7, self)
        self.rounds_table.setObjectName("sessionRoundsTable")
        self.rounds_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rounds_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rounds_table.setAlternatingRowColors(True)
        self.rounds_table.verticalHeader().setVisible(False)
        header = self.rounds_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        self.rounds_table.setMinimumHeight(120)
        layout.addWidget(self.rounds_table)
        return self.rounds_group

    def _build_log_card(self) -> QWidget:
        self.log_group = QGroupBox(self)
        self.log_group.setObjectName("sessionLogGroup")
        self.log_group.setProperty("uiRole", "panel")
        layout = QVBoxLayout(self.log_group)
        self.log_view = QPlainTextEdit(self)
        self.log_view.setObjectName("sessionLogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(4000)
        self.log_view.setPlaceholderText(ui_text("Session log: protocol frames and backend output."))
        layout.addWidget(self.log_view, 1)
        buttons = QHBoxLayout()
        self.clear_log_button = QPushButton(self)
        self.clear_log_button.setObjectName("sessionClearLogButton")
        self.clear_log_button.clicked.connect(self.clear_log)
        buttons.addWidget(self.clear_log_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return self.log_group

    def _build_feedback_card(self) -> QWidget:
        self.feedback_group = QGroupBox(self)
        self.feedback_group.setObjectName("sessionFeedbackGroup")
        self.feedback_group.setProperty("uiRole", "panel")
        layout = QVBoxLayout(self.feedback_group)
        self.feedback_view = QTextBrowser(self)
        self.feedback_view.setObjectName("sessionFeedbackView")
        self.feedback_view.setOpenExternalLinks(False)
        self.feedback_view.setPlaceholderText(ui_text(
            "The backend receipt decides whether a round was accepted."))
        layout.addWidget(self.feedback_view, 1)
        return self.feedback_group

    # --------------------------------------------------------------- language
    def refresh_language(self) -> None:
        self.toggle_button.setText(ui_text("Continuous run session"))
        self.title_label.setText(ui_text("Continuous run session"))
        self.subtitle_label.setText(ui_text(
            "One backend process completes several rounds. Each round needs its own backend "
            "receipt; accepted parameters are not the same as kernel application."))
        self.start_button.setText(ui_text("Start session"))
        self.close_button.setText(ui_text("End session"))
        self.cancel_button.setText(ui_text("Cancel round"))
        self.submit_button.setText(ui_text("Submit round"))
        self.clear_log_button.setText(ui_text("Clear log"))
        self.log_view.setPlaceholderText(ui_text("Session log: protocol frames and backend output."))
        self.feedback_view.setPlaceholderText(ui_text(
            "The backend receipt decides whether a round was accepted."))
        self.current_group.setTitle(ui_text("Current session and round"))
        self.next_group.setTitle(ui_text("Next round"))
        self.rounds_group.setTitle(ui_text("Round records"))
        self.log_group.setTitle(ui_text("Session log"))
        self.feedback_group.setTitle(ui_text("Feedback and receipts"))
        for index, text in enumerate((
            ui_text("Round"),
            ui_text("Request"),
            ui_text("Run"),
            ui_text("Parameters"),
            ui_text("Events"),
            ui_text("Status"),
            ui_text("Record"),
        )):
            item = self.rounds_table.horizontalHeaderItem(index)
            if item is None:
                self.rounds_table.setHorizontalHeaderItem(index, QTableWidgetItem(text))
            else:
                item.setText(text)
        for label, text in (
            (self._field_row_label(0), ui_text("Session")),
            (self._field_row_label(1), ui_text("Kernel")),
            (self._field_row_label(2), ui_text("Revision")),
            (self._field_row_label(3), ui_text("Backend")),
            (self._field_row_label(4), ui_text("Output")),
        ):
            label.setText(text)
        self._particle_label.setText(ui_text("Particle"))
        self._energy_label.setText(ui_text("Energy"))
        self._events_label.setText(ui_text("Events"))
        self._position_label.setText(ui_text("Position (optional)"))
        self._direction_label.setText(ui_text("Direction (optional)"))
        self.energy_edit.setPlaceholderText(ui_text("e.g. 100 MeV"))
        self.position_edit.setPlaceholderText(ui_text("e.g. 0 0 0 mm"))
        self.direction_edit.setPlaceholderText(ui_text("e.g. 0 0 1"))
        self.whitelist_hint.setText(ui_text(
            "Only single-source basic fields are editable here. Geometry, materials, physics, "
            "threads and the output root need a new session."))
        self.round_state_label.setText(ui_text("No round is running."))

    def _field_row_label(self, row: int) -> QLabel:
        item = self._current_form.itemAt(row, QFormLayout.LabelRole)
        if item is None or item.widget() is None:
            label = _field_label("")
            self._current_form.setWidget(row, QFormLayout.LabelRole, label)
            return label
        return item.widget()

    def refresh_theme(self) -> None:
        self._repolish(self)

    def _repolish(self, widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        for child in widget.findChildren(QWidget):
            style.unpolish(child)
            style.polish(child)

    # ------------------------------------------------------------------ states
    def set_view(self, view: dict) -> None:
        session = dict(view.get("session") or {})
        phase = str(view.get("phase") or "closed")
        alive = bool(session.get("alive"))
        handshaken = bool(session.get("session_id"))
        kernel = str(view.get("kernel") or "pre_init")
        revision = view.get("state_revision")
        draft = dict(view.get("draft") or {})
        run = dict(view.get("run") or {})
        self._set_status(phase, alive)
        self.session_id_label.setText((session.get("session_id") or "—")[:12])
        self.kernel_label.setText(kernel)
        if isinstance(revision, int) and isinstance(draft.get("state_revision"), int):
            self.revision_label.setText(ui_format(
                "state {state}, draft {draft}", state=revision,
                draft=draft["state_revision"]))
        elif isinstance(revision, int):
            self.revision_label.setText(ui_format("state {state}", state=revision))
        else:
            self.revision_label.setText("—")
        backend = dict(session.get("backend") or {})
        fingerprint = str(backend.get("source_fingerprint") or "")
        commit = str(backend.get("build_git_commit") or "")
        if fingerprint or commit:
            self.backend_label.setText(ui_format(
                "fingerprint {fingerprint} · build {build}",
                fingerprint=fingerprint[:12] or "unknown", build=commit[:12] or "unknown"))
            self.backend_label.setToolTip(fingerprint + "\n" + commit)
        else:
            self.backend_label.setText("—")
        output_root = str(session.get("output_root") or "")
        record_root = str(session.get("record_root") or "")
        self.output_label.setText(self._elide(output_root) or "—")
        self.output_label.setToolTip("output: " + output_root + "\nrecord: " + record_root)

        editable, reason = _editable(view)
        ready = alive and phase == "ready"
        self.energy_edit.setEnabled(ready and not run)
        self.events_spin.setEnabled(ready and not run)
        self.particle_combo.setEnabled(ready and not run)
        self.position_edit.setEnabled(ready and not run)
        self.direction_edit.setEnabled(ready and not run)
        self.submit_button.setEnabled(bool(ready and editable))
        self.cancel_button.setEnabled(phase == "running")
        self.close_button.setEnabled(alive)
        self.start_button.setEnabled(not alive)
        if not editable and alive and phase == "ready":
            self.whitelist_hint.setText(ui_text(reason))
        elif alive and phase == "ready":
            self.whitelist_hint.setText(ui_text(
                "Only single-source basic fields are editable here. Geometry, materials, "
                "physics, threads and the output root need a new session."))
        elif not alive:
            self.whitelist_hint.setText(ui_text(
                "Start a session first; the generated configuration is loaded by the backend."))
        self._render_run(run, phase)

    def set_session_active(self, active: bool) -> None:
        self.start_button.setEnabled(not active)
        if not active:
            self.cancel_button.setEnabled(False)
            self.submit_button.setEnabled(False)

    def _set_status(self, phase: str, alive: bool) -> None:
        if not alive and phase in {"closed", "failed"}:
            role = _STATUS_ROLES.get(phase, "muted")
        else:
            role = _STATUS_ROLES.get(phase, "muted")
        text = ui_text({
            "starting": "Starting",
            "initializing": "Initializing kernel",
            "ready": "Ready for the next round",
            "running": "Round running",
            "stopping": "Closing",
            "closed": "Closed",
            "failed": "Failed",
            "draft": "Not started",
        }.get(phase, "Not started"))
        self.status_chip.setText(text)
        if self.status_chip.property("statusRole") != role:
            self.status_chip.setProperty("statusRole", role)
            self._repolish(self.status_chip)

    def _render_run(self, run: dict, phase: str) -> None:
        if not run:
            self.round_state_label.setText(ui_text("No round is running."))
            return
        text = ui_format(
            "Round {run_id}: planned {planned}, completed {completed}, cancel requested {cancel}.",
            run_id=str(run.get("run_id") or "—"), planned=run.get("planned_events", "—"),
            completed=run.get("completed_events", "—"),
            cancel=ui_text("yes") if run.get("cancel_requested") else ui_text("no"))
        self.round_state_label.setText(text)

    @staticmethod
    def _elide(text: str, limit: int = 52) -> str:
        if len(text) <= limit:
            return text
        return "…" + text[-(limit - 1):]

    # ------------------------------------------------------------------ rounds
    def set_rounds(self, records) -> None:
        self._records = [dict(record) for record in records]
        self._rebuild_rounds()

    def add_round(self, record: dict) -> None:
        self._records.append(dict(record))
        self._rebuild_rounds()

    def rounds(self) -> list[dict]:
        return [dict(record) for record in self._records]

    def _rounds_placeholder(self) -> bool:
        return not self._records

    @staticmethod
    def _parameters_cell(record: dict) -> str:
        parameters = record.get("parameters")
        if parameters:
            return str(parameters)
        particle = str(record.get("particle") or "")
        energy = format_energy(record.get("energy_mev"))
        return " ".join(part for part in (particle, energy) if part) or "—"

    @staticmethod
    def _status_cell(record: dict) -> str:
        status = str(record.get("status") or "")
        completed = record.get("completed_events")
        planned = record.get("planned_events")
        if status == "completed":
            return ui_format("{completed}/{planned} events", completed=completed, planned=planned)
        if status == "cancelled":
            return ui_format("cancelled after {completed}/{planned} events",
                             completed=completed, planned=planned)
        if status == "aborted":
            return ui_format("aborted after {completed}/{planned} events",
                             completed=completed, planned=planned)
        if status == "failed":
            return ui_format("failed after {completed}/{planned} events",
                             completed=completed, planned=planned)
        return round_status_text(record)

    def _rebuild_rounds(self) -> None:
        self.rounds_table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            values = (
                str(record.get("round") or row + 1),
                str(record.get("run_request_id") or "—")[:12],
                str(record.get("run_id") if record.get("run_id") is not None else "—"),
                self._parameters_cell(record),
                ui_format("{completed}/{planned}", completed=record.get("completed_events", "—"),
                          planned=record.get("planned_events", "—")),
                self._status_cell(record),
                self._receipt_cell(record),
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                if column == 6:
                    item.setToolTip(self._receipt_tooltip(record))
                self.rounds_table.setItem(row, column, item)

    @staticmethod
    def _receipt_cell(record: dict) -> str:
        if record.get("receipt_ok"):
            reference = record.get("receipt_reference")
            if reference and reference.get("path"):
                return ui_text("Record verified")
            return ui_text("Inline record verified")
        return ui_text("Record unusable: ") + str(record.get("receipt_reason") or "unknown")

    @staticmethod
    def _receipt_tooltip(record: dict) -> str:
        lines = [
            ui_text("Run request") + ": " + str(record.get("run_request_id") or "—"),
            ui_text("Run id") + ": " + str(record.get("run_id")),
            ui_text("Status") + ": " + str(record.get("status") or "—"),
            ui_text("Receipt") + ": " + (str(record.get("receipt_path") or "inline")
                                        if record.get("receipt_ok") else str(record.get("receipt_reason"))),
        ]
        if record.get("receipt_sha256"):
            lines.append("sha256: " + str(record["receipt_sha256"]))
        if record.get("artifacts_truncated"):
            lines.append(ui_text("Bounded frame; full receipt reference") + ": "
                         + str(record.get("artifact_count")))
        return "\n".join(lines)

    # ---------------------------------------------------------------- feedback
    def set_message(self, text: str, level: str = "info") -> None:
        self.feedback_view.append(
            "<p><b>{label}</b> {text}</p>".format(
                label=_escape(ui_text({"info": "Info", "success": "Done",
                                       "warning": "Attention", "failed": "Failed"}.get(level, "Info"))),
                text=_escape(text)))
        if level in {"failed", "warning"}:
            self.status_chip.setText(ui_text("Attention") if level == "warning" else ui_text("Rejected"))
            if self.status_chip.property("statusRole") != level:
                self.status_chip.setProperty("statusRole", level if level == "failed" else "warning")
                self._repolish(self.status_chip)

    def set_rejection(self, rejection: dict) -> None:
        reason = str(rejection.get("reason") or "unknown")
        message = str(rejection.get("message") or "")
        self.feedback_view.append("<p><b>{label}</b> {reason}<br>{message}</p>".format(
            label=_escape(ui_text("Rejected")), reason=_escape(reason),
            message=_escape(message)))
        self.status_chip.setText(ui_text("Rejected"))
        self.status_chip.setProperty("statusRole", "failed")
        self._repolish(self.status_chip)
        self.round_state_label.setText(ui_text(
            "The backend rejected this request; no round was started and the previous draft/result stays."))

    def draft(self) -> dict:
        particle = self.particle_combo.currentData()
        return {
            "particle": str(particle or ""),
            "energy_text": self.energy_edit.text().strip(),
            "events": int(self.events_spin.value()),
            "position": self.position_edit.text().strip(),
            "direction": self.direction_edit.text().strip(),
        }

    def set_draft_defaults(self, *, particle: str = "proton", energy_text: str = "",
                           events: int = 1000) -> None:
        index = self.particle_combo.findData(particle)
        if index >= 0:
            self.particle_combo.setCurrentIndex(index)
        if energy_text:
            self.energy_edit.setText(energy_text)
        if events > 0:
            self.events_spin.setValue(min(events, MAX_EVENTS))

    # -------------------------------------------------------------------- log
    def append_log(self, text: str) -> None:
        for line in str(text).splitlines():
            if line:
                self.log_view.appendPlainText(line)

    def clear_log(self) -> None:
        self.log_view.clear()

    # ---------------------------------------------------------------- expander
    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.toggle_button.setChecked(self._expanded)
        self.body.setVisible(self._expanded)
        self._sync_toggle_text()

    def is_expanded(self) -> bool:
        return self._expanded

    def _toggle_expanded(self, checked: bool) -> None:
        self.set_expanded(checked)

    def _sync_toggle_text(self) -> None:
        self.toggle_button.setText(
            ui_text("Collapse session") if self._expanded else ui_text("Expand session"))


def _editable(view: dict) -> tuple[bool, str]:
    from g4usim_gui.core.session_model import session_eligibility

    return session_eligibility(view)


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
