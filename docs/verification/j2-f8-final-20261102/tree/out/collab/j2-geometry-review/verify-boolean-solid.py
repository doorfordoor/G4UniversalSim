"""Independent Boolean construction audit; product read-only, no author test imports."""
from pathlib import Path
import argparse,json,sys,os,hashlib,subprocess,csv,math
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
from run_m0_tests import workspace_source_fingerprint
p=argparse.ArgumentParser();p.add_argument('version',choices=['1132','1143']);a=p.parse_args()
identity=next(x for x in json.loads((ROOT/'out/collab/j2-boolean-build-identities.json').read_text()) if x['version']==a.version)
exe=Path(identity['executable']);fingerprint=identity['source_fingerprint'];assert workspace_source_fingerprint()==fingerprint
assert hashlib.sha256(exe.read_bytes()).hexdigest()==identity['sha256']
OUT=ROOT/f'out/collab/j2-geometry-review/boolean-constructed-{a.version}-r1';OUT.mkdir(exist_ok=False)
sdk=Path('D:/ProgramFiles/Geant4') if a.version=='1132' else ROOT/'out/dependencies/geant4-11.4.3/geant4-11.4.3-win64'
data=Path('D:/ProgramFiles/Geant4/share/Geant4/data') if a.version=='1132' else ROOT/'out/i2-controlled/windows114-data/data'
env=dict(os.environ)
for key in list(env):
 if (key.startswith('G4') and key.endswith('DATA')) or key=='GEANT4_DATA_DIR':env.pop(key,None)
env.update(GEANT4_DATA_DIR=str(data),G4USIM_GEANT4_DATA=str(data));env['PATH']=str(sdk/'bin')+';D:/ProgramFiles/Qt/5.15.2/msvc2019_64/bin;'+env.get('PATH','')
receipt={'identity':identity,'source_before':fingerprint,'data_root':str(data),'results':[]}
def save(): (OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(directory,args):
 r=subprocess.run([str(exe),*args],cwd=directory,env=env,capture_output=True,timeout=90)
 (directory/'stdout.log').write_bytes(r.stdout);(directory/'stderr.log').write_bytes(r.stderr)
 return r
for name,args in [('capabilities',['--capabilities']),('discovery',['--check-geant4-data'])]:
 d=OUT/name;d.mkdir();r=run(d,args);assert r.returncode==0
 value=json.loads(r.stdout)
 if name=='capabilities':assert value['source_fingerprint']==fingerprint and str(value['geant4_version_number'])==a.version
 else:
  assert len(value['datasets'])==12
  assert all(x['found'] and Path(x['path']).is_dir() and Path(x['path']).name==x['folder'] for x in value['datasets'])
  expected_led='G4EMLOW8.6.1' if a.version=='1132' else 'G4EMLOW8.8'
  assert next(x for x in value['datasets'] if x['env']=='G4LEDATA')['folder']==expected_led
WORLD='[world]\nshape=box\nsize=200 mm,200 mm,200 mm\nmaterial=G4_Galactic\n'
TARGET='[volume.V]\nparent=world\nshape=box\nsize=80 mm,80 mm,80 mm\nmaterial=G4_Galactic\nsensitive=true\n'
PROPS={'trd':'dx1=8 mm\ndx2=12 mm\ndy1=12 mm\ndy2=12 mm\ndz=18 mm\n',
       'trap':'dz=18 mm\ntheta=0 deg\nphi=0 deg\ndy1=12 mm\ndx1=8 mm\ndx2=8 mm\nalpha1=0 deg\ndy2=12 mm\ndx3=12 mm\ndx4=12 mm\nalpha2=0 deg\n'}
def tool(shape):return '[volume.V.boolean.0]\noperation=subtraction\nshape='+shape+'\n'+PROPS[shape]
def execute(name,geometry,mode='inspect'):
 d=OUT/name;d.mkdir();(d/'geometry.ini').write_text(geometry,encoding='utf-8')
 ini=('[run]\nthreads=2\nseed=54321\n[materials]\nfile='+str(ROOT/'config/materials/material.ini')+'\n[geometry]\ntemplate=hierarchical\nconfig=geometry.ini\ncheck_overlaps=true\n[physics]\nreference=FTFP_BERT\n[output]\nformat=csv\ntrajectories=4\n[scoring]\nenabled=true\nhits=false\nedep=false\nevent_edep=false\ndose=false\nfluence=true\nauto_create_default_scorers=true\n[source]\nparticle=geantino\nenergy=1 MeV\nposition_type=point\nposition=-60 mm,0 mm,0 mm\ndirection=+x\n')
 (d/'main.ini').write_text(ini,encoding='utf-8');args=['--config','main.ini','--output','output']
 if mode=='inspect':args+=['--inspect-run']
 else:
  (d/'run.mac').write_text('/run/initialize\n/run/beamOn 4\n/AIHL/geometry/exportMesh mesh.json\n');args+=['--macro','run.mac']
 r=run(d,args);rec={'name':name,'exit_code':r.returncode,'mode':mode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()};receipt['results'].append(rec);save()
 return d,r,rec
for shape in ('trd','trap'):
 _,r,_=execute(shape+'-inspect',WORLD+TARGET+tool(shape));assert r.returncode==0,r.stderr.decode('utf-8','replace')
 _,r,_=execute(shape+'-missing-dx1',WORLD+TARGET+tool(shape).replace('dx1=8 mm\n',''));log=(r.stdout+r.stderr).decode('utf-8','replace');assert r.returncode==1 and 'dx1' in log and 'created_geometry_object_count=0' in log
# Strict protocol must reject each volume-only field, independent of old legacy warning behavior.
for key,value in [('material','G4_WATER'),('sensitive','true'),('bias','true'),('region','R'),('parent','world'),('placement','normal'),('copyNo','3'),('vis.color','red'),('cut.gamma','1 mm')]:
 _,r,_=execute('forbidden-'+key.replace('.','-'),'[global]\nversion=2\n'+WORLD+TARGET+tool('trd')+key+'='+value+'\n');log=(r.stdout+r.stderr).decode('utf-8','replace');assert r.returncode==1 and 'created_geometry_object_count=0' in log,(key,log)
for shape,key,value in [('trd','theta','0 deg'),('trap','z_planes','0 mm,1 mm')]:
 _,r,_=execute('unrelated-'+shape,WORLD+TARGET+tool(shape)+key+'='+value+'\n');log=(r.stdout+r.stderr).decode('utf-8','replace');assert r.returncode==1 and key in log and 'created_geometry_object_count=0' in log

def mesh_volume(v):
 vertices=v['vertices'];total=0.0
 for face in v['faces']:
  a=vertices[face[0]]
  for i in range(1,len(face)-1):
   b,c=vertices[face[i]],vertices[face[i+1]]
   cross=(b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0])
   total+=sum(a[j]*cross[j] for j in range(3))/6
 return abs(total)
