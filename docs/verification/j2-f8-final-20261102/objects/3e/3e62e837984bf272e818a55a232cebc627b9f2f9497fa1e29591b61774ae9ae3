from pathlib import Path
from datetime import datetime,timezone
import sys,json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'density-recheck';OUT.mkdir(exist_ok=True);WORK=OUT/('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'));WORK.mkdir();sys.path.insert(0,str(ROOT/'gui'))
from g4usim_gui.editors.material_editor_model import MaterialDocument,MaterialRow,validate_material_document,generate_materials_ini_text,density_internal_value
from g4usim_gui.parsers.materials_parser import parse_materials_text
files=['gui/g4usim_gui/editors/material_editor_model.py','gui/smoke_tests/smoke_j2_materials.py'];before={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
identity=json.loads((ROOT/'out/collab/j2-materials/backend-identities.json').read_text(encoding='utf-8'))[0];exe=Path(identity['exe']);assert hashlib.sha256(exe.read_bytes()).hexdigest()==identity['sha256'];results=[]
for index,(density,valid) in enumerate([('1 G/CM3',True),('2.7 * g/cm3',True),('0x1p0 * KG/M^3',True),('1e308 g/cm3',False),('1e287 g/cm3',False),('1e-999 mg/cm3',False)]):
 d=MaterialDocument(is_dirty=True,rows=[MaterialRow(name='Probe',mode='mass_fraction',density=density,components_text='O:1')]);validate_material_document(d);assert (not d.errors)==valid,(density,d.errors)
 try:text=generate_materials_ini_text(d);generated=True
 except ValueError:generated=False
 assert generated==valid
 if valid:assert not parse_materials_text(text,source_path='generated.ini').errors
 folder=WORK/str(index);folder.mkdir();mat=folder/'material.ini';mat.write_text('[material.Probe]\nmode=mass_fraction\ndensity='+density+'\ncomponents=O:1\n',encoding='utf-8');geom=folder/'geometry.ini';geom.write_text('[world]\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\n[target]\nsize=1 cm,1 cm,1 cm\nmaterial=Probe\n',encoding='utf-8');config=folder/'main.ini';config.write_text('[materials]\nfile='+mat.as_posix()+'\n[geometry]\ntemplate=simple_box\nconfig='+geom.as_posix()+'\n',encoding='utf-8');macro=folder/'run.mac';macro.write_text('/run/initialize\n/run/beamOn 1\n',encoding='utf-8')
 proc=subprocess.run([str(exe),'--config',str(config),'--macro',str(macro),'--output',str(folder/'run'),'--threads','1'],cwd=folder,capture_output=True,timeout=60);(folder/'backend.log').write_bytes(proc.stdout+proc.stderr);assert (proc.returncode==0)==valid,(density,proc.returncode)
 if valid:
  summary=(folder/'run/run_summary.txt').read_text(encoding='utf-8');assert 'status = completed' in summary and 'actual_completed_event_count = 1' in summary
 results.append({'density':density,'valid':valid,'gui_matches':True,'writer_matches':True,'backend_exit_code':proc.returncode})
after={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files};assert before==after
receipt={'conclusion':'M01/M02 independently closed for tested material bytes','source_sha256':after,'backend':identity,'runtime_root':str(WORK),'cases':results,'scope':'targeted fix review, existing backend not current CPP build'};(OUT/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(results,ensure_ascii=False))
