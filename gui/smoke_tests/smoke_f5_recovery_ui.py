"""Actual Qt recovery controls, asynchronous writes and cancellation boundaries."""
from __future__ import annotations

import copy
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
from g4usim_gui.core.project import G4USimProject, project_to_dict
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, project_for_snapshot
from g4usim_gui.editors.material_editor_model import MaterialDocument
from g4usim_gui.core.workspace_recovery import RecoveryStore
from g4usim_gui.window.recovery import RecoveryController
from g4usim_gui.widgets.recovery_dialog import RecoveryDialog


def payload(name="Unsaved recovery draft"):
    project = G4USimProject(projectName=name, materialEditor=MaterialDocument())
    return project_to_dict(project_for_snapshot(WorkspaceSnapshot(project)))


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "Qt recovery condition did not complete"


def cleanup_controller(controller):
    try:
        if not controller._closed:
            controller.discard()
            controller.close()
    finally:
        controller._pool.shutdown(wait=True)
        if controller.session is not None:
            controller.session.close()


def rejected(action, message):
    try:
        action()
    except ValueError as exc:
        assert message in str(exc), str(exc)
    else:
        assert False, "Recovery accepted a stale or conflicting notification"


def main():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    set_application_language(app, "en")
    with tempfile.TemporaryDirectory(prefix="f5-recovery-ui-") as temporary, ExitStack() as cleanup:
        work = Path(temporary)
        owner = QWidget()
        controller = RecoveryController(owner, restore=lambda _: False, root=work / "own")
        cleanup.callback(cleanup_controller, controller)
        controller._debounce.setInterval(25)
        controller._maximum.setInterval(80)
        assert controller.store.discover() == ()
        controller.changed(payload(), 1)
        wait_until(lambda: controller.last_receipt is not None)
        assert controller.last_receipt.revision == 1
        assert controller.session.path.is_file()
        assert not controller.store.discover(), "Another window could recover this active controller"
        for revision in range(2, 22):
            controller.changed(payload(f"rapid {revision}"), revision)
            QTest.qWait(15)  # Continuous input cannot starve the maximum timer.
        assert controller.last_receipt.revision > 1
        assert controller.flush()
        assert controller.last_receipt.revision == 21
        assert controller.saved()
        assert not controller.session.path.exists()

        # A write that has not finished cannot race a retire or close action.
        entered, release = threading.Event(), threading.Event()
        publish = controller.session.publish
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(5)
            return publish(*args, **kwargs)
        with patch.object(controller.session, "publish", delayed):
            controller.changed(payload("pending"), 22)
            controller._start_pending()
            assert entered.wait(2)
            assert not controller.flush(1)
            assert not controller.saved(1)
            assert controller._future is not None
            controller._debounce.setInterval(5000)
            controller._maximum.setInterval(5000)
            controller.changed(payload("newer unprotected edits"), 23)
            rejected(lambda: controller.changed(payload("late older notification"), 22), "older")
            rejected(lambda: controller.changed(payload("same revision conflicting payload"), 23), "different payloads")
            assert controller._pending[1] == 23
            assert controller._pending[0]["projectName"] == "newer unprotected edits"
            release.set()
            wait_until(lambda: controller._future is None)
            assert controller.last_receipt.revision == 22
            assert controller._pending is not None
            assert "newer changes" in controller.status
            assert controller.flush()
            assert controller.last_receipt.revision == 23
        assert controller.saved()
        rejected(lambda: controller.changed(payload("newer unprotected edits"), 23), "retired")
        assert controller._pending is None and not controller.session.path.exists()
        controller.changed(payload("next document"), 24)
        assert controller.flush()
        old_path = controller.session.path
        assert controller.reset()
        assert old_path.is_file(), "Unresolved document was silently deleted by reset"
        candidate = controller.store.discover()[0]
        assert candidate.disposition == "retained"

        # Showing a dialog only reads; keep/cancel does not rewrite its bytes.
        old_bytes = old_path.read_bytes()
        dialog = RecoveryDialog(controller.store, lambda _: False, owner)
        assert dialog.table.rowCount() == 1 and dialog.restore_button.isEnabled()
        assert dialog.later_button.isDefault()
        assert not dialog.restore_selected()
        dialog.reject()
        assert old_path.read_bytes() == old_bytes
        called = []
        with patch.object(controller, "show_recovery_dialog", side_effect=lambda: called.append(True)):
            controller.offer_at_startup()
        assert called == [True], "Default discovery was disabled because Qt is offscreen"

        # Actual restore callback receives the complete codec payload. UI owns
        # replacement confirmation, projection and the new untitled edit state.
        restored = []
        def restore(project):
            restored.append(copy.deepcopy(project))
            assert controller.discard()
            assert controller.reset()
            controller.changed(project, 0)
            return True
        controller.restore = restore
        assert controller.restore_candidate(candidate)
        assert restored[-1] == payload("next document")
        assert not old_path.exists()
        assert controller.last_receipt is not None and controller.last_receipt.revision == 0
        assert controller.close(keep=True)
        assert controller.store.discover()[0].disposition == "retained"
        owner.close()

        # A restore succeeded in memory but successor publication failed:
        # preserve the predecessor and leave an explicit protection warning.
        other_owner = QWidget()
        other = RecoveryController(other_owner, restore=lambda _: False, root=work / "own")
        cleanup.callback(cleanup_controller, other)
        old_candidate = other.store.discover()[0]
        before = old_candidate.path.read_bytes()
        restored.clear()
        def restore_failed_write(project):
            restored.append(project)
            other.changed(project, 0)
            return True
        other.restore = restore_failed_write
        with patch.object(other.session, "publish", side_effect=OSError("injected disk failure")):
            assert other.restore_candidate(old_candidate)
        assert restored
        assert old_candidate.path.read_bytes() == before
        assert "injected disk failure" in other.status
        assert "kept" in other.status
        assert other.discard()
        assert other.close()

        # Invalid files remain listed with recovery disabled. Discard is an
        # explicit decision that does not affect the source/original project.
        store = RecoveryStore(work / "invalid")
        session = store.open_session()
        session.publish(payload(), 0)
        session.close()
        session.path.write_bytes(b"{broken")
        invalid_before = session.path.read_bytes()
        bad = RecoveryDialog(store, lambda _: False, other_owner)
        assert bad.table.rowCount() == 1
        assert not bad.restore_button.isEnabled() and bad.discard_button.isEnabled()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            assert not bad.discard_selected()
        assert session.path.read_bytes() == invalid_before
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            assert bad.discard_selected()
        assert not session.path.exists() and bad.table.rowCount() == 0
        bad.close()

        # Original project observation is separate from referenced source
        # validation, and never overwrites its recorded identity or bytes.
        origin = work / "original-project.json"
        origin.write_bytes(b"original project snapshot")
        observed = hashlib.sha256(origin.read_bytes()).hexdigest()
        origin_store = RecoveryStore(work / "origin")
        origin_session = origin_store.open_session()
        origin_session.publish(payload(), 0, origin_path=str(origin), origin_sha256=observed)
        origin_session.close()
        origin_dialog = RecoveryDialog(origin_store, lambda _: False, other_owner)
        assert "matches its recorded byte identity" in origin_dialog.status.text()
        origin.write_bytes(b"changed by another editor")
        origin_dialog.refresh()
        assert "changed after its recorded identity" in origin_dialog.status.text()
        assert origin.read_bytes() == b"changed by another editor"
        origin.unlink()
        origin_dialog.refresh()
        assert "original project file is missing" in origin_dialog.status.text()
        with origin_store.claim(origin_store.discover()[0]) as claim:
            assert claim.read().origin_sha256 == observed
            claim.discard()
        origin_dialog.close()
        other_owner.close()
        app.processEvents()
    print("F5 Qt recovery controls, writer ordering and explicit recovery: passed")


if __name__ == "__main__":
    main()
