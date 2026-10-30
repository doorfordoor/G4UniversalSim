"""Recheck original real Generate signal, then save/reopen/history boundaries."""
import json,os
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'gui'))
from PySide6.QtWidgets import QApplication,QMessageBox
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.wizard import default_spec
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.history import run_history_store
app=QApplication([]);app.setQuitOnLastWindowClosed(False);set_application_language(app,'en')
cases=[]
with tempfile.TemporaryDirectory(prefix='f5-seed-independent-recheck-') as temporary:
    root=Path(temporary);run_history_store.STATE_PATH=root/'history.json'
    w=MainWindow(recovery_root=root/'recovery',offer_recovery=False)
    w._choose_unsaved_action=lambda:QMessageBox.Discard
    warnings=[];starts=[]
    def warning(*args):warnings.append(str(args[-1]));return QMessageBox.Ok
    try:
        page=w.config_builder_page;page.preview3d_auto_backend.setChecked(False)
        with patch.object(QMessageBox,'warning',warning),patch.object(QMessageBox,'information',return_value=QMessageBox.Ok),patch.object(w,'_start_current_project',side_effect=lambda:starts.append(True)):
            assert w.apply_simulation_wizard(default_spec('single_target'),run_after=False)
            exe=root/'validation-only';exe.write_bytes(b'never executed')
            w.project_page.executable.setText(str(exe));w.project_page.runs_root.setText(str(root/'runs'))
            # Exact pre-fix trigger: config-page input, flush, real connected signal.
            page.seed.setText('not-an-integer');w.flush_pending_edit()
            assert not page.validate_current(w.project).can_run
            page.generatePackageRequested.emit(False)
            assert page.seed.text()=='not-an-integer' and not w._generated_package_dir
            assert w.project_page.seed.text()=='not-an-integer'
            assert warnings and 'seed' in warnings[-1].lower()
            assert not list((root/'runs').glob('*/config/main.ini'))
            cases.append({'case':'exact_original_Generate_signal','raw_seed':page.seed.text(),'blocked':True})
            raw='  not-an-integer  '
            page.seed.setText(raw);w._finish_history_merge()
            assert w._save_project_to(root/'unfinished.json')
            page.seed.setText('17');w._finish_history_merge()
            assert w._load_project_path(str(root/'unfinished.json'))
            assert page.seed.text()==raw
            page.seed.setText('17');w._finish_history_merge()
            w.undo_edit();assert page.seed.text()==raw
            w.redo_edit();assert page.seed.text()=='17'
            w.undo_edit();assert page.seed.text()==raw
            for name,control in [('Configuration',page.seed),('Project',w.project_page.seed)]:
                control.setText('other-invalid-value');w._finish_history_merge()
                control.setText(raw);w._finish_history_merge()
                revision=w._edit_session.revision
                for run_after in (False,True):
                    page.generatePackageRequested.emit(run_after);app.processEvents()
                    assert page.seed.text()==w.project_page.seed.text()==raw
                    assert w._edit_session.revision==revision
                    assert not w._generated_package_dir and not starts
                    assert not page.validate_current(w.project).can_run
                    assert not list((root/'runs').glob('*/config/main.ini'))
                    cases.append({'case':'persisted_history_replayed_seed','entry':name,'run_after':run_after,
                                  'raw_preserved':True,'history_unchanged':True,'generation_and_run_blocked':True})
            for raw in ('17',''):
                page.seed.setText(raw);w._finish_history_merge()
                page.generatePackageRequested.emit(False);app.processEvents()
                assert w._generated_package_dir
                text=Path(w.project.configPath).read_text(encoding='utf-8')
                assert ('seed = 17' in text) if raw else ('seed =' not in text)
                assert page.seed.text()==raw and not starts
                cases.append({'case':'valid_seed_or_empty_control','raw':raw,'generated':True,'backend_executed':False})
    finally:
        w.close();app.processEvents()
print(json.dumps(cases,ensure_ascii=False,indent=2))
