"""Qt projection of the shared, non-Qt editor transaction service.

Only Project and Configuration are editor domains. A history replay never calls
a parser, package writer, runner, or the ordinary project-open path.
"""
from __future__ import annotations

import copy
from pathlib import Path
from contextlib import contextmanager
from functools import wraps
import inspect

from PySide6.QtCore import QEvent, QObject, QProcess, QSignalBlocker, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QAbstractSpinBox, QCheckBox, QComboBox, QLineEdit, QMenu,
    QLabel, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget, QToolBar,
)

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.widgets.qt_data import combo_data

PROJECT_CONTROLS = ('project_name run_input_mode executable workspace_root config_path macro_path '
                    'output_dir runs_root threads seed run_name').split()
CONFIG_CONTROLS = (
    'run_name threads seed beam_on check_overlaps dry_run materials_config geometry_config geometry_template '
    'source_preset source_particle source_energy source_position source_direction physics_reference default_cut '
    'enable_biasing scoring_enabled scoring_hits scoring_event_edep scoring_edep hist_bins hist_min hist_max '
    'source_editor_preset source_editor_particle source_editor_energy source_editor_position_type source_editor_shape '
    'source_editor_position source_editor_radius source_editor_inner_radius source_editor_halfx source_editor_halfy '
    'source_editor_normal source_editor_confine_volume source_editor_direction source_editor_angular_mode '
    'source_editor_theta_min source_editor_theta_max source_editor_phi_min source_editor_phi_max '
    'source_editor_cone_half_angle source_editor_focus_point source_editor_preview_rays source_editor_preview_seed '
    'physics_editor_mode physics_editor_reference physics_editor_default_cut physics_editor_biasing '
    'scoring_editor_enabled scoring_editor_hits scoring_editor_event_edep scoring_editor_edep scoring_editor_dose '
    'scoring_editor_fluence scoring_editor_raw_hist scoring_editor_weighted_hist scoring_editor_trajectories '
    'scoring_editor_bins scoring_editor_min scoring_editor_max scoring_editor_volume_summary '
    'scoring_editor_particle_summary scoring_editor_auto_create geometry_source_copy '
    'simple_world_size simple_world_material simple_target_name simple_target_shape simple_target_size '
    'simple_target_material simple_target_position simple_target_rotation simple_target_sensitive simple_target_bias '
    'simple_target_region layered_world_size layered_world_material layered_axis layered_gap layered_z_start '
    'layered_auto_stack'
).split()
DETAIL_FIELDS = {
    'material': {'name': 'material_name', 'density': 'material_density', 'components_text': 'material_components'},
    'layer': {name: 'layer_' + name for name in ('name', 'thickness', 'xy', 'region', 'copy_no', 'position', 'rotation')},
}


def capture_detail_raw(page, kind, row):
    drafts = {}
    for field, attribute in DETAIL_FIELDS[kind].items():
        text = _read_control(getattr(page, attribute))
        if text != text.strip():
            drafts[field] = text
    row._f5_raw_drafts = drafts


def restore_detail_raw(page, kind, row):
    for field, text in getattr(row, '_f5_raw_drafts', {}).items():
        if field in DETAIL_FIELDS[kind]:
            _write_control(getattr(page, DETAIL_FIELDS[kind][field]), text)


def edit_operation(label: str):
    """Group a complete editor action, including its synchronous signal cascade."""
    def decorate(method):
        parameters = tuple(inspect.signature(method).parameters.values())
        positional_count = sum(item.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                               for item in parameters) - 1
        @wraps(method)
        def invoke(self, *args, **kwargs):
            # PySide truncates surplus Qt signal arguments for ordinary bound
            # methods. A *args wrapper must preserve that same slot contract.
            args = args[:positional_count]
            owner = getattr(self, '_history_owner', None)
            if owner is None or owner._history_restoring or self._building:
                return method(self, *args, **kwargs)
            if not owner.can_mutate_workspace(label):
                return None
            with owner.workspace_transaction(label, flush=method.__name__ not in {
                    '_on_geometry_template_changed', '_on_geometry_source_copy_toggled'}):
                return method(self, *args, **kwargs)
        return invoke
    return decorate


