from pathlib import Path
from datetime import datetime,timezone
import sys,os,json,tempfile,copy,hashlib,shutil,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'r01-recheck';OUT.mkdir(exist_ok=True);WORK=OUT/('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'));WORK.mkdir();tempfile.tempdir=str(WORK);sys.path.insert(0,str(ROOT/'gui'))
from g4usim_gui.core.wizard import apply_to_project,blank_result
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot,snapshot_fingerprint
from g4usim_gui.core.experiment_bundle import export_bundle,load_bundle,collect_bundle_resources
from g4usim_gui.core.run_editor_resources import materialize_run_resources
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.editors.source_physics_scoring_model import validate_source_model
FILES=['gui/g4usim_gui/core/run_editor_resources.py','gui/g4usim_gui/core/experiment_bundle.py','gui/g4usim_gui/writers/package_writer.py','scripts/test_j2_resource_bundle.py']
def hashes():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}
start=hashes();orig=WORK/'original';orig.mkdir();a=orig/'a.csv';b=orig/'b.csv';a.write_bytes(b'phase A\n');b.write_bytes(b'phase B\n')
p=G4USimProject(executable=sys.executable,workspaceRoot=str(orig),runsRoot=str(WORK/'runs'));p.pathSettings=PathSettings(executable=p.executable,workspace_root=p.workspaceRoot,runs_root=p.runsRoot);apply_to_project(p,blank_result());p.sourceEditor.phase_space_file=' b.csv ,a.csv,b.csv '
before=copy.deepcopy(p);src,phy=materialize_run_resources(p.sourceEditor,p.physicsEditor,workspace=orig,destination=WORK/'copies');refs=src.phase_space_file.split(',');assert [Path(x).read_bytes() for x in refs]==[b'phase B\n',b'phase A\n',b'phase B\n'];assert refs[0]==refs[2] and len(list((WORK/'copies').iterdir()))==2 and p==before
snap=WorkspaceSnapshot(p);finger=snapshot_fingerprint(snap);bundle=WORK/'bundle';export_bundle(snap,bundle);a.unlink();b.unlink();moved=WORK/'moved 中文';assert bundle.resolve().is_relative_to(OUT.resolve()) and moved.resolve().is_relative_to(OUT.resolve());shutil.move(str(bundle),str(moved));loaded=load_bundle(moved,executable=sys.executable);refs=loaded.project.sourceEditor.phase_space_file.split(',');assert [Path(x).read_bytes() for x in refs]==[b'phase B\n',b'phase A\n',b'phase B\n'] and refs[0]==refs[2];assert all(Path(x).is_relative_to(moved) for x in refs)
results={'duplicate_order_and_dedup':True,'moved_after_originals_deleted':True,'original_snapshot_unchanged':snapshot_fingerprint(snap)==finger,'empty_parts':[]}
a.write_bytes(b'phase A\n')
for value in ('a.csv,',',a.csv','a.csv,,a.csv'):
 q=copy.deepcopy(p);q.sourceEditor.phase_space_file=value;validate_source_model(q.sourceEditor);assert q.sourceEditor.errors
 target=WORK/('invalid-'+str(len(results['empty_parts'])))
 try:export_bundle(WorkspaceSnapshot(q),target)
 except (OSError,ValueError) as e:error=type(e).__name__
 else:raise AssertionError('empty list part exported')
 assert not target.exists();results['empty_parts'].append({'value':value,'source_rejected':True,'export_rejected':error})
q=copy.deepcopy(p);q.sourceEditor.phase_space_file='a.csv,missing.csv';q_snap=WorkspaceSnapshot(q);before_q=snapshot_fingerprint(q_snap)
try:export_bundle(q_snap,WORK/'missing-second')
except (OSError,ValueError) as e:error=type(e).__name__+': '+str(e)
else:raise AssertionError('missing second exported')
assert not (WORK/'missing-second').exists() and not list(WORK.glob('.missing-second.k1-*')) and snapshot_fingerprint(q_snap)==before_q;results['missing_second']={'rejected':error,'no_publish_or_staging':True,'snapshot_unchanged':True}
env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'gui');env['QT_QPA_PLATFORM']='offscreen';results['cli']=[]
for action in ('generate','validate'):
 proc=subprocess.run([sys.executable,str(moved/'replay.py'),'--executable',sys.executable,'--runs-root',str(WORK/'cli-runs'),'--records',str(WORK/'cli-records'),'--timeout','30',action],cwd=orig,env=env,capture_output=True,timeout=45)
 (OUT/f'{action}.stdout.json').write_bytes(proc.stdout);(OUT/f'{action}.stderr.log').write_bytes(proc.stderr);d=json.loads(proc.stdout);assert proc.returncode==0 and d['ok'];results['cli'].append({'command':action,'exit_code':proc.returncode,'status':d['record']['status']})
results['source_sha256_before']=start;results['source_sha256_after']=hashes();results['source_unchanged']=start==hashes();results['scope']='resource portability/fields/generation only; no Geant4 physics run';(OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in results.items() if not k.startswith('source_sha')},ensure_ascii=False,indent=2))
