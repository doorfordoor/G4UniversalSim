from pathlib import Path
from datetime import datetime, timezone
import os,sys,json,hashlib,traceback,tempfile,copy,shutil,subprocess
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
WORK=OUT/'runtime'
WORK.mkdir(exist_ok=True)
tempfile.tempdir=str(WORK)
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication,QMessageBox,QFileDialog
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(WORK/'settings'))
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window,wait_workflow
from g4usim_gui.core import wizard
from g4usim_gui.core.project import G4USimProject,save_project,load_project,project_to_dict
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot,snapshot_fingerprint,snapshot_to_json,snapshot_from_json
from g4usim_gui.core.experiment_bundle import export_bundle,load_bundle
from g4usim_gui.writers.package_writer import create_run_package,PackageValidationError
from g4usim_gui.editors.geometry_editor_model import HierarchicalVolumeRow
from g4usim_gui.parsers.materials_parser import parse_materials
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.editors.material_editor_model import material_document_from_summary
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
FILES=['core/wizard.py','validators/config_validator.py','window/project.py','window/content.py','window/shell.py','core/experiment_bundle.py','writers/package_writer.py','window/transactions.py','window/recovery.py']
def hashes(): return {f:hashlib.sha256((ROOT/'gui/g4usim_gui'/f).read_bytes()).hexdigest() for f in FILES}
start=hashes(); results=[]
app=QApplication.instance() or QApplication([])
app.setOrganizationName('IndependentReview');app.setApplicationName('J2Blank')
QMessageBox.warning=lambda *a,**k: QMessageBox.Ok
QMessageBox.critical=lambda *a,**k: QMessageBox.Ok

def check(name,fn):
    try:
        detail=fn(); r={'case':name,'status':'observed','detail':detail}
    except Exception as e:
        r={'case':name,'status':'harness_or_product_failure','error':str(e),'traceback':traceback.format_exc()}
    results.append(r); print(json.dumps(r,ensure_ascii=False),flush=True)
def project(name):
    base=WORK/name;base.mkdir(exist_ok=True)
    p=G4USimProject(executable=sys.executable,workspaceRoot=str(base),runsRoot=str(base/'runs'))
    p.pathSettings=PathSettings(executable=p.executable,workspace_root=p.workspaceRoot,runs_root=p.runsRoot)
    wizard.apply_to_project(p,wizard.blank_result(name)); return p

def package(p):
    return create_run_package(project=p,paths=p.pathSettings,run=p.runSettings,geometry=p.geometrySettings,source=p.sourceSettings,physics=p.physicsSettings,scoring=p.scoringSettings,material_document=p.materialEditor,geometry_document=p.geometryEditor,source_model=p.sourceEditor,physics_model=p.physicsEditor,scoring_model=p.scoringEditor)[0]
def window(p):
    w=MainWindow();w._set_project(p);return w

def isolation():
    p=project('isolation');old=package(p)
    p.pathSettings.materials_config=old.materials_ini_path;p.pathSettings.geometry_config=p.geometrySettings.config_path=old.geometry_ini_path
    p.materialEditor=material_document_from_summary(parse_materials(old.materials_ini_path))
    p.geometryEditor=geometry_document_from_summary(parse_geometry(old.geometry_ini_path,'hierarchical'))
    raw={x:Path(x).read_bytes() for x in (old.materials_ini_path,old.geometry_ini_path)}
    for scenario in wizard.SCENARIOS:
        q=copy.deepcopy(p); wizard.apply_to_project(q,wizard.build(wizard.default_spec(scenario)))
        assert not q.pathSettings.materials_config and not q.geometrySettings.config_path
        assert not q.materialEditor.source_path and not q.geometryEditor.raw_source_text
        package(q)
    for x,b in raw.items(): assert Path(x).read_bytes()==b
    return {'templates':5,'old_input_bytes_unchanged':True}