def _read_control(widget):
    if isinstance(widget, QLineEdit):
        return widget.text()
    if isinstance(widget, QPlainTextEdit):
        return widget.toPlainText()
    if isinstance(widget, QComboBox):
        data = combo_data(widget)
        return data if type(data) in (str, int, bool) else widget.currentText()
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QAbstractSpinBox):
        return widget.value()
    raise TypeError(type(widget).__name__)


def _write_control(widget, value):
    if isinstance(widget, QLineEdit):
        widget.setText(value)
    elif isinstance(widget, QPlainTextEdit):
        widget.setPlainText(value)
    elif isinstance(widget, QComboBox):
        if value == '':
            widget.setCurrentIndex(-1)
        elif type(value) in (int, bool) or widget.findData(value) >= 0:
            index = widget.findData(value)
            if index < 0:
                widget.addItem(str(value), value)
                index = widget.count() - 1
            widget.setCurrentIndex(index)
        else:
            index = widget.findText(value)
            if index < 0:
                widget.addItem(value)
                index = widget.count() - 1
            widget.setCurrentIndex(index)
    elif isinstance(widget, QCheckBox):
        widget.setChecked(value)
    elif isinstance(widget, QAbstractSpinBox):
        widget.setValue(value)


class EditorHistoryFilter(QObject):
    """Route undo inside registered editor controls, including delegate editors.

    Native line/text editors consume ShortcutOverride before a window QAction.
    Catch both events and replace their context-menu undo entries as well.
    """
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched, event):  # noqa: N802
        window = self.window
        if window._history_restoring or not window._is_project_editor(watched):
            return False
        kind = event.type()
        if kind in (QEvent.ShortcutOverride, QEvent.KeyPress):
            undo = event.matches(QKeySequence.StandardKey.Undo)
            redo = event.matches(QKeySequence.StandardKey.Redo) or (
                event.key() == Qt.Key_Y and event.modifiers() == Qt.ControlModifier)
            if undo or redo:
                event.accept()
                if kind == QEvent.KeyPress:
                    (window.undo_edit if undo else window.redo_edit)()
                return True
        if kind == QEvent.ContextMenu and isinstance(watched, (QLineEdit, QPlainTextEdit)):
            if watched.isReadOnly():
                return False
            menu = QMenu(watched)
            menu.addAction(window.undo_action)
            menu.addAction(window.redo_action)
            menu.addSeparator()
            for label, method in (('Cut', 'cut'), ('Copy', 'copy'), ('Paste', 'paste'), ('Select all', 'selectAll')):
                menu.addAction(ui_text(label), getattr(watched, method))
            menu.exec(event.globalPos())
            menu.deleteLater()
            return True
        if kind == QEvent.FocusIn:
            window._finish_history_merge()
            window._history_field = window._editor_key(watched)
        elif kind == QEvent.FocusOut:
            # Delay until Qt commits a table/spin editor, then close its group.
            QTimer.singleShot(0, window._finish_history_merge)
        elif kind == QEvent.MouseButtonPress and isinstance(watched, (QPushButton, QCheckBox, QComboBox)):
            window._finish_history_merge()
            window._history_field = window._editor_key(watched)
        elif kind == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab, Qt.Key_Backtab):
            QTimer.singleShot(0, window._finish_history_merge)
        return False


