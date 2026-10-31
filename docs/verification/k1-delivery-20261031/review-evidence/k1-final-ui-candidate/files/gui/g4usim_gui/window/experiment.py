"""Desktop adapter for the shared experiment service; no second run owner."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox

from g4usim_gui.core.i18n import ui_format, ui_text


def experiment_reason(record):
    """Present known reason codes without turning them into new evidence."""
    reason = str(record.get('reason', ''))
    if reason == 'experiment.fields_rejected':
        key = 'Review the field diagnostics before continuing.'
    elif 'record_persistence_failed' in reason:
        key = 'Experiment records could not be saved. This action is not accepted as verified.'
    elif reason == 'experiment.environment_not_ready':
        key = 'Required backend or data is unavailable. Open Environment to choose a working installation.'
    elif record.get('stale') or record.get('status') == 'stale':
        key = 'Configuration or resources changed. Validate the current inputs again.'
    elif record.get('status') == 'cancelled':
        key = 'The experiment action was cancelled.'
    elif record.get('status') == 'pending':
        key = 'Experiment action is in progress.'
    elif record.get('status') == 'passed':
        key = 'Experiment action completed. This qualifies only the indicated evidence level.'
    else:
        key = 'Experiment action failed. Review the diagnostics and action record.'
    return ui_text(key)


def experiment_report(record):
    report = record.get('report')
    if report is not None:
        return report
    if isinstance(record.get('diagnostics'), dict):
        from g4usim_gui.core.diagnostics import diagnostics_from_dict, extend_diagnostics
        from g4usim_gui.validators.config_validator import ValidationReport
        bundle = diagnostics_from_dict(record['diagnostics'])
        report = ValidationReport(list(bundle.errors), list(bundle.warnings), list(bundle.info))
        extend_diagnostics(report, bundle.diagnostics, append=False)
        report.snapshot_id = bundle.snapshot_id
        return report
    return None


class ExperimentMixin:
    def _setup_experiment(self):
        from g4usim_gui.core.experiment_workflow import ExperimentWorkflow
        from g4usim_gui.window import run as run_module
        from g4usim_gui.core.evidence_job import EvidenceJob
        # Display-only association with the process observed by this window.
        # Records/qualification and process ownership remain in the service.
        self._displayed_run_binding = None
        self._run_display_observed = False
        self._experiment_seen_terminal = set()
        self._experiment_loading = False
        self._experiment_close_pending = False
        self._experiment_service_waiting = False
        self._experiment_recovery_closed = False
        self._bundle_job = EvidenceJob(self)
        # The same process is now consumed by the service. The old callbacks
        # remain independently testable protocol adapters, not active owners.
        self._macro_inspection.finished.disconnect(self._on_macro_inspection_finished)
        self._macro_inspection.errorOccurred.disconnect(self._on_macro_inspection_error)
        self.experiment = ExperimentWorkflow(
            self._edit_session, self.runner, inspect_process=self._macro_inspection,
            parent=self, package_factory=lambda **kwargs: run_module.create_run_package(**kwargs),
            apply_snapshot=self._apply_experiment_snapshot,
            records_root=(Path(self._recovery_root) / 'experiment-records'
                          if self._recovery_root is not None else None),
        )
        self.experiment.changed.connect(self._experiment_changed)
        self.experiment.completed.connect(self._experiment_completed)
        self.experiment.closed.connect(self._experiment_service_closed)
        self.run_page.experiment_panel.action_requested.connect(self._experiment_action)
        self.run_page.diagnostics_panel.activationRequested.connect(self._navigate_experiment_diagnostic)
        self._refresh_experiment()

    def _experiment_changed(self):
        records = self.experiment.records()
        if records:
            record = records[-1]
            package = record.get('package', {})
            if (record.get('action') in ('generate', 'run') and record.get('can_run')
                    and not record.get('stale') and package.get('package_dir')
                    and package['package_dir'] != self._generated_package_dir):
                self._bind_experiment_package(record)
        self._update_editor_busy()

    def _apply_experiment_snapshot(self, snapshot):
        # F5 owns projection, rollback and the frozen-workspace failure path.
        self._check_workspace_projection(snapshot)
        self._check_project_history_capacity(snapshot)
        self.apply_workspace(snapshot, reason='experiment')

    def _refresh_experiment(self):
        service = getattr(self, 'experiment', None)
        if service is None:
            return
        panel = self.run_page.experiment_panel
        state = service.state()
        for level in state.get('levels', []):
            if level.get('level') == 'events':
                level['level'] = 'execution'
            if level.get('detail'):
                level['detail'] = experiment_reason(dict(status=level.get('status'), reason=level['detail']))
        for entry in state.get('history', []):
            entry['reason'] = experiment_reason(entry)
        self._project_experiment_run_display(state)
        panel.set_state(state)
        panel.set_busy(service.busy or self._experiment_loading or
                       bool(getattr(self, '_workspace_fault', '')))

    def _bind_started_run_display(self):
        """Bind at the existing runner's actual Starting signal, not preparation.

        A single pending process action is guaranteed by the shared service;
        ambiguity or a legacy runner has no trustworthy current association.
        No label, event count, output path or telemetry run index is an ID.
        """
        records = self.experiment.records()
        candidates = [r for r in records if r.get('status') == 'pending'
                      and not r.get('stale') and (r.get('action') == 'run' or
                          r.get('action') == 'validate' and r.get('level') == 'initialization')]
        self._displayed_run_binding = None
        if len(candidates) == 1:
            record = candidates[0]
            if record.get('record_id') and record.get('run_id') and type(record.get('revision')) is int:
                self._displayed_run_binding = (record['record_id'], record['run_id'], record['revision'])
        self._run_display_observed = True
        self.run_page.begin_run_display()

    def _project_experiment_run_display(self, state):
        """Project existing authority onto the particular result being shown."""
        if not self._run_display_observed:
            return
        binding = self._displayed_run_binding
        records = state.get('history', [])
        record = next((r for r in records if binding is not None and
                       (r.get('record_id'), r.get('run_id'), r.get('revision')) == binding), None)
        if record is None:
            scope = 'unverified'
        elif (record.get('stale') or record.get('status') == 'stale'
              or record.get('revision') != state.get('revision')):
            scope = 'changed'
        elif any(r.get('action') == 'run' or r.get('level') == 'initialization'
                 for r in records[records.index(record) + 1:]):
            scope = 'historical'
        elif self.runner.is_running():
            scope = 'running'
        elif record.get('status') == 'pending' or self.experiment.busy or state.get('qualification') == 'checking':
            scope = 'checking'
        elif record.get('status') == 'passed':
            scope = 'current'
        else:
            scope = 'unverified'
        self.run_page.set_run_display_scope(scope, binding)
        self._render_run_chip()

    def _experiment_action(self, action):
        if action == 'cancel':
            if self._experiment_loading:
                self._bundle_job.cancel()
                self._experiment_loading = False
            self.experiment.cancel()
            self._update_editor_busy()
            return
        if not self.can_mutate_workspace(action):
            return
        self._finish_history_merge()
        try:
            current = self._edit_session.current().project
            if current.runsRoot:
                self.experiment.records_root = Path(current.runsRoot).expanduser().absolute() / 'experiment-records'
            if action == 'environment':
                self._open_environment()
                return
            if action == 'import':
                self._load_experiment_bundle()
                return
            if action == 'export':
                directory = QFileDialog.getExistingDirectory(self, ui_text('Select export parent directory'))
                if not directory:
                    return
                from PySide6.QtWidgets import QInputDialog
                name, accepted = QInputDialog.getText(self, ui_text('Export bundle'), ui_text('New bundle directory name'))
                if not accepted:
                    return
                if not name or name in ('.', '..') or any(char in name for char in '/\\:'):
                    raise ValueError(ui_text('Choose a new simple directory name.'))
                record = self.experiment.export(Path(directory) / name)
            elif action == 'evaluate':
                filename, _ = QFileDialog.getOpenFileName(self, ui_text('Select explicit comparison criteria'), '', 'JSON (*.json)')
                if not filename:
                    return
                from g4usim_gui.core.config_migration import load_json_strict
                with Path(filename).open('rb') as stream:
                    raw = stream.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise ValueError(ui_text('Comparison criteria exceed the size limit.'))
                record = self.experiment.evaluate(comparisons=load_json_strict(raw))
            elif action == 'initialize':
                record = self.experiment.validate(level='initialization')
            elif action == 'validate':
                record = self.experiment.validate(level='fields')
            elif action in ('inspect', 'generate', 'run'):
                if action == 'run':
                    self.run_page.clear_logs()
                    self.run_page.set_result('')
                record = getattr(self.experiment, action)()
            else:
                raise ValueError(f'Unknown experiment action: {action}')
            self._refresh_experiment()
        except Exception as error:
            self._present_raw_run_diagnostic('experiment.action_failed', str(error))
            self.run_page.append_status_message(str(error))
            QMessageBox.warning(self, ui_text('Experiment action failed'), str(error))

    def _experiment_completed(self, record):
        if record.get('status') == 'pending':
            return
        identifier = record.get('record_id')
        if identifier in self._experiment_seen_terminal:
            return
        if identifier:
            self._experiment_seen_terminal.add(identifier)
        action = record.get('action', '')
        if action in ('generate', 'run') and record.get('status') == 'passed' and not record.get('stale'):
            self._bind_experiment_package(record)
        report = experiment_report(record)
        if report is not None and hasattr(report, 'to_text'):
            self.config_builder_page.set_validation_report(report)
            self._present_project_diagnostics(report)
        if action == 'apply':
            self.history_changed()
        # The service owns machine evidence; the adapter only displays it.
        payload = {key: value for key, value in record.items() if key != 'report'}
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        plan = record.get('plan')
        try:
            self.run_page.set_macro_plan(self._format_inspected_plan(plan) if isinstance(plan, dict) else text)
        except (KeyError, TypeError, ValueError) as error:
            self.run_page.set_macro_plan(text)
            self._present_raw_run_diagnostic('backend.inspect_protocol', str(error), raw_message=text)
        self.run_page.append_status_message(experiment_reason(record))
        if record.get('status') == 'failed':
            reason = record.get('reason', text)
            if action == 'inspect':
                raw = reason.removeprefix('experiment.inspect_failed: ')
                self._present_raw_run_diagnostic('backend.inspect_failed', reason, raw_message=raw)
            elif report is None or not report.errors:
                self._present_raw_run_diagnostic('experiment.action_failed', experiment_reason(record), raw_message=text)
            if report is not None and report.errors and not getattr(self, '_closing', False):
                details = '\n'.join(report.errors[:10])
                QMessageBox.warning(self, ui_text('Experiment action failed'),
                                    experiment_reason(record) + '\n\n' + details)
        self._refresh_experiment()
        self._update_editor_busy()
        if self._experiment_close_pending:
            QTimer.singleShot(0, self.close)

    def _navigate_experiment_diagnostic(self, diagnostic):
        location = diagnostic.location
        if location is None or location.editor == 'project':
            return
        page = self.config_builder_page
        current = next((item for item in page.diagnostic_panel.records
                        if item.identity == diagnostic.identity), None)
        if current is not None and page.is_diagnostic_current(current):
            page.navigate_diagnostic(current)

    def _bind_experiment_package(self, record):
        package = record.get('package')
        if not isinstance(package, dict):
            return
        original = self._edit_session.current().project
        for field, key in (('configPath', 'main_ini_path'), ('macroPath', 'run_macro_path'), ('outputDir', 'output_dir')):
            if key in package:
                setattr(self.project, field, str(package[key]))
        self._generated_edit_binding = {
            name: (getattr(original, name), getattr(self.project, name))
            for name in ('configPath', 'macroPath', 'outputDir')
        }
        previous = self._history_restoring
        self._history_restoring = True
        try:
            self.project_page.set_project(self.project)
        finally:
            self._history_restoring = previous
        self._generated_package_dir = str(package.get('package_dir', ''))
        self._generated_package_stale = False
        self.config_builder_page.set_package_path(self._generated_package_dir)
        self.output_page.set_package_dir(self._generated_package_dir, self.project.outputDir)
        self.run_history_page.set_runs_root(self.project.runsRoot)
        self.run_history_page.refresh()
        # This display binding must never publish generated paths into F5.
        command = record.get('command')
        if command:
            launch = record.get('launch') or {}
            execution = record.get('execution_bundle') or {}
            working_directory = (launch.get('working_directory') or execution.get('path')
                                 or ui_text('Unknown'))
            # A completed launch may add transport arguments for a short cwd.
            # Render its observed argv without changing the editor/F5 project.
            if launch.get('program') and isinstance(launch.get('arguments'), list):
                command = [launch['program'], *launch['arguments']]
            self.run_page.set_command(self._format_command_preview(
                command, working_directory=working_directory,
                launch_working_directory=launch.get('launch_working_directory')))

    def _open_environment(self):
        from g4usim_gui.widgets.environment_dialog import EnvironmentDialog
        dialog = EnvironmentDialog([self.project.executable] if self.project.executable else None, self)
        dialog.environment_selected.connect(self._select_environment)
        self._environment_dialog = dialog
        dialog.open()

    def _select_environment(self, facts):
        if not self.can_mutate_workspace('environment'):
            return
        executable = facts.get('executable', '')
        if not executable:
            return
        # Environment selection remains an ordinary reversible editor action;
        # discovery is not permission or evidence to run a simulation.
        with self.workspace_transaction('Select environment'):
            self.project_page.executable.setText(executable)
        self._refresh_experiment()

    def _load_experiment_bundle(self):
        from g4usim_gui.core.experiment_bundle import load_bundle
        directory = QFileDialog.getExistingDirectory(self, ui_text('Load bundle'))
        if not directory:
            return
        executable, _ = QFileDialog.getOpenFileName(self, ui_text('Select executable'), self.project.executable)
        if not executable:
            return
        runs_root = QFileDialog.getExistingDirectory(self, ui_text('Select runs root'), self.project.runsRoot)
        if not runs_root:
            return
        if not self._confirm_unsaved_edits():
            return
        revision = self._edit_session.revision
        self._experiment_loading = True
        self._update_editor_busy()
        def work():
            snapshot = load_bundle(directory, executable=executable)
            snapshot.project.runsRoot = snapshot.project.pathSettings.runs_root = str(Path(runs_root).absolute())
            return snapshot
        def loaded(snapshot, error):
            self._experiment_loading = False
            self._update_editor_busy()
            if getattr(self, '_closing', False):
                return
            try:
                if error is not None:
                    raise error
                if revision != self._edit_session.revision:
                    raise ValueError('experiment.revision_changed')
                self._check_workspace_projection(snapshot)
                self._check_project_history_capacity(snapshot)
                self._edit_session.reset(snapshot, saved=False, apply=self._apply_experiment_snapshot)
                self.project_file = None
                self.experiment.records_root = Path(runs_root).expanduser().absolute() / 'experiment-records'
                self.experiment.invalidate('bundle_loaded_requires_revalidation')
                self.history_changed()
                self.experiment.import_history(snapshot.transient['bundle']['validation_records'])
            except Exception as failure:
                self._present_raw_run_diagnostic('experiment.action_failed', str(failure))
                QMessageBox.warning(self, ui_text('Experiment action failed'), str(failure))
            finally:
                self._update_editor_busy()
        self._bundle_job.submit(work, loaded)

    def _defer_experiment_close(self):
        if self._experiment_loading:
            self._bundle_job.cancel()
            self._experiment_loading = False
        if not self.experiment.busy:
            self._experiment_close_pending = False
            return False
        # The legacy runner is also independently usable. Its aggregate busy
        # flag does not mean there is a service action whose completed will fire.
        has_pending_action = any(r.get('status') == 'pending' and not r.get('stale')
                                 for r in self.experiment.records())
        if not has_pending_action and (self.runner.is_running() or
                                      self._macro_inspection.state() != self._macro_inspection.ProcessState.NotRunning):
            self._experiment_close_pending = False
            return False
        self.experiment.cancel()
        if not self._experiment_close_pending:
            self._experiment_close_pending = True
            QTimer.singleShot(3000, self._force_experiment_close)
        return True

    def _force_experiment_close(self):
        if not self._experiment_close_pending:
            return
        self.experiment.cancel(force=True)
        if not self.experiment.busy:
            self.close()
        else:
            self.statusBar().showMessage(ui_text('Waiting for owned processes to stop before closing.'))

    def _experiment_service_closed(self):
        if self._experiment_service_waiting:
            self._experiment_service_waiting = False
            QTimer.singleShot(0, self.close)
