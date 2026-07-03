from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.project import G4USimProject
from g4usim_gui.editors.geometry_editor_model import (
    BooleanOperationRow,
    GeometryDocument,
    HierarchicalVolumeRow,
    HIERARCHICAL_GEOMETRY_MODES,
    LayerRow,
    EDITABLE_GEOMETRY_MODES,
    geometry_document_from_summary,
    geometry_material_refs,
    set_geometry_mode,
    validate_geometry_document,
)
from g4usim_gui.editors.material_editor_model import (
    MaterialDocument,
    add_default_row,
    delete_row,
    duplicate_row,
    generate_materials_ini_text,
    material_document_from_summary,
    validate_material_document,
)
from g4usim_gui.editors.source_physics_scoring_model import (
    PhysicsEditableModel,
    REFERENCE_LIST_CANDIDATES,
    ScoringEditableModel,
    SourceEditableModel,
    SOURCE_PRESETS,
    validate_physics_model,
    validate_scoring_model,
    validate_source_model,
)
from g4usim_gui.models.package_model import GeometrySettings, PathSettings, RunPackage
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.parsers.geometry_parser import GeometrySummary, parse_geometry
from g4usim_gui.parsers.materials_parser import NIST_QUICK_LIST, MaterialsSummary, parse_materials
from g4usim_gui.preview3d.fallback_preview_widget import FallbackPreviewWidget
from g4usim_gui.preview3d.pyvista_preview_widget import PyVistaPreviewWidget, pyvista_available
from g4usim_gui.preview3d.scene_builder import build_preview_scene
from g4usim_gui.preview3d.scene_model import PreviewScene
from g4usim_gui.validators.config_validator import ValidationReport, validate_config_builder
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.writers.main_ini_writer import build_main_ini_text
from g4usim_gui.widgets.ui_helpers import (
    create_hint_label,
    make_path_row,
    set_table_compact_readonly,
    set_table_minimum_rows,
)


