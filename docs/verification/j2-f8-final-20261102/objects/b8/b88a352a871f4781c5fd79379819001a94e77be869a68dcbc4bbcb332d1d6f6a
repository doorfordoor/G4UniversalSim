from pathlib import Path
from datetime import datetime,timezone
import sys,os,tempfile,json,hashlib,copy,subprocess,traceback
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;WORK=OUT/('runtime-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'));WORK.mkdir();tempfile.tempdir=str(WORK);sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')];os.environ['QT_QPA_PLATFORM']='offscreen'
from g4usim_gui.editors.material_editor_model import MaterialDocument,MaterialRow,validate_material_document,component_source,generate_materials_ini_text,material_document_from_summary
from g4usim_gui.parsers.materials_parser import parse_materials_text
from g4usim_gui.core.project import G4USimProject,save_project,load_project
from g4usim_gui.core.nist_elements import search_elements,custom_elements
FILES=['gui/g4usim_gui/core/nist_elements.py','gui/g4usim_gui/editors/material_editor_model.py','gui/g4usim_gui/parsers/materials_parser.py','gui/g4usim_gui/widgets/config/materials.py','gui/smoke_tests/smoke_j2_materials.py']
def hashes():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}
start=hashes();results=[]
def case(name,fn):
 try:r={'case':name,'status':'observed','detail':fn()}
 except Exception as e:r={'case':name,'status':'execution_failure','error':type(e).__name__+': '+str(e),'traceback':traceback.format_exc()}
 results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
def doc(density='1 g/cm3',mode='mass_fraction',components='O:1'):
 return MaterialDocument(is_dirty=True,rows=[MaterialRow(name='Probe',mode=mode,density=density,components_text=components)])
CUSTOM='[isotope.O18]\nsymbol = O\nz = 8\nn = 18\na = 17.99916 g/mol\n\n[element.O]\nsymbol = enrichedO\nisotopes = O18:1\n'
def priority_roundtrip():
 d=doc();d.preserved_sections=[CUSTOM];validate_material_document(d);assert not d.errors,d.errors
 assert component_source('o','mass_fraction',d).kind=='custom_element' and component_source('G4_O','atom_count',d).kind=='nist_element'
 generated=generate_materials_ini_text(d);assert CUSTOM.rstrip() in generated
 parsed=material_document_from_summary(parse_materials_text(generated,source_path='roundtrip.ini'));validate_material_document(parsed);assert not parsed.errors
 assert component_source('O','mass_fraction',parsed).kind=='custom_element'
 save_project(G4USimProject(materialEditor=d),WORK/'saved.json');saved=load_project(WORK/'saved.json').materialEditor;assert saved.preserved_sections==d.preserved_sections
 assert generate_materials_ini_text(saved)==generated
 return {'custom_O_priority':True,'explicit_G4_O_NIST':True,'isotope_text_and_save_roundtrip':True,'search_Z8_names':[x.name for x in search_elements('8',elements=custom_elements(d.preserved_sections))]}
def volume_modes():
 results=[]
 for mode,components,valid in [('volume_fraction','O:1',False),('volume_fraction','G4_O:1',True),('atom_count','G4_WATER:1',False),('mass_fraction','Sii:1',False)]:
  d=doc('auto' if mode=='volume_fraction' else '1 g/cm3',mode,components);validate_material_document(d);assert bool(d.errors)!=valid,(mode,components,d.errors);results.append({'mode':mode,'components':components,'valid':not d.errors})
 d=doc('auto','volume_fraction','O:1');d.preserved_sections=[CUSTOM];d.rows.append(MaterialRow(name='O',mode='mass_fraction',density='1 g/cm3',components_text='G4_Si:1'));validate_material_document(d);assert not d.errors,d.errors;assert component_source('O','volume_fraction',d).kind=='custom_material'
 return {'mode_checks':results,'volume_material_over_same_name_custom_element':True}
def numeric():
 errors={}
 for density in ['nan g/cm3','1e999 g/cm3','0 mg/cm3','-1 kg/m3','1 frobs','1e308 g/cm3','1 G/CM3','2.7 * g/cm3','1 kg/m^3']:
  d=doc(density);validate_material_document(d);errors[density]=d.errors
 return {'density_errors':errors}
def duplicate_source():
 d=material_document_from_summary(parse_materials_text('[element.O]\nsymbol=O\nsymbol=other\nz=8\na=16 g/mol\n',source_path='bad.ini'))
 before=list(d.source_errors);assert before
 for _ in range(3):validate_material_document(d)
 assert d.source_errors==before and d.errors
 try:generate_materials_ini_text(d)
 except ValueError:blocked=True
 else:blocked=False
 assert blocked
 return {'source_errors_preserved':True,'writer_blocked':True}
