from __future__ import annotations

import json
import codecs
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from g4usim_gui.core.run_progress import ProgressParser
from g4usim_gui.core.log_parser import parse_log_line
from g4usim_gui.core.paths import ensure_directory
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.project_diagnostics import validate_project_report
from g4usim_gui.core.run_result import RunResult, evaluate_run_result, summary_fingerprint


class G4USimRunner(QObject):
    progressReceived = Signal(object)
    progressStateChanged = Signal(str)
    stdoutReceived = Signal(str)
    stderrReceived = Signal(str)
    stateChanged = Signal(str)
    finished = Signal(int)
    errorOccurred = Signal(str)
    logTagDetected = Signal(str, str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._stdout_file = None
        self._stderr_file = None
        self._output_dir: Path | None = None
        self._logs_dir: Path | None = None
        self._run_status_path: Path | None = None
        self._status_data: dict = {}
        self._requested_state: str = ""
        self._summary_path: Path | None = None
        self._summary_before: tuple[int, int] | None = None
        self.last_result: RunResult | None = None
        self._progress = ProgressParser()
        self._stdout_decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._stderr_decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._progress_frozen = False
        # readyRead delivers whatever bytes arrived, so a log line can be split across
        # chunks. ``parse_log_line`` needs whole lines, so keep the unterminated tail of
        # each stream here and feed it with the next chunk (flushed when the run ends).
        self._log_tails: dict[str, str] = {"stdout": "", "stderr": ""}

        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._process.stateChanged.connect(self._on_state_changed)

    @staticmethod
    def validate_project(project: G4USimProject, *, ready_to_run: bool = False) -> list[str]:
        return validate_project_report(project, ready_to_run=ready_to_run).errors

    @staticmethod
    def validation_report(project: G4USimProject, *, ready_to_run: bool = False):
        return validate_project_report(project, ready_to_run=ready_to_run)

    @staticmethod
    def build_command(project: G4USimProject) -> list[str]:
        args: list[str] = []
        if project.configPath:
            args.extend(["--config", project.configPath])
        if project.macroPath:
            args.extend(["--macro", project.macroPath])
        if project.outputDir:
            args.extend(["--output", project.outputDir])
        if project.threads:
            args.extend(["--threads", str(project.threads)])
        if project.seed:
            args.extend(["--seed", str(project.seed)])
        if project.runName:
            args.extend(["--run-name", project.runName])
        return [project.executable, *args]

    def is_running(self) -> bool:
        return self._process.state() != QProcess.NotRunning

    def start(self, project: G4USimProject, command: list[str] | None = None) -> None:
        if self.is_running():
            self.errorOccurred.emit("A run is already active.")
            return

        errors = self.validate_project(project, ready_to_run=True)
        if errors:
            self.errorOccurred.emit("\n".join(errors))
            return

        self._output_dir = ensure_directory(project.outputDir)
        logs_dir = self._resolve_logs_dir(self._output_dir)
        self._logs_dir = logs_dir
        logs_dir.mkdir(parents=True, exist_ok=True)
        self._stdout_file = (logs_dir / "stdout.log").open("w", encoding="utf-8", newline="\n")
        self._stderr_file = (logs_dir / "stderr.log").open("w", encoding="utf-8", newline="\n")

        command = list(command) if command is not None else self.build_command(project)
        self._run_status_path = logs_dir / "run_status.json"
        self._summary_path = self._output_dir / "run_summary.txt"
        self._summary_before = summary_fingerprint(self._summary_path)
        self.last_result = None
        self._progress = ProgressParser()
        self._stdout_decoder.reset()
        self._stderr_decoder.reset()
        self._progress_frozen = False
        self._log_tails = {"stdout": "", "stderr": ""}
        self.progressStateChanged.emit("starting")
        self._requested_state = ""
        self._status_data = {
            "state": "running",
            "startedAt": _now_iso(),
            "command": command,
            "program": command[0],
            "arguments": command[1:],
            "workingDirectory": project.workspaceRoot,
        }
        self._write_run_status()
        program = command[0]
        arguments = command[1:]
        self._process.setProgram(program)
        self._process.setArguments(arguments)
        if project.workspaceRoot:
            self._process.setWorkingDirectory(project.workspaceRoot)
        self._process.start()

    def terminate(self) -> None:
        if self.is_running():
            self._requested_state = "stopped"
            self._progress_frozen = True
            self.progressStateChanged.emit("stopped")
            self._status_data["state"] = "stopping"
            self._status_data["stopRequestedAt"] = _now_iso()
            self._write_run_status()
            self._process.terminate()

    def kill(self) -> None:
        if self.is_running():
            self._requested_state = "killed"
            self._progress_frozen = True
            self.progressStateChanged.emit("killed")
            self._status_data["state"] = "killed"
            self._status_data["killedAt"] = _now_iso()
            self._write_run_status()
            self._process.kill()

    def save_logs(self) -> None:
        if self._stdout_file:
            self._stdout_file.flush()
        if self._stderr_file:
            self._stderr_file.flush()

    def _read_stdout(self) -> None:
        data = self._stdout_decoder.decode(bytes(self._process.readAllStandardOutput()))
        for message in self._progress.feed(data):
            if not self._progress_frozen:
                self.progressReceived.emit(message)
        self._write_and_emit(data, is_stdout=True)

    def _read_stderr(self) -> None:
        data = self._stderr_decoder.decode(bytes(self._process.readAllStandardError()))
        self._write_and_emit(data, is_stdout=False)

    def _write_and_emit(self, text: str, *, is_stdout: bool) -> None:
        if is_stdout:
            if self._stdout_file:
                self._stdout_file.write(text)
                self._stdout_file.flush()
            self.stdoutReceived.emit(text)
        else:
            if self._stderr_file:
                self._stderr_file.write(text)
                self._stderr_file.flush()
            self.stderrReceived.emit(text)

        self._emit_log_tags(text, "stdout" if is_stdout else "stderr")

    # A line without a newline longer than this is parsed as-is instead of buffered
    # without bound (the raw text still goes to the log file).
    _MAX_LOG_LINE = 65536

    def _emit_log_tags(self, text: str, stream: str) -> None:
        pending = self._log_tails.get(stream, "") + text
        pieces = pending.splitlines(keepends=True)
        tail = ""
        if pieces and not pieces[-1].endswith(("\n", "\r")):
            tail = pieces.pop()
        for piece in pieces:
            self._emit_log_line(piece.rstrip("\r\n"))
        if len(tail) > self._MAX_LOG_LINE:
            self._emit_log_line(tail)
            tail = ""
        self._log_tails[stream] = tail

    def _flush_log_lines(self) -> None:
        for stream in ("stdout", "stderr"):
            tail = self._log_tails.get(stream, "")
            self._log_tails[stream] = ""
            if tail:
                self._emit_log_line(tail.rstrip("\r\n"))

    def _emit_log_line(self, line: str) -> None:
        for tag in parse_log_line(line):
            self.logTagDetected.emit(tag.level, tag.message, tag.advice)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        stderr_tail = self._stderr_decoder.decode(b"", final=True)
        if stderr_tail:
            self._write_and_emit(stderr_tail, is_stdout=False)
        tail = self._stdout_decoder.decode(b"", final=True)
        if tail:
            self._write_and_emit(tail, is_stdout=True)
        for message in self._progress.feed(tail, final=True):
            if not self._progress_frozen:
                self.progressReceived.emit(message)
        self._flush_log_lines()
        assert self._summary_path is not None
        after = summary_fingerprint(self._summary_path)
        fresh = after is not None and after != self._summary_before
        self.last_result = evaluate_run_result(
            self._summary_path,
            exit_code=exit_code,
            crashed=exit_status != QProcess.NormalExit or self._status_data.get("state") == "error",
            requested_state=self._requested_state,
            summary_fresh=fresh,
        )
        self._progress_frozen = True
        self.progressStateChanged.emit(self.last_result.state)
        self._status_data["state"] = self.last_result.state
        self._status_data["exitCode"] = exit_code
        self._status_data["exitStatus"] = "normal" if exit_status == QProcess.NormalExit else "crashed"
        self._status_data["resultVersion"] = 1
        self._status_data["resultReason"] = self.last_result.reason
        self._status_data["summaryPath"] = str(self._summary_path)
        self._status_data["summaryFresh"] = fresh
        self._status_data["summaryFingerprint"] = list(after) if after else None
        self._status_data["summaryStatus"] = self.last_result.summary_status
        self._status_data["runCount"] = self.last_result.run_count
        self._status_data["plannedEvents"] = self.last_result.planned_events
        self._status_data["completedEvents"] = self.last_result.completed_events
        self._status_data["finishedAt"] = _now_iso()
        self._write_run_status()
        self.save_logs()
        if self._stdout_file:
            self._stdout_file.close()
            self._stdout_file = None
        if self._stderr_file:
            self._stderr_file.close()
            self._stderr_file = None
        self.finished.emit(exit_code)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        self._progress_frozen = True
        self.progressStateChanged.emit("failed")
        message = f"QProcess error: {getattr(error, 'name', str(error))}"
        self._status_data["state"] = "error"
        self._status_data["errorMessage"] = message
        self._status_data["errorAt"] = _now_iso()
        self._write_run_status()
        if error == QProcess.FailedToStart:
            self.save_logs()
            for name in ("_stdout_file", "_stderr_file"):
                handle = getattr(self, name)
                if handle:
                    handle.close()
                    setattr(self, name, None)
        self.errorOccurred.emit(message)

    def _on_state_changed(self, state: QProcess.ProcessState) -> None:
        names = {
            QProcess.NotRunning: "Not running",
            QProcess.Starting: "Starting",
            QProcess.Running: "Running",
        }
        self.stateChanged.emit(names.get(state, "Unknown"))

    def _resolve_logs_dir(self, output_dir: Path) -> Path:
        parent = output_dir.parent
        if output_dir.name.lower() == "output" and (parent / "config").exists():
            return parent / "logs"
        return output_dir / "logs"

    def _write_run_status(self) -> None:
        if not self._run_status_path:
            return
        try:
            self._run_status_path.parent.mkdir(parents=True, exist_ok=True)
            with self._run_status_path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(self._status_data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
        except Exception:
            pass


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
