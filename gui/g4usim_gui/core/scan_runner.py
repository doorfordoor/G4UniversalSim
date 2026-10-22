"""Runs the points of a parameter scan one after another (roadmap C3).

Each point is started with the normal G4USimRunner, so every point gets the same
logs, run_status.json and evaluate_run_result() judgement as a single Run, and
appears in Run History. A failed point does not stop the scan; stop() terminates
the running point and skips the rest.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.core.scan import ScanManifest


class ScanRunner(QObject):
    pointStarted = Signal(int)
    pointFinished = Signal(int, str)     # index, result state
    allFinished = Signal()
    logLine = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = G4USimRunner(self)
        self._runner.finished.connect(self._on_point_finished)
        self._runner.errorOccurred.connect(self._on_error)
        self._runner.stderrReceived.connect(self.logLine.emit)
        self._queue: list[int] = []
        self._current: int | None = None
        self._manifest: ScanManifest | None = None
        self._executable = ""
        self._workspace = ""
        self._stopping = False
        self._attempt = 0     # identifies the running point; late signals of older points are ignored

    def is_running(self) -> bool:
        return self._current is not None

    def start(self, manifest: ScanManifest, executable: str, workspace_root: str, points: list[int]) -> bool:
        if self.is_running() or not points:
            return False
        self._manifest = manifest
        self._executable = executable
        self._workspace = workspace_root
        self._queue = list(points)
        self._stopping = False
        self._next()
        return True

    def stop(self) -> None:
        self._stopping = True
        self._queue.clear()
        if self._runner.is_running():
            self._runner.terminate()

    def _next(self) -> None:
        if not self._queue or self._stopping:
            self._current = None
            self.allFinished.emit()
            return
        index = self._queue.pop(0)
        point = self._manifest.points[index]
        project = G4USimProject(projectName=self._manifest.name, runInputMode="generated",
                                executable=self._executable, workspaceRoot=self._workspace,
                                configPath=point.main_ini, macroPath=point.macro, outputDir=point.output_dir,
                                threads=self._manifest.threads,
                                # the point's own seed: a run.seed scan must not be overridden by the base seed
                                seed="" if point.seed is None else str(point.seed),
                                runName=f"{self._manifest.name}_p{index:03d}")
        self._current = index
        self._attempt += 1
        self.pointStarted.emit(index)
        self._runner.start(project)

    def _finish(self, attempt: int, state: str) -> None:
        if attempt != self._attempt or self._current is None:
            return   # this point was already finished
        index, self._current = self._current, None
        self.pointFinished.emit(index, state)
        self._next()

    def _on_point_finished(self, _exit_code: int) -> None:
        state = self._runner.last_result.state if self._runner.last_result else "unknown"
        self._finish(self._attempt, state)

    def _on_error(self, message: str) -> None:
        self.logLine.emit(message)
        # A refused start or a process that failed to start emits no finished signal.
        attempt = self._attempt
        QTimer.singleShot(0, lambda: None if self._runner.is_running() else self._finish(attempt, "failed"))
