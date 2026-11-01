from pathlib import Path
from dataclasses import asdict
import os,sys,hashlib,json,importlib,difflib
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent;DRAFT=ROOT/'out/collab/j2-f8-repair-draft-v2'
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path.insert(0,str(ROOT/'gui'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((DRAFT/'manifest.json').read_text())
for f in manifest['files']:
    assert sha(ROOT/f['path'])==f['original_raw_sha256']
    assert sha(DRAFT/'files'/f['path'])==f['candidate_sha256']
v1=ROOT/'out/collab/j2-f8-repair-draft/files/gui/g4usim_gui/editors/material_editor_model.py'
v2=DRAFT/'files/gui/g4usim_gui/editors/material_editor_model.py'
diff=list(difflib.unified_diff(v1.read_text(encoding='utf-8').splitlines(),v2.read_text(encoding='utf-8').splitlines()))
assert len([line for line in diff if line.startswith('+') and not line.startswith('+++')])==1
for short in ['core.i18n','editors.material_editor_model','editors.source_physics_scoring_model','validators.config_validator']:
    module=importlib.import_module('g4usim_gui.'+short);path=DRAFT/'files'/Path(module.__file__).relative_to(ROOT)
    exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),module.__dict__)
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QSignalSpy,QTest
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
from g4usim_gui.editors.material_editor_model import MaterialDocument,MaterialRow
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.diagnostics import diagnostics_to_dict,diagnostics_from_dict
app=QApplication([]);app.setStyle('Fusion');page=ConfigBuilderPage();page._backend_timer.stop();page.schedule_backend_geometry=lambda *a,**k:None
from g4usim_gui.core import wizard
project=G4USimProject();wizard.apply_to_project(project,wizard.blank_result())
project.pathSettings.executable=sys.executable;project.pathSettings.runs_root=str(OUT/'runs');project.pathSettings.workspace_root=str(ROOT)
project.executable=sys.executable;project.runsRoot=str(OUT/'runs');project.workspaceRoot=str(ROOT)
page.set_from_project(project)
page.resize(1200,800);page.show();QTest.qWait(25)
rows=[]
try:
 for language in ['en','zh_CN']:
  set_application_language(app,language);page.refresh_language()
  for label,name,alias,source in [('direct','Unknown','',''),('direct_whitespace','Unknown','  ',''),('alias','Alias','Unknown','source'),('explicit_same_nonG4','Unknown','Unknown','source')]:
    text='[material.'+name+']\nmode=nist\nnist_name='+alias+'\n'
    source_path=OUT/(label+'-'+language+'.ini')
    if source:source_path.write_text(text,encoding='utf-8')
    page.material_document=MaterialDocument(rows=[MaterialRow(name=name,mode='nist',nist_name=alias)],is_dirty=True,source_path=str(source_path) if source else '',raw_source_text=text if source else '')
    page._populate_material_editor();page.materials_table.selectRow(0);page._select_material_row(0)
    report=page.validate_current(project);page.set_validation_report(report)
    print('case',language,label,flush=True)
    record=next(d for d in page.diagnostic_panel.records if d.code=='materials.nist.unknown')
    if not alias.strip():
      assert record.location and record.location.field=='name' and record.location.row==0
      assert not record.unavailable_reason
    else:
      assert record.location is None and record.unavailable_reason=='unsupported_editor'
      assert record.source and record.source.filename==str(source_path)
    snapshot=page._current_diagnostic_snapshot();before=asdict(page.material_document);signal=QSignalSpy(page.settingsChanged)
    outcome=page.navigate_diagnostic(record);app.processEvents()
    if not alias.strip():
      assert outcome.ok and outcome.widget is page.material_name,(label,outcome)
      assert app.focusWidget() is page.material_name,(label,app.focusWidget())
      assert page.material_name.property('diagnosticFocus') is True
      assert page.material_name.text()==name
    else:
      assert outcome.status=='source_shown',(label,outcome)
      assert app.focusWidget() is not page.material_name
    assert asdict(page.material_document)==before and page._current_diagnostic_snapshot()==snapshot
    assert signal.count()==0
    payload=diagnostics_to_dict([record]);assert diagnostics_from_dict(payload).diagnostics[0].identity==record.identity
    rows.append({'language':language,'case':label,'location':asdict(record.location) if record.location else None,'unavailable_reason':record.unavailable_reason,'navigation':outcome.status,'no_model_change':True})
finally:
 page.close();page.deleteLater();app.processEvents()
for f in manifest['files']:assert sha(ROOT/f['path'])==f['original_raw_sha256']
result={'passed':True,'delta_added_lines':1,'v2_material_candidate_sha256':sha(v2),'cases':rows,'tracked_unchanged':True,'no_backend_or_native':True}
(OUT/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))



