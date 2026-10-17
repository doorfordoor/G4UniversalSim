from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.paths import open_directory
from g4usim_gui.core.i18n import ui_text
from g4usim_gui.history.run_history_model import RunHistoryEntry
from g4usim_gui.history.run_history_scanner import scan_runs_root


class RunHistoryPage(QWidget):
    loadSnapshotRequested = Signal(str)
    openOutputRequested = Signal(str, str)
    duplicateRequested = Signal(str)
    duplicateAndRunRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[RunHistoryEntry] = []
        self._filtered: list[RunHistoryEntry] = []

        self.runs_root = QLineEdit()
        self.search = QLineEdit()
        self.status_filter = QComboBox()
        self.status_filter.addItems(["all", "success", "dry_run", "interactive_no_run", "no_run", "failed", "incomplete", "stopped", "killed"])

        self.browse_button = QPushButton("Browse")
        self.refresh_button = QPushButton("Refresh")
        self.open_root_button = QPushButton("Open runs root")

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "timestamp",
            "run name",
            "status",
            "exit code",
            "template",
            "threads",
            "beamOn",
            "summary",
            "merged",
            "package path",
        ])
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlainText("Select a run to view details, logs, output and rerun options.")
        self.table.setMinimumWidth(620)

        self.load_snapshot_button = QPushButton("Load Snapshot into Project")
        self.open_package_button = QPushButton("Open Package")
        self.open_output_button = QPushButton("Open Output")
        self.open_logs_button = QPushButton("Open Logs")
        self.open_config_button = QPushButton("Open Config")
        self.open_macro_button = QPushButton("Open Macro")
        self.duplicate_button = QPushButton("Duplicate Package")
        self.duplicate_run_button = QPushButton("Duplicate and Rerun")

        self._build_layout()
        self._connect()
        self._update_action_buttons()

    def _build_layout(self) -> None:
        top = QHBoxLayout()
        top.addWidget(QLabel("Runs root"))
        top.addWidget(self.runs_root, 1)
        top.addWidget(self.browse_button)
        top.addWidget(self.refresh_button)
        top.addWidget(self.open_root_button)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Search"))
        filter_row.addWidget(self.search, 1)
        filter_row.addWidget(QLabel("Status"))
        filter_row.addWidget(self.status_filter)

        buttons = QHBoxLayout()
        for button in [
            self.load_snapshot_button,
            self.open_package_button,
            self.open_output_button,
            self.open_logs_button,
            self.open_config_button,
            self.open_macro_button,
            self.duplicate_button,
            self.duplicate_run_button,
        ]:
            buttons.addWidget(button)
        buttons.addStretch(1)

        splitter = QSplitter()
        self.splitter = splitter
        splitter.addWidget(self.table)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 460])

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(filter_row)
        layout.addWidget(splitter, 1)
        layout.addLayout(buttons)

    def _connect(self) -> None:
        self.browse_button.clicked.connect(self._browse_runs_root)
        self.refresh_button.clicked.connect(self.refresh)
        self.open_root_button.clicked.connect(lambda: self._open_dir(self.runs_root.text().strip()))
        self.search.textChanged.connect(self._apply_filter)
        self.status_filter.currentTextChanged.connect(self._apply_filter)
        self.table.itemSelectionChanged.connect(self._show_selected)
        self.load_snapshot_button.clicked.connect(self._emit_load_snapshot)
        self.open_package_button.clicked.connect(lambda: self._open_dir(self._selected().package_dir if self._selected() else ""))
        self.open_output_button.clicked.connect(self._emit_open_output)
        self.open_logs_button.clicked.connect(lambda: self._open_dir(str(Path(self._selected().package_dir) / "logs") if self._selected() else ""))
        self.open_config_button.clicked.connect(lambda: self._open_dir(str(Path(self._selected().package_dir) / "config") if self._selected() else ""))
        self.open_macro_button.clicked.connect(lambda: self._open_dir(str(Path(self._selected().package_dir) / "macros") if self._selected() else ""))
        self.duplicate_button.clicked.connect(self._emit_duplicate)
        self.duplicate_run_button.clicked.connect(self._emit_duplicate_run)

    def set_runs_root(self, runs_root: str) -> None:
        self.runs_root.setText(runs_root)

    def refresh(self) -> None:
        root = self.runs_root.text().strip()
        if root and not Path(root).exists():
            self._entries = []
            self._apply_filter()
            self.details.setPlainText("Runs root does not exist. Create one or choose another directory.")
            return
        self._entries = scan_runs_root(root)
        self._apply_filter()

    def _apply_filter(self) -> None:
        term = self.search.text().strip().lower()
        status = self.status_filter.currentText()
        self._filtered = []
        for entry in self._entries:
            if status != "all" and entry.status != status:
                continue
            haystack = " ".join([entry.run_name, entry.package_dir, entry.geometry_template, entry.status]).lower()
            if term and term not in haystack:
                continue
            self._filtered.append(entry)
        self._populate_table()

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        for entry in self._filtered:
            row = self.table.rowCount()
            self.table.insertRow(row)
            merged = all([entry.merged_hits, entry.merged_event_edep, entry.merged_hist_raw, entry.merged_hist_weighted])
            values = [
                entry.timestamp,
                entry.run_name,
                ui_text(entry.status),
                "" if entry.exit_code is None else str(entry.exit_code),
                entry.geometry_template,
                "" if entry.threads is None else str(entry.threads),
                "" if entry.beam_on is None else str(entry.beam_on),
                "yes" if entry.has_run_summary else "no",
                "yes" if merged else "partial" if any([entry.merged_hits, entry.merged_event_edep, entry.merged_hist_raw, entry.merged_hist_weighted]) else "no",
                entry.package_dir,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        self._show_selected()
        if not self._filtered:
            self.details.setPlainText("No run packages found under this runs root.")
        self._update_action_buttons()

    def _show_selected(self) -> None:
        entry = self._selected()
        if not entry:
            if self._filtered:
                self.details.setPlainText("Select a run to view details, logs, output and rerun options.")
            self._update_action_buttons()
            return
        lines = [
            f"package = {entry.package_dir}",
            f"status = {entry.status}",
            f"result_reason = {ui_text(entry.result_reason)}",
            f"exit_code = {entry.exit_code}",
            f"executable = {entry.executable}",
            f"config = {entry.config_path}",
            f"macro = {entry.macro_path}",
            f"output = {entry.output_dir}",
            f"threads = {entry.threads}",
            f"seed = {entry.seed}",
            f"beam_on = {entry.beam_on}",
            f"template = {entry.geometry_template}",
            f"materials_config = {entry.materials_config}",
            f"geometry_config = {entry.geometry_config}",
            "",
            "[files]",
            f"run_summary = {entry.has_run_summary}",
            f"stdout_log = {entry.has_stdout_log}",
            f"stderr_log = {entry.has_stderr_log}",
            f"validation_report = {entry.has_validation_report}",
            f"project_snapshot = {entry.has_project_snapshot}",
            f"hits_files = {entry.hits_files_count}",
            f"event_edep_files = {entry.event_edep_files_count}",
            f"hist_raw_files = {entry.hist_raw_files_count}",
            f"hist_weighted_files = {entry.hist_weighted_files_count}",
            f"merged_hits = {entry.merged_hits}",
            f"merged_event_edep = {entry.merged_event_edep}",
            f"merged_hist_raw = {entry.merged_hist_raw}",
            f"merged_hist_weighted = {entry.merged_hist_weighted}",
        ]
        if entry.warnings:
            lines.extend(["", "[warnings]", *entry.warnings])
        if entry.errors:
            lines.extend(["", "[errors]", *entry.errors])
        self.details.setPlainText("\n".join(lines))
        self._update_action_buttons()

    def _selected(self) -> RunHistoryEntry | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered):
            return None
        return self._filtered[row]

    def _browse_runs_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select runs root")
        if path:
            self.runs_root.setText(path)
            self.refresh()

    def _emit_load_snapshot(self) -> None:
        entry = self._selected()
        if entry:
            self.loadSnapshotRequested.emit(str(Path(entry.package_dir) / "project_snapshot.json"))

    def _emit_open_output(self) -> None:
        entry = self._selected()
        if entry:
            self.openOutputRequested.emit(entry.package_dir, entry.output_dir)

    def _emit_duplicate(self) -> None:
        entry = self._selected()
        if entry:
            self.duplicateRequested.emit(entry.package_dir)

    def _emit_duplicate_run(self) -> None:
        entry = self._selected()
        if entry:
            self.duplicateAndRunRequested.emit(entry.package_dir)

    def _open_dir(self, path: str) -> None:
        if not path:
            QMessageBox.warning(self, "Open directory failed", "Directory path is empty.")
            return
        try:
            open_directory(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open directory failed", f"{path}\n\n{exc}")

    def _update_action_buttons(self) -> None:
        has_selection = self._selected() is not None
        for button in [
            self.load_snapshot_button,
            self.open_package_button,
            self.open_output_button,
            self.open_logs_button,
            self.open_config_button,
            self.open_macro_button,
            self.duplicate_button,
            self.duplicate_run_button,
        ]:
            button.setEnabled(has_selection)
