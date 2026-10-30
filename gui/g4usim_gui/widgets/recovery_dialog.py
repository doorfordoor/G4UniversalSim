"""Explicit recovery selection; merely showing this dialog changes no files."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.workspace_recovery import origin_status


class RecoveryDialog(QDialog):
    def __init__(self, store, restore, parent=None):
        super().__init__(parent)
        self.store, self.restore = store, restore
        self.candidates = ()
        self.setWindowTitle(ui_text("Recover editing copies"))
        self.resize(900, 470)
        layout = QVBoxLayout(self)
        self.boundary = QLabel(ui_text(
            "Recovery opens an unsaved copy. It does not overwrite the original project or run a simulation."))
        self.boundary.setWordWrap(True)
        layout.addWidget(self.boundary)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([ui_text(key) for key in
                                             ("Project", "Last recovery update", "Recovery state", "Original project")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.table)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.refresh_button = QPushButton(ui_text("Refresh recovery list"))
        self.restore_button = QPushButton(ui_text("Restore copy"))
        self.discard_button = QPushButton(ui_text("Discard copy"))
        self.later_button = QPushButton(ui_text("Keep for later"))
        self.later_button.setDefault(True)
        self.refresh_button.clicked.connect(self.refresh)
        self.restore_button.clicked.connect(self.restore_selected)
        self.discard_button.clicked.connect(self.discard_selected)
        self.later_button.clicked.connect(self.reject)
        for button in (self.refresh_button, self.restore_button, self.discard_button, self.later_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.refresh()
        self.later_button.setFocus()

    def refresh(self):
        try:
            self.candidates = self.store.discover()
        except (OSError, ValueError) as exc:
            self.status.setText(ui_format("Recovery list could not be read: {error}", error=str(exc)))
            self.candidates = ()
        self.table.setRowCount(len(self.candidates))
        for row, candidate in enumerate(self.candidates):
            state = (ui_text("Cannot restore this copy") if candidate.error else
                     ui_text("Kept for later") if candidate.disposition == "retained" else
                     ui_text("Session did not finish normally"))
            values = (candidate.project_name or ui_text("untitled"), candidate.updated_utc,
                      state, candidate.origin_path or ui_text("Unsaved project"))
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(str(candidate.path))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        if self.candidates:
            self.table.selectRow(0)
        else:
            self.status.setText(ui_text("No inactive recovery copies were found. Active windows keep their own copies locked."))
        self._selection_changed()

    def selected(self):
        row = self.table.currentRow()
        return self.candidates[row] if 0 <= row < len(self.candidates) else None

    def _selection_changed(self):
        candidate = self.selected()
        self.restore_button.setEnabled(candidate is not None and not candidate.error)
        self.discard_button.setEnabled(candidate is not None and bool(candidate.raw_sha256))
        if candidate is not None:
            text = candidate.error or ui_format("Recovery copy: {path}", path=candidate.path)
            if not candidate.error:
                try:
                    with self.store.claim(candidate) as claim:
                        observed = origin_status(claim.read())
                    keys = {
                        "unsaved": "This draft has no original project file.",
                        "unobserved": "The original project identity was not observed; equality is unverified.",
                        "missing": "The original project file is missing. The editing copy can still be recovered.",
                        "unavailable": "The original project file could not be checked. Equality is unverified.",
                        "changed": "The original project file changed after its recorded identity. Recovery will not overwrite it.",
                        "matches": "The original project file matches its recorded byte identity. Recovery still opens an unsaved copy.",
                    }
                    text += "\n" + ui_text(keys[observed])
                except (OSError, ValueError) as exc:
                    text += "\n" + ui_format("Recovery copy could not be checked: {error}", error=str(exc))
            self.status.setText(text)

    def restore_selected(self):
        candidate = self.selected()
        if candidate is None or candidate.error:
            return False
        try:
            if not self.restore(candidate):
                return False
        except Exception as exc:  # Keep the candidate; callback errors cannot imply recovery.
            self.status.setText(ui_format("Recovery failed: {error}", error=str(exc)))
            return False
        self.accept()
        return True

    def discard_selected(self):
        candidate = self.selected()
        if candidate is None or not candidate.raw_sha256:
            return False
        answer = QMessageBox.question(
            self, ui_text("Discard recovery copy"),
            ui_text("Discard only this recovery copy? The original project and source files will not be changed."),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return False
        try:
            with self.store.claim(candidate) as claim:
                claim.discard()
        except (OSError, ValueError) as exc:
            self.status.setText(ui_format("Recovery copy could not be discarded: {error}", error=str(exc)))
            return False
        self.refresh()
        return True
