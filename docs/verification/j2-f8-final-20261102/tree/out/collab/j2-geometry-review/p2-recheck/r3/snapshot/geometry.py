"""Geometry editor: its widget (the Geometry tab) and its logic on the Configuration page."""

from __future__ import annotations

from g4usim_gui.window.transactions import edit_operation
import copy
from pathlib import Path

from PySide6.QtCore import Signal
from g4usim_gui.core.solid_registry_data import SOLIDS, solid_spec, property_keys, canonical_solid
from g4usim_gui.parsers.geometry_parser import PLACEMENT_PROPERTY_KEYS

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.diagnostics import collect_diagnostics
from g4usim_gui.editors.geometry_editor_model import (
    GeometryDocument,
    HierarchicalVolumeRow,
    HIERARCHICAL_GEOMETRY_MODES,
    EDITABLE_GEOMETRY_MODES,
    geometry_document_from_summary,
    set_geometry_mode,
    validate_geometry_document,
)
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.widgets.ui_helpers import create_hint_label, set_table_minimum_rows, toolbar_grid


class GeometryDetailsWidget(QWidget):
    """Raw text fields for one selected geometry entity; no document/transaction owner."""
    changed = Signal()

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.fields = {}
        self._loading = False
        self._labels = {}
        self._row = None
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = {'volume': 'Selected volume details', 'boolean': 'Boolean tool details',
                   'layer': 'Backend layer details'}[kind]
        self.heading = QLabel(ui_text(heading))
        self.heading.setProperty('i18nSource_labelText', heading)
        layout.addWidget(self.heading)
        layout.addWidget(self.tabs)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        groups = {}
        def group(title):
            if title not in groups:
                panel = QWidget()
                form = QFormLayout(panel)
                groups[title] = form
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(panel)
                self.tabs.addTab(scroll, ui_text(title))
                self.tabs._i18n_tab_sources = list(groups)
            return groups[title]
        def field(key, title, hint='', choices=None):
            edit = QComboBox() if choices is not None else QPlainTextEdit() if key == 'metadata' else QLineEdit()
            if choices is not None:
                edit.setEditable(True)
                edit.addItems(choices)
            edit.setObjectName('j2_' + kind + '_' + key)
            edit.setAccessibleName(key)
            edit.setToolTip(hint or key)
            label = QLabel(key[5:] if key.startswith("prop.") else "copyNo" if key == "copy_no" else key)
            label.setBuddy(edit)
            self.fields[key] = edit
            self._labels[key] = label
            group(title).addRow(label, edit)
            if isinstance(edit, QComboBox):
                edit.currentTextChanged.connect(self._changed)
            elif isinstance(edit, QPlainTextEdit):
                edit.setMaximumHeight(80)
                edit.textChanged.connect(self._changed)
            else:
                edit.textEdited.connect(self._changed)
        if kind != 'layer':
            names = [name for name, entry in SOLIDS.items() if kind != 'boolean' or entry['boolean_tool']]
            field('shape', 'Shape parameters', choices=names)
            field('size', 'Shape parameters', 'x, y, z (full lengths; mm)')
            field('parameters', 'Shape parameters')
            if kind == 'volume':
                field('copy_no', 'Geometry fields', 'copyNo (signed 32-bit integer)')
            else:
                field('name', 'Geometry fields')
            seen = set()
            for name in names:
                for spec in SOLIDS[name]['properties']:
                    if spec['name'] in seen:
                        continue
                    seen.add(spec['name'])
                    field('prop.' + spec['name'], 'Geometry fields', spec['name'] + ' (' + spec['dimension'] + ')')
                    unit = {'length':'mm','angle':'rad / deg','length_list':'mm, ...'}.get(spec['dimension'])
                    if unit: self._labels['prop.' + spec['name']].setText(spec['name'] + ' (' + unit + ')')
            if kind == 'volume':
                for key in ('placement', 'replica_axis', 'replica_count', 'replica_width', 'replica_offset',
                            'copies_file', 'copies', 'copy_step'):
                    choices = ['normal', 'replica', 'parameterised'] if key == 'placement' else None
                    field(key, 'Placement', key, choices=choices)
        if kind != 'boolean':
            for key in ('vis.color', 'vis.alpha', 'vis.visible', 'vis.wireframe'):
                field(key, 'Backend visual settings (saved to simulation configuration)',
                      'Saved to simulation configuration; separate from local 3D appearance.')
                self.fields[key].setProperty('i18nSource_toolTip', 'Saved to simulation configuration; separate from local 3D appearance.')
            for key in ('cut.gamma', 'cut.e-', 'cut.e+', 'cut.proton'):
                field(key, 'Production cuts', 'Positive length in mm; requires a region in this volume.')
                self.fields[key].setProperty('i18nSource_toolTip', 'Positive length in mm; requires a region in this volume.')
            field('metadata', 'Metadata', 'metadata.<name> = value')
        self.setEnabled(False)

    @staticmethod
    def _text(widget):
        return (widget.currentText() if isinstance(widget, QComboBox) else
                widget.toPlainText() if isinstance(widget, QPlainTextEdit) else widget.text())

    def _changed(self, *_):
        if self._loading:
            return
        self._refresh_fields()
        self.changed.emit()

    def _refresh_fields(self):
        if self.kind == 'layer':
            return
        shape = self._text(self.fields['shape'])
        spec = solid_spec(shape)
        allowed = set(property_keys(shape))
        for key, edit in self.fields.items():
            if key.startswith('prop.'):
                visible = key[5:] in allowed or bool(self._text(edit).strip())
                edit.setVisible(visible)
                self._labels[key].setVisible(visible)
        params = ', '.join(f"{f['name']} ({f['dimension']})" for f in (spec or {}).get('parameters', []))
        if spec and spec['uses_size']:
            params = 'size: x, y, z (full lengths; mm)'
        self.hint.setText(params + ('\nparameter_counts: ' + str(spec['parameter_counts']) if spec and spec['parameter_counts'] else '') + ('\n' + ui_text('Experimental solid; backend validation is required.')
                                   if spec and spec['experimental'] else ''))
        self.fields['parameters'].setToolTip(params + '\nlength: mm; angle: rad (bare values), deg/rad explicit')

    def set_row(self, row):
        self._loading = True
        self._row = row
        self.setEnabled(row is not None)
        values = {}
        if row is not None:
            if self.kind != 'layer':
                boolean = self.kind == 'boolean'
                values.update(shape=row.tool_shape if boolean else row.shape,
                              size=row.tool_size if boolean else row.size,
                              parameters=row.tool_parameters if boolean else row.parameters)
                values.update({'prop.' + k: v for k, v in row.shape_properties.items()})
                if boolean:
                    values['name'] = row.name
                else:
                    values['copy_no'] = row.copy_no
                    values.update({k: v for k, v in row.preview_properties.items() if k in PLACEMENT_PROPERTY_KEYS})
            if self.kind != 'boolean':
                values.update(row.visual)
                values.update(row.production_cuts)
                values['metadata'] = row.metadata
        for key, edit in self.fields.items():
            text = values.get(key, '')
            if isinstance(edit, QComboBox):
                edit.setCurrentText(text)
            elif isinstance(edit, QPlainTextEdit):
                edit.setPlainText(text)
            else:
                edit.setText(text)
        self._refresh_fields()
        self._loading = False

    def apply_row(self, row):
        values = {key: self._text(widget) for key, widget in self.fields.items()}
        if self.kind != 'layer':
            if self.kind == 'boolean':
                row.tool_shape, row.tool_size, row.tool_parameters = values['shape'], values['size'], values['parameters']
                row.name = values['name']
            else:
                row.shape, row.size, row.parameters = values['shape'], values['size'], values['parameters']
                row.copy_no = values['copy_no']
                for key in PLACEMENT_PROPERTY_KEYS:
                    if values[key] != "":
                        row.preview_properties[key] = values[key]
                    else:
                        row.preview_properties.pop(key, None)
            # Preserve unknown fields from restored drafts so validation can block.
            for key in self.fields:
                if key.startswith('prop.'):
                    name = key[5:]
                    if values[key] != "":
                        row.shape_properties[name] = values[key]
                        if self.kind == 'volume': row.preview_properties.pop(name, None)
                    else:
                        row.shape_properties.pop(name, None)
                        if self.kind == 'volume': row.preview_properties.pop(name, None)
        if self.kind != 'boolean':
            for key in self.fields:
                target = row.visual if key.startswith('vis.') else row.production_cuts if key.startswith('cut.') else None
                if target is not None:
                    if values[key] != "": target[key] = values[key]
                    else: target.pop(key, None)
            row.metadata = values['metadata']