def qt_memory():
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import QSettings
 QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(WORK/'settings'))
 from gui_test_window import MainWindow
 from smoke_k1_workflow import close_window
 from g4usim_gui.core.wizard import apply_to_project,blank_result
 from g4usim_gui.models.package_model import PathSettings
 from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
 app=QApplication.instance() or QApplication([]);app.setOrganizationName('IndependentReview');app.setApplicationName('MaterialsReview')
 p=G4USimProject(executable=sys.executable,workspaceRoot=str(WORK),runsRoot=str(WORK/'runs'));p.pathSettings=PathSettings(executable=p.executable,workspace_root=p.workspaceRoot,runs_root=p.runsRoot);apply_to_project(p,blank_result());p.materialEditor=doc()
 w=MainWindow();w._set_project(p)
 try:
  page=w.config_builder_page;page.materials_table.selectRow(0);page.material_density.setText('nan g/cm3');page.material_density.textEdited.emit('nan g/cm3');w._finish_history_merge();before=snapshot_fingerprint(w.capture_workspace());assert page.material_document.errors
  page.revert_materials_button.click();w._finish_history_merge();assert snapshot_fingerprint(w.capture_workspace())==before and page.material_density.text()=='nan g/cm3'
  page.material_mode.setCurrentIndex(page.material_mode.findText('volume_fraction'));assert not page.insert_element_button.isEnabled()
  return {'no_source_revert_preserves_invalid_draft':True,'volume_fraction_element_insert_disabled':True}
 finally:close_window(app,w)

BACKEND=json.loads((ROOT/'out/collab/j2-materials/backend-identities.json').read_text(encoding='utf-8'))[0]
exe=Path(BACKEND['exe']);actual_sha=hashlib.sha256(exe.read_bytes()).hexdigest();assert actual_sha==BACKEND['sha256']
def backend_density():
 result=[]
 for name,density in [('uppercase','1 G/CM3'),('asterisk','2.7 * g/cm3'),('converted-overflow','1e308 g/cm3')]:
  folder=WORK/name;folder.mkdir();material=folder/'material.ini';material.write_text('[material.Probe]\nmode=mass_fraction\ndensity='+density+'\ncomponents=O:1\n',encoding='utf-8')
  geom=folder/'geometry.ini';geom.write_text('[world]\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\n[target]\nsize=1 cm,1 cm,1 cm\nmaterial=Probe\n',encoding='utf-8')
  ini=folder/'main.ini';ini.write_text('[materials]\nfile='+material.as_posix()+'\n[geometry]\ntemplate=simple_box\nconfig='+geom.as_posix()+'\n',encoding='utf-8');macro=folder/'run.mac';macro.write_text('/run/initialize\n/run/beamOn 1\n',encoding='utf-8')
  proc=subprocess.run([str(exe),'--config',str(ini),'--macro',str(macro),'--output',str(folder/'run'),'--threads','1'],cwd=folder,capture_output=True,timeout=60);(folder/'backend.log').write_bytes(proc.stdout+proc.stderr)
  gui=doc(density);validate_material_document(gui);summary_path=folder/'run'/'run_summary.txt';summary=summary_path.read_text(encoding='utf-8') if summary_path.is_file() else ''
  result.append({'case':name,'density':density,'backend_exit_code':proc.returncode,'backend_completed':'status = completed' in summary,'gui_accepted':not gui.errors,'gui_errors':gui.errors,'log':str(folder/'backend.log')})
 return {'backend_sha256':actual_sha,'source_fingerprint_from_author_identity':BACKEND.get('source_fingerprint'),'not_current_CPP_build':True,'comparisons':result}
for name,fn in [('priority-isotope-roundtrip',priority_roundtrip),('mode-specific-components',volume_modes),('finite-units-adversarial',numeric),('source-errors-survive-validation',duplicate_source),('memory-draft-controls',qt_memory),('backend-unit-comparison',backend_density)]:case(name,fn)
end=hashes();report={'utc':datetime.now(timezone.utc).isoformat(),'runtime_root':str(WORK),'source_sha256_before':start,'source_sha256_after':end,'five_files_unchanged':start==end,'cases':results}
(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('FIVE_FILES_UNCHANGED',start==end,flush=True)
raise SystemExit(1 if any(x['status']!='observed' for x in results) else 0)
