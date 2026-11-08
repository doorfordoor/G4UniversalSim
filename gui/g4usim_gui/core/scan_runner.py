"""Runs the points of a parameter scan one after another (roadmap C3).

Each point is started with the normal G4USimRunner, so every point gets the same
logs, run_status.json and evaluate_run_result() judgement as a single Run, and
appears in Run History. A failed point does not stop the scan; stop() terminates
the running point and skips the rest.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.backend_run_ownership import BackendRunOwnership
from g4usim_gui.core.i18n import ui_text
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.core.scan import ScanManifest


class ScanRunner(QObject):
    pointStarted = Signal(int)
    pointFinished = Signal(int, str)     # index, result state
    allFinished = Signal()
    logLine = Signal(str)

    def __init__(self, parent: QObject | None = None, *,
                 ownership: BackendRunOwnership | None = None) -> None:
        super().__init__(parent)
        self._ownership = ownership if ownership is not None else BackendRunOwnership()
        self._ownership_lease: object | None = None
        self._runner = G4USimRunner(self, ownership=self._ownership)
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
        return self._ownership_lease is not None

    def start(self, manifest: ScanManifest, executable: str, workspace_root: str, points: list[int]) -> bool:
        if self.is_running() or not points:
            return False
        lease = self._ownership.acquire()
        if lease is None:
            self.logLine.emit(ui_text("Another run already owns the backend process."))
            return False
        self._ownership_lease = lease
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
        if self._runner.is_running() or self._runner._run_claim is not None:
            self._runner.terminate()
        elif self._current is None:
            self._schedule_next()

    def _next(self) -> None:
        if self._ownership_lease is None:
            return
        if self._runner._run_claim is not None:
            # Queued timers can also run in a slot's nested event loop. Do not
            # advance a point until the previous runner's terminal stack exits.
            self._schedule_next()
            return
        if not self._queue or self._stopping:
            self._current = None
            if not self._ownership.release(self._ownership_lease):
                # A terminal signal may be on the stack; it still owns cleanup.
                self._schedule_next()
                return
            self._ownership_lease = None
            self.allFinished.emit()
            return
        index = self._queue.pop(0)
        try:
            self._start_point(index)
        except Exception as error:
            self.logLine.emit(str(error))
            self._stopping = True
            self._current = None
            self._schedule_next()

    def _start_point(self, index: int) -> None:
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
        if self._stopping:
            self._current = None
            self._schedule_next()
            return
        if not self._runner.start(project, ownership_lease=self._ownership_lease):
            self._finish(self._attempt, "failed")

    def _schedule_next(self) -> None:
        lease, attempt = self._ownership_lease, self._attempt
        def advance() -> None:
            if (lease is not None and lease is self._ownership_lease
                    and attempt == self._attempt and self._current is None):
                self._next()
        QTimer.singleShot(1, advance)

    def _finish(self, attempt: int, state: str) -> None:
        if attempt != self._attempt or self._current is None:
            return   # this point was already finished
        index, self._current = self._current, None
        self.pointFinished.emit(index, state)
        self._schedule_next()

    def _on_point_finished(self, _exit_code: int) -> None:
        state = self._runner.last_result.state if self._runner.last_result else "unknown"
        self._finish(self._attempt, state)

    def _on_error(self, message: str) -> None:
        self.logLine.emit(message)
        # A refused start or a process that failed to start emits no finished signal.
        attempt = self._attempt
        def resolve() -> None:
            if attempt != self._attempt or self._current is None or self._runner.is_running():
                return
            if self._runner._run_claim is not None:
                # A reentrant refused entry can emit an error while the current
                # point is still preparing. It is not that point's completion.
                QTimer.singleShot(1, resolve)
                return
            self._finish(attempt, "failed")
        QTimer.singleShot(0, resolve)
