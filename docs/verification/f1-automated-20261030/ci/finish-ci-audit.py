"""Finalize a fully collected third-freeze corpus; strict CI and integrity are separate."""
from pathlib import Path,PurePosixPath,PureWindowsPath
import sys,hashlib,json,zipfile,stat,re,importlib.util
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];BASE=Path(__file__).resolve().parent
HEAD='f176d0ed4cea60b7ca5a80ed81017c9404ec1257';RUNS=(41028779177,41028779326)
PROFILES={'linux-evidence-11.3.2':{'static','gui','backend','integration'},'linux-evidence-11.4.3':{'static','gui','backend','integration'},'m0-report-ubuntu-latest':{'static','gui'},'m0-report-windows-latest':{'static','gui'}}
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,data):
 raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
 if path.exists():assert path.read_bytes()==raw,'existing evidence differs';return
 with path.open('xb') as f:f.write(raw)
def main():
 frozen=load(BASE/'frozen-case-manifest.json');assert frozen['head_sha']==HEAD
 frozen_names=[name for profile in frozen['profiles'].values() for name in profile];assert len(frozen_names)==len(set(frozen_names))==143
 ci=load(BASE/'ci-evidence.json');assert ci['head_sha']==HEAD and ci['complete'] is True
 spec=importlib.util.spec_from_file_location('third_ci_gate',ROOT/'scripts/check_report_evidence.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
 artifacts=[];jobs=[];raw_runs=[]
 for rid in RUNS:
  run=load(BASE/f'{rid}-run.json');assert run['id']==rid and run['head_sha']==HEAD and run['status']=='completed';raw_runs.append({'id':rid,'status':run['status'],'conclusion':run['conclusion'],'head_sha':run['head_sha']})
  for job in load(BASE/f'{rid}-jobs.json')['jobs']:
   assert job['run_id']==rid and job['status']=='completed'
   path=BASE/f"job-{job['id']}.log";assert path.is_file()
   jobs.append({'id':job['id'],'run_id':rid,'name':job['name'],'conclusion':job['conclusion'],'path':path.name,'bytes':path.stat().st_size,'sha256':sha(path)})
  for item in load(BASE/f'{rid}-artifacts.json')['artifacts']:
   assert item['name'] in PROFILES and item['workflow_run']['id']==rid and item['workflow_run']['head_sha']==HEAD
   archive=BASE/(item['name']+'.zip');actual='sha256:'+sha(archive);assert actual==item['digest']
   dest=BASE/item['name'];seen=set();members=0
   with zipfile.ZipFile(archive) as source:
    for entry in source.infolist():
     relative=PurePosixPath(entry.filename);assert not relative.is_absolute() and '..' not in relative.parts and not PureWindowsPath(entry.filename).drive and '\\' not in entry.filename
     assert not stat.S_ISLNK(entry.external_attr>>16)
     path=dest.joinpath(*relative.parts);resolved=path.resolve();assert resolved.is_relative_to(dest.resolve()) and resolved not in seen;seen.add(resolved)
     if entry.is_dir():continue
     raw=source.read(entry);assert path.is_file() and path.read_bytes()==raw;members+=1
   artifacts.append({'id':item['id'],'name':item['name'],'run_id':rid,'official_digest':item['digest'],'sha256':actual,'member_files_verified':members})
 assert len(artifacts)==len({x['name'] for x in artifacts})==4 and len(jobs)==4
 reports=[];logs=[];pairs=set();failures=[]
 for path in sorted(BASE.rglob('report.json')):
  data=load(path);artifact=path.relative_to(BASE).parts[0];profile=data['profile']
  assert artifact in PROFILES and profile in PROFILES[artifact] and (artifact,profile) not in pairs;pairs.add((artifact,profile))
  assert data['git_head']==HEAD and data['tracked_source_gate']=='pass'
  for key in ('source_fingerprint','tests_content_fingerprint'):assert data[key]==frozen[key]
  assert {r['name'] for r in data['results']}==set(frozen['profiles'][profile])
  bad=[r for r in data['results'] if r['status']!='pass']
  summary=[r for r in ci['reports'] if r['path'].replace('\\','/')==path.relative_to(BASE).as_posix()];assert len(summary)==1
  gate.validate_report(data,report_path=path,allow_incomplete=bool(bad))
  assert (summary[0]['strict_gate_exit_code']==0)==(not bad)
  for row in data['results']:
   name=PurePosixPath(row['log'].replace('\\','/')).name;log=next((candidate for candidate in (path.parent/name,path.parent/'logs'/name) if candidate.is_file()),None)
   assert log is not None and log.resolve().is_relative_to(BASE.resolve()) and sha(log)==row['log_sha256']
   markers=re.findall(rb'^G4USIM_ASSERTS=(\d+)\r?$',log.read_bytes(),re.M);assert markers and int(markers[-1])==row['assertions_executed']
   assert row['assert_probe']==data['assert_probe']
   if row['status']=='pass':assert row['exit_code']==0 and row['assertions_executed']>0
   else:assert row['status']=='fail' and row['exit_code']!=0
   item={'artifact':artifact,'profile':profile,'case':row['name'],'status':row['status'],'exit_code':row['exit_code'],'assertions':row['assertions_executed'],'path':log.relative_to(BASE).as_posix(),'sha256':sha(log),'bytes':log.stat().st_size};logs.append(item)
   if row['status']!='pass':failures.append(item)
  reports.append({'artifact':artifact,'profile':profile,'path':path.relative_to(BASE).as_posix(),'sha256':sha(path),'cases':len(data['results']),'assertions':data['assertions_executed_total'],'failures':[x['name'] for x in bad],'strict_gate_exit_code':summary[0]['strict_gate_exit_code'],'triage_integrity_only':bool(bad),'git_dirty':data['git_dirty']})
 assert pairs=={(a,p) for a,ps in PROFILES.items() for p in ps} and len(reports)==12
 expected_records=sum(len(frozen['profiles'][profile]) for _,profile in pairs);assert len(logs)==expected_records
 passed=not failures and all(x['conclusion']=='success' for x in raw_runs+jobs)
 assert (ci['status']=='passed')==passed
 audit={'head_sha':HEAD,'raw_runs':raw_runs,'artifacts':artifacts,'job_logs':jobs,'reports':reports,'case_logs':logs,'all_case_logs_sha_marker_matched':True,'complete_artifact_profile_pairs':True,'source_fingerprint':frozen['source_fingerprint'],'tests_content_fingerprint':frozen['tests_content_fingerprint']}
 save(BASE/'evidence-integrity-audit.json',audit)
 summary={'head_sha':HEAD,'status':'passed' if passed else 'failed','ci_acceptance_passed':passed,'stage_acceptance':'pending_other_required_evidence','evidence_collection_complete':True,'reports_total':len(reports),'strict_pass_reports':sum(r['strict_gate_exit_code']==0 for r in reports),'case_executions':len(logs),'failed_case_executions':len(failures),'failures':failures,'reports':reports,'artifacts':artifacts,'job_logs':jobs,'boundary':'CI acceptance is distinct from Windows all-profile, visible UI and physical validation.'}
 save(BASE/('round-summary.json' if passed else 'failed-round-summary.json'),summary)
 text='# F1第三冻结CI：'+('通过' if passed else '未通过')+'\n\nHEAD `'+HEAD+'`。Linux run41028779177；M0 run41028779326。四原ZIP官方digest及解包文件字节、四完整decoded joblogs、12报告与全部'+str(len(logs))+'case日志SHA/断言marker已核对，冻结143case按每个profile精确匹配，head/source/tests一致。\n\n'
 text+='严格门禁通过 '+str(summary['strict_pass_reports'])+'/12。失败case '+str(len(failures))+'。未重跑CI、修改源码、启动主exe或操作UI；原证据只独占保存或复用相同字节。\n\n'
 text+='|Artifact|Profile|Cases|Strict exit|非pass|\n|---|---|---:|---:|---|\n'
 for row in reports:text+='|'+row['artifact']+'|['+row['profile']+']('+row['path']+')|'+str(row['cases'])+'|'+str(row['strict_gate_exit_code'])+'|'+(','.join(row['failures']) or '无')+'|\n'
 text+='\n[CI机器收据](ci-evidence.json)、[逐日志与ZIP成员核对](evidence-integrity-audit.json)、[轮次汇总]('+('round-summary.json' if passed else 'failed-round-summary.json')+')。verify helper只用verify模式，未使用collect凭据fallback。通用git_dirty按原报告保留，不擅自推断其具体来源。CI通过不自动关闭Windows全量、实窗观察或科研物理验证。\n'
 if (BASE/'README.md').exists():assert (BASE/'README.md').read_bytes()==text.encode('utf-8')
 else:
  with (BASE/'README.md').open('xb') as f:f.write(text.encode('utf-8'))
 print(json.dumps({k:summary[k] for k in ('status','evidence_collection_complete','reports_total','strict_pass_reports','case_executions','failed_case_executions')}))
if __name__=='__main__':main()
