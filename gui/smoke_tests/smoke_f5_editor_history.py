"""F5 real Qt editing, semantic replay, raw drafts and lifecycle guards."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from contextlib import contextmanager

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QMenu, QMessageBox
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint, snapshot_to_json, snapshot_from_json, project_for_snapshot
from g4usim_gui.core.project import load_project, project_to_dict
from g4usim_gui.core.edit_transactions import TransactionApplyError
from g4usim_gui.core.wizard import default_spec
from g4usim_gui.main_window import MainWindow
from g4usim_gui.history import run_history_store
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text


def drain(app):
    app.processEvents()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def type_text(app, widget, text):
    widget.setFocus()
    drain(app)
    widget.selectAll()
    QTest.keyClicks(widget, text)
    drain(app)


@contextmanager
def owned_window(app, root):
    with patch.object(run_history_store, 'STATE_PATH', root.parent / 'test-gui-state.json'):
        window = MainWindow(recovery_root=root, offer_recovery=False)
        window._choose_unsaved_action = lambda: QMessageBox.Discard
        try:
            yield window
        finally:
            window._choose_unsaved_action = lambda: QMessageBox.Discard
            window.close()
            drain(app)


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName('G4UniversalSimSmoke')
    app.setApplicationName('F5EditorHistory')
    messages = []
    with tempfile.TemporaryDirectory(prefix='g4usim-f5-ui-') as temp, owned_window(app, Path(temp) / 'recovery') as w:
        root = Path(temp)
        w.show()
        w.page_stack.setCurrentWidget(w.config_builder_page)
        drain(app)
        page = w.config_builder_page
        baseline = snapshot_fingerprint(w.capture_workspace())
        assert not w._edit_session.is_modified and not w._edit_session.can_undo

        # One typing gesture, one command; mirrored source controls share it.
        type_text(app, page.source_energy, '123 MeV')
        w.flush_pending_edit()
        assert page.source_editor.energy == '123 MeV'
        assert page.source_editor_energy.text() == '123 MeV'
        assert w._edit_session.history_count == 1
        assert w._edit_session.is_modified
        QTest.keyClick(page.source_energy, Qt.Key_Z, Qt.ControlModifier)
        drain(app)
        assert snapshot_fingerprint(w.capture_workspace()) == baseline
        assert not w._edit_session.is_modified
        QTest.keyClick(page.source_energy, Qt.Key_Y, Qt.ControlModifier)
        drain(app)
        assert page.source_editor.energy == '123 MeV'
        # Context-menu Undo is the same command, never QLineEdit's second stack.
        class ClickUndoMenu(QMenu):
            def exec(self, pos):
                self.actions()[0].trigger()
        with patch('g4usim_gui.window.transactions.QMenu', ClickUndoMenu):
            point = page.source_energy.rect().center()
            assert w._history_filter.eventFilter(page.source_energy, QContextMenuEvent(QContextMenuEvent.Mouse, point, page.source_energy.mapToGlobal(point)))
        assert not w._edit_session.is_modified
        w.redo_edit()
        w.undo_edit()
        type_text(app, page.seed, 'not-an-integer')
        assert page.seed.text() == 'not-an-integer' and not w._edit_session.can_redo
        invalid = w.capture_workspace()
        restored = snapshot_from_json(snapshot_to_json(invalid))
        assert restored.state['drafts']['config.seed'] == 'not-an-integer'
        w.apply_workspace(restored)
        assert page.seed.text() == 'not-an-integer'
        assert not page.validate_current(w.project).can_run

        # Whole wizard application is one command; undo does not read source.
        w._reset_edit_history()
        before = snapshot_fingerprint(w.capture_workspace())
        assert w.apply_simulation_wizard(default_spec('single_target'), run_after=False)
        assert w._edit_session.history_count == 1
        wizard_geometry = generate_geometry_ini_text(page.geometry_document)
        with (patch('g4usim_gui.widgets.config.materials.parse_materials', side_effect=AssertionError('disk reload')),
             patch('g4usim_gui.widgets.config.geometry.parse_geometry', side_effect=AssertionError('disk reload'))):
            w.undo_edit()
            assert snapshot_fingerprint(w.capture_workspace()) == before
            w.redo_edit()
        assert generate_geometry_ini_text(page.geometry_document) == wizard_geometry

        # Future callers use the same transaction by composing registered edits.
        w._reset_edit_history()
        previous_text = generate_geometry_ini_text(page.geometry_document)
        def compound(configuration, project):
            configuration.geometry_table.item(1, 4).setText('G4_Si')
            configuration.geometry_table.item(1, 6).setText('2 mm,3 mm,4 mm')
            configuration.scoring_editor_dose.setChecked(True)
        assert w.apply_editor_operation('Compound test edit', compound, expected_revision=w._edit_session.revision)
        assert w._edit_session.history_count == 1
        compound_text = generate_geometry_ini_text(page.geometry_document)
        assert compound_text != previous_text and page.scoring_editor.dose
        w.undo_edit()
        assert generate_geometry_ini_text(page.geometry_document) == previous_text
        w.redo_edit()
        assert generate_geometry_ini_text(page.geometry_document) == compound_text and page.scoring_editor.dose

        # Structured operations each form a single reversible transaction.
        w._reset_edit_history()
        n = len(page.geometry_document.volumes)
        page._add_hierarchical_volume()
        assert len(page.geometry_document.volumes) == n + 1
        assert w._edit_session.history_count == 1
        w.undo_edit()
        assert len(page.geometry_document.volumes) == n
        w.redo_edit()
        assert len(page.geometry_document.volumes) == n + 1
        page.geometry_table.selectRow(n)
        page._duplicate_hierarchical_volume()
        assert w._edit_session.history_count == 2
        assert len(page.geometry_document.volumes) == n + 2
        page.geometry_document.volumes[-1].shape_properties['test'] = 'copy-only'
        assert 'test' not in page.geometry_document.volumes[-2].shape_properties
        page.geometry_document.volumes[-1].shape_properties.pop('test')
        w.undo_edit()
        page._add_boolean_op()
        assert len(page.geometry_document.boolean_ops) == 1
        w.undo_edit()
        assert not page.geometry_document.boolean_ops

        # An in-cell edit is captured before focus-out, and Escape cancels it.
        page.workspace_tabs.setCurrentIndex(1)
        table = page.geometry_table
        table.setCurrentCell(1, 6)
        original = table.item(1, 6).text()
        table.editItem(table.item(1, 6))
        drain(app)
        editors = [item for item in table.findChildren(QLineEdit) if item.isVisible()]
        assert editors
        editor = editors[0]
        type_text(app, editor, 'unfinished unit')
        assert table.item(1, 6).text() == original
        assert w.capture_workspace().state['tables']['geometry_table'][1][6] == 'unfinished unit'
        pending = snapshot_from_json(snapshot_to_json(w.capture_workspace()))
        w.apply_workspace(pending)
        assert table.item(1, 6).text() == original
        editors = [item for item in table.findChildren(QLineEdit) if item.isVisible()]
        assert editors and editors[0].text() == 'unfinished unit'
        editor = editors[0]
        QTest.keyClick(editor, Qt.Key_Escape)
        drain(app)
        assert table.item(1, 6).text() == original

        # Material drafts and source blockers survive full persistence/replay.
        page.workspace_tabs.setCurrentIndex(0)
        page._add_material('mass_fraction')
        row = page._selected_material_row
        type_text(app, page.material_density, '  invalid density  ')
        assert page.material_density.text() == '  invalid density  '
        snapshot = snapshot_from_json(snapshot_to_json(w.capture_workspace()))
        w.apply_workspace(snapshot)
        assert page.material_document.rows[row].density == 'invalid density'
        assert page.material_density.text() == '  invalid density  '
        saved = root / '草稿.json'
        assert w._save_project_to(saved)
        assert not w._edit_session.is_modified
        loaded = load_project(saved)
        assert loaded.materialEditor.rows[row].density == 'invalid density'
        assert loaded.editingState['drafts'][f'detail.material.{row}.density'] == '  invalid density  '
        assert w._recovery_origin_path == str(saved)

        # Layer detail selection is presentation; raw whitespace remains a draft.
        back = w.capture_workspace()
        count_before_mode = w._edit_session.history_count
        page._set_geometry_template_token('layered_device')
        assert w._edit_session.history_count == count_before_mode + 1
        page._add_layer()
        layer_row = page._selected_layer_row
        page.workspace_tabs.setCurrentIndex(1)
        type_text(app, page.layer_thickness, '  unfinished  ')
        assert page.layer_thickness.text() == '  unfinished  '
        layer_snapshot = snapshot_from_json(snapshot_to_json(w.capture_workspace()))
        w.apply_workspace(layer_snapshot)
        assert page.geometry_document.layered_device.layers[layer_row].thickness == 'unfinished'
        assert page.layer_thickness.text() == '  unfinished  '
        w.apply_workspace(back)
        w._reset_edit_history()

        # Corrupt binding/table data must reject before replacing any state.
        frozen = snapshot_fingerprint(w.capture_workspace())
        for alter in (lambda state: state['drafts'].__setitem__('config.future_search', 'x'),
                      lambda state: state['tables']['geometry_table'].append(['extra'])):
            corrupt = w.capture_workspace()
            alter(corrupt.state)
            try:
                w.apply_workspace(corrupt)
                accepted = True
            except ValueError:
                accepted = False
            assert not accepted
            assert snapshot_fingerprint(w.capture_workspace()) == frozen

        # Save failure keeps original bytes, dirty state, target and history.
        type_text(app, page.material_density, '7 g/cm3')
        old_bytes, old_file = saved.read_bytes(), w.project_file
        count = w._edit_session.history_count
        with (patch('g4usim_gui.window.project.save_project', side_effect=OSError('injected save failure')),
             patch.object(QMessageBox, 'critical', side_effect=lambda *args: messages.append(args[2]))):
            assert not w._save_project_to(saved)
        assert saved.read_bytes() == old_bytes and w.project_file == old_file
        assert w._edit_session.is_modified and w._edit_session.history_count == count
        assert any('injected save failure' in text for text in messages)

        # Cancel close keeps producers/timers; Save cancellation does not close.
        w._choose_unsaved_action = lambda: QMessageBox.Cancel
        assert not w.close()
        assert not getattr(w, '_closing', False)
        w._choose_unsaved_action = lambda: QMessageBox.Save
        with patch.object(w, 'save_project', return_value=None):
            assert not w._confirm_unsaved_edits()
        w._choose_unsaved_action = lambda: QMessageBox.Discard
        assert w._confirm_unsaved_edits()
        assert w._history_discard_on_close

        # Anchors are captured at read time. Equal text at a different relative
        # location must not silently become the original restored source.
        saved_workspace = w.capture_workspace()
        old_cwd = Path.cwd()
        source_dir, other_dir = root / 'source', root / 'other'
        source_dir.mkdir(); other_dir.mkdir()
        source_text = '[NIST]\nmaterials = G4_AIR, G4_Si\n'
        (source_dir / 'materials.ini').write_text(source_text, encoding='utf-8')
        (other_dir / 'materials.ini').write_text(source_text, encoding='utf-8')
        try:
            os.chdir(source_dir)
            page.materials_config.setText('materials.ini')
            page.reload_materials()
            relative = snapshot_from_json(snapshot_to_json(w.capture_workspace()))
            assert relative.state['sources']['materials']['path'] == str((source_dir / 'materials.ini').resolve())
            os.chdir(other_dir)
            w.apply_workspace(relative)
            assert page.materials_summary.path == str((source_dir / 'materials.ini').resolve())
            assert page.materials_config.text() == 'materials.ini'
            report = page.validate_current(w.project)
            assert any(item.code == 'config.source.materials.recovered_changed' for item in report.diagnostics)
            page.materials_config.setText(str(root / 'missing-materials.ini'))
            page.reload_materials()
            missing = snapshot_from_json(snapshot_to_json(w.capture_workspace()))
            assert not missing.state['sources']['materials']['read_success']
            w.apply_workspace(missing)
            assert not page.materials_summary._f4_read_success
            assert page.material_document.source_errors
        finally:
            os.chdir(old_cwd)
            w.apply_workspace(saved_workspace)
            w._reset_edit_history(saved=False)

        # Runtime-derived package paths are excluded from configuration history.
        w.flush_pending_edit()
        prior = w.capture_workspace()
        binding = {}
        for field in ('configPath', 'macroPath', 'outputDir'):
            original = getattr(w.project, field)
            generated = str(root / ('generated-' + field))
            binding[field] = (original, generated)
            setattr(w.project, field, generated)
        w._generated_edit_binding = binding
        w.project_page.set_project(w.project)
        assert snapshot_fingerprint(w.capture_workspace()) == snapshot_fingerprint(prior)
        w._generated_edit_binding = None
        w.apply_workspace(prior)

        # Busy history is rejected; the transaction API is shared by UI callers.
        page.run_name.setText('f5-after-recovery')
        w.flush_pending_edit()
        revision = w._edit_session.revision
        with patch.object(w.runner, 'is_running', return_value=True):
            w.undo_edit()
            assert w._edit_session.revision == revision
            assert not w.can_mutate_workspace('open')
        before_diagnostic_epoch = page._diagnostic_generation
        w.undo_edit()
        assert page._diagnostic_generation > before_diagnostic_epoch
        assert w._generated_package_stale
        w.run_page.set_result('success')
        w._set_run_chip('success', 'success')
        w.run_page.set_progress_state('starting')
        w.run_page.set_progress({'run_id': 0, 'completed_events': 10, 'planned_events': 10, 'phase': 'running'})
        w.run_page.append_stdout('previous-run-evidence\n')
        w.apply_workspace(w.capture_workspace())
        assert w.run_page._result_state == 'Not run yet'
        assert w._run_chip[0] == 'Needs validation' and w.run_page._progress_data is None
        assert 'previous-run-evidence' in w.run_page.stdout_view.toPlainText()
        assert not w.scan_page._project_recovery_scope_hint.isHidden()

        # A partial Qt projection plus failed rollback must never be recorded
        # as a new successful edit. Exercise Undo, recovery reset and Open.
        page.beam_on.setValue(101)
        w.flush_pending_edit()
        safe = w._edit_session.current()
        safe_hash = snapshot_fingerprint(safe)
        revision = w._edit_session.revision
        projection = page.set_from_project
        saved_before = w._edit_session.saved_fingerprint
        def broken_projection(*args, **kwargs):
            page.beam_on.setValue(2569)
            raise RuntimeError('injected Qt projection failure after widget mutation')
        for trigger in (
                w.undo_edit,
                lambda: w._restore_recovery_payload(project_to_dict(project_for_snapshot(safe))),
                lambda: w._set_project(copy.deepcopy(safe.project))):
            with patch.object(page, 'set_from_project', broken_projection):
                try:
                    trigger()
                except TransactionApplyError as exc:
                    assert exc.rollback is not None
                else:
                    assert False, 'A double projection failure was not reported'
                assert not w.restore_last_verified_workspace()
            assert w._workspace_fault and not w.can_mutate_workspace('save')
            assert page.beam_on.value() == 2569
            assert snapshot_fingerprint(w._edit_session.current()) == safe_hash
            assert snapshot_fingerprint(w._workspace_fault_snapshot) == safe_hash
            assert w._edit_session.revision == revision
            assert w._edit_session.saved_fingerprint == saved_before
            assert not w.undo_action.isEnabled() and not w.redo_action.isEnabled()
            assert w.repair_editor_action.isVisible()
            blocked_path = root / 'must-not-save-broken.json'
            assert not w._save_project_to(blocked_path) and not blocked_path.exists()
            assert not w._generate_current_package()
            called = []
            with patch.object(w.runner, 'start', side_effect=lambda *args: called.append('run')):
                w.start_run()
                w._start_current_project()
            assert not called
            assert not w.apply_editor_operation('blocked operation', lambda *_: called.append('edit'))
            try:
                with w.workspace_transaction('blocked direct transaction'):
                    called.append('transaction')
            except ValueError:
                pass
            assert not called
            w.flush_pending_edit()
            drain(app)
            assert w._edit_session.revision == revision
            assert w.restore_last_verified_workspace()
            assert not w._workspace_fault and w.can_mutate_workspace('save')
            assert snapshot_fingerprint(w.capture_workspace()) == safe_hash
            assert page.beam_on.value() == 101
            assert w._edit_session.revision == revision and w._edit_session.saved_fingerprint == saved_before
        # A failed attempt with a successful rollback does not leave a lock.
        attempts = []
        def fail_once(*args, **kwargs):
            attempts.append(True)
            if len(attempts) == 1:
                return broken_projection(*args, **kwargs)
            return projection(*args, **kwargs)
        with patch.object(page, 'set_from_project', fail_once):
            try:
                w.undo_edit()
            except TransactionApplyError as exc:
                assert exc.rollback is None
        assert not w._workspace_fault and w.can_mutate_workspace()
        assert snapshot_fingerprint(w.capture_workspace()) == safe_hash
        assert w.close()
        drain(app)
    # Invoke the public Generate/Generate & Run signal: validation must see the
    # raw seed from either page, including after save, reopen and history replay.
    with tempfile.TemporaryDirectory(prefix='g4usim-f5-seed-') as temp, owned_window(app, Path(temp) / 'recovery') as w:
        root = Path(temp)
        page = w.config_builder_page
        with (patch.object(QMessageBox, 'warning', return_value=QMessageBox.Ok),
              patch.object(QMessageBox, 'information', return_value=QMessageBox.Ok)):
            assert w.apply_simulation_wizard(default_spec('single_target'), run_after=False)
            executable = root / 'validation-only-backend'
            executable.write_bytes(b'not executed by this test')
            w.project_page.executable.setText(str(executable))
            w.project_page.runs_root.setText(str(root / 'packages'))
            page.seed.setText('  not-an-integer  ')
            w._finish_history_merge()
            before = w._edit_session.current()
            saved = root / 'invalid-seed.json'
            assert w._save_project_to(saved)
            assert w._load_project_path(str(saved))
            assert page.seed.text() == '  not-an-integer  '
            page.seed.setText('42')
            w._finish_history_merge()
            w.undo_edit()
            assert page.seed.text() == '  not-an-integer  '
            w.redo_edit()
            assert page.seed.text() == '42'
            w.undo_edit()
            for control in (page.seed, w.project_page.seed):
                control.setText('  not-an-integer  ')
                w._finish_history_merge()
                history = w._edit_session.revision
                starts = []
                with patch.object(w, '_start_current_project', side_effect=lambda: starts.append(True)):
                    for run_after in (False, True):
                        page.generatePackageRequested.emit(run_after)
                        drain(app)
                        assert page.seed.text() == w.project_page.seed.text() == '  not-an-integer  '
                        assert not w._generated_package_dir and not starts
                        assert not page.validate_current(w.project).can_run
                        assert w._edit_session.revision == history
                        assert not list((root / 'packages').glob('*/config/main.ini'))
            for raw in ('42', ''):
                page.seed.setText(raw)
                w._finish_history_merge()
                page.generatePackageRequested.emit(False)
                drain(app)
                assert Path(w._generated_package_dir).is_dir()
                main_ini = Path(w.project.configPath).read_text(encoding='utf-8')
                assert ('seed = 42' in main_ini) if raw else ('seed =' not in main_ini)
                assert page.seed.text() == raw
    print('smoke_f5_editor_history: ok')


if __name__ == '__main__':
    main()
