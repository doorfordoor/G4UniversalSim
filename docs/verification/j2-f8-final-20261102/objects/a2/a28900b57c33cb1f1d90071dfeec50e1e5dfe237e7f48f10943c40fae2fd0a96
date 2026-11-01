"""Append only the explicitly terminal third static group; never inspect pending peers."""
import hashlib,importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
r=Path.cwd();a=r/'out/collab/j2-f8-archive-plan';v=a/'versions/v3-18c5858';s=a/'staging-v3-18c5858';d=r/'out/verification/j2-f8-18c5858/windows-static';o=v/'third-static-terminal';assert not o.exists();o.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
j=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def put(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
l=j(d/'launch.json');assert l['status']=='passed' and l['runner_exit_code']==l['gate_exit_code']==0 and l['identity_errors']==[];p=d/'20261102-040156-d08e6301/report.json';rr=j(p);assert len(rr['results'])==46 and rr['assertions_executed_total']==4586 and not rr['git_dirty'];assert all(c['status']=='pass' for c in rr['results']);assert sha(p)==l['report_sha256'];assert l['ending']['head']=='18c5858fd6e80a5cb6096beacebfef69c479ad49'
ck=s/'tree/scripts/check_report_evidence.py';sp=importlib.util.spec_from_file_location('_third_static_evidence_checker',ck);ckm=importlib.util.module_from_spec(sp);sp.loader.exec_module(ckm)
entries={}
def add(q,role,expected=None):
 h=sha(q);assert expected is None or h==expected;rel=q.relative_to(r).as_posix();obj=s/'objects'/h[:2]/h;logical=s/'tree'/rel
 if not obj.exists():obj.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(q,obj)
 assert sha(obj)==h
 if not logical.exists():logical.parent.mkdir(parents=True,exist_ok=True);os.link(obj,logical)
 assert sha(logical)==h;entries[rel]={'source':rel,'logical_path':'tree/'+rel,'object':obj.relative_to(s).as_posix(),'sha256':h,'bytes':q.stat().st_size,'role':role,'candidate':'18c5858','original_state_unmodified':True};return logical
staged=add(p,'third_static_terminal_report',l['report_sha256'])
for c in rr['results']:q=ckm.resolve_log(c,p);assert q;add(q,'third_static_original_case_log',c['log_sha256'])
for q in d.iterdir():
 if q.is_file():add(q,'third_static_terminal_launcher_gate_receipt')
base=Path(l['gate_command'][l['gate_command'].index('--baseline')+1]);sb=add(base,'matching_historical_static_baseline');br=j(base)
for c in br['results']:q=ckm.resolve_log(c,base);assert q;add(q,'matching_historical_static_raw_log',c['log_sha256'])
for rp in [staged,sb]:
 for c in j(rp)['results']:
  q=ckm.resolve_log(c,rp);assert q and q.resolve().is_relative_to(s.resolve());assert sha(q)==c['log_sha256']
runs=[]
for name,rp,bp in [('historical-baseline',sb,None),('third-static-original',staged,sb)]:
 cmd=[sys.executable,'-B',str(ck),'--report',str(rp)]
 if bp:cmd+=['--baseline',str(bp)]
 z=subprocess.run(cmd,capture_output=True);log=o/(name+'.log');log.write_bytes(z.stdout+z.stderr);assert z.returncode==0;runs.append({'kind':name,'exit':z.returncode,'log_sha256':sha(log),'command':cmd})
put(o/'manifest.json',{'group':'third-candidate-18c5858-static-only','status':'terminal_passed','cases':46,'assertions':4586,'launcher_exit':0,'gate_exit':0,'identity_errors':[],'report_sha256':sha(p),'launch_sha256':sha(d/'launch.json'),'entries':list(entries.values()),'kept_separate_from_2901f42_complete_300':True,'other_third_profile_directories_read':False,'strict_relocation_runs':runs,'all_logs_resolve_inside_staging':True,'product_tests_or_formal_profiles_started':False})
for q in o.iterdir():
 if q.is_file():dest=s/'plan/third-static-terminal'/q.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(q,dest)
print(json.dumps({'third_static_cases':46,'assertions':4586,'staged_logical_entries':len(entries),'strict_replay_exits':[x['exit'] for x in runs]}))
