"""Cross-page diagnostic presentation; field semantics stay with the producers."""
from __future__ import annotations

from g4usim_gui.core.diagnostics import emit_diagnostic
from g4usim_gui.validators.config_validator import ValidationReport
from g4usim_gui.widgets.form_diagnostics import FormDiagnosticController
from g4usim_gui.widgets.diagnostic_navigation import can_reveal_widget, reveal_widget
from g4usim_gui.widgets.diagnostic_panel import diagnostic_text


class DiagnosticsMixin:
    def _clear_diagnostic_highlights(self) -> None:
        from g4usim_gui.widgets.diagnostic_navigation import WidgetHighlighter
        for highlighter in self.findChildren(WidgetHighlighter):
            highlighter.clear()

    def _setup_diagnostic_routes(self) -> None:
        fields = self.project_page.diagnostic_fields()
        snapshot = self.project_page.diagnostic_values
        reveal = lambda _widget: self.page_stack.setCurrentWidget(self.project_page)
        self._project_diagnostics = FormDiagnosticController(
            self.project_page, self.project_page.diagnostics_panel, 'project', fields, snapshot, reveal=reveal)
        self._run_diagnostics = FormDiagnosticController(
            self.run_page, self.run_page.diagnostics_panel, 'project', fields, snapshot, reveal=reveal)
        self.project_page.diagnostics_panel.revalidateRequested.connect(self._validate_project_diagnostics)
        self.run_page.diagnostics_panel.revalidateRequested.connect(self._validate_project_diagnostics)
        self.config_builder_page.diagnosticPageRequested.connect(
            lambda: self.page_stack.setCurrentWidget(self.config_builder_page))
        self.config_builder_page.diagnosticNavigationRequested.connect(self._navigate_config_project_diagnostic)
        self.project_page.projectChanged.connect(self.config_builder_page.invalidate_diagnostics)

    def _navigate_config_project_diagnostic(self, record) -> bool:
        page = self.config_builder_page
        if not page.is_diagnostic_current(record):
            return False
        location = record.location
        if location is None or location.editor not in ('setup', 'project') or location.collection:
            return False
        widget = self.project_page.diagnostic_fields().get(location.field)
        if widget is None:
            page.diagnostic_panel.show_status('No editable control is registered for this diagnostic.', 'warning')
            return False
        result = can_reveal_widget(widget)
        if not result.ok:
            page.diagnostic_panel.show_status('{message}', 'warning', message=result.message)
            return False
        self.page_stack.setCurrentWidget(self.project_page)
        result = reveal_widget(widget)
        if result.ok:
            page.diagnostic_navigator.highlighter.highlight(widget, record.severity, diagnostic_text(record))
        page.diagnostic_panel.show_status('Located {field}. No configuration value was changed.', field=location.field)
        return result.ok

    def _validate_project_diagnostics(self) -> None:
        self._update_project_from_page_without_preview()
        self._present_project_diagnostics(self.runner.validation_report(self.project))

    def _present_project_diagnostics(self, report) -> None:
        for controller in (self._project_diagnostics, self._run_diagnostics):
            controller.set_report(report)
            controller.panel.setVisible(bool(report.diagnostics))

    def _present_raw_run_diagnostic(self, code: str, message: str, *, severity: str = 'error',
                                    raw_message: str | None = None) -> None:
        report = ValidationReport()
        emit_diagnostic(report, code, severity, message, origin='backend',
                        raw_message=message if raw_message is None else raw_message,
                        unavailable_reason='The backend did not provide a structured editable location.')
        self._run_diagnostics.set_report(report)
        self.run_page.diagnostics_panel.show()

    def _invalidate_project_diagnostics(self, *, force: bool = False) -> None:
        self._project_diagnostics.invalidate(force=force)
        self._run_diagnostics.invalidate(force=force)

    def _clear_project_diagnostics(self) -> None:
        for controller in (self._project_diagnostics, self._run_diagnostics):
            controller.clear()
            controller.panel.hide()
