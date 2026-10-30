"""Qt lifecycle adapter for the shared project recovery payload.

The window owns capture/apply and dirty confirmation. This adapter never
mutates controls, starts a run or saves an original project path.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
import copy
from pathlib import Path
import time

from PySide6.QtCore import QObject, QTimer, Signal, Qt

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.workspace_recovery import RecoveryStore, payload_digest


class RecoveryController(QObject):
    statusChanged = Signal(str)
    _completed = Signal(object)

    def __init__(self, owner, *, restore, root: str | Path | None = None):
        super().__init__(owner)
        self.restore = restore
        self.store = None
        self.session = None
        self.status = ui_text("Recovery copy: no unsaved changes")
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="g4usim-recovery")
        self._future = None
        self._pending = None
        self._closed = False
        self._last_error = ""
        self._highest_revision = -1
        self._highest_payload_sha256 = None
        self._retired_revision = -1
        self.last_receipt = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(1500)
        self._debounce.timeout.connect(self._start_pending)
        self._maximum = QTimer(self)
        self._maximum.setSingleShot(True)
        self._maximum.setInterval(10000)
        self._maximum.timeout.connect(self._start_pending)
        self._completed.connect(self._finish_future, Qt.QueuedConnection)
        try:
            self.store = RecoveryStore(root)
            self.session = self.store.open_session()
        except (OSError, ValueError) as exc:
            self._failed(exc)

    def _set_status(self, text):
        self.status = text
        self.statusChanged.emit(text)

    def _failed(self, exc):
        self._last_error = str(exc)
        self._set_status(ui_format("Recovery copy update failed: {error}", error=str(exc)))

    def changed(self, payload: dict, revision: int, *, origin_path: str = "",
                origin_sha256: str | None = None, saved_digest: str | None = None):
        if self._closed:
            return
        if type(revision) is not int or revision < 0 or revision < self._highest_revision:
            raise ValueError("Recovery notification is older than the latest requested revision")
        if revision <= self._retired_revision:
            raise ValueError("Recovery notification belongs to a retired revision")
        detached = copy.deepcopy(payload)
        fingerprint = payload_digest(detached)
        if revision == self._highest_revision:
            if fingerprint != self._highest_payload_sha256:
                raise ValueError("One recovery revision cannot describe different payloads")
            if self._pending is not None or self._future is not None or not self._last_error:
                return  # Identical duplicate; retain the earlier immutable request.
        self._highest_revision = revision
        self._highest_payload_sha256 = fingerprint
        self._pending = (detached, revision,
                         dict(origin_path=origin_path, origin_sha256=origin_sha256, saved_digest=saved_digest))
        self._debounce.start()
        if not self._maximum.isActive():
            self._maximum.start()
        self._set_status(ui_text("Recovery copy: changes waiting to be protected"))

    def _stop_timers(self):
        self._debounce.stop()
        self._maximum.stop()

    def _start_pending(self):
        if self._closed or self._pending is None or self._future is not None:
            return
        self._stop_timers()
        if self.session is None:
            self._failed(self._last_error or "Recovery storage is unavailable")
            return
        payload, revision, options = self._pending
        self._pending = None
        self._set_status(ui_text("Updating recovery copy…"))
        self._future = self._pool.submit(self.session.publish, payload, revision, **options)
        future = self._future

        def done(completed):
            try:
                self._completed.emit(completed)
            except RuntimeError:
                pass  # Owner gone; a completed write remains valid on disk.
        future.add_done_callback(done)

    def _finish_future(self, future):
        if future is not self._future or not future.done():
            return
        self._future = None
        try:
            self.last_receipt = future.result()
            self._last_error = ""
            if self._pending is not None:
                self._set_status(ui_format(
                    "Recovery copy updated: {time}; newer changes are still waiting to be protected.",
                    time=self.last_receipt.updated_utc))
            elif self.last_receipt.cleanup_warning:
                self._set_status(ui_format("Recovery copy updated with cleanup warning: {error}",
                                           error=self.last_receipt.cleanup_warning))
            else:
                self._set_status(ui_format("Recovery copy updated: {time}", time=self.last_receipt.updated_utc))
        except Exception as exc:
            self._failed(exc)
        if self._pending is not None and not self._debounce.isActive():
            self._start_pending()

    def flush(self, timeout_ms: int = 5000) -> bool:
        deadline = time.monotonic() + timeout_ms / 1000
        self._stop_timers()
        while self._pending is not None or self._future is not None:
            self._start_pending()
            future = self._future
            if future is None:
                return False
            try:
                future.result(timeout=max(0.0, deadline - time.monotonic()))
            except TimeoutError:
                self._failed(ui_text("Still waiting for the recovery write to finish."))
                return False
            except Exception:
                pass  # GUI status is published in the one completion path below.
            self._finish_future(future)
            if time.monotonic() > deadline and (self._future is not None or self._pending is not None):
                self._failed(ui_text("Still waiting for the recovery write to finish."))
                return False
        return not self._last_error

    def _retire(self, reason: str, timeout_ms: int = 5000) -> bool:
        if self._closed:
            return False
        self._stop_timers()
        # The caller has saved or explicitly discarded this exact current state.
        # Queued old edits must not recreate a copy after retirement.
        self._pending = None
        self._retired_revision = max(self._retired_revision, self._highest_revision)
        if not self.flush(timeout_ms):
            # A failed completed autosave must not prevent successful manual
            # saving/discarding; an in-flight write, however, must settle.
            if self._future is not None:
                return False
        if self.session is None:
            self._last_error = ""
            return True
        try:
            receipt = self.session.retire(reason)
        except (OSError, ValueError) as exc:
            self._failed(exc)
            return False
        self.last_receipt = None
        self._last_error = ""
        if receipt is not None and receipt.cleanup_warning:
            self._set_status(ui_format("Recovery copy cleanup warning: {error}", error=receipt.cleanup_warning))
        else:
            self._set_status(ui_text("Recovery copy: no unsaved changes"))
        return True

    def saved(self, timeout_ms: int = 5000) -> bool:
        return self._retire("saved", timeout_ms)

    def discard(self, timeout_ms: int = 5000) -> bool:
        return self._retire("discarded", timeout_ms)

    def reset(self) -> bool:
        if self._closed:
            return False
        if not self.flush():
            return False
        if self.session is not None:
            try:
                self.session.retain()  # Never silently lose a caller's unresolved draft.
            except (OSError, ValueError) as exc:
                self._failed(exc)
                return False
            self.session.close()
        if self.store is None:
            return False
        try:
            self.session = self.store.open_session()
            self.last_receipt = None
            self._highest_revision = -1
            self._highest_payload_sha256 = None
            self._retired_revision = -1
            return True
        except (OSError, ValueError) as exc:
            self.session = None
            self._failed(exc)
            return False

    def restore_candidate(self, candidate) -> bool:
        if self.store is None:
            return False
        with self.store.claim(candidate) as claim:
            record = claim.read()
            if not self.restore(copy.deepcopy(record.payload)):
                return False
            # The window callback resets its edit session and calls changed()
            # with its complete restored state. If persistence fails, leave
            # the original recovery candidate intact for another attempt.
            if self._pending is not None and self.flush():
                claim.discard()
                self._set_status(ui_text("Recovered as an unsaved copy. Validate and generate again before running."))
            else:
                self._set_status(ui_format(
                    "Editing state was restored, but its new recovery copy is not protected yet. The previous copy is kept. {error}",
                    error=self._last_error))
            return True

    def show_recovery_dialog(self):
        if self.store is None:
            self._failed(self._last_error or "Recovery storage is unavailable")
            return None
        from g4usim_gui.widgets.recovery_dialog import RecoveryDialog
        dialog = RecoveryDialog(self.store, self.restore_candidate, self.parent())
        dialog.exec()
        return dialog

    def offer_at_startup(self):
        if self.store is not None and self.store.discover():
            self.show_recovery_dialog()

    def close(self, *, keep: bool = False, timeout_ms: int = 5000) -> bool:
        if self._closed:
            return True
        if self.session is None and self._pending is None and self._future is None:
            self._closed = True
            self._pool.shutdown(wait=False)
            return True
        if not self.flush(timeout_ms):
            return False
        if self.session is not None:
            try:
                # An orderly close leaving a recovery copy is distinguishable
                # from a process killed while its live record was active.
                self.session.retain()
            except (OSError, ValueError) as exc:
                self._failed(exc)
                return False
            self.session.close()
        self._closed = True
        self._pool.shutdown(wait=False)
        return True


class RecoveryMixin:
    """MainWindow hooks; all editor mutations use its transaction interface."""

    def _setup_recovery(self):
        from PySide6.QtWidgets import QLabel
        self._recovery_origin_path = ""
        self._recovery_origin_sha256 = None
        self._recovery_last_revision = None
        self._recovery = RecoveryController(
            self, restore=self._restore_recovery_payload, root=getattr(self, "_recovery_root", None))
        self.recovery_status = QLabel(self._recovery.status)
        self.recovery_status.setWordWrap(True)
        self.recovery_status.setMaximumWidth(480)
        self._recovery.statusChanged.connect(self.recovery_status.setText)
        self._recovery.statusChanged.connect(self.recovery_status.setToolTip)
        self.statusBar().addPermanentWidget(self.recovery_status)
        self.recovery_action = self.edit_menu.addAction(ui_text("Recover editing copies…"))
        self.recovery_action.triggered.connect(self._recovery.show_recovery_dialog)
        if getattr(self, "_offer_recovery", True):
            QTimer.singleShot(0, self._recovery.offer_at_startup)

    def _recovery_history_changed(self):
        if not hasattr(self, "_recovery") or self._recovery._closed:
            return
        self.recovery_action.setText(ui_text("Recover editing copies…"))
        session = self._edit_session
        if not session.is_modified:
            self._recovery.saved()
            self._recovery_last_revision = None
            return
        if self._recovery_last_revision == session.revision:
            # closeEvent may have stopped all QTimers before an owned process
            # refuses to close. Re-arm pending protection in that case.
            if self._recovery._pending is not None and not self._recovery._debounce.isActive():
                self._recovery._debounce.start()
                self._recovery._maximum.start()
            return
        from g4usim_gui.core.edit_snapshot import project_for_snapshot
        from g4usim_gui.core.project import project_to_dict
        payload = project_to_dict(project_for_snapshot(session.current()))
        self._recovery.changed(payload, session.revision,
                               origin_path=self._recovery_origin_path,
                               origin_sha256=self._recovery_origin_sha256,
                               saved_digest=session.saved_fingerprint)
        self._recovery_last_revision = session.revision

    def _recovery_project_replaced(self, *, origin_path=None, origin_sha256=None):
        if not hasattr(self, "_recovery"):
            return True
        if not self._recovery.discard() or not self._recovery.reset():
            return False
        self._recovery_origin_path = str(origin_path if origin_path is not None else self.project_file or "")
        self._recovery_origin_sha256 = origin_sha256
        self._recovery_last_revision = None
        self._recovery_history_changed()
        return True

    def _recovery_project_saved(self, *, origin_path=None, origin_sha256=None):
        if not hasattr(self, "_recovery"):
            return True
        # A caller may provide the actual successful save receipt. Do not
        # re-read here and present later bytes as what the save wrote.
        if origin_path is not None:
            self._recovery_origin_path = str(origin_path)
            self._recovery_origin_sha256 = origin_sha256
        self._recovery_last_revision = None
        if self._edit_session.is_modified:
            self._recovery_history_changed()
            return True
        return self._recovery.saved()

    def _restore_recovery_payload(self, payload):
        from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
        from g4usim_gui.core.project import project_from_dict
        if not self.can_mutate_workspace("recover"):
            return False
        snapshot = WorkspaceSnapshot(project_from_dict(payload))
        self._check_workspace_projection(snapshot)
        if not self._confirm_unsaved_edits():
            return False
        self._edit_session.reset(snapshot, saved=False,
                                 apply=lambda value: self.apply_workspace(value, reason="recovery"))
        self.project_file = None
        self._history_discard_on_close = False
        self._recovery_origin_path = ""
        self._recovery_origin_sha256 = None
        # The new project is already atomically published in memory. A disk
        # failure preserves the predecessor recovery candidate in the caller.
        if self._recovery.discard():
            self._recovery.reset()
        self._recovery_last_revision = None
        self.history_changed()
        return True

    def _recovery_before_close(self, *, discard=False):
        if not hasattr(self, "_recovery"):
            return True
        if discard and not self._recovery.discard():
            return False
        if not self._edit_session.is_modified and not self._recovery.saved():
            return False
        return self._recovery.close(keep=self._edit_session.is_modified and not discard)
