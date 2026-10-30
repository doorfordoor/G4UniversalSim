"""Independent actual Scan buttons, preserving independent cached-base scope."""
import hashlib,json,os
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'gui'))
from PySide6.QtWidgets import QApplication,QMessageBox
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.wizard import default_spec
from g4usim_gui.core.edit_transactions import TransactionApplyError
from g4usim_gui.history import run_history_store
from g4usim_gui.core.i18n import set_application_language
app=QApplication([]);app.setQuitOnLastWindowClosed(False);set_application_language(app,'en')
facts=[]
def inventory(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
with tempfile.TemporaryDirectory(prefix='f5-scan-independent-recheck-') as temporary:
    work=Path(temporary);runs=work/'packages';run_history_store.STATE_PATH=work/'state.json'
    window=MainWindow(recovery_root=work/'recovery',offer_recovery=False)
    window._choose_unsaved_action=lambda:QMessageBox.Discard
    page=window.config_builder_page;scan=window.scan_page
    try:
        with patch.object(QMessageBox,'warning',return_value=QMessageBox.Ok),patch.object(QMessageBox,'information',return_value=QMessageBox.Ok),patch.object(window.runner,'start',side_effect=AssertionError('Backend must not execute')):
            assert window.apply_simulation_wizard(default_spec('single_target'),run_after=False)
            page.preview3d_auto_backend.setChecked(False)
            fake=work/'validation-only';fake.write_bytes(b'never executed')
            window.project_page.executable.setText(str(fake));window.project_page.runs_root.setText(str(runs))
            page.seed.setText('42');page.beam_on.setValue(101);window._finish_history_merge()
            scan.refresh_button.click();assert scan._base is not None
            assert scan.select_parameter('source.energy');scan.values.setText('2 MeV');scan.name.setText('safe')
            scan.create_button.click();assert scan._manifest
            assert 'seed = 42' in Path(scan._manifest.points[0].main_ini).read_text(encoding='utf-8')
            # The already captured independent base remains usable until refresh.
            page.seed.setText('not-an-integer');window._finish_history_merge()
            scan.name.setText('safe-cached');scan.values.setText('3 MeV');scan.create_button.click()
            assert 'seed = 42' in Path(scan._manifest.points[0].main_ini).read_text(encoding='utf-8')
            facts.append({'case':'cached_independent_valid_base','still_generates_original_seed_42':True})
            before=inventory(runs);manifest=scan._manifest
            scan.refresh_button.click();scan.create_button.click()
            assert scan._base is None and scan._manifest is manifest
            assert inventory(runs)==before
            assert page.seed.text()=='not-an-integer' and scan.values.text()=='3 MeV'
            assert 'seed' in scan.status.text().lower()
            facts.append({'case':'invalid_raw_seed_current_scan_base','rejected':True,'old_files_and_scan_draft_preserved':True})
            # Exact original fault: real main widget changes before both raises.
            page.seed.setText('42');window._finish_history_merge()
            scan.refresh_button.click();assert scan._base is not None
            def broken(*args,**kwargs):
                page.beam_on.setValue(2569);raise RuntimeError('independent projection fault')
            with patch.object(page,'set_from_project',broken):
                try:window.undo_edit()
                except TransactionApplyError as exc:assert exc.rollback is not None
                else:assert False,'double failure was not reported'
            assert window._workspace_fault and page.beam_on.value()==2569
            assert window._edit_session.current().project.runSettings.beam_on==101
            before=inventory(runs);manifest=scan._manifest
            scan.refresh_button.click();scan.create_button.click()
            assert scan._base is None and scan._manifest is manifest
            assert inventory(runs)==before
            assert scan.values.text()=='3 MeV'
            assert window.restore_last_verified_workspace()
            scan.refresh_button.click();scan.name.setText('repaired');scan.create_button.click()
            assert '/run/beamOn 101' in Path(scan._manifest.points[0].macro).read_text(encoding='utf-8')
            facts.append({'case':'double_failure_current_scan_base','rejected':True,'after_explicit_repair_beam_on':101})
            # Real persisted captured source followed by external file mutation.
            material=work/'material.ini';original='[NIST]\nmaterials = G4_AIR, G4_Si\n'
            material.write_text(original,encoding='utf-8')
            page.materials_config.setText(str(material));page.reload_materials();window._finish_history_merge()
            assert window._save_project_to(work/'source-snapshot.json')
            assert window._load_project_path(str(work/'source-snapshot.json'))
            assert 'materials' in page._f5_frozen_sources
            material.write_text(original+'# externally changed\n',encoding='utf-8')
            before=inventory(runs);manifest=scan._manifest
            scan.refresh_button.click();scan.create_button.click()
            assert scan._base is None and scan._manifest is manifest and inventory(runs)==before
            assert page.material_document.raw_source_text==original
            assert 'source changed' in scan.status.text().lower()
            facts.append({'case':'recovered_material_source_changed','new_current_base_rejected':True,'captured_draft_and_old_files_preserved':True})
    finally:
        if window._workspace_fault:window.restore_last_verified_workspace()
        window.close();app.processEvents()
print(json.dumps(facts,ensure_ascii=False,indent=2))
