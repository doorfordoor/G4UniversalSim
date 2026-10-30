"""Explicit F5 lifecycle policy for older, unrelated window smoke tests.

These tests exercise their original feature and choose Discard when replacing
their synthetic project or closing it. Production MainWindow still asks the
user; dedicated F5 tests exercise all Save/Discard/Cancel choices. Each test
window owns a separate recovery directory and never scans a user's drafts.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtWidgets import QMessageBox
from g4usim_gui.main_window import MainWindow as ProductMainWindow
from g4usim_gui.history import run_history_store


# Preserve a test's explicit state file; otherwise isolate the legacy default.
_app_state_directory = tempfile.TemporaryDirectory(prefix="g4usim-smoke-state-")
if run_history_store.STATE_PATH == Path.home() / ".g4universalsim_gui_state.json":
    run_history_store.STATE_PATH = Path(_app_state_directory.name) / "state.json"


class MainWindow(ProductMainWindow):
    def __init__(self, *args, **kwargs):
        directory = tempfile.TemporaryDirectory(prefix="g4usim-smoke-recovery-")
        kwargs.setdefault("recovery_root", directory.name)
        kwargs.setdefault("offer_recovery", False)
        super().__init__(*args, **kwargs)
        self._smoke_recovery_directory = directory

    def _choose_unsaved_action(self):
        return QMessageBox.Discard