class GeometryEditor(QWidget):
    """Geometry tab: mode, source copy and the editors for each geometry template."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.volume_details = GeometryDetailsWidget('volume')
        self.boolean_details = GeometryDetailsWidget('boolean')
        self.layer_backend_details = GeometryDetailsWidget('layer')
        self.geometry_table = QTableWidget(0, 17)
        self.geometry_table.setHorizontalHeaderLabels(["enabled", "name", "parent", "shape", "material", "position", "size/parameters", "rotation", "sensitive", "bias", "region", "dx1", "dx2", "dy1", "dy2", "dz", "status"])
        set_table_minimum_rows(self.geometry_table, 8)
        self.geometry_count_label = QLabel("Volumes: 0 entries | Preview only")
        self.geometry_count_label.setWordWrap(True)
        self.add_volume_button = QPushButton("Add Volume")
        self.duplicate_volume_button = QPushButton("Duplicate Volume")
        self.delete_volume_button = QPushButton("Delete Volume")
        self.move_volume_up_button = QPushButton("Move Up")
        self.move_volume_down_button = QPushButton("Move Down")
        self.validate_geometry_button = QPushButton("Validate Geometry")
        self.revert_geometry_button = QPushButton("Revert Geometry")
        self.boolean_table = QTableWidget(0, 10)
        self.boolean_table.setHorizontalHeaderLabels(["enabled", "target", "index", "operation", "tool shape", "tool size", "tool parameters", "position", "rotation", "status"])
        set_table_minimum_rows(self.boolean_table, 8)
        self.boolean_count_label = QLabel("Boolean ops: 0 entries | Preview only")
        self.boolean_count_label.setWordWrap(True)
        self.add_boolean_button = QPushButton("Add Boolean Operation")
        self.duplicate_boolean_button = QPushButton("Duplicate Operation")
        self.delete_boolean_button = QPushButton("Delete Operation")
        self.move_boolean_up_button = QPushButton("Move Up")
        self.move_boolean_down_button = QPushButton("Move Down")
        self.validate_boolean_button = QPushButton("Validate Boolean Ops")
        self.geometry_editor_tabs = QTabWidget()
        self.geometry_mode_label = QLabel("Geometry editor: preview-only")
        self.geometry_mode_label.setWordWrap(True)
        self.geometry_source_copy = QCheckBox("Copy the original geometry file")
        self.geometry_source_copy.setToolTip(
            "Use the source geometry file unchanged in the run package; the Geometry Editor's validation is "
            "bypassed for it")
        self.simple_world_size = QLineEdit("10 cm, 10 cm, 10 cm")
        self.simple_world_material = QComboBox()
        self.simple_world_material.setEditable(True)
        self.simple_target_name = QLineEdit("Target")
        self.simple_target_shape = QComboBox()
        self.simple_target_shape.addItems(["box"])
        self.simple_target_size = QLineEdit("1 cm, 1 cm, 1 mm")
        self.simple_target_material = QComboBox()
        self.simple_target_material.setEditable(True)
        self.simple_target_position = QLineEdit("0 mm, 0 mm, 0 mm")
        self.simple_target_rotation = QLineEdit("0 deg, 0 deg, 0 deg")
        self.simple_target_sensitive = QCheckBox("Sensitive")
        self.simple_target_sensitive.setChecked(True)
        self.simple_target_bias = QCheckBox("Bias volume")
        self.simple_target_region = QLineEdit("SV")
        self.layered_world_size = QLineEdit("20 cm, 20 cm, 20 cm")
        self.layered_world_material = QComboBox()
        self.layered_world_material.setEditable(True)
        self.layered_axis = QComboBox()
        self.layered_axis.addItems(["z"])
        self.layered_gap = QLineEdit("0 um")
        self.layered_z_start = QLineEdit()
        self.layered_auto_stack = QCheckBox("Automatically stack layers")
        self.layered_auto_stack.setChecked(True)
        self.layer_table = QTableWidget(0, 8)
        self.layer_table.setHorizontalHeaderLabels(["enabled", "name", "material", "thickness", "xy", "sensitive", "bias", "region"])
        set_table_minimum_rows(self.layer_table, 6)
        self.add_layer_button = QPushButton("Add Layer")
        self.duplicate_layer_button = QPushButton("Duplicate")
        self.delete_layer_button = QPushButton("Delete")
        self.move_layer_up_button = QPushButton("Up")
        self.move_layer_down_button = QPushButton("Down")
        self.layer_enabled = QCheckBox("Enabled")
        self.layer_name = QLineEdit()
        self.layer_material = QComboBox()
        self.layer_material.setEditable(True)
        self.layer_thickness = QLineEdit()
        self.layer_xy = QLineEdit()
        self.layer_sensitive = QCheckBox("Sensitive")
        self.layer_bias = QCheckBox("Bias volume")
        self.layer_region = QLineEdit()
        self.layer_copy_no = QLineEdit()
        self.layer_position = QLineEdit()
        self.layer_rotation = QLineEdit()
        self.layer_status = QPlainTextEdit()
        self.layer_status.setReadOnly(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.geometry_mode_label)
        layout.addWidget(self.geometry_source_copy)
        self.geometry_editor_tabs.addTab(self._simple_box_editor_tab(), "Simple Box")
        self.geometry_editor_tabs.addTab(self._layered_device_editor_tab(), "Layered Device")
        self.geometry_editor_tabs.addTab(self._hierarchical_editor_tab(), "Hierarchical Volumes")
        self.geometry_editor_tabs.addTab(self._boolean_editor_tab(), "Boolean Operations")
        self.geometry_editor_tabs.addTab(self._geometry_preview_tab(), "Preview / Unsupported Template")
        layout.addWidget(self.geometry_editor_tabs, 1)

    def _simple_box_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(create_hint_label("Generates a SimpleBoxTemplate geometry.ini with [world] and [target]."))
        form = QFormLayout()
        form.addRow("World size", self.simple_world_size)
        form.addRow("World material", self.simple_world_material)
        form.addRow("Target name", self.simple_target_name)
        form.addRow("Target shape", self.simple_target_shape)
        form.addRow("Target size", self.simple_target_size)
        form.addRow("Target material", self.simple_target_material)
        form.addRow("Target position", self.simple_target_position)
        form.addRow("Target rotation", self.simple_target_rotation)
        form.addRow("", self.simple_target_sensitive)
        form.addRow("", self.simple_target_bias)
        form.addRow("Target region", self.simple_target_region)
        layout.addLayout(form)
        layout.addStretch(1)
        return tab

    def _layered_device_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(create_hint_label("Generates a LayeredDeviceTemplate geometry.ini. The C++ template currently supports axis=z only."))
        form = QFormLayout()
        form.addRow("World size", self.layered_world_size)
        form.addRow("World material", self.layered_world_material)
        form.addRow("Stacking axis", self.layered_axis)
        form.addRow("Gap", self.layered_gap)
        form.addRow("z_start", self.layered_z_start)
        form.addRow("", self.layered_auto_stack)
        layout.addLayout(form)
        toolbar = QHBoxLayout()
        for button in [
            self.add_layer_button,
            self.duplicate_layer_button,
            self.delete_layer_button,
            self.move_layer_up_button,
            self.move_layer_down_button,
        ]:
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        layout.addWidget(self.layer_table, 2)
        detail = QGroupBox("Selected layer")
        detail_form = QFormLayout(detail)
        detail_form.addRow("", self.layer_enabled)
        detail_form.addRow("Name", self.layer_name)
        detail_form.addRow("Material", self.layer_material)
        detail_form.addRow("Thickness", self.layer_thickness)
        detail_form.addRow("XY size", self.layer_xy)
        detail_form.addRow("", self.layer_sensitive)
        detail_form.addRow("", self.layer_bias)
        detail_form.addRow("Region", self.layer_region)
        detail_form.addRow("copyNo", self.layer_copy_no)
        detail_form.addRow("Position (manual stacking)", self.layer_position)
        detail_form.addRow("Rotation", self.layer_rotation)
        layout.addWidget(detail)
        layout.addWidget(QLabel("Layer validation"))
        layout.addWidget(self.layer_backend_details)
        layout.addWidget(self.layer_status, 1)
        return tab

    def _hierarchical_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(create_hint_label("Edits generic [world] and [volume.*] sections. Disabled rows stay in the GUI but are not generated."))
        toolbar = toolbar_grid([
            self.add_volume_button,
            self.duplicate_volume_button,
            self.delete_volume_button,
            self.move_volume_up_button,
            self.move_volume_down_button,
            self.validate_geometry_button,
            self.revert_geometry_button,
        ], 4)
        layout.addLayout(toolbar)
        layout.addWidget(self.geometry_count_label)
        layout.addWidget(self.geometry_table, 1)
        layout.addWidget(self.volume_details)
        return tab

    def _boolean_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(create_hint_label("Boolean tools are solid operands, not volumes. They do not have material/sensitive/bias state. Writer renumbers enabled ops per target."))
        toolbar = toolbar_grid([
            self.add_boolean_button,
            self.duplicate_boolean_button,
            self.delete_boolean_button,
            self.move_boolean_up_button,
            self.move_boolean_down_button,
            self.validate_boolean_button,
        ], 3)
        layout.addLayout(toolbar)
        layout.addWidget(self.boolean_count_label)
        layout.addWidget(self.boolean_table, 1)
        layout.addWidget(self.boolean_details)
        return tab

    def _geometry_preview_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(create_hint_label("Unsupported templates are preview-only and are copied unchanged unless the mode is switched to an editable template. Parsed volume/boolean rows are shown in the Hierarchical and Boolean tabs."))
        layout.addWidget(self.geometry_count_label)
        layout.addWidget(self.boolean_count_label)
        layout.addStretch(1)
        return tab


class GeometryMixin:
    """Geometry logic; mixed into ConfigBuilderPage, which holds the documents."""

    def _connect_geometry_signals(self) -> None:
        """Geometry tab fields, tables and buttons."""
        for widget in [
            self.simple_world_size,
            self.simple_target_name,
            self.simple_target_size,
            self.simple_target_position,
            self.simple_target_rotation,
            self.simple_target_region,
            self.layered_world_size,
            self.layered_gap,
            self.layered_z_start,
            self.layer_name,
            self.layer_thickness,
            self.layer_xy,
            self.layer_region,
            self.layer_copy_no,
            self.layer_position,
            self.layer_rotation,
        ]:
            widget.textEdited.connect(self._update_geometry_from_widgets)
        for combo in [
            self.simple_world_material,
            self.simple_target_shape,
            self.simple_target_material,
            self.layered_world_material,
            self.layered_axis,
            self.layer_material,
        ]:
            combo.currentTextChanged.connect(self._update_geometry_from_widgets)
        for widget in [
            self.simple_target_sensitive,
            self.simple_target_bias,
            self.layer_enabled,
            self.layer_sensitive,
            self.layer_bias,
            self.layered_auto_stack,
        ]:
            widget.stateChanged.connect(self._update_geometry_from_widgets)
        self.layer_table.itemSelectionChanged.connect(self._on_layer_selection_changed)
        self.add_layer_button.clicked.connect(self._add_layer)
        self.duplicate_layer_button.clicked.connect(self._duplicate_layer)
        self.delete_layer_button.clicked.connect(self._delete_layer)
        self.move_layer_up_button.clicked.connect(lambda: self._move_layer(-1))
        self.move_layer_down_button.clicked.connect(lambda: self._move_layer(1))
        self.geometry_table.itemSelectionChanged.connect(self._select_geometry_details)
        self.boolean_table.itemSelectionChanged.connect(self._select_boolean_details)
        self.volume_details.changed.connect(self._on_volume_details_changed)
        self.boolean_details.changed.connect(self._on_boolean_details_changed)
        self.layer_backend_details.changed.connect(self._on_layer_backend_details_changed)
        self.geometry_table.itemChanged.connect(self._on_hierarchical_table_changed)
        self.boolean_table.itemChanged.connect(self._on_boolean_table_changed)
        self.add_volume_button.clicked.connect(self._add_hierarchical_volume)
        self.duplicate_volume_button.clicked.connect(self._duplicate_hierarchical_volume)
        self.delete_volume_button.clicked.connect(self._delete_hierarchical_volume)
        self.move_volume_up_button.clicked.connect(lambda: self._move_hierarchical_volume(-1))
        self.move_volume_down_button.clicked.connect(lambda: self._move_hierarchical_volume(1))
        self.validate_geometry_button.clicked.connect(self._validate_geometry_editor)
        self.revert_geometry_button.clicked.connect(self.reload_geometry)
        self.add_boolean_button.clicked.connect(self._add_boolean_op)
        self.duplicate_boolean_button.clicked.connect(self._duplicate_boolean_op)
        self.delete_boolean_button.clicked.connect(self._delete_boolean_op)
        self.move_boolean_up_button.clicked.connect(lambda: self._move_boolean_op(-1))
        self.move_boolean_down_button.clicked.connect(lambda: self._move_boolean_op(1))
        self.validate_boolean_button.clicked.connect(self._validate_geometry_editor)
        self.geometry_source_copy.toggled.connect(self._on_geometry_source_copy_toggled)

    def reload_geometry(self) -> None:
        path = self.geometry_config.text().strip()
        template = self._geometry_template_token()
        # No source is a legitimate in-memory document. Do not project defaults,
        # clear tables, flush pending editors or manufacture an empty read receipt.
        if not path:
            message = ("This geometry document is in memory; Reload/Revert needs a source file. Your edits are retained."
                       if not self.geometry_document.source_path else
                       "The imported geometry still requires its source path. Your edits are retained.")
            self.geometry_messages.setPlainText(ui_text(message))
            return
        candidate = parse_geometry(path, template)
        if not getattr(candidate, "_f4_read_success", False):
            # Failed reads are current errors, never successful empty geometry.
            # Keep the model and pending widgets so an IO error cannot erase edits.
            self.geometry_summary = candidate
            self.geometry_document.source_errors = list(dict.fromkeys(
                [*self.geometry_document.source_errors, *candidate.errors]))
            self.geometry_document._f4_source_diagnostics = collect_diagnostics(candidate)
            self.geometry_document._f4_source_snapshot = getattr(candidate, "_f4_source_snapshot", None)
            self.geometry_messages.setPlainText(self._messages_text(candidate.errors, candidate.warnings))
            self._validate_geometry_editor()
            self._update_generated_geometry_preview()
            return
        self.geometry_summary = candidate
        self.geometry_summary._f5_source_anchor = str(Path(path).expanduser().resolve())
        self.geometry_table.setRowCount(0)
        self.boolean_table.setRowCount(0)
        self.geometry_messages.clear()
        self.geometry_raw.clear()
        self.geometry_document = geometry_document_from_summary(self.geometry_summary, template)
        self.geometry_document.source_path = self.geometry_summary._f5_source_anchor
        self.geometry_document.is_dirty = False
        self._populate_hierarchical_tables()
        self.geometry_messages.setPlainText(self._messages_text(self.geometry_summary.errors, self.geometry_summary.warnings))
        self.geometry_raw.setPlainText(self._preview_text(self.geometry_summary.raw_text))
        self.geometry_count_label.setText(
            f"Volumes: {len(self.geometry_summary.volumes)} entries | "
            f"{len(self.geometry_summary.errors)} errors, {len(self.geometry_summary.warnings)} warnings | Preview only"
        )
        self.boolean_count_label.setText(f"Boolean ops: {len(self.geometry_summary.boolean_ops)} entries | Preview only")
        self._populate_geometry_editor()
        self._populate_material_editor()
        self._update_workspace_summary()

    @edit_operation('Change geometry mode')
    def _on_geometry_template_changed(self) -> None:
        if self._building:
            return
        set_geometry_mode(self.geometry_document, self._geometry_template_token())
        if self.geometry_document.mode in HIERARCHICAL_GEOMETRY_MODES and not self.geometry_document.volumes:
            self.geometry_document.volumes.append(
                HierarchicalVolumeRow(name="world", shape="box", size="10 cm,10 cm,10 cm", material="G4_AIR", position="0 mm,0 mm,0 mm", rotation="0 deg,0 deg,0 deg")
            )
        self._apply_geometry_mode_to_tabs()
        self._populate_hierarchical_tables()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._update_workspace_summary()
        self._emit_changed()

    def _apply_geometry_mode_to_tabs(self) -> None:
        mode = self.geometry_document.mode
        editable = mode in EDITABLE_GEOMETRY_MODES and not self.geometry_document.source_copy_mode
        label = {
            "simple_box": "Geometry editor: Simple Box mode. Package generation will write a new geometry.ini when dirty.",
            "layered_device": "Geometry editor: Layered Device mode. Package generation will write a new geometry.ini when dirty.",
            "hierarchical": "Geometry editor: Hierarchical mode. Package generation writes [world] and [volume.*] sections when dirty.",
            "hierarchical_boolean": "Geometry editor: Hierarchical Boolean mode. Boolean tools are generated as [volume.<target>.boolean.<index>] sections.",
            "boolean_hierarchical": "Geometry editor: Hierarchical Boolean mode. Boolean tools are generated as [volume.<target>.boolean.<index>] sections.",
            "boolean": "Geometry editor: Boolean mode using hierarchical volumes plus boolean operations.",
            "preview_only": "Geometry editor: preview-only. Unsupported templates are copied unchanged.",
        }.get(mode, "Geometry editor: preview-only.")
        self.geometry_mode_label.setText(label)
        current = 0 if mode == "simple_box" else 1 if mode == "layered_device" else 2 if mode in HIERARCHICAL_GEOMETRY_MODES else 4
        self.geometry_editor_tabs.setCurrentIndex(current)
        self.geometry_editor_tabs.setTabEnabled(0, editable and mode == "simple_box")
        self.geometry_editor_tabs.setTabEnabled(1, editable and mode == "layered_device")
        self.geometry_editor_tabs.setTabEnabled(2, editable and mode in HIERARCHICAL_GEOMETRY_MODES)
        self.geometry_editor_tabs.setTabEnabled(3, editable and mode in HIERARCHICAL_GEOMETRY_MODES)

    @edit_operation('Change source-copy mode')
    def _on_geometry_source_copy_toggled(self, checked: bool) -> None:
        if self._building:
            return
        self.geometry_document.source_copy_mode = checked
        self._apply_geometry_mode_to_tabs()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._update_workspace_summary()
        self._emit_changed()

    def _populate_geometry_editor(self) -> None:
        self._building = True
        self.geometry_source_copy.setChecked(self.geometry_document.source_copy_mode)
        self._apply_material_candidates()
        simple = self.geometry_document.simple_box
        self.simple_world_size.setText(simple.world_size)
        self._set_combo_text(self.simple_world_material, simple.world_material)
        self.simple_target_name.setText(simple.target_name)
        self._set_combo_text(self.simple_target_shape, simple.target_shape)
        self.simple_target_size.setText(simple.target_size)
        self._set_combo_text(self.simple_target_material, simple.target_material)
        self.simple_target_position.setText(simple.target_position)
        self.simple_target_rotation.setText(simple.target_rotation)
        self.simple_target_sensitive.setChecked(simple.target_sensitive)
        self.simple_target_bias.setChecked(simple.target_bias)
        self.simple_target_region.setText(simple.target_region)

        layered = self.geometry_document.layered_device
        self.layered_world_size.setText(layered.world_size)
        self._set_combo_text(self.layered_world_material, layered.world_material)
        self._set_combo_text(self.layered_axis, layered.axis)
        self.layered_gap.setText(layered.gap)
        self.layered_z_start.setText(layered.z_start)
        self.layered_auto_stack.setChecked(layered.auto_stack)
        self._building = False
        self._populate_layers_table()
        self._populate_hierarchical_tables()
        self._apply_geometry_mode_to_tabs()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()

    def _populate_hierarchical_tables(self) -> None:
        volume_index = self.geometry_table.currentRow()
        boolean_index = self.boolean_table.currentRow()
        self._building = True
        self.geometry_table.setRowCount(0)
        for volume in self.geometry_document.volumes:
            row = self.geometry_table.rowCount()
            self.geometry_table.insertRow(row)
            size_or_parameters = volume.parameters if volume.shape.strip().lower() != "box" and volume.parameters else volume.size
            status = self._row_status(volume.errors, volume.warnings)
            values = [
                "true" if volume.enabled else "false",
                volume.name,
                volume.parent,
                volume.shape,
                volume.material,
                volume.position,
                size_or_parameters,
                volume.rotation,
                "true" if volume.sensitive else "false",
                "true" if volume.bias else "false",
                volume.region,
                volume.shape_properties.get("dx1", ""),
                volume.shape_properties.get("dx2", ""),
                volume.shape_properties.get("dy1", ""),
                volume.shape_properties.get("dy2", ""),
                volume.shape_properties.get("dz", ""),
                status,
            ]
            for col, value in enumerate(values):
                self.geometry_table.setItem(row, col, QTableWidgetItem(value))
        self.geometry_table.resizeColumnsToContents()

        self.boolean_table.setRowCount(0)
        for op in self.geometry_document.boolean_ops:
            row = self.boolean_table.rowCount()
            self.boolean_table.insertRow(row)
            status = self._row_status(op.errors, op.warnings)
            values = [
                "true" if op.enabled else "false",
                op.target_volume,
                str(op.index),
                op.operation,
                op.tool_shape,
                op.tool_size,
                op.tool_parameters,
                op.position,
                op.rotation,
                status,
            ]
            for col, value in enumerate(values):
                self.boolean_table.setItem(row, col, QTableWidgetItem(value))
        self.boolean_table.resizeColumnsToContents()
        self._building = False
        self._update_hierarchical_count_labels()
        if self.geometry_table.rowCount():
            self.geometry_table.selectRow(min(max(volume_index, 0), self.geometry_table.rowCount()-1))
        if self.boolean_table.rowCount():
            self.boolean_table.selectRow(min(max(boolean_index, 0), self.boolean_table.rowCount()-1))
        self._select_geometry_details()
        self._select_boolean_details()

    def _update_geometry_from_widgets(self) -> None:
        if self._building:
            return
        simple = self.geometry_document.simple_box
        simple.world_size = self.simple_world_size.text().strip()
        simple.world_material = self.simple_world_material.currentText().strip()
        simple.target_name = self.simple_target_name.text().strip()
        simple.target_shape = self.simple_target_shape.currentText().strip()
        simple.target_size = self.simple_target_size.text().strip()
        simple.target_material = self.simple_target_material.currentText().strip()
        simple.target_position = self.simple_target_position.text().strip()
        simple.target_rotation = self.simple_target_rotation.text().strip()
        simple.target_sensitive = self.simple_target_sensitive.isChecked()
        simple.target_bias = self.simple_target_bias.isChecked()
        simple.target_region = self.simple_target_region.text().strip()

        layered = self.geometry_document.layered_device
        layered.world_size = self.layered_world_size.text().strip()
        layered.world_material = self.layered_world_material.currentText().strip()
        layered.axis = self.layered_axis.currentText().strip()
        layered.gap = self.layered_gap.text().strip()
        layered.z_start = self.layered_z_start.text().strip()
        layered.auto_stack = self.layered_auto_stack.isChecked()
        self._update_selected_layer_from_detail()
        self.geometry_document.is_dirty = self.geometry_document.mode in EDITABLE_GEOMETRY_MODES
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._update_workspace_summary()
        self._emit_changed()

    def _on_hierarchical_table_changed(self, item: QTableWidgetItem) -> None:
        if self._building:
            return
        row = item.row()
        if row < 0 or row >= len(self.geometry_document.volumes):
            return
        volume = self.geometry_document.volumes[row]
        values = [self._table_text(self.geometry_table, row, col) for col in range(self.geometry_table.columnCount())]
        volume.enabled = self._as_bool(values[0])
        volume.name = values[1]
        volume.parent = values[2]
        volume.shape = values[3] or "box"
        volume.material = values[4]
        volume.position = values[5]
        if canonical_solid(volume.shape) == "box":
            volume.size = values[6]
        else:
            volume.parameters = values[6]
        volume.rotation = values[7]
        volume.sensitive = self._as_bool(values[8])
        volume.bias = self._as_bool(values[9])
        volume.region = values[10]
        for field, value in zip(("dx1", "dx2", "dy1", "dy2", "dz"), values[11:16]):
            if value:
                volume.shape_properties[field] = value
            else:
                volume.shape_properties.pop(field, None)
        self._select_geometry_details()
        self._mark_geometry_dirty()


    def _mark_geometry_dirty(self) -> None:
        self.geometry_document.is_dirty = self.geometry_document.mode in EDITABLE_GEOMETRY_MODES
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._update_workspace_summary()
        self._emit_changed()

    @edit_operation('Add volume')
    def _add_hierarchical_volume(self) -> None:
        existing = {volume.name for volume in self.geometry_document.volumes}
        name = self._unique_name("Volume", existing)
        parent = "world" if any(volume.name.lower() == "world" for volume in self.geometry_document.volumes) else ""
        self.geometry_document.volumes.append(
            HierarchicalVolumeRow(name=name, parent=parent, shape="box", size="1 mm,1 mm,1 mm", material="G4_Si", position="0 mm,0 mm,0 mm", rotation="0 deg,0 deg,0 deg")
        )
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()

    @edit_operation('Duplicate volume')
    def _duplicate_hierarchical_volume(self) -> None:
        row = self.geometry_table.currentRow()
        if row < 0 or row >= len(self.geometry_document.volumes):
            return
        source = self.geometry_document.volumes[row]
        duplicate = copy.deepcopy(source)
        duplicate.name = self._unique_name(f"{source.name}_copy", {volume.name for volume in self.geometry_document.volumes})
        duplicate.errors = []
        duplicate.warnings = []
        self.geometry_document.volumes.insert(row + 1, duplicate)
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()
        self.geometry_table.selectRow(row + 1)

    @edit_operation('Delete volume')
    def _delete_hierarchical_volume(self) -> None:
        row = self.geometry_table.currentRow()
        if row < 0 or row >= len(self.geometry_document.volumes):
            return
        if self.geometry_document.volumes[row].name.strip().lower() == "world":
            self.geometry_document.warnings.append("World volume was not deleted.")
            self._validate_geometry_editor()
            return
        del self.geometry_document.volumes[row]
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()

    @edit_operation('Move volume')
    def _move_hierarchical_volume(self, direction: int) -> None:
        row = self.geometry_table.currentRow()
        target = row + direction
        rows = self.geometry_document.volumes
        if row < 0 or target < 0 or row >= len(rows) or target >= len(rows):
            return
        rows[row], rows[target] = rows[target], rows[row]
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()
        self.geometry_table.selectRow(target)


    def _first_non_world_volume_name(self) -> str:
        for volume in self.geometry_document.volumes:
            if volume.enabled and volume.name.strip().lower() != "world":
                return volume.name.strip()
        return self.geometry_document.volumes[0].name.strip() if self.geometry_document.volumes else ""


    def _validate_geometry_editor(self) -> None:
        material_names = {row.name for row in self.material_document.rows if row.enabled and row.name}
        validate_geometry_document(
            self.geometry_document,
            material_names=material_names,
            scoring_hits_enabled=self.scoring_editor.hits,
            physics_biasing_enabled=self.physics_editor.enable_biasing_physics,
        )
        self.layer_status.setPlainText(self._messages_text(self.geometry_document.errors, self.geometry_document.warnings))
        self.geometry_messages.setPlainText(self._messages_text(self.geometry_document.errors, self.geometry_document.warnings))
        self._refresh_hierarchical_status_columns()
        self._update_hierarchical_count_labels()

    def _refresh_hierarchical_status_columns(self) -> None:
        self._building = True
        for row, volume in enumerate(self.geometry_document.volumes):
            if row < self.geometry_table.rowCount():
                self.geometry_table.setItem(row, 16, QTableWidgetItem(self._row_status(volume.errors, volume.warnings)))
        for row, op in enumerate(self.geometry_document.boolean_ops):
            if row < self.boolean_table.rowCount():
                self.boolean_table.setItem(row, 9, QTableWidgetItem(self._row_status(op.errors, op.warnings)))
        self._building = False

    def _update_hierarchical_count_labels(self) -> None:
        volume_errors = sum(len(volume.errors) for volume in self.geometry_document.volumes)
        volume_warnings = sum(len(volume.warnings) for volume in self.geometry_document.volumes)
        boolean_errors = sum(len(op.errors) for op in self.geometry_document.boolean_ops)
        boolean_warnings = sum(len(op.warnings) for op in self.geometry_document.boolean_ops)
        mode_text = ui_text("editable" if self.geometry_document.mode in HIERARCHICAL_GEOMETRY_MODES else "preview")
        self.geometry_count_label.setText(
            ui_format(
                "Volumes: {count} rows, {enabled} enabled | {errors} errors, {warnings} warnings | {mode}",
                count=len(self.geometry_document.volumes),
                enabled=sum(1 for volume in self.geometry_document.volumes if volume.enabled),
                errors=volume_errors,
                warnings=volume_warnings,
                mode=mode_text,
            )
        )
        self.boolean_count_label.setText(
            ui_format(
                "Boolean ops: {count} rows, {enabled} enabled | {errors} errors, {warnings} warnings | {mode}",
                count=len(self.geometry_document.boolean_ops),
                enabled=sum(1 for op in self.geometry_document.boolean_ops if op.enabled),
                errors=boolean_errors,
                warnings=boolean_warnings,
                mode=mode_text,
            )
        )

    def _update_generated_geometry_preview(self) -> None:
        if self.geometry_document.mode not in EDITABLE_GEOMETRY_MODES:
            self.generated_geometry_raw.setPlainText("Preview-only template. Package writer will copy source geometry.ini unchanged.")
            return
        try:
            self.generated_geometry_raw.setPlainText(generate_geometry_ini_text(self.geometry_document))
        except Exception as exc:  # noqa: BLE001
            self.generated_geometry_raw.setPlainText(f"Generated geometry preview unavailable:\n{exc}")

    def select_geometry_row(self, name: str) -> None:
        """Select the volume table row of a volume picked in the 3D view (without switching tabs)."""
        target = name.strip().lower()
        self.geometry_table.blockSignals(True)
        self.geometry_table.clearSelection()
        for row in range(self.geometry_table.rowCount()):
            item = self.geometry_table.item(row, 1)
            if target and item is not None and item.text().strip().lower() == target:
                self.geometry_table.selectRow(row)
                break
        self.geometry_table.blockSignals(False)
        self._select_geometry_details()

    def _on_geometry_row_selected(self) -> None:
        rows = {index.row() for index in self.geometry_table.selectedIndexes()}
        item = self.geometry_table.item(min(rows), 1) if rows else None
        self.preview3d_widget.select_volume(item.text().strip() if item is not None else "")

    def _select_geometry_details(self) -> None:
        if self._building: return
        index = self.geometry_table.currentRow()
        rows = self.geometry_document.volumes
        self.volume_details.set_row(rows[index] if 0 <= index < len(rows) else None)

    def _select_boolean_details(self) -> None:
        if self._building: return
        index = self.boolean_table.currentRow()
        rows = self.geometry_document.boolean_ops
        self.boolean_details.set_row(rows[index] if 0 <= index < len(rows) else None)

    @edit_operation('Edit volume details')
    def _on_volume_details_changed(self) -> None:
        if self._building: return
        index = self.geometry_table.currentRow()
        if not 0 <= index < len(self.geometry_document.volumes): return
        self.volume_details.apply_row(self.geometry_document.volumes[index])
        self._mark_geometry_dirty()
        self._sync_details_table(index, boolean=False)

    @edit_operation('Edit boolean tool details')
    def _on_boolean_details_changed(self) -> None:
        if self._building: return
        index = self.boolean_table.currentRow()
        if not 0 <= index < len(self.geometry_document.boolean_ops): return
        self.boolean_details.apply_row(self.geometry_document.boolean_ops[index])
        self._mark_geometry_dirty()
        self._sync_details_table(index, boolean=True)

    @edit_operation('Edit layer backend details')
    def _on_layer_backend_details_changed(self) -> None:
        if self._building: return
        index = self._selected_layer_row
        rows = self.geometry_document.layered_device.layers
        if not 0 <= index < len(rows): return
        self.layer_backend_details.apply_row(rows[index])
        self._mark_geometry_dirty()

    def _sync_details_table(self, index: int, *, boolean: bool) -> None:
        previous = self._building
        self._building = True
        try:
            if boolean:
                row = self.geometry_document.boolean_ops[index]
                table = self.boolean_table
                fields = {4: row.tool_shape, 5: row.tool_size, 6: row.tool_parameters}
            else:
                row = self.geometry_document.volumes[index]
                table = self.geometry_table
                fields = {3: row.shape, 6: row.size if canonical_solid(row.shape) == 'box' else row.parameters}
                fields.update({col: row.shape_properties.get(key, '')
                               for col, key in enumerate(('dx1','dx2','dy1','dy2','dz'), 11)})
            for col, value in fields.items():
                item = table.item(index, col)
                if item is not None: item.setText(value)
        finally:
            self._building = previous
