from __future__ import annotations

import json
import codecs
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from g4usim_gui.core.backend_launch import BackendLaunchError, prepare_backend_launch, unsupported_working_directory
from g4usim_gui.core.backend_run_ownership import BackendRunOwnership
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
    # Raw bytes of a controlled session. The session client owns the protocol;
    # the runner stays the single owner of the backend process.
    sessionData = Signal(bytes, bool)
    processStarted = Signal()
    # No process exists for a rejected/failed session launch. The window routes
    # this to the session client's existing terminal transition (not run result).
    sessionStartFailed = Signal()

    def __init__(self, parent: QObject | None = None, *,
                 ownership: BackendRunOwnership | None = None) -> None:
        super().__init__(parent)
        self._ownership = ownership if ownership is not None else BackendRunOwnership()
        self._ownership_lease: object | None = None
        self._run_claim: object | None = None
        self._owns_lease = False
        self._terminal_callback = False
        self._in_error_callback = False
        self._pending_finished = None
        self._reporting_refusal = False
        self._completion_slots = None
        self._session_start_lease: object | None = None
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
        self.last_launch = None
        self._stderr_diagnostic_tail = ""
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
        self._process.started.connect(self.processStarted)
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

    def start(self, project: G4USimProject, command: list[str] | None = None, *,
              ownership_lease: object | None = None) -> bool:
        return self._start(project, command, session=False, ownership_lease=ownership_lease)

    def start_session(self, project: G4USimProject, command: list[str] | None = None) -> bool:
        """Start the same owned process for a controlled session.

        The session client speaks the JSON-lines protocol through ``sessionData``
        and never creates another process owner.
        """
        return self._start(project, command, session=True,
                           ownership_lease=self._session_start_lease,
                           release_lease=True)

    @contextmanager
    def session_start_admission(self):
        """Reserve across SessionClient's synchronous pre-start signals.

        A successful start transfers release to the process claim. A refused or
        abandoned start releases on scope exit. There is no new process owner.
        """
        lease = self._ownership.acquire()
        if lease is None:
            yield False
            return
        self._session_start_lease = lease
        try:
            yield True
        finally:
            self._session_start_lease = None
            self._ownership.release(lease)  # refuses while a process claim lives

    def write_session_data(self, payload: bytes) -> int:
        """Write one protocol frame to the owned session process."""
        if not self._session_mode or not self.is_running():
            return -1
        return int(self._process.write(payload))

    def _start(self, project: G4USimProject, command: list[str] | None,
               *, session: bool, ownership_lease: object | None = None,
               release_lease: bool = False) -> bool:
        # Claim before validation, file writes or any public signal. In particular,
        # a cached scan executable cannot bypass this admission boundary.
        if self.is_running() or self._run_claim is not None:
            self._refuse_start("A run is already active.")
            return False
        lease = ownership_lease if ownership_lease is not None else self._ownership.acquire()
        claim = self._ownership.claim(lease) if lease is not None else None
        if claim is None:
            self._refuse_start("Another run already owns the backend process.")
            return False
        self._ownership_lease, self._run_claim = lease, claim
        self._owns_lease = ownership_lease is None or release_lease
        started = False
        try:
            if self._completion_slots is not None:
                done, error = self._completion_slots
                self._process.finished.disconnect(done)
                self._process.errorOccurred.disconnect(error)
            done = lambda code, status: self._dispatch_finished(claim, code, status)
            error = lambda value: self._dispatch_error(claim, value)
            self._completion_slots = (done, error)
            self._process.finished.connect(done)
            self._process.errorOccurred.connect(error)
            started = bool(self._start_owned(project, command, session=session))
            return started
        except Exception as error:
            self.errorOccurred.emit(str(error))
            return False
        finally:
            if not started and not self.is_running():
                try:
                    self._close_start_logs()
                finally:
                    try:
                        if session:
                            self.sessionStartFailed.emit()
                    finally:
                        self._release_run_claim(claim)

    def _refuse_start(self, message: str) -> None:
        # A refusal slot may itself try another entry. Report once on this stack
        # while every nested attempt still receives False.
        if not self._reporting_refusal:
            self._reporting_refusal = True
            try:
                self.errorOccurred.emit(ui_text(message))
            finally:
                self._reporting_refusal = False

    def _release_run_claim(self, claim: object) -> None:
        if claim is None or claim is not self._run_claim:
            return
        lease = self._ownership_lease
        self._ownership.release_claim(lease, claim)
        if self._owns_lease:
            self._ownership.release(lease)
        self._run_claim = self._ownership_lease = None
        self._owns_lease = False

    def _close_start_logs(self) -> None:
        first_error = None
        for name in ("_stdout_file", "_stderr_file"):
            handle = getattr(self, name)
            if handle is not None:
                try:
                    handle.close()
                except OSError as error:
                    first_error = first_error or error
                finally:
                    setattr(self, name, None)
        if first_error is not None:
            raise first_error

    def _dispatch_finished(self, claim: object, code: int, status: QProcess.ExitStatus) -> None:
        if claim is None or claim is not self._run_claim or self.is_running():
            return
        if self._terminal_callback:
            if self._in_error_callback:
                self._pending_finished = (claim, code, status)
            return
        self._terminal_callback = True
        try:
            self._on_finished(code, status)
        finally:
            # Keep admission closed throughout synchronous finished slots. Scan
            # continuation is queued, after this stack has unwound.
            self._release_run_claim(claim)
            self._terminal_callback = False

    def _dispatch_error(self, claim: object, error: QProcess.ProcessError) -> None:
        if claim is None or claim is not self._run_claim or self._terminal_callback:
            return
        self._terminal_callback = True
        self._in_error_callback = True
        try:
            self._on_error(error)
            if error == QProcess.FailedToStart and self._session_mode:
                self.sessionStartFailed.emit()
        finally:
            if error == QProcess.FailedToStart and not self.is_running():
                self._release_run_claim(claim)
            self._in_error_callback = False
            self._terminal_callback = False
            pending, self._pending_finished = self._pending_finished, None
            if pending is not None:
                self._dispatch_finished(*pending)

    def _start_owned(self, project: G4USimProject, command: list[str] | None,
                     *, session: bool) -> bool:

        errors = self.validate_project(project, ready_to_run=True)
        if errors:
            self.errorOccurred.emit("\n".join(errors))
            return False

        requested_command = list(command) if command is not None else self.build_command(project)
        try:
            launch = prepare_backend_launch(requested_command, project.workspaceRoot or None)
        except BackendLaunchError as error:
            self.last_launch = None
            self.last_result = RunResult("failed", str(error))
            self._progress_frozen = True
            self.progressStateChanged.emit("failed")
            self.errorOccurred.emit(str(error))
            return False
        self.last_launch = launch
        self._stderr_diagnostic_tail = ""
        self._output_dir = ensure_directory(project.outputDir)
        logs_dir = self._resolve_logs_dir(self._output_dir)
        self._logs_dir = logs_dir
        logs_dir.mkdir(parents=True, exist_ok=True)
        self._stdout_file = (logs_dir / "stdout.log").open("w", encoding="utf-8", newline="\n")
        self._stderr_file = (logs_dir / "stderr.log").open("w", encoding="utf-8", newline="\n")

        command = launch.command
        self._run_status_path = logs_dir / "run_status.json"
        self._summary_path = self._output_dir / "run_summary.txt"
        self._summary_before = summary_fingerprint(self._summary_path)
        self.last_result = None
        self._progress = ProgressParser()
        self._stdout_decoder.reset()
        self._stderr_decoder.reset()
        self._progress_frozen = False
        self._session_mode = bool(session)
        self._log_tails = {"stdout": "", "stderr": ""}
        self._requested_state = ""
        self._status_data = {
            "state": "running",
            "startedAt": _now_iso(),
            "command": command,
            "program": command[0],
            "arguments": command[1:],
            "workingDirectory": project.workspaceRoot or launch.logical_cwd,
            "logicalWorkingDirectory": launch.logical_cwd,
            "launchWorkingDirectory": launch.launch_cwd,
            "launchRoute": launch.route,
            "requestedCommand": requested_command,
        }
        self._write_run_status()
        self.progressStateChanged.emit("starting")
        program = command[0]
        arguments = command[1:]
        self._process.setProgram(program)
        self._process.setArguments(arguments)
        self._process.setWorkingDirectory(launch.launch_cwd)
        if self._requested_state in {"stopped", "killed"}:
            self._status_data["state"] = self._requested_state
            self._status_data["finishedAt"] = _now_iso()
            self._write_run_status()
            return False
        self._process.start()
        return True

    def terminate(self) -> None:
        if self.is_running() or (self._run_claim is not None and not self._terminal_callback):
            self._requested_state = "stopped"
            self._progress_frozen = True
            self.progressStateChanged.emit("stopped")
            self._status_data["state"] = "stopping"
            self._status_data["stopRequestedAt"] = _now_iso()
            self._write_run_status()
            self._process.terminate()

    def kill(self) -> None:
        if self.is_running() or (self._run_claim is not None and not self._terminal_callback):
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
        data = bytes(self._process.readAllStandardOutput())
        if self._session_mode:
            if data:
                self._write_session_log(data, is_stdout=True)
                self.sessionData.emit(data, True)
            return
        text = self._stdout_decoder.decode(data)
        for message in self._progress.feed(text):
            if not self._progress_frozen:
                self.progressReceived.emit(message)
        self._write_and_emit(text, is_stdout=True)

    def _read_stderr(self) -> None:
        data = bytes(self._process.readAllStandardError())
        if self._session_mode:
            if data:
                self._write_session_log(data, is_stdout=False)
                self.sessionData.emit(data, False)
            return
        text = self._stderr_decoder.decode(data)
        self._write_and_emit(text, is_stdout=False)

    def _write_session_log(self, data: bytes, *, is_stdout: bool) -> None:
        handle = self._stdout_file if is_stdout else self._stderr_file
        if handle is None:
            return
        try:
            handle.write(data.decode("utf-8", errors="replace"))
            handle.flush()
        except OSError:
            pass

    def _write_and_emit(self, text: str, *, is_stdout: bool) -> None:
        if is_stdout:
            if self._stdout_file:
                self._stdout_file.write(text)
                self._stdout_file.flush()
            self.stdoutReceived.emit(text)
        else:
            self._stderr_diagnostic_tail = (self._stderr_diagnostic_tail + text)[-8192:]
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
        if self._session_mode:
            self._finish_session(exit_code, exit_status)
            return
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
        if (exit_code != 0 and self.last_launch is not None
                and self.last_launch.requires_working_directory
                and unsupported_working_directory(self._stderr_diagnostic_tail)):
            self.last_result = RunResult("failed", "backend_launch.unsupported_working_directory")
            self._status_data["launchStatus"] = "unsupported_working_directory"
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

    def _finish_session(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        """Close the owned process without applying single-run result semantics."""
        self.last_result = RunResult(
            "closed" if exit_code == 0 else "failed",
            "session process exited" if exit_code == 0 else f"session process exit code {exit_code}",
        )
        self._progress_frozen = True
        self.progressStateChanged.emit("idle")
        self._status_data["state"] = "session_closed" if exit_code == 0 else "session_failed"
        self._status_data["exitCode"] = exit_code
        self._status_data["exitStatus"] = "normal" if exit_status == QProcess.NormalExit else "crashed"
        self._status_data["sessionMode"] = True
        self._status_data["finishedAt"] = _now_iso()
        self._write_run_status()
        self.save_logs()
        if self._stdout_file:
            self._stdout_file.close()
            self._stdout_file = None
        if self._stderr_file:
            self._stderr_file.close()
            self._stderr_file = None
        self._session_mode = False
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
