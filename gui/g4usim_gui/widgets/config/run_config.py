"""Source, Physics and Scoring editors: their widget (the Run Config tab) and logic."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import set_schema_tooltip, ui_text
from g4usim_gui.editors.source_physics_scoring_model import (
    REFERENCE_LIST_CANDIDATES,
    SOURCE_PRESETS,
    validate_physics_model,
    validate_scoring_model,
    validate_source_model,
)
from g4usim_gui.models.package_model import RunPackage
from g4usim_gui.writers.main_ini_writer import build_main_ini_text
from g4usim_gui.widgets.ui_helpers import create_hint_label


class RunConfigEditor(QWidget):
    """Run Config tab: the Source, Physics and Scoring editors."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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
        self.physics_status_label = QLabel("Physics: OK")
        self.physics_editor_mode = QComboBox()
        self.physics_editor_mode.addItems(["reference", "manual"])
        self.physics_editor_reference = QComboBox()
        self.physics_editor_reference.setEditable(True)
        self.physics_editor_reference.addItems(REFERENCE_LIST_CANDIDATES)
        self.physics_editor_default_cut = QLineEdit("1 mm")
        self.physics_editor_biasing = QCheckBox(ui_text("Biasing hook (external input only)"))
        self.physics_editor_messages = QPlainTextEdit()
        self.physics_editor_messages.setReadOnly(True)
        self.scoring_status_label = QLabel("Scoring: OK")
        self.scoring_editor_enabled = QCheckBox("Enable scoring")
        self.scoring_editor_enabled.setChecked(True)
        self.scoring_editor_hits = QCheckBox("Write hits")
        self.scoring_editor_hits.setChecked(True)
        self.scoring_editor_event_edep = QCheckBox("Write event_edep")
        self.scoring_editor_event_edep.setChecked(True)
        self.scoring_editor_edep = QCheckBox("Enable EdepScorer")
        self.scoring_editor_edep.setChecked(True)
        self.scoring_editor_dose = QCheckBox(ui_text("Enable sensitive-volume Dose (Gy, prototype)"))
        self.scoring_editor_dose.setChecked(False)
        self.scoring_editor_fluence = QCheckBox(ui_text("Enable track-length Fluence (mm^-2, prototype)"))
        self.scoring_editor_fluence.setChecked(False)
        self.scoring_editor_raw_hist = QCheckBox("Raw edep histogram")
        self.scoring_editor_raw_hist.setChecked(True)
        self.scoring_editor_weighted_hist = QCheckBox("Weighted edep histogram")
        self.scoring_editor_weighted_hist.setChecked(True)
        self.scoring_editor_trajectories = QSpinBox()
        self.scoring_editor_trajectories.setRange(0, 1000)
        self.scoring_editor_trajectories.setSpecialValueText(ui_text("off"))
        set_schema_tooltip(self.scoring_editor_trajectories, "output", "trajectories")
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
        # Use the same field hints in Setup and Run Config, including language changes.
        for widget, section, key in (
            (self.source_editor_energy, "source", "energy"),
            (self.source_editor_preset, "source", "preset"),
            (self.source_editor_particle, "source", "particle"),
            (self.source_editor_direction, "source", "direction"),
            (self.source_editor_radius, "source", "radius"),
            (self.source_editor_halfx, "source", "halfx"),
            (self.source_editor_halfy, "source", "halfy"),
            (self.physics_editor_reference, "physics", "reference"),
            (self.physics_editor_default_cut, "physics", "default_cut"),
            (self.scoring_editor_bins, "scoring.edep", "bins"),
            (self.scoring_editor_min, "scoring.edep", "min"),
            (self.scoring_editor_max, "scoring.edep", "max"),
        ):
            set_schema_tooltip(widget, section, key)
        self.scoring_editor_messages = QPlainTextEdit()
        self.scoring_editor_messages.setReadOnly(True)
        layout = QVBoxLayout(self)
        status = QHBoxLayout()
        status.addWidget(self.source_status_label)
        status.addWidget(self.physics_status_label)
        status.addWidget(self.scoring_status_label)
        status.addStretch(1)
        layout.addLayout(status)
        tabs = QTabWidget()
        self.run_config_tabs = tabs
        tabs.addTab(self._source_editor_tab(), "Source")
        tabs.addTab(self._physics_editor_tab(), "Physics")
        tabs.addTab(self._scoring_editor_tab(), "Scoring")
        layout.addWidget(tabs, 1)

    def _source_editor_tab(self) -> QWidget:
        content = QWidget()
        content.setObjectName("sourceEditorContent")
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
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
        layout.addWidget(create_hint_label("This editor generates point, plane circle, and XY-plane rectangle (halfx/halfy) sources with fixed or isotropic emission. Square, annulus, cone, cosine, and focused modes are preview-only here and blocked from package generation; the backend supports them (and spectra, volume, beam, multi-source, ion and phase-space sources) in a hand-written main INI."))
        layout.addWidget(QLabel("Validation messages"))
        self.source_editor_messages.setMinimumHeight(110)
        layout.addWidget(self.source_editor_messages)

        self.source_editor_scroll = QScrollArea()
        self.source_editor_scroll.setObjectName("sourceEditorScroll")
        self.source_editor_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.source_editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.source_editor_scroll.setWidgetResizable(True)
        self.source_editor_scroll.setWidget(content)
        return self.source_editor_scroll

    def _physics_editor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        form.addRow("Mode", self.physics_editor_mode)
        form.addRow("Reference list", self.physics_editor_reference)
        form.addRow("Default cut", self.physics_editor_default_cut)
        form.addRow("", self.physics_editor_biasing)
        layout.addLayout(form)
        layout.addWidget(create_hint_label(ui_text("Generated packages cannot configure biasing rules. Use external config/macro for process-level biasing.")))
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
            self.scoring_editor_dose,
            self.scoring_editor_fluence,
        ]:
            switch_layout.addWidget(widget)
        trajectories_row = QHBoxLayout()
        trajectories_row.addWidget(QLabel("Particle tracks of the first events"))
        trajectories_row.addWidget(self.scoring_editor_trajectories)
        trajectories_row.addStretch(1)
        switch_layout.addLayout(trajectories_row)
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
        layout.addWidget(create_hint_label(ui_text("Dose and Fluence are experimental sensitive-volume scorers; LET remains unavailable.")))
        layout.addWidget(QLabel("Validation messages"))
        layout.addWidget(self.scoring_editor_messages, 1)
        return tab


