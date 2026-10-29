from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QSplitter, QTreeWidget, QTreeWidgetItem, QPlainTextEdit,
    QFileDialog, QTabWidget, QHeaderView, QSizePolicy)

from ..core.effective_config import MISSING, load_snapshot, value_text
from ..core.i18n import ui_text, ui_format


class EffectiveConfigPage(QWidget):
    """Read-only snapshot review. Loading never changes a project or runner."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.snapshot = None
        self.snapshot_path = None
        self.stale = False
        self._error = ""
        self._raw = ""
        layout = QVBoxLayout(self)
        self.title = QLabel()
        layout.addWidget(self.title)
        self.boundary = QLabel()
        self.boundary.setWordWrap(True)
        layout.addWidget(self.boundary)
        bar = QHBoxLayout()
        self.load_button = QPushButton()
        self.reload_button = QPushButton()
        self.search = QLineEdit()
        self.unknown_only = QCheckBox()
        for widget in (self.load_button, self.reload_button, self.search, self.unknown_only):
            bar.addWidget(widget)
        layout.addLayout(bar)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.meta = QLabel()
        self.meta.setWordWrap(True)
        layout.addWidget(self.meta)
        for label in (self.title, self.boundary, self.status, self.meta):
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        split = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setMinimumWidth(260)
        self.tree.setColumnCount(4)
        self.tree.header().setSectionResizeMode(QHeaderView.Interactive)
        self.tree.header().setStretchLastSection(False)
        for index, width in enumerate((200, 140, 130, 160)):
            self.tree.setColumnWidth(index, width)
        split.addWidget(self.tree)
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(260)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.raw = QPlainTextEdit()
        self.raw.setReadOnly(True)
        self.tabs.addTab(self.details, "")
        self.tabs.addTab(self.raw, "")
        split.addWidget(self.tabs)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 4)
        split.setSizes([600, 800])
        split.setChildrenCollapsible(False)
        layout.addWidget(split, 1)
        self.load_button.clicked.connect(self._browse)
        self.reload_button.clicked.connect(self._reload)
        self.search.textChanged.connect(self._populate)
        self.unknown_only.toggled.connect(self._populate)
        self.tree.currentItemChanged.connect(self._selected)
        self.refresh_language()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, ui_text("Load EffectiveConfig snapshot"), "", "JSON (*.json)")
        if path:
            self.load_file(path)

    def _reload(self):
        if self.snapshot_path:
            self.load_file(self.snapshot_path)

    def load_file(self, path: str | Path) -> bool:
        """Replace the entire snapshot only after successful bounded validation."""
        try:
            candidate, raw = load_snapshot(path)
        except (OSError, ValueError, RecursionError) as exc:
            self._error = str(exc)
            self.stale = self.snapshot is not None
            self._update_status()
            return False
        self.snapshot = candidate
        self.snapshot_path = Path(path)
        self._raw = raw
        self._error = ""
        self.stale = False
        self.raw.setPlainText(raw)
        self._populate()
        self._update_status()
        return True

    @staticmethod
    def _unknown(field):
        return ("requested" not in field or "resolved" not in field or
                field.get("application_status", "unknown") == "unknown" or
                "evidence_level" not in field)

    def _value(self, field, key):
        value = field.get(key, MISSING)
        return ui_text("Unknown (not provided)") if value is MISSING else value_text(value)

    def _populate(self, *_):
        current = self.tree.currentItem()
        selected = current.data(0, Qt.UserRole) if current is not None else None
        selected_path = selected.get("path") if selected else None
        self.tree.clear()
        self.details.clear()
        if self.snapshot is None:
            return
        query = self.search.text().casefold()
        groups = {}
        selected_item = None
        for field in self.snapshot["fields"]:
            path = field["path"]
            tokens = [v.replace("~1", "/").replace("~0", "~") for v in path.split("/")[1:]]
            matches = query in path.casefold() or any(query in token.casefold() for token in tokens)
            if not matches or (self.unknown_only.isChecked() and not self._unknown(field)):
                continue
            parent = self.tree.invisibleRootItem()
            for index, token in enumerate(tokens[:-1]):
                prefix = tuple(tokens[:index + 1])
                if prefix not in groups:
                    groups[prefix] = QTreeWidgetItem(parent, [token])
                parent = groups[prefix]
            item = QTreeWidgetItem(parent, [tokens[-1], self._value(field, "resolved"),
                field.get("application_status", "unknown"), field.get("evidence_level", ui_text("Unknown (not provided)"))])
            item.setData(0, Qt.UserRole, field)
            item.setToolTip(0, path)
            if path == selected_path:
                selected_item = item
        self.tree.expandToDepth(0)
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)

    def _selected(self, item, _previous):
        if item is None:
            return
        field = item.data(0, Qt.UserRole)
        if field is None:
            paths = []
            def collect(node):
                value = node.data(0, Qt.UserRole)
                if value:
                    paths.append(value["path"])
                for index in range(node.childCount()):
                    collect(node.child(index))
            collect(item)
            self.details.setPlainText(ui_format("Visible fields: {count}", count=len(paths)) + "\n" + "\n".join(paths))
            return
        keys = ("path", "requested", "resolved", "unit", "application_status", "revision",
                "applied_revision", "evidence_level", "evidence_source", "reason", "origins")
        lines = [f"{ui_text(key)}: {self._value(field, key)}" for key in keys]
        lines.append(ui_text("Experimental / runtime capability: unknown (not provided by this schema)."))
        self.details.setPlainText("\n\n".join(lines))

    def _update_status(self):
        if self._error:
            text = ui_format("Snapshot load failed: {error}", error=self._error)
            if self.stale:
                text += "\n" + ui_text("Stale: showing the previous valid snapshot; failed input was not merged.")
        elif self.snapshot is None:
            text = ui_text("No snapshot loaded. This page does not generate snapshots.")
        else:
            text = ui_text("Snapshot loaded for review only.")
        self.status.setText(text)
        self.reload_button.setEnabled(self.snapshot_path is not None)
        if self.snapshot is not None:
            self.meta.setText(ui_format("File: {path} | stage: {stage} | revision: {revision} | run_id: {run} | scope: {scope}",
                path=self.snapshot_path, stage=self.snapshot["stage"], revision=self.snapshot["revision"],
                run=value_text(self.snapshot["run_id"]), scope=self.snapshot.get("scope", ui_text("Unknown (not provided)"))))

    def refresh_language(self):
        self.title.setText(ui_text("Effective configuration review — read only"))
        self.boundary.setText(ui_text("Manager state subset only. Manager acceptance is not kernel application. This snapshot does not establish simulation success; use the independent run result."))
        self.load_button.setText(ui_text("Load snapshot..."))
        self.reload_button.setText(ui_text("Reload snapshot"))
        self.search.setPlaceholderText(ui_text("Search canonical path or object name"))
        self.search.setAccessibleName(ui_text("Search canonical path or object name"))
        self.unknown_only.setText(ui_text("Only unknown fields"))
        self.tree.setHeaderLabels([ui_text(v) for v in ("Field / object", "Resolved", "Application status", "Evidence level")])
        self.tree.setAccessibleName(ui_text("Effective configuration object tree"))
        self.details.setAccessibleName(ui_text("Field details and origin chain"))
        self.tabs.setTabText(0, ui_text("Field details and origin chain"))
        self.tabs.setTabText(1, ui_text("Original JSON"))
        self._populate()
        self._update_status()
