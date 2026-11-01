from pathlib import Path
import sys,json,hashlib,tempfile,copy
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'resources-round';WORK=OUT/('io-runtime-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'));WORK.mkdir();tempfile.tempdir=str(WORK);sys.path.insert(0,str(ROOT/'gui'))
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.wizard import blank_result,apply_to_project
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot,snapshot_fingerprint
from g4usim_gui.core.experiment_bundle import export_bundle
from g4usim_gui.core.run_editor_model import GPSDefinition
from g4usim_gui.models.package_model import PathSettings
orig=WORK/'original';orig.mkdir();raw=b'e_low_MeV,e_high_MeV,weight\n1,2,1\n'
for x in ('a.csv','b.csv'):(orig/x).write_bytes(raw)
p=G4USimProject(executable=sys.executable,workspaceRoot=str(orig),runsRoot=str(WORK/'runs'));p.pathSettings=PathSettings(executable=p.executable,workspace_root=p.workspaceRoot,runs_root=p.runsRoot);apply_to_project(p,blank_result());p.sourceEditor.gps_sources=[GPSDefinition(name=n,energy_type='histogram',spectrum_file=n+'.csv') for n in ('a','b')]
snap=WorkspaceSnapshot(p);before=snapshot_fingerprint(snap);original_open=Path.open;hit=[]
def fail_open(self,mode='r',*args,**kwargs):
 if mode=='xb' and self.name=='r0001.csv' and self.parent.name=='resources':
  hit.append(str(self));raise OSError('controlled second-resource write failure')
 return original_open(self,mode,*args,**kwargs)
try:
 with patch.object(Path,'open',new=fail_open):export_bundle(snap,WORK/'bundle')
except OSError as e:error=str(e)
else:raise AssertionError('write failure not propagated')
assert len(hit)==1 and not (WORK/'bundle').exists() and not list(WORK.glob('.bundle.k1-*'))
assert snapshot_fingerprint(snap)==before and all((orig/x).read_bytes()==raw for x in ('a.csv','b.csv'))
result={'injected_write_failure':error,'injection_hits':len(hit),'target_not_published':True,'staging_removed':True,'original_snapshot_and_resource_bytes_unchanged':True,'scope':'controlled IO exception, not physical disk failure'}
existing=WORK/'existing';existing.mkdir();(existing/'sentinel.txt').write_bytes(b'KEEP')
try:export_bundle(snap,existing)
except FileExistsError:pass
else:raise AssertionError('existing bundle destination overwritten')
assert (existing/'sentinel.txt').read_bytes()==b'KEEP' and list(existing.iterdir())==[existing/'sentinel.txt']
result['existing_destination_preserved']=True
(OUT/'io-failure-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
