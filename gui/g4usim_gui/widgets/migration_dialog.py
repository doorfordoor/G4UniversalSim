"""Review a format migration and write an explicit, separate copy."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Callable

from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from g4usim_gui.core.i18n import ui_format, ui_text


class MigrationDialog(QDialog):
    """The core owns parsing, compatibility rules and exclusive file publication."""

    def __init__(self, parent=None, *, open_project: Callable[[str], bool] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(ui_text("Configuration migration copy..."))
        self.resize(960, 700)
        self._plan = None
        self._written_path: Path | None = None
        self._open_project = open_project
        self.kind = QComboBox()
        for label, token in (("Project JSON", "project"), ("Main INI", "main"), ("Geometry INI", "geometry")):
            self.kind.addItem(ui_text(label), token)
        self.source_path = QLineEdit()
        self.source_path.setPlaceholderText(ui_text("Select the source file; it will remain unchanged."))
        self.browse_button = QPushButton(ui_text("Browse..."))
        self.preview_button = QPushButton(ui_text("Preview migration"))
        self.preview_button.setDefault(True)
        inputs = QHBoxLayout()
        for widget in (self.kind, self.source_path, self.browse_button, self.preview_button):
            inputs.addWidget(widget)
        self.template = QComboBox()
        for token in ("hierarchical", "layered_device", "simple_box", "array", "shielding", "gdml"):
            self.template.addItem(token, token)
        self.template.setToolTip(ui_text("Geometry template from the original main INI; this does not expand GUI editing support."))
        self.template.setVisible(False)
        self.mapping = QPlainTextEdit()
        self.mapping.setMaximumHeight(80)
        self.mapping.setPlaceholderText(ui_text('Optional explicit metadata map as JSON: {"[volume.target]/label": "metadata.label"}'))
        self.mapping.setVisible(False)
        self.version_label = QLabel(ui_text("No migration preview loaded."))
        self.version_label.setWordWrap(True)
        self.boundary_label = QLabel(ui_text("Format checks only. No simulation has run and physical correctness is not established."))
        self.boundary_label.setWordWrap(True)
        self.changes = QTableWidget(0, 1)
        self.changes.setHorizontalHeaderLabels([ui_text("Reviewed changes")])
        self.changes.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.changes.horizontalHeader().setStretchLastSection(True)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.output_preview = QPlainTextEdit()
        self.output_preview.setReadOnly(True)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.changes, ui_text("Changes"))
        self.tabs.addTab(self.diagnostics, ui_text("Diagnostics"))
        self.tabs.addTab(self.output_preview, ui_text("Output preview"))
        self.status = QLabel(ui_text("Previewing does not change the current project."))
        self.status.setWordWrap(True)
        self.write_button = QPushButton(ui_text("Write new copy..."))
        self.write_button.setEnabled(False)
        self.open_button = QPushButton(ui_text("Open new project copy"))
        self.open_button.setEnabled(False)
        self.close_button = QPushButton(ui_text("Close"))
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for widget in (self.write_button, self.open_button, self.close_button):
            widget.setAutoDefault(False)
            buttons.addWidget(widget)
        self.browse_button.setAutoDefault(False)
        layout = QVBoxLayout(self)
        for widget in (self.boundary_label,):
            layout.addWidget(widget)
        layout.addLayout(inputs)
        layout.addWidget(self.template)
        layout.addWidget(self.mapping)
        layout.addWidget(self.version_label)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        self.browse_button.clicked.connect(self._browse)
        self.preview_button.clicked.connect(self.preview)
        self.write_button.clicked.connect(self._choose_target)
        self.open_button.clicked.connect(self._open_copy)
        self.close_button.clicked.connect(self.reject)
        self.source_path.textChanged.connect(self._invalidate)
        self.kind.currentIndexChanged.connect(self._invalidate)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.template.currentIndexChanged.connect(self._invalidate)
        self.mapping.textChanged.connect(self._invalidate)

    def _kind_changed(self) -> None:
        geometry = self.kind.currentData() == "geometry"
        self.template.setVisible(geometry)
        self.mapping.setVisible(geometry)

    def _invalidate(self, *_args) -> None:
        self._plan = None
        self._written_path = None
        self.write_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.version_label.setText(ui_text("No migration preview loaded."))
        self.changes.setRowCount(0)
        self.diagnostics.clear()
        self.output_preview.clear()
        self.status.setText(ui_text("Inputs changed; preview again before writing a copy."))

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, ui_text("Select migration source"), self.source_path.text())
        if path:
            self.source_path.setText(path)

    def preview(self) -> bool:
        self._invalidate()
        try:
            source = self.source_path.text().strip()
            if self.kind.currentData() == "project":
                from g4usim_gui.core.project_migration import plan_project_migration
                plan = plan_project_migration(source)
            elif self.kind.currentData() == "geometry":
                from g4usim_gui.core.config_migration import load_json_strict
                from g4usim_gui.core.geometry_migration import plan_geometry_migration
                mapping = load_json_strict(self.mapping.toPlainText()) if self.mapping.toPlainText().strip() else {}
                if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
                    raise ValueError(ui_text("Metadata mapping must be a JSON object of string keys and values."))
                plan = plan_geometry_migration(source, self.template.currentData(), metadata_mapping=mapping)
            else:
                from g4usim_gui.core.main_ini_migration import plan_main_ini_migration
                plan = plan_main_ini_migration(source)
            self._display_plan(plan)
        except Exception as error:  # noqa: BLE001 - failed candidates never become writable.
            self.status.setText(ui_format("Migration preview failed: {error}", error=error))
            self.diagnostics.setPlainText(ui_format("Blocked: {error}", error=error))
            return False
        self._plan = plan
        return True

    def _display_plan(self, plan) -> None:
        self.version_label.setText(ui_format(
            "{kind}: input version {input_version} → output version {target}",
            kind=self.kind.currentText(), input_version=plan.input_version if plan.input_version is not None else ui_text("absent (legacy)"),
            target=plan.output_version,
        ))
        self.changes.setRowCount(len(plan.changes))
        for row, change in enumerate(plan.changes):
            version_change = re.fullmatch(r"(Project|Geometry) version (.+) -> (.+)", change)
            if version_change:
                change = ui_format("{kind} format version: {before} → {after}", kind=ui_text(version_change[1]),
                                   before=version_change[2], after=version_change[3])
            else:
                change = ui_text(change)
            self.changes.setItem(row, 0, QTableWidgetItem(change))
        self.changes.resizeRowsToContents()
        lines = [ui_text("Checks performed and remaining boundaries:")]
        lines.extend(ui_text(item) for item in plan.validation)
        self.diagnostics.setPlainText("\n".join(lines))
        self.output_preview.setPlainText(plan.payload.decode("utf-8"))
        self.write_button.setEnabled(True)
        self.status.setText(ui_text("Review the changes, then choose a new file. Existing files cannot be overwritten."))

    def _choose_target(self) -> None:
        if self._plan is None:
            return
        source = Path(self.source_path.text())
        suggested = source.with_name(source.stem + ".migrated" + source.suffix)
        path, _ = QFileDialog.getSaveFileName(self, ui_text("Write migration copy"), str(suggested),
                                              options=QFileDialog.Option.DontConfirmOverwrite)
        if path:
            self.write_copy(path)

    def write_copy(self, target: str | Path) -> bool:
        if self._plan is None:
            return False
        try:
            from g4usim_gui.core.config_migration import publish_migration
            result = publish_migration(self._plan, target)
            written = result.destination
        except Exception as error:  # noqa: BLE001 - leave the current project and source untouched.
            self.status.setText(ui_format("Migration copy failed: {error}", error=error))
            return False
        self._written_path = Path(written)
        self.open_button.setEnabled(self.kind.currentData() == "project" and self._open_project is not None)
        self.status.setText(ui_format("New copy written: {path}. The current project has not changed.", path=written))
        if result.cleanup_warning:
            self.status.setText(self.status.text() + "\n" + ui_format("Published copy cleanup warning: {warning}", warning=result.cleanup_warning))
        return True

    def _open_copy(self) -> None:
        if self._written_path is not None and self._open_project is not None:
            if self._open_project(str(self._written_path)):
                self.accept()
