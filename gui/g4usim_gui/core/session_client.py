"""Protocol/state client for ``g4usim-session-v1``.

The single process owner stays :class:`G4USimRunner`: this module attaches to it
through ``sessionData``/``processStarted``/``finished`` signals, so the GUI keeps
one runner for K1, scans, ordinary runs and sessions. This client never starts a
second ``QProcess`` and never blocks the Qt main thread; requests are answered by
signal callbacks and per-request Qt timers.
"""
from __future__ import annotations

import codecs
import json
import os
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, Signal

from g4usim_gui.core.run_progress import PREFIX as PROGRESS_PREFIX, ProgressParser
from g4usim_gui.core.session_model import (
    ENERGY_ERROR_TEXT,
    next_revision,
    DRAFT_TEXT,
    MAX_EVENTS,
    PROTOCOL,
    describe_rejection,
    empty_view,
    format_energy,
    merge_round,
    parse_energy_text,
    session_eligibility,
    summarize_round,
)

if False:  # pragma: no cover - type-checking only, avoids a runtime import cycle
    from g4usim_gui.core.runner import G4USimRunner


class SessionClient(QObject):
    """Turns the owned runner process into a controllable A/B/A session."""

    stateChanged = Signal(object)
    roundStarted = Signal(object)
    roundFinished = Signal(object)
    roundRejected = Signal(object)
    frameLogged = Signal(str)
    logReceived = Signal(str)
    failure = Signal(str)
    closed = Signal(object)

    HANDSHAKE_TIMEOUT_MS = 20_000
    REQUEST_TIMEOUT_MS = 60_000
    CANCEL_TIMEOUT_MS = 10_000
    SHUTDOWN_TIMEOUT_MS = 15_000

    def __init__(self, runner, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = runner
        self._started = False
        self._replay_mode = False
        runner.sessionData.connect(self._on_session_data)
        runner.processStarted.connect(self._on_process_started)
        runner.finished.connect(self._on_runner_finished)
        runner.errorOccurred.connect(self._on_runner_error)
        self._handshake_timer = QTimer(self)
        self._handshake_timer.setSingleShot(True)
        self._handshake_timer.timeout.connect(self._on_handshake_timeout)
        self._request_timers: dict[str, QTimer] = {}
        self._stdout_decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._stderr_decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._progress = ProgressParser()
        self._view: dict[str, Any] = empty_view()
        self._view["draft"] = {"status": "draft", "message": DRAFT_TEXT["draft"]}
        self._seq = 0
        self._revision = 0
        self._pending: dict[str, dict[str, Any]] = {}
        self._round_plan: dict[str, Any] | None = None
        self._round_source: dict[str, Any] = {}
        self._closing_expected = False
        self._last_stderr = ""

    # ------------------------------------------------------------------ state
    def is_active(self) -> bool:
        return self._started and bool(self._runner.is_running())

    def is_handshaken(self) -> bool:
        return bool(self._view.get("session", {}).get("session_id"))

    def snapshot(self) -> dict[str, Any]:
        view = dict(self._view)
        view["session"] = dict(view.get("session") or {})
        view["source"] = dict(view.get("source") or {})
        view["run"] = dict(view.get("run") or {})
        view["draft"] = dict(view.get("draft") or {})
        view["last_rejection"] = dict(view.get("last_rejection") or {})
        view["rounds"] = [dict(item) for item in view.get("rounds") or []]
        view["active"] = self.is_active()
        return view

    def _emit(self) -> None:
        self.stateChanged.emit(self.snapshot())

    def _set_message(self, message: str) -> None:
        self._view["message"] = message

    def _set_draft(self, status: str, message: str = "") -> None:
        self._view["draft"] = {"status": status, "message": message or DRAFT_TEXT.get(status, "")}

    def _adopt_revision(self, frame: dict[str, Any]) -> None:
        # Session revisions only move forward: a stale cached ack must not roll
        # the client back to a revision the backend already superseded.
        revision = next_revision(self._revision, frame.get("state_revision"))
        self._revision = revision
        self._view["state_revision"] = revision

    # -------------------------------------------------------------- lifecycle
    def start(self, project, command: list[str]) -> None:
        self._start_session(project, command, replay=False)

    def start_replay(self, project, command: list[str]) -> None:
        """Replay a recorded, completed session in a new backend process."""
        self._start_session(project, command, replay=True)

    def _start_session(self, project, command: list[str], *, replay: bool) -> None:
        if self._runner.is_running():
            self.failure.emit("A run or session is already active.")
            return
        self._replay_mode = replay
        self._seq = 0
        self._revision = 0
        self._closing_expected = False
        self._round_plan = None
        self._round_source = {}
        self._progress = ProgressParser()
        self._stdout_decoder.reset()
        self._stderr_decoder.reset()
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._last_stderr = ""
        self._started = True
        self._view = empty_view()
        self._view["phase"] = "starting"
        self._view["session"] = {
            "command": list(command),
            "config": str(getattr(project, "configPath", "") or ""),
            "alive": True,
            "threads": int(getattr(project, "threads", 0) or 0),
        }
        self._view["draft"] = {"status": "draft", "message": DRAFT_TEXT["draft"]}
        self._handshake_timer.start(self.HANDSHAKE_TIMEOUT_MS)
        self._set_message("Starting the backend session process.")
        self._emit()
        self._runner.start_session(project, command)

    def shutdown(self) -> None:
        if not self.is_active() or self._closing_expected:
            return
        if not self.is_handshaken():
            self._closing_expected = True
            self._runner.kill()
            return
        self._closing_expected = True
        self._view["phase"] = "stopping"
        self._set_message("Closing the session; waiting for the backend to acknowledge.")
        self._send_request("shutdown", {}, timeout_ms=self.SHUTDOWN_TIMEOUT_MS,
                           on_ok=self._on_shutdown_ack, on_reject=self._on_shutdown_rejected)
        self._emit()

    def kill(self) -> None:
        self._closing_expected = True
        self._runner.kill()

    # --------------------------------------------------------------- requests
    def _send_request(self, op: str, params: dict[str, Any] | None = None, *,
                      timeout_ms: int | None = None,
                      on_ok: Callable[[dict[str, Any]], None] | None = None,
                      on_reject: Callable[[dict[str, Any], str], None] | None = None) -> str:
        self._seq += 1
        request_id = _hex_id()
        frame: dict[str, Any] = {
            "kind": "request",
            "seq": self._seq,
            "id": _hex_id(),
            "request_id": request_id,
            "op": op,
        }
        if op != "get_state":
            frame["state_revision"] = self._revision
        if params is not None:
            frame["params"] = params
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._on_request_timeout(request_id))
        timer.start(timeout_ms or self.REQUEST_TIMEOUT_MS)
        self._request_timers[request_id] = timer
        self._pending[request_id] = {"op": op, "on_ok": on_ok, "on_reject": on_reject}
        self._write_frame(frame)
        self.frameLogged.emit(f"→ {op}")
        return request_id

    def _write_frame(self, frame: dict[str, Any]) -> None:
        payload = json.dumps(frame, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._runner.write_session_data(payload + b"\n")

    def _finish_request(self, request_id: str) -> dict[str, Any] | None:
        timer = self._request_timers.pop(request_id, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        return self._pending.pop(request_id, None)

    def _on_request_timeout(self, request_id: str) -> None:
        pending = self._finish_request(request_id)
        op = str((pending or {}).get("op") or "request")
        self.failure.emit(f"The backend did not answer {op} within the timeout.")
        self._set_message(f"{op}: no response before the timeout.")
        if self._round_plan is not None:
            self._abort_round("timeout", f"{op} timed out")
        self._emit()

    # ------------------------------------------------------------------ round
    def start_round(self, *, particle: str, energy_text: str, events: int,
                    position: str | None = None, direction: str | None = None) -> None:
        if not self.is_handshaken():
            self.failure.emit("Start (and initialize) the session before running a round.")
            return
        if self._round_plan is not None or self._view.get("phase") == "running":
            self._reject_local(
                "busy",
                "A round is already running in this session; wait for its receipt or cancel it.",
            )
            return
        if self._view.get("phase") != "ready":
            self.failure.emit("The session is not ready for another round.")
            return
        editable, reason = session_eligibility(self._view)
        if not editable:
            self._reject_local("source_not_editable", reason)
            return
        energy_mev, error = parse_energy_text(energy_text)
        if energy_mev is None:
            message = ENERGY_ERROR_TEXT.get(error or "energy_number", "Invalid energy.")
            self._reject_local(error or "energy_number", f"{message} ({energy_text!r})")
            return
        if int(events) <= 0 or int(events) > MAX_EVENTS:
            self._reject_local("invalid_events", f"Events must be in 1..{MAX_EVENTS}.")
            return
        steps: list[tuple[str, dict[str, Any]]] = [
            ("set_source", {"field": "particle", "value": particle}),
            ("set_source", {"field": "energy", "value": f"{energy_mev:.12g} MeV"}),
        ]
        if position:
            steps.append(("set_source", {"field": "position", "value": position}))
        if direction:
            steps.append(("set_source", {"field": "direction", "value": direction}))
        steps.append(("run", {"events": int(events)}))
        self._round_source = {"particle": particle, "energy_mev": energy_mev,
                              "energy_text": format_energy(energy_mev),
                              "position": position or "", "direction": direction or ""}
        self._round_plan = {"steps": steps, "index": 0, "events": int(events)}
        self._set_draft("pending", "Sending the round parameters to the backend.")
        self._view["last_rejection"] = {}
        self._emit()
        self._advance_round()

    def _advance_round(self) -> None:
        plan = self._round_plan
        if plan is None:
            return
        if plan["index"] >= len(plan["steps"]):
            self._round_plan = None
            return
        op, params = plan["steps"][plan["index"]]
        plan["index"] += 1
        if op == "run":
            self._send_request("run", params, on_ok=self._on_run_accepted,
                               on_reject=self._on_round_rejected)
        else:
            self._send_request("set_source", params,
                               on_ok=lambda response, params=params: self._on_edit_accepted(response, params),
                               on_reject=self._on_round_rejected)

    def _on_edit_accepted(self, response: dict[str, Any], params: dict[str, Any]) -> None:
        resolved = response.get("resolved")
        if isinstance(resolved, dict) and resolved:
            self._view["source"] = dict(resolved)
        self._set_draft("accepted", "The backend accepted the round parameter; no kernel event has run yet.")
        self._emit()
        self._advance_round()

    def _on_run_accepted(self, response: dict[str, Any]) -> None:
        self._view["phase"] = "running"
        self._view["run"] = {
            "request_id": response.get("request_id") or "",
            "run_request_id": response.get("run_request_id") or response.get("request_id") or "",
            "run_id": None,
            "planned_events": response.get("planned_events"),
            "completed_events": 0,
            "status": "running",
            "cancel_requested": False,
            "progress": {},
        }
        self._set_message("Round accepted; the backend is running it in this session.")
        self._set_draft("accepted", "Round accepted; waiting for the per-round receipt.")
        self._emit()

    def cancel_round(self) -> None:
        if self._view.get("phase") != "running":
            self.failure.emit("No round is active to cancel.")
            return
        run = self._view.get("run") or {}
        params: dict[str, Any] = {}
        request_id = run.get("run_request_id") or run.get("request_id")
        if request_id:
            params["run_request_id"] = request_id
        self._send_request("cancel", params, timeout_ms=self.CANCEL_TIMEOUT_MS,
                           on_ok=self._on_cancel_accepted, on_reject=self._on_cancel_rejected)
        self._set_message("Cancel requested; the run stops at the next event boundary.")
        self._emit()

    def _on_cancel_accepted(self, _response: dict[str, Any]) -> None:
        run = dict(self._view.get("run") or {})
        run["cancel_requested"] = True
        self._view["run"] = run
        self._set_message("Cancel accepted by the backend.")
        self._emit()

    def _on_cancel_rejected(self, response: dict[str, Any], message: str) -> None:
        self._set_message(f"Cancel rejected: {message}")
        self._view["last_rejection"] = {"op": "cancel", "reason": response.get("reason") or "",
                                        "message": response.get("message") or ""}
        self._emit()

    def _abort_round(self, reason: str, message: str) -> None:
        self._round_plan = None
        self._set_draft("rejected", "The backend rejected the round; no run was started.")
        self._view["last_rejection"] = {"op": "round", "reason": reason, "message": message}
        self.roundRejected.emit(self.snapshot())

    def _reject_local(self, reason: str, message: str) -> None:
        self._set_draft("rejected", "The parameter was rejected before it reached the backend.")
        self._view["last_rejection"] = {"op": "local", "reason": reason, "message": message}
        self._emit()
        self.roundRejected.emit(self.snapshot())

    def _on_round_rejected(self, response: dict[str, Any], message: str) -> None:
        self._abort_round(str(response.get("reason") or "rejected"), message)
        self._set_message(f"Round rejected: {message}")
        self._emit()

    # ----------------------------------------------------------- frame parsing
    def _on_session_data(self, data: bytes, is_stdout: bool) -> None:
        if not self._started:
            return
        if is_stdout:
            text = self._stdout_decoder.decode(bytes(data))
            if not text:
                return
            self._stdout_buffer += text
            while "\n" in self._stdout_buffer:
                line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
                line = line.rstrip("\r")
                if line:
                    self._handle_stdout_line(line)
        else:
            text = self._stderr_decoder.decode(bytes(data))
            if not text:
                return
            self._stderr_buffer += text
            while "\n" in self._stderr_buffer:
                line, self._stderr_buffer = self._stderr_buffer.split("\n", 1)
                line = line.rstrip("\r")
                if not line:
                    continue
                self._last_stderr = line
                self.logReceived.emit(f"stderr: {line}")

    def _handle_stdout_line(self, line: str) -> None:
        if line.startswith(PROGRESS_PREFIX):
            self._handle_progress(line[len(PROGRESS_PREFIX):])
            return
        stripped = line.lstrip()
        if stripped.startswith("{"):
            try:
                frame = json.loads(stripped)
            except json.JSONDecodeError:
                self.logReceived.emit(f"stdout: {line}")
                return
            if isinstance(frame, dict) and str(frame.get("kind") or ""):
                self._handle_frame(frame)
                return
        self.logReceived.emit(f"stdout: {line}")

    def _handle_progress(self, payload: str) -> None:
        messages = self._progress.feed(PROGRESS_PREFIX + payload + "\n", final=True)
        for message in messages:
            run = dict(self._view.get("run") or {})
            if not run:
                continue
            run["run_id"] = message.get("run_id", run.get("run_id"))
            run["planned_events"] = message.get("planned_events", run.get("planned_events"))
            run["completed_events"] = message.get("completed_events", run.get("completed_events"))
            run["progress"] = message
            self._view["run"] = run
            self._emit()

    def _handle_frame(self, frame: dict[str, Any]) -> None:
        self.frameLogged.emit(f"← {_frame_summary(frame)}")
        kind = str(frame.get("kind") or "")
        if kind == "welcome":
            self._on_welcome(frame)
        elif kind == "response":
            self._on_response(frame)
        elif kind == "event":
            self._on_event(frame)
        elif kind == "error":
            self._on_error_frame(frame)
        else:
            self.logReceived.emit(f"session frame: {_frame_summary(frame)}")

    def _on_welcome(self, frame: dict[str, Any]) -> None:
        self._handshake_timer.stop()
        self._adopt_revision(frame)
        session = dict(self._view.get("session") or {})
        state = frame.get("state") if isinstance(frame.get("state"), dict) else {}
        session.update({
            "session_id": str(frame.get("session_id") or ""),
            "protocol": str(frame.get("protocol") or ""),
            "backend": dict(frame.get("backend") or {}),
            "limits": dict(frame.get("limits") or {}),
            "output_root": str(state.get("output_root") or session.get("output_root") or ""),
            "record_root": str(state.get("record_root") or session.get("record_root") or ""),
            "session_root": str(state.get("session_root") or ""),
        })
        self._view["session"] = session
        self._apply_state(state)
        replay_info = frame.get("replay") if isinstance(frame.get("replay"), dict) else None
        if self._replay_mode:
            if not replay_info or not replay_info.get("replayable"):
                self._view["phase"] = "failed"
                self._set_message("The backend refused to replay this session.")
                self.failure.emit("The backend refused to replay this session.")
                self._emit()
                self._closing_expected = True
                self._runner.kill()
                return
            self._view["replay"] = dict(replay_info)
            self._view["phase"] = "replaying"
            self._set_message("Replaying the recorded rounds from the captured random engine state.")
            self._emit()
            return
        self._set_message("Session ready. The generated configuration was loaded; initializing the kernel.")
        self._view["phase"] = "initializing"
        self._emit()
        self._send_request("initialize", {}, on_ok=self._on_initialize_accepted,
                           on_reject=self._on_initialize_rejected)

    def _on_initialize_accepted(self, response: dict[str, Any]) -> None:
        self._view["kernel"] = str(response.get("kernel_state") or "idle")
        self._view["phase"] = "ready"
        self._set_message("Kernel initialized. Edit the next round, then run it.")
        self._emit()

    def _on_initialize_rejected(self, response: dict[str, Any], message: str) -> None:
        self._view["phase"] = "failed"
        self._view["last_rejection"] = {"op": "initialize", "reason": response.get("reason") or "",
                                        "message": response.get("message") or ""}
        self.failure.emit(f"Kernel initialization failed: {message}")
        self._set_message(f"Kernel initialization failed: {message}")
        self._emit()

    def _apply_state(self, state: Any) -> None:
        if not isinstance(state, dict):
            return
        self._view["kernel"] = str(state.get("kernel_state") or self._view.get("kernel") or "pre_init")
        source = state.get("source")
        if isinstance(source, dict):
            self._view["source"] = dict(source)
        self._adopt_revision(state)
        if isinstance(state.get("draft_revision"), int):
            self._view["draft_revision"] = state["draft_revision"]
        for key in ("output_root", "record_root", "session_root"):
            if state.get(key):
                session = dict(self._view.get("session") or {})
                session[key] = str(state[key])
                self._view["session"] = session

    def _on_response(self, frame: dict[str, Any]) -> None:
        request_id = str(frame.get("request_id") or "")
        pending = self._finish_request(request_id)
        status = str(frame.get("status") or "")
        self._adopt_revision(frame)
        if status in {"rejected", "failed"}:
            message = describe_rejection(frame)
            if pending is not None:
                callback = pending.get("on_reject")
                if callback is not None:
                    callback(frame, message)
                    self._emit()
                    return
            self._view["last_rejection"] = {"op": str(frame.get("op") or ""),
                                            "reason": frame.get("reason") or "",
                                            "message": frame.get("message") or ""}
            self._set_message(f"Backend rejected {frame.get('op')}: {message}")
            self.failure.emit(message)
            self._emit()
            return
        if pending is not None:
            callback = pending.get("on_ok")
            if callback is not None:
                callback(frame)
                self._emit()
                return
        self._emit()

    def _on_event(self, frame: dict[str, Any]) -> None:
        event = str(frame.get("event") or "")
        if event == "run_started":
            self._adopt_revision(frame)
            run = dict(self._view.get("run") or {})
            run.update({
                "run_id": frame.get("run_id"),
                "run_request_id": frame.get("run_request_id") or run.get("run_request_id"),
                "planned_events": frame.get("planned_events"),
                "completed_events": 0,
                "status": "running",
                "cancel_requested": bool(frame.get("cancel_requested")),
            })
            self._view["run"] = run
            self._view["phase"] = "running"
            self.roundStarted.emit(self.snapshot())
            self._emit()
            return
        if event == "run_finished":
            self._on_run_finished(frame)
            return
        if event == "closing":
            self._view["phase"] = "stopping"
            self._set_message(str(frame.get("reason") or "Session is closing."))
            self._emit()
            return
        self.logReceived.emit(f"session event: {_frame_summary(frame)}")
        self._emit()

    def _on_run_finished(self, frame: dict[str, Any]) -> None:
        self._adopt_revision(frame)
        source = self._round_source
        record = summarize_round(frame, str(source.get("particle") or ""), source.get("energy_mev"))
        self._view["rounds"] = merge_round(self._view.get("rounds") or [], record)
        run = dict(self._view.get("run") or {})
        run.update({
            "run_id": record.get("run_id"),
            "completed_events": record.get("completed_events"),
            "planned_events": record.get("planned_events"),
            "status": record.get("status"),
            "cancel_requested": record.get("cancel_requested"),
            "receipt_ok": record.get("receipt_ok"),
            "receipt_reason": record.get("receipt_reason"),
            "receipt_path": record.get("receipt_path"),
        })
        self._view["run"] = run
        self._view["phase"] = "ready"
        self._view["kernel"] = "idle"
        self._round_plan = None
        self._round_source = {}
        if record.get("receipt_ok"):
            self._set_draft("accepted", "Round finished; the receipt was verified against its path, size and SHA-256.")
            self._set_message(f"Round {record.get('run_id')} finished: {record.get('status')}.")
        else:
            self._set_draft("rejected", "Round finished but the receipt could not be verified; do not treat it as a complete success.")
            self._set_message("Round finished, but the receipt could not be verified.")
        self.roundFinished.emit(record)
        self._emit()

    def _on_error_frame(self, frame: dict[str, Any]) -> None:
        code = str(frame.get("code") or "error")
        message = str(frame.get("message") or "")
        self._set_message(f"Backend error: {code}{(': ' + message) if message else ''}")
        if code in {"frame_too_large", "invalid_json", "non_object_root", "duplicate_key"}:
            self._view["phase"] = "failed"
        self.failure.emit(f"{code}: {message}" if message else code)
        self._emit()

    # ----------------------------------------------------------------- process
    def _flush_buffers(self) -> None:
        if self._stdout_buffer.strip():
            for line in self._stdout_buffer.splitlines():
                if line.strip():
                    self._handle_stdout_line(line.rstrip("\r"))
        if self._stderr_buffer.strip():
            self._last_stderr = self._stderr_buffer.strip().splitlines()[-1]
            self.logReceived.emit(f"stderr: {self._stderr_buffer.strip()}")
        self._stdout_buffer = ""
        self._stderr_buffer = ""

    def _on_process_started(self) -> None:
        if not self._started:
            return
        self._view["phase"] = "handshaking"
        self._set_message("Backend process started; sending the protocol handshake.")
        self._write_frame({"kind": "hello", "protocol": PROTOCOL})
        self.frameLogged.emit("→ hello")
        self._emit()

    def can_replay(self) -> bool:
        replay = self._view.get("replay") if isinstance(self._view.get("replay"), dict) else {}
        return (bool(replay.get("replayable")) and self._view.get("phase") == "closed"
                and not self.is_active())

    def _load_replay_manifest(self) -> None:
        session = dict(self._view.get("session") or {})
        root = str(session.get("session_root") or "")
        if not root:
            return
        path = Path(root) / "replay-manifest.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        self._view["replay"] = {
            "manifest_path": str(path),
            "replayable": bool(data.get("replayable")),
            "reason": str(data.get("reason") or ""),
            "steps": [dict(step) for step in data.get("steps") or [] if isinstance(step, dict)],
        }

    def _on_runner_finished(self, exit_code: int) -> None:
        if not self._started:
            return
        self._handshake_timer.stop()
        for request_id in list(self._pending):
            self._finish_request(request_id)
        self._flush_buffers()
        expected = self._closing_expected
        self._started = False
        self._view["phase"] = "closed" if expected else "failed"
        if expected and exit_code == 0:
            self._set_message("Session closed.")
        elif expected:
            self._set_message(f"Session process exited with code {exit_code}.")
        else:
            self._set_message(f"Session process ended unexpectedly with code {exit_code}.")
        session = dict(self._view.get("session") or {})
        session["alive"] = False
        self._view["session"] = session
        if expected and exit_code == 0 and not self._replay_mode:
            self._load_replay_manifest()
        payload = {"exit_code": exit_code, "expected": expected,
                   "session": dict(session)}
        self._emit()
        self.closed.emit(payload)
        if not expected:
            detail = self._last_stderr or "no stderr output"
            self.failure.emit(f"Session ended unexpectedly (exit code {exit_code}): {detail}")

    def _on_runner_error(self, message: str) -> None:
        if not self._started:
            return
        self.failure.emit(message)
        self._set_message(message)
        self._emit()

    def _on_handshake_timeout(self) -> None:
        if self.is_handshaken() or not self._started:
            return
        self._view["phase"] = "failed"
        self.failure.emit("The backend did not complete the session handshake before the timeout.")
        self._set_message("The handshake timed out.")
        self._emit()
        self._closing_expected = True
        self._runner.kill()

    def _on_shutdown_ack(self, _response: dict[str, Any]) -> None:
        self._set_message("The backend accepted the shutdown request; waiting for the process to exit.")

    def _on_shutdown_rejected(self, _response: dict[str, Any], message: str) -> None:
        self._set_message(f"Shutdown was rejected: {message}")
        self.failure.emit(f"Shutdown was rejected: {message}")


def _hex_id() -> str:
    return os.urandom(16).hex()


def _frame_summary(frame: dict[str, Any]) -> str:
    kind = frame.get("kind")
    if kind == "response":
        return f"response {frame.get('op')} {frame.get('status')}"
    if kind == "event":
        return f"event {frame.get('event')}"
    if kind == "welcome":
        return "welcome"
    if kind == "error":
        return f"error {frame.get('code')}"
    return str(kind or "frame")
