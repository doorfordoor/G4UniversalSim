"""Runs the backend export for the 3D view and caches the result (roadmap G1).

One export at a time: a request that arrives while Geant4 is busy replaces any
earlier waiting request and starts when the current one ends, so fast edits end in one
export of the latest inputs. Results are cached by GeometryInputs.key (the most
recent few), so switching back to an earlier world or changing settings that do not
touch the geometry shows it at once.
"""

from __future__ import annotations

import tempfile
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from g4usim_gui.preview3d.backend_inputs import GeometryInputs, backend_failure, write_main_ini
from g4usim_gui.preview3d.backend_mesh import BackendMesh, export_arguments, load_backend_mesh, write_export_macro

CACHE_SIZE = 8


class BackendGeometryController(QObject):
    started = Signal()
    meshReady = Signal(object, bool)     # BackendMesh, True when it came from the cache
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)
        self._cache: OrderedDict[str, BackendMesh] = OrderedDict()
        self._running: GeometryInputs | None = None
        self._pending: tuple[GeometryInputs, str, str] | None = None
        self._work: tempfile.TemporaryDirectory | None = None
        self.exports = 0      # Geant4 runs started (for tests and the status line)

    def is_running(self) -> bool:
        return self.process.state() != QProcess.NotRunning

    def cached(self, key: str) -> BackendMesh | None:
        return self._cache.get(key)

    def request(self, inputs: GeometryInputs, executable: str, working_directory: str) -> None:
        mesh = self._cache.get(inputs.key)
        if mesh is not None:
            self._cache.move_to_end(inputs.key)
            self._pending = None
            self.meshReady.emit(mesh, True)
            return
        if self.is_running():
            if self._running is None or self._running.key != inputs.key:
                self._pending = (inputs, executable, working_directory)
            return
        if not executable or not Path(executable).is_file():
            self.failed.emit(f"Backend executable not found: {executable or '<none>'}")
            return
        self._start(inputs, executable, working_directory)

    def stop(self) -> None:
        self._pending = None
        if self.is_running():
            self.process.kill()
            self.process.waitForFinished(3000)

    def _start(self, inputs: GeometryInputs, executable: str, working_directory: str) -> None:
        self._work = tempfile.TemporaryDirectory(prefix="g4usim_geometry_")
        work = Path(self._work.name)
        main = write_main_ini(inputs, work)
        macro = write_export_macro(work, work / "geometry_mesh.json")
        self._running = inputs
        self.exports += 1
        self.process.setProgram(executable)
        self.process.setArguments(export_arguments(str(main), macro, work / "output"))
        self.process.setWorkingDirectory(working_directory or str(main.parent))
        self.started.emit()
        self.process.start()

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            self._finish(None, self.process.errorString())

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        work = Path(self._work.name) if self._work else None
        stderr = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        stdout = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if exit_status == QProcess.NormalExit and exit_code == 0 and work and (work / "geometry_mesh.json").is_file():
            try:
                self._finish(load_backend_mesh(work / "geometry_mesh.json"), "")
            except ValueError as error:
                self._finish(None, str(error))
            return
        self._finish(None, backend_failure(stderr, stdout, work or ".") or f"exit code {exit_code}")

    def _finish(self, mesh: BackendMesh | None, reason: str) -> None:
        inputs, self._running = self._running, None
        if self._work:
            self._work.cleanup()
            self._work = None
        pending, self._pending = self._pending, None
        if mesh is not None and inputs is not None:
            self._cache[inputs.key] = mesh
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        if pending is not None and (inputs is None or pending[0].key != inputs.key):
            self.request(*pending)    # newer inputs arrived meanwhile: show those instead
            return
        if mesh is not None:
            self.meshReady.emit(mesh, False)
        else:
            self.failed.emit(reason)
