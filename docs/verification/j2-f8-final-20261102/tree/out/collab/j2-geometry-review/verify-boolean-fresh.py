"""Independent post-fix trd/trap Inspect; never builds or edits product files."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'gui'));sys.path.insert(0,str(ROOT/'scripts'))
from run_m0_tests import workspace_source_fingerprint
from g4usim_gui.editors.geometry_editor_model import GeometryDocument,HierarchicalVolumeRow as R,BooleanOperationRow as B,geometry_document_from_summary
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--executable',type=Path,required=True);p.add_argument('--sdk-bin',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True);p.add_argument('--fingerprint',required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
assert a.fingerprint!='149b25dd00773898c324d09a53dd1ef64b0bf37bc105ca0f74d0c4933245756f','Use the post-Boolean-fix identity'
assert workspace_source_fingerprint()==a.fingerprint,'Workspace no longer matches requested identity'
env=dict(os.environ)
for key in list(env):
 if (key.startswith('G4') and key.endswith('DATA')) or key=='GEANT4_DATA_DIR':env.pop(key,None)
env.update(GEANT4_DATA_DIR=str(a.data_root.resolve()),G4USIM_GEANT4_DATA=str(a.data_root.resolve()))
env['PATH']=str(a.sdk_bin.resolve())+';D:/ProgramFiles/Qt/5.15.2/msvc2019_64/bin;'+env.get('PATH','')
exe=a.executable.resolve();exe_sha=hashlib.sha256(exe.read_bytes()).hexdigest()
def invoke(directory,args):
 r=subprocess.run([str(exe),*args],cwd=directory,env=env,capture_output=True,timeout=60)
 (directory/'stdout.log').write_bytes(r.stdout);(directory/'stderr.log').write_bytes(r.stderr)
 return r
capdir=a.output/'capabilities';capdir.mkdir();r=invoke(capdir,['--capabilities']);assert r.returncode==0
cap=json.loads(r.stdout);assert cap['source_fingerprint']==a.fingerprint
receipt={'executable':str(exe),'executable_sha256':exe_sha,'source_fingerprint':a.fingerprint,'capabilities':cap,'results':[]}
(a.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
props={'trd':{'dx1':'1 mm','dx2':'2 mm','dy1':'1 mm','dy2':'1 mm','dz':'2 mm'},
       'trap':{'dz':'2 mm','theta':'0 deg','phi':'0 deg','dy1':'1 mm','dx1':'1 mm','dx2':'1 mm','alpha1':'0 deg','dy2':'1 mm','dx3':'1 mm','dx4':'1 mm','alpha2':'0 deg'}}
for shape,fields in props.items():
 for invalid in (False,True):
  name=shape+('-missing-field' if invalid else '-valid');out=a.output/name;out.mkdir()
  model=GeometryDocument(mode='hierarchical_boolean',volumes=[R(name='world',shape='box',size='100 mm,100 mm,100 mm',material='G4_Galactic'),R(name='V',parent='world',shape='box',size='20 mm,20 mm,20 mm',material='G4_Galactic')],boolean_ops=[B(target_volume='V',operation='subtraction',tool_shape=shape,shape_properties=dict(fields))])
  text=generate_geometry_ini_text(model)
  summary=geometry_document_from_summary(parse_geometry_text(text,source_path=out/'geometry.ini',template_name='hierarchical'))
  assert summary.boolean_ops[0].shape_properties==fields,'Writer/parser lost Boolean attributes'
  if invalid:text='\n'.join(line for line in text.splitlines() if not line.startswith('dx1 ='))+'\n'
  (out/'geometry.ini').write_text(text,encoding='utf-8')
  (out/'main.ini').write_text('[materials]\nfile='+str(ROOT/'config/materials/material.ini')+'\n[geometry]\ntemplate=hierarchical\nconfig=geometry.ini\n[physics]\nreference=FTFP_BERT\n[source]\npreset=mono_proton\n',encoding='utf-8')
  r=invoke(out,['--config','main.ini','--inspect-run'])
  receipt['results'].append({'name':name,'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()})
  (a.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
  if invalid:
   log=(r.stdout+r.stderr).decode('utf-8','replace');assert r.returncode==1 and 'dx1' in log and 'created_geometry_object_count=0' in log,log
  else:
   assert r.returncode==0,(r.stdout+r.stderr).decode('utf-8','replace')
   plan=json.loads(r.stdout);assert plan.get('version')==1
  print(name,'PASS',r.returncode,flush=True)
assert workspace_source_fingerprint()==a.fingerprint and hashlib.sha256(exe.read_bytes()).hexdigest()==exe_sha
receipt['status']='passed';receipt['source_unchanged']=True
(a.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Independent Boolean verification PASS',a.output)
