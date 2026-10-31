"""Offscreen I1 dialog lifecycle, event-loop and selection regression."""
from __future__ import annotations

import os
import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication, QDialog
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.core import environment_discovery as discovery
from g4usim_gui.core.backend_capabilities import CAPABILITY_GROUPS
from g4usim_gui.widgets import environment_dialog as module


def wait_until(app, condition, seconds=8):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert condition(), "Timed out waiting for asynchronous GUI state"


def fixture(status="data_incomplete"):
    return {"schema": "g4usim_environment_discovery_v1", "host": {"tools": {}}, "sdk": [],
            "environments": [{"executable": "/中文 backend.exe", "status": status,
                "architecture": {"machine": "x86_64"},
                "capabilities": {"status": "available"}, "identity": {"stable": True},
                "build": {"compiler_id": "Fixture", "compiler_version": "1", "geant4_version_number": 1132}},
                {"executable": "/missing backend.exe", "status": "not_found",
                 "capabilities": {"status": "not_probed"}}]}


def main():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    apply_theme(app, "light")
    app.setQuitOnLastWindowClosed(False)
    app.setProperty("languageCode", "en")
    main_thread = threading.get_ident()
    called_threads = []
    started, release = threading.Event(), threading.Event()
    ticks = []
    heartbeat = QTimer()
    heartbeat.setInterval(5)
    heartbeat.timeout.connect(lambda: ticks.append(1))
    heartbeat.start()

    def slow_discovery(candidates, **options):
        called_threads.append(threading.get_ident())
        started.set()
        if not release.wait(5):
            raise TimeoutError("test release was not signalled")
        return fixture()

    with patch.object(module, "discover_environments", side_effect=slow_discovery):
        dialog = module.EnvironmentDialog(candidates=[])
        choices = []
        dialog.environment_selected.connect(choices.append)
        start = time.monotonic()
        dialog.show()
        wait_until(app, started.is_set)
        assert time.monotonic() - start < 2
        wait_until(app, lambda: len(ticks) >= 3)
        assert dialog.busy and not dialog.select_button.isEnabled()
        assert not dialog.refresh_button.isEnabled()
        dialog.refresh()  # Busy refresh cannot queue a duplicate probe.
        assert len(called_threads) == 1
        assert called_threads[0] != main_thread
        release.set()
        wait_until(app, lambda: not dialog.busy)
        assert dialog.table.rowCount() == 2
        assert dialog.select_button.isEnabled()
        assert "required data is missing" in dialog.table.item(0, 1).text()
        assert dialog.selected_environment() is None
        assert dialog.selected_executable() is None
        dialog.table.selectRow(1)
        assert not dialog.select_button.isEnabled()
        dialog.choose_selected()
        assert choices == []
        dialog.table.selectRow(0)
        assert dialog.select_button.isEnabled()
        dialog.choose_selected()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert len(choices) == 1
        assert dialog.selected_executable() == "/中文 backend.exe"
        returned = dialog.selected_environment()
        returned["executable"] = "mutated"
        assert dialog.selected_executable() == "/中文 backend.exe"
        assert choices[0]["status"] == "data_incomplete"

    # Closing/deleting the dialog while work is running neither blocks nor lets
    # an old queued receipt overwrite a subsequent dialog's state.
    started.clear()
    release.clear()
    with patch.object(module, "discover_environments", side_effect=slow_discovery):
        closing = module.EnvironmentDialog(candidates=[])
        closing.show()
        wait_until(app, started.is_set)
        generation = closing._generation
        start = time.monotonic()
        closing.close()
        assert time.monotonic() - start < 0.5
        assert not closing.isVisible()
        closing._completed(generation, fixture("ready"))
        assert closing.facts is None
        closing.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        release.set()
        wait_until(app, lambda: QThreadPool.globalInstance().activeThreadCount() == 0)
        app.processEvents()

    def fail(*args, **kwargs):
        raise OSError("fixture dependency failure")
    with patch.object(module, "discover_environments", side_effect=fail):
        failed = module.EnvironmentDialog(candidates=[])
        failed.show()
        wait_until(app, lambda: "fixture dependency failure" in failed.status.text())
        assert not failed.busy
        assert failed.refresh_button.isEnabled()
        assert not failed.select_button.isEnabled()
        failed.close()

    empty_facts = {"schema": "g4usim_environment_discovery_v1", "environments": [], "host": {}, "sdk": []}
    with patch.object(module, "discover_environments", return_value=empty_facts):
        empty = module.EnvironmentDialog(candidates=[])
        empty.show()
        wait_until(app, lambda: empty.facts is not None)
        assert empty.table.rowCount() == 0
        assert not empty.select_button.isEnabled()
        assert '"host"' in empty.details.toPlainText()
        empty.close()

    # Refresh makes all prior rows/receipts unusable until the new worker finishes.
    with patch.object(module, "discover_environments", return_value=fixture("ready")):
        refresh = module.EnvironmentDialog(candidates=[], auto_discover=False)
        refresh.show()
        refresh.refresh()
        wait_until(app, lambda: refresh.facts is not None)
        generation = refresh._generation
        refresh.refresh()
        assert refresh.facts is None and not refresh.select_button.isEnabled()
        refresh._completed(generation, fixture("not_found"))
        assert refresh.facts is None
        wait_until(app, lambda: refresh.facts is not None)
        assert refresh.facts["environments"][0]["status"] == "ready"
        refresh.close()

    # Real parser/probe + Qt widgets: malformed data never claims completeness.
    # Capability-only path selection remains permitted with explicit partial state.
    capability = {"schema": "G4UniversalSimCapabilities", "version": 1,
                  **{group: [] for group in CAPABILITY_GROUPS}}
    overflow = ('{"schema":"g4usim_geant4_data_v1","required_complete":true,'
                '"datasets":[{"env":"G4XDATA","folder":"X1","required":true,'
                '"found":true,"path":"/fixture","extra":{"nested":[1e999]}}]}')
    def overflow_response(argv, **kwargs):
        return {"status": "completed", "exit_code": 0}, (
            json.dumps(capability) if argv[-1] == "--capabilities" else overflow)
    with patch.object(discovery, "_command", side_effect=overflow_response):
        partial_facts = discovery.probe_environment(sys.executable)
    assert partial_facts["status"] == "partial"
    assert partial_facts["data"]["status"] == "protocol_error"
    assert partial_facts["data"]["required_complete"] is None
    assert json.loads(json.dumps(partial_facts, allow_nan=False)) == partial_facts
    partial_dialog = module.EnvironmentDialog(candidates=[], auto_discover=False)
    partial_dialog._completed(partial_dialog._generation, {
        "environments": [partial_facts], "host": {}, "sdk": []})
    assert partial_dialog.table.item(0, 1).text() == module.ui_text(module.STATUS_TEXT["partial"])
    assert "Infinity" not in partial_dialog.details.toPlainText()
    assert partial_dialog.select_button.isEnabled()
    partial_dialog.choose_selected()
    assert partial_dialog.selected_environment()["status"] == "partial"

    executable = None if '--component' in sys.argv else os.environ.get("G4USIM_EXE")
    if executable:
        real = module.EnvironmentDialog(candidates=[executable], timeout=5)
        real.show()
        wait_until(app, lambda: real.facts is not None, seconds=40)
        assert real.facts["environments"][0]["capabilities"]["status"] == "available", real.details.toPlainText()
        assert real.select_button.isEnabled()
        screenshot = os.environ.get("G4USIM_I1_SCREENSHOT")
        if screenshot:
            app.processEvents()
            assert real.grab().save(screenshot), screenshot
        real.choose_selected()
        assert Path(real.selected_executable()).resolve() == Path(executable).resolve()
    heartbeat.stop()
    wait_until(app, lambda: QThreadPool.globalInstance().activeThreadCount() == 0)
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    print("PASS I1 GUI: worker/event loop, selection, empty/failure, close/delete, stale receipts; real backend:", bool(executable))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
