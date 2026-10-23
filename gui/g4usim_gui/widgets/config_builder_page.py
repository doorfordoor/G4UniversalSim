from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.editors.geometry_editor_model import GeometryDocument
from g4usim_gui.editors.material_editor_model import MaterialDocument
from g4usim_gui.editors.source_physics_scoring_model import (
    PhysicsEditableModel,
    ScoringEditableModel,
    SourceEditableModel,
    SOURCE_PRESETS,
)
from g4usim_gui.parsers.geometry_parser import GeometrySummary
from g4usim_gui.parsers.materials_parser import MaterialsSummary
from g4usim_gui.preview3d.scene_model import PreviewScene
from g4usim_gui.validators.config_validator import ValidationReport, validate_config_builder
from g4usim_gui.widgets.config.setup_panel import SetupPanel, SetupMixin
from g4usim_gui.widgets.config.materials import MaterialsEditor, MaterialsMixin
from g4usim_gui.widgets.config.booleans import BooleansMixin
from g4usim_gui.widgets.config.geometry import GeometryEditor, GeometryMixin
from g4usim_gui.widgets.config.layers import LayersMixin
from g4usim_gui.widgets.config.preview3d import Preview3DPanel, Preview3DMixin
from g4usim_gui.widgets.config.run_config import RunConfigEditor, RunConfigMixin
from g4usim_gui.widgets.config.details import DetailsPanel


