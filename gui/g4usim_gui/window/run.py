"""Running: command preview, input inspection, package generation, start/stop and the runner's signals."""

from __future__ import annotations

import json

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QMessageBox

from pathlib import Path
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.writers.package_writer import create_run_package


class RunMixin:
    """Running: command preview, input inspection, package generation, start/stop and the runner's signals. Mixed into MainWindow."""

    def build_command_preview(self, *, show_errors: bool = True) -> None:
        if getattr(self, '_workspace_fault', ''):
            return
        self._update_project_from_page_without_preview()
        if self.project.runInputMode == "generated" and self._generated_package_stale:
            self.run_page.set_command([ui_text("Configuration changed; the run package will be regenerated at run time.")])
            return
        validation = self.runner.validation_report(self.project)
        self._present_project_diagnostics(validation)
        errors = validation.errors
        if errors:
            self.run_page.set_command(["Validation errors:", *errors])
            if show_errors:
                QMessageBox.warning(self, "Validation failed", "\n".join(errors))
            return
        command = self.runner.build_command(self.project)
        self.run_page.set_command(self._format_command_preview(command))

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

    def _macro_inspection_inputs(self) -> tuple[object, ...]:
        session = getattr(self, '_edit_session', None)
        return (session.revision if session is not None else 0, self.project.runInputMode, self.project.executable,
                self.project.workspaceRoot, self.project.configPath, self.project.macroPath,
                self.project.outputDir, self.project.threads, self.project.seed, self.project.runName)

    def inspect_external_macro(self, *, run_after: bool = False) -> None:
        if not self.can_mutate_workspace('inspect'):
            return
        self.flush_pending_edit()
        if self._macro_inspection.state() != QProcess.NotRunning:
            return
        self._update_project_from_page_without_preview()
        if self.project.runInputMode != "external":
            self.run_page.set_macro_plan(ui_text(
                "Input inspection is available in external mode."
            ))
            return
        validation = self.runner.validation_report(self.project, ready_to_run=True)
        self._present_project_diagnostics(validation)
        errors = validation.errors
        if errors:
            self.run_page.set_macro_plan("\n".join(errors))
            return
        args = ["--inspect-run", *self.runner.build_command(self.project)[1:]]
        self._pending_inspection_run = run_after
        self._macro_inspection_snapshot = self._macro_inspection_inputs()
        self._macro_inspection.setProgram(self.project.executable)
        self._macro_inspection.setArguments(args)
        self._macro_inspection.setWorkingDirectory(self.project.workspaceRoot or str(Path.cwd()))
        self.run_page.set_macro_plan(ui_text("Inspecting inputs with backend preflight..."))
        self._macro_inspection.start()

    def _on_macro_inspection_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        run_after = self._pending_inspection_run
        self._pending_inspection_run = False
        self.project_page.apply_to_project(self.project)
        if self._macro_inspection_snapshot != self._macro_inspection_inputs():
            self.run_page.set_macro_plan(ui_text("Run plan is stale; inputs changed."))
            return
        stderr_raw = bytes(self._macro_inspection.readAllStandardError()).decode("utf-8", errors="replace")
        stderr = stderr_raw.strip()
        stdout = bytes(self._macro_inspection.readAllStandardOutput()).decode("utf-8", errors="replace")
        if exit_status != QProcess.NormalExit or exit_code != 0:
            self.run_page.set_macro_plan(ui_format("Input inspection failed: {reason}", reason=stderr or exit_code))
            self._present_raw_run_diagnostic('backend.inspect_failed',
                ui_format("Input inspection failed: {reason}", reason=stderr or exit_code),
                raw_message=stderr_raw or stdout or str(exit_code))
            return
        try:
            plan = json.loads(stdout)
            if not isinstance(plan, dict):
                raise ValueError('run plan must be a JSON object')
            if plan.get("schema") != "G4UniversalSimRunPlan" or plan.get("version") != 1:
                raise ValueError("unsupported run plan schema")
            commands = plan["macro_plan"]["commands"]
            if not isinstance(commands, list):
                raise ValueError("macro plan commands are not a list")
            lines = [
                ui_text("Configuration before macro execution; runtime results remain unknown."),
                ui_text("Initial configuration and sources:"),
            ]
            for item in plan["initial_configuration"]:
                location = f" {item.get('file', '')}:{item.get('line', '')}" if item["source"] == "main_ini" else ""
                lines.append(f"{item['name']} = {item['value']} [{item['source']}]{location}")
            lines.extend(["", ui_format("Expanded commands: {count}", count=len(commands)),
                          ui_text("Macro commands may change configuration after initialization.")])
            for item in commands:
                lines.append(f"{item['file']}:{item['line']} [{item['category']}] {item['text']}")
            if plan["macro_execution_planned"] and not any(item["category"] == "beam_on" for item in commands):
                lines.extend(["", ui_text("No beamOn command was found; no macro events are planned.")])
            if stderr:
                lines.extend(["", ui_text("Backend diagnostics:"), stderr])
                self._present_raw_run_diagnostic('backend.inspect_messages', stderr, severity='info',
                                                 raw_message=stderr_raw)
            self.run_page.set_macro_plan("\n".join(lines))
            if run_after:
                self._start_current_project()
        except (KeyError, TypeError, ValueError) as error:
            self.run_page.set_macro_plan(ui_format("Input inspection failed: {reason}", reason=str(error)))
            self._present_raw_run_diagnostic('backend.inspect_protocol', str(error),
                                             raw_message=stdout + '\n' + stderr_raw)

    def _on_macro_inspection_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            self._pending_inspection_run = False
            self.project_page.apply_to_project(self.project)
            if self._macro_inspection_snapshot != self._macro_inspection_inputs():
                self.run_page.set_macro_plan(ui_text('Run plan is stale; inputs changed.'))
                return
            self.run_page.set_macro_plan(ui_format("Input inspection failed: {reason}", reason=self._macro_inspection.errorString()))
            self._present_raw_run_diagnostic('backend.inspect_start', self._macro_inspection.errorString())

    def start_run(self) -> None:
        if not self.can_mutate_workspace('run'):
            return
        if self.runner.is_running() or self._macro_inspection.state() != QProcess.NotRunning:
            self.run_page.append_status_message(ui_text("A run is already active."))
            return
        self._finish_history_merge()
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        if self.project.runInputMode == "generated":
            if not self._generate_current_package():
                return
            self._start_current_project()
            return
        self.inspect_external_macro(run_after=True)

    def _start_current_project(self) -> None:
        if not self.can_mutate_workspace('run'):
            return
        validation = self.runner.validation_report(self.project, ready_to_run=True)
        self._present_project_diagnostics(validation)
        errors = validation.errors
        if errors:
            message = "\n".join(errors)
            self.run_page.append_status_message(message)
            QMessageBox.warning(self, "Validation failed", message)
            return
        self.run_page.clear_logs()
        self.run_page.set_result("")
        command = self.runner.build_command(self.project)
        self.run_page.set_command(self._format_command_preview(command))
        self.run_page.append_status_message("Starting run")
        self.statusBar().showMessage("Running", 5000)
        self.runner.start(self.project, command)

    def validate_generated_config(self) -> None:
        if not self.can_mutate_workspace('validate'):
            return
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        try:
            report = self.config_builder_page.validate_current(self.project)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Validation failed", str(exc))
            self.config_builder_page.set_validation_text(str(exc))
            return
        self.config_builder_page.set_validation_report(report)
        if report.can_run:
            self.statusBar().showMessage("Config Builder validation passed", 5000)
        else:
            QMessageBox.warning(self, "Validation failed", "\n".join(report.errors))

    def generate_package(self, run_after_generate: bool) -> None:
        if not self.can_mutate_workspace('generate'):
            return
        self._finish_history_merge()
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        if not self._generate_current_package():
            return
        if run_after_generate:
            self._start_current_project()

    def _generate_current_package(self) -> bool:
        if not self.can_mutate_workspace('generate'):
            return False
        original_paths = self.capture_workspace().project
        try:
            pre_report = self.config_builder_page.validate_current(self.project)
            if not pre_report.can_run:
                self.config_builder_page.set_validation_report(pre_report)
                QMessageBox.warning(self, "Validation failed", "\n".join(pre_report.errors))
                return False
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
                geometry_document=self.config_builder_page.geometry_document,
                source_model=self.config_builder_page.source_editor,
                physics_model=self.config_builder_page.physics_editor,
                scoring_model=self.config_builder_page.scoring_editor,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if getattr(exc, 'report', None) is not None:
                self.config_builder_page.set_validation_report(exc.report)
            else:
                self.config_builder_page.set_validation_text(message)
            QMessageBox.warning(self, "Generate package failed", message)
            return False

        self.project.configPath = package.main_ini_path
        self.project.macroPath = package.run_macro_path
        self.project.outputDir = package.output_dir
        self.project.runName = self.config_builder_page.run_settings().run_name
        self.project.threads = self.config_builder_page.run_settings().threads
        seed = self.config_builder_page.run_settings().seed
        self.project.seed = "" if seed is None else str(seed)
        self.project.runInputMode = "generated"
        self._generated_edit_binding = {
            name: (getattr(original_paths, name), getattr(self.project, name))
            for name in ('configPath', 'macroPath', 'outputDir')
        }
        self.project_page.set_project(self.project)
        self._generated_package_dir = package.package_dir
        self._generated_package_stale = False
        self.config_builder_page.set_package_path(package.package_dir)
        self.config_builder_page.set_validation_report(pre_report)
        self.config_builder_page.validation_text.setPlainText(report_text)
        self.output_page.set_package_dir(package.package_dir, package.output_dir)
        self.run_history_page.set_runs_root(self.project.runsRoot)
        self.run_history_page.refresh()
        self.build_command_preview(show_errors=False)
        self.statusBar().showMessage(f"Generated package: {package.package_dir}", 8000)

        return True

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
        self._set_run_chip(state, "running" if running else "")
        self.project_page.set_inputs_enabled(not running)
        self._update_editor_busy()

    def _on_finished(self, exit_code: int) -> None:
        self.run_page.set_exit_code(exit_code)
        result = self.runner.last_result
        state = result.state if result else "incomplete"
        reason = result.reason if result else "Run result is unavailable."
        self.run_page.set_result(state)
        self.run_page.append_status_message(ui_format("Run result: {state}. {reason}", state=ui_text(state), reason=ui_text(reason)))
        self.project_page.set_inputs_enabled(True)
        self._update_editor_busy()
        self.output_page.set_output_dir(self.project.outputDir)
        self.output_page.refresh()
        self.run_history_page.refresh()
        self.load_tracks(self.project.outputDir, quiet=True)   # a run with trajectories shows them (G6)
        self._set_run_chip(state, {"success": "success", "failed": "failed"}.get(state, ""))
        self.statusBar().showMessage(ui_format("Run result: {state}. {reason}", state=ui_text(state), reason=ui_text(reason)), 8000)

    def _on_runner_error(self, message: str) -> None:
        self.run_page.append_status_message(message)
        QMessageBox.warning(self, "Runner error", message)

    def _on_log_tag(self, level: str, message: str, advice: str) -> None:
        self.statusBar().showMessage(f"{level.upper()}: {message}", 8000)
        detail = f"{level.upper()}: {message}"
        if advice:
            detail += f" | Advice: {advice}"
        self.run_page.append_status_message(detail)
