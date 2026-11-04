"""Real-backend checks for the controlled GUI session panel.

The test drives the same public GUI entry points a user does: the generated
configuration is created through the existing package writer, the session
starts one real backend process, and three rounds (A/B/A) run in it.  It also
checks the visible rejection paths and a bounded close while a round is
running.  No mock replaces the backend.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "gui", ROOT / "gui" / "smoke_tests"):
    text = str(entry)
    if text not in sys.path:
        sys.path.insert(0, text)

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import gui_test_window  # noqa: E402
from g4usim_gui.core import i18n, theme  # noqa: E402


def pump(app: QApplication, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def wait_until(app: QApplication, predicate, timeout: float, label: str):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        app.processEvents()
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {label}")


def main() -> int:
    executable_text = os.environ.get("G4USIM_EXE", "")
    assert executable_text and Path(executable_text).is_file(), "G4USIM_EXE required; no fallback"
    executable = Path(executable_text)

    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope,
                      tempfile.mkdtemp(prefix="g4usim-session-owner-"))
    app = QApplication(["-session-backend"])
    app.setStyle("Fusion")
    i18n.apply_language(app, "en")
    theme.apply_theme(app, "light", light_skin="B", dark_skin="midnight")

    window = gui_test_window.MainWindow()
    window._smoke_recovery_directory._finalizer.detach()
    # Drive the real UI entry the user uses; never fall back to backend discovery.
    window.project_page.executable.setText(str(executable))
    window.flush_pending_edit()
    assert Path(str(window.project.executable)) == executable, window.project.executable

    import atexit

    def _emergency_stop() -> None:
        try:
            if window.session_owns_process():
                window.session_client.kill()
        except Exception:  # noqa: BLE001 - best effort during interpreter teardown
            pass

    atexit.register(_emergency_stop)
    window.resize(1440, 900)
    window.show()
    pump(app, 0.3)

    panel = window.session_panel
    client = window.session_client
    rounds: list[dict] = []
    rejections: list[dict] = []
    client.roundFinished.connect(lambda record: rounds.append(dict(record)))
    client.roundRejected.connect(lambda rejection: rejections.append(dict(rejection)))

    panel.set_draft_defaults(particle="proton", energy_text="100 MeV", events=5)
    window.start_session()
    wait_until(app, lambda: client.snapshot().get("phase") == "ready", 120.0, "session ready")
    view = client.snapshot()
    assert view["session"]["session_id"], view
    command = list(view["session"].get("command") or [])
    assert command and Path(str(command[0])) == executable, command
    assert "--session-server" in command and "--session-record-dir" in command, command
    output_root = Path(str(view["session"]["output_root"]))
    record_root = Path(str(view["session"]["record_root"]))
    assert not record_root.is_relative_to(output_root), (record_root, output_root)
    assert "fingerprint" in panel.backend_label.toolTip() or panel.backend_label.text() != "—"
    assert panel.session_id_label.text() != "—"

    expected = [("100 MeV", 100.0), ("200 MeV", 200.0), ("100 MeV", 100.0)]
    for index, (energy_text, energy_mev) in enumerate(expected):
        if index == 0:
            panel.set_draft_defaults(particle="proton", energy_text=energy_text, events=5)
        else:
            # Drive the real user controls: after a finished round the phase is
            # ready and the inputs must be editable (regression: A/B/A).
            assert panel.energy_edit.isEnabled(), f"energy disabled after round {index - 1}"
            assert panel.events_spin.isEnabled(), f"events disabled after round {index - 1}"
            assert panel.particle_combo.isEnabled(), f"particle disabled after round {index - 1}"
            assert panel.position_edit.isEnabled(), f"position disabled after round {index - 1}"
            assert panel.direction_edit.isEnabled(), f"direction disabled after round {index - 1}"
            panel.energy_edit.setText(energy_text)
            panel.events_spin.setValue(5)
            pump(app, 0.1)
        window.submit_session_round()
        wait_until(app, lambda: len(rounds) > index, 180.0, f"round {index} finished")
        record = rounds[index]
        assert record["status"] == "completed", record
        assert record["planned_events"] == 5 and record["completed_events"] == 5, record
        assert record["receipt_ok"] is True, record
        assert record["run_id"] == index, record
        assert abs(float(record["energy_mev"]) - energy_mev) < 1e-9, record
        wait_until(app, lambda: client.snapshot().get("phase") == "ready", 60.0,
                   f"round {index} ready")
    assert len({record["run_request_id"] for record in rounds}) == 3
    assert len(panel.rounds()) == 3

    # -- an invalid draft is rejected locally and the next valid round works
    panel.set_draft_defaults(particle="proton", energy_text="banana", events=5)
    window.submit_session_round()
    wait_until(app, lambda: rejections or client.snapshot().get("last_rejection"),
               10.0, "local rejection")
    pump(app, 0.5)
    assert len(rounds) == 3, rounds
    panel.set_draft_defaults(particle="proton", energy_text="50 MeV", events=4)
    window.submit_session_round()
    wait_until(app, lambda: len(rounds) == 4, 180.0, "round after rejection")
    assert rounds[3]["status"] == "completed" and rounds[3]["completed_events"] == 4, rounds[3]
    wait_until(app, lambda: client.snapshot().get("phase") == "ready", 60.0, "ready after recovery")

    # -- busy rejection while a round runs, then a real cancel and a new round
    panel.set_draft_defaults(particle="proton", energy_text="50 MeV", events=20000)
    window.submit_session_round()
    wait_until(app, lambda: client.snapshot().get("phase") == "running", 120.0, "long round running")
    busy_before = len(rejections)
    panel.set_draft_defaults(particle="electron", energy_text="25 MeV", events=5)
    window.submit_session_round()
    wait_until(app, lambda: len(rejections) > busy_before, 30.0, "busy rejection")
    assert len(rounds) == 4, rounds
    assert panel.round_state_label.text() != ""
    window.cancel_session_round()
    wait_until(app, lambda: len(rounds) == 5, 180.0, "cancelled round record")
    cancelled = rounds[4]
    assert cancelled["status"] in {"cancelled", "aborted"}, cancelled
    assert cancelled["completed_events"] < cancelled["planned_events"], cancelled
    assert cancelled["receipt_ok"] is True, cancelled
    wait_until(app, lambda: client.snapshot().get("phase") == "ready", 60.0, "ready after cancel")
    # A cancelled round keeps its facts as history, but the next round must be
    # editable again once the phase is ready.
    assert panel.energy_edit.isEnabled() and panel.events_spin.isEnabled(), "inputs stay disabled after cancel"
    assert panel.submit_button.isEnabled()
    panel.energy_edit.setText("30 MeV")
    panel.events_spin.setValue(3)
    pump(app, 0.1)
    window.submit_session_round()
    wait_until(app, lambda: len(rounds) == 6, 120.0, "round after cancel")
    assert rounds[5]["status"] == "completed" and rounds[5]["completed_events"] == 3, rounds[5]
    wait_until(app, lambda: client.snapshot().get("phase") == "ready", 60.0, "ready after cancel round")

    # -- closing while a round runs must release the process owner, bounded
    panel.set_draft_defaults(particle="proton", energy_text="50 MeV", events=20000)
    window.submit_session_round()
    wait_until(app, lambda: client.snapshot().get("phase") == "running", 120.0, "round before close")
    window.close()
    wait_until(app, lambda: not window.runner.is_running(), 30.0, "session process ended")
    wait_until(app, lambda: not client.is_active(), 30.0, "session owner released")
    assert window.session_owns_process() is False

    for record in rounds:
        assert "receipt_path" in record and record["receipt_path"], record
        assert Path(record["receipt_path"]).exists(), record["receipt_path"]

    # -- a cleanly closed session is replayable from the panel entry; the replay
    #    runs in a new backend process and writes into a new output directory.
    replay_window = gui_test_window.MainWindow()
    replay_window._smoke_recovery_directory._finalizer.detach()
    replay_window.project_page.executable.setText(str(executable))
    replay_window.flush_pending_edit()
    replay_window.resize(1440, 900)
    replay_window.show()
    pump(app, 0.3)
    replay_panel = replay_window.session_panel
    replay_client = replay_window.session_client
    replay_rounds: list[dict] = []
    replay_client.roundFinished.connect(lambda record: replay_rounds.append(dict(record)))
    replay_failures: list[str] = []
    replay_client.failure.connect(lambda message: replay_failures.append(str(message)))

    def _emergency_stop_replay() -> None:
        try:
            if replay_window.session_owns_process():
                replay_window.session_client.kill()
        except Exception:  # noqa: BLE001 - best effort during interpreter teardown
            pass

    atexit.register(_emergency_stop_replay)
    replay_window.start_session()
    wait_until(app, lambda: replay_client.snapshot().get("phase") == "ready", 120.0,
               "replay source session ready")
    first_output = str(replay_client.snapshot()["session"]["output_root"])
    for expected, energy in ((1, "100 MeV"), (2, "200 MeV")):
        replay_panel.set_draft_defaults(particle="proton", energy_text=energy, events=5)
        replay_window.submit_session_round()
        wait_until(app, lambda e=expected: len(replay_rounds) == e, 180.0,
                   f"replay source round {energy}")
        wait_until(app, lambda: replay_client.snapshot().get("phase") == "ready", 60.0,
                   f"replay source ready after {energy}")
    assert len(replay_rounds) == 2, replay_rounds
    replay_window.close_session()
    wait_until(app, lambda: not replay_client.is_active(), 60.0, "source session closed")
    wait_until(app, lambda: replay_client.snapshot().get("phase") == "closed", 30.0,
               "source session phase closed")
    assert replay_panel.replay_button.isEnabled(), "the replay button must be enabled"
    replay_panel.replay_button.click()
    wait_until(app, lambda: len(replay_rounds) == 4, 300.0, "replayed rounds")
    replayed = replay_rounds[2:]
    assert all(record["status"] == "completed" for record in replayed), replayed
    assert [record["completed_events"] for record in replayed] == [5, 5], replayed
    assert all(record["receipt_ok"] for record in replayed), replayed
    command = list(replay_client.snapshot()["session"].get("command") or [])
    assert "--session-replay" in command, command
    replay_output = str(replay_client.snapshot()["session"]["output_root"])
    assert replay_output and replay_output != first_output, (first_output, replay_output)
    wait_until(app, lambda: not replay_client.is_active(), 60.0, "replay session closed")
    wait_until(app, lambda: replay_client.snapshot().get("phase") == "closed", 60.0,
               "replay terminal accepted")
    replay_snapshot = replay_client.snapshot()
    assert replay_snapshot.get("phase") == "closed", replay_snapshot
    assert replay_snapshot["session"].get("alive") is False, replay_snapshot
    assert not replay_failures, replay_failures
    replay_closing = dict(replay_snapshot.get("closing") or {})
    assert replay_closing.get("reason") == "replay_finished", replay_closing
    executed_runs = int(replay_closing.get("steps_executed") or 0)
    total_operations = int(replay_closing.get("steps_total") or 0)
    assert executed_runs == len(replayed), (executed_runs, replayed)
    assert total_operations >= executed_runs > 0, replay_closing
    replay_window.close()
    wait_until(app, lambda: not replay_window.runner.is_running(), 30.0, "replay process ended")
    print(f"session backend smoke passed: {len(rounds)} rounds, {len(rejections)} rejections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
