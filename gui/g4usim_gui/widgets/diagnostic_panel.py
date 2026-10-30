"""Shared, read-only diagnostic list. Activation never changes configuration."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text


def diagnostic_text(diagnostic: Any) -> str:
    """Render the producer's template; do not infer a location from its text."""
    if diagnostic.message_key:
        params = dict(diagnostic.params)
        if "field_label" in params:
            params["field_label"] = ui_text(params["field_label"])
        return ui_format(diagnostic.message_key, **params)
    return ui_text(diagnostic.message)


def location_text(diagnostic: Any) -> str:
    location = diagnostic.location
    if location is not None:
        parts = [location.editor]
        if location.collection:
            parts.append(location.collection)
        if location.row is not None:
            parts[-1] += f"[{location.row}]"
        if location.field:
            parts.append(location.field)
        return ".".join(parts)
    source = diagnostic.source
    if source is not None:
        return f"{source.filename}:{source.line}" if source.line is not None else source.filename
    return ui_text("No editable location")


class DiagnosticPanel(QWidget):
    """Keep typed records separate from localized row labels and raw reports."""

    activationRequested = Signal(object)
    sourceRequested = Signal(object)
    revalidateRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("diagnosticPanel")
        self._records: tuple[Any, ...] = ()
        self._stale = False
        self._status_spec: tuple[str, dict[str, Any], str] = ("No diagnostic report.", {}, "info")
        self._source = None
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("diagnosticTable")
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(96)
        self.table.setMaximumHeight(220)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemActivated.connect(lambda _item: self._activate())
        self.locate_button = QPushButton()
        self.source_button = QPushButton()
        self.revalidate_button = QPushButton()
        self.locate_button.clicked.connect(self._activate)
        self.source_button.clicked.connect(self._view_source)
        self.revalidate_button.clicked.connect(self.revalidateRequested.emit)
        actions = QHBoxLayout()
        actions.addWidget(self.locate_button)
        actions.addWidget(self.source_button)
        actions.addWidget(self.revalidate_button)
        actions.addStretch(1)
        self.status = QLabel()
        self.status.setObjectName("diagnosticStatus")
        self.status.setWordWrap(True)
        self.detail = QPlainTextEdit()
        self.detail.setObjectName("diagnosticRawMessage")
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(48)
        self.detail.setMaximumHeight(76)
        self.source_caption = QLabel()
        self.source_caption.setWordWrap(True)
        self.source_view = QPlainTextEdit()
        self.source_view.setObjectName("diagnosticSourceView")
        self.source_view.setReadOnly(True)
        self.source_view.setMinimumHeight(130)
        self.source_view.setMaximumHeight(230)
        self.source_caption.hide()
        self.source_view.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(actions)
        layout.addWidget(self.status)
        layout.addWidget(self.detail)
        layout.addWidget(self.source_caption)
        layout.addWidget(self.source_view)
        self.refresh_language()

    @property
    def records(self) -> tuple[Any, ...]:
        return self._records

    @property
    def stale(self) -> bool:
        return self._stale

    def selected_diagnostic(self) -> Any | None:
        row = self.table.currentRow()
        return self._records[row] if 0 <= row < len(self._records) else None

    def set_report(self, report: Any) -> None:
        self.set_records(report.diagnostics)

    def set_records(self, records: Iterable[Any]) -> None:
        self._records = tuple(records)
        self._stale = False
        self._source = None
        self.source_view.clear()
        self.source_view.hide()
        self.source_caption.hide()
        self._render_rows()
        self.show_status("Select a diagnostic, then locate its field or view its source.")

    def clear(self) -> None:
        self.set_records(())
        self.show_status("No diagnostic report.")

    def set_stale(self, stale: bool = True) -> None:
        self._stale = bool(stale)
        if self._stale:
            self.show_status("Diagnostics are stale. Validate the current inputs again.", "warning")
        self._selection_changed()

    def show_status(self, text: str, severity: str = "info", **params: Any) -> None:
        self._status_spec = (text, dict(params), severity)
        self._render_status()

    def show_source(self, source: Any, text: str) -> None:
        """Show content already checked by the caller against the source receipt."""
        self._source = source
        self.source_view.setPlainText(text)
        self.source_caption.show()
        self.source_view.show()
        self._render_source_caption()
        if source.line is not None:
            block = self.source_view.document().findBlockByNumber(source.line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.LineUnderCursor)
                self.source_view.setTextCursor(cursor)
                self.source_view.centerCursor()

    def refresh_language(self) -> None:
        self.table.setHorizontalHeaderLabels([ui_text(x) for x in ("Severity", "Code", "Location", "Message")])
        self.table.setAccessibleName(ui_text("Validation diagnostics"))
        self.locate_button.setText(ui_text("Locate field"))
        self.source_button.setText(ui_text("View source"))
        self.revalidate_button.setText(ui_text("Validate again"))
        self._render_rows()
        self._render_status()
        self._render_source_caption()

    def _render_rows(self) -> None:
        selected = self.selected_diagnostic()
        identity = selected.identity if selected is not None else None
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._records))
        severity_labels = {"error": "Error", "blocker": "Error", "warning": "Warning", "info": "Information"}
        current = 0
        for row, diagnostic in enumerate(self._records):
            values = (ui_text(severity_labels[diagnostic.severity]), diagnostic.code,
                      location_text(diagnostic), diagnostic_text(diagnostic))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
            if diagnostic.identity == identity:
                current = row
        self.table.blockSignals(False)
        if self._records:
            self.table.setCurrentCell(current, 0)
        self._selection_changed()

    def _selection_changed(self) -> None:
        diagnostic = self.selected_diagnostic()
        self.locate_button.setEnabled(not self._stale and diagnostic is not None and diagnostic.location is not None)
        self.source_button.setEnabled(not self._stale and diagnostic is not None and diagnostic.source is not None)
        if diagnostic is None:
            self.detail.clear()
            return
        text = diagnostic.raw_message or diagnostic.message
        if diagnostic.unavailable_reason:
            text += "\n" + ui_format("Location unavailable: {reason}", reason=diagnostic.unavailable_reason)
        self.detail.setPlainText(text)

    def _activate(self) -> None:
        diagnostic = self.selected_diagnostic()
        if diagnostic is not None and not self._stale:
            self.activationRequested.emit(diagnostic)

    def _view_source(self) -> None:
        diagnostic = self.selected_diagnostic()
        if diagnostic is not None and not self._stale:
            self.sourceRequested.emit(diagnostic)

    def _render_status(self) -> None:
        text, params, severity = self._status_spec
        label = {"error": "Error", "blocker": "Error", "warning": "Warning", "info": "Information"}.get(severity, "Information")
        message = ui_format(text, **params) if params else ui_text(text)
        self.status.setText(f"{ui_text(label)}: {message}")

    def _render_source_caption(self) -> None:
        if self._source is not None:
            self.source_caption.setText(ui_format("Source: {file}; line: {line}", file=self._source.filename,
                                                 line=self._source.line if self._source.line is not None else ui_text("unknown")))
