from pathlib import Path
import os,sys,json,time,hashlib,copy,traceback
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')];os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QSettings
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.core import wizard
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.core.edit_snapshot import snapshot_from_json,snapshot_to_json,snapshot_fingerprint
WORK=OUT/('source-blank-'+str(time.time_ns()));WORK.mkdir()
FILES=['widgets/config_builder_page.py','window/transactions.py','widgets/diagnostic_navigation.py']
def hashes():return {p:hashlib.sha256((ROOT/'gui/g4usim_gui'/p).read_bytes()).hexdigest() for p in FILES}
start=hashes();QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(WORK/'settings'))
app=QApplication([]);app.setOrganizationName('IndependentReview');app.setApplicationName('J2OldSummaryBlank')
p=G4USimProject(executable=sys.executable,workspaceRoot=str(WORK),runsRoot=str(WORK/'runs'))
p.pathSettings=PathSettings(executable=p.executable,workspace_root=p.workspaceRoot,runs_root=p.runsRoot)
wizard.apply_to_project(p,wizard.blank_result())
source=WORK/'geometry.ini';original='[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_AIR\n[volume.OLD]\nparent=world\nshape=box\nsize=1 mm,1 mm,1 mm\nmaterial=G4_Si\n'
source.write_text(original,encoding='utf-8')
p.geometrySettings.config_path=str(source);p.pathSettings.geometry_config=str(source)
# No dirty saved document overrides the explicitly imported source.
p.geometryEditor.is_dirty=False
w=MainWindow();assert w._set_project(p) is not False;page=w.config_builder_page
results={}
try:
    assert page.geometry_summary is not None and len(page.geometry_document.volumes)==2
    page.geometry_table.selectRow(1);page.volume_details.fields['vis.alpha'].setText(' bad ');w._finish_history_merge()
    captured=w.capture_workspace();report=page.validate_current(w.project);page.set_validation_report(report)
    issue=next(d for d in report.diagnostics if d.location and d.location.field=='vis.alpha')
    source.write_text(original.replace('1 mm,1 mm,1 mm','9 mm,9 mm,9 mm'),encoding='utf-8')
    w.apply_workspace(snapshot_from_json(snapshot_to_json(captured)))
    changed=page.validate_current(w.project)
    results['restore_changed_source']={'can_run':changed.can_run,'codes':[d.code for d in changed.diagnostics if d.severity=='error'],'raw_kept':page.geometry_document.volumes[1].visual.get('vis.alpha'),'source_path':page.geometry_document.source_path,'old_diagnostic_rejected':not page.navigate_diagnostic(issue).ok}
    # Exclude the intentionally invalid vis value as a false explanation of the
    # source failure: restore the valid original snapshot with the file missing.
    safe=copy.deepcopy(captured);safe.project.geometryEditor.volumes[1].visual.pop('vis.alpha',None)
    source.rename(WORK/'geometry-away.ini')
    w.apply_workspace(safe)
    missing=page.validate_current(w.project)
    results['restore_missing_source']={'can_run':missing.can_run,'codes':[d.code for d in missing.diagnostics if d.severity=='error'],'names':[r.name for r in page.geometry_document.volumes],'source_path':page.geometry_document.source_path}
    # The real new-blank UI transition must retire all previous source evidence.
    w._choose_unsaved_action=lambda:QMessageBox.Discard
    accepted=w.new_blank_project();snap=w.capture_workspace();blank_report=page.validate_current(w.project)
    results['old_summary_to_new_blank']={'accepted':accepted,'summary_is_none':page.geometry_summary is None,'source_path':page.geometry_document.source_path,'raw_source_empty':not page.geometry_document.raw_source_text,'captured_sources':list(snap.state['sources']),'names':[r.name for r in page.geometry_document.volumes],'source_errors':page.geometry_document.source_errors,'can_run':blank_report.can_run,'old_report_rejected':not page.navigate_diagnostic(issue).ok,'raw_panel_has_old_volume':'OLD' in page.geometry_raw.toPlainText()}
finally:close_window(app,w)
result={'before':start,'after':hashes(),'sources_unchanged':start==hashes(),'results':results}
(WORK/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'latest-source-blank-receipt.txt').write_text(str(WORK/'receipt.json'),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
