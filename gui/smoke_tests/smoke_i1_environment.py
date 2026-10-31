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
from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool, QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit
from PySide6.QtGui import QFontDatabase, QFontMetrics, QTextOption
from PySide6.QtTest import QTest
from g4usim_gui.core.i18n import ZH_CN, current_language, set_application_language
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


def ensure_test_fonts(app):
    # Qt's Windows offscreen plugin can expose an empty font database. Load the
    # installed fonts used by the real theme; tofu boxes are not layout evidence.
    metrics = QFontMetrics(app.font())
    if os.name == "nt" and (not metrics.inFont("A") or not metrics.inFont("中")):
        font_root = Path(os.environ["WINDIR"]) / "Fonts"
        for name in ("segoeui.ttf", "msyh.ttc"):
            assert QFontDatabase.addApplicationFont(str(font_root / name)) >= 0
    assert QFontMetrics(app.font()).inFont("A")
    assert QFontMetrics(app.font()).inFont("中")


def check_summary_layout(app):
    previous_language = current_language()
    dialog = module.EnvironmentDialog(candidates=[], auto_discover=False)
    long_path = "C:/中文工作区/" + "very-long-directory-name/" * 10 + "G4UniversalSim.exe"
    facts = fixture()
    facts["environments"][0]["executable"] = long_path
    facts["environments"][0]["data"] = {
        "status": "incomplete", "required_complete": False,
        "report": {"datasets": [
            {"env": "G4LEDATA", "folder": "G4EMLOW8.6.1", "required": True, "found": False},
            {"env": "G4OPTIONAL", "folder": "optional-not-required", "required": False, "found": False},
        ]},
    }
    original_facts = json.loads(json.dumps(facts))
    try:
        dialog._completed(dialog._generation, facts)
        dialog.show()
        app.processEvents()
        assert dialog.summary.isVisible()
        assert QFontMetrics(dialog.summary.font()).inFont("中")
        assert dialog.summary.isReadOnly()
        assert isinstance(dialog.details, QPlainTextEdit)
        assert not dialog.details.isVisible()
        assert not dialog.details_toggle.isChecked()
        assert dialog.summary.lineWrapMode() == QPlainTextEdit.WidgetWidth
        assert dialog.summary.wordWrapMode() == QTextOption.WrapAtWordBoundaryOrAnywhere
        assert dialog.table.item(0, 3).text() == "11.3.2"
        assert not dialog.summary.toPlainText().lstrip().startswith("{")
        assert json.loads(dialog.details.toPlainText())["environment"]["build"]["geant4_version_number"] == 1132
        for language in ("zh_CN", "en", "zh_CN"):
            set_application_language(app, language)
            dialog.retranslate_ui()
            text = dialog.summary.toPlainText()
            assert long_path in text
            assert "11.3.2" in text
            assert module.ui_text(module.STATUS_TEXT["data_incomplete"]) in text
            assert module.ui_text("Required data is missing") in text
            assert "G4EMLOW8.6.1" in text
            assert "optional-not-required" not in text
            assert module.ui_text("Selection only chooses a backend path; it does not start or validate a simulation.") in text
            if language == "zh_CN":
                # These are real centralized translations, never a test dictionary.
                for source in ("Backend executable", "Discovery status", module.STATUS_TEXT["data_incomplete"]):
                    assert source in ZH_CN
                    assert module.ui_text(source) != source
                    assert any("\u4e00" <= ch <= "\u9fff" for ch in module.ui_text(source))
                assert "后端程序" in text
                assert "缺少必需数据" in text
            for width in (960, 480, 640, 480):
                dialog.resize(width, 640)
                app.processEvents()
                assert dialog.width() == width
                for button in dialog._buttons:
                    assert button.width() >= button.sizeHint().width()
                    assert button.isVisible()
                assert dialog.summary.isVisible() and not dialog.details.isVisible()
                assert dialog.table.columnWidth(0) > dialog.table.columnWidth(4)
                assert dialog.table.columnWidth(1) > dialog.table.columnWidth(4)
                status_width = dialog.table.fontMetrics().horizontalAdvance(dialog.table.item(0, 1).text())
                assert dialog.table.columnWidth(1) >= status_width + 16
                for column in range(5):
                    assert dialog.table.item(0, column).toolTip() == dialog.table.item(0, column).text()
                assert dialog.table.item(0, 0).toolTip() == long_path
                assert dialog.summary.horizontalScrollBar().maximum() == 0
                block = dialog.summary.document().firstBlock()
                assert block.layout().lineCount() > 1  # Whole path wraps, not elides.
                for index in range(block.layout().lineCount()):
                    assert block.layout().lineAt(index).naturalTextWidth() <= dialog.summary.viewport().width()
                if width == 480:
                    assert dialog.table.horizontalScrollBar().maximum() > 0
                    dialog.table.horizontalScrollBar().setValue(dialog.table.horizontalScrollBar().maximum())
                    assert dialog.table.visualItemRect(dialog.table.item(0, 4)).intersects(dialog.table.viewport().rect())
                dialog.table.horizontalScrollBar().setValue(0)
                dialog.summary.setFocus()
                QTest.keyClick(dialog.summary, Qt.Key_A, Qt.ControlModifier)
                assert dialog.summary.textCursor().selectedText().replace("\u2029", "\n") == text
        assert dialog.current_environment()["data"]["required_complete"] is False
        dialog.details_toggle.click()
        app.processEvents()
        assert dialog.details.isVisible()
        assert json.loads(dialog.details.toPlainText())["environment"]["executable"] == long_path
        dialog.details_toggle.click()
        assert not dialog.details.isVisible()
        assert facts == original_facts  # Rendering never repairs or reclassifies facts.
        dialog.table.selectRow(1)
        assert long_path not in dialog.summary.toPlainText()
        assert module.ui_text("Unknown") in dialog.summary.toPlainText()
        assert module.ui_text("Data availability is unknown") in dialog.summary.toPlainText()
        assert not dialog.select_button.isEnabled()
        dialog.table.selectRow(0)
        assert dialog.select_button.isEnabled()  # Missing data still permits path selection.
        for status in ("partial", "ready", "future-status"):
            observation = fixture(status)
            dialog._completed(dialog._generation, observation)
            assert module.ui_text("Data availability is unknown") in dialog.summary.toPlainText()
            assert dialog.current_environment()["status"] == status
            assert dialog.select_button.isEnabled()
        complete = fixture("ready")
        complete["environments"][0]["data"] = {"required_complete": True, "report": {"datasets": []}}
        dialog._completed(dialog._generation, complete)
        assert module.ui_text("Required data directories found") in dialog.summary.toPlainText()
        assert dialog.current_environment()["data"]["required_complete"] is True
        dialog._completed(dialog._generation, {"environments": [], "host": {}, "sdk": []})
        assert long_path not in dialog.summary.toPlainText()
        assert not dialog.select_button.isEnabled()
        assert '"host"' in dialog.details.toPlainText()
        assert module.ui_text("Select a backend to view its summary.") in dialog.summary.toPlainText()
    finally:
        dialog.close()
        dialog.deleteLater()
        set_application_language(app, previous_language)


def main():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    apply_theme(app, "light")
    ensure_test_fonts(app)
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

    check_summary_layout(app)

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
