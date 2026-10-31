"""Real MainWindow bundle import/collect regression, offscreen only.

Dialogs are mocked automation, never native-UI evidence. Default components
validates fields without a backend; --mode backend additionally initializes
and completes real events through the window's existing action signal.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from uuid import uuid4
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(os.environ.get('K1_WORKSPACE_ROOT', Path(__file__).resolve().parents[2]))
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'gui/smoke_tests'), str(ROOT / 'scripts')]


def wait(app, predicate, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(.005)
    assert predicate(), 'Relocated GUI workflow did not drain'


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def import_ui(app, window, directory, executable, runs):
    from PySide6.QtWidgets import QFileDialog
    runs.mkdir(parents=True)
    with patch.object(QFileDialog, 'getExistingDirectory', side_effect=[str(directory), str(runs)]), \
            patch.object(QFileDialog, 'getOpenFileName', return_value=(str(executable), '')):
        window.run_page.experiment_panel.action_requested.emit('import')
    wait(app, lambda: not window._experiment_loading and not window.experiment.busy)
    assert window.project_file is None
    assert window.project.executable == str(executable)
    assert Path(window.project.runsRoot) == runs


def action(app, window, received, name):
    before = len(received)
    window.run_page.experiment_panel.action_requested.emit(name)
    wait(app, lambda: len(received) > before and not window.experiment.busy)
    assert received[-1]['status'] != 'pending'
    return received[-1]


def assert_paths(window, root):
    snapshot = window.capture_workspace()
    for control, value, draft in (
        (window.config_builder_page.materials_config, snapshot.project.pathSettings.materials_config, 'config.materials_config'),
        (window.config_builder_page.geometry_config, snapshot.project.geometrySettings.config_path, 'config.geometry_config'),
    ):
        assert Path(control.text().strip()).is_absolute(), control.text()
        assert Path(value).is_relative_to(root), value
        assert Path(value).is_file(), value
        assert snapshot.state['drafts'][draft] == control.text()
        assert Path(snapshot.state['drafts'][draft].strip()) == Path(value)
    assert snapshot.project.pathSettings.geometry_config == snapshot.project.geometrySettings.config_path
    for source in snapshot.state['sources'].values():
        assert Path(source['path']).is_relative_to(root), source['path']
    return snapshot


def exercise(args):
    root = Path(args.evidence_root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    executable = Path(args.executable).resolve() if args.mode == 'backend' else Path(sys.executable).resolve()
    assert executable.is_file()
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox
    from gui_test_window import MainWindow
    from test_f5_transactions_backend import initial_state
    from g4usim_gui.core.experiment_bundle import load_bundle, export_bundle
    from g4usim_gui.core.project import load_project
    from g4usim_gui.core.edit_snapshot import snapshot_to_json, snapshot_from_json
    app = QApplication.instance() or QApplication([])
    window = MainWindow(recovery_root=root / 'recovery')
    received, warnings = [], []
    window.experiment.completed.connect(received.append)
    try:
        with patch.object(QMessageBox, 'warning', side_effect=lambda *a: warnings.append(a[-1])), \
                patch.object(QMessageBox, 'critical', side_effect=lambda *a: warnings.append(a[-1])):
            if args.source_bundle:
                original = Path(args.source_bundle).resolve()
            else:
                inputs = root / 'source-inputs'
                inputs.mkdir()
                snapshot, _ = initial_state(inputs, executable)
                window._edit_session.reset(snapshot, saved=True, apply=window.apply_workspace)
                window.history_changed()
                with patch.object(QFileDialog, 'getExistingDirectory', return_value=str(root)), \
                        patch.object(QInputDialog, 'getText', return_value=('exported-source', True)):
                    record = action(app, window, received, 'export')
                assert record['status'] == 'passed', record['reason']
                original = root / 'exported-source'
            original_sha = hashes(original)
            moved = root / '搬移 clean' / '实验包'
            shutil.copytree(original, moved)
            assert hashes(moved) == original_sha
            # For generated test inputs, hide the original tree after byte-copy.
            # Never touch the user-supplied actualUI export or its source files.
            if not args.source_bundle:
                (root / 'source-inputs').rename(root / 'hidden-original-inputs')
                original.rename(root / 'hidden-original-export')
                original = root / 'hidden-original-export'
            imports_before = len(received)
            import_ui(app, window, moved, executable, root / 'fresh-runs')
            assert len(received) > imports_before
            assert not any(r.get('action') == 'run' and not r.get('stale') for r in window.experiment.records())
            before_starts = []
            window.runner.stateChanged.connect(before_starts.append)
            fields = action(app, window, received, 'validate')
            print('post-import field status:', fields['status'], fields['reason'], flush=True)
            if fields['status'] != 'passed':
                print(fields.get('report').errors if fields.get('report') else fields.get('diagnostics'), flush=True)
            assert fields['status'] == 'passed', 'Relocated GUI collect must not report existing resources missing'
            assert not before_starts, 'Fields must not start a backend'
            normalized = assert_paths(window, moved)
            assert hashes(moved) == original_sha
            if args.counterexample:
                return

            # A repeated no-edit collect must preserve resource selection.
            window._finish_history_merge()
            revision = window._edit_session.revision
            window._finish_history_merge()
            assert window._edit_session.revision == revision
            assert_paths(window, moved)
            if args.mode == 'backend':
                initialized = action(app, window, received, 'initialize')
                assert initialized['status'] == 'passed', initialized['reason']
                assert initialized['result']['state'] == 'no_run'
                completed = action(app, window, received, 'run')
                assert completed['status'] == 'passed', completed['reason']
                assert completed['result']['completed_events'] == completed['result']['planned_events'] == 3
                assert completed['execution_id']
                assert_paths(window, moved)

            # Real editor signals, F5 undo/redo, then ordinary save/reopen from a
            # different parent. Persisted paths cannot depend on project_file.
            old_seed = window.config_builder_page.seed.text()
            window.config_builder_page.seed.setText(str(int(old_seed) + 1))
            window._finish_history_merge()
            assert_paths(window, moved)
            window.undo_edit()
            assert window.config_builder_page.seed.text() == old_seed
            assert_paths(window, moved)
            window.redo_edit()
            assert window.config_builder_page.seed.text() != old_seed
            assert_paths(window, moved)
            window.undo_edit()
            saved = root / 'ordinary save elsewhere' / 'workspace.json'
            saved.parent.mkdir()
            assert window._save_project_to(saved)
            persisted = load_project(saved)
            assert Path(persisted.pathSettings.materials_config).is_relative_to(moved)
            assert persisted.editingState['drafts']['config.materials_config'] == normalized.state['drafts']['config.materials_config']
            assert window._load_project_path(str(saved))
            assert_paths(window, moved)
            restored = snapshot_from_json(snapshot_to_json(window.capture_workspace()))
            assert restored.state['drafts']['config.geometry_config'] == window.config_builder_page.geometry_config.text()
            assert action(app, window, received, 'validate')['status'] == 'passed'
            if args.mode == 'backend':
                rerun = action(app, window, received, 'run')
                assert rerun['status'] == 'passed', rerun['reason']
                assert rerun['result']['completed_events'] == 3
                assert rerun['run_id'] != completed['run_id']
                assert rerun['execution_id'] != completed['execution_id']

            # Equivalent lexical whitespace stays present. Empty and invalid
            # drafts must survive loading and remain rejected by the real UI.
            variant = load_bundle(moved, executable=str(executable))
            for binding in ('config.materials_config', 'config.geometry_config'):
                variant.state['drafts'][binding] = ' \t' + variant.state['drafts'][binding] + '  '
            variant.state['drafts']['config.seed'] = 'not-a-seed'
            invalid_bundle = root / 'invalid-seed-bundle'
            export_bundle(variant, invalid_bundle)
            invalid_loaded = load_bundle(invalid_bundle, executable=str(executable))
            for binding in ('config.materials_config', 'config.geometry_config'):
                text = invalid_loaded.state['drafts'][binding]
                assert text.startswith(' \t') and text.endswith('  ')
                assert Path(text.strip()).is_relative_to(invalid_bundle)
            assert invalid_loaded.state['drafts']['config.seed'] == 'not-a-seed'
            import_ui(app, window, invalid_bundle, executable, root / 'invalid-seed-runs')
            assert window.config_builder_page.seed.text() == 'not-a-seed'
            assert action(app, window, received, 'validate')['status'] == 'failed'
            assert window.config_builder_page.seed.text() == 'not-a-seed'

            for raw in ('', 'not-existing-resource.ini'):
                invalid = load_bundle(moved, executable=str(executable))
                invalid.state['drafts']['config.materials_config'] = raw
                name = 'blank' if not raw else 'missing'
                target = root / (name + '-draft-bundle')
                export_bundle(invalid, target)
                assert load_bundle(target).state['drafts']['config.materials_config'] == raw
                import_ui(app, window, target, executable, root / (name + '-runs'))
                assert window.config_builder_page.materials_config.text() == raw
                rejected = action(app, window, received, 'validate')
                assert rejected['status'] == 'failed'
                assert window.config_builder_page.materials_config.text() == raw

            # External main/macro drafts use the same verified relocation;
            # this check is about the load codec, not extra backend execution.
            external = load_bundle(moved, executable=str(executable))
            replay = external.transient['bundle']['replay_inputs']
            external.project.runInputMode = 'external'
            external.state['drafts']['project.run_input_mode'] = 'external'
            for field, binding, key in (('configPath', 'project.config_path', 'config'),
                                         ('macroPath', 'project.macro_path', 'macro')):
                path = str(moved / replay[key])
                setattr(external.project, field, path)
                external.state['drafts'][binding] = '  ' + path + '\t'
            external_bundle = root / 'external-drafts-bundle'
            export_bundle(external, external_bundle)
            external_loaded = load_bundle(external_bundle, executable=str(executable))
            for field, binding in (('configPath', 'project.config_path'), ('macroPath', 'project.macro_path')):
                raw = external_loaded.state['drafts'][binding]
                assert raw.startswith('  ') and raw.endswith('\t')
                assert raw.strip() == getattr(external_loaded.project, field)
                assert Path(raw.strip()).is_relative_to(external_bundle)

            assert hashes(moved) == original_sha
            assert hashes(original) == original_sha
            result = {'mode': args.mode, 'native_ui_observed': False, 'dialogs': 'mocked automation only',
                'bundle_source': str(original), 'relocated_bundle': str(moved), 'input_sha256': original_sha,
                'records': [{k: r.get(k) for k in ('record_id', 'run_id', 'action', 'level', 'status', 'revision', 'reason',
                                                  'result', 'execution_id', 'actual_inputs', 'output_dir')}
                            for r in received], 'backend_sha256': hashlib.sha256(executable.read_bytes()).hexdigest()
                            if args.mode == 'backend' else None}
            (root / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            print('smoke_k1_relocation: OK;', args.mode, 'real MainWindow import/collect/actions/undo/save-reopen; raw rejections preserved')
    finally:
        if window.experiment.busy:
            window.experiment.cancel(force=True)
        wait(app, lambda: not window.experiment.busy and not window._experiment_loading)
        window.experiment.close()
        wait(app, lambda: window.experiment._closed)
        assert not window.runner.is_running()
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['components', 'backend'], default='components')
    parser.add_argument('--executable', default=os.environ.get('G4USIM_EXE'))
    parser.add_argument('--source-bundle')
    parser.add_argument('--evidence-root')
    parser.add_argument('--counterexample', action='store_true')
    args = parser.parse_args()
    if args.evidence_root:
        exercise(args)
    elif os.environ.get('G4USIM_TEST_EVIDENCE_DIR'):
        parent = Path(os.environ['G4USIM_TEST_EVIDENCE_DIR']).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        args.evidence_root = str(parent / ('k1-relocation-' + uuid4().hex))
        exercise(args)
    else:
        with tempfile.TemporaryDirectory(prefix='k1-relocation-') as directory:
            args.evidence_root = str(Path(directory).resolve() / 'evidence')
            exercise(args)


if __name__ == '__main__':
    main()
