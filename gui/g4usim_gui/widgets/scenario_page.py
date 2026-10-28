"""Shielding and coating scenario page (roadmap 2B).

The page is a thin Qt view over ``core.scenario_shielding``: the field list comes from
that module (basic + advanced), validation uses the same configuration schema as the
editor, generation goes through ``scenario_model`` and the run is a QProcess so the Qt
main thread stays free.  Results are shown with their evidence label; a missing
statistics file is an error, never a zero result.

The page never decides whether a result is "good": it shows what the analysis report
and run_summary.txt say, with warnings, and says so in the evidence panel.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core import scenario_shielding as shielding
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.install_layout import default_runs_root

_COLUMNS = ("Group", "Label", "Value", "Unit", "Evidence")
_MAX_LOG_LINES = 5000


class ScenarioPage(QWidget):
    """Run the shielding/coating scenario and show TID/DDD/transmission with evidence."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._executable = ""
        self._generated: shielding.GeneratedScenario | None = None
        self._outcome: shielding.ScenarioOutcome | None = None
        self._rows: list[dict[str, str]] = []
        self._process: QProcess | None = None
        self._log_buffer = ""
        self._fields: dict[str, QWidget] = {}

        title = QLabel(ui_text("Shielding and coating scenario"))
        title.setObjectName("pageSectionTitle")
        description = QLabel(ui_text(
            "Set the layer stack, run the real backend and read TID, DDD, transmission "
            "and albedo together with the evidence each number comes from."))
        description.setWordWrap(True)
        description.setObjectName("pageHint")

        self.directory_edit = QLineEdit()
        self.directory_edit.setText(str(default_runs_root() / "scenario_shielding"))
        self.directory_edit.setToolTip(ui_text("Working directory for the generated scenario and its output."))
        self.browse_button = QPushButton(ui_text("Browse..."))
        self.browse_button.clicked.connect(self._browse_directory)

        directory_row = QHBoxLayout()
        directory_row.addWidget(QLabel(ui_text("Working directory")))
        directory_row.addWidget(self.directory_edit, 1)
        directory_row.addWidget(self.browse_button)

        self.basic_group = QGroupBox(ui_text("Scenario"))
        self.basic_form = QFormLayout(self.basic_group)
        for field in shielding.visible_fields():
            self._add_field(self.basic_form, field)

        self.advanced_check = QCheckBox(ui_text("Show advanced fields"))
        self.advanced_check.toggled.connect(self._toggle_advanced)
        self.advanced_group = QGroupBox(ui_text("Advanced"))
        self.advanced_form = QFormLayout(self.advanced_group)
        for field in shielding.visible_fields(advanced=True):
            self._add_field(self.advanced_form, field)
        self.advanced_group.setVisible(False)

        self.validate_button = QPushButton(ui_text("Validate"))
        self.validate_button.clicked.connect(self.validate_form)
        self.generate_button = QPushButton(ui_text("Generate scenario files"))
        self.generate_button.clicked.connect(self.generate_scenario)
        self.run_button = QPushButton(ui_text("Run scenario"))
        self.run_button.setProperty("buttonRole", "primary")
        self.run_button.clicked.connect(self.start_run)
        self.stop_button = QPushButton(ui_text("Stop"))
        self.stop_button.setProperty("buttonRole", "danger")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_run)
        buttons = QHBoxLayout()
        buttons.addWidget(self.validate_button)
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.run_button)
        buttons.addStretch(1)
        buttons.addWidget(self.stop_button)

        self.status_label = QLabel(ui_text("Not run yet."))
        self.status_label.setObjectName("statusChip")

        self.problems_view = QPlainTextEdit()
        self.problems_view.setReadOnly(True)
        self.problems_view.setMaximumBlockCount(200)
        self.problems_view.setPlaceholderText(ui_text("Validation messages"))
        self.problems_view.setFixedHeight(64)

        self.results_table = QTableWidget(0, len(_COLUMNS))
        self.results_table.setHorizontalHeaderLabels([ui_text(text) for text in _COLUMNS])
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        self.evidence_view = QPlainTextEdit()
        self.evidence_view.setReadOnly(True)
        self.evidence_view.setMaximumBlockCount(200)
        self.evidence_view.setPlaceholderText(ui_text("Evidence and warnings"))

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(_MAX_LOG_LINES)
        self.log_view.setObjectName("scenarioLog")

        results_split = QSplitter()
        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(QLabel(ui_text("Results")))
        results_layout.addWidget(self.results_table, 1)
        results_layout.addWidget(QLabel(ui_text("Evidence and warnings")))
        results_layout.addWidget(self.evidence_view, 1)
        results_split.addWidget(results_panel)
        log_panel = QWidget()
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(QLabel(ui_text("Backend log")))
        log_layout.addWidget(self.log_view, 1)
        results_split.addWidget(log_panel)
        results_split.setSizes([900, 500])

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(title)
        left_layout.addWidget(description)
        left_layout.addLayout(directory_row)
        left_layout.addWidget(self.basic_group)
        left_layout.addWidget(self.advanced_check)
        left_layout.addWidget(self.advanced_group)
        left_layout.addLayout(buttons)
        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.problems_view)
        left_layout.addStretch(1)

        main = QHBoxLayout(self)
        main.addWidget(left, 1)
        main.addWidget(results_split, 2)

        self._refresh_field_states()

    # ------------------------------------------------------------------ form fields

    def _add_field(self, form: QFormLayout, field: shielding.ScenarioField) -> None:
        label = QLabel(ui_text(field.label))
        if field.help:
            label.setToolTip(ui_text(field.help))
        if field.kind == "choice":
            widget: QWidget = QComboBox()
            for choice in field.choices:
                widget.addItem(choice, choice)
            widget.setToolTip(ui_text(field.help) if field.help else "")
            widget.currentIndexChanged.connect(self._refresh_field_states)
        else:
            widget = QLineEdit()
            widget.setText(field.default)
            widget.setPlaceholderText(ui_text(field.help) if field.help else "")
            widget.setToolTip(ui_text(field.help) if field.help else "")
            widget.textEdited.connect(self._refresh_field_states)
        self._fields[field.key] = widget
        form.addRow(label, widget)

    def values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for key, widget in self._fields.items():
            if isinstance(widget, QComboBox):
                values[key] = str(widget.currentData())
            else:
                values[key] = widget.text()
        return values

    def set_values(self, values: dict[str, str]) -> None:
        for key, value in values.items():
            widget = self._fields.get(key)
            if widget is None:
                raise KeyError(key)
            if isinstance(widget, QComboBox):
                index = widget.findData(value)
                if index < 0:
                    raise ValueError(f"{key} must be one of {[widget.itemData(i) for i in range(widget.count())]}")
                widget.setCurrentIndex(index)
            else:
                widget.setText(value)
        self._refresh_field_states()

    def set_directory(self, path: str | Path) -> None:
        self.directory_edit.setText(str(path))

    def directory(self) -> Path:
        text = self.directory_edit.text().strip()
        return Path(text) if text else default_runs_root() / "scenario_shielding"

    def set_executable(self, executable: str | Path) -> None:
        self._executable = str(executable)

    def _toggle_advanced(self, shown: bool) -> None:
        self.advanced_group.setVisible(shown)
        self._refresh_field_states()

    def _refresh_field_states(self) -> None:
        problems = self.validate_form(update_ui=False)
        self.run_button.setEnabled(not problems and self._process is None)
        self.generate_button.setEnabled(self._process is None)
        self.validate_button.setEnabled(self._process is None)

    # --------------------------------------------------------------------- validation

    def validate_form(self, *, update_ui: bool = True) -> list[str]:
        problems = shielding.validate_values(self.values())
        if update_ui:
            self._show_problems(problems)
            self.status_label.setText(
                ui_text("The form is valid.") if not problems else ui_text("Fix the validation messages first."))
        return problems

    def _show_problems(self, problems: list[str]) -> None:
        self.problems_view.setPlainText("\n".join(ui_text(problem) for problem in problems))
        self.problems_view.setVisible(bool(problems))

    # --------------------------------------------------------------------- generate

    def _prepare_directory(self, directory: Path) -> None:
        if directory.exists():
            if not directory.is_dir():
                raise shielding.ScenarioRunError(
                    f"The working directory {directory} is not a directory.")
            looks_like_scenario = (directory / "main.ini").is_file() or (directory / "scenario.json").is_file()
            has_content = any(directory.iterdir())
            if has_content and not looks_like_scenario:
                raise shielding.ScenarioRunError(
                    f"The working directory {directory} is not empty and does not look like a "
                    "scenario folder; choose an empty or previously generated directory.")
            shielding.cleanup_directory(directory)
        directory.mkdir(parents=True, exist_ok=True)

    def generate_scenario(self) -> shielding.GeneratedScenario | None:
        directory = self.directory()
        try:
            self._prepare_directory(directory)
            self._generated = shielding.generate(self.values(), directory)
        except shielding.ScenarioRunError as exc:
            self._show_problems([str(exc)])
            self.status_label.setText(ui_text("The scenario was not generated."))
            return None
        self.problems_view.clear()
        self.status_label.setText(ui_format("Scenario files written to {path}", path=str(directory)))
        self._rows = []
        self._fill_rows()
        self.evidence_view.clear()
        return self._generated

    # -------------------------------------------------------------------------- run

    def _resolve_executable(self) -> str:
        if self._executable:
            return self._executable
        from g4usim_gui.core.install_layout import default_backend_executable  # noqa: PLC0415

        return default_backend_executable()

    def start_run(self) -> bool:
        if self._process is not None:
            return False
        if self.validate_form(update_ui=True):
            return False
        executable = self._resolve_executable()
        if not executable or not Path(executable).is_file():
            self._show_problems([ui_format("The backend executable was not found: {path}", path=executable or "?")])
            self.status_label.setText(ui_text("The scenario was not started."))
            return False
        generated = self.generate_scenario()
        if generated is None:
            return False
        self._outcome = None
        self._log_buffer = ""
        self.log_view.clear()
        process = QProcess(self)
        self._process = process
        process.setWorkingDirectory(str(generated.directory))
        process.setProcessChannelMode(QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(lambda: self._read_process(process, stderr=False))
        process.readyReadStandardError.connect(lambda: self._read_process(process, stderr=True))
        process.finished.connect(lambda code, _status: self._on_finished(code))
        process.errorOccurred.connect(self._on_process_error)
        self.status_label.setText(ui_text("Running the backend..."))
        self.stop_button.setEnabled(True)
        self._refresh_field_states()
        self.log_view.appendPlainText("$ " + executable + " --config main.ini")
        process.start(executable, ["--config", "main.ini"])
        return True

    @property
    def is_running(self) -> bool:
        return self._process is not None

    def _read_process(self, process: QProcess, *, stderr: bool) -> None:
        if stderr:
            data = bytes(process.readAllStandardError())
        else:
            data = bytes(process.readAllStandardOutput())
        if not data:
            return
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        for line in text.splitlines():
            self.log_view.appendPlainText(line)

    def stop_run(self) -> None:
        if self._process is not None:
            self._process.kill()
            self.status_label.setText(ui_text("Stopping the backend..."))

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        if self._process is None:
            return
        self._show_problems([ui_format("The backend process failed: {error}", error=str(error))])

    def _on_finished(self, exit_code: int) -> None:
        process = self._process
        self._process = None
        self.stop_button.setEnabled(False)
        generated = self._generated
        if generated is None or process is None:
            self._refresh_field_states()
            return
        outcome = shielding.ScenarioOutcome(
            generated=generated,
            command=(self._resolve_executable(), "--config", "main.ini"),
            exit_code=exit_code,
            duration_seconds=0.0,
            log_path=generated.directory / "backend.log",
        )
        outcome.log_path.write_bytes(
            self.log_view.toPlainText().replace("\r\n", "\n").encode("utf-8"))
        outcome.summary = shielding.read_summary(generated.output_directory)
        if exit_code != 0:
            outcome.error = shielding.describe_failure(outcome.summary, exit_code)
            self.status_label.setText(ui_format("The scenario run failed (exit code {code}).", code=exit_code))
            self._show_problems([outcome.error])
            self._rows = []
            self._fill_rows()
            self.evidence_view.setPlainText(ui_text(outcome.error))
            self._refresh_field_states()
            return
        try:
            outcome.report = shielding.analyse(generated)
        except shielding.ScenarioRunError as exc:
            outcome.error = str(exc)
            self.status_label.setText(ui_text("The run finished but the analysis refused the output."))
            self._show_problems([outcome.error])
            self._rows = []
            self._fill_rows()
            self.evidence_view.setPlainText(ui_text("No result: ") + ui_text(str(exc)))
            self._refresh_field_states()
            return
        self.status_label.setText(
            ui_format("Scenario run finished: {events} events, {status}.",
                      events=outcome.summary.get("run_0_completed_events", "?"),
                      status=outcome.summary.get("status", "unknown")))
        self.problems_view.clear()
        self._outcome = outcome
        self._rows = shielding.result_rows(outcome.report)
        self._fill_rows()
        lines = shielding.evidence_summary(outcome.report)
        self.evidence_view.setPlainText("\n".join(ui_text(line) for line in lines))
        for warning in outcome.warnings:
            self.log_view.appendPlainText("[warning] " + ui_text(warning))
        self._refresh_field_states()

    # ---------------------------------------------------------------------- results

    def _fill_rows(self) -> None:
        self.results_table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            for column, key in enumerate(("group", "label", "value", "unit", "evidence")):
                item = QTableWidgetItem(ui_text(row.get(key, "")))
                self.results_table.setItem(row_index, column, item)
        self.results_table.resizeColumnsToContents()

    def result_rows(self) -> list[dict[str, str]]:
        return list(self._rows)

    def evidence_lines(self) -> list[str]:
        return self.evidence_view.toPlainText().splitlines()

    def status_text(self) -> str:
        return self.status_label.text()

    def log_text(self) -> str:
        return self.log_view.toPlainText()

    @property
    def outcome(self) -> shielding.ScenarioOutcome | None:
        return self._outcome

    # ------------------------------------------------------------------ misc / i18n

    def _browse_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, ui_text("Choose the scenario working directory"),
                                                     str(self.directory()))
        if directory:
            self.directory_edit.setText(directory)

    def refresh_language(self) -> None:
        self.results_table.setHorizontalHeaderLabels([ui_text(text) for text in _COLUMNS])

    def refresh_theme(self) -> None:
        """Nothing is painted by hand yet; the page keeps the palette from the stylesheet."""

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._process is not None:
            self._process.kill()
            self._process = None
        super().closeEvent(event)
