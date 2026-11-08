"""Real Qt action/projection checks; no backend or generated physics run."""
from __future__ import annotations
import copy
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSignalBlocker, QLocale
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.edit_snapshot import snapshot_to_json, project_for_snapshot
from g4usim_gui.core.project import G4USimProject, load_project, save_project
from g4usim_gui.core.run_path_model import reduce_run_path, run_path_projection, BINDINGS
from g4usim_gui.core.edit_transactions import TransactionApplyError, TransactionCapacityError
from g4usim_gui.window.transactions import _write_control
from smoke_f5_editor_history import owned_window, drain, type_text



def generated_rejection_checks(app, root):
    # Same production adapter/transaction path; no backend processes.
    for binding in ('project.config_path', 'project.macro_path', 'project.output_dir'):
        for stale in (False, True):
            for mode in ('capture', 'capacity', 'projection', 'outer_capacity', 'outer_projection',
                         'outer_body', 'outer_noop', 'accepted', 'outer_accepted', 'double', 'outer_double'):
                name = binding.replace('.', '-') + '-' + str(stale) + '-' + mode
                with owned_window(app, root / name / 'recovery') as w:
                    p = G4USimProject()
                    p.runInputMode = 'generated'
                    p.configPath, p.macroPath, p.outputDir = 'old.ini', 'old.mac', 'old-out'
                    w._set_project(p)
                    w._bind_experiment_package({'package': {
                        'main_ini_path': 'display.ini', 'run_macro_path': 'display.mac',
                        'output_dir': 'display-out', 'package_dir': str(root / name / 'package')}})
                    if stale:
                        w._mark_generated_package_stale()
                    def observed():
                        return (snapshot_to_json(w._edit_session.current()),
                                w._edit_session.revision, w._edit_session.history_count,
                                copy.deepcopy(w._generated_edit_binding),
                                w._generated_package_dir, w._generated_package_stale,
                                tuple(getattr(w.project_page, key).text() for key in
                                      ('config_path', 'macro_path', 'output_dir')),
                                (w.project.configPath, w.project.macroPath, w.project.outputDir),
                                w.config_builder_page.package_label.text(),
                                w.run_page.command_preview.toPlainText(),
                                w.run_page.macro_plan_view.toPlainText())
                    before = observed()
                    epoch = w.experiment._epoch
                    original_capture = w.capture_workspace
                    capture_error = RuntimeError('unmigrated capture rejected')
                    def failed_capture():
                        original_capture()
                        raise capture_error
                    original = w._project_run_path
                    calls = []
                    injected = RuntimeError('generated view projection failed')
                    body_error = RuntimeError('outer body rejected')
                    def projection(snapshot, active=None):
                        calls.append(1)
                        original(snapshot, active)
                        if len(calls) == 1 or mode in ('double', 'outer_double'):
                            if mode == 'projection' and len(calls) == 1:
                                w.experiment.invalidate('independent-invalidation-during-rejection')
                            raise injected
                    capacity = w._edit_session.max_bytes
                    error = None
                    try:
                        if 'capacity' in mode:
                            w._edit_session.max_bytes = 1
                        projector = projection if ('projection' in mode or 'double' in mode) else original
                        if mode == 'capture':
                            # A real control has already changed when its signal dispatches.
                            widget = w._editable_controls()[binding]
                            blocker = QSignalBlocker(widget)
                            widget.setText('edited-path')
                            del blocker
                        capture = failed_capture if mode == 'capture' else original_capture
                        with patch.object(w, '_project_run_path', projector), patch.object(w, 'capture_workspace', capture):
                            if mode.startswith('outer_'):
                                with w.workspace_transaction('Generated path action'):
                                    if mode != 'outer_noop':
                                        w.edit_run_path(binding, 'edited-path')
                                    if mode == 'outer_body':
                                        raise body_error
                            else:
                                w.edit_run_path(binding, 'edited-path')
                    except Exception as exc:
                        error = exc
                    finally:
                        w._edit_session.max_bytes = capacity
                    after = observed()
                    if 'accepted' in mode:
                        assert error is None, (name, error)
                        assert after[1] == before[1] + 1 and after[2] == before[2] + 1
                        assert after[3] is None and after[5] is True
                        w.undo_edit()
                        assert w._generated_package_stale and not w._generated_edit_binding
                        w.redo_edit()
                        assert w._generated_package_stale and not w._generated_edit_binding
                    elif mode == 'outer_noop':
                        assert error is None and after == before
                    elif 'double' in mode:
                        assert isinstance(error, TransactionApplyError) and error.rollback is not None
                        assert error.original is injected
                        assert after[:3] == before[:3]
                        assert w._workspace_fault and w._generated_package_stale
                        assert not w._generated_package_dir
                        assert all(not w.can_mutate_workspace(action) for action in ('save', 'generate', 'run'))
                        assert w.restore_last_verified_workspace()
                        assert w._generated_package_stale and not w._generated_edit_binding
                    else:
                        assert error is not None, name
                        if mode == 'capture':
                            assert error is capture_error
                        elif 'capacity' in mode:
                            assert isinstance(error, TransactionCapacityError)
                        elif mode == 'outer_body':
                            assert error is body_error
                        elif mode == 'projection':
                            assert isinstance(error, TransactionApplyError) and error.original is injected
                            assert error.rollback is None
                        else:
                            assert error is injected
                        assert after == before, name
                        assert not w._workspace_fault
                    assert w.experiment._epoch >= epoch
                    if mode == 'projection':
                        assert w.experiment._epoch >= epoch + 1
                    print('generated rejection scenario:', name, flush=True)


