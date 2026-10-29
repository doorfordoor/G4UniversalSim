"""Projects: the default project, open/save/recent, keeping pages and the project in step, history packages."""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

from pathlib import Path
from g4usim_gui.core import install_layout
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.project import G4USimProject, load_project, save_project
from g4usim_gui.history.run_history_store import (
    add_recent_project,
    clear_recent_projects,
    get_recent_projects,
    load_state,
)
from g4usim_gui.history.run_package_actions import duplicate_package
from g4usim_gui.models.package_model import PathSettings


class ProjectMixin:
    """Projects: the default project, open/save/recent, keeping pages and the project in step, history packages. Mixed into MainWindow."""

    def _default_project(self) -> G4USimProject:
        root = install_layout.application_root()
        runs_root = install_layout.default_runs_root()
        output = runs_root / "demo" / "output"
        project = G4USimProject(
            projectName="demo",
            runInputMode="generated",
            workspaceRoot=str(root),
            configPath="",
            macroPath="",
            outputDir=str(output),
            runsRoot=str(runs_root),
            threads=1,
            runName="demo_run",
        )
        executable = install_layout.default_backend_executable()
        project.executable = executable
        project.pathSettings = PathSettings(
            executable=executable,
            workspace_root=str(root),
            runs_root=str(runs_root),
            # the materials the demo geometry uses (silicon, iron, water, ...), as test/main_hierarchical.ini
            materials_config=str(root / "test" / "materials" / "test_materials.ini"),
            geometry_config=str(root / "test" / "geometry" / "hierarchical_test.ini"),
        )
        project.geometrySettings.config_path = project.pathSettings.geometry_config
        project.geometrySettings.template = "hierarchical"
        return project

    def _set_project(self, project: G4USimProject) -> None:
        self.project = project
        self.scenario_page.set_executable(project.executable)
        self.run_page.set_macro_plan("")
        self._generated_package_stale = project.runInputMode == "generated"
        self._generated_package_dir = ""
        self.project_page.set_project(project)
        self.config_builder_page.set_from_project(project)
        self.output_page.set_workspace_root(project.workspaceRoot, project.executable)
        self.output_page.set_output_dir(project.outputDir)
        self.run_history_page.set_runs_root(project.runsRoot)
        self.project_context.setText(
            ui_format("Project: {name}", name=project.projectName or ui_text("untitled"))
        )
        self.build_command_preview(show_errors=False)

    def _update_project_from_page(self) -> None:
        before = self._project_page_stale_signature(self.project)
        macro_before = self._macro_inspection_inputs()
        self.project_page.apply_to_project(self.project)
        after = self._project_page_stale_signature(self.project)
        if macro_before != self._macro_inspection_inputs():
            self.run_page.set_macro_plan(ui_text("Run plan is stale; inputs changed."))
        self.project_context.setText(
            ui_format("Project: {name}", name=self.project.projectName or ui_text("untitled"))
        )
        self._sync_flat_project_to_nested_paths()
        self.config_builder_page.set_run_defaults(self.project)
        self.output_page.set_workspace_root(self.project.workspaceRoot, self.project.executable)
        self.output_page.set_output_dir(self.project.outputDir)
        self.run_history_page.set_runs_root(self.project.runsRoot)
        if before != after and self.project.runInputMode == "generated":
            self._mark_generated_package_stale()
        else:
            self.build_command_preview(show_errors=False)

    def _update_project_from_config_builder(self) -> None:
        self.config_builder_page.update_project(self.project)
        run = self.project.runSettings
        self.project.runName = run.run_name
        self.project.threads = run.threads
        self.project.seed = "" if run.seed is None else str(run.seed)
        self.project_page.set_project(self.project)
        self._mark_generated_package_stale()

    def _update_project_from_page_without_preview(self) -> None:
        self.project_page.apply_to_project(self.project)
        self._sync_flat_project_to_nested_paths()
        self.config_builder_page.set_run_defaults(self.project)
        self.output_page.set_workspace_root(self.project.workspaceRoot, self.project.executable)
        self.output_page.set_output_dir(self.project.outputDir)
        self.run_history_page.set_runs_root(self.project.runsRoot)

    def _sync_flat_project_to_nested_paths(self) -> None:
        self.project.pathSettings.executable = self.project.executable
        self.project.pathSettings.workspace_root = self.project.workspaceRoot
        self.project.pathSettings.runs_root = self.project.runsRoot

    def _project_page_stale_signature(self, project: G4USimProject) -> tuple[object, ...]:
        return (
            project.runInputMode,
            project.projectName,
            project.executable,
            project.workspaceRoot,
            project.outputDir,
            project.runsRoot,
            project.threads,
            project.seed,
            project.runName,
        )

    def _mark_generated_package_stale(self) -> None:
        if self.project.runInputMode != "generated":
            self.build_command_preview(show_errors=False)
            return
        self._generated_package_stale = True
        self.config_builder_page.set_package_path("<stale>")
        self.run_page.set_command([ui_text("Configuration changed; the run package will be regenerated at run time.")])

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open G4UniversalSim project", filter="JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        self._load_project_path(path)

    def _load_project_path(self, path: str, *, snapshot: bool = False) -> bool:
        try:
            project = load_project(path)
        except Exception as exc:  # noqa: BLE001 - user-facing project load errors.
            QMessageBox.critical(self, ui_text("Open project failed"), str(exc))
            return False
        self._set_project(project)
        if not snapshot:
            self.project_file = Path(path)
            add_recent_project(path)
            self._refresh_recent_menu()
        self.statusBar().showMessage(ui_format("Loaded project: {path}", path=path), 5000)
        return True

    def save_project(self) -> None:
        if self.project_file is None:
            self.save_project_as()
            return
        self._save_project_to(self.project_file)

    def save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save G4UniversalSim project", filter="JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        if self._save_project_to(Path(path)):
            self.project_file = Path(path)

    def _save_project_to(self, target: Path) -> bool:
        self._update_project_from_page()
        self.config_builder_page.update_project(self.project)
        try:
            save_project(self.project, target)
        except Exception as exc:  # noqa: BLE001 - keep the previous project path on failure.
            QMessageBox.critical(self, ui_text("Save project failed"), str(exc))
            return False
        self.statusBar().showMessage(ui_format("Saved project: {path}", path=target), 5000)
        add_recent_project(str(target))
        self._refresh_recent_menu()
        return True

    def open_migration_preview(self) -> None:
        from g4usim_gui.widgets.migration_dialog import MigrationDialog

        dialog = MigrationDialog(self, open_project=self._load_project_path)
        dialog.exec()

    def load_snapshot_into_project(self, snapshot_path: str) -> None:
        # Keep historical package paths visible, but users can generate a new package before running.
        if self._load_project_path(snapshot_path, snapshot=True):
            self.statusBar().showMessage(ui_text("Snapshot loaded. You can generate a new package or rerun with the existing package."), 8000)

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
        self.project.runInputMode = "external"
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

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.clear()
        projects = get_recent_projects()
        self.start_page.set_recent_projects(projects)
        if not projects:
            action = self.recent_menu.addAction("<none>")
            action.setEnabled(False)
            return
        for path in projects:
            action = self.recent_menu.addAction(path)
            action.triggered.connect(lambda _checked=False, p=path: self._open_recent_project(p))

    def _open_recent_project(self, path: str) -> None:
        self._load_project_path(path)

    def clear_recent_projects(self) -> None:
        clear_recent_projects()
        self._refresh_recent_menu()
