from pathlib import Path
import sys,os,json,tempfile,hashlib,copy
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;WORK=OUT/'reload-recheck-runtime';WORK.mkdir(exist_ok=True);tempfile.tempdir=str(WORK)
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QSettings
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(WORK/'settings'))
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.core import wizard
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.editors.geometry_editor_model import HierarchicalVolumeRow
from g4usim_gui.writers.geometry_ini_writer import write_geometry_ini
app=QApplication([]);app.setOrganizationName('IndependentReview');app.setApplicationName('J2Reload')
files=['widgets/config/geometry.py','widgets/config/materials.py','core/wizard.py','window/project.py','window/transactions.py']
def hashes():return {f:hashlib.sha256((ROOT/'gui/g4usim_gui'/f).read_bytes()).hexdigest() for f in files}
start=hashes();p=G4USimProject(executable=sys.executable,workspaceRoot=str(WORK),runsRoot=str(WORK/'runs'))
p.pathSettings=PathSettings(executable=p.executable,workspace_root=p.workspaceRoot,runs_root=p.runsRoot)
wizard.apply_to_project(p,wizard.blank_result())
p.geometryEditor.volumes.append(HierarchicalVolumeRow(name='KEEP',parent='world',shape='box',size='2 mm,2 mm,2 mm',material='G4_Si'))
original_doc=copy.deepcopy(p.geometryEditor)
w=MainWindow();w._set_project(p);page=w.config_builder_page
results={}
try:
    before=snapshot_fingerprint(w.capture_workspace()); names=[v.name for v in page.geometry_document.volumes]
    rev=w._edit_session.revision
    page.revert_geometry_button.click();app.processEvents();w._finish_history_merge()
    results['revert_without_source']={'before_names':names,'after_names':[v.name for v in page.geometry_document.volumes],'source_path':page.geometry_config.text(),'revision_before':rev,'revision_after':w._edit_session.revision,'can_undo':w._edit_session.can_undo,'fingerprint_changed':before!=snapshot_fingerprint(w.capture_workspace()),'message':page.geometry_messages.toPlainText()}
    if w._edit_session.can_undo:w.undo_edit()
    results['undo_after_revert']={'names':[v.name for v in page.geometry_document.volumes],'fingerprint_restored':before==snapshot_fingerprint(w.capture_workspace())}
    # Reimport real geometry into the previously memory-only editor.
    doc=copy.deepcopy(original_doc);doc.volumes[1].name='REIMPORTED';file=WORK/'new-source.ini';write_geometry_ini(str(file),doc)
    page.geometry_config.setText(str(file));page.reload_geometry();w._finish_history_merge()
    snap=w.capture_workspace()
    results['reimport_after_blank']={'names':[v.name for v in page.geometry_document.volumes],'source_path':page.geometry_document.source_path,'captured_source':snap.state['sources'].get('geometry',{}).get('path'),'raw_matches':page.geometry_document.raw_source_text==file.read_text(encoding='utf-8'),'can_run':page.validate_current(w.project).can_run}
finally:close_window(app,w)
results['source_hashes_before']=start;results['source_hashes_after']=hashes();results['source_unchanged']=start==hashes()
(OUT/'reload-recheck-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in results.items() if not k.startswith('source_hash')},ensure_ascii=False,indent=2))