class RunConfigMixin:
    """Source/Physics/Scoring logic; mixed into ConfigBuilderPage, which holds the models."""

    def _connect_sps_editor_signals(self) -> None:
        """Source, Physics and Scoring editor fields."""
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
            self.scoring_editor_dose,
            self.scoring_editor_fluence,
            self.scoring_editor_raw_hist,
            self.scoring_editor_weighted_hist,
            self.scoring_editor_volume_summary,
            self.scoring_editor_particle_summary,
            self.scoring_editor_auto_create,
        ]:
            widget.stateChanged.connect(self._update_sps_from_widgets)
        self.scoring_editor_bins.valueChanged.connect(self._update_sps_from_widgets)
        self.scoring_editor_trajectories.valueChanged.connect(self._update_sps_from_widgets)
        self.source_editor_preview_rays.valueChanged.connect(self._update_sps_from_widgets)
        self.source_editor_preview_seed.valueChanged.connect(self._update_sps_from_widgets)

    def _connect_sps_summary_signals(self) -> None:
        """The setup column's quick source/physics/scoring fields."""
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
        self.scoring_editor_dose.setChecked(self.scoring_editor.dose)
        self.scoring_editor_fluence.setChecked(self.scoring_editor.fluence)
        self.scoring_editor_trajectories.setValue(self.scoring_editor.trajectory_events)
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
        self.scoring_editor.dose = self.scoring_editor_dose.isChecked()
        self.scoring_editor.fluence = self.scoring_editor_fluence.isChecked()
        self.scoring_editor.trajectory_events = self.scoring_editor_trajectories.value()
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
        """Mirror the setup column's quick fields into the Source/Physics/Scoring models.

        The setup column only exposes the scalar source fields written below (preset,
        particle, energy, position, direction) plus physics/scoring fields. It has no
        control for the source geometry (``position_mode``/``position_type``/
        ``source_shape``) or for the angular distribution (``angular_mode``/``theta``/
        ``phi``): those belong to the Source editor, and ``main_ini_writer`` derives
        ``position_type``, ``center``, ``halfx``/``halfy`` and ``isotropic`` from them.
        This slot used to force ``point`` geometry and a fixed direction unconditionally,
        so editing e.g. the energy here silently collapsed a configured plane/rectangle
        isotropic source back to a point source with a fixed beam (the run still
        "succeeded", with the wrong physics). Only fields that a setup control actually
        mirrors may be written here; a forced reset would need an explicit condition.
        """
        if self._building:
            return
        self.source_editor.preset = self.source_preset.currentText().strip()
        self.source_editor.particle = self.source_particle.text().strip()
        self.source_editor.energy = self.source_energy.text().strip()
        self.source_editor.position = self.source_position.text().strip()
        self.source_editor.direction = self.source_direction.text().strip()
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
