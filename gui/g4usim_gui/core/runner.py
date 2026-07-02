from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from g4usim_gui.core.log_parser import parse_log_line
from g4usim_gui.core.paths import ensure_directory
from g4usim_gui.core.project import G4USimProject


class G4USimRunner(QObject):
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

        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._process.stateChanged.connect(self._on_state_changed)

    @staticmethod
    def validate_project(project: G4USimProject) -> list[str]:
        errors: list[str] = []

        executable = Path(project.executable).expanduser() if project.executable else None
        if not project.executable:
            errors.append("Executable path is required.")
        elif not executable or not executable.exists():
            errors.append(f"Executable does not exist: {project.executable}")
        elif not executable.is_file():
            errors.append(f"Executable path is not a file: {project.executable}")

        if not project.macroPath:
            errors.append("Macro path is required.")
        elif not Path(project.macroPath).expanduser().exists():
            errors.append(f"Macro file does not exist: {project.macroPath}")

        if project.configPath and not Path(project.configPath).expanduser().exists():
            errors.append(f"Config file does not exist: {project.configPath}")

        if project.workspaceRoot and not Path(project.workspaceRoot).expanduser().is_dir():
            errors.append(f"Workspace root does not exist: {project.workspaceRoot}")

        if not project.outputDir:
            errors.append("Output directory is required.")
        else:
            output_dir = Path(project.outputDir).expanduser()
            if output_dir.exists() and not output_dir.is_dir():
                errors.append(f"Output path exists but is not a directory: {project.outputDir}")
            else:
                existing_parent = output_dir
                while not existing_parent.exists() and existing_parent.parent != existing_parent:
                    existing_parent = existing_parent.parent
                if not existing_parent.exists():
                    errors.append(f"Output directory has no existing parent: {project.outputDir}")

        if project.threads <= 0:
            errors.append("Threads must be a positive integer.")

        if project.seed:
            try:
                int(project.seed)
            except ValueError:
                errors.append("Seed must be an integer when provided.")

        return errors

    @staticmethod
    def build_command(project: G4USimProject) -> list[str]:
        args: list[str] = []
        if project.configPath:
            args.extend(["--config", project.configPath])
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

    def start(self, project: G4USimProject) -> None:
        if self.is_running():
            self.errorOccurred.emit("A run is already active.")
            return

        errors = self.validate_project(project)
        if errors:
            self.errorOccurred.emit("\n".join(errors))
            return

        self._output_dir = ensure_directory(project.outputDir)
        logs_dir = self._resolve_logs_dir(self._output_dir)
        self._logs_dir = logs_dir
        logs_dir.mkdir(parents=True, exist_ok=True)
        self._stdout_file = (logs_dir / "stdout.log").open("w", encoding="utf-8", newline="\n")
        self._stderr_file = (logs_dir / "stderr.log").open("w", encoding="utf-8", newline="\n")

        command = self.build_command(project)
        self._run_status_path = logs_dir / "run_status.json"
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
            self._status_data["state"] = "stopping"
            self._status_data["stopRequestedAt"] = _now_iso()
            self._write_run_status()
            self._process.terminate()

    def kill(self) -> None:
        if self.is_running():
            self._requested_state = "killed"
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
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._write_and_emit(data, is_stdout=True)

    def _read_stderr(self) -> None:
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
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

        for line in text.splitlines():
            for tag in parse_log_line(line):
                self.logTagDetected.emit(tag.level, tag.message, tag.advice)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        state = self._requested_state or "finished"
        self._status_data["state"] = state
        self._status_data["exitCode"] = exit_code
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
        message = f"QProcess error: {getattr(error, 'name', str(error))}"
        self._status_data["state"] = "error"
        self._status_data["errorMessage"] = message
        self._status_data["errorAt"] = _now_iso()
        self._write_run_status()
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
