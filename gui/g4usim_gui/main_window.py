from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from g4usim_gui.core.project import G4USimProject, load_project, save_project
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.history.run_history_store import add_recent_project, clear_recent_projects, get_recent_projects, load_state, save_state
from g4usim_gui.history.run_package_actions import duplicate_package
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.writers.package_writer import create_run_package
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
from g4usim_gui.widgets.output_page import OutputPage
from g4usim_gui.widgets.project_page import ProjectPage
from g4usim_gui.widgets.run_page import RunPage
from g4usim_gui.widgets.run_history_page import RunHistoryPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("G4UniversalSim Runner")
        self.resize(1500, 950)
        self.setMinimumSize(1200, 760)

        self.project = self._default_project()
        self.project_file: Path | None = None
        self.runner = G4USimRunner(self)

        self.project_page = ProjectPage()
        self.config_builder_page = ConfigBuilderPage()
        self.run_page = RunPage()
        self.output_page = OutputPage()
        self.run_history_page = RunHistoryPage()

        tabs = QTabWidget()
        tabs.addTab(self.project_page, "Project")
        tabs.addTab(self.config_builder_page, "Config Builder")
        tabs.addTab(self.run_page, "Run")
        tabs.addTab(self.output_page, "Output")
        tabs.addTab(self.run_history_page, "Run History")
        self.setCentralWidget(tabs)
        self.tabs = tabs

        self._connect_signals()
        self._create_menu()
        self._restore_app_state()
        self._set_project(self.project)
        self.statusBar().showMessage("Ready", 5000)

    def _default_project(self) -> G4USimProject:
        root = Path(__file__).resolve().parents[2]
        output = root / "gui_runs" / "demo" / "output"
        project = G4USimProject(
            projectName="demo",
            workspaceRoot=str(root),
            configPath=str(root / "config" / "main.ini"),
            macroPath=str(root / "macros" / "test_simple_min.mac"),
            outputDir=str(output),
            runsRoot=str(root / "gui_runs"),
            threads=1,
            runName="demo_run",
        )
        project.pathSettings = PathSettings(
            executable="",
            workspace_root=str(root),
            runs_root=str(root / "gui_runs"),
            materials_config=str(root / "config" / "materials" / "material.ini"),
            geometry_config=str(root / "config" / "geometry" / "simple_box.ini"),
        )
        project.geometrySettings.config_path = project.pathSettings.geometry_config
        project.geometrySettings.template = "simple_box"
        return project

    def _connect_signals(self) -> None:
        self.project_page.projectChanged.connect(self._update_project_from_page)
        self.project_page.saveProjectRequested.connect(self.save_project_as)
        self.project_page.loadProjectRequested.connect(self.open_project)
        self.config_builder_page.settingsChanged.connect(self._update_project_from_config_builder)
        self.config_builder_page.validateRequested.connect(self.validate_generated_config)
        self.config_builder_page.generatePackageRequested.connect(self.generate_package)

        self.run_page.buildCommandRequested.connect(self.build_command_preview)
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

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        open_action = file_menu.addAction("Open Project...")
        save_action = file_menu.addAction("Save Project")
        save_as_action = file_menu.addAction("Save Project As...")
        self.recent_menu = file_menu.addMenu("Recent Projects")
        clear_recent_action = file_menu.addAction("Clear Recent Projects")
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")

        open_action.triggered.connect(self.open_project)
        save_action.triggered.connect(self.save_project)
        save_as_action.triggered.connect(self.save_project_as)
        clear_recent_action.triggered.connect(self.clear_recent_projects)
        exit_action.triggered.connect(self.close)
        self._refresh_recent_menu()

    def _set_project(self, project: G4USimProject) -> None:
        self.project = project
        self.project_page.set_project(project)
        self.config_builder_page.set_from_project(project)
        self.output_page.set_workspace_root(project.workspaceRoot)
        self.output_page.set_output_dir(project.outputDir)
        self.run_history_page.set_runs_root(project.runsRoot)
        self.build_command_preview(show_errors=False)

    def _update_project_from_page(self) -> None:
        self.project = self.project_page.to_project()
        self._sync_flat_project_to_nested_paths()
        self.output_page.set_workspace_root(self.project.workspaceRoot)
        self.output_page.set_output_dir(self.project.outputDir)
        self.run_history_page.set_runs_root(self.project.runsRoot)
        self.build_command_preview(show_errors=False)

    def _update_project_from_config_builder(self) -> None:
        self.config_builder_page.update_project(self.project)

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open G4UniversalSim project", filter="JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            project = load_project(path)
        except Exception as exc:  # noqa: BLE001 - user-facing project load errors.
            QMessageBox.critical(self, "Open project failed", str(exc))
            return
        self.project_file = Path(path)
        add_recent_project(path)
        self._refresh_recent_menu()
        self._set_project(project)
        self.statusBar().showMessage(f"Loaded project: {path}", 5000)

    def save_project(self) -> None:
        if self.project_file is None:
            self.save_project_as()
            return
        self._update_project_from_page()
        self.config_builder_page.update_project(self.project)
        try:
            save_project(self.project, self.project_file)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save project failed", str(exc))
            return
        self.statusBar().showMessage(f"Saved project: {self.project_file}", 5000)
        add_recent_project(str(self.project_file))
        self._refresh_recent_menu()

    def save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save G4UniversalSim project", filter="JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        self.project_file = Path(path)
        self.save_project()

    def build_command_preview(self, *, show_errors: bool = True) -> None:
        self._update_project_from_page_without_preview()
        errors = self.runner.validate_project(self.project)
        if errors:
            self.run_page.set_command(["Validation errors:", *errors])
            if show_errors:
                QMessageBox.warning(self, "Validation failed", "\n".join(errors))
            return
        command = self.runner.build_command(self.project)
        self.run_page.set_command(self._format_command_preview(command))

    def start_run(self) -> None:
        self._update_project_from_page_without_preview()
        errors = self.runner.validate_project(self.project)
        if errors:
            message = "\n".join(errors)
            self.run_page.append_status_message(message)
            QMessageBox.warning(self, "Validation failed", message)
            return
        self.run_page.clear_logs()
        self.run_page.set_command(self._format_command_preview(self.runner.build_command(self.project)))
        self.run_page.append_status_message("Starting run")
        self.statusBar().showMessage("Running", 5000)
        self.runner.start(self.project)

    def validate_generated_config(self) -> None:
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        try:
            report = self.config_builder_page.validate_current(self.project)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Validation failed", str(exc))
            self.config_builder_page.set_validation_text(str(exc))
            return
        self.config_builder_page.set_validation_text(report.to_text())
        if report.can_run:
            self.statusBar().showMessage("Config Builder validation passed", 5000)
        else:
            QMessageBox.warning(self, "Validation failed", "\n".join(report.errors))

    def generate_package(self, run_after_generate: bool) -> None:
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        try:
            pre_report = self.config_builder_page.validate_current(self.project)
            if not pre_report.can_run:
                self.config_builder_page.set_validation_text(pre_report.to_text())
                QMessageBox.warning(self, "Validation failed", "\n".join(pre_report.errors))
                return
            if pre_report.warnings:
                QMessageBox.information(
                    self,
                    "Validation warnings",
                    "Package generation will continue with warnings:\n\n"
                    + "\n".join(pre_report.warnings[:10]),
                )
            package, report_text = create_run_package(
                project=self.project,
                paths=self.config_builder_page.path_settings(self.project),
                run=self.config_builder_page.run_settings(),
                geometry=self.config_builder_page.geometry_settings(),
                source=self.config_builder_page.source_settings(),
                physics=self.config_builder_page.physics_settings(),
                scoring=self.config_builder_page.scoring_settings(),
                material_document=self.config_builder_page.material_document if self.config_builder_page.material_document.is_dirty else None,
                geometry_document=self.config_builder_page.geometry_document if self.config_builder_page.geometry_document.is_dirty else None,
                source_model=self.config_builder_page.source_editor,
                physics_model=self.config_builder_page.physics_editor,
                scoring_model=self.config_builder_page.scoring_editor,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self.config_builder_page.set_validation_text(message)
            QMessageBox.warning(self, "Generate package failed", message)
            return

        self.project.configPath = package.main_ini_path
        self.project.macroPath = package.run_macro_path
        self.project.outputDir = package.output_dir
        self.project.runName = self.config_builder_page.run_settings().run_name
        self.project.threads = self.config_builder_page.run_settings().threads
        seed = self.config_builder_page.run_settings().seed
        self.project.seed = "" if seed is None else str(seed)
        self.project_page.set_project(self.project)
        self.config_builder_page.set_package_path(package.package_dir)
        self.config_builder_page.set_validation_text(report_text)
        self.output_page.set_package_dir(package.package_dir, package.output_dir)
        self.run_history_page.set_runs_root(self.project.runsRoot)
        self.run_history_page.refresh()
        self.build_command_preview(show_errors=False)
        self.statusBar().showMessage(f"Generated package: {package.package_dir}", 8000)

        if run_after_generate:
            self.start_run()

    def stop_run(self) -> None:
        self.runner.terminate()
        self.run_page.append_status_message("Terminate requested. Use Kill if the process does not exit.")
        QTimer.singleShot(3000, self._offer_kill_if_running)

    def _offer_kill_if_running(self) -> None:
        if not self.runner.is_running():
            return
        self.run_page.append_status_message("Process is still running; Kill is available.")

    def _on_state_changed(self, state: str) -> None:
        self.run_page.set_state(state)
        running = state in {"Starting", "Running"}
        self.project_page.set_inputs_enabled(not running)

    def _on_finished(self, exit_code: int) -> None:
        self.run_page.set_exit_code(exit_code)
        self.project_page.set_inputs_enabled(True)
        self.output_page.set_output_dir(self.project.outputDir)
        self.output_page.refresh()
        self.run_history_page.refresh()
        self.statusBar().showMessage(("Finished" if exit_code == 0 else "Failed") + f" with exit code {exit_code}", 8000)

    def _on_runner_error(self, message: str) -> None:
        self.run_page.append_status_message(message)
        QMessageBox.warning(self, "Runner error", message)

    def _on_log_tag(self, level: str, message: str, advice: str) -> None:
        self.statusBar().showMessage(f"{level.upper()}: {message}", 8000)
        detail = f"{level.upper()}: {message}"
        if advice:
            detail += f" | Advice: {advice}"
        self.run_page.append_status_message(detail)

    def _update_project_from_page_without_preview(self) -> None:
        self.project = self.project_page.to_project()
        self._sync_flat_project_to_nested_paths()
        self.output_page.set_workspace_root(self.project.workspaceRoot)
        self.output_page.set_output_dir(self.project.outputDir)
        self.run_history_page.set_runs_root(self.project.runsRoot)

    def _sync_flat_project_to_nested_paths(self) -> None:
        self.project.pathSettings.executable = self.project.executable
        self.project.pathSettings.workspace_root = self.project.workspaceRoot
        self.project.pathSettings.runs_root = self.project.runsRoot

    def _format_command_preview(self, command: list[str]) -> list[str]:
        if not command:
            return []
        working_directory = self.project.workspaceRoot or "<not set>"
        lines = [
            "program:",
            f"  {command[0]}",
            "arguments:",
        ]
        lines.extend(f"  {arg}" for arg in command[1:])
        lines.extend(["working directory:", f"  {working_directory}", "", "human-readable:", "  " + " ".join(command)])
        return lines

    def load_snapshot_into_project(self, snapshot_path: str) -> None:
        try:
            project = load_project(snapshot_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Load snapshot failed", str(exc))
            return
        # Keep historical package paths visible, but users can generate a new package before running.
        self._set_project(project)
        self.statusBar().showMessage("Snapshot loaded. You can generate a new package or rerun with the existing package.", 8000)

    def open_history_output(self, package_dir: str, output_dir: str) -> None:
        self.output_page.set_package_dir(package_dir, output_dir)
        self.tabs.setCurrentWidget(self.output_page)

    def duplicate_history_package(self, package_dir: str, *, run_after: bool) -> None:
        try:
            new_package = duplicate_package(package_dir, self.project.runsRoot)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Duplicate failed", str(exc))
            return
        package = Path(new_package)
        self.project.configPath = str(package / "config" / "main.ini")
        self.project.macroPath = str(package / "macros" / "run.mac")
        self.project.outputDir = str(package / "output")
        self.project_page.set_project(self.project)
        self.output_page.set_package_dir(str(package), self.project.outputDir)
        self.run_history_page.refresh()
        self.build_command_preview(show_errors=False)
        self.tabs.setCurrentWidget(self.run_page)
        if run_after:
            self.start_run()

    def _restore_app_state(self) -> None:
        state = load_state()
        if state.get("lastWorkspaceRoot") and not self.project.workspaceRoot:
            self.project.workspaceRoot = state["lastWorkspaceRoot"]
        if state.get("lastRunsRoot") and not self.project.runsRoot:
            self.project.runsRoot = state["lastRunsRoot"]

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override.
        state = load_state()
        state["lastWorkspaceRoot"] = self.project.workspaceRoot
        state["lastRunsRoot"] = self.project.runsRoot
        save_state(state)
        super().closeEvent(event)

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.clear()
        projects = get_recent_projects()
        if not projects:
            action = self.recent_menu.addAction("<none>")
            action.setEnabled(False)
            return
        for path in projects:
            action = self.recent_menu.addAction(path)
            action.triggered.connect(lambda _checked=False, p=path: self._open_recent_project(p))

    def _open_recent_project(self, path: str) -> None:
        try:
            project = load_project(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open recent project failed", str(exc))
            return
        self.project_file = Path(path)
        self._set_project(project)

    def clear_recent_projects(self) -> None:
        clear_recent_projects()
        self._refresh_recent_menu()
