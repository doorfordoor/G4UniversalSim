"""Run the two bundled M5 postprocessors in a separate, observable process."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal


class OutputExtensionRunner(QObject):
    outputReceived = Signal(str)
    stateChanged = Signal(bool)
    finished = Signal(str, str, bool, str)

    BUILTINS = ("dose_json", "fluence_json")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._active: tuple[str, Path] | None = None
        self._cancelled = False
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def is_running(self) -> bool:
        return self._active is not None

    def _cli_script(self) -> Path:
        return Path(__file__).resolve().parents[3] / "scripts" / "run_output_extension.py"

    def start(self, extension_id: str, input_dir: str | Path, output: str | Path) -> None:
        if self.is_running():
            raise ValueError("An output extension is already running.")
        if extension_id not in self.BUILTINS:
            raise ValueError(f"Unknown built-in output extension: {extension_id}")
        if not str(input_dir).strip():
            raise ValueError("Select an existing output directory first.")
        source = Path(input_dir).resolve()
        target = Path(output).resolve()
        if not source.is_dir():
            raise ValueError(f"Output CSV directory does not exist: {source}")
        if target.suffix.lower() != ".json":
            raise ValueError("Extension output must be a .json file.")
        if not target.parent.is_dir():
            raise ValueError(f"JSON destination directory does not exist: {target.parent}")
        if target.exists():
            raise ValueError(f"JSON destination already exists; choose another file: {target}")
        script = self._cli_script()
        if not script.is_file():
            raise ValueError(f"Output extension CLI is missing: {script}")
        self._active = (extension_id, target)
        self._cancelled = False
        self.stateChanged.emit(True)
        self._process.setProgram(sys.executable)
        self._process.setArguments([
            "-B", str(script), "--run", extension_id,
            "--input-dir", str(source), "--output", str(target),
        ])
        self._process.start()

    def cancel(self) -> None:
        if self.is_running():
            self._cancelled = True
            if self._process.state() == QProcess.NotRunning:
                self._complete(False, "Output extension cancelled.")
            else:
                self._process.kill()

    def shutdown(self) -> None:
        """Stop the child before Qt destroys the Results page and its QProcess."""
        self.cancel()
        if self._process.state() != QProcess.NotRunning:
            self._process.waitForFinished(2000)

    def _read_stdout(self) -> None:
        chunk = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if chunk:
            self.outputReceived.emit(chunk)

    def _read_stderr(self) -> None:
        chunk = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        if chunk:
            self.outputReceived.emit(chunk)

    def _complete(self, success: bool, message: str) -> None:
        current = self._active
        if current is None:
            return
        self._active = None
        self.stateChanged.emit(False)
        self.finished.emit(current[0], str(current[1]), success, message)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            self._complete(False, f"Cannot start extension process: {self._process.errorString()}")

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        if self._active is None:
            return
        extension_id, target = self._active
        if self._cancelled:
            self._complete(False, "Output extension cancelled.")
            return
        if exit_status != QProcess.NormalExit or exit_code != 0:
            self._complete(False, f"Output extension failed (exit code {exit_code}).")
            return
        if not target.is_file():
            self._complete(False, "Output extension exited successfully but JSON is missing.")
            return
        try:
            with target.open(encoding="utf-8") as stream:
                result = json.load(stream, parse_constant=self._reject_nonfinite)
            if not isinstance(result, dict):
                raise ValueError("Extension result must be an object")
            if (result.get("schema") != "G4UniversalSimOutputExtensionResult"
                    or result.get("version") != 1 or result.get("extension_id") != extension_id):
                raise ValueError("Unexpected extension result schema or ID")
            version = result.get("extension_version")
            if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
                raise ValueError("Unexpected extension version")
            data = result.get("data")
            if not isinstance(data, dict):
                raise ValueError("Extension data must be an object")
            warnings = data.get("warnings", [])
            if not isinstance(warnings, list):
                raise ValueError("Unexpected extension warnings format")
        except (OSError, ValueError, TypeError, AttributeError) as error:
            self._complete(False, f"Cannot verify extension JSON: {error}")
            return
        self._complete(True, f"JSON: {target}\nWarnings ({len(warnings)}): " +
                       ("\n".join(map(str, warnings)) if warnings else "none"))

    @staticmethod
    def _reject_nonfinite(value: str) -> None:
        raise ValueError(f"Non-finite JSON value: {value}")
