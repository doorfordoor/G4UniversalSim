"""Materials editor: its widget (the Materials tab) and its logic on the Configuration page."""

from __future__ import annotations

from g4usim_gui.window.transactions import edit_operation, capture_detail_raw, restore_detail_raw
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.editors.geometry_editor_model import geometry_material_refs
from g4usim_gui.editors.material_editor_model import (
    MaterialDocument,
    add_default_row,
    delete_row,
    duplicate_row,
    generate_materials_ini_text,
    material_document_from_summary,
    validate_material_document,
)
from g4usim_gui.parsers.materials_parser import NIST_QUICK_LIST, parse_materials
from g4usim_gui.widgets.ui_helpers import set_table_compact_readonly, set_table_minimum_rows, toolbar_grid


class MaterialsEditor(QWidget):
    """Materials tab: the table of materials and the selected material's fields."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.materials_table = QTableWidget(0, 6)
        self.materials_table.setHorizontalHeaderLabels(["enabled", "name", "mode", "density", "components", "status"])
        set_table_compact_readonly(self.materials_table)
        set_table_minimum_rows(self.materials_table, 8)
        self.materials_count_label = QLabel("Materials: 0 entries | Preview only")
        self.materials_count_label.setWordWrap(True)
        self.load_materials_editor_button = QPushButton("Load from file")
        self.load_materials_editor_button.setToolTip("Load the selected materials.ini into the editor")
        self.add_nist_button = QPushButton("Add NIST")
        self.add_mass_button = QPushButton("Add mass_fraction")
        self.add_volume_fraction_button = QPushButton("Add volume_fraction")
        self.add_atom_button = QPushButton("Add atom_count")
        self.duplicate_material_button = QPushButton("Duplicate")
        self.delete_material_button = QPushButton("Delete")
        self.validate_materials_button = QPushButton("Validate Materials")
        self.revert_materials_button = QPushButton("Revert to source")
        self.material_name = QLineEdit()
        self.material_mode = QComboBox()
        self.material_mode.addItems(["nist", "mass_fraction", "volume_fraction", "atom_count"])
        self.material_density = QLineEdit()
        self.material_enabled = QCheckBox("Enabled")
        self.material_components = QPlainTextEdit()
        self.material_components.setPlaceholderText("One component per line, e.g.\nG4_Si:0.7\nG4_O:0.3")
        self.material_notes = QPlainTextEdit()
        self.material_notes.setReadOnly(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Materials Editor"))
        layout.addWidget(self.materials_count_label)
        target = QLabel("Generated target: run package config/materials/material.ini. Source file is never overwritten.")
        target.setWordWrap(True)
        layout.addWidget(target)
        # two rows: adding materials, then file and edit actions (one row of five was too wide)
        layout.addLayout(toolbar_grid([
            self.add_nist_button,
            self.add_mass_button,
            self.add_volume_fraction_button,
            self.add_atom_button,
        ], 4))
        layout.addLayout(toolbar_grid([
            self.load_materials_editor_button,
            self.duplicate_material_button,
            self.delete_material_button,
            self.validate_materials_button,
            self.revert_materials_button,
        ], 5))
        layout.addWidget(self.materials_table, 2)

        detail = QGroupBox("Selected material")
        detail_layout = QGridLayout(detail)
        detail_layout.addWidget(QLabel("Name"), 0, 0)
        detail_layout.addWidget(self.material_name, 0, 1)
        detail_layout.addWidget(QLabel("Mode"), 0, 2)
        detail_layout.addWidget(self.material_mode, 0, 3)
        detail_layout.addWidget(QLabel("Density"), 1, 0)
        detail_layout.addWidget(self.material_density, 1, 1)
        detail_layout.addWidget(self.material_enabled, 1, 2, 1, 2)
        detail_layout.addWidget(QLabel("Components"), 2, 0)
        detail_layout.addWidget(self.material_components, 2, 1, 1, 3)
        detail_layout.addWidget(QLabel("Status"), 3, 0)
        detail_layout.addWidget(self.material_notes, 3, 1, 1, 3)
        self.material_components.setMinimumHeight(90)
        self.material_notes.setMinimumHeight(70)
        layout.addWidget(detail, 1)


class MaterialsMixin:
    """Materials logic; mixed into ConfigBuilderPage, which holds the documents."""

    def _connect_material_buttons(self) -> None:
        """Materials tab buttons and table."""
        self.load_materials_editor_button.clicked.connect(self.reload_materials)
        self.add_nist_button.clicked.connect(lambda: self._add_material("nist"))
        self.add_mass_button.clicked.connect(lambda: self._add_material("mass_fraction"))
        self.add_volume_fraction_button.clicked.connect(lambda: self._add_material("volume_fraction"))
        self.add_atom_button.clicked.connect(lambda: self._add_material("atom_count"))
        self.duplicate_material_button.clicked.connect(self._duplicate_material)
        self.delete_material_button.clicked.connect(self._delete_material)
        self.validate_materials_button.clicked.connect(self._validate_materials_editor)
        self.revert_materials_button.clicked.connect(self.reload_materials)
        self.materials_table.itemSelectionChanged.connect(self._on_material_selection_changed)

    def _connect_material_detail(self) -> None:
        """The selected material's fields."""
        self.material_name.textEdited.connect(self._update_selected_material_from_detail)
        self.material_mode.currentTextChanged.connect(self._update_selected_material_from_detail)
        self.material_density.textEdited.connect(self._update_selected_material_from_detail)
        self.material_components.textChanged.connect(self._update_selected_material_from_detail)
        self.material_enabled.stateChanged.connect(self._update_selected_material_from_detail)

    def reload_materials(self) -> None:
        path = self.materials_config.text().strip()
        self.materials_summary = parse_materials(path) if path else None
        if self.materials_summary is not None:
            self.materials_summary._f5_source_anchor = str(Path(path).expanduser().resolve())
        self.materials_messages.clear()
        self.materials_raw.clear()
        self.generated_materials_raw.clear()
        if not self.materials_summary:
            self.material_document = MaterialDocument()
            self._selected_material_row = -1
            self._populate_material_editor()
            self._update_workspace_summary()
            return
        self.material_document = material_document_from_summary(self.materials_summary)
        self.material_document.source_path = self.materials_summary._f5_source_anchor
        self._selected_material_row = -1
        self._populate_material_editor()
        self.materials_messages.setPlainText(self._messages_text(self.materials_summary.errors, self.materials_summary.warnings))
        self.materials_raw.setPlainText(self._preview_text(self.materials_summary.raw_text))
        self._update_workspace_summary()

    def _geometry_refs(self):
        """Materials used by the geometry being generated: the edited document when dirty, else the source file."""
        if self.geometry_document.is_dirty:
            return geometry_material_refs(self.geometry_document)
        return self.geometry_summary.material_refs if self.geometry_summary else None

    def _populate_material_editor(self) -> None:
        refs = self._geometry_refs()
        validate_material_document(
            self.material_document,
            geometry_material_refs=refs,
        )
        self.materials_table.setRowCount(0)
        for item in self.material_document.rows:
            row = self.materials_table.rowCount()
            self.materials_table.insertRow(row)
            values = [
                "yes" if item.enabled else "no",
                item.name,
                item.mode,
                item.density,
                self._component_preview(item.components_text),
                item.status,
            ]
            for col, value in enumerate(values):
                self.materials_table.setItem(row, col, QTableWidgetItem(value))
        self.materials_table.resizeColumnsToContents()
        self._update_material_count_label()
        self.materials_messages.setPlainText(self._messages_text(self.material_document.errors, self.material_document.warnings))
        try:
            self.generated_materials_raw.setPlainText(generate_materials_ini_text(self.material_document))
        except Exception as exc:  # noqa: BLE001
            self.generated_materials_raw.setPlainText(f"Generated preview unavailable:\n{exc}")
        validate_material_document(
            self.material_document,
            geometry_material_refs=refs,
        )
        self.materials_messages.setPlainText(self._messages_text(self.material_document.errors, self.material_document.warnings))
        self._apply_material_candidates()
        self._validate_geometry_editor()
        self._update_workspace_summary()
        self._select_material_row(min(self._selected_material_row, len(self.material_document.rows) - 1))

    def _update_material_count_label(self) -> None:
        self.materials_count_label.setText(
            ui_format(
                "Materials: {count} rows, {enabled} enabled | {errors} errors, {warnings} warnings | {state}",
                count=len(self.material_document.rows),
                enabled=sum(1 for row in self.material_document.rows if row.enabled),
                errors=len(self.material_document.errors),
                warnings=len(self.material_document.warnings),
                state=ui_text("Dirty" if self.material_document.is_dirty else "Clean"),
            )
        )

    def _select_material_row(self, row: int) -> None:
        self._building = True
        self._selected_material_row = row
        if row < 0 or row >= len(self.material_document.rows):
            self.material_name.clear()
            self.material_density.clear()
            self.material_components.clear()
            self.material_notes.setPlainText("Select a material row to edit.")
            self.material_enabled.setChecked(False)
            self._building = False
            return
        item = self.material_document.rows[row]
        self.material_name.setText(item.name)
        self._set_combo_text(self.material_mode, item.mode)
        self.material_density.setText(item.density)
        self.material_enabled.setChecked(item.enabled)
        self.material_components.setPlainText(item.components_text)
        notes = []
        if item.notes:
            notes.append(item.notes)
        notes.extend(f"[ERROR] {text}" for text in item.errors)
        notes.extend(f"[WARN] {text}" for text in item.warnings)
        if not notes:
            notes.append("[INFO] OK")
        self.material_notes.setPlainText("\n".join(notes))
        restore_detail_raw(self, "material", item)
        self._building = False

    def _on_material_selection_changed(self) -> None:
        self._select_material_row(self.materials_table.currentRow())

    def _update_selected_material_from_detail(self) -> None:
        if self._building:
            return
        row = self._selected_material_row
        if row < 0 or row >= len(self.material_document.rows):
            return
        item = self.material_document.rows[row]
        capture_detail_raw(self, "material", item)
        item.name = self.material_name.text().strip()
        item.mode = self.material_mode.currentText().strip()
        item.density = self.material_density.text().strip()
        item.enabled = self.material_enabled.isChecked()
        item.components_text = self.material_components.toPlainText().strip()
        if item.mode == "nist" and item.name.startswith("G4_"):
            item.nist_name = item.name
        item.is_dirty = True
        self.material_document.is_dirty = True
        self._populate_material_editor()
        self.materials_table.selectRow(row)
        self._emit_changed()

    @edit_operation('Add material')
    def _add_material(self, mode: str) -> None:
        row = add_default_row(self.material_document, mode)
        self._selected_material_row = self.material_document.rows.index(row)
        self._populate_material_editor()
        self.materials_table.selectRow(self._selected_material_row)
        self._emit_changed()

    @edit_operation('Duplicate material')
    def _duplicate_material(self) -> None:
        row = self.materials_table.currentRow()
        duplicated = duplicate_row(self.material_document, row)
        if duplicated is None:
            return
        self._selected_material_row = self.material_document.rows.index(duplicated)
        self._populate_material_editor()
        self.materials_table.selectRow(self._selected_material_row)
        self._emit_changed()

    @edit_operation('Delete material')
    def _delete_material(self) -> None:
        row = self.materials_table.currentRow()
        if self.geometry_summary and 0 <= row < len(self.material_document.rows):
            name = self.material_document.rows[row].name
            if name in self.geometry_summary.material_refs:
                self.materials_messages.setPlainText(
                    self.materials_messages.toPlainText()
                    + f"\n[WARN] Deleted material '{name}' is referenced by geometry; validation will report this."
                )
        delete_row(self.material_document, row)
        self._selected_material_row = min(row, len(self.material_document.rows) - 1)
        self._populate_material_editor()
        if self._selected_material_row >= 0:
            self.materials_table.selectRow(self._selected_material_row)
        self._emit_changed()

    def _validate_materials_editor(self) -> None:
        validate_material_document(self.material_document, geometry_material_refs=self._geometry_refs())
        self._populate_material_editor()

    def _component_preview(self, text: str) -> str:
        normalized = "; ".join(line.strip() for line in text.replace(",", "\n").splitlines() if line.strip())
        return normalized[:120] + ("..." if len(normalized) > 120 else "")

    def _populate_nist_table(self) -> None:
        self.nist_table.setRowCount(0)
        for name in sorted(NIST_QUICK_LIST):
            row = self.nist_table.rowCount()
            self.nist_table.insertRow(row)
            self.nist_table.setItem(row, 0, QTableWidgetItem(name))
        self.nist_table.resizeColumnsToContents()

    def _apply_material_candidates(self) -> None:
        candidates = sorted({row.name for row in self.material_document.rows if row.enabled and row.name} | NIST_QUICK_LIST)
        for combo in [self.simple_world_material, self.simple_target_material, self.layered_world_material, self.layer_material]:
            current = combo.currentText().strip()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(candidates)
            if current:
                index = combo.findText(current)
                if index < 0:
                    combo.addItem(current)
                    index = combo.findText(current)
                combo.setCurrentIndex(index)
            combo.blockSignals(False)
