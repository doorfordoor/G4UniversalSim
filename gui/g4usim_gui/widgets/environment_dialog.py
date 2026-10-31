"""Asynchronous environment selection. No runner, installer or project ownership."""
from __future__ import annotations

import copy
import json

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QGridLayout, QHeaderView, QLabel, QPlainTextEdit,
    QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout,
)

from g4usim_gui.core.environment_discovery import discover_environments
from g4usim_gui.core.i18n import ui_format, ui_text


class _Signals(QObject):
    completed = Signal(int, object)
    failed = Signal(int, str)


class _DiscoveryTask(QRunnable):
    def __init__(self, generation, candidates, options):
        super().__init__()
        self.generation, self.candidates, self.options = generation, candidates, options
        self.signals = _Signals()

    def run(self):
        try:
            result = discover_environments(self.candidates, **self.options)
        except Exception as exc:
            # Worker boundary only: preserve failures for the dialog, never success.
            self.signals.failed.emit(self.generation, str(exc))
        else:
            self.signals.completed.emit(self.generation, result)


STATUS_TEXT = {
    "ready": "Backend responds; required data directories found",
    "data_incomplete": "Backend responds; required data is missing",
    "partial": "Backend responds; data availability is unknown",
    "unavailable": "Backend probe failed",
    "not_found": "Backend executable was not found",
    "changed_during_probe": "Backend changed during discovery; refresh required",
    "error": "Environment could not be inspected",
    "invalid_candidate": "Invalid environment candidate",
}


