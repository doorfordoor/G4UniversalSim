"""Projects: the default project, open/save/recent, keeping pages and the project in step, history packages."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import QFileDialog, QMessageBox

from pathlib import Path
from g4usim_gui.core import install_layout
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.project import G4USimProject, load_project, load_project_with_receipt, save_project
from g4usim_gui.history.run_history_store import (
    add_recent_project,
    clear_recent_projects,
    get_recent_projects,
    load_state,
)
from g4usim_gui.history.run_package_actions import duplicate_package, read_generated_run_settings
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

    def _check_project_projection(self, project: G4USimProject) -> None:
        """Reject values the current editors would overflow or silently clamp."""
        page = self.config_builder_page
        bindings = (
            ("project.threads", project.threads, self.project_page.threads),
            ("project.threads", project.threads, page.threads),
            ("project.runSettings.threads", project.runSettings.threads, page.threads),
            ("project.runSettings.beam_on", project.runSettings.beam_on, page.beam_on),
            ("project.scoringSettings.hist_bins", project.scoringSettings.hist_bins, page.hist_bins),
            ("project.scoringEditor.hist_bins", project.scoringEditor.hist_bins, page.scoring_editor_bins),
            ("project.scoringEditor.hist_bins", project.scoringEditor.hist_bins, page.hist_bins),
            ("project.scoringEditor.trajectory_events", project.scoringEditor.trajectory_events, page.scoring_editor_trajectories),
            ("project.sourceEditor.preview_ray_count", project.sourceEditor.preview_ray_count, page.source_editor_preview_rays),
            ("project.sourceEditor.random_seed_preview", project.sourceEditor.random_seed_preview, page.source_editor_preview_seed),
        )
        for path, value, widget in bindings:
            if type(value) is not int or not widget.minimum() <= value <= widget.maximum():
                raise ValueError(ui_format(
                    "Project field {path} = {value} is outside the editable GUI range [{minimum}, {maximum}].",
                    path=path, value=value, minimum=widget.minimum(), maximum=widget.maximum(),
                ))

    def _set_project(self, project: G4USimProject) -> None:
        if getattr(self, '_workspace_fault', ''):
            raise ValueError('Restore the last verified editor state before opening another project.')
        verified = self._edit_session.current() if hasattr(self, '_edit_session') else None
        try:
            if getattr(project, 'editingState', None) is not None:
                from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
                self.apply_workspace(WorkspaceSnapshot(project), reason='open')
            else:
                previous = getattr(self, '_history_restoring', False)
                self._history_restoring = True
                try:
                    self._project_initial_projection(project)
                finally:
                    self._history_restoring = previous
        except Exception as original:
            if verified is not None:
                try:
                    self.apply_workspace(verified, reason='open-rollback')
                except Exception as rollback:
                    from g4usim_gui.core.edit_transactions import TransactionApplyError
                    raise TransactionApplyError(original, rollback) from original
            raise
        self._reset_edit_history()

    def _project_initial_projection(self, project: G4USimProject) -> None:
        self._check_project_projection(project)
        self._clear_project_diagnostics()
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
        if getattr(self, '_workspace_fault', '') and not self._history_restoring:
            return
        before = self._project_page_stale_signature(self.project)
        macro_before = self._macro_inspection_inputs()
        self.project_page.apply_to_project(self.project)
        self.project.seed = self.project_page.seed.text()
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
        if getattr(self, '_workspace_fault', '') and not self._history_restoring:
            return
        self._invalidate_project_diagnostics(force=True)
        self.config_builder_page.update_project(self.project)
        run = self.project.runSettings
        self.project.runName = run.run_name
        self.project.threads = run.threads
        # The parsed setting is None for both empty and invalid input. Preserve
        # the raw mirror so Generate cannot erase an invalid seed before validation.
        self.project.seed = self.config_builder_page.seed.text()
        self.project_page.set_project(self.project)
        self._mark_generated_package_stale()

    def _update_project_from_page_without_preview(self) -> None:
        if getattr(self, '_workspace_fault', '') and not self._history_restoring:
            return
        self.project_page.apply_to_project(self.project)
        self.project.seed = self.project_page.seed.text()
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
        if not self.can_mutate_workspace('open'):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open G4UniversalSim project", filter="JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        self._load_project_path(path)

    def _load_project_path(self, path: str, *, snapshot: bool = False, recent: bool = False) -> bool:
        if not self.can_mutate_workspace('open'):
            return False
        try:
            restored = None
            receipt = None
            if snapshot:
                from g4usim_gui.core.project import load_project_snapshot

                restored = load_project_snapshot(path)
                project = restored.project
            else:
                project, receipt = load_project_with_receipt(path)
            self._check_project_projection(project)
            if project.editingState is not None:
                from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
                self._check_workspace_projection(WorkspaceSnapshot(project))
        except Exception as exc:  # noqa: BLE001 - reject predictable failures before publishing.
            if snapshot:
                QMessageBox.warning(self, ui_text("Load snapshot failed"), str(exc))
            elif recent:
                QMessageBox.warning(self, ui_text("Open recent project failed"), str(exc))
            else:
                QMessageBox.critical(self, ui_text("Open project failed"), str(exc))
            return False
        if not self._confirm_unsaved_edits():
            return False
        self._set_project(project)
        if snapshot:
            self.project_file = None
            self._edit_session.mark_saved()  # imported snapshot is a new document baseline
        if not snapshot:
            self.project_file = Path(path)
            add_recent_project(path)
            self._refresh_recent_menu()
        if restored is not None:
            self._show_snapshot_restore_notes(restored)
        else:
            self.statusBar().showMessage(ui_format("Loaded project: {path}", path=path), 5000)
        self._history_discard_on_close = False
        callback = getattr(self, '_recovery_project_replaced', None)
        if callback is not None:
            callback(origin_path=receipt.path if receipt is not None else '',
                     origin_sha256=receipt.sha256 if receipt is not None else None)
        return True

    def _show_snapshot_restore_notes(self, restored) -> None:
        if restored.package_root:
            scope = ui_text(
                "Restored the package's current materials and geometry, together with the editing parameters recorded in the snapshot. "
                "Validate them again and generate a new run package. Hand-edited main/macro files, unsaved drafts and historical run success were not restored."
            )
            context = ui_format("Package: {path}", path=restored.package_root)
            status = "Package inputs restored; review the details and generate a new package."
        else:
            scope = ui_text("Loaded legacy saved project settings. Original input files and historical results were not verified; validate the settings and generate a new package.")
            context = ""
            status = "Legacy project settings loaded; validate and generate a new package."
        details = "\n\n".join(part for part in (
            scope, context, "\n".join(ui_text(note) for note in restored.notes),
        ) if part)
        page = self.config_builder_page
        page.set_validation_text(details)
        self.run_page.append_status_message(details)
        self.page_stack.setCurrentWidget(page)
        for index in range(page.workspace_tabs.count()):
            container = page.workspace_tabs.widget(index)
            if container is page.details_tabs or container.isAncestorOf(page.details_tabs):
                page.workspace_tabs.setCurrentIndex(index)
                break
        page.details_tabs.setCurrentIndex(0)
        self.statusBar().showMessage(ui_text(status), 8000)

    def save_project(self) -> None:
        if not self.can_mutate_workspace('save'):
            return
        if self.project_file is None:
            self.save_project_as()
            return
        self._save_project_to(self.project_file)

    def save_project_as(self) -> None:
        if not self.can_mutate_workspace('save'):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save G4UniversalSim project", filter="JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        if self._save_project_to(Path(path)):
            self.project_file = Path(path)

    def _save_project_to(self, target: Path) -> bool:
        from g4usim_gui.core.edit_snapshot import project_for_snapshot
        if not self.can_mutate_workspace('save'):
            return False
        self._finish_history_merge()
        if not self.can_mutate_workspace('save'):
            return False
        snapshot = self.capture_workspace()
        try:
            receipt = save_project(project_for_snapshot(snapshot), target)
        except Exception as exc:  # noqa: BLE001 - keep the previous project path on failure.
            QMessageBox.critical(self, ui_text("Save project failed"), str(exc))
            return False
        self._edit_session.mark_saved(snapshot)
        self._history_discard_on_close = False
        self.history_changed()
        callback = getattr(self, '_recovery_project_saved', None)
        if callback is not None:
            callback(origin_path=receipt.path, origin_sha256=receipt.sha256)
        self.statusBar().showMessage(ui_format("Saved project: {path}", path=target), 5000)
        add_recent_project(str(target))
        self._refresh_recent_menu()
        return True

    def open_migration_preview(self) -> None:
        from g4usim_gui.widgets.migration_dialog import MigrationDialog

        dialog = MigrationDialog(self, open_project=self._load_project_path)
        dialog.exec()

    def load_snapshot_into_project(self, snapshot_path: str) -> None:
        self._load_project_path(snapshot_path, snapshot=True)

    def open_history_output(self, package_dir: str, output_dir: str) -> None:
        self.output_page.set_package_dir(package_dir, output_dir)
        self.tabs.setCurrentWidget(self.output_page)

    def duplicate_history_package(self, package_dir: str, *, run_after: bool) -> None:
        if not self.can_mutate_workspace('duplicate') or not self._confirm_unsaved_edits():
            return
        new_package = ""
        try:
            candidate = copy.deepcopy(self.project)
            self.project_page.apply_to_project(candidate)
            new_package = duplicate_package(package_dir, candidate.runsRoot)
            package = Path(new_package)
            startup = read_generated_run_settings(package)
            candidate.configPath = str(package / "config" / "main.ini")
            candidate.macroPath = str(package / "macros" / "run.mac")
            candidate.outputDir = str(package / "output")
            candidate.workspaceRoot = str(package)
            candidate.pathSettings.workspace_root = str(package)
            candidate.pathSettings.executable = candidate.executable
            candidate.pathSettings.runs_root = candidate.runsRoot
            candidate.runInputMode = "external"
            candidate.threads = candidate.runSettings.threads = startup.threads
            candidate.seed = "" if startup.seed is None else str(startup.seed)
            candidate.runSettings.seed = startup.seed
            candidate.runName = candidate.runSettings.run_name = startup.run_name
            self._check_project_projection(candidate)
        except Exception as exc:  # noqa: BLE001
            message = (ui_format("Copy created at {path}, but it was not loaded and no run was started: {error}", path=new_package, error=exc)
                       if new_package else str(exc))
            title = "Copy created; not loaded or run" if new_package else "Duplicate failed"
            QMessageBox.warning(self, ui_text(title), message)
            return
        self._set_project(candidate)
        self.output_page.set_package_dir(str(package), self.project.outputDir)
        self.run_history_page.refresh()
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
        self._load_project_path(path, recent=True)

    def clear_recent_projects(self) -> None:
        clear_recent_projects()
        self._refresh_recent_menu()