class TransactionsMixin:
    """MainWindow hooks shared with the recovery controller."""

    def _setup_edit_history(self):
        from g4usim_gui.core.edit_transactions import EditSession
        self._history_restoring = False
        self._history_depth = 0
        self._history_field = None
        self._history_merge_epoch = 0
        self._history_discard_on_close = False
        self._workspace_fault = ''
        self._workspace_fault_snapshot = None
        self._history_timer = QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.timeout.connect(self.flush_pending_edit)
        self._history_merge_timer = QTimer(self)
        self._history_merge_timer.setSingleShot(True)
        self._history_merge_timer.setInterval(800)
        self._history_merge_timer.timeout.connect(self._finish_history_merge)
        self._edit_session = EditSession(self.capture_workspace())
        self.config_builder_page._history_owner = self
        self._history_filter = EditorHistoryFilter(self)
        QApplication.instance().installEventFilter(self._history_filter)
        self.project_page.projectChanged.connect(self._queue_history_change)
        self.config_builder_page.settingsChanged.connect(self._queue_history_change)
        # Raw drafts can change without a valid model update (notably seed and
        # programmatic line edits); captures still use the same transaction API.
        for widget in self._editable_controls().values():
            if isinstance(widget, (QLineEdit, QPlainTextEdit)):
                widget.textChanged.connect(self._queue_history_change)
            elif isinstance(widget, QAbstractSpinBox):
                widget.lineEdit().textEdited.connect(self._queue_history_change)
        self.history_changed()
        for page in (self.scan_page, self.scenario_page):
            hint = QLabel(ui_text('This page has a separate temporary draft. Project undo and recovery protect Project and Configuration only.'))
            hint.setWordWrap(True)
            (page.input_scroll.widget().layout() if page is self.scenario_page else page.layout()).insertWidget(0, hint)
            page._project_recovery_scope_hint = hint

    def _editable_controls(self):
        return {**{f'project.{name}': getattr(self.project_page, name) for name in PROJECT_CONTROLS},
                **{f'config.{name}': getattr(self.config_builder_page, name) for name in CONFIG_CONTROLS}}

    def _is_project_editor(self, widget):
        return any(page is widget or page.isAncestorOf(widget) for page in
                   (self.project_page, self.config_builder_page)) if hasattr(widget, 'isWidgetType') and widget.isWidgetType() else False

    def _editor_key(self, widget):
        for name, control in self._editable_controls().items():
            if control is widget or control.isAncestorOf(widget):
                return name
        page = self.config_builder_page
        for name in ('materials_table', 'geometry_table', 'boolean_table', 'layer_table'):
            table = getattr(page, name, None)
            if table is not None and (table is widget or table.isAncestorOf(widget)):
                return f'config.{name}.{table.currentRow()}.{table.currentColumn()}'
        for name, control in vars(page).items():
            if control is widget:
                row = page._selected_material_row if name.startswith('material_') else page._selected_layer_row
                return f'config.{name}.{row}'
        return None

    def _capture_drafts(self):
        drafts = {key: _read_control(widget) for key, widget in self._editable_controls().items()}
        for key, widget in self._editable_controls().items():
            if isinstance(widget, QAbstractSpinBox):
                drafts[key + '.raw'] = widget.lineEdit().text()
        page = self.config_builder_page
        for kind, rows in (('material', page.material_document.rows), ('layer', page.geometry_document.layered_device.layers)):
            for index, row in enumerate(rows):
                for field, text in getattr(row, '_f5_raw_drafts', {}).items():
                    drafts[f'detail.{kind}.{index}.{field}'] = text
        return drafts

    def capture_workspace(self):
        from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
        from g4usim_gui.core.edit_state import empty_editing_state
        page = self.config_builder_page
        project = copy.deepcopy(self.project)
        self.project_page.apply_to_project(project)
        page.update_project(project)
        project.pathSettings.executable = project.executable
        project.pathSettings.workspace_root = project.workspaceRoot
        project.pathSettings.runs_root = project.runsRoot
        binding = getattr(self, '_generated_edit_binding', None)
        if project.runInputMode == 'generated' and binding is not None:
            for name, (original, generated) in binding.items():
                if getattr(project, name) == generated:
                    setattr(project, name, original)
        project.materialEditor = copy.deepcopy(page.material_document)
        project.geometryEditor = copy.deepcopy(page.geometry_document)
        state = empty_editing_state()
        state['drafts'] = self._capture_drafts()
        if project.runInputMode == 'generated' and binding is not None:
            for name, control in (('configPath', 'config_path'), ('macroPath', 'macro_path'), ('outputDir', 'output_dir')):
                original, generated = binding[name]
                if state['drafts'][f'project.{control}'] == generated:
                    state['drafts'][f'project.{control}'] = original
        for name in ('geometry_table', 'boolean_table'):
            table = getattr(page, name)
            state['tables'][name] = [[table.item(row, col).text() if table.item(row, col) else ''
                                     for col in range(table.columnCount() - 1)] for row in range(table.rowCount())]
            for editor in table.findChildren(QLineEdit):
                if editor.isVisible() and hasattr(editor, '_f5_cell_row'):
                    row, column = editor._f5_cell_row, editor._f5_cell_column
                    if 0 <= row < table.rowCount() and 0 <= column < table.columnCount() - 1:
                        state['tables'][name][row][column] = editor.text()
                        state['selections'][f'pending_{name}_row'] = row
                        state['selections'][f'pending_{name}_column'] = column
        for name in ('materials_table', 'layer_table', 'geometry_table', 'boolean_table'):
            table = getattr(page, name, None)
            if table is not None:
                state['selections'][name] = table.currentRow()
        for kind, summary in (('materials', page.materials_summary), ('geometry', page.geometry_summary)):
            if summary is not None:
                state['sources'][kind] = {
                    'path': getattr(summary, '_f5_source_anchor', str(Path(summary.path).expanduser().resolve())), 'text': summary.raw_text,
                    'read_success': bool(getattr(summary, '_f4_read_success', False)),
                    'template': getattr(summary, 'template_hint', ''),
                }
        return WorkspaceSnapshot(project, state,
                                 {'materials': copy.deepcopy(page.materials_summary),
                                  'geometry': copy.deepcopy(page.geometry_summary)})

    def _check_workspace_projection(self, snapshot):
        from g4usim_gui.core.edit_state import validate_editing_state
        self._check_project_projection(snapshot.project)
        validate_editing_state(snapshot.state)
        if snapshot.project.materialEditor is None:
            raise ValueError('Editor snapshot does not contain a material document.')
        for kind, source in snapshot.state['sources'].items():
            if source['path'] and not Path(source['path']).is_absolute():
                raise ValueError(f'Recovered source has no absolute capture anchor: {kind}')
        controls = self._editable_controls()
        for key, value in snapshot.state['drafts'].items():
            if key.startswith('detail.'):
                pieces = key.split('.')
                if len(pieces) != 4 or pieces[1] not in DETAIL_FIELDS or pieces[3] not in DETAIL_FIELDS[pieces[1]] or not pieces[2].isdigit():
                    raise ValueError(f'Unknown detail editor binding: {key}')
                rows = snapshot.project.materialEditor.rows if pieces[1] == 'material' else snapshot.project.geometryEditor.layered_device.layers
                if int(pieces[2]) >= len(rows) or type(value) is not str:
                    raise ValueError(f'Invalid detail editor binding: {key}')
                continue
            raw_spin = key.endswith('.raw') and key[:-4] in controls and isinstance(controls[key[:-4]], QAbstractSpinBox)
            if raw_spin:
                if type(value) is not str:
                    raise ValueError(f'Expected spin editor text: {key}')
                continue
            if key not in controls:
                raise ValueError(f'Unknown editor binding: {key}')
            widget = controls[key]
            if isinstance(widget, (QLineEdit, QPlainTextEdit)) and type(value) is not str:
                raise ValueError(f'Expected editor text: {key}')
            if isinstance(widget, QCheckBox) and type(value) is not bool:
                raise ValueError(f'Expected editor boolean: {key}')
            if isinstance(widget, QAbstractSpinBox) and (type(value) is not int or not widget.minimum() <= value <= widget.maximum()):
                raise ValueError(f'Editor integer is outside the control range: {key}')
            if isinstance(widget, QComboBox) and type(value) not in (str, bool, int):
                raise ValueError(f'Invalid combo value: {key}')
        geometry = snapshot.project.geometryEditor
        shape = {'geometry_table': (len(geometry.volumes), 16), 'boolean_table': (len(geometry.boolean_ops), 9)}
        for key, rows in snapshot.state['tables'].items():
            if key not in shape or len(rows) != shape[key][0] or any(len(row) != shape[key][1] for row in rows):
                raise ValueError(f'Invalid editor table shape: {key}')
        allowed_selections = {'materials_table', 'layer_table', 'geometry_table', 'boolean_table'}
        for name, (rows, columns) in shape.items():
            row_key, col_key = f'pending_{name}_row', f'pending_{name}_column'
            allowed_selections.update((row_key, col_key))
            selections = snapshot.state['selections']
            if row_key in selections or col_key in selections:
                if (row_key not in selections or col_key not in selections or
                        not 0 <= selections[row_key] < rows or not 0 <= selections[col_key] < columns):
                    raise ValueError(f'Invalid pending cell binding: {name}')
        if set(snapshot.state['selections']) - allowed_selections:
            raise ValueError('Unknown editor selection binding.')

    def apply_workspace(self, snapshot, *, reason='restore'):
        """Publish an already decoded snapshot without reading its source files."""
        from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
        fault_snapshot = getattr(self, '_workspace_fault_snapshot', None)
        if fault_snapshot is not None and snapshot_fingerprint(snapshot) != snapshot_fingerprint(fault_snapshot):
            raise ValueError('Restore the last verified editor state before opening another workspace.')
        self._check_workspace_projection(snapshot)
        verified = self._edit_session.current() if hasattr(self, '_edit_session') else None
        self._history_restoring = True
        try:
            self._cancel_edit_observers()
            self.project = copy.deepcopy(snapshot.project)
            page = self.config_builder_page
            # The guarded projection path is deliberately separate from Open.
            page.set_from_project(self.project, reload_sources=False)
            page.material_document = copy.deepcopy(snapshot.project.materialEditor)
            page.geometry_document = copy.deepcopy(snapshot.project.geometryEditor)
            for key, text in snapshot.state['drafts'].items():
                if key.startswith('detail.'):
                    _, kind, index, field = key.split('.')
                    rows = page.material_document.rows if kind == 'material' else page.geometry_document.layered_device.layers
                    row = rows[int(index)]
                    if not hasattr(row, '_f5_raw_drafts'):
                        row._f5_raw_drafts = {}
                    row._f5_raw_drafts[field] = text
            self._restore_source_summaries(snapshot)
            page._f5_frozen_sources = set(snapshot.state['sources'])
            page._selected_material_row = min(page._selected_material_row, len(page.material_document.rows) - 1)
            page._selected_layer_row = min(page._selected_layer_row, len(page.geometry_document.layered_device.layers) - 1)
            page._populate_geometry_editor()
            page._populate_material_editor()
            page.materials_raw.setPlainText(page._preview_text(page.material_document.raw_source_text))
            page.geometry_raw.setPlainText(page._preview_text(page.geometry_document.raw_source_text))
            self.project_page.set_project(self.project)
            controls = self._editable_controls()
            blocked = [QSignalBlocker(widget) for widget in controls.values()]
            try:
                for key, value in snapshot.state['drafts'].items():
                    if key in controls:
                        _write_control(controls[key], value)
                    elif key.endswith('.raw') and key[:-4] in controls:
                        controls[key[:-4]].lineEdit().setText(value)
            finally:
                del blocked
            for name in ('geometry_table', 'boolean_table'):
                table = getattr(page, name)
                blocker = QSignalBlocker(table)
                for row, values in enumerate(snapshot.state['tables'].get(name, [])):
                    for column, text in enumerate(values):
                        if (row == snapshot.state['selections'].get(f'pending_{name}_row') and
                                column == snapshot.state['selections'].get(f'pending_{name}_column')):
                            continue
                        table.item(row, column).setText(text)
                del blocker
            for name, row in snapshot.state['selections'].items():
                table = getattr(page, name, None)
                if table is not None and 0 <= row < table.rowCount():
                    table.selectRow(row)
            for name in ('geometry_table', 'boolean_table'):
                row = snapshot.state['selections'].get(f'pending_{name}_row')
                if row is None:
                    continue
                column = snapshot.state['selections'][f'pending_{name}_column']
                table = getattr(page, name)
                page.workspace_tabs.setCurrentIndex(1 if name == 'geometry_table' else 2)
                table.setCurrentCell(row, column)
                table.editItem(table.item(row, column))
                for editor in table.findChildren(QLineEdit):
                    if not editor.isHidden() and hasattr(editor, '_f5_cell_row'):
                        editor.setText(snapshot.state['tables'][name][row][column])
                        break
            page.invalidate_diagnostics()
            self._invalidate_project_diagnostics(force=True)
            page._mark_preview_stale()
            self._generated_package_dir = ''
            self._generated_edit_binding = None
            self._generated_package_stale = True
            page.set_package_path('<stale>')
            self.run_page.set_macro_plan(ui_text('Run plan is stale; inputs changed.'))
            self.run_page.set_command([ui_text('Configuration changed; the run package will be regenerated at run time.')])
            if self.run_page._result_state or self.run_page._progress_data is not None:
                self.run_page.append_status_message(ui_text('Configuration restored. Previous logs and results remain associated with their original run.'))
            self.run_page.set_state('Not running')
            self.run_page.set_result('Not run yet')
            self.run_page._progress_data = None
            self.run_page._exit_code = None
            self.run_page._elapsed.invalidate()
            self.run_page.set_progress_state('idle')
            self.run_page.refresh_language()
            self._set_run_chip('Needs validation', 'warning')
            self.project_context.setText(ui_format('Project: {name}', name=self.project.projectName or ui_text('untitled')))
            self.scenario_page.set_executable(self.project.executable)
            if fault_snapshot is not None:
                if snapshot_fingerprint(self.capture_workspace()) != snapshot_fingerprint(fault_snapshot):
                    raise ValueError('Restored editor controls do not match the last verified snapshot.')
        except Exception as exc:
            if verified is not None:
                self._freeze_workspace(exc, verified)
            raise
        finally:
            self._history_restoring = False
        if fault_snapshot is not None:
            self._workspace_fault = ''
            self._workspace_fault_snapshot = None
            self._update_editor_busy()

    def _restore_source_summaries(self, snapshot):
        from g4usim_gui.parsers.materials_parser import parse_materials_text, MaterialsSummary
        from g4usim_gui.parsers.geometry_parser import parse_geometry_text, GeometrySummary
        page = self.config_builder_page
        for kind, attr in (('materials', 'materials_summary'), ('geometry', 'geometry_summary')):
            if kind in snapshot.transient:
                summary = copy.deepcopy(snapshot.transient[kind])
            else:
                source = snapshot.state['sources'].get(kind)
                if source is None:
                    summary = None
                elif source['read_success']:
                    summary = (parse_materials_text(source['text'], source_path=source['path']) if kind == 'materials'
                               else parse_geometry_text(source['text'], source_path=source['path'], template_name=source['template']))
                else:
                    document = page.material_document if kind == 'materials' else page.geometry_document
                    summary = (MaterialsSummary(source['path']) if kind == 'materials' else GeometrySummary(source['path']))
                    summary.raw_text = source['text']
                    summary.errors = list(document.source_errors)
                    summary.warnings = list(getattr(document, 'source_warnings', document.warnings))
                    summary._f4_read_success = False
                if summary is not None:
                    summary._f5_source_anchor = source['path']
            setattr(page, attr, summary)

    def _cancel_edit_observers(self):
        self._pending_inspection_run = False
        self._macro_inspection_snapshot = None
        if self._macro_inspection.state() != QProcess.NotRunning:
            self._macro_inspection.kill()
            self._macro_inspection.waitForFinished(1000)
        self.config_builder_page._backend_timer.stop()
        self.geometry_controller.stop()

    def _queue_history_change(self, *_args):
        if not hasattr(self, '_edit_session') or self._history_restoring or self._history_depth or self._workspace_fault:
            return
        if self.project_page._building or self.config_builder_page._building:
            return
        self._history_timer.start(0)
        self._history_merge_timer.start()

    def flush_pending_edit(self):
        if not hasattr(self, '_edit_session') or self._history_restoring or self._history_depth or self._workspace_fault:
            return
        self._history_timer.stop()
        merge = f'{self._history_merge_epoch}:{self._history_field}' if self._history_field else None
        try:
            snapshot = self.capture_workspace()
            self._edit_session.replace('Edit configuration', snapshot, merge_key=merge)
        except (ValueError, TypeError) as exc:
            self.apply_workspace(self._edit_session.current(), reason='rejected')
            self.statusBar().showMessage(ui_format('Edit was not applied: {reason}', reason=str(exc)), 8000)
        self.history_changed()

    def _finish_history_merge(self):
        self.flush_pending_edit()
        self._history_merge_epoch += 1
        self._history_field = None
        self._history_merge_timer.stop()
        self._edit_session.break_merge()

    def apply_editor_operation(self, label, operation, *, expected_revision=None):
        """Apply a composed operation through existing editor bindings.

        The callback receives the Configuration and Project pages; it must use
        their editing methods/signals, not mutate a detached typed snapshot and
        leave stale draft mirrors. The shared EditSession remains authoritative.
        """
        if not self.can_mutate_workspace(label):
            return False
        self.flush_pending_edit()
        if expected_revision is not None and expected_revision != self._edit_session.revision:
            from g4usim_gui.core.edit_transactions import TransactionConflict
            raise TransactionConflict('Workspace changed before the editor operation could be applied')
        with self.workspace_transaction(label):
            operation(self.config_builder_page, self.project_page)
        return True

    @contextmanager
    def workspace_transaction(self, label, *, flush=True):
        if getattr(self, '_workspace_fault', '') and not self._history_restoring:
            raise ValueError('Editor state is inconsistent; restore the last verified snapshot first.')
        if self._history_restoring or not hasattr(self, '_edit_session'):
            yield
            return
        outer = self._history_depth == 0
        if outer:
            if flush:
                self._finish_history_merge()
            else:
                # The combo/checkbox has already changed before its Qt signal
                # invokes us. Its value and dependent model belong to one step.
                self._history_timer.stop()
                self._history_merge_epoch += 1
                self._history_field = None
                self._edit_session.break_merge()
            before = self._edit_session.current()
        self._history_depth += 1
        try:
            yield
            if outer:
                self._edit_session.replace(label, self.capture_workspace())
        except Exception:
            if outer:
                self.apply_workspace(before, reason='rollback')
            raise
        finally:
            self._history_depth -= 1
            if outer:
                self.history_changed()

    def can_mutate_workspace(self, reason='edit'):
        if getattr(self, '_workspace_fault', ''):
            self.statusBar().showMessage(ui_text('Editor recovery required. Use Edit > Restore last verified editor state before saving or running.'))
            return False
        busy = self.runner.is_running() or self._macro_inspection.state() != QProcess.NotRunning
        if busy:
            self.statusBar().showMessage(ui_text('Editing is unavailable while a run or input inspection is active.'), 5000)
        return not busy and not getattr(self, '_closing', False)

    def _update_editor_busy(self, *_args):
        busy = bool(getattr(self, '_workspace_fault', '')) or self.runner.is_running() or self._macro_inspection.state() != QProcess.NotRunning
        self.project_page.setEnabled(not busy)
        self.config_builder_page.setEnabled(not busy)
        self.history_changed()

    def _freeze_workspace(self, error, verified):
        """Retain the authoritative state; never publish the damaged widgets."""
        if self._workspace_fault_snapshot is None:
            self._workspace_fault_snapshot = copy.deepcopy(verified)
        self._workspace_fault = str(error)
        self._history_timer.stop()
        self._history_merge_timer.stop()
        self._generated_package_stale = True
        self._generated_package_dir = ''
        self.project_page.setEnabled(False)
        self.config_builder_page.setEnabled(False)
        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)
        self.repair_editor_action.setEnabled(True)
        self.repair_editor_action.setVisible(True)
        self._set_run_chip('Editor recovery required', 'warning')
        self.run_page.set_command([ui_text('Editor state is inconsistent. Saving, generation and execution are blocked.')])
        self.run_page.append_status_message(str(error))
        self.statusBar().showMessage(ui_text('Editor recovery required. Use Edit > Restore last verified editor state before saving or running.'))

    def restore_last_verified_workspace(self):
        """Explicit repair of a failed projection; retains history and save point."""
        snapshot = self._workspace_fault_snapshot
        if snapshot is None:
            return True
        if self.runner.is_running() or self._macro_inspection.state() != QProcess.NotRunning:
            return False
        try:
            self.apply_workspace(snapshot, reason='fault-repair')
        except Exception as exc:
            self.statusBar().showMessage(ui_format('Editor recovery failed: {reason}', reason=str(exc)))
            return False
        self.history_changed()
        self.statusBar().showMessage(ui_text('Last verified editor state restored. Review it before saving or reopening a project.'), 8000)
        return True

    def undo_edit(self):
        if not self.can_mutate_workspace('undo'):
            return
        self._finish_history_merge()
        self._edit_session.undo(apply=lambda snapshot: self.apply_workspace(snapshot, reason='undo'))
        self.history_changed()

    def redo_edit(self):
        if not self.can_mutate_workspace('redo'):
            return
        self._finish_history_merge()
        self._edit_session.redo(apply=lambda snapshot: self.apply_workspace(snapshot, reason='redo'))
        self.history_changed()

    def _create_history_actions(self):
        self.edit_menu = self.menuBar().addMenu(ui_text('Edit'))
        self.undo_action = QAction(ui_text('Undo'), self)
        self.undo_action.setShortcuts([QKeySequence('Ctrl+Z')])
        self.undo_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.undo_action.triggered.connect(self.undo_edit)
        self.redo_action = QAction(ui_text('Redo'), self)
        self.redo_action.setShortcuts([QKeySequence('Ctrl+Shift+Z'), QKeySequence('Ctrl+Y')])
        self.redo_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.redo_action.triggered.connect(self.redo_edit)
        self.edit_menu.addActions([self.undo_action, self.redo_action])
        self.repair_editor_action = QAction(ui_text('Restore last verified editor state'), self)
        self.repair_editor_action.triggered.connect(self.restore_last_verified_workspace)
        self.repair_editor_action.setVisible(False)
        self.edit_menu.addAction(self.repair_editor_action)
        for page in (self.project_page, self.config_builder_page):
            page.addActions([self.undo_action, self.redo_action])
        self.history_toolbar = QToolBar(ui_text('Edit history'), self)
        self.history_toolbar.setObjectName('editHistoryToolbar')
        self.history_toolbar.setMovable(False)
        self.history_toolbar.addActions([self.undo_action, self.redo_action])
        self.history_toolbar.addAction(self.repair_editor_action)
        self.addToolBar(self.history_toolbar)

    def history_changed(self):
        if not hasattr(self, '_edit_session') or self._history_restoring:
            return
        session = self._edit_session
        fault = bool(self._workspace_fault)
        busy = fault or self.runner.is_running() or self._macro_inspection.state() != QProcess.NotRunning
        self.repair_editor_action.setVisible(fault)
        self.repair_editor_action.setEnabled(fault)
        self.undo_action.setEnabled(session.can_undo and not busy)
        self.redo_action.setEnabled(session.can_redo and not busy)
        self.undo_action.setText(ui_format('Undo: {action}', action=ui_text(session.undo_label)) if session.can_undo else ui_text('Undo'))
        self.redo_action.setText(ui_format('Redo: {action}', action=ui_text(session.redo_label)) if session.can_redo else ui_text('Redo'))
        self.edit_menu.setTitle(ui_text('Edit'))
        self.history_toolbar.setWindowTitle(ui_text('Edit history'))
        self.setWindowTitle(f'G4UniversalSim Runner — {self.project.projectName}' + (' *' if session.is_modified else ''))
        callback = getattr(self, '_recovery_history_changed', None)
        if callback is not None and not fault:
            callback()

    def _reset_edit_history(self, *, saved=True):
        if not hasattr(self, '_edit_session'):
            return
        if self._workspace_fault:
            raise ValueError('Cannot replace history while editor recovery is required.')
        self._history_timer.stop()
        self._history_merge_timer.stop()
        self._history_merge_epoch += 1
        self._history_field = None
        self._edit_session.reset(self.capture_workspace(), saved=saved)
        self.history_changed()

    def _confirm_unsaved_edits(self):
        if not hasattr(self, '_edit_session'):
            return True
        if self._workspace_fault:
            self.can_mutate_workspace('close')
            return False
        self._finish_history_merge()
        if not self._edit_session.is_modified:
            return True
        choice = self._choose_unsaved_action()
        if choice == QMessageBox.Cancel:
            return False
        if choice == QMessageBox.Save:
            self.save_project()
            return not self._edit_session.is_modified
        if choice == QMessageBox.Discard:
            self._history_discard_on_close = True
            return True
        return False

    def _choose_unsaved_action(self):
        """Injectable decision only; tests still exercise the real close guard."""
        return QMessageBox.question(
            self, ui_text('Unsaved project changes'),
            ui_text('Save the current project changes before continuing? Recovery copies do not replace a saved project.'),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
