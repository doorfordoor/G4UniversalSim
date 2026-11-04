"""Continuous-run session wiring: generation, protocol client and panel lifecycle.

The session entry reuses the window's single ``G4USimRunner`` process owner: the
client speaks the versioned JSON-lines protocol through the runner's session
signals, so K1, scans, plain runs and the configuration agent can never be
silently displaced by a second process owner.  When a session holds the owner
the plain run entry is refused; when a plain run or the experiment workflow is
busy the session entry is refused with a visible message.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from g4usim_gui.core.i18n import ui_text
from g4usim_gui.core.session_client import SessionClient
from g4usim_gui.writers.package_writer import create_run_package


class SessionMixin:
    """Owns the controlled-session panel and its generated package."""

    # ------------------------------------------------------------------ setup
    def _setup_session(self) -> None:
        self.session_client = SessionClient(self.runner, parent=self)
        self.session_panel = self.run_page.session_panel
        self.session_panel.startSessionRequested.connect(self.start_session)
        self.session_panel.closeSessionRequested.connect(self.close_session)
        self.session_panel.submitRoundRequested.connect(self.submit_session_round)
        self.session_panel.cancelRoundRequested.connect(self.cancel_session_round)
        self.session_client.stateChanged.connect(self._session_view_changed)
        self.session_client.roundStarted.connect(self._session_round_started)
        self.session_client.roundFinished.connect(self._session_round_finished)
        self.session_client.roundRejected.connect(self._session_round_rejected)
        self.session_client.frameLogged.connect(self.session_panel.append_log)
        self.session_client.logReceived.connect(self.session_panel.append_log)
        self.session_client.failure.connect(self._session_failure)
        self.session_client.closed.connect(self._session_closed)
        self.session_panel.set_view(self.session_client.snapshot())

    # -------------------------------------------------------------- ownership
    def _session_owner(self) -> tuple[bool, str]:
        if self.runner.is_running():
            return False, ui_text("Another run already owns the backend process.")
        experiment = getattr(self, "experiment", None)
        if experiment is not None and getattr(experiment, "busy", False):
            return False, ui_text("The configuration experiment workflow is busy.")
        scan = getattr(self, "scan_page", None)
        scan_runner = getattr(scan, "runner", None)
        if scan_runner is not None and scan_runner.is_running():
            return False, ui_text("A parameter scan already owns the backend process.")
        return True, ""

    def session_owns_process(self) -> bool:
        client = getattr(self, "session_client", None)
        return bool(client is not None and client.is_active())

    # ------------------------------------------------------------------ entry
    def start_session(self) -> None:
        client = getattr(self, "session_client", None)
        if client is None:
            return
        if client.is_active():
            return
        allowed, message = self._session_owner()
        if not allowed:
            self.session_panel.set_message(message, "failed")
            return
        try:
            package = self._create_session_package()
        except Exception as error:  # noqa: BLE001 - shown in the panel, never silent
            self.session_panel.set_message(
                ui_text("Generate package failed") + ": " + str(error), "failed")
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        package_name = Path(str(package.package_dir)).name
        records = (Path(str(package.output_dir)).parent / "session-records"
                   / f"{package_name}-{stamp}")
        records.mkdir(parents=True, exist_ok=True)
        command = self._session_command(package, records)
        self.session_panel.set_expanded(True)
        self.session_panel.clear_log()
        self.session_panel.set_rounds([])
        self.session_panel.set_session_active(True)
        self.session_panel.append_log(ui_text("Starting the controlled session process."))
        self.session_panel.append_log("command: " + " ".join(command))
        client.start(self.project, command)
        self._session_started = True
        self._set_session_owner_controls(True)

    def close_session(self) -> None:
        client = getattr(self, "session_client", None)
        if client is None or not client.is_active():
            return
        self.session_panel.set_message(ui_text(
            "Closing the session; the backend process must exit before the owner is released."))
        client.shutdown()

    def submit_session_round(self) -> None:
        client = getattr(self, "session_client", None)
        if client is None:
            return
        draft = self.session_panel.draft()
        self.session_panel.set_message(ui_text(
            "Submitting this round's parameters; the backend receipt decides the state."))
        client.start_round(
            particle=draft["particle"] or "proton",
            energy_text=draft["energy_text"],
            events=int(draft["events"]),
            position=draft["position"] or None,
            direction=draft["direction"] or None,
        )

    def cancel_session_round(self) -> None:
        client = getattr(self, "session_client", None)
        if client is None:
            return
        client.cancel_round()

    # --------------------------------------------------------------- package
    def _create_session_package(self):
        """Create the generated package synchronously for the session entry.

        The session sends the generated main configuration through the protocol,
        so the INI's macro entry stays empty; ``run.mac`` remains the plain-run
        wrapper and is recorded only as the package artifact.
        """
        if not self.can_mutate_workspace("generate"):
            raise RuntimeError(ui_text("A workspace transaction is in progress."))
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        report = self.config_builder_page.validate_current(self.project)
        if not report.can_run:
            raise RuntimeError("\n".join(report.errors))
        package, _report_text = create_run_package(
            project=self.project,
            paths=self.config_builder_page.path_settings(self.project),
            run=self.config_builder_page.run_settings(),
            geometry=self.config_builder_page.geometry_settings(),
            source=self.config_builder_page.source_settings(),
            physics=self.config_builder_page.physics_settings(),
            scoring=self.config_builder_page.scoring_settings(),
            material_document=(self.config_builder_page.material_document
                               if self.config_builder_page.material_document.is_dirty else None),
            geometry_document=self.config_builder_page.geometry_document,
            source_model=self.config_builder_page.source_editor,
            physics_model=self.config_builder_page.physics_editor,
            scoring_model=self.config_builder_page.scoring_editor,
        )
        self.project.configPath = package.main_ini_path
        self.project.macroPath = package.run_macro_path
        self.project.outputDir = package.output_dir
        settings = self.config_builder_page.run_settings()
        self.project.runName = settings.run_name
        self.project.threads = settings.threads
        self.project.seed = "" if settings.seed is None else str(settings.seed)
        self.project.runInputMode = "generated"
        self._generated_package_dir = package.package_dir
        self._generated_package_stale = False
        self.config_builder_page.set_package_path(package.package_dir)
        self.config_builder_page.set_validation_report(report)
        self.output_page.set_package_dir(package.package_dir, package.output_dir)
        self.run_history_page.set_runs_root(self.project.runsRoot)
        self.run_history_page.refresh()
        return package

    def _session_command(self, package, records: Path) -> list[str]:
        command = [
            self.project.executable,
            "--config", str(package.main_ini_path),
            "--session-server",
            "--output", str(package.output_dir),
            "--session-record-dir", str(records),
        ]
        if self.project.threads:
            command.extend(["--threads", str(self.project.threads)])
        return command

    # --------------------------------------------------------------- signals
    def _refresh_session_chip(self) -> None:
        """Keep the window header honest: a session owns the process, not a single run."""
        phase = str(self.session_client.snapshot().get("phase") or "")
        labels = {
            "starting": ("Session starting", "running"),
            "handshaking": ("Session starting", "running"),
            "initializing": ("Session starting", "running"),
            "ready": ("Session ready", "success"),
            "running": ("Session running", "running"),
            "stopping": ("Session closing", "warning"),
            "closed": ("Session closed", ""),
            "failed": ("Session failed", "failed"),
        }
        state, role = labels.get(phase, ("Session", ""))
        self._set_run_chip(state, role)

    def _session_view_changed(self, view: dict) -> None:
        self.session_panel.set_view(view)
        active = bool(self.session_client.is_active())
        self.session_panel.set_session_active(active)
        self._set_session_owner_controls(active)
        self._set_legacy_run_strip_visible(not active)
        self._refresh_session_chip()

    def _session_round_started(self, view: dict) -> None:
        self.session_panel.set_view(view)
        self.session_panel.append_log(ui_text("Round started; progress comes from the backend's run events."))

    def _session_round_finished(self, record: dict) -> None:
        self.session_panel.add_round(record)
        status = str(record.get("status") or "")
        if record.get("receipt_ok"):
            self.session_panel.append_log(
                ui_text("Round finished: {status} with a verified receipt.").format(status=status))
        else:
            self.session_panel.append_log(
                ui_text("Round finished, but its record is not usable: {reason}").format(
                    reason=record.get("receipt_reason") or "unknown"))
        self.refresh_after_session_round(record)
        self.history_changed()

    def refresh_after_session_round(self, record: dict) -> None:
        """Refresh result/history services without re-granting old round success."""
        output_dir = ""
        session = self.session_client.snapshot().get("session") or {}
        output_dir = str(session.get("output_root") or "")
        if output_dir:
            try:
                self.output_page.set_output_dir(output_dir)
            except Exception:  # noqa: BLE001 - read-only refresh must not break the session
                pass
        self.run_history_page.refresh()

    def _session_round_rejected(self, rejection: dict) -> None:
        self.session_panel.set_rejection(rejection)
        self.session_panel.append_log(
            ui_text("Request rejected; no round was started.") + " " + str(rejection.get("reason") or ""))

    def _session_failure(self, message: str) -> None:
        self._set_run_chip("Session failed", "failed")
        shown = ui_text(message)
        self.session_panel.set_message(shown, "failed")
        self.session_panel.append_log(shown)
        self.statusBar().showMessage(shown, 8000)

    def _session_closed(self, payload: dict) -> None:
        exit_code = int(payload.get("exit_code") or 0)
        expected = bool(payload.get("expected"))
        if expected and exit_code == 0:
            self.session_panel.set_message(ui_text("Session closed; the process owner is free."), "success")
        else:
            self.session_panel.set_message(ui_text(
                "Session process ended without a clean close (exit code {code}).").format(
                    code=exit_code), "failed")
        self.session_panel.set_session_active(False)
        self._set_session_owner_controls(False)
        self._session_started = False
        self._set_legacy_run_strip_visible(True)
        self._refresh_session_chip()
        self.project_page.set_inputs_enabled(True)
        self._update_editor_busy()
        self._set_run_chip("Session closed", "")

    def _set_legacy_run_strip_visible(self, visible: bool) -> None:
        """A session reports its own phase; hide the single-run progress strip meanwhile."""
        for name in ("progress_bar", "progress_label", "state_label", "exit_label",
                     "result_label", "elapsed_label"):
            widget = getattr(self.run_page, name, None)
            if widget is not None:
                widget.setVisible(visible)

    def _set_session_owner_controls(self, active: bool) -> None:
        for widget in (getattr(self.run_page, "run_button", None),
                       getattr(self.run_page, "build_button", None)):
            if widget is not None:
                widget.setEnabled(not active)
        experiment_panel = getattr(self.run_page, "experiment_panel", None)
        if experiment_panel is not None and hasattr(experiment_panel, "setEnabled"):
            experiment_panel.setEnabled(not active)

    # ------------------------------------------------------------- lifecycle
    def stop_session_before_close(self) -> None:
        client = getattr(self, "session_client", None)
        if client is None or not client.is_active():
            return
        client.kill()
        process = getattr(self.runner, "_process", None)
        if process is not None and process.state() is not None:
            process.waitForFinished(1500)
