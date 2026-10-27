from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text


class RunPage(QWidget):
    buildCommandRequested = Signal()
    inspectMacroRequested = Signal()
    runRequested = Signal()
    stopRequested = Signal()
    killRequested = Signal()
    saveLogsRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_elapsed)
        self._elapsed = QElapsedTimer()
        self._current_state = "Not running"
        self._exit_code: int | None = None
        self._result_state = ""
        self._progress_data = None
        self._progress_state = "idle"

        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumBlockCount(1000)
        self.command_preview.setMaximumHeight(110)

        self.stdout_view = QPlainTextEdit()
        self.stdout_view.setReadOnly(True)
        self.stderr_view = QPlainTextEdit()
        self.stderr_view.setReadOnly(True)
        self.merged_view = QPlainTextEdit()
        self.merged_view.setReadOnly(True)
        self.macro_plan_view = QPlainTextEdit()
        self.macro_plan_view.setReadOnly(True)
        self.macro_plan_view.setMaximumBlockCount(5000)

        tabs = QTabWidget()
        tabs.addTab(self.stdout_view, "stdout")
        tabs.addTab(self.stderr_view, "stderr")
        tabs.addTab(self.merged_view, "merged log")
        tabs.addTab(self.macro_plan_view, "Run plan")

        self.progress_bar = QProgressBar()
        self.progress_label = QLabel()
        self.progress_label.setWordWrap(True)
        self._render_progress()

        self.state_label = QLabel("State: Not running")
        self.exit_label = QLabel("Exit code: -")
        self.result_label = QLabel("")
        self.elapsed_label = QLabel("Elapsed: 00:00:00")
        status = QHBoxLayout()
        status.addWidget(self.state_label)
        status.addWidget(self.exit_label)
        status.addWidget(self.result_label)
        status.addWidget(self.elapsed_label)
        status.addStretch(1)

        self.build_button = QPushButton("Build command")
        self.inspect_macro_button = QPushButton("Inspect inputs")
        self.run_button = QPushButton("Run")
        self.stop_button = QPushButton("Stop")
        self.kill_button = QPushButton("Kill")
        self.clear_button = QPushButton("Clear log")
        self.save_logs_button = QPushButton("Save logs")
        self.stop_button.setEnabled(False)
        self.kill_button.setEnabled(False)

        self.build_button.clicked.connect(self.buildCommandRequested.emit)
        self.inspect_macro_button.clicked.connect(self.inspectMacroRequested.emit)
        self.run_button.clicked.connect(self.runRequested.emit)
        self.stop_button.clicked.connect(self.stopRequested.emit)
        self.kill_button.clicked.connect(self.killRequested.emit)
        self.clear_button.clicked.connect(self.clear_logs)
        self.save_logs_button.clicked.connect(self.saveLogsRequested.emit)

        buttons = QHBoxLayout()
        for button in [
            self.build_button,
            self.inspect_macro_button,
            self.run_button,
            self.stop_button,
            self.kill_button,
            self.clear_button,
            self.save_logs_button,
        ]:
            buttons.addWidget(button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Build the command first when paths change. Validation errors usually point back to the Project page."))
        layout.addWidget(QLabel("Command preview"))
        layout.addWidget(self.command_preview)
        layout.addLayout(buttons)
        layout.addLayout(status)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)
        layout.addWidget(tabs, 1)

    def set_progress(self, message: dict) -> None:
        if self._progress_state not in {"starting", "active"}:
            return
        self._progress_data = message
        self._progress_state = "active"
        self._render_progress()

    def set_progress_state(self, state: str) -> None:
        if state == "starting":
            self._progress_data = None
        self._progress_state = state
        self._render_progress()

    def _render_progress(self) -> None:
        data = self._progress_data
        active = self._progress_state in {"starting", "active"}
        planned = data.get("planned_events") if data else None
        completed = data.get("completed_events") if data else None
        if planned and completed is not None:
            self.progress_bar.setRange(0, 1000)
            self.progress_bar.setValue(min(1000, completed * 1000 // planned))
            # Keep the machine count readable even when the OS locale selects
            # non-decimal display glyphs (e.g. zh_HK Suzhou numerals).
            self.progress_bar.setFormat(f"{min(100, completed * 100 // planned)}%")
        else:
            self.progress_bar.setRange(0, 0 if active else 1000)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat(ui_text("Unknown progress"))
        if data:
            unknown = ui_text("Unknown")
            rate = data.get("rate_eps")
            eta = data.get("eta_s")
            text = ui_format(
                "Run {run}: {completed}/{planned} events | {phase} | {rate} events/s | ETA {eta}",
                run=data["run_id"], completed=completed if completed is not None else unknown,
                planned=planned if planned is not None else unknown,
                phase=ui_text("Progress finishing" if data["phase"] == "running" and planned is not None and completed == planned else "Progress " + data["phase"]),
                rate=f"{rate:.1f}" if rate is not None else unknown,
                eta=ui_format("{seconds} s", seconds=f"{eta:.1f}") if eta is not None else unknown,
            )
        else:
            text = ui_text("Waiting for backend progress; older backends may not report it.")
        if not active and self._progress_state != "idle":
            text += " | " + ui_format("Progress frozen: {state}; see final result.", state=ui_text(self._progress_state))
        self.progress_label.setText(text)

    def set_command(self, command: list[str]) -> None:
        self.command_preview.setPlainText("\n".join(command))

    def set_macro_plan(self, text: str) -> None:
        self.macro_plan_view.setPlainText(text)

    def append_stdout(self, text: str) -> None:
        self.stdout_view.insertPlainText(text)
        self.stdout_view.ensureCursorVisible()
        self._append_merged(text, "stdout")

    def append_stderr(self, text: str) -> None:
        self.stderr_view.insertPlainText(text)
        self.stderr_view.ensureCursorVisible()
        self._append_merged(text, "stderr")

    def append_status_message(self, text: str) -> None:
        self._append_merged(f"[gui] {text}\n", "gui")

    def set_state(self, state: str) -> None:
        self._current_state = state
        self.state_label.setText(ui_format("State: {state}", state=ui_text(state)))
        running = state in {"Starting", "Running"}
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.kill_button.setEnabled(running)
        if running and not self._timer.isActive():
            self._elapsed.restart()
            self._timer.start(500)
        elif not running:
            self._timer.stop()

    def set_exit_code(self, code: int) -> None:
        self._exit_code = code
        self.exit_label.setText(ui_format("Exit code: {code}", code=code))
        self.set_state("Not running")

    def set_result(self, state: str) -> None:
        self._result_state = state
        self.result_label.setText(ui_format("Result: {state}", state=ui_text(state)) if state else "")

    def refresh_language(self) -> None:
        self._render_progress()
        self.state_label.setText(ui_format("State: {state}", state=ui_text(self._current_state)))
        code = "-" if self._exit_code is None else self._exit_code
        self.exit_label.setText(ui_format("Exit code: {code}", code=code))
        if self._result_state:
            self.set_result(self._result_state)
        self._update_elapsed()

    def clear_logs(self) -> None:
        self.stdout_view.clear()
        self.stderr_view.clear()
        self.merged_view.clear()

    def _append_merged(self, text: str, stream: str) -> None:
        prefix = f"[{stream}] "
        for line in text.splitlines(True):
            self.merged_view.insertPlainText(prefix + line)
        self.merged_view.ensureCursorVisible()

    def _update_elapsed(self) -> None:
        seconds = self._elapsed.elapsed() // 1000 if self._elapsed.isValid() else 0
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        self.elapsed_label.setText(
            ui_format("Elapsed: {elapsed}", elapsed=f"{hours:02d}:{minutes:02d}:{secs:02d}")
        )
