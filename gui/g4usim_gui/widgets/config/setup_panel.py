"""The Configuration page's left column: its widget and its logic."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import set_schema_tooltip, ui_format, ui_text
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.editors.source_physics_scoring_model import SOURCE_PRESETS
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.widgets.ui_helpers import CollapsibleSection, create_hint_label, make_path_row


class SetupPanel(QScrollArea):
    """The left column: run settings, input files, quick source/physics/scoring fields and actions."""

    SOURCE_PRESETS = ["proton_beam", "mono_proton", "neutron_beam", "gamma_beam", "isotropic_neutron", "plane_proton_beam"]

    def __init__(self, browse_materials, browse_geometry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._browse_materials = browse_materials
        self._browse_geometry = browse_geometry
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
        # the INI field each control writes: its tooltip comes from the configuration schema (E2)
        for widget, field in ((self.run_name, "name"), (self.threads, "threads"), (self.seed, "seed"),
                              (self.check_overlaps, "check_overlaps"), (self.dry_run, "dry_run")):
            set_schema_tooltip(widget, "run", field)

        self.materials_config = QLineEdit()
        self.geometry_config = QLineEdit()
        self.geometry_template = QComboBox()
        self.reload_materials_button = QPushButton("Reload materials")
        self.reload_geometry_button = QPushButton("Reload geometry")
        self.source_preset = QComboBox()
        self.source_preset.addItems(self.SOURCE_PRESETS)
        self.source_particle = QLineEdit("proton")
        self.source_energy = QLineEdit("10 MeV")
        self.source_position = QLineEdit("0,0,-1 mm")
        self.source_direction = QLineEdit("0,0,1")
        self.physics_reference = QLineEdit("FTFP_BERT_EMZ")
        self.default_cut = QLineEdit("1 mm")
        self.enable_biasing = QCheckBox()
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
        # Use the same field hints in Setup and Run Config, including language changes.
        for widget, section, key in (
            (self.source_energy, "source", "energy"),
            (self.source_particle, "source", "particle"),
            (self.source_preset, "source", "preset"),
            (self.source_direction, "source", "direction"),
            (self.physics_reference, "physics", "reference"),
            (self.default_cut, "physics", "default_cut"),
            (self.hist_bins, "scoring.edep", "bins"),
            (self.hist_min, "scoring.edep", "min"),
            (self.hist_max, "scoring.edep", "max"),
        ):
            set_schema_tooltip(widget, section, key)
        self.validate_button = QPushButton("Validate")
        self.generate_button = QPushButton("Generate Package")
        self.generate_run_button = QPushButton("Generate and Run")
        self.package_label = QLabel("Generated package: <none>")
        self.package_label.setWordWrap(True)
        content = QWidget()
        content.setObjectName("setupPanel")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)
        content_layout.addWidget(create_hint_label("Setup generates a reproducible run package. Material and geometry previews are read-only in this round."))
        self.setup_sections = [CollapsibleSection(group) for group in (
            self._run_group(), self._input_group(), self._source_group(), self._physics_group(),
            self._scoring_group())]
        for section in self.setup_sections:
            content_layout.addWidget(section)

        buttons = QGridLayout()
        buttons.setHorizontalSpacing(8)
        buttons.setVerticalSpacing(8)
        buttons.addWidget(self.validate_button, 0, 0)
        buttons.addWidget(self.generate_button, 0, 1)
        buttons.addWidget(self.generate_run_button, 1, 0, 1, 2)
        actions = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions)
        actions_layout.addLayout(buttons)
        actions_layout.addWidget(self.package_label)
        content_layout.addWidget(actions)
        content_layout.addStretch(1)

        scroll = self
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        # wide enough for the widest row (path + Browse), so nothing is clipped without a scroll bar
        scroll.setMinimumWidth(content.minimumSizeHint().width() + scroll.verticalScrollBar().sizeHint().width() + 4)
        self.setup_scroll = scroll

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
        form.addRow(ui_text("Biasing hook (external input only)"), self.enable_biasing)
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


class SetupMixin:
    """Setup-column logic; mixed into ConfigBuilderPage."""

    def _connect_setup_actions(self) -> None:
        """Actions and reload buttons."""
        self.validate_button.clicked.connect(self.validateRequested.emit)
        self.generate_button.clicked.connect(lambda: self.generatePackageRequested.emit(False))
        self.generate_run_button.clicked.connect(lambda: self.generatePackageRequested.emit(True))
        self.reload_materials_button.clicked.connect(self.reload_materials)
        self.reload_geometry_button.clicked.connect(self.reload_geometry)

    def _connect_setup_changes(self) -> None:
        """Run, input and quick fields that change the package."""
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
        self.geometry_template.currentIndexChanged.connect(self._on_geometry_template_changed)
        self.source_preset.currentTextChanged.connect(self._emit_changed)

    def set_run_defaults(self, project: G4USimProject) -> None:
        """Apply flat Project-page run defaults without replacing editor models."""
        self._building = True
        self.run_name.setText(project.runName or project.projectName or "gui_run")
        self.threads.setValue(max(1, int(project.threads)))
        self.seed.setText(str(project.seed) if project.seed else "")
        self._building = False

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
            template=self._geometry_template_token(),
            config_path=self.geometry_config.text().strip(),
        )

    def source_settings(self) -> SourceSettings:
        return self.source_editor.to_settings()

    def physics_settings(self) -> PhysicsSettings:
        return self.physics_editor.to_settings()

    def scoring_settings(self) -> ScoringSettings:
        return self.scoring_editor.to_settings()

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

    def _geometry_template_token(self) -> str:
        return str(self.geometry_template.currentData() or "").strip()

    def _set_geometry_template_token(self, token: str) -> None:
        normalized = token.strip() or "hierarchical"
        index = self.geometry_template.findData(normalized)
        if index < 0:
            self._populate_geometry_template_options(normalized)
            index = self.geometry_template.findData(normalized)
        self.geometry_template.setCurrentIndex(max(0, index))

    def _populate_geometry_template_options(self, selected_token: str = "") -> None:
        token = selected_token.strip() or self._geometry_template_token() or "hierarchical"
        blocked = self.geometry_template.blockSignals(True)
        self.geometry_template.clear()
        for machine_value, label in self.GEOMETRY_PRIMARY_OPTIONS:
            self.geometry_template.addItem(ui_text(label), machine_value)
        for machine_value, label in self.GEOMETRY_PLANNED_OPTIONS:
            index = self.geometry_template.count()
            self.geometry_template.addItem(ui_text(label), machine_value)
            model = self.geometry_template.model()
            if isinstance(model, QStandardItemModel):
                item = model.item(index)
                if item is not None:
                    item.setEnabled(False)
        known_values = {
            machine_value for machine_value, _label in self.GEOMETRY_PRIMARY_OPTIONS + self.GEOMETRY_PLANNED_OPTIONS
        }
        if token not in known_values:
            self.geometry_template.insertSeparator(self.geometry_template.count())
            label = self.GEOMETRY_COMPATIBILITY_LABELS.get(token)
            display = ui_text(label) if label else ui_format("Compatibility mode: {token}", token=token)
            self.geometry_template.addItem(display, token)
        index = self.geometry_template.findData(token)
        if index < 0 or token == "external_geometry_import":
            index = self.geometry_template.findData("hierarchical")
        self.geometry_template.setCurrentIndex(max(0, index))
        self.geometry_template.blockSignals(blocked)
