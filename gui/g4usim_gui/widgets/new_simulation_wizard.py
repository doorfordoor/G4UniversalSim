"""Guided "New simulation" wizard (roadmap C2): scenario -> geometry -> source -> run.

The dialog only edits a core.wizard.WizardSpec; core.wizard.build() turns it into the
Configuration page's editor models, so the generated package goes through the same
validation and writers as the full editors (which remain the advanced mode).
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from g4usim_gui.core import icons
from g4usim_gui.core import wizard as wz
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.theme import current_colors
from g4usim_gui.core.diagnostics import emit_diagnostic
from g4usim_gui.validators.config_validator import ValidationReport
from g4usim_gui.widgets.diagnostic_panel import DiagnosticPanel
from g4usim_gui.widgets.form_diagnostics import FormDiagnosticController
from g4usim_gui.widgets.qt_data import combo_data

SCENARIO_TEXT = {
    "single_target": ("Single target", "One sensitive box: energy deposit, dose and fluence in a slab of any material."),
    "depth_dose": ("Depth-dose in a phantom", "A phantom cut into sensitive slabs; the dose per slab is the depth-dose curve (Results / Plots)."),
    "shielding": ("Shielding slab", "A shield followed by a sensitive detector 1 mm behind it: transmitted dose and fluence."),
    "silicon_detector": ("Silicon detector", "A thin silicon pad: energy deposit spectrum of charged particles."),
    "gamma_spectrometer": ("Gamma spectrometer", "A scintillator cylinder with an isotropic point source: pulse-height spectrum from per-event deposits."),
}
SCENARIO_ICONS = {"single_target": "target", "depth_dose": "layers", "shielding": "shield",
                  "silicon_detector": "chip", "gamma_spectrometer": "spectrum"}
SOURCE_TEXT = {"pencil": "Pencil beam (point, along +z)", "broad": "Broad beam (rectangle, along +z)",
               "isotropic": "Isotropic point source"}


def _combo(values, current: str, labels: dict | None = None) -> QComboBox:
    combo = QComboBox()
    for value in values:
        combo.addItem(ui_text(labels[value]) if labels else value, value)
    combo.setCurrentIndex(max(0, combo.findData(current)))
    return combo


def _length(maximum: float = 1e5) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setDecimals(4)
    box.setRange(0.0001, maximum)
    box.setSuffix(" mm")
    return box


class ScenarioPage(QWizardPage):
    def __init__(self, wizard: "NewSimulationWizard") -> None:
        super().__init__()
        self.setTitle(ui_text("Scenario"))
        self.setSubTitle(ui_text("Choose what to simulate. Every value can be changed later in the full editors."))
        self._wizard = wizard
        self.list = QListWidget()
        self.list.setIconSize(QSize(24, 24))
        self.list.setSpacing(2)
        accent = current_colors().accent
        for key in wz.SCENARIOS:
            title, description = SCENARIO_TEXT[key]
            item = QListWidgetItem(icons.icon(SCENARIO_ICONS[key], accent, 24), ui_text(title))
            item.setSizeHint(QSize(0, 40))
            item.setData(256, key)   # Qt.UserRole
            item.setToolTip(ui_text(description))
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.name = QLineEdit(wz.default_spec(wz.SCENARIOS[0]).project_name)
        form = QFormLayout()
        form.addRow(ui_text("Simulation name"), self.name)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.description)
        layout.addLayout(form)
        self.list.currentRowChanged.connect(self._changed)
        self._changed()

    def scenario(self) -> str:
        item = self.list.currentItem()
        return item.data(256) if item else wz.SCENARIOS[0]

    def _changed(self) -> None:
        key = self.scenario()
        self.description.setText(ui_text(SCENARIO_TEXT[key][1]))
        previous = self._wizard.spec.scenario
        if key != previous:
            self._wizard.spec = wz.default_spec(key)
            if self.name.text().strip() in ("", previous, wz.default_spec(previous).project_name):
                self.name.setText(self._wizard.spec.project_name)

    def validatePage(self) -> bool:   # noqa: N802 - Qt override
        self._wizard.spec.project_name = self.name.text().strip()
        return bool(self._wizard.spec.project_name)


class GeometryPage(QWizardPage):
    def __init__(self, wizard: "NewSimulationWizard") -> None:
        super().__init__()
        self.setTitle(ui_text("Materials and geometry"))
        self._wizard = wizard
        self.target_material = QComboBox()
        self.world_material = QComboBox()
        self.thickness = _length()
        self.lateral = _length()
        self.slabs = QSpinBox()
        self.slabs.setRange(1, 200)
        self.detector_material = QComboBox()
        self.detector_thickness = _length()
        self.form = QFormLayout(self)
        self.thickness_label = QLabel()
        self.lateral_label = QLabel()
        self.slabs_label = QLabel(ui_text("Number of slabs"))
        self.detector_label = QLabel(ui_text("Detector material"))
        self.detector_thickness_label = QLabel(ui_text("Detector thickness"))
        self.form.addRow(ui_text("Material"), self.target_material)
        self.form.addRow(ui_text("World material"), self.world_material)
        self.form.addRow(self.thickness_label, self.thickness)
        self.form.addRow(self.lateral_label, self.lateral)
        self.form.addRow(self.slabs_label, self.slabs)
        self.form.addRow(self.detector_label, self.detector_material)
        self.form.addRow(self.detector_thickness_label, self.detector_thickness)
        for combo, values in ((self.target_material, wz.MATERIALS), (self.world_material, wz.WORLD_MATERIALS),
                              (self.detector_material, wz.MATERIALS)):
            for value in values:
                combo.addItem(value, value)

    def initializePage(self) -> None:   # noqa: N802 - Qt override
        spec = self._wizard.spec
        self.setSubTitle(ui_text("Only Geant4 NIST materials are offered; custom materials use the Materials editor."))
        gamma = spec.scenario == "gamma_spectrometer"
        self.thickness_label.setText(ui_text("Crystal length" if gamma else "Thickness"))
        self.lateral_label.setText(ui_text("Crystal diameter" if gamma else "Lateral size"))
        for widget in (self.slabs, self.slabs_label):
            widget.setVisible(spec.scenario == "depth_dose")
        for widget in (self.detector_material, self.detector_label, self.detector_thickness,
                       self.detector_thickness_label):
            widget.setVisible(spec.scenario == "shielding")
        self.target_material.setCurrentIndex(self.target_material.findData(spec.target_material))
        self.world_material.setCurrentIndex(self.world_material.findData(spec.world_material))
        self.detector_material.setCurrentIndex(self.detector_material.findData(spec.detector_material))
        self.thickness.setValue(spec.thickness_mm)
        self.lateral.setValue(spec.lateral_mm)
        self.slabs.setValue(spec.slabs)
        self.detector_thickness.setValue(spec.detector_thickness_mm)

    def validatePage(self) -> bool:   # noqa: N802 - Qt override
        spec = self._wizard.spec
        spec.target_material = self.target_material.currentData()
        spec.world_material = self.world_material.currentData()
        spec.detector_material = self.detector_material.currentData()
        spec.thickness_mm = self.thickness.value()
        spec.lateral_mm = self.lateral.value()
        spec.slabs = self.slabs.value()
        spec.detector_thickness_mm = self.detector_thickness.value()
        return True


class SourcePage(QWizardPage):
    def __init__(self, wizard: "NewSimulationWizard") -> None:
        super().__init__()
        self.setTitle(ui_text("Source"))
        self.setSubTitle(ui_text("The source sits 10 mm in front of the target and points along +z."))
        self._wizard = wizard
        self.particle = QComboBox()
        for value in wz.PARTICLES:
            self.particle.addItem(value, value)
        self.energy = QDoubleSpinBox()
        self.energy.setDecimals(4)
        self.energy.setRange(0.0001, 1e6)
        self.energy.setSuffix(" MeV")
        self.kind = QComboBox()
        for value in wz.SOURCE_KINDS:
            self.kind.addItem(ui_text(SOURCE_TEXT[value]), value)
        form = QFormLayout(self)
        form.addRow(ui_text("Particle"), self.particle)
        form.addRow(ui_text("Energy"), self.energy)
        form.addRow(ui_text("Source type"), self.kind)

    def initializePage(self) -> None:   # noqa: N802 - Qt override
        spec = self._wizard.spec
        self.particle.setCurrentIndex(self.particle.findData(spec.particle))
        self.energy.setValue(spec.energy_MeV)
        self.kind.setCurrentIndex(self.kind.findData(spec.source_kind))

    def validatePage(self) -> bool:   # noqa: N802 - Qt override
        spec = self._wizard.spec
        spec.particle = self.particle.currentData()
        spec.energy_MeV = self.energy.value()
        spec.source_kind = self.kind.currentData()
        return True


class RunPage(QWizardPage):
    def __init__(self, wizard: "NewSimulationWizard") -> None:
        super().__init__()
        self.setTitle(ui_text("Physics, outputs and run"))
        self._wizard = wizard
        self._loading = False   # widgets are being filled from the spec; do not read them back yet
        self.physics = QComboBox()
        for value in wz.PHYSICS:
            self.physics.addItem(value, value)
        self.events = QSpinBox()
        self.events.setRange(1, 1_000_000_000)
        self.threads = QSpinBox()
        self.threads.setRange(1, 256)
        self.seed = QLineEdit()
        self.hits = QCheckBox(ui_text("Step hits (large files)"))
        self.event_edep = QCheckBox(ui_text("Per-event energy deposit"))
        self.dose = QCheckBox(ui_text("Dose in sensitive volumes"))
        self.fluence = QCheckBox(ui_text("Track-length fluence"))
        self.run_after = QCheckBox(ui_text("Generate the package and run when finished"))
        self.run_after.setChecked(True)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMinimumHeight(100)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.addRow(ui_text("Physics list"), self.physics)
        form.addRow(ui_text("Events"), self.events)
        form.addRow(ui_text("Threads"), self.threads)
        form.addRow(ui_text("Seed"), self.seed)
        outputs = QWidget()
        outputs_layout = QVBoxLayout(outputs)
        outputs_layout.setContentsMargins(0, 0, 0, 0)
        for box in (self.event_edep, self.dose, self.fluence, self.hits):
            outputs_layout.addWidget(box)
        form.addRow(ui_text("Outputs"), outputs)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.addLayout(form)
        layout.addWidget(QLabel(ui_text("Summary")))
        layout.addWidget(self.summary, 1)
        self.diagnostics_panel = DiagnosticPanel(self)
        self.diagnostics_panel.hide()
        layout.addWidget(self.diagnostics_panel)
        layout.addWidget(self.run_after)
        self.content_scroll = QScrollArea(self)
        self.content_scroll.setObjectName("wizardRunScroll")
        self.content_scroll.setFrameShape(QFrame.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.content_scroll)
        for widget in (self.physics, self.events, self.threads, self.seed, self.hits, self.event_edep, self.dose,
                       self.fluence):
            signal = getattr(widget, "currentIndexChanged", None) or getattr(widget, "valueChanged", None) \
                or getattr(widget, "textChanged", None) or widget.toggled
            signal.connect(self._update)

    def initializePage(self) -> None:   # noqa: N802 - Qt override
        spec = self._wizard.spec
        self._loading = True
        self.physics.setCurrentIndex(self.physics.findData(spec.physics))
        self.events.setValue(spec.events)
        self.threads.setValue(spec.threads)
        self.seed.setText("" if spec.seed is None else str(spec.seed))
        self.hits.setChecked(spec.hits)
        self.event_edep.setChecked(spec.event_edep)
        self.dose.setChecked(spec.dose)
        self.fluence.setChecked(spec.fluence)
        self._loading = False
        self._update()

    def _read_records(self) -> list[tuple[str, str, str, dict]]:
        spec = self._wizard.spec
        spec.physics = self.physics.currentData()
        spec.events = self.events.value()
        spec.threads = self.threads.value()
        spec.hits, spec.event_edep = self.hits.isChecked(), self.event_edep.isChecked()
        spec.dose, spec.fluence = self.dose.isChecked(), self.fluence.isChecked()
        errors = []
        text = self.seed.text().strip()
        try:
            spec.seed = int(text) if text else None
        except ValueError:
            errors.append(('seed', 'seed_parse', "The seed must be an integer.", {}))
        return errors + wz.validate_spec_records(spec)

    def _read(self) -> list[tuple[str, dict]]:
        return [(template, values) for _field, _code, template, values in self._read_records()]

    def _update(self) -> None:
        if self._loading:
            return
        records = self._read_records()
        errors = [(template, values) for _field, _code, template, values in records]
        report = ValidationReport()
        for field, code, template, values in records:
            emit_diagnostic(report, 'wizard.' + code, 'error', ui_format(template, **values),
                            origin='wizard_validation', editor='wizard', field=field,
                            message_key=template, params=values)
        if hasattr(self._wizard, 'diagnostic_controller'):
            self._wizard.diagnostic_controller.set_report(report)
            self.diagnostics_panel.setVisible(bool(report.diagnostics))
        lines = [ui_format(t, **v) for t, v in wz.summary(self._wizard.spec)]
        if errors:
            lines += ["", ui_text("Cannot finish:")] + [ui_format(t, **v) for t, v in errors]
        self.summary.setPlainText("\n".join(lines))
        self.completeChanged.emit()

    def isComplete(self) -> bool:   # noqa: N802 - Qt override
        return not self._loading and not self._read()


class NewSimulationWizard(QWizard):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(ui_text("New simulation"))
        self.spec = wz.default_spec(wz.SCENARIOS[0])
        self.scenario_page = ScenarioPage(self)
        self.geometry_page = GeometryPage(self)
        self.source_page = SourcePage(self)
        self.run_page = RunPage(self)
        for page in (self.scenario_page, self.geometry_page, self.source_page, self.run_page):
            self.addPage(page)
        self._diagnostic_navigation = False
        self._diagnostic_fields = {
            'scenario': self.scenario_page.list, 'project_name': self.scenario_page.name,
            'target_material': self.geometry_page.target_material,
            'world_material': self.geometry_page.world_material,
            'detector_material': self.geometry_page.detector_material,
            'thickness_mm': self.geometry_page.thickness, 'lateral_mm': self.geometry_page.lateral,
            'detector_thickness_mm': self.geometry_page.detector_thickness, 'slabs': self.geometry_page.slabs,
            'particle': self.source_page.particle, 'energy_MeV': self.source_page.energy,
            'source_kind': self.source_page.kind, 'physics': self.run_page.physics,
            'events': self.run_page.events, 'threads': self.run_page.threads,
            'seed': self.run_page.seed, 'outputs': self.run_page.event_edep,
        }
        self.diagnostic_controller = FormDiagnosticController(
            self, self.run_page.diagnostics_panel, 'wizard', self._diagnostic_fields,
            self._diagnostic_values, reveal=self._reveal_diagnostic_field,
            revealable_ancestors=lambda widget: tuple(self.page(i) for i in self.pageIds()
                                                    if self.page(i).isAncestorOf(widget)))
        self.run_page.diagnostics_panel.revalidateRequested.connect(self.run_page._update)
        self.resize(720, 560)

    def _diagnostic_values(self) -> dict:
        values = {}
        for name, widget in self._diagnostic_fields.items():
            if isinstance(widget, QComboBox):
                values[name] = combo_data(widget)
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QListWidget):
                values[name] = widget.currentRow()
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                values[name] = widget.value()
            else:
                values[name] = widget.text()
        values['outputs'] = [box.isChecked() for box in
                             (self.run_page.event_edep, self.run_page.hits, self.run_page.dose, self.run_page.fluence)]
        return values

    def _reveal_diagnostic_field(self, widget: QWidget) -> bool:
        page_id = next((i for i in self.pageIds() if self.page(i).isAncestorOf(widget)), None)
        if page_id is None or page_id not in self.visitedIds():
            return False
        # A diagnostic jump is presentation only. Normal forward navigation still
        # initializes pages from the wizard model as before.
        self._diagnostic_navigation = True
        try:
            self.setCurrentId(page_id)
        finally:
            self._diagnostic_navigation = False
        return self.currentId() == page_id

    def initializePage(self, page_id: int) -> None:  # noqa: N802
        if not getattr(self, '_diagnostic_navigation', False):
            super().initializePage(page_id)

    def run_after_finish(self) -> bool:
        return self.run_page.run_after.isChecked()

    def result_models(self) -> wz.WizardResult:
        return wz.build(self.spec)
