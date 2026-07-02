from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.paths import format_size, open_directory
from g4usim_gui.output.csv_preview import read_csv_preview
from g4usim_gui.output.file_classifier import OutputFileInfo, OutputFileType, classify_files
from g4usim_gui.output.merge_plan import MergePlan, MergeTask, build_merge_plan
from g4usim_gui.output.merge_runner import MergeRunner
from g4usim_gui.output.run_summary_parser import parse_run_summary


class OutputPage(QWidget):
    MAX_PREVIEW_BYTES = 50 * 1024 * 1024

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._output_dir = ""
        self._package_dir = ""
        self._workspace_root = ""
        self._files: list[OutputFileInfo] = []
        self._merge_plan = MergePlan([])
        self._selected_file: Path | None = None
        self._merge_runner = MergeRunner(self)

        self.output_label = QLabel("Output directory: <none>")
        self.refresh_button = QPushButton("Refresh")
        self.open_package_button = QPushButton("Open package folder")
        self.open_output_button = QPushButton("Open output folder")

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Name", "Type", "Size", "Path"])
        self.file_tree.setMinimumWidth(300)
        self.file_tree.itemSelectionChanged.connect(self._on_file_selected)

        self.tabs = QTabWidget()
        self.overview_text = QPlainTextEdit()
        self.overview_text.setReadOnly(True)
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.summary_text = QPlainTextEdit()
        self.summary_text.setReadOnly(True)
        self.csv_limit = QComboBox()
        self.csv_limit.addItems(["50", "200", "1000"])
        self.csv_limit.setCurrentText("200")
        self.csv_limit.currentTextChanged.connect(self._refresh_csv_preview)
        self.csv_table = QTableWidget()
        self.csv_message = QLabel("")
        self.merge_table = QTableWidget(0, 7)
        self.merge_table.setHorizontalHeaderLabels(["name", "pattern", "matches", "output", "tool", "available", "reason"])
        self.merge_log = QPlainTextEdit()
        self.merge_log.setReadOnly(True)
        self.logs_text = QPlainTextEdit()
        self.logs_text.setReadOnly(True)

        self._build_layout()
        self._connect_signals()

    def _build_layout(self) -> None:
        top = QHBoxLayout()
        top.addWidget(self.output_label, 1)
        top.addWidget(self.refresh_button)
        top.addWidget(self.open_package_button)
        top.addWidget(self.open_output_button)

        self.tabs.addTab(self.overview_text, "Overview")
        self.tabs.addTab(self.preview_text, "Preview")
        self.tabs.addTab(self.summary_text, "Run Summary")

        csv_tab = QWidget()
        csv_layout = QVBoxLayout(csv_tab)
        row = QHBoxLayout()
        row.addWidget(QLabel("Rows"))
        row.addWidget(self.csv_limit)
        row.addStretch(1)
        csv_layout.addLayout(row)
        csv_layout.addWidget(self.csv_message)
        csv_layout.addWidget(self.csv_table, 1)
        self.tabs.addTab(csv_tab, "CSV Preview")

        merge_tab = QWidget()
        merge_layout = QVBoxLayout(merge_tab)
        merge_buttons = QHBoxLayout()
        self.refresh_merge_button = QPushButton("Refresh merge plan")
        self.run_selected_merge_button = QPushButton("Run selected merge")
        self.run_all_merge_button = QPushButton("Run all available")
        self.cancel_merge_button = QPushButton("Cancel merge")
        merge_buttons.addWidget(self.refresh_merge_button)
        merge_buttons.addWidget(self.run_selected_merge_button)
        merge_buttons.addWidget(self.run_all_merge_button)
        merge_buttons.addWidget(self.cancel_merge_button)
        merge_buttons.addStretch(1)
        merge_layout.addLayout(merge_buttons)
        merge_layout.addWidget(self.merge_table, 2)
        merge_layout.addWidget(QLabel("Merge stdout/stderr"))
        merge_layout.addWidget(self.merge_log, 1)
        self.tabs.addTab(merge_tab, "Merge")
        self.tabs.addTab(self.logs_text, "Logs")

        self.splitter = QSplitter()
        self.splitter.addWidget(self.file_tree)
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([360, 980])

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.splitter, 1)

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self.refresh)
        self.open_package_button.clicked.connect(self.open_package_directory)
        self.open_output_button.clicked.connect(self.open_output_directory)
        self.refresh_merge_button.clicked.connect(self.refresh_merge_plan)
        self.run_selected_merge_button.clicked.connect(self.run_selected_merge)
        self.run_all_merge_button.clicked.connect(self.run_all_available_merges)
        self.cancel_merge_button.clicked.connect(self._merge_runner.cancel)
        self._merge_runner.stdoutReceived.connect(lambda text: self.merge_log.insertPlainText(text))
        self._merge_runner.stderrReceived.connect(lambda text: self.merge_log.insertPlainText(text))
        self._merge_runner.taskStarted.connect(lambda name: self.merge_log.insertPlainText(f"\n[start] {name}\n"))
        self._merge_runner.taskFinished.connect(self._on_merge_finished)
        self._merge_runner.allFinished.connect(self._on_all_merges_finished)
        self._merge_runner.errorOccurred.connect(lambda msg: QMessageBox.warning(self, "Merge error", msg))
        self._merge_runner.stateChanged.connect(self._on_merge_state_changed)

    def set_workspace_root(self, workspace_root: str) -> None:
        self._workspace_root = workspace_root
        self.refresh_merge_plan()

    def set_output_dir(self, output_dir: str) -> None:
        self._output_dir = output_dir
        self._package_dir = self._infer_package_root(output_dir)
        self.output_label.setText(f"Output directory: {output_dir or '<none>'}")
        self.refresh()

    def set_package_dir(self, package_dir: str, output_dir: str) -> None:
        self._package_dir = package_dir
        self._output_dir = output_dir
        self.output_label.setText(f"Package: {package_dir or '<none>'}    Output: {output_dir or '<none>'}")
        self.refresh()

    def refresh(self) -> None:
        self.file_tree.clear()
        self.preview_text.clear()
        root_text = self._package_dir or self._output_dir
        if not root_text:
            self._files = []
            self._update_overview()
            self._update_open_buttons()
            return
        root = Path(root_text)
        if not root.exists():
            self._files = []
            self.preview_text.setPlainText(f"Directory does not exist yet:\n{root}")
            self._update_overview()
            self._update_open_buttons()
            return
        self._files = sorted(classify_files(root), key=self._file_sort_key)
        for info in self._files:
            item = QTreeWidgetItem([info.relative_path, info.file_type.value, format_size(info.size), info.path])
            self.file_tree.addTopLevelItem(item)
        for column in range(3):
            self.file_tree.resizeColumnToContents(column)
        self._update_overview()
        self._update_run_summary()
        self._update_logs_tab()
        self.refresh_merge_plan()
        self._update_open_buttons()

    def refresh_merge_plan(self) -> None:
        if not self._output_dir:
            self._merge_plan = MergePlan([])
        else:
            self._merge_plan = build_merge_plan(self._output_dir, self._workspace_root)
        self._populate_merge_table()
        self._update_merge_buttons(False)

    def open_package_directory(self) -> None:
        target = self._package_dir or self._output_dir
        if not target:
            QMessageBox.warning(self, "No package directory", "Package directory is empty.")
            return
        self._open_directory(target)

    def open_output_directory(self) -> None:
        if not self._output_dir:
            QMessageBox.warning(self, "No output directory", "Output directory is empty.")
            return
        self._open_directory(self._output_dir)

    def run_selected_merge(self) -> None:
        row = self.merge_table.currentRow()
        if row < 0 or row >= len(self._merge_plan.tasks):
            QMessageBox.warning(self, "No merge selected", "Select a merge task first.")
            return
        task = self._merge_plan.tasks[row]
        self._run_merge_tasks([task])

    def run_all_available_merges(self) -> None:
        self._run_merge_tasks([task for task in self._merge_plan.tasks if task.available])

    def _run_merge_tasks(self, tasks: list[MergeTask]) -> None:
        if not tasks:
            QMessageBox.warning(self, "No available merge", "There are no available merge tasks.")
            return
        logs_dir = Path(self._package_dir) / "logs" if self._package_dir else Path(self._output_dir) / "logs"
        self.merge_log.clear()
        self._update_merge_buttons(True)
        self._merge_runner.run_tasks(tasks, logs_dir)

    def _on_file_selected(self) -> None:
        items = self.file_tree.selectedItems()
        if not items:
            return
        self._selected_file = Path(items[0].text(3))
        self._preview_selected_file()
        self._refresh_csv_preview()

    def _preview_selected_file(self) -> None:
        path = self._selected_file
        if not path or not path.exists():
            self.preview_text.setPlainText("No file selected.")
            return
        info = classify_files(path.parent)
        selected_info = next((item for item in info if Path(item.path) == path), None)
        if path.stat().st_size > self.MAX_PREVIEW_BYTES:
            self.preview_text.setPlainText(f"{path}\n\nSize: {format_size(path.stat().st_size)}\nFile is larger than 50 MB.")
            return
        suffix = path.suffix.lower()
        try:
            if suffix == ".json":
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    self.preview_text.setPlainText(json.dumps(json.load(handle), indent=2, ensure_ascii=False))
            elif suffix in {".txt", ".log", ".ini", ".mac", ".csv"}:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    if suffix == ".csv":
                        lines = []
                        for index, line in enumerate(handle):
                            if index >= 200:
                                lines.append("\n... preview truncated at 200 lines ...\n")
                                break
                            lines.append(line)
                        self.preview_text.setPlainText("".join(lines))
                    else:
                        self.preview_text.setPlainText(handle.read())
            else:
                kind = selected_info.file_type.value if selected_info else "unknown"
                self.preview_text.setPlainText(f"{path}\n\nType: {kind}\nSize: {format_size(path.stat().st_size)}")
        except Exception as exc:  # noqa: BLE001
            self.preview_text.setPlainText(f"Failed to preview file:\n{path}\n\n{exc}")

    def _refresh_csv_preview(self) -> None:
        self.csv_table.clear()
        self.csv_table.setRowCount(0)
        self.csv_table.setColumnCount(0)
        path = self._selected_file
        if not path or path.suffix.lower() != ".csv":
            self.csv_message.setText("Select a CSV file to preview.")
            return
        preview = read_csv_preview(path, max_rows=int(self.csv_limit.currentText()), max_bytes=self.MAX_PREVIEW_BYTES)
        if preview.too_large:
            self.csv_message.setText(f"Large CSV: {format_size(preview.size)}. Open externally for full view.")
            return
        self.csv_message.setText("; ".join(preview.warnings) if preview.warnings else f"Previewing {len(preview.rows)} row(s).")
        columns = max(len(preview.header), *(len(row) for row in preview.rows), 1)
        self.csv_table.setColumnCount(columns)
        if preview.header:
            self.csv_table.setHorizontalHeaderLabels(preview.header + [f"col{i}" for i in range(len(preview.header), columns)])
        self.csv_table.setRowCount(len(preview.rows))
        for row_index, row in enumerate(preview.rows):
            for col_index in range(columns):
                self.csv_table.setItem(row_index, col_index, QTableWidgetItem(row[col_index] if col_index < len(row) else ""))
        self.csv_table.resizeColumnsToContents()

    def _update_overview(self) -> None:
        counts: dict[str, int] = {}
        for info in self._files:
            counts[info.file_type.value] = counts.get(info.file_type.value, 0) + 1
        thread_csv = sum(counts.get(kind.value, 0) for kind in [
            OutputFileType.HITS_THREAD_CSV,
            OutputFileType.EVENT_EDEP_THREAD_CSV,
            OutputFileType.HIST_EDEP_RAW_THREAD_CSV,
            OutputFileType.HIST_EDEP_WEIGHTED_THREAD_CSV,
        ])
        merged = sum(counts.get(kind.value, 0) for kind in [
            OutputFileType.HITS_MERGED_CSV,
            OutputFileType.EVENT_EDEP_MERGED_CSV,
            OutputFileType.HIST_EDEP_RAW_MERGED_CSV,
            OutputFileType.HIST_EDEP_WEIGHTED_MERGED_CSV,
        ])
        lines = [
            f"package root = {self._package_dir or '<none>'}",
            f"output dir = {self._output_dir or '<none>'}",
            f"files = {len(self._files)}",
            f"thread CSV files = {thread_csv}",
            f"merged files = {merged}",
            f"run_summary exists = {str(counts.get(OutputFileType.RUN_SUMMARY.value, 0) > 0).lower()}",
            f"validation_report exists = {str(counts.get(OutputFileType.VALIDATION_REPORT.value, 0) > 0).lower()}",
            "",
        ]
        if not self._files:
            lines.extend([
                "No output files found. Run a simulation or select a package/output directory.",
                "",
            ])
        if not self._package_dir:
            lines.extend([
                "Current output directory is not recognized as a generated run package.",
                "",
            ])
        lines.extend([
            "[file types]",
        ])
        lines.extend(f"{key} = {value}" for key, value in sorted(counts.items()))
        self.overview_text.setPlainText("\n".join(lines))

    def _update_run_summary(self) -> None:
        path = self._find_first(OutputFileType.RUN_SUMMARY)
        if not path:
            self.summary_text.setPlainText("run_summary.txt not found.")
            return
        summary = parse_run_summary(path)
        lines = [f"path = {summary.path}", f"exists = {str(summary.exists).lower()}", "", "[key values]"]
        if summary.key_values:
            lines.extend(f"{key} = {value}" for key, value in sorted(summary.key_values.items()))
        else:
            lines.append("<none>")
        lines.extend(["", "[raw]", summary.raw_text])
        if summary.warnings:
            lines.extend(["", "[warnings]", *summary.warnings])
        self.summary_text.setPlainText("\n".join(lines))

    def _update_logs_tab(self) -> None:
        chunks: list[str] = []
        for kind in [OutputFileType.STDOUT_LOG, OutputFileType.STDERR_LOG, OutputFileType.VALIDATION_REPORT]:
            path = self._find_first(kind)
            if not path:
                continue
            chunks.append(f"===== {Path(path).name} =====")
            try:
                chunks.append(Path(path).read_text(encoding="utf-8", errors="replace"))
            except Exception as exc:  # noqa: BLE001
                chunks.append(f"Failed to read {path}: {exc}")
        self.logs_text.setPlainText("\n\n".join(chunks) if chunks else "No logs found.")

    def _populate_merge_table(self) -> None:
        self.merge_table.setRowCount(0)
        for task in self._merge_plan.tasks:
            row = self.merge_table.rowCount()
            self.merge_table.insertRow(row)
            values = [
                task.name,
                task.pattern,
                str(len(task.matched_files)),
                task.output_file,
                task.tool_type,
                "yes" if task.available else "no",
                task.reason,
            ]
            for col, value in enumerate(values):
                self.merge_table.setItem(row, col, QTableWidgetItem(value))
        self.merge_table.resizeColumnsToContents()

    def _on_merge_finished(self, name: str, exit_code: int) -> None:
        self.merge_log.insertPlainText(f"\n[finished] {name}, exit code={exit_code}\n")
        if exit_code != 0:
            QMessageBox.warning(self, "Merge failed", f"{name} failed with exit code {exit_code}.")

    def _on_all_merges_finished(self) -> None:
        self.merge_log.insertPlainText("\n[all merge tasks finished]\n")
        self._update_merge_buttons(False)
        self.refresh()

    def _on_merge_state_changed(self, state: str) -> None:
        self._update_merge_buttons(state in {"Starting", "Running"})

    def _update_merge_buttons(self, running: bool) -> None:
        any_available = any(task.available for task in self._merge_plan.tasks)
        self.refresh_merge_button.setEnabled(not running)
        self.run_selected_merge_button.setEnabled(not running and any_available)
        self.run_all_merge_button.setEnabled(not running and any_available)
        self.cancel_merge_button.setEnabled(running)

    def _find_first(self, kind: OutputFileType) -> str:
        for info in self._files:
            if info.file_type == kind:
                return info.path
        return ""

    def _open_directory(self, path: str) -> None:
        try:
            open_directory(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open directory failed", str(exc))

    def _infer_package_root(self, output_dir: str) -> str:
        if not output_dir:
            return ""
        output = Path(output_dir)
        parent = output.parent
        if all((parent / name).exists() for name in ["config", "macros", "logs", "output"]):
            return str(parent)
        snapshot = parent / "project_snapshot.json"
        if snapshot.exists():
            return str(parent)
        return ""

    def _file_sort_key(self, info: OutputFileInfo) -> tuple[int, str]:
        priority = {
            OutputFileType.RUN_SUMMARY: 0,
            OutputFileType.VALIDATION_REPORT: 1,
            OutputFileType.STDOUT_LOG: 2,
            OutputFileType.STDERR_LOG: 3,
            OutputFileType.HITS_MERGED_CSV: 4,
            OutputFileType.EVENT_EDEP_MERGED_CSV: 5,
            OutputFileType.HIST_EDEP_RAW_MERGED_CSV: 6,
            OutputFileType.HIST_EDEP_WEIGHTED_MERGED_CSV: 7,
        }
        return (priority.get(info.file_type, 50), info.relative_path.lower())

    def _update_open_buttons(self) -> None:
        self.open_package_button.setEnabled(bool(self._package_dir and Path(self._package_dir).exists()))
        self.open_output_button.setEnabled(bool(self._output_dir))
