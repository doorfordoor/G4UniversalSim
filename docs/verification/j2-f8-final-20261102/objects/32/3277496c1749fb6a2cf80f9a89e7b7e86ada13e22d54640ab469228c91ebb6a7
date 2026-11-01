"""Frozen candidate formal Windows113 acceptance orchestration; no product/test writes."""
from pathlib import Path
import subprocess,json,sys,os,hashlib,time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
from run_m0_tests import workspace_source_fingerprint
from PySide6.QtCore import QLibraryInfo
BASE=ROOT/'out/verification/j2-f8-56b689f'
HEAD='56b689fb9ac920cbb1203b2b94dae2483d25f622'
FP='9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a'
identity=next(x for x in json.loads((BASE/'identity/build-identities.json').read_text()) if x['version']=='1132')
exe=Path(identity['executable']);merge=exe.with_name('mergeHistograms.exe')
env=dict(os.environ)
for k in list(env):
 if (k.startswith('G4') and k.endswith('DATA')) or k=='GEANT4_DATA_DIR':env.pop(k,None)
data=Path('D:/ProgramFiles/Geant4/share/Geant4/data')
env.update(GEANT4_DATA_DIR=str(data),G4USIM_GEANT4_DATA=str(data),G4USIM_EXE=str(exe),G4USIM_MERGE_EXE=str(merge),PYTHONDONTWRITEBYTECODE='1',QT_QPA_PLATFORM='offscreen',QT_PLUGIN_PATH=QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath),PYTHONUNBUFFERED='1')
env['PATH']='D:/ProgramFiles/Geant4/bin;D:/ProgramFiles/Qt/5.15.2/msvc2019_64/bin;'+env.get('PATH','')
# Only child-process Git behavior changes; repository config is untouched.
env['GIT_CONFIG_COUNT']='1';env['GIT_CONFIG_KEY_0']='core.longpaths';env['GIT_CONFIG_VALUE_0']='true'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==HEAD
assert not subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain=v1','-uno'],cwd=ROOT)
assert workspace_source_fingerprint()==FP and sha(exe)==identity['executable_sha256']
baselines=json.loads((ROOT/'out/collab/j2-f8-baselines.json').read_text())['baselines']
receipt=dict(head=HEAD,source_fingerprint=FP,executable=str(exe),executable_sha256=sha(exe),merge_executable=str(merge),merge_sha256=sha(merge),data_root=str(data),path_prefix=env['PATH'].split(';')[:2],qt_plugin_path=env['QT_PLUGIN_PATH'],started=time.strftime('%Y-%m-%dT%H:%M:%S'),profiles=[])
def save():
 (BASE/'windows113-execution-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (BASE/'windows113-checkpoint.md').write_text('# Windows113正式验收\n\nHEAD '+HEAD+'；产品/测试冻结。运行身份、逐profile状态见windows113-execution-receipt.json；完整输出见windows113-{backend,integration}.runner.log与对应report-root。\n\n当前阶段：'+receipt.get('stage','preflight')+'。保留初败，不自动改判据或重跑。\n',encoding='utf-8')
for name,args in [('capabilities',['--capabilities']),('data-discovery',['--check-geant4-data'])]:
 r=subprocess.run([str(exe),*args],cwd=ROOT,env=env,capture_output=True,timeout=30)
 (BASE/f'windows113-{name}.stdout.json').write_bytes(r.stdout);(BASE/f'windows113-{name}.stderr.log').write_bytes(r.stderr);assert r.returncode==0
 x=json.loads(r.stdout)
 if name=='capabilities':assert x['build_git_commit']==HEAD and x['build_git_source_state']=='clean' and x['source_fingerprint']==FP and x['geant4_version_number']==1132
 else:
  assert len(x['datasets'])==12 and all(y['found'] and Path(y['path']).is_dir() and Path(y['path']).resolve().is_relative_to(data.resolve()) and Path(y['path']).name==y['folder'] for y in x['datasets'])
  assert next(y for y in x['datasets'] if y['env']=='G4LEDATA')['folder']=='G4EMLOW8.6.1'
for profile in ('backend','integration'):
 baseline=next(x for x in baselines if x['id']=='windows113-'+profile);bp=ROOT/baseline['original_report'];assert sha(bp)==baseline['report_sha256']
 reportroot=BASE/('windows113-'+profile);assert not reportroot.exists() or not list(reportroot.glob('*/report.json')),'do not overwrite/repeat formal profile'
 cmd=[sys.executable,'-B',str(ROOT/'scripts/run_m0_tests.py'),'--profile',profile,'--executable',str(exe),'--merge-executable',str(merge),'--report-root',str(reportroot),'--require-tracked-sources','--fail-on-skip']
 rec=dict(profile=profile,command=cmd,baseline=baseline,started=time.strftime('%Y-%m-%dT%H:%M:%S'));receipt['profiles'].append(rec);receipt['stage']='running '+profile;save();print('START',profile,flush=True)
 with (BASE/f'windows113-{profile}.runner.log').open('wb') as log:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
 rec['runner_exit']=r.returncode;reports=sorted(reportroot.glob('*/report.json'));assert len(reports)==1;report=reports[0];rec['report']=str(report)
 x=json.loads(report.read_text());rec.update(cases=len(x['results']),assertions=x.get('assertions_executed_total'),statuses={s:sum(y['status']==s for y in x['results']) for s in ('pass','fail','skip')},failures=[y for y in x['results'] if y['status']!='pass'])
 receipt['stage']='gating '+profile;save()
 gate=[sys.executable,'-B',str(ROOT/'scripts/check_report_evidence.py'),'--report',str(report),'--baseline',str(bp)]
 gr=subprocess.run(gate,cwd=ROOT,env=env,capture_output=True);(BASE/f'windows113-{profile}.strict-baseline.log').write_bytes(gr.stdout+gr.stderr);rec['strict_baseline_exit']=gr.returncode;rec['gate_command']=gate;save();print('DONE',profile,'runner',r.returncode,'gate',gr.returncode,'cases',rec['cases'],'assertions',rec['assertions'],'statuses',rec['statuses'],flush=True)
receipt['source_after']=workspace_source_fingerprint();receipt['head_after']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();receipt['exe_sha256_after']=sha(exe);receipt['merge_sha256_after']=sha(merge)
receipt['tracked_status_after']=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain=v1','-uno'],cwd=ROOT,text=True)
receipt['identity_unchanged']=receipt['source_after']==FP and receipt['head_after']==HEAD and receipt['exe_sha256_after']==receipt['executable_sha256'] and receipt['merge_sha256_after']==receipt['merge_sha256'] and not receipt['tracked_status_after']
receipt['stage']='complete';receipt['status']='passed' if receipt['identity_unchanged'] and all(x['runner_exit']==0 and x['strict_baseline_exit']==0 for x in receipt['profiles']) else 'failed';save();print('FINAL',receipt['status'],flush=True)
sys.exit(0 if receipt['status']=='passed' else 1)
