from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from g4usim_gui.output.merge_plan import MergeTask
from g4usim_gui.output.provenance import output_evidence


class MergeRunner(QObject):
    stdoutReceived = Signal(str)
    stderrReceived = Signal(str)
    stateChanged = Signal(str)
    taskStarted = Signal(str)
    taskFinished = Signal(str, int)
    allFinished = Signal()
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._queue: list[MergeTask] = []
        self._current: MergeTask | None = None
        self._stdout_file = None
        self._stderr_file = None
        self._logs_dir = Path.cwd()

        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._process.stateChanged.connect(self._on_state_changed)

    def is_running(self) -> bool:
        return self._process.state() != QProcess.NotRunning

    def run_task(self, task: MergeTask, logs_dir: str | Path) -> None:
        self.run_tasks([task], logs_dir)

    def run_tasks(self, tasks: list[MergeTask], logs_dir: str | Path) -> None:
        if self.is_running():
            self.errorOccurred.emit("A merge process is already running.")
            return
        self._queue = [task for task in tasks if task.available]
        self._logs_dir = Path(logs_dir)
        self._logs_dir.mkdir(parents=True, exist_ok=True)
        if not self._queue:
            self.errorOccurred.emit("No available merge tasks to run.")
            return
        self._start_next()

    def cancel(self) -> None:
        self._queue.clear()
        if self.is_running():
            self._process.terminate()

    def kill(self) -> None:
        self._queue.clear()
        if self.is_running():
            self._process.kill()

    def _start_next(self) -> None:
        if not self._queue:
            self._current = None
            self.allFinished.emit()
            return
        self._current = self._queue.pop(0)
        if self._current.automatic_inputs:
            try:
                evidence = output_evidence(self._current.input_dir, fresh=True)
                if (evidence.status != self._current.provenance_status or
                        evidence.manifest_digest != self._current.manifest_digest):
                    raise ValueError("Output provenance changed after the merge plan was created; refresh the plan.")
                current = [str(p) for p in evidence.matching(self._current.pattern)]
                if current != self._current.matched_files:
                    raise ValueError("Output inputs changed after the merge plan was created; refresh the plan.")
            except ValueError as error:
                self._queue.clear()
                self._current = None
                self.errorOccurred.emit(str(error))
                self.allFinished.emit()
                return
        self._close_logs()
        self._stdout_file = (self._logs_dir / f"{self._current.log_prefix}_stdout.log").open("w", encoding="utf-8", newline="\n")
        self._stderr_file = (self._logs_dir / f"{self._current.log_prefix}_stderr.log").open("w", encoding="utf-8", newline="\n")
        self.taskStarted.emit(self._current.name)
        self._process.setProgram(self._current.command_program)
        self._process.setArguments(self._current.command_args)
        self._process.start()

    def _read_stdout(self) -> None:
        text = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if self._stdout_file:
            self._stdout_file.write(text)
            self._stdout_file.flush()
        self.stdoutReceived.emit(text)

    def _read_stderr(self) -> None:
        text = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        if self._stderr_file:
            self._stderr_file.write(text)
            self._stderr_file.flush()
        self.stderrReceived.emit(text)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        name = self._current.name if self._current else "<none>"
        self._close_logs()
        self.taskFinished.emit(name, exit_code)
        if exit_code != 0:
            self._queue.clear()
            self.allFinished.emit()
            return
        self._start_next()

    def _on_error(self, error: QProcess.ProcessError) -> None:
        self.errorOccurred.emit(f"QProcess error: {getattr(error, 'name', str(error))}")

    def _on_state_changed(self, state: QProcess.ProcessState) -> None:
        names = {
            QProcess.NotRunning: "Not running",
            QProcess.Starting: "Starting",
            QProcess.Running: "Running",
        }
        self.stateChanged.emit(names.get(state, "Unknown"))

    def _close_logs(self) -> None:
        if self._stdout_file:
            self._stdout_file.close()
            self._stdout_file = None
        if self._stderr_file:
            self._stderr_file.close()
            self._stderr_file = None