class EnvironmentDialog(QDialog):
    """Call open()/show(); construction/refresh never wait for child processes.

    environment_selected emits a detached JSON-compatible fact dictionary.
    Selection is permitted with incomplete data, because choosing a path is not
    permission to run. The existing runner owns all subsequent run validation.
    """
    environment_selected = Signal(dict)

    def __init__(self, candidates=None, parent=None, *, timeout=5.0, env=None,
                 sdk_roots=(), auto_discover=True):
        super().__init__(parent)
        self._candidates = copy.deepcopy(candidates)
        self._options = {"timeout": timeout, "env": copy.deepcopy(env), "sdk_roots": tuple(sdk_roots)}
        self._generation = 0
        self._closed = False
        self._busy = False
        self._task = None
        self.facts = None
        self._choice = None
        self.setWindowTitle(ui_text("Environment discovery and diagnostics"))
        self.resize(960, 640)
        layout = QVBoxLayout(self)
        self.boundary = QLabel(ui_text(
            "Discovery reports backend and dependency facts. It does not initialize or validate a simulation."))
        self.boundary.setWordWrap(True)
        layout.addWidget(self.boundary)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([ui_text(key) for key in
                                             ("Backend executable", "Discovery status", "Architecture", "Geant4", "Build compiler")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(110)
        self.table.setMaximumHeight(200)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.table)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.summary.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.summary.setAccessibleName(ui_text("Selected environment summary"))
        layout.addWidget(self.summary, 1)
        self.details_toggle = QToolButton()
        self.details_toggle.setText(ui_text("Technical details (JSON)"))
        self.details_toggle.setCheckable(True)
        self.details_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.details_toggle.setArrowType(Qt.RightArrow)
        layout.addWidget(self.details_toggle)
        # Keep the public details member and its complete JSON for diagnostics.
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setAccessibleName(ui_text("Environment diagnostic facts"))
        self.details.setMaximumHeight(180)
        self.details.hide()
        self.details_toggle.toggled.connect(self.details.setVisible)
        self.details_toggle.toggled.connect(lambda checked: self.details_toggle.setArrowType(
            Qt.DownArrow if checked else Qt.RightArrow))
        layout.addWidget(self.details)
        self.status = QLabel(ui_text("Not run yet"))
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)
        self._buttons_layout = QGridLayout()
        self.refresh_button = QPushButton(ui_text("Refresh environments"))
        self.browse_button = QPushButton(ui_text("Add backend executable…"))
        self.select_button = QPushButton(ui_text("Use selected environment"))
        self.close_button = QPushButton(ui_text("Close"))
        self.select_button.setEnabled(False)
        self.refresh_button.clicked.connect(self.refresh)
        self.browse_button.clicked.connect(self.browse)
        self.select_button.clicked.connect(self.choose_selected)
        self.close_button.clicked.connect(self.reject)
        self._buttons = (self.refresh_button, self.browse_button, self.select_button, self.close_button)
        for button in self._buttons:
            # Let the dialog shrink first; _adapt_layout gives full labels a row
            # whenever two columns no longer fit at the actual font size.
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._button_columns = 0
        layout.addLayout(self._buttons_layout)
        self._adapt_layout()
        self._render_summary(None)
        if auto_discover:
            QTimer.singleShot(0, self._initial_discovery)

    @property
    def busy(self):
        return self._busy

    def _initial_discovery(self):
        if not self._closed and self.facts is None and not self.busy:
            self.refresh()

    @Slot()
    def refresh(self):
        if self.busy or self._closed:
            return
        self._generation += 1
        self._busy = True
        self._choice = None
        # Old rows must not remain selectable while a fresh observation is pending.
        self.table.setRowCount(0)
        self.facts = None
        self.details.clear()
        self._render_summary(None)
        self.select_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.status.setText(ui_text("Discovering environments…"))
        task = _DiscoveryTask(self._generation, copy.deepcopy(self._candidates), self._options.copy())
        task.signals.completed.connect(self._completed, Qt.QueuedConnection)
        task.signals.failed.connect(self._failed, Qt.QueuedConnection)
        self._task = task
        QThreadPool.globalInstance().start(task)

    @Slot(int, object)
    def _completed(self, generation, facts):
        if self._closed or generation != self._generation:
            return
        self._finish()
        self.facts = facts
        environments = facts["environments"]
        self.table.setRowCount(len(environments))
        for row, item in enumerate(environments):
            for column, value in enumerate(self._row_values(item)):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.table.setItem(row, column, cell)
        self._adapt_layout()
        self.status.setText(ui_format("Discovered {count} backend candidates. Selection does not start a simulation.", count=len(environments)))
        if environments:
            self.table.selectRow(0)
        self._selection_changed()

    @Slot(int, str)
    def _failed(self, generation, error):
        if self._closed or generation != self._generation:
            return
        self._finish()
        self.status.setText(ui_format("Environment discovery failed: {error}", error=error))

    def _finish(self):
        self._busy = False
        self._task = None
        self.refresh_button.setEnabled(True)
        self.browse_button.setEnabled(True)

    def current_environment(self):
        row = self.table.currentRow()
        rows = self.facts["environments"] if self.facts else []
        return copy.deepcopy(rows[row]) if 0 <= row < len(rows) else None

    def selected_environment(self):
        """Accepted choice only; table highlighting alone does not accept a path."""
        return copy.deepcopy(self._choice)

    def selected_executable(self):
        return self._choice["executable"] if self._choice else None

    @Slot()
    def _selection_changed(self):
        current = self.current_environment()
        selectable = bool(current and current.get("capabilities", {}).get("status") == "available"
                          and current.get("identity", {}).get("stable") is True)
        self.select_button.setEnabled(selectable and not self.busy and not self._closed)
        # Raw backend messages and stable protocol fields are intentionally untranslated.
        details = {"environment": current, "host": self.facts.get("host"), "sdk": self.facts.get("sdk")} if self.facts else {}
        self.details.setPlainText(json.dumps(details, ensure_ascii=False, indent=2))
        self._render_summary(current)

    @staticmethod
    def _version(value):
        # G4VERSION_NUMBER is major*100 + minor*10 + patch; format only.
        # The original backend value remains untouched in facts/details.
        if type(value) is int and 1000 <= value <= 9999:
            return f"{value // 100}.{value // 10 % 10}.{value % 10}"
        return str(value) if value is not None else ui_text("Unknown")

    def _row_values(self, item):
        architecture = item.get("architecture", {}).get("machine", "unknown")
        build = item.get("build", {})
        return (
            item["executable"], ui_text(STATUS_TEXT.get(item["status"], "Unknown")),
            ui_text("Unknown") if architecture == "unknown" else architecture,
            self._version(build.get("geant4_version_number")),
            " ".join(str(build.get(key) or "") for key in ("compiler_id", "compiler_version")).strip()
            or ui_text("Unknown"),
        )

    def _render_summary(self, current):
        boundary = ui_text("Selection only chooses a backend path; it does not start or validate a simulation.")
        if current is None:
            self.summary.setPlainText(ui_text("Select a backend to view its summary.") + "\n\n" + boundary)
            return
        values = self._row_values(current)
        lines = [ui_format("{label}: {value}", label=ui_text(label), value=value)
                 for label, value in zip(
                     ("Backend executable", "Discovery status", "Architecture", "Geant4", "Build compiler"), values)]
        data = current.get("data") or {}
        # Display the discovery service's explicit facts, never infer readiness
        # from directories, the overall status, or a missing data report.
        complete = data.get("required_complete")
        if complete is True:
            data_text = ui_text("Required data directories found")
        elif complete is False:
            data_text = ui_text("Required data is missing")
        else:
            data_text = ui_text("Data availability is unknown")
        lines.append(ui_format("{label}: {value}", label=ui_text("Required datasets"), value=data_text))
        report = data.get("report") or {}
        for dataset in report.get("datasets", []):
            if dataset.get("required") is True and dataset.get("found") is False:
                lines.append(ui_format("Missing required dataset: {name}",
                                       name=dataset.get("folder") or dataset.get("env") or ui_text("Unknown")))
        self.summary.setPlainText("\n".join(lines) + "\n\n" + boundary)

    def _adapt_layout(self):
        # Reserve usable widths for path and status; on small windows the table
        # scrolls horizontally instead of donating all spare width to compiler.
        status_width = max([240] + [self.table.fontMetrics().horizontalAdvance(
            self.table.item(row, 1).text()) + 24 for row in range(self.table.rowCount())
            if self.table.item(row, 1) is not None])
        widths = [300, status_width, 80, 80, 150]
        extra = max(0, self.table.viewport().width() - sum(widths))
        widths[0] += extra * 3 // 5
        widths[1] += extra - extra * 3 // 5
        for column, width in enumerate(widths):
            self.table.setColumnWidth(column, width)
        button_width = max(button.sizeHint().width() for button in self._buttons)
        columns = 2 if self.width() - 32 >= 2 * button_width + 6 else 1
        if columns != self._button_columns:
            while self._buttons_layout.count():
                self._buttons_layout.takeAt(0)
            for index, button in enumerate(self._buttons):
                self._buttons_layout.addWidget(button, index // columns, index % columns)
            self._button_columns = columns

    def retranslate_ui(self):
        self.setWindowTitle(ui_text("Environment discovery and diagnostics"))
        self.boundary.setText(ui_text(
            "Discovery reports backend and dependency facts. It does not initialize or validate a simulation."))
        self.details_toggle.setText(ui_text("Technical details (JSON)"))
        self.summary.setAccessibleName(ui_text("Selected environment summary"))
        self.details.setAccessibleName(ui_text("Environment diagnostic facts"))
        for button, text in zip(self._buttons, (
                "Refresh environments", "Add backend executable…", "Use selected environment", "Close")):
            button.setText(ui_text(text))
        self.table.setHorizontalHeaderLabels([ui_text(key) for key in (
            "Backend executable", "Discovery status", "Architecture", "Geant4", "Build compiler")])
        for row, item in enumerate((self.facts or {}).get("environments", [])):
            for column, text in enumerate(self._row_values(item)):
                cell = self.table.item(row, column)
                cell.setText(text)
                cell.setToolTip(text)
        if self.busy:
            self.status.setText(ui_text("Discovering environments…"))
        elif self.facts is not None:
            self.status.setText(ui_format(
                "Discovered {count} backend candidates. Selection does not start a simulation.",
                count=len(self.facts["environments"])))
        self._render_summary(self.current_environment())
        self._adapt_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_layout()

    @Slot()
    def choose_selected(self):
        if not self.select_button.isEnabled():
            return
        self._choice = self.current_environment()
        self.environment_selected.emit(copy.deepcopy(self._choice))
        self.accept()

    @Slot()
    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, ui_text("Choose backend executable"))
        if path:
            existing = self._candidates
            if existing is None:
                existing = [item["executable"] for item in (self.facts or {}).get("environments", [])]
            elif isinstance(existing, (str, dict)):
                existing = [existing]
            else:
                try:
                    existing = list(existing)
                except TypeError:
                    existing = [existing]
            self._candidates = existing + [path]
            self.refresh()

    def done(self, result):
        self._closed = True
        self._generation += 1
        # Pool owns the bounded worker. Closing never waits or destroys a live QThread.
        self._busy = False
        self.select_button.setEnabled(False)
        super().done(result)