def disappeared():
    p=project('missing'); pkg=package(p)
    p.pathSettings.materials_config=pkg.materials_ini_path
    p.geometrySettings.config_path=p.pathSettings.geometry_config=pkg.geometry_ini_path
    p.materialEditor=material_document_from_summary(parse_materials(pkg.materials_ini_path));p.materialEditor.is_dirty=True
    p.geometryEditor=geometry_document_from_summary(parse_geometry(pkg.geometry_ini_path,'hierarchical'));p.geometryEditor.is_dirty=True
    Path(pkg.geometry_ini_path).unlink()
    try: package(p)
    except PackageValidationError as e:
        codes=[x.code for x in e.report.diagnostics]; assert 'config.path.geometry.missing' in codes
    else: assert False,'missing imported source accepted'
    p.geometrySettings.config_path=p.pathSettings.geometry_config='';p.pathSettings.materials_config=''
    try: package(p)
    except PackageValidationError as e:
        codes=[x.code for x in e.report.diagnostics]; assert 'config.path.geometry.required' in codes and 'config.path.materials.required' in codes
    else: assert False,'cleared controls laundered imported provenance'
    return {'missing_and_cleared_external_sources_rejected':True}

def cancel_invalid():
    w=window(project('cancel'))
    try:
        w.config_builder_page.seed.setText('not-an-integer');w._finish_history_merge()
        old=WORK/'cancel'/'old.json';w.project_file=old
        before=snapshot_fingerprint(w.capture_workspace());rev=w._edit_session.revision
        w._choose_unsaved_action=lambda: QMessageBox.Cancel
        assert not w.new_blank_project()
        assert before==snapshot_fingerprint(w.capture_workspace()) and w.project_file==old
        assert w._edit_session.revision==rev
        return {'invalid_seed_preserved':w.config_builder_page.seed.text(),'revision':rev}
    finally: w._choose_unsaved_action=lambda: QMessageBox.Discard;close_window(app,w)

def projection_failure():
    w=window(project('failure'))
    try:
        w.project_page.project_name.setText('KEEP DIRTY');w._finish_history_merge()
        old=WORK/'failure'/'old.json';w.project_file=old
        before=snapshot_fingerprint(w.capture_workspace()); rev=w._edit_session.revision
        flag_before=w._history_discard_on_close
        real=w._project_initial_projection
        def fail(p):
            real(p)
            raise ValueError('controlled projection failure after publication')
        w._choose_unsaved_action=lambda: QMessageBox.Discard
        with patch.object(w,'_project_initial_projection',side_effect=fail): ok=w.new_blank_project()
        after=snapshot_fingerprint(w.capture_workspace())
        assert not ok and after==before and w.project_file==old and rev==w._edit_session.revision
        return {'returned':ok,'old_draft_and_path_restored':True,'discard_flag_before':flag_before,'discard_flag_after':w._history_discard_on_close,'workspace_fault':w._workspace_fault}
    finally: close_window(app,w)

def preflight_failure():
    w=window(project('preflight'))
    try:
        w.project_page.project_name.setText('KEEP');w._finish_history_merge();before=snapshot_fingerprint(w.capture_workspace())
        prompts=[];w._choose_unsaved_action=lambda:prompts.append(True) or QMessageBox.Discard
        caught=None
        with patch.object(w,'_check_project_projection',side_effect=ValueError('controlled candidate rejection')):
            try: value=w.new_blank_project()
            except Exception as e: caught=type(e).__name__+': '+str(e);value=None
        assert before==snapshot_fingerprint(w.capture_workspace()) and not prompts
        return {'exception_escaped':caught,'returned':value,'no_prompt_or_mutation':True}
    finally: w._choose_unsaved_action=lambda:QMessageBox.Discard;close_window(app,w)