class ConfigBuilderPage(SetupMixin, MaterialsMixin, GeometryMixin, LayersMixin, BooleansMixin,
                        Preview3DMixin, RunConfigMixin, QWidget):
    """The Configuration page: the setup column and the editor tabs (roadmap E5 split).

    Each editor lives in widgets/config/<editor>.py as a widget (its controls and layout,
    buildable on its own) plus a mixin with its logic. The page holds the shared state
    (documents and models), composes the widgets and coordinates across editors. The
    editors' controls are also attributes of the page (adopted from each widget), so
    the logic and the rest of the GUI address them as before.
    """

    validateRequested = Signal()
    generatePackageRequested = Signal(bool)
    settingsChanged = Signal()
    backendGeometryRequested = Signal()
    autoBackendGeometryRequested = Signal()   # the 3D tab wants the Geant4 world after a change (G1)

    GEOMETRY_PRIMARY_OPTIONS = (
        ("layered_device", "Layered Model"),
        ("hierarchical", "Hierarchical Model"),
    )
    GEOMETRY_PLANNED_OPTIONS = (
        ("external_geometry_import", "External Geometry Import (Planned)"),
    )
    GEOMETRY_COMPATIBILITY_LABELS = {
        "simple_box": "Single Target Preset (Legacy)",
        "simple": "Single Target Preset (Legacy)",
        "array": "Regular Array Preset (Legacy)",
        "shielding": "Shielding Preset (Legacy)",
        "boolean_hierarchical": "Hierarchical Boolean Alias (Legacy)",
        "hierarchical_boolean": "Hierarchical Boolean Alias (Legacy)",
        "boolean": "Hierarchical Boolean Alias (Legacy)",
        "layered": "Layered Model",
    }
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
        self._selected_layer_row = -1
        self.preview_scene = PreviewScene()
        self.geometry_document = GeometryDocument()
        # debounce: one export after a burst of edits
        self._backend_timer = QTimer(self)
        self._backend_timer.setSingleShot(True)
        self._backend_timer.setInterval(1200)
        self._backend_timer.timeout.connect(self._request_auto_backend_geometry)

        self.setup_panel = SetupPanel(self._browse_materials, self._browse_geometry)
        self._adopt(self.setup_panel)
        self._populate_geometry_template_options("hierarchical")
        self.workspace_summary = QLabel("Materials: 0 | Geometry: 0 volumes, 0 boolean ops | Current mode: Preview only")
        self.workspace_summary.setWordWrap(True)
        # built in the order the tabs always were: later tabs take over widgets shown in two places
        self.materials_editor = MaterialsEditor()
        self._adopt(self.materials_editor)
        self.geometry_editor = GeometryEditor()
        self._adopt(self.geometry_editor)
        self.boolean_tab = self._table_tab(self.boolean_count_label, self.boolean_table)
        self.preview3d_panel = Preview3DPanel()
        self._adopt(self.preview3d_panel)
        self.run_config_editor = RunConfigEditor()
        self._adopt(self.run_config_editor)
        self.details_tabs = DetailsPanel(self.preview3d_messages)
        self._adopt(self.details_tabs)

        self._build_layout()
        self._connect_signals()
        self._populate_nist_table()

    def _adopt(self, editor: QWidget) -> None:
        """Make the editor widget's controls attributes of the page (names are unique across editors)."""
        for name, value in vars(editor).items():
            if name.startswith("_") or hasattr(type(editor), name):   # signals and methods stay on the widget
                continue
            if name in self.__dict__ and self.__dict__[name] is not value:
                raise AttributeError(f"{type(editor).__name__}.{name} clashes with a page attribute")
            setattr(self, name, value)

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        splitter = QSplitter()
        splitter.addWidget(self.setup_panel)
        splitter.addWidget(self._workspace_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 980])
        layout.addWidget(splitter, 1)

    def _workspace_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.workspace_summary)

        tabs = QTabWidget()
        self.workspace_tabs = tabs
        tabs.addTab(self.materials_editor, "Materials")
        tabs.addTab(self.geometry_editor, "Geometry")
        tabs.addTab(self.boolean_tab, "Boolean Ops")
        tabs.addTab(self.preview3d_panel, "3D Preview")
        tabs.addTab(self.run_config_editor, "Run Config")
        # messages, raw/generated files and the NIST list are reference views: one tab with sub-tabs
        tabs.addTab(self.details_tabs, "Messages and files")
        layout.addWidget(tabs, 1)
        return panel

    def _table_tab(self, label: QLabel, table: QTableWidget) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(label)
        layout.addWidget(table, 1)
        return tab

    def _connect_signals(self) -> None:
        # in the order they were always connected (slots of one signal run in this order)
        self._connect_setup_actions()
        self._connect_material_buttons()
        self._connect_setup_changes()
        self._connect_material_detail()
        self._connect_geometry_signals()
        self._connect_preview_signals()
        self._connect_sps_editor_signals()
        self._connect_sps_summary_signals()

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
        self._set_geometry_template_token(geometry.template)

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
        if isinstance(saved_geometry, GeometryDocument) and (
            saved_geometry.is_dirty or saved_geometry.source_copy_mode
        ):
            self.geometry_document = saved_geometry
            self._populate_geometry_editor()
            # revalidate materials against the restored (edited) geometry, not the source file
            self._populate_material_editor()
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

    def validate_current(self, project: G4USimProject) -> ValidationReport:
        if not self.material_document.is_dirty:
            self.reload_materials()
        if not self.geometry_document.is_dirty and not self.geometry_document.source_copy_mode:
            self.reload_geometry()
        report = validate_config_builder(
            paths=self.path_settings(project),
            run=self.run_settings(),
            geometry=self.geometry_settings(),
            source=self.source_settings(),
            physics=self.physics_settings(),
            scoring=self.scoring_settings(),
            material_document=self.material_document if self.material_document.is_dirty else None,
            geometry_document=self.geometry_document,
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
            self.schedule_backend_geometry()
            self.settingsChanged.emit()

    def _row_status(self, errors: list[str], warnings: list[str]) -> str:
        if errors:
            return "ERROR"
        if warnings:
            return "WARN"
        return "OK"

    def _table_text(self, table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        return item.text().strip() if item else ""

    def _as_bool(self, value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}

    def _unique_name(self, base: str, existing: set[str]) -> str:
        existing_lower = {name.lower() for name in existing}
        candidate = base
        index = 1
        while candidate.lower() in existing_lower:
            index += 1
            candidate = f"{base}{index}"
        return candidate

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

    def refresh_theme(self) -> None:
        set_theme = getattr(self.preview3d_widget, "set_theme", None)
        if set_theme is not None:
            set_theme()

    def refresh_language(self) -> None:
        refresh = getattr(self.preview3d_widget, "refresh_language", None)
        if refresh is not None:
            refresh()
        self._populate_geometry_template_options(self._geometry_template_token())
        self._update_material_count_label()
        self._update_hierarchical_count_labels()
        self._update_workspace_summary()

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
        if self.geometry_document.is_dirty:   # the edited geometry is what will be generated
            volume_count = sum(1 for v in self.geometry_document.volumes if v.enabled)
            boolean_count = sum(1 for op in self.geometry_document.boolean_ops if op.enabled)
        else:
            volume_count = len(self.geometry_summary.volumes) if self.geometry_summary else 0
            boolean_count = len(self.geometry_summary.boolean_ops) if self.geometry_summary else 0
        # GeometryDocument merges source and validation diagnostics. MaterialDocument
        # retains source errors, while parser warnings live only in the summary.
        material_source_warnings = len(self.materials_summary.warnings) if self.materials_summary else 0
        warning_count = material_source_warnings + len(self.material_document.warnings) + len(self.geometry_document.warnings)
        error_count = len(self.material_document.errors) + len(self.geometry_document.errors)
        self.workspace_summary.setText(
            ui_format(
                "Materials: {materials} entries | Geometry: {volumes} volumes, {booleans} boolean ops | Messages: {errors} errors, {warnings} warnings | Materials: {material_state} | Geometry: {geometry_mode} {geometry_state} | Source: {source_status} | Physics: {physics} | Scoring: {scoring}",
                materials=material_count,
                volumes=volume_count,
                booleans=boolean_count,
                errors=error_count,
                warnings=warning_count,
                material_state=ui_text("Dirty" if self.material_document.is_dirty else "Clean"),
                geometry_mode=self.geometry_document.mode,
                geometry_state=ui_text("Dirty" if self.geometry_document.is_dirty else "Clean"),
                source_status=self._status_text(self.source_editor.errors, self.source_editor.warnings),
                physics=self._status_text(self.physics_editor.errors, self.physics_editor.warnings),
                scoring=self._status_text(self.scoring_editor.errors, self.scoring_editor.warnings),
            )
        )
