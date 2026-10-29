from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QSplitter, QTreeWidget, QTreeWidgetItem, QPlainTextEdit,
    QFileDialog, QTabWidget, QHeaderView, QSizePolicy, QComboBox)

from ..core.effective_config import (MISSING, load_snapshot_document, value_text,
    decoded_path, snapshot_diff)
from ..core.i18n import ui_text, ui_format
from .qt_data import combo_data


MAX_FILES = 64
MAX_TOTAL_BYTES = 32 * 1024 * 1024


class EffectiveConfigPage(QWidget):
    """Read-only snapshot review. Loading never changes a project or runner."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.snapshot = None
        self.snapshot_path = None
        self.stale = False
        self._error = ""
        self._raw = ""
        self._snapshots = []   # list of dict(entry metadata)
        self._current = -1
        self._baseline = -1    # -1 means none

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
        self.module_filter_label = QLabel()
        self.module_filter = QComboBox()
        self.diff_only = QCheckBox()
        self.snapshot_label = QLabel()
        self.snapshot_combo = QComboBox()
        self.baseline_label = QLabel()
        self.baseline_combo = QComboBox()
        for widget in (self.load_button, self.reload_button):
            bar.addWidget(widget)
        bar.addStretch()
        layout.addLayout(bar)
        selectors = QHBoxLayout()
        for label, combo in ((self.snapshot_label, self.snapshot_combo), (self.baseline_label, self.baseline_combo)):
            combo.setMinimumContentsLength(16)
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            selectors.addWidget(label)
            selectors.addWidget(combo, 1)
        layout.addLayout(selectors)

        bar2 = QHBoxLayout()
        for widget in (self.search, self.module_filter_label, self.module_filter):
            bar2.addWidget(widget)
        layout.addLayout(bar2)
        checks = QHBoxLayout()
        checks.addWidget(self.unknown_only)
        checks.addWidget(self.diff_only)
        checks.addStretch()
        layout.addLayout(checks)

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
        self.tree.setMinimumWidth(240)
        self.tree.setColumnCount(4)
        self.tree.header().setSectionResizeMode(QHeaderView.Interactive)
        self.tree.header().setStretchLastSection(False)
        for index, width in enumerate((200, 140, 130, 160)):
            self.tree.setColumnWidth(index, width)
        split.addWidget(self.tree)

        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(240)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.raw = QPlainTextEdit()
        self.raw.setReadOnly(True)
        self.diff = QPlainTextEdit()
        self.diff.setReadOnly(True)
        self.tabs.addTab(self.details, "")
        self.tabs.addTab(self.raw, "")
        self.tabs.addTab(self.diff, "")
        split.addWidget(self.tabs)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 4)
        split.setSizes([560, 760])
        split.setChildrenCollapsible(False)
        layout.addWidget(split, 1)

        self.load_button.clicked.connect(self._browse)
        self.reload_button.clicked.connect(self._reload)
        self.search.textChanged.connect(self._populate)
        self.unknown_only.toggled.connect(self._populate)
        self.diff_only.toggled.connect(self._populate)
        self.module_filter.currentIndexChanged.connect(self._populate)
        self.tree.currentItemChanged.connect(self._selected)
        self.snapshot_combo.currentIndexChanged.connect(self._snapshot_selected)
        self.baseline_combo.currentIndexChanged.connect(self._baseline_selected)
        self.refresh_language()

    # ---------- loading ----------

    def _browse(self):
        paths, _ = QFileDialog.getOpenFileNames(self, ui_text("Load EffectiveConfig snapshot"), "", "JSON (*.json)")
        if paths:
            self.load_files(paths)

    def _reload(self):
        if not self._snapshots:
            return
        # Stage every member before publishing, preserving comparison selections.
        current, baseline = self._current, self._baseline
        if self.load_files([entry["path"] for entry in self._snapshots]):
            self._commit_selection(current, baseline)

    def _read_validate(self, path):
        return load_snapshot_document(path)

    def _entry(self, path, snap, raw, content):
        import hashlib
        return {
            "path": str(path),
            "name": Path(path).name,
            "snapshot": snap,
            "raw": raw,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        }

    def load_file(self, path: str | Path) -> bool:
        """Back-compat: load a single file replacing the current set."""
        return self.load_files([path])

    def load_files(self, paths) -> bool:
        """Atomically load a set of snapshot files. All must validate."""
        paths = [Path(p) for p in paths]
        if not paths or len(paths) > MAX_FILES:
            self._error = ui_text("Snapshot set invalid (empty or exceeds 64 files)")
            self.stale = self.snapshot is not None
            self._update_status()
            return False
        new_entries = []
        total = 0
        for path in paths:
            try:
                snap, raw, content = self._read_validate(path)
            except (OSError, ValueError, RecursionError) as exc:
                self._error = str(exc)
                self.stale = self.snapshot is not None
                self._update_status()
                return False
            total += len(content)
            if total > MAX_TOTAL_BYTES:
                self._error = ui_text("Snapshot set exceeds 32 MiB total limit")
                self.stale = self.snapshot is not None
                self._update_status()
                return False
            new_entries.append(self._entry(path, snap, raw, content))
        self._commit(new_entries)
        return True

    def _replace_one(self, index, path):
        try:
            snap, raw, content = self._read_validate(path)
        except (OSError, ValueError, RecursionError) as exc:
            self._error = str(exc)
            self.stale = True
            self._update_status()
            return False
        entry = self._entry(path, snap, raw, content)
        if sum(e["size"] for i, e in enumerate(self._snapshots) if i != index) + entry["size"] > MAX_TOTAL_BYTES:
            self._error = ui_text("Snapshot set exceeds 32 MiB total limit")
            self.stale = True
            self._update_status()
            return False
        self._snapshots[index] = entry
        self._error = ""
        self.stale = False
        self._commit_selection(self._current, self._baseline)
        return True

    def _commit(self, entries):
        self._snapshots = entries
        self._current = 0 if entries else -1
        self._baseline = -1
        self._error = ""
        self.stale = False
        self._commit_selection(self._current, self._baseline)

    def _commit_selection(self, current, baseline):
        self._current = current
        self._baseline = baseline
        if 0 <= current < len(self._snapshots):
            entry = self._snapshots[current]
            self.snapshot = entry["snapshot"]
            self.snapshot_path = Path(entry["path"])
            self._raw = entry["raw"]
            self.raw.setPlainText(entry["raw"])
        else:
            self.snapshot = None
            self.snapshot_path = None
            self._raw = ""
            self.raw.clear()
        self._rebuild_combos()
        self._refresh_module_filter()
        self._populate()
        self._populate_diff()
        self._update_status()

    # ---------- combos ----------

    def _entry_label(self, entry):
        snap = entry["snapshot"]
        return ui_format("{file} | stage: {stage} | run: {run} | thread: {thread} | revision: {rev}",
                         file=entry["name"], stage=snap["stage"],
                         run=self._diff_value(snap.get("run_id", MISSING)), thread=self._diff_value(snap.get("thread_id", MISSING)), rev=snap["revision"])

    def _rebuild_combos(self):
        self.snapshot_combo.blockSignals(True)
        self.baseline_combo.blockSignals(True)
        try:
            self.snapshot_combo.clear()
            self.baseline_combo.clear()
            self.baseline_combo.addItem(ui_text("None"), -1)
            for index, entry in enumerate(self._snapshots):
                label = self._entry_label(entry)
                self.snapshot_combo.addItem(label, index)
                self.baseline_combo.addItem(label, index)
            if 0 <= self._current < self.snapshot_combo.count():
                self.snapshot_combo.setCurrentIndex(self._current)
            # baseline index maps: item 0 == -1, else index+1
            self.baseline_combo.setCurrentIndex(self._baseline + 1 if self._baseline >= 0 else 0)
        finally:
            self.snapshot_combo.blockSignals(False)
            self.baseline_combo.blockSignals(False)

    def _snapshot_selected(self, combo_index):
        data = combo_data(self.snapshot_combo, combo_index)
        if data is None or data < 0 or data >= len(self._snapshots):
            return
        self._commit_selection(data, self._baseline)

    def _baseline_selected(self, combo_index):
        data = combo_data(self.baseline_combo, combo_index)
        self._baseline = -1 if data is None else data
        self._populate_diff()
        self._populate()

    # ---------- filters ----------

    def _refresh_module_filter(self):
        self.module_filter.blockSignals(True)
        try:
            previous = combo_data(self.module_filter)
            self.module_filter.clear()
            self.module_filter.addItem(ui_text("All modules"), "")
            modules = set()
            if self.snapshot is not None:
                for field in self.snapshot["fields"]:
                    tokens = field["path"].split("/")[1:]
                    modules.add(tokens[0] if tokens else "")
            for module in sorted(modules):
                self.module_filter.addItem(module, module)
            if previous:
                idx = self.module_filter.findData(previous)
                if idx >= 0:
                    self.module_filter.setCurrentIndex(idx)
        finally:
            self.module_filter.blockSignals(False)

    @staticmethod
    def _unknown(field):
        return ("requested" not in field or "resolved" not in field or
                field.get("application_status", "unknown") == "unknown" or
                "evidence_level" not in field)

    def _value(self, field, key):
        value = field.get(key, MISSING)
        return ui_text("Unknown (not provided)") if value is MISSING else value_text(value)

    def _diff_map(self):
        if self._baseline < 0 or self._baseline >= len(self._snapshots):
            return {}
        before = self._snapshots[self._baseline]["snapshot"]
        if self.snapshot is None:
            return {}
        changes = snapshot_diff(before, self.snapshot)
        return {c["path"]: c for c in changes}

    def _populate(self, *_):
        current = self.tree.currentItem()
        selected = current.data(0, Qt.UserRole) if current is not None else None
        selected_path = selected.get("path") if selected else None
        self.tree.clear()
        self.details.clear()
        if self.snapshot is None:
            return
        query = self.search.text().casefold()
        module = self.module_filter.currentData()
        diff_map = self._diff_map()
        only_diff = self._baseline >= 0 and self.diff_only.isChecked()
        groups = {}
        selected_item = None

        for field in self.snapshot["fields"]:
            path = field["path"]
            tokens = decoded_path(path)
            canonical_tokens = path.split("/")[1:]
            if module and canonical_tokens[0] != module:
                continue
            matches = query in path.casefold() or any(query in token.casefold() for token in tokens)
            if not matches or (self.unknown_only.isChecked() and not self._unknown(field)):
                continue
            if only_diff and path not in diff_map:
                continue
            parent = self.tree.invisibleRootItem()
            for index, token in enumerate(tokens[:-1]):
                prefix = tuple(canonical_tokens[:index + 1])
                if prefix not in groups:
                    groups[prefix] = QTreeWidgetItem(parent, [token])
                parent = groups[prefix]
            status = field.get("application_status", "unknown")
            diff = diff_map.get(path)
            marker = ""
            if diff is not None:
                marker = {"added": " [+]" , "removed": " [-]", "changed": " [~]"}.get(diff["kind"], "")
            item = QTreeWidgetItem(parent, [tokens[-1] + marker, self._value(field, "resolved"),
                ui_text(status), ui_text(field.get("evidence_level", "Unknown (not provided)"))])
            item.setData(0, Qt.UserRole, field)
            item.setToolTip(0, path)
            if path == selected_path:
                selected_item = item
        def summarize(node):
            if node.data(0, Qt.UserRole):
                return 1
            count = sum(summarize(node.child(i)) for i in range(node.childCount()))
            node.setText(1, ui_format("Visible fields: {count}", count=count))
            node.setToolTip(1, ui_text("Summary — not a coverage or success proof"))
            return count
        for index in range(self.tree.topLevelItemCount()):
            summarize(self.tree.topLevelItem(index))
        self.tree.expandToDepth(0)
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)

    def _populate_diff(self):
        self.diff_only.setEnabled(self._baseline >= 0 and self.snapshot is not None)
        if self._baseline < 0 or self._baseline >= len(self._snapshots) or self.snapshot is None:
            self.diff.setPlainText(ui_text("No comparison baseline selected."))
            return
        before = self._snapshots[self._baseline]["snapshot"]
        changes = snapshot_diff(before, self.snapshot)
        if not changes:
            self.diff.setPlainText(ui_text("No differences between compared snapshots."))
            return
        lines = [ui_format("Added: {a}  Removed: {r}  Changed: {c}",
                           a=sum(1 for c in changes if c["kind"] == "added"),
                           r=sum(1 for c in changes if c["kind"] == "removed"),
                           c=sum(1 for c in changes if c["kind"] == "changed")), ""]
        for change in changes:
            lines.append(ui_format("[{kind}] {path}", kind=ui_text(change["kind"]), path=change["path"]))
            if change["kind"] == "changed":
                for key in change["keys"]:
                    before_val = change["before"].get(key, MISSING) if key in change["before"] else MISSING
                    after_val = change["after"].get(key, MISSING) if key in change["after"] else MISSING
                    lines.append(f"  {key}: " + self._diff_value(before_val) + " -> " + self._diff_value(after_val))
            else:
                present = change["after"] if change["kind"] == "added" else change["before"]
                for key in ("requested", "resolved", "application_status", "evidence_level", "origins"):
                    if key in present:
                        lines.append(f"  {key}: " + value_text(present[key]))
            lines.append("")
        self.diff.setPlainText("\n".join(lines))

    @staticmethod
    def _diff_value(value):
        return value_text(value) if value is not MISSING else ui_text("Unknown (not provided)")

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
                "applied_revision", "evidence_level", "evidence_source", "reason")
        lines = [f"{ui_text(key)}: {self._value(field, key)}" for key in keys]
        origins = field.get("origins", [])
        lines.append("")
        lines.append(ui_text("Origins (in order):"))
        if not origins:
            lines.append("  " + ui_text("Unknown (not provided)"))
        else:
            for origin in origins:
                lines.append("  " + json.dumps(origin, ensure_ascii=False))
        for optional in ("evidence", "inputs", "coverage"):
            if optional in self.snapshot:
                lines.append("")
                lines.append(f"{ui_text(optional.capitalize())}: " + json.dumps(self.snapshot[optional], ensure_ascii=False))
        self.details.setPlainText("\n".join(lines))

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
        enabled = self.snapshot is not None
        self.reload_button.setEnabled(enabled)
        if not enabled:
            self.meta.clear()
            return
        entry = self._snapshots[self._current] if 0 <= self._current < len(self._snapshots) else None
        snap = self.snapshot
        self.meta.setText(ui_format("File: {path} | stage: {stage} | revision: {revision} | run_id: {run} | scope: {scope} | set: {n}",
            path=self.snapshot_path, stage=snap["stage"], revision=snap["revision"],
            run=value_text(snap.get("run_id", MISSING)), scope=snap.get("scope", ui_text("Unknown (not provided)")),
            n=len(self._snapshots)))

    def refresh_language(self):
        self.title.setText(ui_text("Effective configuration review — read only"))
        self.boundary.setText(ui_text("Configuration values and application evidence are separate. A snapshot does not establish simulation success; use the independent run result.") + "\n" + ui_text("Differences do not establish chronology. Missing coverage metadata remains unknown."))
        self.load_button.setText(ui_text("Load snapshot..."))
        self.reload_button.setText(ui_text("Reload snapshot"))
        self.search.setPlaceholderText(ui_text("Search canonical path or object name"))
        self.search.setAccessibleName(ui_text("Search canonical path or object name"))
        self.unknown_only.setText(ui_text("Only unknown fields"))
        self.diff_only.setText(ui_text("Only differences vs baseline"))
        self.module_filter_label.setText(ui_text("Module:"))
        self.snapshot_label.setText(ui_text("Snapshot:"))
        self.baseline_label.setText(ui_text("Baseline:"))
        self.tree.setHeaderLabels([ui_text(v) for v in ("Field / object", "Resolved", "Application status", "Evidence level")])
        self.tree.setAccessibleName(ui_text("Effective configuration object tree"))
        self.details.setAccessibleName(ui_text("Field details and origin chain"))
        self.raw.setAccessibleName(ui_text("Original JSON"))
        self.diff.setAccessibleName(ui_text("Snapshot differences"))
        self.tabs.setTabText(0, ui_text("Field details and origin chain"))
        self.tabs.setTabText(1, ui_text("Original JSON"))
        self.tabs.setTabText(2, ui_text("Differences"))
        self._rebuild_combos()
        self._refresh_module_filter()
        self._populate()
        self._populate_diff()
        self._update_status()
