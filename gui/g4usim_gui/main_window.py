from __future__ import annotations

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QMainWindow

from pathlib import Path
from g4usim_gui.core.i18n import current_language, ui_text
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.history.run_history_store import load_state, save_state
from g4usim_gui.preview3d.backend_geometry_controller import BackendGeometryController
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
from g4usim_gui.widgets.output_page import OutputPage
from g4usim_gui.widgets.project_page import ProjectPage
from g4usim_gui.widgets.run_page import RunPage
from g4usim_gui.widgets.run_history_page import RunHistoryPage
from g4usim_gui.widgets.scan_page import ScanPage
from g4usim_gui.widgets.start_page import StartPage
from g4usim_gui.window.shell import ShellMixin
from g4usim_gui.window.project import ProjectMixin
from g4usim_gui.window.run import RunMixin
from g4usim_gui.window.content import ContentMixin


class MainWindow(ShellMixin, ProjectMixin, RunMixin, ContentMixin, QMainWindow):
    """The main window: pages, runner and controllers; its behaviour is split by area in g4usim_gui/window/."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("G4UniversalSim Runner")
        self.resize(1500, 950)
        self.setMinimumSize(1200, 760)

        self.project = self._default_project()
        self.project_file: Path | None = None
        self._generated_package_stale = True
        self._generated_package_dir = ""
        self.runner = G4USimRunner(self)
        self._macro_inspection = QProcess(self)
        self.geometry_controller = BackendGeometryController(self)
        self._geometry_export = self.geometry_controller.process   # the export's QProcess (tests wait on it)
        self._macro_inspection_snapshot: tuple[object, ...] | None = None
        self._pending_inspection_run = False
        self._macro_inspection.finished.connect(self._on_macro_inspection_finished)
        self._macro_inspection.errorOccurred.connect(self._on_macro_inspection_error)

        self.start_page = StartPage()
        self.project_page = ProjectPage()
        self.config_builder_page = ConfigBuilderPage()
        self.run_page = RunPage()
        self.output_page = OutputPage()
        self.run_history_page = RunHistoryPage()
        self.scan_page = ScanPage()
        self.scan_page.set_base_provider(self.scan_base)

        self._build_workspace_shell()
        self._apply_visual_roles()
        self._run_chip = ("Idle", "")

        self._connect_signals()
        self._create_menu()
        self._restore_app_state()
        self._set_project(self.project)
        self._set_language(current_language(), persist=False)
        self.statusBar().showMessage(ui_text("Ready"), 5000)

    def _connect_signals(self) -> None:
        self.start_page.newSimulationRequested.connect(self.open_new_simulation_wizard)
        self.start_page.openProjectRequested.connect(self.open_project)
        self.start_page.recentProjectRequested.connect(self._open_recent_project)
        self.start_page.exampleRequested.connect(self.open_example)
        self.project_page.projectChanged.connect(self._update_project_from_page)
        self.project_page.saveProjectRequested.connect(self.save_project_as)
        self.project_page.loadProjectRequested.connect(self.open_project)
        self.config_builder_page.settingsChanged.connect(self._update_project_from_config_builder)
        self.config_builder_page.validateRequested.connect(self.validate_generated_config)
        self.config_builder_page.generatePackageRequested.connect(self.generate_package)
        self.config_builder_page.backendGeometryRequested.connect(self.export_backend_geometry)
        self.config_builder_page.autoBackendGeometryRequested.connect(lambda: self.export_backend_geometry(auto=True))
        self.config_builder_page.workspace_tabs.currentChanged.connect(
            lambda _index: self.config_builder_page.schedule_backend_geometry(100))
        controller = self.geometry_controller
        controller.started.connect(lambda: self.config_builder_page.set_backend_geometry_busy(True))
        controller.meshReady.connect(self._on_backend_mesh)
        controller.failed.connect(self._on_backend_geometry_failed)

        self.run_page.buildCommandRequested.connect(self.build_command_preview)
        self.run_page.inspectMacroRequested.connect(self.inspect_external_macro)
        self.run_page.runRequested.connect(self.start_run)
        self.run_page.stopRequested.connect(self.stop_run)
        self.run_page.killRequested.connect(self.runner.kill)
        self.run_page.saveLogsRequested.connect(self.runner.save_logs)

        self.runner.stdoutReceived.connect(self.run_page.append_stdout)
        self.runner.stderrReceived.connect(self.run_page.append_stderr)
        self.runner.stateChanged.connect(self._on_state_changed)
        self.runner.finished.connect(self._on_finished)
        self.runner.errorOccurred.connect(self._on_runner_error)
        self.runner.logTagDetected.connect(self._on_log_tag)
        self.run_history_page.loadSnapshotRequested.connect(self.load_snapshot_into_project)
        self.run_history_page.openOutputRequested.connect(self.open_history_output)
        self.run_history_page.duplicateRequested.connect(lambda package: self.duplicate_history_package(package, run_after=False))
        self.run_history_page.duplicateAndRunRequested.connect(lambda package: self.duplicate_history_package(package, run_after=True))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override.
        if self._macro_inspection.state() != QProcess.NotRunning:
            self._macro_inspection.kill()
            self._macro_inspection.waitForFinished(1000)
        self.geometry_controller.stop()
        if self.scan_page.runner.is_running():   # do not leave a scan point running after exit
            self.scan_page.runner.stop()
        state = load_state()
        state["lastWorkspaceRoot"] = self.project.workspaceRoot
        state["lastRunsRoot"] = self.project.runsRoot
        save_state(state)
        super().closeEvent(event)