def wizard_undo_restore():
    w=window(project('undo'))
    try:
        page=w.config_builder_page
        page.seed.setText('invalid-draft');w._finish_history_merge()
        before=snapshot_fingerprint(w.capture_workspace())
        assert w.apply_simulation_wizard(wizard.default_spec('silicon_detector'),run_after=False)
        assert page.materials_summary is None and page.geometry_summary is None
        w.undo_edit(); assert snapshot_fingerprint(w.capture_workspace())==before
        assert page.seed.text()=='invalid-draft'
        w.redo_edit(); assert w.project.projectName=='silicon_detector'
        snapshot=w.capture_workspace(); encoded=snapshot_to_json(snapshot); restored=snapshot_from_json(encoded)
        assert snapshot_fingerprint(restored)==snapshot_fingerprint(snapshot)
        assert not restored.project.geometryEditor.source_path
        payload=project_to_dict(restored.project)
        w._restore_recovery_payload(payload)
        assert page.geometry_summary is None and page.materials_summary is None
        assert page.validate_current(w.project).can_run
        return {'undo_invalid_draft':True,'snapshot_codec':True,'recovery_projection':True,'no_stale_source_summaries':True}
    finally:close_window(app,w)

def export_reimport():
    p=project('portable');p.geometryEditor.volumes.append(HierarchicalVolumeRow(name='detector',parent='world',shape='box',size='1 mm,1 mm,1 mm',material='G4_Si',sensitive=True))
    w=window(p)
    try:
        snap=w.capture_workspace(); bundle=WORK/'portable'/'bundle';export_bundle(snap,bundle)
        moved=WORK/'moved-bundle';shutil.move(str(bundle),str(moved))
        restored=load_bundle(moved,executable=sys.executable)
        other=WORK/'elsewhere';other.mkdir(exist_ok=True)
        cwd=Path.cwd();os.chdir(other)
        try:
            w._apply_experiment_snapshot(restored)
            collected=w.capture_workspace();pkg=package(collected.project)
            assert 'detector' in Path(pkg.geometry_ini_path).read_text(encoding='utf-8')
            assert not collected.project.geometryEditor.source_path
        finally:os.chdir(cwd)
        with patch.object(QFileDialog,'getExistingDirectory',side_effect=[str(moved),str(WORK/'portable'/'new-runs')]),patch.object(QFileDialog,'getOpenFileName',return_value=(sys.executable,'')):
            w._load_experiment_bundle();wait_workflow(app,w,predicate=lambda:not w._experiment_loading)
        assert w.project_file is None
        final=w.capture_workspace(); assert not final.project.geometryEditor.source_path
        assert w.config_builder_page.validate_current(w.project).can_run
        return {'moved_bundle_fresh_cwd':True,'actual_async_gui_import':True,'collected_package':True,'source_paths':final.state.get('sources')}
    finally:close_window(app,w)

def dirty_export():
    w=window(project('dirty-export'))
    try:
        w.config_builder_page.seed.setText('bad-seed');w._finish_history_merge(); snap=w.capture_workspace()
        target=WORK/'dirty-export'/'bundle'
        try:export_bundle(snap,target)
        except ValueError as e: rejected=type(e).__name__+': '+str(e)
        else:rejected=None
        saved=WORK/'dirty-export'/'saved.json';save_project(snap.project,saved);q=load_project(saved)
        assert q.editingState['drafts']['config.seed']=='bad-seed'
        return {'export_rejection':rejected,'published':target.exists(),'ordinary_save_preserves_invalid_draft':True}
    finally:close_window(app,w)

for name,fn in [('old-input-isolation',isolation),('source-disappeared-and-cleared',disappeared),('cancel-invalid-draft',cancel_invalid),('new-projection-failure',projection_failure),('new-candidate-rejection',preflight_failure),('wizard-undo-recovery',wizard_undo_restore),('portable-async-reimport',export_reimport),('invalid-draft-export',dirty_export)]:check(name,fn)
end=hashes()
report={'started_source_sha256':start,'finished_source_sha256':end,'source_unchanged_during_run':start==end,'utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'cases':results}
(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('SOURCE_UNCHANGED',start==end,flush=True)
raise SystemExit(1 if any(x['status']!='observed' for x in results) else 0)