class ConfigBuilderPage(QWidget):
    validateRequested = Signal()
    generatePackageRequested = Signal(bool)
    settingsChanged = Signal()

    GEOMETRY_TEMPLATES = ["simple_box", "layered_device", "hierarchical", "boolean_hierarchical", "array", "shielding"]
    SOURCE_PRESETS = ["proton_beam", "mono_proton", "neutron_beam", "gamma_beam", "isotropic_neutron", "plane_proton_beam"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._building = False
        self.materials_summary: MaterialsSummary | None = None
        self.geometry_summary: GeometrySummary | None = None
        self.material_document = MaterialDocument()
        self.source_editor = SourceEditableModel()
        self.physics_editor = PhysicsEditableModel()
        self.scoring_editor = ScoringEditableModel()
        self._selected_material_row = -1

        self.run_name = QLineEdit("gui_run")
        self.threads = QSpinBox()
        self.threads.setRange(1, 1024)
        self.threads.setValue(1)
        self.seed = QLineEdit("12345")
        self.beam_on = QSpinBox()
        self.beam_on.setRange(0, 2_000_000_000)
        self.beam_on.setValue(100)
        self.check_overlaps = QCheckBox()
        self.check_overlaps.setChecked(True)
        self.dry_run = QCheckBox()

        self.materials_config = QLineEdit()
        self.geometry_config = QLineEdit()
        self.geometry_template = QComboBox()
        self.geometry_template.addItems(self.GEOMETRY_TEMPLATES)
        self.reload_materials_button = QPushButton("Reload materials")
        self.reload_geometry_button = QPushButton("Reload geometry")

        self.materials_table = QTableWidget(0, 6)
        self.materials_table.setHorizontalHeaderLabels(["enabled", "name", "mode", "density", "components", "status"])
        set_table_compact_readonly(self.materials_table)
        set_table_minimum_rows(self.materials_table, 8)
        self.materials_count_label = QLabel("Materials: 0 entries | Preview only")
        self.load_materials_editor_button = QPushButton("Load from selected materials.ini")
        self.add_nist_button = QPushButton("Add NIST")
        self.add_mass_button = QPushButton("Add mass_fraction")
        self.add_volume_button = QPushButton("Add volume_fraction")
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
        self.materials_messages = QPlainTextEdit()
        self.materials_messages.setReadOnly(True)
        self.materials_raw = QPlainTextEdit()
        self.materials_raw.setReadOnly(True)
        self.generated_materials_raw = QPlainTextEdit()
        self.generated_materials_raw.setReadOnly(True)
        self.nist_table = QTableWidget(0, 1)
        self.nist_table.setHorizontalHeaderLabels(["common NIST names"])
        set_table_compact_readonly(self.nist_table)
        set_table_minimum_rows(self.nist_table, 8)
        self.nist_table.itemClicked.connect(lambda item: QApplication.clipboard().setText(item.text()))

        self.geometry_table = QTableWidget(0, 12)
        self.geometry_table.setHorizontalHeaderLabels(["enabled", "name", "parent", "shape", "material", "position", "size/parameters", "rotation", "sensitive", "bias", "region", "status"])
        set_table_minimum_rows(self.geometry_table, 8)
        self.geometry_count_label = QLabel("Volumes: 0 entries | Preview only")
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
        self.add_boolean_button = QPushButton("Add Boolean Operation")
        self.duplicate_boolean_button = QPushButton("Duplicate Operation")
        self.delete_boolean_button = QPushButton("Delete Operation")
        self.move_boolean_up_button = QPushButton("Move Up")
        self.move_boolean_down_button = QPushButton("Move Down")
        self.validate_boolean_button = QPushButton("Validate Boolean Ops")
        self.geometry_messages = QPlainTextEdit()
        self.geometry_messages.setReadOnly(True)
        self.geometry_raw = QPlainTextEdit()
        self.geometry_raw.setReadOnly(True)
        self.generated_geometry_raw = QPlainTextEdit()
        self.generated_geometry_raw.setReadOnly(True)
        self.preview3d_refresh_button = QPushButton("Refresh Preview")
        self.preview3d_reset_button = QPushButton("Reset Camera")
        self.preview3d_show_source = QCheckBox("Show Source")
        self.preview3d_show_source.setChecked(True)
        self.preview3d_show_labels = QCheckBox("Show Labels")
        self.preview3d_show_labels.setChecked(True)
        self.preview3d_status = QLabel("3D Preview: stale")
        self.preview3d_status.setWordWrap(True)
        self.preview3d_messages = QPlainTextEdit()
        self.preview3d_messages.setReadOnly(True)
        self.preview_scene = PreviewScene()
        self.preview3d_widget = self._create_preview3d_widget()
        self.geometry_document = GeometryDocument()
        self.geometry_editor_tabs = QTabWidget()
        self.geometry_mode_label = QLabel("Geometry editor: preview-only")
        self.geometry_mode_label.setWordWrap(True)
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
        self.layer_status = QPlainTextEdit()
        self.layer_status.setReadOnly(True)
        self._selected_layer_row = -1
        self.workspace_summary = QLabel("Materials: 0 | Geometry: 0 volumes, 0 boolean ops | Current mode: Preview only")
        self.workspace_summary.setWordWrap(True)

        self.source_preset = QComboBox()
        self.source_preset.addItems(self.SOURCE_PRESETS)
        self.source_particle = QLineEdit("proton")
        self.source_energy = QLineEdit("10 MeV")
        self.source_position = QLineEdit("0,0,-1 mm")
        self.source_direction = QLineEdit("0,0,1")
        self.source_status_label = QLabel("Source: OK")
        self.source_editor_preset = QComboBox()
        self.source_editor_preset.addItems(SOURCE_PRESETS)
        self.source_editor_particle = QLineEdit("proton")
        self.source_editor_energy = QLineEdit("10 MeV")
        self.source_editor_position_type = QComboBox()
        self.source_editor_position_type.addItems(["point", "plane"])
        self.source_editor_shape = QComboBox()
        self.source_editor_shape.addItems(["point", "circle", "rectangle", "square", "annulus"])
        self.source_editor_position = QLineEdit("0,0,-1 mm")
        self.source_editor_radius = QLineEdit("1 mm")
        self.source_editor_inner_radius = QLineEdit("")
        self.source_editor_halfx = QLineEdit("1 mm")
        self.source_editor_halfy = QLineEdit("1 mm")
        self.source_editor_normal = QLineEdit("0,0,1")
        self.source_editor_confine_volume = QLineEdit("")
        self.source_editor_direction = QLineEdit("0,0,1")
        self.source_editor_angular_mode = QComboBox()
        self.source_editor_angular_mode.addItems(["fixed", "isotropic", "cone", "cosine", "focused"])
        self.source_editor_theta_min = QLineEdit("0 deg")
        self.source_editor_theta_max = QLineEdit("180 deg")
        self.source_editor_phi_min = QLineEdit("0 deg")
        self.source_editor_phi_max = QLineEdit("360 deg")
        self.source_editor_cone_half_angle = QLineEdit("5 deg")
        self.source_editor_focus_point = QLineEdit("0,0,0 mm")
        self.source_editor_preview_rays = QSpinBox()
        self.source_editor_preview_rays.setRange(1, 512)
        self.source_editor_preview_rays.setValue(12)
        self.source_editor_preview_seed = QSpinBox()
        self.source_editor_preview_seed.setRange(0, 2_147_483_647)
        self.source_editor_preview_seed.setValue(12345)
        self.source_editor_messages = QPlainTextEdit()
        self.source_editor_messages.setReadOnly(True)

        self.physics_reference = QLineEdit("FTFP_BERT_EMZ")
        self.default_cut = QLineEdit("1 mm")
        self.enable_biasing = QCheckBox()
        self.physics_status_label = QLabel("Physics: OK")
        self.physics_editor_mode = QComboBox()
        self.physics_editor_mode.addItems(["reference", "manual"])
        self.physics_editor_reference = QComboBox()
        self.physics_editor_reference.setEditable(True)
        self.physics_editor_reference.addItems(REFERENCE_LIST_CANDIDATES)
        self.physics_editor_default_cut = QLineEdit("1 mm")
        self.physics_editor_biasing = QCheckBox("Enable biasing physics hook")
        self.physics_editor_messages = QPlainTextEdit()
        self.physics_editor_messages.setReadOnly(True)

        self.scoring_enabled = QCheckBox()
        self.scoring_enabled.setChecked(True)
        self.scoring_hits = QCheckBox()
        self.scoring_hits.setChecked(True)
        self.scoring_event_edep = QCheckBox()
        self.scoring_event_edep.setChecked(True)
        self.scoring_edep = QCheckBox()
        self.scoring_edep.setChecked(True)
        self.hist_bins = QSpinBox()
        self.hist_bins.setRange(1, 10_000_000)
        self.hist_bins.setValue(100)
        self.hist_min = QLineEdit("0 eV")
        self.hist_max = QLineEdit("10 MeV")
        self.scoring_status_label = QLabel("Scoring: OK")
        self.scoring_editor_enabled = QCheckBox("Enable scoring")
        self.scoring_editor_enabled.setChecked(True)
        self.scoring_editor_hits = QCheckBox("Write hits")
        self.scoring_editor_hits.setChecked(True)
        self.scoring_editor_event_edep = QCheckBox("Write event_edep")
        self.scoring_editor_event_edep.setChecked(True)
        self.scoring_editor_edep = QCheckBox("Enable EdepScorer")
        self.scoring_editor_edep.setChecked(True)
        self.scoring_editor_raw_hist = QCheckBox("Raw edep histogram")
        self.scoring_editor_raw_hist.setChecked(True)
        self.scoring_editor_weighted_hist = QCheckBox("Weighted edep histogram")
        self.scoring_editor_weighted_hist.setChecked(True)
        self.scoring_editor_bins = QSpinBox()
        self.scoring_editor_bins.setRange(0, 10_000_000)
        self.scoring_editor_min = QLineEdit("0 eV")
        self.scoring_editor_max = QLineEdit("10 MeV")
        self.scoring_editor_volume_summary = QCheckBox("Volume summary")
        self.scoring_editor_volume_summary.setChecked(True)
        self.scoring_editor_particle_summary = QCheckBox("Particle summary")
        self.scoring_editor_particle_summary.setChecked(True)
        self.scoring_editor_auto_create = QCheckBox("Auto-create default scorers")
        self.scoring_editor_auto_create.setChecked(True)
        self.scoring_editor_messages = QPlainTextEdit()
        self.scoring_editor_messages.setReadOnly(True)
        self.generated_main_ini_raw = QPlainTextEdit()
        self.generated_main_ini_raw.setReadOnly(True)

        self.validate_button = QPushButton("Validate")
        self.generate_button = QPushButton("Generate Package")
        self.generate_run_button = QPushButton("Generate and Run")
        self.validation_text = QPlainTextEdit()
        self.validation_text.setReadOnly(True)
        self.package_label = QLabel("Generated package: <none>")
        self.package_label.setWordWrap(True)

        self._build_layout()
        self._connect_signals()
        self._populate_nist_table()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        splitter = QSplitter()
        splitter.addWidget(self._setup_panel())
        splitter.addWidget(self._workspace_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 980])
        layout.addWidget(splitter, 1)

    def _setup_panel(self) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)
        content_layout.addWidget(create_hint_label("Setup generates a reproducible run package. Material and geometry previews are read-only in this round."))
        content_layout.addWidget(self._run_group())
        content_layout.addWidget(self._input_group())
        content_layout.addWidget(self._source_group())
        content_layout.addWidget(self._physics_group())
        content_layout.addWidget(self._scoring_group())

        buttons = QHBoxLayout()
        buttons.addWidget(self.validate_button)
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.generate_run_button)
        actions = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions)
        actions_layout.addLayout(buttons)
        actions_layout.addWidget(self.package_label)
        content_layout.addWidget(actions)
        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(380)
        scroll.setWidget(content)
        return scroll

    def _workspace_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.workspace_summary)

        tabs = QTabWidget()
        tabs.addTab(self._materials_editor_tab(), "Materials")
        tabs.addTab(self._geometry_editor_tab(), "Geometry")
        tabs.addTab(self._table_tab(self.boolean_count_label, self.boolean_table), "Boolean Ops")
        tabs.addTab(self._preview3d_tab(), "3D Preview")
        tabs.addTab(self._run_config_tab(), "Run Config")
        tabs.addTab(self._messages_tab(), "Messages")
        tabs.addTab(self._raw_files_tab(), "Raw Files")
        tabs.addTab(self._table_tab(QLabel("Click a material name to copy it to the clipboard."), self.nist_table), "NIST Quick List")
        layout.addWidget(tabs, 1)
        return panel

    def _table_tab(self, label: QLabel, table: QTableWidget) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(label)
        layout.addWidget(table, 1)
        return tab

    def _materials_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Materials Editor"))
        layout.addWidget(self.materials_count_label)
        layout.addWidget(QLabel("Generated target: run package config/materials/material.ini. Source file is never overwritten."))
        toolbar = QHBoxLayout()
        for button in [
            self.load_materials_editor_button,
            self.add_nist_button,
            self.add_mass_button,
            self.add_volume_button,
            self.add_atom_button,
            self.duplicate_material_button,
            self.delete_material_button,
            self.validate_materials_button,
            self.revert_materials_button,
        ]:
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
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
        return tab

    def _geometry_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self.geometry_mode_label)
        self.geometry_editor_tabs.addTab(self._simple_box_editor_tab(), "Simple Box")
        self.geometry_editor_tabs.addTab(self._layered_device_editor_tab(), "Layered Device")
        self.geometry_editor_tabs.addTab(self._hierarchical_editor_tab(), "Hierarchical Volumes")
        self.geometry_editor_tabs.addTab(self._boolean_editor_tab(), "Boolean Operations")
        self.geometry_editor_tabs.addTab(self._geometry_preview_tab(), "Preview / Unsupported Template")
        layout.addWidget(self.geometry_editor_tabs, 1)
        return tab

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
        layout.addWidget(detail)
        layout.addWidget(QLabel("Layer validation"))
        layout.addWidget(self.layer_status, 1)
        return tab

    def _geometry_preview_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(create_hint_label("Unsupported templates are preview-only and are copied unchanged unless the mode is switched to an editable template. Parsed volume/boolean rows are shown in the Hierarchical and Boolean tabs."))
        layout.addWidget(self.geometry_count_label)
        layout.addWidget(self.boolean_count_label)
        layout.addStretch(1)
        return tab

    def _hierarchical_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(create_hint_label("Edits generic [world] and [volume.*] sections. Disabled rows stay in the GUI but are not generated."))
        toolbar = QHBoxLayout()
        for button in [
            self.add_volume_button,
            self.duplicate_volume_button,
            self.delete_volume_button,
            self.move_volume_up_button,
            self.move_volume_down_button,
            self.validate_geometry_button,
            self.revert_geometry_button,
        ]:
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        layout.addWidget(self.geometry_count_label)
        layout.addWidget(self.geometry_table, 1)
        return tab

    def _boolean_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(create_hint_label("Boolean tools are solid operands, not volumes. They do not have material/sensitive/bias state. Writer renumbers enabled ops per target."))
        toolbar = QHBoxLayout()
        for button in [
            self.add_boolean_button,
            self.duplicate_boolean_button,
            self.delete_boolean_button,
            self.move_boolean_up_button,
            self.move_boolean_down_button,
            self.validate_boolean_button,
        ]:
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        layout.addWidget(self.boolean_count_label)
        layout.addWidget(self.boolean_table, 1)
        return tab

    def _preview3d_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.preview3d_refresh_button)
        toolbar.addWidget(self.preview3d_reset_button)
        toolbar.addWidget(self.preview3d_show_source)
        toolbar.addWidget(self.preview3d_show_labels)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        layout.addWidget(self.preview3d_status)
        layout.addWidget(self.preview3d_widget, 3)
        layout.addWidget(QLabel("3D preview messages"))
        layout.addWidget(self.preview3d_messages, 1)
        return tab

    def _create_preview3d_widget(self) -> QWidget:
        available, reason = pyvista_available()
        if not available:
            return FallbackPreviewWidget(reason=reason)
        try:
            return PyVistaPreviewWidget()
        except Exception as exc:  # noqa: BLE001
            return FallbackPreviewWidget(reason=str(exc))

    def _run_config_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        status = QHBoxLayout()
        status.addWidget(self.source_status_label)
        status.addWidget(self.physics_status_label)
        status.addWidget(self.scoring_status_label)
        status.addStretch(1)
        layout.addLayout(status)
        tabs = QTabWidget()
        tabs.addTab(self._source_editor_tab(), "Source")
        tabs.addTab(self._physics_editor_tab(), "Physics")
        tabs.addTab(self._scoring_editor_tab(), "Scoring")
        layout.addWidget(tabs, 1)
        return tab

    def _source_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        basic = QGroupBox("Basic")
        basic_form = QFormLayout(basic)
        basic_form.addRow("Preset", self.source_editor_preset)
        basic_form.addRow("Particle", self.source_editor_particle)
        basic_form.addRow("Energy", self.source_editor_energy)
        layout.addWidget(basic)

        position = QGroupBox("Position Distribution")
        position_form = QFormLayout(position)
        position_form.addRow("Mode", self.source_editor_position_type)
        position_form.addRow("Center / position", self.source_editor_position)
        position_form.addRow("Shape", self.source_editor_shape)
        position_form.addRow("Radius", self.source_editor_radius)
        position_form.addRow("Inner radius", self.source_editor_inner_radius)
        position_form.addRow("Half X", self.source_editor_halfx)
        position_form.addRow("Half Y", self.source_editor_halfy)
        position_form.addRow("Normal", self.source_editor_normal)
        position_form.addRow("Confine volume", self.source_editor_confine_volume)
        layout.addWidget(position)

        angular = QGroupBox("Angular Distribution")
        angular_form = QFormLayout(angular)
        angular_form.addRow("Mode", self.source_editor_angular_mode)
        angular_form.addRow("Direction / axis", self.source_editor_direction)
        angular_form.addRow("Theta min", self.source_editor_theta_min)
        angular_form.addRow("Theta max", self.source_editor_theta_max)
        angular_form.addRow("Phi min", self.source_editor_phi_min)
        angular_form.addRow("Phi max", self.source_editor_phi_max)
        angular_form.addRow("Cone half angle", self.source_editor_cone_half_angle)
        angular_form.addRow("Focus point", self.source_editor_focus_point)
        angular_form.addRow("Preview ray count", self.source_editor_preview_rays)
        angular_form.addRow("Preview random seed", self.source_editor_preview_seed)
        layout.addWidget(angular)
        layout.addWidget(create_hint_label("Backend support: point/fixed, point/isotropic, plane circle/fixed, and plane circle/isotropic are generated to main.ini. Rectangle, annulus, cone, cosine, and focused modes are shown in preview but blocked from package generation until the C++ Source backend supports them."))
        layout.addWidget(QLabel("Validation messages"))
        layout.addWidget(self.source_editor_messages, 1)
        return tab

    def _physics_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        form.addRow("Mode", self.physics_editor_mode)
        form.addRow("Reference list", self.physics_editor_reference)
        form.addRow("Default cut", self.physics_editor_default_cut)
        form.addRow("", self.physics_editor_biasing)
        layout.addLayout(form)
        layout.addWidget(create_hint_label("Biasing physics only enables the physics hook. Biasing rules are configured in a later editor. Manual mode is not generated by this MVP."))
        layout.addWidget(QLabel("Validation messages"))
        layout.addWidget(self.physics_editor_messages, 1)
        return tab

    def _scoring_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        switches = QGroupBox("Outputs")
        switch_layout = QVBoxLayout(switches)
        for widget in [
            self.scoring_editor_enabled,
            self.scoring_editor_hits,
            self.scoring_editor_event_edep,
            self.scoring_editor_edep,
        ]:
            switch_layout.addWidget(widget)
        hist = QGroupBox("Edep histogram")
        hist_form = QFormLayout(hist)
        hist_form.addRow("", self.scoring_editor_raw_hist)
        hist_form.addRow("", self.scoring_editor_weighted_hist)
        hist_form.addRow("Bins", self.scoring_editor_bins)
        hist_form.addRow("Min", self.scoring_editor_min)
        hist_form.addRow("Max", self.scoring_editor_max)
        summary = QGroupBox("Summaries")
        summary_layout = QVBoxLayout(summary)
        summary_layout.addWidget(self.scoring_editor_volume_summary)
        summary_layout.addWidget(self.scoring_editor_particle_summary)
        summary_layout.addWidget(self.scoring_editor_auto_create)
        layout.addWidget(switches)
        layout.addWidget(hist)
        layout.addWidget(summary)
        layout.addWidget(QLabel("LET/Dose/Fluence are experimental stubs and are not exposed by this MVP."))
        layout.addWidget(QLabel("Validation messages"))
        layout.addWidget(self.scoring_editor_messages, 1)
        return tab

    def _messages_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Validation result"))
        layout.addWidget(self.validation_text, 1)
        layout.addWidget(QLabel("Materials messages"))
        layout.addWidget(self.materials_messages, 1)
        layout.addWidget(QLabel("Geometry messages"))
        layout.addWidget(self.geometry_messages, 1)
        layout.addWidget(QLabel("3D Preview messages"))
        layout.addWidget(self.preview3d_messages, 1)
        return tab

    def _raw_files_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        raw_tabs = QTabWidget()
        raw_tabs.addTab(self.materials_raw, "Source materials raw")
        raw_tabs.addTab(self.generated_materials_raw, "Generated materials preview")
        raw_tabs.addTab(self.generated_geometry_raw, "Generated geometry preview")
        raw_tabs.addTab(self.generated_main_ini_raw, "Generated main.ini preview")
        raw_tabs.addTab(self.geometry_raw, "Geometry raw")
        layout.addWidget(raw_tabs, 1)
        return tab

    def _run_group(self) -> QGroupBox:
        group = QGroupBox("Run")
        form = QFormLayout(group)
        form.addRow("Run name", self.run_name)
        form.addRow("Threads", self.threads)
        form.addRow("Seed", self.seed)
        form.addRow("BeamOn", self.beam_on)
        form.addRow("Check overlaps", self.check_overlaps)
        form.addRow("Dry run", self.dry_run)
        return group

    def _input_group(self) -> QGroupBox:
        group = QGroupBox("Input files")
        form = QFormLayout(group)
        form.addRow("Materials config", self._with_browse(self.materials_config, self._browse_materials))
        form.addRow("", self.reload_materials_button)
        form.addRow("Geometry config", self._with_browse(self.geometry_config, self._browse_geometry))
        form.addRow("", self.reload_geometry_button)
        form.addRow("Geometry template", self.geometry_template)
        return group

    def _source_group(self) -> QGroupBox:
        group = QGroupBox("Source")
        form = QFormLayout(group)
        form.addRow("Preset", self.source_preset)
        form.addRow("Particle", self.source_particle)
        form.addRow("Energy", self.source_energy)
        form.addRow("Position", self.source_position)
        form.addRow("Direction", self.source_direction)
        return group

    def _physics_group(self) -> QGroupBox:
        group = QGroupBox("Physics")
        form = QFormLayout(group)
        form.addRow("Reference list", self.physics_reference)
        form.addRow("Default cut", self.default_cut)
        form.addRow("Enable biasing physics", self.enable_biasing)
        return group

    def _scoring_group(self) -> QGroupBox:
        group = QGroupBox("Scoring")
        form = QFormLayout(group)
        form.addRow("Enable scoring", self.scoring_enabled)
        form.addRow("Hits", self.scoring_hits)
        form.addRow("Event edep", self.scoring_event_edep)
        form.addRow("Edep histogram", self.scoring_edep)
        form.addRow("Histogram bins", self.hist_bins)
        form.addRow("Histogram min", self.hist_min)
        form.addRow("Histogram max", self.hist_max)
        return group

    def _with_browse(self, line_edit: QLineEdit, callback) -> QWidget:
        return make_path_row(line_edit, "Browse", callback)

    def _connect_signals(self) -> None:
        self.validate_button.clicked.connect(self.validateRequested.emit)
        self.generate_button.clicked.connect(lambda: self.generatePackageRequested.emit(False))
        self.generate_run_button.clicked.connect(lambda: self.generatePackageRequested.emit(True))
        self.reload_materials_button.clicked.connect(self.reload_materials)
        self.reload_geometry_button.clicked.connect(self.reload_geometry)
        self.load_materials_editor_button.clicked.connect(self.reload_materials)
        self.add_nist_button.clicked.connect(lambda: self._add_material("nist"))
        self.add_mass_button.clicked.connect(lambda: self._add_material("mass_fraction"))
        self.add_volume_button.clicked.connect(lambda: self._add_material("volume_fraction"))
        self.add_atom_button.clicked.connect(lambda: self._add_material("atom_count"))
        self.duplicate_material_button.clicked.connect(self._duplicate_material)
        self.delete_material_button.clicked.connect(self._delete_material)
        self.validate_materials_button.clicked.connect(self._validate_materials_editor)
        self.revert_materials_button.clicked.connect(self.reload_materials)
        self.materials_table.itemSelectionChanged.connect(self._on_material_selection_changed)

        widgets = [
            self.run_name,
            self.seed,
            self.materials_config,
            self.geometry_config,
            self.source_particle,
            self.source_energy,
            self.source_position,
            self.source_direction,
            self.physics_reference,
            self.default_cut,
            self.hist_min,
            self.hist_max,
        ]
        for widget in widgets:
            widget.textChanged.connect(self._emit_changed)
        for widget in [
            self.threads,
            self.beam_on,
            self.hist_bins,
        ]:
            widget.valueChanged.connect(self._emit_changed)
        for widget in [
            self.check_overlaps,
            self.dry_run,
            self.enable_biasing,
            self.scoring_enabled,
            self.scoring_hits,
            self.scoring_event_edep,
            self.scoring_edep,
        ]:
            widget.stateChanged.connect(self._emit_changed)
        self.geometry_template.currentTextChanged.connect(self._on_geometry_template_changed)
        self.source_preset.currentTextChanged.connect(self._emit_changed)
        self.material_name.textEdited.connect(self._update_selected_material_from_detail)
        self.material_mode.currentTextChanged.connect(self._update_selected_material_from_detail)
        self.material_density.textEdited.connect(self._update_selected_material_from_detail)
        self.material_components.textChanged.connect(self._update_selected_material_from_detail)
        self.material_enabled.stateChanged.connect(self._update_selected_material_from_detail)
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
        self.preview3d_refresh_button.clicked.connect(self.refresh_3d_preview)
        self.preview3d_reset_button.clicked.connect(lambda: self.preview3d_widget.reset_camera())
        self.preview3d_show_source.stateChanged.connect(self._update_preview_display_options)
        self.preview3d_show_labels.stateChanged.connect(self._update_preview_display_options)
        for widget in [
            self.source_editor_particle,
            self.source_editor_energy,
            self.source_editor_position,
            self.source_editor_radius,
            self.source_editor_inner_radius,
            self.source_editor_halfx,
            self.source_editor_halfy,
            self.source_editor_normal,
            self.source_editor_confine_volume,
            self.source_editor_direction,
            self.source_editor_theta_min,
            self.source_editor_theta_max,
            self.source_editor_phi_min,
            self.source_editor_phi_max,
            self.source_editor_cone_half_angle,
            self.source_editor_focus_point,
            self.physics_editor_default_cut,
            self.scoring_editor_min,
            self.scoring_editor_max,
        ]:
            widget.textEdited.connect(self._update_sps_from_widgets)
        for combo in [
            self.source_editor_preset,
            self.source_editor_position_type,
            self.source_editor_shape,
            self.source_editor_angular_mode,
            self.physics_editor_mode,
            self.physics_editor_reference,
        ]:
            combo.currentTextChanged.connect(self._update_sps_from_widgets)
        for widget in [
            self.physics_editor_biasing,
            self.scoring_editor_enabled,
            self.scoring_editor_hits,
            self.scoring_editor_event_edep,
            self.scoring_editor_edep,
            self.scoring_editor_raw_hist,
            self.scoring_editor_weighted_hist,
            self.scoring_editor_volume_summary,
            self.scoring_editor_particle_summary,
            self.scoring_editor_auto_create,
        ]:
            widget.stateChanged.connect(self._update_sps_from_widgets)
        self.scoring_editor_bins.valueChanged.connect(self._update_sps_from_widgets)
        self.source_editor_preview_rays.valueChanged.connect(self._update_sps_from_widgets)
        self.source_editor_preview_seed.valueChanged.connect(self._update_sps_from_widgets)
        for widget in [
            self.source_particle,
            self.source_energy,
            self.source_position,
            self.source_direction,
            self.physics_reference,
            self.default_cut,
            self.hist_min,
            self.hist_max,
        ]:
            widget.textEdited.connect(self._update_sps_from_summary_widgets)
        self.source_preset.currentTextChanged.connect(self._update_sps_from_summary_widgets)
        self.enable_biasing.stateChanged.connect(self._update_sps_from_summary_widgets)
        for widget in [
            self.scoring_enabled,
            self.scoring_hits,
            self.scoring_event_edep,
            self.scoring_edep,
        ]:
            widget.stateChanged.connect(self._update_sps_from_summary_widgets)
        self.hist_bins.valueChanged.connect(self._update_sps_from_summary_widgets)

    def set_from_project(self, project: G4USimProject) -> None:
        self._building = True
        run = project.runSettings
        paths = project.pathSettings
        geometry = project.geometrySettings
        source = project.sourceSettings
        physics = project.physicsSettings
        scoring = project.scoringSettings

        self.run_name.setText(run.run_name or project.runName or project.projectName)
        self.threads.setValue(run.threads or project.threads or 1)
        self.seed.setText("" if run.seed is None else str(run.seed))
        self.beam_on.setValue(run.beam_on)
        self.check_overlaps.setChecked(run.check_overlaps)
        self.dry_run.setChecked(run.dry_run)

        self.materials_config.setText(paths.materials_config)
        self.geometry_config.setText(geometry.config_path or paths.geometry_config)
        self._set_combo_text(self.geometry_template, geometry.template)

        self._set_combo_text(self.source_preset, source.preset)
        self.source_particle.setText(source.particle)
        self.source_energy.setText(source.energy)
        self.source_position.setText(source.position)
        self.source_direction.setText(source.direction)

        self.physics_reference.setText(physics.reference)
        self.default_cut.setText(physics.default_cut)
        self.enable_biasing.setChecked(physics.enable_biasing)

        self.scoring_enabled.setChecked(scoring.enabled)
        self.scoring_hits.setChecked(scoring.hits)
        self.scoring_event_edep.setChecked(scoring.event_edep)
        self.scoring_edep.setChecked(scoring.edep)
        self.hist_bins.setValue(scoring.hist_bins)
        self.hist_min.setText(scoring.hist_min)
        self.hist_max.setText(scoring.hist_max)
        self._building = False
        self.source_editor = getattr(project, "sourceEditor", SourceEditableModel.from_settings(source))
        self.physics_editor = getattr(project, "physicsEditor", PhysicsEditableModel.from_settings(physics))
        self.scoring_editor = getattr(project, "scoringEditor", ScoringEditableModel.from_settings(scoring))
        self._populate_sps_editors()
        self.reload_materials()
        self.reload_geometry()
        saved_geometry = getattr(project, "geometryEditor", None)
        if isinstance(saved_geometry, GeometryDocument) and saved_geometry.is_dirty:
            self.geometry_document = saved_geometry
            self._populate_geometry_editor()
            self._update_workspace_summary()

    def update_project(self, project: G4USimProject) -> None:
        project.runSettings = self.run_settings()
        project.pathSettings.materials_config = self.materials_config.text().strip()
        project.pathSettings.geometry_config = self.geometry_config.text().strip()
        project.geometrySettings = self.geometry_settings()
        project.geometryEditor = self.geometry_document
        project.sourceEditor = self.source_editor
        project.physicsEditor = self.physics_editor
        project.scoringEditor = self.scoring_editor
        project.sourceSettings = self.source_settings()
        project.physicsSettings = self.physics_settings()
        project.scoringSettings = self.scoring_settings()

    def path_settings(self, project: G4USimProject) -> PathSettings:
        paths = PathSettings(
            executable=project.executable,
            workspace_root=project.workspaceRoot,
            runs_root=project.runsRoot,
            materials_config=self.materials_config.text().strip(),
            geometry_config=self.geometry_config.text().strip(),
        )
        if not paths.runs_root and project.outputDir:
            paths.runs_root = project.outputDir
        return paths

    def run_settings(self) -> RunSettings:
        seed_text = self.seed.text().strip()
        seed_value: int | None
        try:
            seed_value = int(seed_text) if seed_text else None
        except ValueError:
            seed_value = None
        return RunSettings(
            run_name=self.run_name.text().strip() or "gui_run",
            threads=self.threads.value(),
            seed=seed_value,
            beam_on=self.beam_on.value(),
            check_overlaps=self.check_overlaps.isChecked(),
            dry_run=self.dry_run.isChecked(),
        )

    def geometry_settings(self) -> GeometrySettings:
        return GeometrySettings(
            template=self.geometry_template.currentText().strip(),
            config_path=self.geometry_config.text().strip(),
        )

    def source_settings(self) -> SourceSettings:
        return self.source_editor.to_settings()

    def physics_settings(self) -> PhysicsSettings:
        return self.physics_editor.to_settings()

    def scoring_settings(self) -> ScoringSettings:
        return self.scoring_editor.to_settings()

    def validate_current(self, project: G4USimProject) -> ValidationReport:
        if not self.material_document.is_dirty:
            self.reload_materials()
        if not self.geometry_document.is_dirty:
            self.reload_geometry()
        report = validate_config_builder(
            paths=self.path_settings(project),
            run=self.run_settings(),
            geometry=self.geometry_settings(),
            source=self.source_settings(),
            physics=self.physics_settings(),
            scoring=self.scoring_settings(),
            material_document=self.material_document if self.material_document.is_dirty else None,
            geometry_document=self.geometry_document if self.geometry_document.is_dirty else None,
            source_model=self.source_editor,
            physics_model=self.physics_editor,
            scoring_model=self.scoring_editor,
        )
        seed_text = self.seed.text().strip()
        if seed_text:
            try:
                int(seed_text)
            except ValueError:
                report.errors.append("Seed must be an integer when provided.")
        return report

    def set_validation_text(self, text: str) -> None:
        self.validation_text.setPlainText(text)

    def set_package_path(self, path: str) -> None:
        self.package_label.setText(f"Generated package: {path or '<none>'}")

    def _browse_materials(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select materials config", filter="INI files (*.ini);;All files (*)")
        if path:
            self.materials_config.setText(path)
            self.reload_materials()

    def _browse_geometry(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select geometry config", filter="INI files (*.ini);;All files (*)")
        if path:
            self.geometry_config.setText(path)
            self.reload_geometry()

    def _set_combo_text(self, combo: QComboBox, value: str) -> None:
        if not value:
            return
        index = combo.findText(value)
        if index < 0:
            combo.addItem(value)
            index = combo.findText(value)
        combo.setCurrentIndex(index)

    def _emit_changed(self) -> None:
        if not self._building:
            self._mark_preview_stale()
            self.settingsChanged.emit()

    def _mark_preview_stale(self) -> None:
        if hasattr(self, "preview3d_status"):
            self.preview3d_status.setText("3D Preview: stale. Click Refresh Preview to rebuild the scene.")

    def _update_preview_display_options(self) -> None:
        if hasattr(self.preview3d_widget, "set_show_source"):
            self.preview3d_widget.set_show_source(self.preview3d_show_source.isChecked())
        if hasattr(self.preview3d_widget, "set_show_labels"):
            self.preview3d_widget.set_show_labels(self.preview3d_show_labels.isChecked())
        self._mark_preview_stale()

    def refresh_3d_preview(self) -> None:
        try:
            self.preview_scene = build_preview_scene(self.geometry_document, self.source_editor)
            if hasattr(self.preview3d_widget, "set_show_source"):
                self.preview3d_widget.set_show_source(self.preview3d_show_source.isChecked())
            if hasattr(self.preview3d_widget, "set_show_labels"):
                self.preview3d_widget.set_show_labels(self.preview3d_show_labels.isChecked())
            self.preview3d_widget.render_scene(self.preview_scene)
            message_lines = self.preview_scene.summary_lines()
            self.preview3d_messages.setPlainText("\n".join(message_lines))
            status = "ERROR" if self.preview_scene.errors else "WARN" if self.preview_scene.warnings else "OK"
            self.preview3d_status.setText(f"3D Preview: {status} | volumes={len(self.preview_scene.volumes)}")
        except Exception as exc:  # noqa: BLE001
            self.preview3d_status.setText(f"3D Preview: ERROR")
            self.preview3d_messages.setPlainText(f"Preview refresh failed:\n{exc}")

    def _on_geometry_template_changed(self) -> None:
        if self._building:
            return
        set_geometry_mode(self.geometry_document, self.geometry_template.currentText())
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
        editable = mode in EDITABLE_GEOMETRY_MODES
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

    def _populate_geometry_editor(self) -> None:
        self._building = True
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
        self._building = False
        self._populate_layers_table()
        self._populate_hierarchical_tables()
        self._apply_geometry_mode_to_tabs()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()

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

    def _row_status(self, errors: list[str], warnings: list[str]) -> str:
        if errors:
            return "ERROR"
        if warnings:
            return "WARN"
        return "OK"

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
        self._mark_geometry_dirty()

    def _on_boolean_table_changed(self, item: QTableWidgetItem) -> None:
        if self._building:
            return
        row = item.row()
        if row < 0 or row >= len(self.geometry_document.boolean_ops):
            return
        op = self.geometry_document.boolean_ops[row]
        values = [self._table_text(self.boolean_table, row, col) for col in range(self.boolean_table.columnCount())]
        op.enabled = self._as_bool(values[0])
        op.target_volume = values[1]
        try:
            op.index = int(values[2])
        except ValueError:
            op.index = row
        op.operation = values[3] or "subtraction"
        op.tool_shape = values[4] or "box"
        op.tool_size = values[5]
        op.tool_parameters = values[6]
        op.position = values[7]
        op.rotation = values[8]
        self._mark_geometry_dirty()

    def _mark_geometry_dirty(self) -> None:
        self.geometry_document.is_dirty = self.geometry_document.mode in EDITABLE_GEOMETRY_MODES
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._update_workspace_summary()
        self._emit_changed()

    def _table_text(self, table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        return item.text().strip() if item else ""

    def _as_bool(self, value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}

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

    def _add_boolean_op(self) -> None:
        target = self._first_non_world_volume_name()
        index = sum(1 for op in self.geometry_document.boolean_ops if op.target_volume == target)
        self.geometry_document.boolean_ops.append(
            BooleanOperationRow(
                target_volume=target,
                index=index,
                operation="subtraction",
                tool_shape="box",
                tool_size="1 mm,1 mm,1 mm",
                position="0 mm,0 mm,0 mm",
                rotation="0 deg,0 deg,0 deg",
                name=f"{target}_cut_{index}" if target else "",
            )
        )
        if self.geometry_document.mode == "hierarchical":
            self.geometry_document.mode = "hierarchical_boolean"
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()

    def _duplicate_boolean_op(self) -> None:
        row = self.boolean_table.currentRow()
        if row < 0 or row >= len(self.geometry_document.boolean_ops):
            return
        source = self.geometry_document.boolean_ops[row]
        duplicate = BooleanOperationRow(**{k: v for k, v in source.__dict__.items() if k in BooleanOperationRow.__dataclass_fields__})
        duplicate.index = source.index + 1
        duplicate.name = f"{source.name}_copy" if source.name else ""
        duplicate.errors = []
        duplicate.warnings = []
        self.geometry_document.boolean_ops.insert(row + 1, duplicate)
        self._renumber_boolean_ops()
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()
        self.boolean_table.selectRow(row + 1)

    def _delete_boolean_op(self) -> None:
        row = self.boolean_table.currentRow()
        if row < 0 or row >= len(self.geometry_document.boolean_ops):
            return
        del self.geometry_document.boolean_ops[row]
        self._renumber_boolean_ops()
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()

    def _move_boolean_op(self, direction: int) -> None:
        row = self.boolean_table.currentRow()
        target = row + direction
        rows = self.geometry_document.boolean_ops
        if row < 0 or target < 0 or row >= len(rows) or target >= len(rows):
            return
        rows[row], rows[target] = rows[target], rows[row]
        self._renumber_boolean_ops()
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()
        self.boolean_table.selectRow(target)

    def _renumber_boolean_ops(self) -> None:
        counts: dict[str, int] = {}
        for op in self.geometry_document.boolean_ops:
            target = op.target_volume.strip()
            op.index = counts.get(target, 0)
            counts[target] = op.index + 1

    def _first_non_world_volume_name(self) -> str:
        for volume in self.geometry_document.volumes:
            if volume.enabled and volume.name.strip().lower() != "world":
                return volume.name.strip()
        return self.geometry_document.volumes[0].name.strip() if self.geometry_document.volumes else ""

    def _unique_name(self, base: str, existing: set[str]) -> str:
        existing_lower = {name.lower() for name in existing}
        candidate = base
        index = 1
        while candidate.lower() in existing_lower:
            index += 1
            candidate = f"{base}{index}"
        return candidate

    def _populate_layers_table(self) -> None:
        self._building = True
        self.layer_table.setRowCount(0)
        for layer in self.geometry_document.layered_device.layers:
            row = self.layer_table.rowCount()
            self.layer_table.insertRow(row)
            values = [
                "yes" if layer.enabled else "no",
                layer.name,
                layer.material,
                layer.thickness,
                layer.xy,
                "yes" if layer.sensitive else "no",
                "yes" if layer.bias else "no",
                layer.region,
            ]
            for col, value in enumerate(values):
                self.layer_table.setItem(row, col, QTableWidgetItem(value))
        self.layer_table.resizeColumnsToContents()
        self._building = False
        if self.geometry_document.layered_device.layers:
            row = min(max(self._selected_layer_row, 0), len(self.geometry_document.layered_device.layers) - 1)
            self.layer_table.selectRow(row)
            self._select_layer_row(row)
        else:
            self._select_layer_row(-1)

    def _on_layer_selection_changed(self) -> None:
        if self._building:
            return
        self._select_layer_row(self.layer_table.currentRow())

    def _select_layer_row(self, row: int) -> None:
        self._building = True
        self._selected_layer_row = row
        layers = self.geometry_document.layered_device.layers
        if row < 0 or row >= len(layers):
            self.layer_enabled.setChecked(False)
            self.layer_name.clear()
            self.layer_thickness.clear()
            self.layer_xy.clear()
            self.layer_region.clear()
            self.layer_copy_no.clear()
            self.layer_status.setPlainText("Select a layer to edit.")
            self._building = False
            return
        layer = layers[row]
        self.layer_enabled.setChecked(layer.enabled)
        self.layer_name.setText(layer.name)
        self._set_combo_text(self.layer_material, layer.material)
        self.layer_thickness.setText(layer.thickness)
        self.layer_xy.setText(layer.xy)
        self.layer_sensitive.setChecked(layer.sensitive)
        self.layer_bias.setChecked(layer.bias)
        self.layer_region.setText(layer.region)
        self.layer_copy_no.setText(layer.copy_no)
        self._building = False

    def _update_selected_layer_from_detail(self) -> None:
        row = self._selected_layer_row
        layers = self.geometry_document.layered_device.layers
        if row < 0 or row >= len(layers):
            return
        layer = layers[row]
        layer.enabled = self.layer_enabled.isChecked()
        layer.name = self.layer_name.text().strip()
        layer.material = self.layer_material.currentText().strip()
        layer.thickness = self.layer_thickness.text().strip()
        layer.xy = self.layer_xy.text().strip()
        layer.sensitive = self.layer_sensitive.isChecked()
        layer.bias = self.layer_bias.isChecked()
        layer.region = self.layer_region.text().strip()
        layer.copy_no = self.layer_copy_no.text().strip()
        self._populate_layers_table()
        if 0 <= row < self.layer_table.rowCount():
            self.layer_table.selectRow(row)

    def _add_layer(self) -> None:
        layer = LayerRow(name=f"Layer{len(self.geometry_document.layered_device.layers) + 1}", material="G4_Si", thickness="1 um", xy="10 mm, 10 mm")
        self.geometry_document.layered_device.layers.append(layer)
        self.geometry_document.is_dirty = True
        self._selected_layer_row = len(self.geometry_document.layered_device.layers) - 1
        self._populate_layers_table()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._emit_changed()

    def _duplicate_layer(self) -> None:
        row = self._selected_layer_row
        layers = self.geometry_document.layered_device.layers
        if row < 0 or row >= len(layers):
            return
        source = layers[row]
        duplicate = LayerRow(**source.__dict__.copy())
        duplicate.name = f"{source.name}_copy"
        layers.insert(row + 1, duplicate)
        self.geometry_document.is_dirty = True
        self._selected_layer_row = row + 1
        self._populate_layers_table()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._emit_changed()

    def _delete_layer(self) -> None:
        row = self._selected_layer_row
        layers = self.geometry_document.layered_device.layers
        if row < 0 or row >= len(layers):
            return
        del layers[row]
        self.geometry_document.is_dirty = True
        self._selected_layer_row = min(row, len(layers) - 1)
        self._populate_layers_table()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._emit_changed()

    def _move_layer(self, direction: int) -> None:
        row = self._selected_layer_row
        layers = self.geometry_document.layered_device.layers
        target = row + direction
        if row < 0 or row >= len(layers) or target < 0 or target >= len(layers):
            return
        layers[row], layers[target] = layers[target], layers[row]
        self.geometry_document.is_dirty = True
        self._selected_layer_row = target
        self._populate_layers_table()
        self._update_generated_geometry_preview()
        self._emit_changed()

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
                self.geometry_table.setItem(row, 11, QTableWidgetItem(self._row_status(volume.errors, volume.warnings)))
        for row, op in enumerate(self.geometry_document.boolean_ops):
            if row < self.boolean_table.rowCount():
                self.boolean_table.setItem(row, 9, QTableWidgetItem(self._row_status(op.errors, op.warnings)))
        self._building = False

    def _update_hierarchical_count_labels(self) -> None:
        volume_errors = sum(len(volume.errors) for volume in self.geometry_document.volumes)
        volume_warnings = sum(len(volume.warnings) for volume in self.geometry_document.volumes)
        boolean_errors = sum(len(op.errors) for op in self.geometry_document.boolean_ops)
        boolean_warnings = sum(len(op.warnings) for op in self.geometry_document.boolean_ops)
        mode_text = "editable" if self.geometry_document.mode in HIERARCHICAL_GEOMETRY_MODES else "preview"
        self.geometry_count_label.setText(
            f"Volumes: {len(self.geometry_document.volumes)} rows, "
            f"{sum(1 for volume in self.geometry_document.volumes if volume.enabled)} enabled | "
            f"{volume_errors} errors, {volume_warnings} warnings | {mode_text}"
        )
        self.boolean_count_label.setText(
            f"Boolean ops: {len(self.geometry_document.boolean_ops)} rows, "
            f"{sum(1 for op in self.geometry_document.boolean_ops if op.enabled)} enabled | "
            f"{boolean_errors} errors, {boolean_warnings} warnings | {mode_text}"
        )

    def _update_generated_geometry_preview(self) -> None:
        if self.geometry_document.mode not in EDITABLE_GEOMETRY_MODES:
            self.generated_geometry_raw.setPlainText("Preview-only template. Package writer will copy source geometry.ini unchanged.")
            return
        try:
            self.generated_geometry_raw.setPlainText(generate_geometry_ini_text(self.geometry_document))
        except Exception as exc:  # noqa: BLE001
            self.generated_geometry_raw.setPlainText(f"Generated geometry preview unavailable:\n{exc}")

    def _populate_sps_editors(self) -> None:
        self._building = True
        self._set_combo_text(self.source_editor_preset, self.source_editor.preset)
        self.source_editor_particle.setText(self.source_editor.particle)
        self.source_editor_energy.setText(self.source_editor.energy)
        self._set_combo_text(self.source_editor_position_type, self.source_editor.position_mode or self.source_editor.position_type)
        self._set_combo_text(self.source_editor_shape, self.source_editor.source_shape)
        self.source_editor_position.setText(self.source_editor.position)
        self.source_editor_radius.setText(self.source_editor.radius)
        self.source_editor_inner_radius.setText(self.source_editor.inner_radius)
        self.source_editor_halfx.setText(self.source_editor.halfx)
        self.source_editor_halfy.setText(self.source_editor.halfy)
        self.source_editor_normal.setText(self.source_editor.normal)
        self.source_editor_confine_volume.setText(self.source_editor.confine_volume)
        self.source_editor_direction.setText(self.source_editor.direction)
        self._set_combo_text(self.source_editor_angular_mode, self.source_editor.angular_mode)
        self.source_editor_theta_min.setText(self.source_editor.theta_min)
        self.source_editor_theta_max.setText(self.source_editor.theta_max)
        self.source_editor_phi_min.setText(self.source_editor.phi_min)
        self.source_editor_phi_max.setText(self.source_editor.phi_max)
        self.source_editor_cone_half_angle.setText(self.source_editor.cone_half_angle)
        self.source_editor_focus_point.setText(self.source_editor.focus_point)
        self.source_editor_preview_rays.setValue(self.source_editor.preview_ray_count)
        self.source_editor_preview_seed.setValue(self.source_editor.random_seed_preview)

        self._set_combo_text(self.physics_editor_mode, self.physics_editor.mode)
        self._set_combo_text(self.physics_editor_reference, self.physics_editor.reference_list)
        self.physics_editor_default_cut.setText(self.physics_editor.default_cut)
        self.physics_editor_biasing.setChecked(self.physics_editor.enable_biasing_physics)

        self.scoring_editor_enabled.setChecked(self.scoring_editor.enabled)
        self.scoring_editor_hits.setChecked(self.scoring_editor.hits)
        self.scoring_editor_event_edep.setChecked(self.scoring_editor.event_edep)
        self.scoring_editor_edep.setChecked(self.scoring_editor.edep)
        self.scoring_editor_raw_hist.setChecked(self.scoring_editor.raw_histogram)
        self.scoring_editor_weighted_hist.setChecked(self.scoring_editor.weighted_histogram)
        self.scoring_editor_bins.setValue(self.scoring_editor.hist_bins)
        self.scoring_editor_min.setText(self.scoring_editor.hist_min)
        self.scoring_editor_max.setText(self.scoring_editor.hist_max)
        self.scoring_editor_volume_summary.setChecked(self.scoring_editor.volume_summary)
        self.scoring_editor_particle_summary.setChecked(self.scoring_editor.particle_summary)
        self.scoring_editor_auto_create.setChecked(self.scoring_editor.auto_create_default_scorers)
        self._building = False
        self._sync_sps_summary_widgets()
        self._validate_sps_editors()

    def _update_sps_from_widgets(self) -> None:
        if self._building:
            return
        self.source_editor.preset = self.source_editor_preset.currentText().strip()
        self.source_editor.particle = self.source_editor_particle.text().strip()
        self.source_editor.energy = self.source_editor_energy.text().strip()
        self.source_editor.position_mode = self.source_editor_position_type.currentText().strip()
        self.source_editor.position_type = self.source_editor.position_mode
        self.source_editor.source_shape = self.source_editor_shape.currentText().strip()
        self.source_editor.position = self.source_editor_position.text().strip()
        self.source_editor.radius = self.source_editor_radius.text().strip()
        self.source_editor.inner_radius = self.source_editor_inner_radius.text().strip()
        self.source_editor.halfx = self.source_editor_halfx.text().strip()
        self.source_editor.halfy = self.source_editor_halfy.text().strip()
        self.source_editor.normal = self.source_editor_normal.text().strip()
        self.source_editor.confine_volume = self.source_editor_confine_volume.text().strip()
        self.source_editor.direction = self.source_editor_direction.text().strip()
        self.source_editor.angular_mode = self.source_editor_angular_mode.currentText().strip()
        self.source_editor.theta_min = self.source_editor_theta_min.text().strip()
        self.source_editor.theta_max = self.source_editor_theta_max.text().strip()
        self.source_editor.phi_min = self.source_editor_phi_min.text().strip()
        self.source_editor.phi_max = self.source_editor_phi_max.text().strip()
        self.source_editor.cone_half_angle = self.source_editor_cone_half_angle.text().strip()
        self.source_editor.focus_point = self.source_editor_focus_point.text().strip()
        self.source_editor.preview_ray_count = self.source_editor_preview_rays.value()
        self.source_editor.random_seed_preview = self.source_editor_preview_seed.value()
        self.source_editor.is_dirty = True

        self.physics_editor.mode = self.physics_editor_mode.currentText().strip()
        self.physics_editor.reference_list = self.physics_editor_reference.currentText().strip()
        self.physics_editor.default_cut = self.physics_editor_default_cut.text().strip()
        self.physics_editor.enable_biasing_physics = self.physics_editor_biasing.isChecked()
        self.physics_editor.is_dirty = True

        self.scoring_editor.enabled = self.scoring_editor_enabled.isChecked()
        self.scoring_editor.hits = self.scoring_editor_hits.isChecked()
        self.scoring_editor.event_edep = self.scoring_editor_event_edep.isChecked()
        self.scoring_editor.edep = self.scoring_editor_edep.isChecked()
        self.scoring_editor.raw_histogram = self.scoring_editor_raw_hist.isChecked()
        self.scoring_editor.weighted_histogram = self.scoring_editor_weighted_hist.isChecked()
        self.scoring_editor.hist_bins = self.scoring_editor_bins.value()
        self.scoring_editor.hist_min = self.scoring_editor_min.text().strip()
        self.scoring_editor.hist_max = self.scoring_editor_max.text().strip()
        self.scoring_editor.volume_summary = self.scoring_editor_volume_summary.isChecked()
        self.scoring_editor.particle_summary = self.scoring_editor_particle_summary.isChecked()
        self.scoring_editor.auto_create_default_scorers = self.scoring_editor_auto_create.isChecked()
        self.scoring_editor.is_dirty = True
        self._sync_sps_summary_widgets()
        self._validate_sps_editors()
        self._emit_changed()

    def _update_sps_from_summary_widgets(self) -> None:
        if self._building:
            return
        self.source_editor.preset = self.source_preset.currentText().strip()
        self.source_editor.particle = self.source_particle.text().strip()
        self.source_editor.energy = self.source_energy.text().strip()
        self.source_editor.position = self.source_position.text().strip()
        self.source_editor.direction = self.source_direction.text().strip()
        self.source_editor.position_mode = "point"
        self.source_editor.position_type = "point"
        self.source_editor.source_shape = "point"
        self.source_editor.angular_mode = "fixed"
        self.physics_editor.reference_list = self.physics_reference.text().strip()
        self.physics_editor.default_cut = self.default_cut.text().strip()
        self.physics_editor.enable_biasing_physics = self.enable_biasing.isChecked()
        self.scoring_editor.enabled = self.scoring_enabled.isChecked()
        self.scoring_editor.hits = self.scoring_hits.isChecked()
        self.scoring_editor.event_edep = self.scoring_event_edep.isChecked()
        self.scoring_editor.edep = self.scoring_edep.isChecked()
        self.scoring_editor.hist_bins = self.hist_bins.value()
        self.scoring_editor.hist_min = self.hist_min.text().strip()
        self.scoring_editor.hist_max = self.hist_max.text().strip()
        self.source_editor.is_dirty = True
        self.physics_editor.is_dirty = True
        self.scoring_editor.is_dirty = True
        self._populate_sps_editors()
        self._emit_changed()

    def _sync_sps_summary_widgets(self) -> None:
        self._building = True
        self._set_combo_text(self.source_preset, self.source_editor.preset)
        self.source_particle.setText(self.source_editor.particle)
        self.source_energy.setText(self.source_editor.energy)
        self.source_position.setText(self.source_editor.position)
        self.source_direction.setText(self.source_editor.direction)
        self.physics_reference.setText(self.physics_editor.reference_list)
        self.default_cut.setText(self.physics_editor.default_cut)
        self.enable_biasing.setChecked(self.physics_editor.enable_biasing_physics)
        self.scoring_enabled.setChecked(self.scoring_editor.enabled)
        self.scoring_hits.setChecked(self.scoring_editor.hits)
        self.scoring_event_edep.setChecked(self.scoring_editor.event_edep)
        self.scoring_edep.setChecked(self.scoring_editor.edep)
        self.hist_bins.setValue(self.scoring_editor.hist_bins)
        self.hist_min.setText(self.scoring_editor.hist_min)
        self.hist_max.setText(self.scoring_editor.hist_max)
        self._building = False

    def _validate_sps_editors(self) -> None:
        validate_source_model(self.source_editor)
        validate_physics_model(self.physics_editor)
        validate_scoring_model(self.scoring_editor)
        self.source_status_label.setText("Source: " + self._status_text(self.source_editor.errors, self.source_editor.warnings))
        self.physics_status_label.setText("Physics: " + self._status_text(self.physics_editor.errors, self.physics_editor.warnings))
        self.scoring_status_label.setText("Scoring: " + self._status_text(self.scoring_editor.errors, self.scoring_editor.warnings))
        self.source_editor_messages.setPlainText(self._prefixed_messages("SOURCE", self.source_editor.errors, self.source_editor.warnings))
        self.physics_editor_messages.setPlainText(self._prefixed_messages("PHYSICS", self.physics_editor.errors, self.physics_editor.warnings))
        self.scoring_editor_messages.setPlainText(self._prefixed_messages("SCORING", self.scoring_editor.errors, self.scoring_editor.warnings))
        self._validate_geometry_editor()
        self._update_main_ini_preview()
        self._update_workspace_summary()

    def _status_text(self, errors: list[str], warnings: list[str]) -> str:
        if errors:
            return "ERROR"
        if warnings:
            return "WARN"
        return "OK"

    def _prefixed_messages(self, tag: str, errors: list[str], warnings: list[str]) -> str:
        lines = [f"[{tag}][ERROR] {item}" for item in errors]
        lines.extend(f"[{tag}][WARN] {item}" for item in warnings)
        if not lines:
            lines.append(f"[{tag}][INFO] OK")
        return "\n".join(lines)

    def _update_main_ini_preview(self) -> None:
        fake_package = RunPackage(
            package_dir="<package>",
            config_dir="<package>/config",
            macro_dir="<package>/macros",
            logs_dir="<package>/logs",
            output_dir="<package>/output",
            main_ini_path="<package>/config/main.ini",
            run_macro_path="<package>/macros/run.mac",
            validation_report_path="<package>/validation_report.txt",
            project_snapshot_path="<package>/project_snapshot.json",
            materials_ini_path="<package>/config/materials/material.ini",
            geometry_ini_path="<package>/config/geometry/geometry.ini",
        )
        try:
            text = build_main_ini_text(
                package=fake_package,
                run=self.run_settings(),
                geometry=self.geometry_settings(),
                source=self.source_settings(),
                physics=self.physics_settings(),
                scoring=self.scoring_settings(),
                source_model=self.source_editor,
                physics_model=self.physics_editor,
                scoring_model=self.scoring_editor,
            )
        except Exception as exc:  # noqa: BLE001
            text = f"Generated main.ini preview unavailable:\n{exc}"
        self.generated_main_ini_raw.setPlainText(text)

    def reload_materials(self) -> None:
        path = self.materials_config.text().strip()
        self.materials_summary = parse_materials(path) if path else None
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
        self._selected_material_row = -1
        self._populate_material_editor()
        self.materials_messages.setPlainText(self._messages_text(self.materials_summary.errors, self.materials_summary.warnings))
        self.materials_raw.setPlainText(self._preview_text(self.materials_summary.raw_text))
        self._update_workspace_summary()

    def reload_geometry(self) -> None:
        path = self.geometry_config.text().strip()
        self.geometry_summary = parse_geometry(path) if path else None
        self.geometry_table.setRowCount(0)
        self.boolean_table.setRowCount(0)
        self.geometry_messages.clear()
        self.geometry_raw.clear()
        if not self.geometry_summary:
            self.geometry_document = GeometryDocument()
            set_geometry_mode(self.geometry_document, self.geometry_template.currentText())
            self._populate_geometry_editor()
            self.geometry_count_label.setText("Volumes: 0 entries | Preview only")
            self.boolean_count_label.setText("Boolean ops: 0 entries | Preview only")
            self._update_workspace_summary()
            return
        self.geometry_document = geometry_document_from_summary(self.geometry_summary, self.geometry_template.currentText())
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

    def _populate_material_editor(self) -> None:
        refs = geometry_material_refs(self.geometry_document) if self.geometry_document.is_dirty else (
            self.geometry_summary.material_refs if self.geometry_summary else None
        )
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
        self.materials_count_label.setText(
            f"Materials: {len(self.material_document.rows)} rows, "
            f"{sum(1 for row in self.material_document.rows if row.enabled)} enabled | "
            f"{len(self.material_document.errors)} errors, {len(self.material_document.warnings)} warnings | "
            f"{'Dirty' if self.material_document.is_dirty else 'Clean'}"
        )
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

    def _add_material(self, mode: str) -> None:
        row = add_default_row(self.material_document, mode)
        self._selected_material_row = self.material_document.rows.index(row)
        self._populate_material_editor()
        self.materials_table.selectRow(self._selected_material_row)
        self._emit_changed()

    def _duplicate_material(self) -> None:
        row = self.materials_table.currentRow()
        duplicated = duplicate_row(self.material_document, row)
        if duplicated is None:
            return
        self._selected_material_row = self.material_document.rows.index(duplicated)
        self._populate_material_editor()
        self.materials_table.selectRow(self._selected_material_row)
        self._emit_changed()

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
        validate_material_document(
            self.material_document,
            geometry_material_refs=self.geometry_summary.material_refs if self.geometry_summary else None,
        )
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

    def _messages_text(self, errors: list[str], warnings: list[str]) -> str:
        lines: list[str] = []
        if errors:
            lines.extend(f"[ERROR] {item}" for item in errors)
        if warnings:
            lines.extend(f"[WARN] {item}" for item in warnings)
        if not lines:
            lines.append("[INFO] No messages.")
        return "\n".join(lines)

    def _preview_text(self, text: str) -> str:
        limit = 2 * 1024 * 1024
        if len(text.encode("utf-8", errors="replace")) > limit:
            return text[:limit] + "\n\n... raw preview truncated at 2 MB ..."
        return text

    def _update_workspace_summary(self) -> None:
        material_count = len(self.material_document.rows)
        volume_count = len(self.geometry_summary.volumes) if self.geometry_summary else 0
        boolean_count = len(self.geometry_summary.boolean_ops) if self.geometry_summary else 0
        warning_count = len(self.material_document.warnings) + (
            len(self.geometry_summary.warnings) if self.geometry_summary else 0
        ) + len(self.geometry_document.warnings)
        error_count = len(self.material_document.errors) + (
            len(self.geometry_summary.errors) if self.geometry_summary else 0
        ) + len(self.geometry_document.errors)
        self.workspace_summary.setText(
            f"Materials: {material_count} entries | Geometry: {volume_count} volumes, {boolean_count} boolean ops | "
            f"Messages: {error_count} errors, {warning_count} warnings | Materials: {'Dirty' if self.material_document.is_dirty else 'Clean'} | "
            f"Geometry: {self.geometry_document.mode} {'Dirty' if self.geometry_document.is_dirty else 'Clean'} | "
            f"Source: {self._status_text(self.source_editor.errors, self.source_editor.warnings)} | "
            f"Physics: {self._status_text(self.physics_editor.errors, self.physics_editor.warnings)} | "
            f"Scoring: {self._status_text(self.scoring_editor.errors, self.scoring_editor.warnings)}"
        )
