"""Content entry points: the new-simulation wizard, gallery examples, scans and the backend geometry view."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox

from g4usim_gui.core import examples as gallery, scan as parameter_scan, wizard as simulation_wizard
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.preview3d.backend_inputs import external_inputs, generated_inputs
from g4usim_gui.preview3d.trajectories import available_runs, load_trajectories
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard


class ContentMixin:
    """Content entry points: the new-simulation wizard, gallery examples, scans and the backend geometry view. Mixed into MainWindow."""

    def scan_base(self) -> tuple[parameter_scan.ScanBase, str, str, str]:
        """Snapshot of the Configuration page for a parameter scan (same inputs as Generate & Run)."""
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        if self.project.runInputMode != "generated":
            raise ValueError(ui_text("Parameter scans use the Configuration page as run input (generated mode)."))
        page = self.config_builder_page
        paths = page.path_settings(self.project)
        base = parameter_scan.ScanBase(
            project=copy.deepcopy(self.project), paths=paths, run=page.run_settings(),
            geometry_settings=page.geometry_settings(), geometry=copy.deepcopy(page.geometry_document),
            source=copy.deepcopy(page.source_editor), physics=copy.deepcopy(page.physics_editor),
            scoring=copy.deepcopy(page.scoring_editor),
            materials=copy.deepcopy(page.material_document) if page.material_document.is_dirty else None)
        return base, paths.runs_root, self.project.executable or paths.executable, self.project.workspaceRoot

    def open_new_simulation_wizard(self) -> None:
        if not self.can_mutate_workspace('wizard'):
            return
        wizard = NewSimulationWizard(self)
        hint = QLabel(ui_text('Wizard drafts are temporary. Finish applies one undoable change to the project; Cancel discards the draft.'))
        hint.setWordWrap(True)
        wizard.scenario_page.layout().insertWidget(0, hint)
        if wizard.exec() != NewSimulationWizard.Accepted:
            return
        self.apply_simulation_wizard(wizard.spec, run_after=wizard.run_after_finish())

    def apply_simulation_wizard(self, spec: simulation_wizard.WizardSpec, *, run_after: bool) -> bool:
        """Put a wizard result into the current project (in place) and show the Configuration page."""
        if not self.can_mutate_workspace('wizard'):
            return False
        try:
            result = simulation_wizard.build(spec)
            candidate = copy.deepcopy(self.project)
            self.project_page.apply_to_project(candidate)
            simulation_wizard.apply_to_project(candidate, result)
            self._check_project_projection(candidate)
        except ValueError as error:
            QMessageBox.warning(self, ui_text("New simulation"), str(error))
            return False
        with self.workspace_transaction('Apply simulation wizard'):
            self._update_project_from_page_without_preview()
            simulation_wizard.apply_to_project(self.project, result)
            self.project.materialEditor = None
            self.project.editingState = None
            previous = self._history_restoring
            self._history_restoring = True
            try:
                self._project_initial_projection(self.project)
            finally:
                self._history_restoring = previous
        index = self.page_stack.indexOf(self.config_builder_page)
        self.page_stack.setCurrentIndex(index)
        self._nav_buttons[index].setChecked(True)
        self.statusBar().showMessage(
            ui_format("New simulation {name}: review the editors or press Generate & Run.", name=spec.project_name),
            8000)
        if run_after:
            self.generate_package(run_after_generate=True)
        return True

    def open_example(self, example_id: str) -> bool:
        """Load a gallery example: its wizard spec into the project, its bundled results into the views."""
        example = gallery.find(example_id)
        if example is None:
            return False
        if not self.apply_simulation_wizard(example.spec(), run_after=False):
            return False
        if example.is_scan:
            if example.has_results():
                self.scan_page.refresh_base()
                self.scan_page.select_parameter(example.scan_parameter)
                self.scan_page.values.setText(example.scan_values)
                self.scan_page.name.setText(example.id)
                self.scan_page.load_scan(example.scan_dir())
                self.scan_page.select_quantity(*example.scan_quantity)
            self.page_stack.setCurrentWidget(self.scan_page)
        elif example.has_results():
            self.output_page.set_output_dir(str(example.output_dir()))
            self.output_page.show_plot(example.plot)
            self.page_stack.setCurrentWidget(self.output_page)
        message = ("Example {name} loaded with its bundled scan results; Create scan makes new run packages."
                   if example.is_scan else
                   "Example {name} loaded with its bundled results; Generate & Run computes it again.")
        self.statusBar().showMessage(ui_format(message, name=ui_text(example.title)), 10000)
        return True

    def export_backend_geometry(self, auto: bool = False) -> None:
        """Show the world Geant4 builds (roadmap A5/G1); generated mode needs no run package."""
        self._update_project_from_page_without_preview()
        page = self.config_builder_page
        executable = self.project.executable
        try:
            if self.project.runInputMode == "external":
                inputs = external_inputs(self.project.configPath, executable)
            else:
                inputs = generated_inputs(
                    template=page.geometry_settings().template, geometry_config=page.geometry_config.text().strip(),
                    geometry=page.geometry_document, materials_config=page.materials_config.text().strip(),
                    materials=page.material_document, executable=executable)
        except (ValueError, OSError) as exc:
            if auto:
                page.refresh_3d_preview()
            page.show_backend_geometry_message(ui_text(str(exc)))
            return
        self.geometry_controller.request(inputs, executable, self.project.workspaceRoot)

    def load_tracks(self, directory: str = "", *, quiet: bool = False) -> bool:
        """Overlay a run's particle tracks (roadmap G6): the given folder, else the last run's output."""
        page = self.config_builder_page
        candidates = [directory] if directory else [self.project.outputDir, self.output_page._output_dir]
        try:
            folder = next((c for c in candidates if c and available_runs(c)), "")
        except ValueError as error:
            page.preview3d_messages.setPlainText(ui_format("Cannot load tracks: {error}", error=error))
            return False
        if not folder and not quiet and not directory:
            folder = QFileDialog.getExistingDirectory(self, ui_text("Choose a run output folder with trajectory files"),
                                                      self.project.outputDir or "")
        if not folder:
            if not quiet:
                page.preview3d_messages.setPlainText(ui_text(
                    "No trajectory files found. Set 'Particle tracks of the first events' on the Run Config tab "
                    "and run again."))
            return False
        try:
            trajectories = load_trajectories(folder)
        except ValueError as error:
            if not quiet:
                page.preview3d_messages.setPlainText(ui_format("Cannot load tracks: {error}", error=error))
            return False
        page.preview3d_widget.show_trajectories(trajectories)
        self.statusBar().showMessage(ui_format("Tracks of {count} events loaded in the 3D view (run {run}).",
                                               count=len(trajectories.events), run=trajectories.run), 8000)
        return True

    def _on_backend_mesh(self, mesh, cached: bool) -> None:
        self.config_builder_page.set_backend_geometry_busy(False)
        # the Source editor's source is the run's only when the package is generated from the Configuration page
        self.config_builder_page.show_backend_geometry(
            mesh, cached, with_source=(self.project.runInputMode or "generated") == "generated")

    def _on_backend_geometry_failed(self, reason: str) -> None:
        self.config_builder_page.set_backend_geometry_busy(False)
        self.config_builder_page.show_backend_geometry_message(
            ui_format("Geant4 could not build this geometry: {reason}", reason=reason))
