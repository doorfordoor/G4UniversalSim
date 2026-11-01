from pathlib import Path
import sys,json,copy,hashlib,os,subprocess
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'gui'));sys.path.insert(0,str(ROOT/'scripts'))
from run_m0_tests import workspace_source_fingerprint
from g4usim_gui.editors.geometry_editor_model import GeometryDocument,HierarchicalVolumeRow as R,validate_geometry_document
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.core.diagnostics import collect_diagnostics
OUT=Path(__file__).resolve().parent/'supplement';OUT.mkdir(exist_ok=False)
model_path=ROOT/'gui/g4usim_gui/editors/geometry_editor_model.py';before_sha=hashlib.sha256(model_path.read_bytes()).hexdigest();before_cpp=workspace_source_fingerprint()
exe=ROOT/'out/build-i2-formal113/Release/G4UniversalSim.exe';env=dict(os.environ)
for k in list(env):
 if (k.startswith('G4') and k.endswith('DATA')) or k=='GEANT4_DATA_DIR':env.pop(k,None)
env.update(GEANT4_DATA_DIR='D:/ProgramFiles/Geant4/share/Geant4/data',G4USIM_GEANT4_DATA='D:/ProgramFiles/Geant4/share/Geant4/data');env['PATH']='D:/ProgramFiles/Geant4/bin;D:/ProgramFiles/Qt/5.15.2/msvc2019_64/bin;'+env.get('PATH','')
observations=[]
def make(row):return GeometryDocument(mode='hierarchical',volumes=[R(name='world',shape='box',size='100 mm,100 mm,100 mm',material='G4_Galactic'),row])
def audit(name,d,blocked,fields=(),backend=False):
 folder=OUT/name;folder.mkdir();raw=[{k:getattr(row,k) for k in ('parameters','size','position','rotation')} for row in d.volumes]
 validate_geometry_document(d,material_names={'G4_Galactic'})
 got_fields={x.location.field for x in collect_diagnostics(d) if x.severity=='error' and x.location}
 assert set(fields)<=got_fields,(name,got_fields)
 try:text=generate_geometry_ini_text(d);accepted=True
 except ValueError:text=None;accepted=False
 assert accepted!=blocked,(name,d.errors)
 assert raw==[{k:getattr(row,k) for k in ('parameters','size','position','rotation')} for row in d.volumes],name
 record={'name':name,'writer_accepted':accepted,'errors':d.errors,'diagnostic_fields':sorted(got_fields),'raw_preserved':True}
 if backend:
  assert text is not None
  (folder/'geometry.ini').write_text(text,encoding='utf-8')
  (folder/'main.ini').write_text('[materials]\nfile='+str(ROOT/'config/materials/material.ini')+'\n[geometry]\ntemplate=hierarchical\nconfig=geometry.ini\n[physics]\nreference=FTFP_BERT\n[source]\npreset=mono_proton\n')
  r=subprocess.run([str(exe),'--config','main.ini','--inspect-run'],cwd=folder,env=env,capture_output=True,timeout=30)
  (folder/'stdout.log').write_bytes(r.stdout);(folder/'stderr.log').write_bytes(r.stderr)
  assert r.returncode==0,(name,(r.stdout+r.stderr).decode('utf-8','replace'))
  record['backend_exit']=r.returncode
 observations.append(record)
for name,value in [('ten-token','0 mm 10 mm 20 mm 0 deg 360 deg'),('five-token','0 10 20 0 6.283185307179586')]:
 audit(name,make(R(name='V',parent='world',shape='tubs',parameters=value,material='G4_Galactic')),False,backend=True)
csv=ROOT/'out/collab/j2-geometry-review/p2-recheck/r3/resources/moved.csv'
for name,pos,rot,fields in [('position',' 0 mm,0 mm,0 mm ','',('position',)),('rotation','',' 0 deg,0 deg,0 deg ',('rotation',)),('both','0,0,0','0,0,0',('position','rotation'))]:
 audit('table-'+name,make(R(name='V',parent='world',shape='box',size='1 mm,1 mm,1 mm',material='G4_Galactic',position=pos,rotation=rot,preview_properties={'placement':'parameterised','copies_file':str(csv)})),True,fields)
world=R(name='world',shape='box',size='1,1,2 cm',material='G4_Galactic')
for name,size,blocked in [('good','1 mm,1 mm,1 cm',False),('wrong-cross-section','10 mm,10 mm,1 cm',True)]:
 d=GeometryDocument(mode='hierarchical',volumes=[copy.deepcopy(world),R(name='V',parent='world',shape='box',size=size,material='G4_Galactic',preview_properties={'placement':'replica','replica_axis':'z','replica_count':'2','replica_width':'1 cm'})])
 audit('mixed-replica-'+name,d,blocked,backend=not blocked)
assert before_sha==hashlib.sha256(model_path.read_bytes()).hexdigest()
assert before_cpp==workspace_source_fingerprint()
receipt={'status':'passed','cases':len(observations),'source_sha256':before_sha,'cpp_source_fingerprint':before_cpp,'source_unchanged':True,'observations':observations}
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False,indent=2))
