"""Geometry editor: its widget (the Geometry tab) and its logic on the Configuration page."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text
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


class GeometryEditor(QWidget):
    """Geometry tab: mode, source copy and the editors for each geometry template."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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
        self.geometry_summary = parse_geometry(path, template) if path else None
        self.geometry_table.setRowCount(0)
        self.boolean_table.setRowCount(0)
        self.geometry_messages.clear()
        self.geometry_raw.clear()
        if not self.geometry_summary:
            self.geometry_document = GeometryDocument()
            set_geometry_mode(self.geometry_document, template)
            self._populate_geometry_editor()
            self.geometry_count_label.setText("Volumes: 0 entries | Preview only")
            self.boolean_count_label.setText("Boolean ops: 0 entries | Preview only")
            self._update_workspace_summary()
            return
        self.geometry_document = geometry_document_from_summary(self.geometry_summary, template)
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
        if volume.shape.strip().lower() == "box":
            volume.size = values[6]
            volume.parameters = ""
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
        self._mark_geometry_dirty()


    def _mark_geometry_dirty(self) -> None:
        self.geometry_document.is_dirty = self.geometry_document.mode in EDITABLE_GEOMETRY_MODES
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._update_workspace_summary()
        self._emit_changed()

    def _add_hierarchical_volume(self) -> None:
        existing = {volume.name for volume in self.geometry_document.volumes}
        name = self._unique_name("Volume", existing)
        parent = "world" if any(volume.name.lower() == "world" for volume in self.geometry_document.volumes) else ""
        self.geometry_document.volumes.append(
            HierarchicalVolumeRow(name=name, parent=parent, shape="box", size="1 mm,1 mm,1 mm", material="G4_Si", position="0 mm,0 mm,0 mm", rotation="0 deg,0 deg,0 deg")
        )
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()

    def _duplicate_hierarchical_volume(self) -> None:
        row = self.geometry_table.currentRow()
        if row < 0 or row >= len(self.geometry_document.volumes):
            return
        source = self.geometry_document.volumes[row]
        duplicate = HierarchicalVolumeRow(**{k: v for k, v in source.__dict__.items() if k in HierarchicalVolumeRow.__dataclass_fields__})
        duplicate.name = self._unique_name(f"{source.name}_copy", {volume.name for volume in self.geometry_document.volumes})
        duplicate.errors = []
        duplicate.warnings = []
        self.geometry_document.volumes.insert(row + 1, duplicate)
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()
        self.geometry_table.selectRow(row + 1)

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

    def _on_geometry_row_selected(self) -> None:
        rows = {index.row() for index in self.geometry_table.selectedIndexes()}
        item = self.geometry_table.item(min(rows), 1) if rows else None
        self.preview3d_widget.select_volume(item.text().strip() if item is not None else "")