for shape in ('base','trd','trap'):
 d,r,rec=execute(shape+'-constructed',WORLD+TARGET+('' if shape=='base' else tool(shape)),'run');assert r.returncode==0,(r.stdout+r.stderr).decode('utf-8','replace')
 facts={k.strip():v.strip() for line in (d/'output/run_summary.txt').read_text().splitlines() if '=' in line for k,v in [line.split('=',1)]}
 assert facts['status']=='completed' and int(facts['actual_completed_event_count'])==4
 mesh=json.loads((d/'mesh.json').read_text());v=next(x for x in mesh['volumes'] if x['name']=='V_PV')
 expected=80**3-(0 if shape=='base' else 17280)
 assert v['solid']==('G4Box' if shape=='base' else 'G4SubtractionSolid'),v['solid']
 volume=mesh_volume(v);assert abs(volume-expected)<1e-6,(shape,volume,expected)
 assert abs(v['cubic_volume_mm3']/expected-1)<.02,(shape,v['cubic_volume_mm3'],expected)
 csvrows=[row for file in (d/'output').glob('fluence_volume_summary_t*.csv') for row in csv.DictReader(file.open(encoding='utf-8',newline='')) if '/V_PV#0' in row['volume_path']]
 assert csvrows
 path=sum(float(row['raw_track_length_mm']) for row in csvrows);expected_path=4*(80 if shape=='base' else 60)
 assert abs(path-expected_path)<1e-6,(shape,path,expected_path)
 assert all(abs(float(row['volume_mm3'])/expected-1)<.02 for row in csvrows),(shape,csvrows)
 xs=[]
 for file in (d/'output').glob('trajectories_t*.json'):
  for event in json.loads(file.read_text())['events']:
   track=next(t for t in event['tracks'] if t['parent']==0);xs.append([point[0] for point in track['points']])
 assert len(xs)==4
 if shape!='base':assert all(any(abs(x+10)<1e-6 for x in points) and any(abs(x-10)<1e-6 for x in points) for points in xs),xs
 rec.update(solid_type=v['solid'],analytic_volume_mm3=expected,mesh_integrated_volume_mm3=volume,g4_cubic_volume_mm3=v['cubic_volume_mm3'],fluence_volumes_mm3=[float(row['volume_mm3']) for row in csvrows],total_sensitive_path_mm=path,expected_path_mm=expected_path,trajectory_x_mm=xs)
 save();print(shape,'constructed actual solid/mesh/transport PASS',flush=True)
assert workspace_source_fingerprint()==fingerprint and hashlib.sha256(exe.read_bytes()).hexdigest()==identity['sha256']
receipt.update(status='passed',source_after=workspace_source_fingerprint(),source_unchanged=True);save();print('Independent Boolean audit PASS',a.version,len(receipt['results']),OUT)
