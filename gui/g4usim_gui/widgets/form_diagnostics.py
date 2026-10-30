"""Field navigation for static forms, using the same records and UI as configuration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from g4usim_gui.core.diagnostics import Diagnostic, semantic_snapshot
from g4usim_gui.core.i18n import ui_text
from shiboken6 import isValid
from g4usim_gui.widgets.diagnostic_navigation import (
    WidgetHighlighter, can_reveal_widget, reveal_widget, source_view_text,
)
from g4usim_gui.widgets.diagnostic_panel import DiagnosticPanel, diagnostic_text


class FormDiagnosticController(QObject):
    """Resolve registered fields and a complete form snapshot before any UI mutation."""

    def __init__(self, owner: QWidget, panel: DiagnosticPanel, editor: str,
                 fields: Mapping[str, QWidget], snapshot: Callable[[], Any],
                 *, reveal: Callable[[QWidget], bool] | None = None,
                 revealable_ancestors: Callable[[QWidget], tuple[QWidget, ...]] | None = None) -> None:
        super().__init__(owner)
        self.panel = panel
        self.editor = editor
        self.fields = dict(fields)
        self.snapshot = snapshot
        self.reveal = reveal
        self.revealable_ancestors = revealable_ancestors
        self._binding_token = object()
        self.highlighter = WidgetHighlighter(self)
        self._epoch = 0
        self._report_snapshot: str | None = None
        panel.activationRequested.connect(self.navigate)
        panel.sourceRequested.connect(self.view_source)
        for widget in set(self.fields.values()):
            for name in ('textChanged', 'currentIndexChanged', 'valueChanged', 'toggled', 'currentRowChanged'):
                signal = getattr(widget, name, None)
                if signal is not None:
                    signal.connect(lambda *_args: self.invalidate())
                    break

    def _current_snapshot(self) -> str:
        return semantic_snapshot({'epoch': self._epoch, 'values': self.snapshot()})

    def set_report(self, report) -> None:
        current = self._current_snapshot()
        bindings = getattr(report, '_f4_form_bindings', None)
        if bindings is None:
            bindings = report._f4_form_bindings = {}
        captured = bindings.setdefault(self._binding_token, current)
        self._set_records(report.diagnostics, captured)

    def _set_records(self, records, captured: str) -> None:
        self.highlighter.clear()
        self._report_snapshot = captured
        self.panel.set_records(tuple(replace(record, location=replace(record.location, snapshot_id=captured))
            if record.location is not None and not record.location.snapshot_id else record for record in records))
        if captured != self._current_snapshot():
            self.panel.set_stale()

    def invalidate(self, *, force: bool = False) -> None:
        if force:
            self._epoch += 1
        if self._report_snapshot is not None and (
                force or self._current_snapshot() != self._report_snapshot):
            if not force and not self.panel.stale:
                self._epoch += 1
            self.highlighter.clear()
            self.panel.set_stale()

    def clear(self) -> None:
        self.highlighter.clear()
        self._epoch += 1
        self._report_snapshot = None
        self.panel.clear()

    def _record(self, diagnostic: Diagnostic) -> Diagnostic | None:
        self.invalidate()
        if self.panel.stale or self._report_snapshot is None:
            self.panel.show_status('Diagnostics are stale. Validate the current inputs again.', 'warning')
            return None
        if diagnostic.location is not None and diagnostic.location.snapshot_id and diagnostic.location.snapshot_id != self._report_snapshot:
            self.panel.show_status('This diagnostic belongs to a different editor or snapshot.', 'warning')
            return None
        return next((record for record in self.panel.records if record.identity == diagnostic.identity), None)

    def navigate(self, diagnostic: Diagnostic) -> bool:
        record = self._record(diagnostic)
        if record is None:
            return False
        location = record.location
        if location is None:
            if record.source is not None:
                return self.view_source(record)
            self.panel.show_status('This diagnostic has no editable target: {reason}', 'warning',
                                   reason=ui_text(record.unavailable_reason or 'unknown'))
            return False
        if location.editor != self.editor or location.collection or location.row is not None:
            self.panel.show_status('This diagnostic belongs to a different editor or snapshot.', 'warning')
            return False
        widget = self.fields.get(location.field)
        if widget is None:
            self.panel.show_status('This diagnostic has no editable target: {reason}', 'warning',
                                   reason=ui_text('The field is not exposed by this editor.'))
            return False
        if not isValid(widget) or not widget.isEnabled() or widget.isHidden():
            self.panel.show_status('This field is not currently editable.', 'warning')
            return False
        if callable(getattr(widget, 'isReadOnly', None)) and widget.isReadOnly():
            self.panel.show_status('This field is not currently editable.', 'warning')
            return False
        result = can_reveal_widget(widget, revealable_ancestors=(
            self.revealable_ancestors(widget) if self.revealable_ancestors is not None else ()))
        if not result.ok:
            self.panel.show_status('{message}', 'warning', message=result.message)
            return False
        # The owning form may reveal a known wizard page or advanced group. It
        # cannot enable a disabled field, rewrite values or resolve unknown fields.
        if self.reveal is not None and self.reveal(widget) is False:
            self.panel.show_status('This editor is unavailable in the current mode.', 'warning')
            return False
        result = reveal_widget(widget)
        if not result.ok:
            self.panel.show_status('{message}', 'warning', message=result.message)
            return False
        self.highlighter.highlight(widget, record.severity, diagnostic_text(record))
        self.panel.show_status('Located {field}. No configuration value was changed.', field=location.field)
        return True

    def view_source(self, diagnostic: Diagnostic) -> bool:
        record = self._record(diagnostic)
        if record is None or record.source is None:
            return False
        result, text = source_view_text(record.source)
        if not result.ok:
            self.panel.show_status('{message}', 'warning', message=result.message)
            return False
        self.panel.show_source(record.source, text)
        self.panel.show_status('{message}', 'warning' if result.status == 'historical_source' else 'info',
                               message=result.message)
        return True
