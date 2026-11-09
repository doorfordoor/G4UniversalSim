from __future__ import annotations

from dataclasses import replace
import copy
from pathlib import Path

from PySide6.QtCore import QTimer, Signal, QSignalBlocker
from PySide6.QtWidgets import (
    QFrame,
    QAbstractButton,
    QAbstractSpinBox,
    QLineEdit,
    QApplication,
    QPlainTextEdit,
    QScrollArea,
    QComboBox,
    QLabel,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.config_schema import check_value
from g4usim_gui.core.diagnostics import Diagnostic
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
from g4usim_gui.window.transactions import edit_operation
from g4usim_gui.widgets.diagnostic_navigation import (
    ConfigDiagnosticNavigator, DiagnosticDraftDelegate, NavigationResult, configuration_snapshot,
    reveal_widget, source_view_text,
)


class LiveDraftDelegate(DiagnosticDraftDelegate):
    """Capture pending cell text without committing it to the business model."""

    def createEditor(self, parent, option, index):  # noqa: N802
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor._f5_cell_row = index.row()
            editor._f5_cell_column = index.column()
            page = self.parent()
            while page is not None and not isinstance(page, ConfigBuilderPage):
                page = page.parentWidget()
            if page is not None:
                owner = getattr(page, '_history_owner', None)
                from g4usim_gui.core.document_edit_model import row_ref
                collection = 'volume' if self.parent() is page.geometry_table else 'boolean'
                editor._document_collection = collection
                editor._document_owner = owner
                editor._document_page = page
                editor._document_ref = row_ref(page._document_snapshot(), collection, index.row(),
                                               owner._edit_session.revision if owner else 0)
                def buffer(text):
                    page._document_action({'kind':'geometry_buffer','ref':editor._document_ref,
                                           'column':index.column(),'raw':text})
                    editor._document_ref = row_ref(page._document_snapshot(), collection, index.row(),
                                                   owner._edit_session.revision if owner else 0)
                editor.textEdited.connect(buffer)
        return editor

    def setModelData(self, editor, model, index):  # noqa: N802
        page = getattr(editor, '_document_page', None)
        if page is None:
            return super().setModelData(editor, model, index)
        page._document_action({'kind':'geometry_cell','ref':editor._document_ref,
                               'column':index.column(),'raw':editor.text()})
        editor._document_committed = True

    def destroyEditor(self, editor, index):  # noqa: N802
        owner = getattr(editor, '_document_owner', None)
        if owner is not None and not getattr(editor, '_document_retired', False) and not owner._history_restoring and not getattr(owner.config_builder_page, '_document_projecting', False):
            owner.finish_document_pending(editor._document_collection, editor._document_ref, index.column())
        elif owner is None and hasattr(editor, '_document_page') and not getattr(editor, '_document_retired', False):
            page = editor._document_page
            if not getattr(page, '_document_projecting', False):
                from g4usim_gui.core.document_edit_model import TABLES
                table = TABLES[editor._document_collection]
                state = getattr(page, '_document_local_state', None)
                if state is not None:
                    state['selections'].pop(f'pending_{table}_row', None)
                    state['selections'].pop(f'pending_{table}_column', None)
        return super().destroyEditor(editor, index)


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
    tracksRequested = Signal()                # overlay a run's particle tracks in the 3D view (G6)
    autoBackendGeometryRequested = Signal()   # the 3D tab wants the Geant4 world after a change (G1)
    diagnosticPageRequested = Signal()
    diagnosticNavigationRequested = Signal(object)

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

    @property
    def source_editor(self):
        context = getattr(self, '_sps_projection_editors', None)
        if context is not None:
            return context['sourceEditor']
        owner = getattr(self, '_history_owner', None)
        if owner is not None:
            return getattr(owner.run_path_snapshot().project, 'sourceEditor')
        return self._source_editor

    @source_editor.setter
    def source_editor(self, value):
        if getattr(self, '_history_owner', None) is None:
            self._source_editor = value

    @property
    def physics_editor(self):
        context = getattr(self, '_sps_projection_editors', None)
        if context is not None:
            return context['physicsEditor']
        owner = getattr(self, '_history_owner', None)
        if owner is not None:
            return getattr(owner.run_path_snapshot().project, 'physicsEditor')
        return self._physics_editor

    @physics_editor.setter
    def physics_editor(self, value):
        if getattr(self, '_history_owner', None) is None:
            self._physics_editor = value

    @property
    def scoring_editor(self):
        context = getattr(self, '_sps_projection_editors', None)
        if context is not None:
            return context['scoringEditor']
        owner = getattr(self, '_history_owner', None)
        if owner is not None:
            return getattr(owner.run_path_snapshot().project, 'scoringEditor')
        return self._scoring_editor

    @scoring_editor.setter
    def scoring_editor(self, value):
        if getattr(self, '_history_owner', None) is None:
            self._scoring_editor = value

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._building = False
        self._diagnostic_generation = 0
        self._diagnostic_snapshot = ""
        self._diagnostic_report = None
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
        self._f5_frozen_sources: set[str] = set()
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
        self.diagnostic_navigator = ConfigDiagnosticNavigator(self)
        self.diagnostic_panel.activationRequested.connect(self.navigate_diagnostic)
        self.diagnostic_panel.sourceRequested.connect(self.view_diagnostic_source)
        self.diagnostic_panel.revalidateRequested.connect(self.validateRequested.emit)
        self._connect_signals()
        self._connect_diagnostic_drafts()
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
        # tabs scroll when the window is smaller than they need (they used to overlap)
        tabs.addTab(self._scrolled(self.materials_editor), "Materials")
        tabs.addTab(self._scrolled(self.geometry_editor), "Geometry")
        tabs.addTab(self._scrolled(self.boolean_tab), "Boolean Ops")
        tabs.addTab(self._scrolled(self.preview3d_panel), "3D Preview")
        self._preview3d_tab_index = tabs.count() - 1   # the tab wraps the panel in a scroll area
        tabs.addTab(self._scrolled(self.run_config_editor), "Run Config")
        # messages, raw/generated files and the NIST list are reference views: one tab with sub-tabs
        tabs.addTab(self._scrolled(self.details_tabs), "Messages and files")
        layout.addWidget(tabs, 1)
        tabs.currentChanged.connect(self._on_workspace_tab_changed)
        return panel

    def _table_tab(self, label: QLabel, table: QTableWidget) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(label)
        layout.addWidget(table, 1)
        return tab

    @staticmethod
    def _scrolled(editor: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName("editorScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(editor)
        return scroll

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

    def set_from_project(self, project: G4USimProject, *, reload_sources: bool = True) -> None:
        owner = getattr(self, '_history_owner', None)
        if owner is None:
            return self._set_from_project_projection(project, reload_sources=reload_sources)
        from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
        previous = getattr(owner, '_sps_projection_snapshot', None)
        # Legacy Open projects before EditSession.reset. Read this explicit input,
        # not the old session, for this synchronous projection only.
        owner._sps_projection_snapshot = WorkspaceSnapshot(project)
        try:
            with self._sps_private_projection(project):
                result = self._set_from_project_projection(project, reload_sources=reload_sources)
            if reload_sources:
                # Legacy input normalization is explicit data, consumed by the
                # caller's reset/outer transaction; it is not a later capture.
                project.materialEditor = copy.deepcopy(self.material_document)
                project.geometryEditor = copy.deepcopy(self.geometry_document)
                state = copy.deepcopy(owner._sps_projection_snapshot.state)
                project.editingState = state
                if owner._history_depth:
                    candidate = owner.run_path_snapshot()
                    candidate.project.materialEditor = copy.deepcopy(project.materialEditor)
                    candidate.project.geometryEditor = copy.deepcopy(project.geometryEditor)
                    candidate.state['sources'] = copy.deepcopy(state['sources'])
                    candidate.state['tables'] = copy.deepcopy(state['tables'])
                    candidate.project.editingState = copy.deepcopy(candidate.state)
                    owner._run_path_transaction_candidate = candidate
            return result
        finally:
            if previous is None:
                owner.__dict__.pop('_sps_projection_snapshot', None)
            else:
                owner._sps_projection_snapshot = previous

    def _set_from_project_projection(self, project: G4USimProject, *, reload_sources: bool = True) -> None:
        self._document_input_project = copy.deepcopy(project)
        self._document_local_state = copy.deepcopy(project.editingState)
        self.invalidate_diagnostics()
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
        if not reload_sources:
            return
        # Explicit legacy input normalization. An existing empty document is
        # still a document; only absent material input selects the file loader.
        saved_materials = getattr(project, 'materialEditor', None)
        saved_geometry = getattr(project, 'geometryEditor', None)
        self.material_document = copy.deepcopy(saved_materials) if saved_materials is not None else MaterialDocument()
        self.geometry_document = copy.deepcopy(saved_geometry) if saved_geometry is not None else GeometryDocument()
        self.materials_summary = self.geometry_summary = None
        self.materials_raw.setPlainText(self._preview_text(self.material_document.raw_source_text))
        self.geometry_raw.setPlainText(self._preview_text(self.geometry_document.raw_source_text))
        if saved_materials is None:
            self.reload_materials()
        if not (saved_geometry is not None and (saved_geometry.is_dirty or saved_geometry.source_copy_mode
                or saved_geometry.raw_source_text or project.editingState is not None)):
            self.reload_geometry()
        self._populate_geometry_editor()
        self._populate_material_editor()
        self._update_workspace_summary()

    def update_project(self, project: G4USimProject) -> None:
        if getattr(self, '_history_owner', None) is None:
            project.runSettings = self.run_settings()
            project.pathSettings.materials_config = self.materials_config.text().strip()
            project.pathSettings.geometry_config = self.geometry_config.text().strip()
            project.geometrySettings = self.geometry_settings()
        else:
            # Template is outside AR4 run/path; config_path is model-owned.
            project.geometrySettings.template = self._history_owner.run_path_snapshot().project.geometrySettings.template
        project.geometryEditor = (copy.deepcopy(self._history_owner.run_path_snapshot().project.geometryEditor)
                                  if getattr(self, '_history_owner', None) is not None else self.geometry_document)
        owner = getattr(self, '_history_owner', None)
        if owner is not None:
            from g4usim_gui.core.sps_edit_model import copy_sps
            copy_sps(project, owner.run_path_snapshot().project)
        else:
            project.sourceEditor = self.source_editor
            project.physicsEditor = self.physics_editor
            project.scoringEditor = self.scoring_editor
            project.sourceSettings = self.source_settings()
            project.physicsSettings = self.physics_settings()
            project.scoringSettings = self.scoring_settings()
        project.materialEditor = (copy.deepcopy(owner.run_path_snapshot().project.materialEditor)
                                  if owner is not None else self.material_document)

    def _document_snapshot(self):
        from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
        owner = getattr(self, '_history_owner', None)
        if owner is not None:
            return owner.run_path_snapshot()
        project = copy.deepcopy(getattr(self, '_document_input_project', G4USimProject()))
        project.materialEditor = copy.deepcopy(self.material_document)
        project.geometryEditor = copy.deepcopy(self.geometry_document)
        # An unbound page is an explicit input adapter, not a second session.
        project.pathSettings = self.path_settings(project)
        project.geometrySettings = self.geometry_settings()
        return WorkspaceSnapshot(project, getattr(self, '_document_local_state', project.editingState))

    def _document_action(self, action, *, collection=None, index=None):
        from g4usim_gui.core.document_edit_model import row_ref, reduce_documents
        if self._building or getattr(self, '_document_projecting', False):
            return
        owner = getattr(self, '_history_owner', None)
        snapshot = self._document_snapshot()
        revision = owner._edit_session.revision if owner is not None else 0
        if index is not None:
            action = dict(action, ref=row_ref(snapshot, collection, index, revision))
        if owner is not None:
            return owner.edit_document(action)
        candidate = reduce_documents(snapshot, action, revision=revision)
        if action['kind'] in ('geometry_buffer','geometry_cell'):
            self._project_document_buffer(candidate)
        else:
            self._project_document_candidate(candidate, material_only=action['kind'].startswith('material_'))
        self._document_input_project = copy.deepcopy(candidate.project)
        self._document_local_state = copy.deepcopy(candidate.state)
        if action['kind'] == 'geometry_cell': self._refresh_document_cell_view()
        self._emit_changed()

    def _refresh_document_cell_view(self):
        self._validate_geometry_editor()
        self._select_geometry_details()
        self._select_boolean_details()
        self._update_generated_geometry_preview()
        self._update_workspace_summary()

    def _project_document_buffer(self, snapshot):
        self.geometry_document = copy.deepcopy(snapshot.project.geometryEditor)
        for name in ('geometry_table', 'boolean_table'):
            table = getattr(self, name)
            blocker = QSignalBlocker(table)
            for row, values in enumerate(snapshot.state['tables'].get(name, [])):
                for column, text in enumerate(values):
                    if (snapshot.state['selections'].get(f'pending_{name}_row') == row
                            and snapshot.state['selections'].get(f'pending_{name}_column') == column):
                        continue
                    item = table.item(row,column)
                    if item is not None and item.text() != text:
                        item.setText(text)
            for editor in table.findChildren(QLineEdit):
                if not editor.isHidden() and hasattr(editor,'_f5_cell_row'):
                    row,column=editor._f5_cell_row,editor._f5_cell_column
                    values=snapshot.state['tables'].get(name,[])
                    if 0 <= row < len(values) and editor.text()!=values[row][column]:
                        position=editor.cursorPosition()
                        editor.setText(values[row][column])
                        editor.setCursorPosition(min(position,len(editor.text())))
            del blocker


    def _project_document_candidate(self, snapshot, *, material_only=False):
        """Disposable view objects; validators never mutate the published document."""
        previous = self._building
        from shiboken6 import isValid
        focused = QApplication.focusWidget()
        cursor = focused.cursorPosition() if isinstance(focused, QLineEdit) else None
        text_cursor = focused.textCursor() if isinstance(focused, QPlainTextEdit) else None
        blocked = [QSignalBlocker(w) for w in self.findChildren(QWidget)
                   if isinstance(w, (QLineEdit, QPlainTextEdit, QComboBox, QAbstractButton, QAbstractSpinBox, QTableWidget))
                   and not hasattr(w, "_f5_cell_row")]
        self._document_projecting = True
        if not material_only:
            for name in ('geometry_table', 'boolean_table'):
                for editor in getattr(self, name).findChildren(QLineEdit):
                    if hasattr(editor, '_document_ref'): editor._document_retired = True
        try:
            self.material_document = copy.deepcopy(snapshot.project.materialEditor)
            if not material_only:
                self.geometry_document = copy.deepcopy(snapshot.project.geometryEditor)
                self._set_geometry_template_token(snapshot.project.geometrySettings.template)
            for key, text in snapshot.state['drafts'].items():
                if key.startswith(('detail.material.', 'detail.layer.')):
                    if material_only and key.startswith('detail.layer.'): continue
                    _, kind, index, field = key.split('.')
                    rows = self.material_document.rows if kind == 'material' else self.geometry_document.layered_device.layers
                    row = rows[int(index)]
                    if not hasattr(row, '_f5_raw_drafts'): row._f5_raw_drafts = {}
                    row._f5_raw_drafts[field] = text
            self._selected_material_row = snapshot.state['selections'].get('materials_table', -1)
            self._selected_layer_row = snapshot.state['selections'].get('layer_table', -1)
            if not material_only:
                self._populate_geometry_editor()
            self._populate_material_editor()
            for name in ('materials_table',) if material_only else ('materials_table','layer_table','geometry_table','boolean_table'):
                table = getattr(self,name)
                index = snapshot.state['selections'].get(name,-1)
                if index >= 0: table.selectRow(index)
                else:
                    table.setCurrentCell(-1,-1)
                    table.clearSelection()
            self._select_material_row(self._selected_material_row)
            if not material_only:
                self._select_layer_row(self._selected_layer_row)
                self._select_geometry_details()
                self._select_boolean_details()
                from g4usim_gui.window.transactions import _write_control
                from g4usim_gui.core.document_edit_model import DOCUMENT_BINDINGS
                for binding in DOCUMENT_BINDINGS:
                    if binding in snapshot.state['drafts']:
                        _write_control(getattr(self,binding[7:]),snapshot.state['drafts'][binding])
                for name in ('geometry_table','boolean_table'):
                    table=getattr(self,name)
                    for i, row in enumerate(snapshot.state['tables'].get(name,[])):
                        for j, text in enumerate(row):
                            table.item(i,j).setText(text)
            if focused is not None and isValid(focused) and not hasattr(focused, "_f5_cell_row") and self.isAncestorOf(focused):
                focused.setFocus()
                if cursor is not None: focused.setCursorPosition(min(cursor,len(focused.text())))
                if text_cursor is not None:
                    text_cursor.setPosition(min(text_cursor.position(),len(focused.toPlainText())))
                    focused.setTextCursor(text_cursor)
        finally:
            self._document_projecting = False
            self._building = previous
            del blocked
        if not material_only:
            for name in ('geometry_table', 'boolean_table'):
                row = snapshot.state['selections'].get(f'pending_{name}_row')
                column = snapshot.state['selections'].get(f'pending_{name}_column')
                if row is not None and column is not None:
                    table = getattr(self, name)
                    blocker = QSignalBlocker(table)
                    table.setCurrentCell(row, column)
                    table.editItem(table.item(row, column))
                    del blocker

    def validate_current(self, project: G4USimProject) -> ValidationReport:
        snapshot = self._document_snapshot()
        materials = copy.deepcopy(snapshot.project.materialEditor)
        geometry = copy.deepcopy(snapshot.project.geometryEditor)
        report = validate_config_builder(
            paths=self.path_settings(project),
            run=self.run_settings(),
            geometry=copy.deepcopy(snapshot.project.geometrySettings),
            source=self.source_settings(),
            physics=self.physics_settings(),
            scoring=self.scoring_settings(),
            material_document=materials if materials is not None and materials.is_dirty else None,
            geometry_document=geometry,
            source_model=self.source_editor,
            physics_model=self.physics_editor,
            scoring_model=self.scoring_editor,
        )
        seed_text = self.seed.text().strip()
        if seed_text:
            problem = check_value("run", "seed", seed_text)   # as the backend reads it: 0..2147483647
            if problem:
                template = "Seed must be an integer from 0 to 2147483647 ({problem})."
                report.add("run.seed.invalid", "error", ui_format(template, problem=problem),
                           origin="run", editor="run", field="seed", message_key=template,
                           params={"problem": problem}, identity_parameters={"value": seed_text})
        from g4usim_gui.core.experiment_workflow import document_raw_diagnostics, document_source_diagnostics
        document_raw_diagnostics(snapshot,report)
        document_source_diagnostics(snapshot,report,recovered=True)
        report._f4_editor_snapshot = self._current_diagnostic_snapshot()
        return report

    def set_validation_text(self, text: str) -> None:
        self.clear_diagnostic_navigation()
        self._diagnostic_report = None
        self._diagnostic_snapshot = ""
        self.diagnostic_panel.clear()
        self.validation_text.setPlainText(text)

    def _current_diagnostic_snapshot(self) -> str:
        return configuration_snapshot(self, self._diagnostic_generation)

    def _connect_diagnostic_drafts(self) -> None:
        # Detail selection populates under _building. Programmatic raw drafts
        # outside that guard still invalidate even where old slots use textEdited.
        for widget in self.findChildren(QLineEdit):
            widget.textChanged.connect(self._diagnostic_draft_changed)
        for table in (self.geometry_table, self.boolean_table):
            table.setItemDelegate(LiveDraftDelegate(table, self._diagnostic_draft_changed))

    def _diagnostic_draft_changed(self, *_args) -> None:
        current = self.sender()
        while current is not None and current is not self:
            if getattr(current, '_projecting', False) or getattr(current, '_loading', False):
                return
            current = current.parent()
        if not self._building:
            self.invalidate_diagnostics()

    def set_validation_report(self, report: ValidationReport) -> None:
        """Bind typed locations to this exact editor revision, preserving raw text."""
        self.clear_diagnostic_navigation()
        self.validation_text.setPlainText(report.to_text())
        current = self._current_diagnostic_snapshot()
        captured = getattr(report, "_f4_editor_snapshot", current)
        report._f4_editor_snapshot = captured
        self._diagnostic_report = report
        self._diagnostic_snapshot = captured
        records = tuple(replace(record, location=replace(record.location, snapshot_id=captured))
                        if record.location is not None and not record.location.snapshot_id else record
                        for record in report.diagnostics)
        self.diagnostic_panel.set_records(records)
        if captured != current:
            self.diagnostic_panel.set_stale()

    def invalidate_diagnostics(self) -> None:
        """A new edit/load generation cannot revive an old report by undoing values."""
        self._diagnostic_generation += 1
        if hasattr(self, "diagnostic_navigator"):
            self.clear_diagnostic_navigation()
        if hasattr(self, "diagnostic_panel") and self._diagnostic_snapshot:
            self.diagnostic_panel.set_stale()

    def clear_diagnostic_navigation(self) -> None:
        self.diagnostic_navigator.clear()

    def _current_diagnostic_record(self, diagnostic: Diagnostic) -> Diagnostic | None:
        if (not self._diagnostic_snapshot or self.diagnostic_panel.stale or
                self._diagnostic_snapshot != self._current_diagnostic_snapshot()):
            self.clear_diagnostic_navigation()
            self.diagnostic_panel.set_stale()
            return None
        if (diagnostic.location is not None and diagnostic.location.snapshot_id and
                diagnostic.location.snapshot_id != self._diagnostic_snapshot):
            self.diagnostic_panel.show_status("This diagnostic belongs to a different editor or snapshot.", "warning")
            return None
        record = next((item for item in self.diagnostic_panel.records
                       if item.identity == diagnostic.identity), None)
        if record is None or (record.location is not None and
                              record.location.snapshot_id != self._diagnostic_snapshot):
            self.diagnostic_panel.show_status("This diagnostic belongs to a different editor or snapshot.", "warning")
            return None
        return record

    def is_diagnostic_current(self, diagnostic: Diagnostic) -> bool:
        return self._current_diagnostic_record(diagnostic) is not None

    def navigate_diagnostic(self, diagnostic: Diagnostic) -> NavigationResult:
        record = self._current_diagnostic_record(diagnostic)
        if record is None:
            return NavigationResult("stale", ui_text("Diagnostics are stale. Validate the current inputs again."))
        if record.location is None:
            if record.source is not None:
                return self.view_diagnostic_source(record)
            result = NavigationResult("unavailable", ui_text("This diagnostic has no editable location."))
        elif (record.location.editor == "project" or
              record.location.editor == "setup" and record.location.field in
              {"executable", "workspace_root", "runs_root"}):
            self.diagnosticNavigationRequested.emit(record)
            return NavigationResult("delegated", ui_text("The target is in the project settings."))
        else:
            result = self.diagnostic_navigator.navigate(record)
        self.diagnostic_panel.show_status("{message}", "info" if result.ok else "warning", message=result.message)
        return result

    def view_diagnostic_source(self, diagnostic: Diagnostic) -> NavigationResult:
        record = self._current_diagnostic_record(diagnostic)
        if record is None or record.source is None:
            return NavigationResult("unavailable", ui_text("This diagnostic has no recorded source location."))
        result, text = source_view_text(record.source)
        if result.ok:
            self.diagnosticPageRequested.emit()
            self.diagnostic_panel.show_source(record.source, text)
            reveal_widget(self.diagnostic_panel.source_view, allow_read_only=True)
        self.diagnostic_panel.show_status("{message}", "warning" if result.status != "source_shown" else "info",
                                          message=result.message)
        return result

    def reload_materials(self):
        return self._reload_document('materials')

    def reload_geometry(self):
        return self._reload_document('geometry')

    def _reload_document(self, domain):
        # A reload attempt retires the old navigation evidence even when the
        # source is missing or cannot be read. The editor state stays intact.
        self.invalidate_diagnostics()
        from g4usim_gui.core.edit_transactions import TransactionConflict
        from g4usim_gui.core.document_edit_model import reduce_documents
        from g4usim_gui.parsers.materials_parser import parse_materials_text
        from g4usim_gui.parsers.geometry_parser import parse_geometry_text
        from g4usim_gui.editors.material_editor_model import material_document_from_summary
        from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
        owner=getattr(self,'_history_owner',None)
        before=self._document_snapshot()
        session=owner._edit_session if owner is not None else None
        revision=session.revision if session is not None else 0
        selected=(before.project.pathSettings.materials_config if domain=='materials'
                  else before.project.geometrySettings.config_path or before.project.pathSettings.geometry_config)
        message=getattr(self,domain+'_messages')
        if not selected.strip():
            document = before.project.materialEditor if domain == 'materials' else before.project.geometryEditor
            notice = ('This material document is in memory; Reload/Revert needs a source file. Your edits are retained.'
                      if domain == 'materials' else
                      'This geometry document is in memory; Reload/Revert needs a source file. Your edits are retained.'
                      if not document.source_path else
                      'The imported geometry still requires its source path. Your edits are retained.')
            message.setPlainText(ui_text(notice))
            return {'kind':domain,'status':'no_source','attempted_path':'','error':''}
        # Preserve the existing explicit Reload cwd-relative input rule; freeze
        # its absolute anchor at this read, never reinterpret it during replay.
        path=Path(selected).expanduser()
        try:
            path=path.resolve()
            text=path.read_text(encoding='utf-8',errors='replace')
        except OSError as error:
            message.setPlainText(str(error))
            return {'kind':domain,'status':'read_failed','attempted_path':str(path),'error':str(error)}
        template=before.project.geometrySettings.template if domain=='geometry' else ''
        summary=(parse_materials_text(text,source_path=path) if domain=='materials' else
                 parse_geometry_text(text,source_path=path,template_name=template))
        summary._f5_source_anchor=str(path)
        document=(material_document_from_summary(summary) if domain=='materials' else
                  geometry_document_from_summary(summary,template))
        document.source_path=str(path)
        source={'path':str(path),'text':summary.raw_text,'read_success':True,'template':template}
        action={'kind':'replace_document','domain':domain,'document':document,'source':source,'summary':summary}
        if owner is not None and not owner._history_restoring:
            if owner._edit_session is not session or session.revision != revision or self._document_snapshot().project != before.project:
                raise TransactionConflict('Document source request is no longer current')
            owner.edit_document(action)
        else:
            # Explicit legacy Open/standalone input normalization, not a widget capture.
            candidate=reduce_documents(before,action,revision=revision)
            self._project_document_candidate(candidate,material_only=domain=='materials')
            self._document_input_project=copy.deepcopy(candidate.project)
            self._document_local_state=copy.deepcopy(candidate.state)
            if owner is not None:
                owner._sps_projection_snapshot=candidate
        setattr(self,domain+'_summary',summary)
        getattr(self,domain+'_raw').setPlainText(self._preview_text(summary.raw_text))
        self._f5_frozen_sources.add(domain)
        self._update_workspace_summary()
        return {'kind':domain,'status':'read_success','attempted_path':str(path),'error':''}

    def set_package_path(self, path: str) -> None:
        self.package_label.setText(f"Generated package: {path or '<none>'}")

    def _set_combo_text(self, combo: QComboBox, value: str) -> None:
        if not value:
            combo.setCurrentIndex(-1)
            return
        index = combo.findText(value)
        if index < 0:
            combo.addItem(value)
            index = combo.findText(value)
        combo.setCurrentIndex(index)

    def _emit_changed(self) -> None:
        if not self._building:
            owner = getattr(self, '_history_owner', None)
            if owner is not None:
                owner.dispatch_run_path_control(self, self.sender())
            self.invalidate_diagnostics()
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
        self.clear_diagnostic_navigation()
        set_theme = getattr(self.preview3d_widget, "set_theme", None)
        if set_theme is not None:
            set_theme()

    def refresh_language(self) -> None:
        self.clear_diagnostic_navigation()
        self.diagnostic_panel.refresh_language()
        refresh = getattr(self.preview3d_widget, "refresh_language", None)
        if refresh is not None:
            refresh()
        self._populate_geometry_template_options(self._geometry_template_token())
        self._update_material_count_label()
        self._update_hierarchical_count_labels()
        self._update_workspace_summary()

    def closeEvent(self, event) -> None:
        self.clear_diagnostic_navigation()
        super().closeEvent(event)

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
