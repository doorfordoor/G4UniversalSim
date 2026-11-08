"""Qt-only checks for the controlled-session panel and its Qt-free model.

The real backend is exercised separately in ``smoke_session_backend.py``.  This
test owns no backend process: it feeds the panel the same view dictionaries the
session client emits and verifies the visible state, the receipt qualification
and the translation wiring.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "gui", ROOT / "gui" / "smoke_tests"):
    text = str(entry)
    if text not in sys.path:
        sys.path.insert(0, text)

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QLabel

import gui_test_window  # noqa: E402  (also isolates the history state file)
from g4usim_gui.core import i18n, theme  # noqa: E402
from g4usim_gui.core.session_model import (  # noqa: E402
    PROTOCOL,
    ReceiptCheck,
    next_revision,
    parse_energy_text,
    receipt_check_for_event,
    session_eligibility,
    verify_receipt_reference,
)
from g4usim_gui.core.session_client import SessionClient  # noqa: E402
from PySide6.QtCore import QObject, Signal  # noqa: E402


def answer(value: object) -> None:
    assert value is True or value == "" or value == 0 or value == [], value


def base_view(**overrides: object) -> dict:
    view = {
        "phase": "ready",
        "kernel": "idle",
        "state_revision": 3,
        "session": {
            "alive": True,
            "session_id": "session-1",
            "threads": 1,
            "backend": {"source_fingerprint": "f" * 64, "build_git_commit": "a" * 40},
            "output_root": str(Path(tempfile.gettempdir()) / "session-out"),
            "record_root": str(Path(tempfile.gettempdir()) / "session-records"),
            "session_root": str(Path(tempfile.gettempdir()) / "session-records" / "session-1"),
        },
        "source": {
            "source_count": 1,
            "phase_space": False,
            "advanced": False,
            "ion": False,
            "preset": "proton_beam",
            "particle": "proton",
            "energy_type": "mono",
            "mono_energy_MeV": 100.0,
            "position_type": "point",
            "isotropic": False,
            "has_direction": True,
        },
        "run": {},
        "draft": {"status": "draft", "message": "", "params": {}, "state_revision": 3},
        "limits": {"max_frame_bytes": 65536, "max_events_per_run": 100_000_000},
        "last_rejection": {},
        "feedback": [],
    }
    view.update(overrides)
    return view


def round_record(index: int, *, receipt_ok: bool, reason: str = "") -> dict:
    return {
        "index": index,
        "run_id": index,
        "run_request_id": f"{index:032x}",
        "parameter_summary": "proton 100 MeV",
        "planned_events": 5,
        "completed_events": 5,
        "status": "completed",
        "cancel_requested": False,
        "receipt_ok": receipt_ok,
        "receipt_reason": reason,
        "receipt_path": f"/tmp/session/run-{index:04d}.json",
        "receipt_sha256": ("ab" * 32) if receipt_ok else "",
        "artifacts_truncated": False,
        "artifact_count": 3,
        "output_failed": False,
    }


def write_receipt(directory: Path, *, run_id: int = 0, request_id: str = "0" * 32) -> tuple[Path, str]:
    receipt = {
        "schema": "g4usim_session_run_receipt_v1",
        "session_id": "session-1",
        "run_request_id": request_id,
        "run_id": run_id,
        "planned_events": 5,
        "completed_events": 5,
        "aborted_events": 0,
        "status": "completed",
        "cancel_requested": False,
        "output_failed": False,
        "artifacts": [],
    }
    path = directory / f"run-{run_id:04d}.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def model_checks(directory: Path) -> None:
    assert PROTOCOL == "g4usim-session-v1"
    for text, expected, key in (
        ("100 MeV", 100.0, ""),
        ("50keV", 0.05, ""),
        ("1.5e2 MeV", 150.0, ""),
        ("2 GeV", 2000.0, ""),
        ("1 eV", 1e-6, ""),
        ("1 keV", 1e-3, ""),
        ("1 TeV", 1e6, ""),
        ("100", 100.0, ""),
        ("", None, "energy_empty"),
        ("50 banana", None, "energy_unit"),
        ("abc MeV", None, "energy_number"),
        ("-1 MeV", None, "energy_range"),
        ("inf MeV", None, "energy_number"),
        # Case-sensitive units: milli-eV is not mega-eV.
        ("1 meV", None, "energy_unit"),
        ("1 mev", None, "energy_unit"),
        ("1 MEV", None, "energy_unit"),
        # Overflow (inf) and underflow (0) are rejected before reaching the backend.
        ("1e308 TeV", None, "energy_range"),
        ("1e-323 eV", None, "energy_range"),
        ("1e999 MeV", None, "energy_number"),
    ):
        value, reason = parse_energy_text(text)
        assert reason == key, (text, reason, key)
        if expected is not None:
            assert value is not None and abs(value - expected) < 1e-12, (text, value)
    assert next_revision(5, 3) == 5
    assert next_revision(5, 5) == 5
    assert next_revision(0, 7) == 7
    assert next_revision(5, True) == 5
    assert next_revision(5, -2) == 5
    assert next_revision(5, None) == 5
    assert next_revision(-3, 2) == 2

    class StubRunner(QObject):
        sessionData = Signal(bytes, bool)
        processStarted = Signal()
        finished = Signal(int)
        errorOccurred = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self.session_started = 0
            self.running = False
            self.killed = False

        def is_running(self) -> bool:
            return self.running

        def start_session(self, project, command) -> None:
            self.session_started += 1
            self.running = True

        def write_session_data(self, payload) -> int:
            return len(payload)

        def kill(self) -> None:
            self.killed = True
            self.running = False

    stub = StubRunner()
    client = SessionClient(stub)
    try:
        client._adopt_revision({"state_revision": 5})
        assert client.snapshot()["state_revision"] == 5
        # A stale ack that arrives after a newer state must not roll the client back.
        client._adopt_revision({"state_revision": 3})
        assert client._revision == 5 and client.snapshot()["state_revision"] == 5
        client._adopt_revision({"state_revision": True})
        client._adopt_revision({"state_revision": -4})
        client._adopt_revision({"state_revision": None})
        assert client.snapshot()["state_revision"] == 5
        client._adopt_revision({"state_revision": 6})
        assert client.snapshot()["state_revision"] == 6
        project = type("Project", (), {"configPath": "main.ini", "threads": 1})()
        client.start(project, ["G4UniversalSim.exe"])
        client._handshake_timer.stop()
        assert stub.session_started == 1
        # A new session starts from revision 0 and never compares across sessions.
        assert client._revision == 0 and client.snapshot()["state_revision"] == 0
        assert client.snapshot()["phase"] == "starting"
    finally:
        client.deleteLater()

    editable, reason = session_eligibility(base_view())
    assert editable and reason == "", (editable, reason)
    for patch, key in (
        ({"source": {**base_view()["source"], "source_count": 2}}, "multiple_sources"),
        ({"source": {**base_view()["source"], "phase_space": True}}, "phase_space_source"),
        ({"source": {**base_view()["source"], "advanced": True}}, "advanced_source"),
        ({"source": {**base_view()["source"], "ion": True}}, "ion_source"),
        ({"source": {**base_view()["source"], "preset": "isotropic_neutron"}}, ""),
    ):
        editable, reason = session_eligibility(base_view(**patch))
        assert reason == key, (patch, reason, key)
    assert session_eligibility(None) == (False, "unsupported")

    path, digest = write_receipt(directory)
    check = verify_receipt_reference(
        {"path": str(path), "schema": "g4usim_session_run_receipt_v1",
         "sha256": digest, "size_bytes": path.stat().st_size},
        expected_run_id=0,
        expected_run_request_id="0" * 32,
    )
    assert check.ok and check.sha256 == digest, check
    bad = verify_receipt_reference(
        {"path": str(path), "schema": "g4usim_session_run_receipt_v1",
         "sha256": "0" * 64, "size_bytes": path.stat().st_size},
        expected_run_id=0,
        expected_run_request_id="0" * 32,
    )
    assert not bad.ok and bad.reason == "sha_mismatch", bad
    wrong_run = verify_receipt_reference(
        {"path": str(path), "schema": "g4usim_session_run_receipt_v1",
         "sha256": digest, "size_bytes": path.stat().st_size},
        expected_run_id=1,
        expected_run_request_id="0" * 32,
    )
    assert not wrong_run.ok and wrong_run.reason == "run_mismatch", wrong_run

    inline_ok = receipt_check_for_event({
        "receipt_integrity": "written",
        "run_id": 0,
        "run_request_id": "0" * 32,
        "receipt": {"schema": "g4usim_session_run_receipt_v1", "run_id": 0,
                    "run_request_id": "0" * 32, "status": "completed"},
        "status": "completed",
    })
    assert inline_ok.ok, inline_ok
    unavailable = receipt_check_for_event({
        "receipt_integrity": "unavailable",
        "run_id": 0,
        "run_request_id": "0" * 32,
        "receipt": {"schema": "g4usim_session_run_receipt_v1", "run_id": 0,
                    "run_request_id": "0" * 32, "status": "completed"},
        "status": "completed",
    })
    assert not unavailable.ok and unavailable.reason == "receipt_unavailable", unavailable
    unknown = receipt_check_for_event({"receipt_integrity": "maybe", "status": "completed"})
    assert not unknown.ok and unknown.reason == "receipt_integrity_unknown", unknown
    missing = receipt_check_for_event({"status": "completed"})
    assert not missing.ok and missing.reason == "missing_receipt", missing
    thin = receipt_check_for_event({
        "receipt_integrity": "written",
        "receipt_ref": {"path": str(path), "schema": "g4usim_session_run_receipt_v1",
                        "sha256": digest, "size_bytes": path.stat().st_size},
        "run_id": 0,
        "run_request_id": "0" * 32,
        "status": "completed",
    })
    assert thin.ok, thin

    # Encoding a valid receipt by reference must not change status admission.
    paired_path = directory / "paired-receipt.json"
    for receipt_status in ("completed", "failed", "aborted", "cancelled"):
        payload = {"schema": "g4usim_session_run_receipt_v1", "run_id": 0,
                   "run_request_id": "0" * 32, "status": receipt_status}
        raw = json.dumps(payload).encode("utf-8")
        paired_path.write_bytes(raw)
        reference = {"path": str(paired_path), "size_bytes": len(raw),
                     "sha256": hashlib.sha256(raw).hexdigest()}
        for event_status in ("completed", "failed", "aborted", "cancelled"):
            envelope = {"receipt_integrity": "written", "run_id": 0,
                        "run_request_id": "0" * 32, "status": event_status}
            inline = receipt_check_for_event({**envelope, "receipt": payload})
            referenced = receipt_check_for_event({**envelope, "receipt_ref": reference})
            assert (inline.ok, inline.reason) == (referenced.ok, referenced.reason)
            assert inline.ok == (event_status == receipt_status)
            if not inline.ok:
                assert inline.reason == "status_mismatch"
        for key, value, reason in (("run_id", 1, "run_mismatch"),
                                   ("run_request_id", "different", "request_mismatch"),
                                   ("run_request_id", None, "request_mismatch")):
            envelope = {"receipt_integrity": "written", "run_id": 0,
                        "run_request_id": "0" * 32, "status": receipt_status, key: value}
            for representation in ({"receipt": payload}, {"receipt_ref": reference}):
                check = receipt_check_for_event({**envelope, **representation})
                assert not check.ok and check.reason == reason, check
        # File integrity precedes semantics, including a status conflict.
        broken = receipt_check_for_event({"run_id": 0, "run_request_id": "0" * 32,
            "status": "conflict", "receipt_ref": {**reference, "sha256": "0" * 64}})
        assert not broken.ok and broken.reason == "sha_mismatch", broken

    valid = {"schema": "g4usim_session_run_receipt_v1", "run_id": 0,
             "run_request_id": "request", "status": "completed"}
    for evidence in ({"output_failed": True},
                     {"artifacts": [{"integrity_status": "unavailable", "reason": "read failed"}]}):
        payload = {**valid, **evidence}
        raw = json.dumps(payload).encode("utf-8")
        paired_path.write_bytes(raw)
        reference = {"path": str(paired_path), "size_bytes": len(raw),
                     "sha256": hashlib.sha256(raw).hexdigest()}
        for representation in ({"receipt": payload}, {"receipt_ref": reference}):
            check = receipt_check_for_event({**valid, **representation})
            assert not check.ok and check.reason == "artifact_unavailable", check
    absent = object()
    for key, values in (("run_id", [absent, None, False, 0.0, -1]),
                        ("run_request_id", [absent, None, "", 1, False]),
                        ("status", [absent, None, "", "unknown", 1])):
        for value in values:
            for malformed_side in ("envelope", "receipt", "both"):
                envelope = {k: valid[k] for k in ("run_id", "run_request_id", "status")}
                payload = dict(valid)
                for obj in ([envelope] if malformed_side == "envelope" else
                            [payload] if malformed_side == "receipt" else [envelope, payload]):
                    if value is absent:
                        obj.pop(key)
                    else:
                        obj[key] = value
                raw = json.dumps(payload).encode("utf-8")
                paired_path.write_bytes(raw)
                reference = {"path": str(paired_path), "size_bytes": len(raw),
                             "sha256": hashlib.sha256(raw).hexdigest()}
                for representation in ({"receipt": payload}, {"receipt_ref": reference}):
                    check = receipt_check_for_event({**envelope, **representation})
                    assert not check.ok, (key, value, malformed_side, check)


def find_ancestor(widget, predicate) -> bool:
    parent = widget.parentWidget()
    while parent is not None:
        if predicate(parent):
            return True
        parent = parent.parentWidget()
    return False


def panel_checks(app: QApplication, directory: Path) -> None:
    window = gui_test_window.MainWindow()
    # The window may still hold the recovery lease when the interpreter exits;
    # detach the temporary directory finalizer instead of failing at shutdown.
    window._smoke_recovery_directory._finalizer.detach()
    window.resize(1440, 900)
    window.show()
    for _ in range(3):
        app.processEvents()
    panel = window.session_panel
    assert panel is not None
    assert window.run_page.session_panel is panel
    assert window.run_page.experiment_panel is not None
    assert find_ancestor(panel, lambda widget: widget.objectName() == "runContentScroll")
    assert window.session_client is not None
    assert window.session_owns_process() is False

    panel.set_view(base_view())
    assert panel.submit_button.isEnabled() is True
    assert panel.energy_edit.isEnabled() is True
    assert panel.events_spin.isEnabled() is True
    assert panel.particle_combo.isEnabled() is True
    assert panel.position_edit.isEnabled() is True
    assert panel.direction_edit.isEnabled() is True
    assert panel.whitelist_hint.text() != ""

    # A completed round stays visible as history; phase is ready and the next
    # round must be editable through the real controls (regression: A/B/A).
    panel.set_view(base_view(run={"run_id": 0, "run_request_id": "a" * 32,
                                  "planned_events": 5, "completed_events": 5,
                                  "status": "completed", "cancel_requested": False}))
    assert panel.status_chip.text() == "Ready for the next round", panel.status_chip.text()
    assert panel.energy_edit.isEnabled() is True
    assert panel.events_spin.isEnabled() is True
    assert panel.submit_button.isEnabled() is True

    panel.set_view(base_view(
        source={**base_view()["source"], "source_count": 2},
        phase="ready",
    ))
    assert panel.submit_button.isEnabled() is False
    assert panel.energy_edit.isEnabled() is False
    assert panel.events_spin.isEnabled() is False
    assert panel.particle_combo.isEnabled() is False
    hint = panel.whitelist_hint.text()
    assert hint == "multiple_sources" or "multiple_sources" in hint or "多个" in hint, hint

    running = base_view(phase="running", run={"run_id": 0, "run_request_id": "ab" * 16,
                                              "planned_events": 10, "completed_events": 4})
    panel.set_view(running)
    assert panel.cancel_button.isEnabled() is True
    assert panel.energy_edit.isEnabled() is False
    assert panel.events_spin.isEnabled() is False
    assert panel.submit_button.isEnabled() is False

    # Replay is only offered for a cleanly closed session with a replayable
    # manifest; a refused record keeps its reason visible on the button.
    panel.set_view(base_view(
        phase="closed",
        session={**base_view()["session"], "alive": False},
        replay={"manifest_path": str(Path(tempfile.gettempdir()) /
                                     "g4usim-replay-manifest.json"),
                "replayable": True,
                "reason": "", "steps": []},
    ))
    assert panel.replay_button.isEnabled() is True
    replayed: list[bool] = []
    panel.replayRequested.connect(lambda: replayed.append(True))
    panel.replay_button.click()
    assert replayed == [True]
    panel.set_view(base_view(
        phase="closed",
        session={**base_view()["session"], "alive": False},
        replay={"manifest_path": "", "replayable": False,
                "reason": "the session did not finish every run", "steps": []},
    ))
    assert panel.replay_button.isEnabled() is False
    tooltip = panel.replay_button.toolTip()
    assert "cannot be replayed" in tooltip.lower() or "无法重放" in tooltip, tooltip
    panel.set_view(base_view())

    panel.set_rounds([])
    panel.add_round(round_record(0, receipt_ok=True))
    assert len(panel.rounds()) == 1
    panel.add_round(round_record(1, receipt_ok=False, reason="receipt_unavailable"))
    assert len(panel.rounds()) == 2 and panel.rounds_table.rowCount() == 2
    receipt_cell = panel.rounds_table.item(1, 6).text()
    assert "unavailable" in receipt_cell or "fail" in receipt_cell, receipt_cell
    tooltip = panel.rounds_table.item(1, 6).toolTip()
    assert "receipt" in tooltip.lower(), tooltip

    panel.set_message("Info Next round is ready.", "info")
    assert panel.feedback_view.toPlainText() != ""

    # Replay terminals are judged by closing facts, never by exit code alone.
    from g4usim_gui.core.session_client import replay_terminal_problem
    good_round = [round_record(0, receipt_ok=True), round_record(1, receipt_ok=True)]
    good_closing = {"reason": "replay_finished", "exit_code": 0,
                    "steps_total": 6, "steps_executed": 2}
    assert replay_terminal_problem(good_closing, good_round) == ""
    assert replay_terminal_problem({}, good_round) != ""
    assert replay_terminal_problem(
        {"reason": "replay_failed", "exit_code": 4, "message": "replay step 4 failed"},
        good_round) != ""
    assert replay_terminal_problem(
        {**good_closing, "steps_executed": 3}, good_round) != ""
    assert replay_terminal_problem(
        {**good_closing, "steps_total": 1}, good_round) != ""
    assert replay_terminal_problem(
        {**good_closing, "steps_executed": 0}, good_round) != ""
    assert replay_terminal_problem(
        good_closing, [round_record(0, receipt_ok=True),
                       round_record(1, receipt_ok=False, reason="receipt_unavailable")]) != ""
    cancelled_round = dict(good_round[1])
    cancelled_round["status"] = "cancelled"
    assert replay_terminal_problem(good_closing, [good_round[0], cancelled_round]) != ""
    assert replay_terminal_problem(
        {**good_closing, "exit_code": 4}, good_round) != ""

    panel.set_draft_defaults(particle="e-", energy_text="50 MeV", events=7)
    draft = panel.draft()
    assert draft.get("energy_text") == "50 MeV" or draft.get("energy") == "50 MeV", draft
    assert int(draft.get("events") or 0) == 7, draft

    panel.set_view(base_view())
    toggled = []
    panel.submitRoundRequested.connect(lambda: toggled.append(True))
    panel.submit_button.click()
    assert toggled == [True]

    window._set_language("zh_CN")
    for _ in range(3):
        app.processEvents()
    assert "连续" in panel.title_label.text(), panel.title_label.text()
    assert panel.submit_button.text() != "Submit next round", panel.submit_button.text()
    window._set_language("en")
    for _ in range(3):
        app.processEvents()

    theme.apply_theme(app, "dark", light_skin="B", dark_skin="midnight")
    panel.refresh_theme()
    assert panel.status_chip is not None
    theme.apply_theme(app, "light", light_skin="B", dark_skin="midnight")

    panel.set_expanded(False)
    assert panel.is_expanded() is False
    panel.set_expanded(True)
    assert panel.is_expanded() is True

    # Exercise the real stdout -> client -> window -> panel path. A path alone
    # does not qualify a reference, and inline receipt precedence is retained.
    for index, variant in enumerate(("reference", "inline", "bad_sha", "path_only", "both"), 20):
        request_id = f"{index:032x}"
        path, digest = write_receipt(directory, run_id=index, request_id=request_id)
        reference = {"path": str(path), "size_bytes": path.stat().st_size, "sha256": digest}
        frame = {"kind": "event", "event": "run_finished", "run_id": index,
                 "run_request_id": request_id, "status": "completed",
                 "planned_events": 5, "completed_events": 5, "aborted_events": 0,
                 "receipt_integrity": "written"}
        if variant in {"reference", "bad_sha", "both"}:
            frame["receipt_ref"] = {**reference, "sha256": "0" * 64} if variant == "bad_sha" else reference
        if variant in {"inline", "both"}:
            frame["receipt"] = json.loads(path.read_text(encoding="utf-8"))
        if variant == "path_only":
            frame["receipt_path"] = str(path)
        window.session_client._handle_stdout_line(json.dumps(frame))
        app.processEvents()
        record = next(item for item in panel.rounds() if item["run_request_id"] == request_id)
        row = next(i for i, item in enumerate(panel.rounds()) if item["run_request_id"] == request_id)
        cell = panel.rounds_table.item(row, 6)
        if variant == "reference":
            assert record["receipt_reference"] == reference
            assert cell.text() == "Record verified", cell.text()
            assert str(path) in cell.toolTip() and digest in cell.toolTip()
        elif variant in {"inline", "both"}:
            assert record["receipt_ok"] and record["receipt_reference"] is None
            assert cell.text() == "Inline record verified", cell.text()
        else:
            assert not record["receipt_ok"] and record["receipt_reference"] is None
            assert cell.text().startswith("Record unusable: "), cell.text()
            assert record["receipt_reason"] == ("sha_mismatch" if variant == "bad_sha" else "missing_receipt")
    window.close()
    app.processEvents()


def main() -> int:
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tempfile.mkdtemp(prefix="g4usim-session-settings-"))
    app = QApplication(["-session-panel"])
    app.setStyle("Fusion")
    i18n.apply_language(app, "en")
    theme.apply_theme(app, "light", light_skin="B", dark_skin="midnight")
    directory = Path(tempfile.mkdtemp(prefix="g4usim-session-receipts-"))
    model_checks(directory)
    panel_checks(app, directory)
    print("session panel smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
