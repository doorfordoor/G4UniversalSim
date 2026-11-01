from pathlib import Path
import os,sys,json,hashlib,copy,traceback,time
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtCore import QSettings,Qt
from PySide6.QtTest import QTest
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.core import wizard
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.core.run_editor_model import GPSDefinition
from g4usim_gui.editors.geometry_editor_model import HierarchicalVolumeRow as Row
from g4usim_gui.core.edit_snapshot import snapshot_from_json,snapshot_to_json,snapshot_fingerprint
FILES=['window/transactions.py','widgets/diagnostic_navigation.py','widgets/config_builder_page.py','editors/source_physics_scoring_model.py','core/run_editor_resources.py','writers/package_writer.py']
def hashes():return {p:hashlib.sha256((ROOT/'gui/g4usim_gui'/p).read_bytes()).hexdigest() for p in FILES}
start=hashes()
WORK=OUT/('workspace-'+str(time.time_ns()));WORK.mkdir()
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(WORK/'settings'))
app=QApplication([]);app.setOrganizationName('IndependentReview');app.setApplicationName('J2Integration')
p=G4USimProject(executable=sys.executable,workspaceRoot=str(WORK),runsRoot=str(WORK/'runs'))
p.pathSettings=PathSettings(executable=p.executable,workspace_root=p.workspaceRoot,runs_root=p.runsRoot)
wizard.apply_to_project(p,wizard.blank_result())
p.geometryEditor.volumes.extend([Row(name='A',parent='world',shape='box',size='1 mm,1 mm,1 mm',material='G4_Si'),Row(name='B',parent='world',shape='box',size='2 mm,2 mm,2 mm',material='G4_Si')])
p.sourceEditor.gps_sources=[GPSDefinition(name='first',energy='1 MeV'),GPSDefinition(name='second',energy='1 MeV')]
w=MainWindow();assert w._set_project(p) is not False;page=w.config_builder_page
w.show();app.processEvents();results={}
def run(name,fn):
    try:results[name]=fn()
    except Exception as exc:results[name]={'unexpected_error':repr(exc),'traceback':traceback.format_exc()}
    print(name,json.dumps(results[name],ensure_ascii=False),flush=True)
def report_issue(field):
    report=page.validate_current(w.project);page.set_validation_report(report)
    return next(d for d in report.diagnostics if d.location and d.location.field==field)
def select_geometry(index):page.geometry_table.selectRow(index)
def typed(control,text):
    control.setFocus();control.selectAll();QTest.keyClicks(control,text)
def fast_programmatic():
    select_geometry(1);edit=page.volume_details.fields['vis.alpha']
    edit.setText('  programmatic-invalid  ')
    select_geometry(2);w._finish_history_merge()
    snap=w.capture_workspace()
    return {'a_raw':snap.project.geometryEditor.volumes[1].visual.get('vis.alpha'),'b_raw':snap.project.geometryEditor.volumes[2].visual.get('vis.alpha'),'wanted':'  programmatic-invalid  '}
def actual_typing():
    select_geometry(1);edit=page.volume_details.fields['vis.alpha']
    typed(edit,'  typed-invalid  ');select_geometry(2);w._finish_history_merge()
    raw=w.capture_workspace().project.geometryEditor.volumes[1].visual.get('vis.alpha')
    w.undo_edit();after_undo=page.geometry_document.volumes[1].visual.get('vis.alpha')
    w.redo_edit();after_redo=page.geometry_document.volumes[1].visual.get('vis.alpha')
    return {'raw':raw,'undo':after_undo,'redo':after_redo,'pass':raw==after_redo=='  typed-invalid  '}
def selection_navigation():
    select_geometry(1);issue=report_issue('vis.alpha')
    rev=w._edit_session.revision;gen=page._diagnostic_generation
    select_geometry(2);app.processEvents();w._finish_history_merge()
    result=page.navigate_diagnostic(issue)
    return {'generation_unchanged':page._diagnostic_generation==gen,'revision_unchanged':w._edit_session.revision==rev,'navigation_ok':result.ok,'row':page.geometry_table.currentRow(),'raw':page.volume_details.fields['vis.alpha'].text()}
def source_identity():
    editor=page.j2_run_editors.row_editors['gps_sources'];editor.list.setCurrentRow(1)
    identity=editor.rows[1].editor_id
    typed(editor.controls['energy'],' bad-energy ');w._finish_history_merge()
    issue=report_issue('energy')
    editor.list.setCurrentRow(0);good=page.navigate_diagnostic(issue)
    editor._structure('Move up');w._finish_history_merge()
    stale=page.navigate_diagnostic(issue)
    current=report_issue('energy')
    w.undo_edit();old_after_undo=page.navigate_diagnostic(current)
    w.redo_edit();old_after_redo=page.navigate_diagnostic(current)
    return {'original_id':identity,'first_entity':issue.location.entity,'first_row':issue.location.row,'focus_after_select':good.ok,'new_entity':current.location.entity,'new_row':current.location.row,'old_after_move':stale.ok,'old_after_undo':old_after_undo.ok,'old_after_redo':old_after_redo.ok,'pass':good.ok and current.location.entity==identity and current.location.row==0 and not stale.ok and not old_after_undo.ok and not old_after_redo.ok}
def recovery():
    select_geometry(1)
    typed(page.volume_details.fields['vis.alpha'],'  nan  ');w._finish_history_merge()
    old=report_issue('vis.alpha');snap=w.capture_workspace()
    token=snapshot_to_json(snap);restored=snapshot_from_json(token)
    w.apply_workspace(restored)
    now=w.capture_workspace();stale=page.navigate_diagnostic(old)
    return {'raw':now.project.geometryEditor.volumes[1].visual.get('vis.alpha'),'fingerprint_equal':snapshot_fingerprint(now)==snapshot_fingerprint(snap),'old_report_rejected':not stale.ok,'source_path':now.project.geometryEditor.source_path}
try:
    run('programmatic-raw-immediate-selection',fast_programmatic)
    run('real-typing-selection-undo-redo',actual_typing)
    run('geometry-selection-navigation',selection_navigation)
    run('source-stable-id-reorder',source_identity)
    run('recovery-invalidates-report',recovery)
finally:close_window(app,w)
result={'before':start,'after':hashes(),'sources_unchanged':start==hashes(),'results':results}
(WORK/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'latest-workspace-receipt.txt').write_text(str(WORK/'receipt.json'),encoding='utf-8')
print('receipt',WORK/'receipt.json',flush=True)