def main():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='ar4-run-path-') as temp, owned_window(app, Path(temp)/'recovery') as w:
        page, project = w.config_builder_page, w.project_page
        p = G4USimProject()
        p.runName, p.runSettings.run_name = 'flat', 'typed'
        p.threads, p.runSettings.threads = 2, 7
        p.seed, p.runSettings.seed = ' 0042 ', 83
        w._set_project(p)
        assert project.threads.value() == 2 and page.threads.value() == 7
        assert project.seed.text() == ' 0042 ' and page.seed.text() == '83'
        captured = w.capture_workspace()
        assert captured.project.threads == 2 and captured.project.runSettings.threads == 7
        # A stale/blocked widget must not become a second model writer.
        blocker = QSignalBlocker(project.seed)
        project.seed.setText('STALE CONTROL')
        del blocker
        assert w.capture_workspace().project.seed == ' 0042 '
        w.apply_workspace(captured)
        assert project.seed.text() == ' 0042 '

        w.show()
        w.page_stack.setCurrentWidget(page)
        drain(app)
        type_text(app, page.seed, '1e')
        w.flush_pending_edit()
        assert page.seed.text() == project.seed.text() == '1e'
        assert w._edit_session.current().project.runSettings.seed is None
        assert w._edit_session.history_count == 1
        w.undo_edit()
        assert page.seed.text() == '83' and project.seed.text() == ' 0042 '
        w.redo_edit()
        assert page.seed.text() == project.seed.text() == '1e'

        w._finish_history_merge()
        page.threads.setLocale(QLocale('de_DE'))
        page.threads.setValue(1000)
        w.edit_run_path('config.threads.raw', '-')
        assert page.threads.value() == 1000 and page.threads.lineEdit().text() == '-'
        assert project.threads.value() == 1000
        assert project.threads.lineEdit().text() != '-'
        # Project's same-value mirror resets the nonactive spin through its
        # own locale, without copying Project's textual spelling.
        project.seed.setText('42')
        assert page.threads.lineEdit().text() == page.threads.textFromValue(1000)
        w.edit_run_path('config.threads.raw', '-')
        snapshot = w.capture_workspace()
        file = Path(temp)/'saved.json'
        save_project(project_for_snapshot(snapshot), file)
        w._set_project(load_project(file))
        assert page.threads.lineEdit().text() == '-'
        assert page.threads.value() == 1000

        # Generated display binding changes neither drafts nor edit identity.
        before = snapshot_to_json(w.capture_workspace())
        revision, count = w._edit_session.revision, w._edit_session.history_count
        display = copy.deepcopy(w.project)
        display.configPath, display.macroPath, display.outputDir = 'generated.ini', 'run.mac', 'generated-output'
        w._bind_experiment_package({'package': {'main_ini_path': display.configPath,
            'run_macro_path': display.macroPath, 'output_dir': display.outputDir, 'package_dir': str(Path(temp))}})
        assert snapshot_to_json(w.capture_workspace()) == before
        assert (w._edit_session.revision, w._edit_session.history_count) == (revision, count)
        assert page.threads.lineEdit().text() == '-'
        assert project.config_path.text() == 'generated.ini'

        # Compound Browse uses the same model transaction and does not capture
        # the displayed generated paths as new editable values.
        w._finish_history_merge()
        previous = snapshot_to_json(w.capture_workspace())
        with patch('g4usim_gui.widgets.project_page.QFileDialog.getOpenFileName', return_value=(str(Path(temp)/'backend.exe'), '')):
            project._browse_executable()
        assert w._edit_session.history_count == count + 1
        assert w._edit_session.current().project.executable.endswith('backend.exe')
        assert w._edit_session.current().project.configPath != 'generated.ini'
        assert w._generated_package_stale
        w.undo_edit()
        assert snapshot_to_json(w.capture_workspace()) == previous

        # Path + real reload is one transaction, retains source bytes in undo.
        source = Path(temp)/'materials.ini'
        source.write_text('[material.Si]\nbase = G4_Si\n', encoding='utf-8')
        count = w._edit_session.history_count
        with patch('g4usim_gui.widgets.config.setup_panel.QFileDialog.getOpenFileName', return_value=(str(source), '')):
            page._browse_materials()
        assert w._edit_session.current().project.pathSettings.materials_config == str(source)
        assert w._edit_session.history_count == count  # replaces the undone Browse branch
        assert w.capture_workspace().state['sources']['materials']['text'] == source.read_text()
        source.unlink()
        w.undo_edit()
        assert page.materials_config.text() == ''
        w.redo_edit()
        assert page.materials_config.text() == str(source)
        assert w.capture_workspace().state['sources']['materials']['text'].startswith('[material.Si]')

        # Every public UI binding dispatches the same production data action.
        values = ['edit-name', 'external', 'missing-backend.exe', '../workspace', 'main.ini',
                  'run.mac', 'out', 'runs', 3, ' 0042 ', 'run', 'typed-name', 5, '1e',
                  12, True, True, 'missing-materials.ini', 'missing-geometry.ini']
        keys = ['project.' + k for k in ('project_name', 'run_input_mode', 'executable',
                'workspace_root', 'config_path', 'macro_path', 'output_dir', 'runs_root',
                'threads', 'seed', 'run_name')]
        keys += ['config.' + k for k in ('run_name', 'threads', 'seed', 'beam_on',
                 'check_overlaps', 'dry_run', 'materials_config', 'geometry_config')]
        assert set(keys) == BINDINGS
        for key, value in zip(keys, values):
            w._finish_history_merge()
            before = w.run_path_snapshot()
            expected = reduce_run_path(before, key, value)
            _write_control(w._editable_controls()[key], value)
            actual = w.run_path_snapshot()
            assert {k: run_path_projection(actual)[k] for k in BINDINGS} == {
                k: run_path_projection(expected)[k] for k in BINDINGS}, key
            assert actual.project.runSettings == expected.project.runSettings, key
            assert actual.project.pathSettings == expected.project.pathSettings, key

        # The new narrow projection obeys the existing failed-rollback freeze.
        w._finish_history_merge()
        before = snapshot_to_json(w.run_path_snapshot())
        original = w._project_run_path
        calls = []
        def fail(candidate, active=None):
            calls.append(candidate)
            original(candidate, active)
            raise RuntimeError('injected run/path projection failure')
        with patch.object(w, '_project_run_path', fail):
            try:
                w.edit_run_path('config.seed', 'new invalid draft')
            except TransactionApplyError as exc:
                assert exc.rollback is not None
            else:
                raise AssertionError('projection failure accepted')
        assert len(calls) == 2
        assert snapshot_to_json(w.run_path_snapshot()) == before
        assert w._workspace_fault and not w.can_mutate_workspace('save')
        assert w.restore_last_verified_workspace()
        assert not w._workspace_fault
    with tempfile.TemporaryDirectory(prefix='ar4-generated-rejection-') as temp:
        generated_rejection_checks(app, Path(temp))
    print('AR4 Qt run/path checks passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
