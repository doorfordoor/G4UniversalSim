from pathlib import Path
import sys,os,tempfile,json,copy,hashlib
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;WORK=OUT/'source-undo-runtime';WORK.mkdir(exist_ok=True);tempfile.tempdir=str(WORK)
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QSettings
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(WORK/'settings'))
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.core import wizard
from g4usim_gui.core.project import G4USimProject,save_project,load_project
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.writers.geometry_ini_writer import write_geometry_ini
from g4usim_gui.writers.materials_ini_writer import write_materials_ini
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.window import content
app=QApplication([]);app.setOrganizationName('IndependentReview');app.setApplicationName('J2SourceUndo')
p=G4USimProject(executable=sys.executable,workspaceRoot=str(WORK),runsRoot=str(WORK/'runs'));p.pathSettings=PathSettings(executable=p.executable,workspace_root=p.workspaceRoot,runs_root=p.runsRoot);wizard.apply_to_project(p,wizard.blank_result())
geom=WORK/'source-geometry.ini';mat=WORK/'source-materials.ini';write_geometry_ini(str(geom),p.geometryEditor);write_materials_ini(str(mat),p.materialEditor)
w=MainWindow();w._set_project(p);page=w.config_builder_page;result={}
try:
    page.geometry_config.setText(str(geom));page.materials_config.setText(str(mat));page.reload_geometry();page.reload_materials();page.seed.setText('BAD-SEED');w._finish_history_merge()
    before=snapshot_fingerprint(w.capture_workspace()); source=page.geometry_document.source_path
    with patch.object(content.NewSimulationWizard,'exec',return_value=content.NewSimulationWizard.Rejected):w.open_new_simulation_wizard()
    assert snapshot_fingerprint(w.capture_workspace())==before
    result['wizard_cancel_preserves_imported_dirty_draft']=True
    assert w.apply_simulation_wizard(wizard.default_spec('single_target'),run_after=False)
    geom.unlink();mat.unlink()
    assert page.validate_current(w.project).can_run
    w.undo_edit();snap=w.capture_workspace()
    assert snapshot_fingerprint(snap)==before and page.seed.text()=='BAD-SEED'
    report=page.validate_current(w.project); codes=[d.code for d in report.diagnostics]
    assert not report.can_run and 'config.path.geometry.missing' in codes and 'config.path.materials.missing' in codes
    saved=WORK/'after-undo.json';save_project(snap.project,saved);loaded=load_project(saved)
    assert loaded.geometryEditor.source_path==source and loaded.editingState['sources']['geometry']['path']==source
    result['undo_after_sources_deleted']={'template_independent_before_undo':True,'old_snapshot_restored':True,'codes':codes,'source_anchor_retained_on_save_load':True}
finally:close_window(app,w)
(OUT/'source-undo-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
