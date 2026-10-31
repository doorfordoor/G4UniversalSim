from pathlib import Path
import hashlib,json
root=Path.cwd();v=root/'out/verification/k1-4167c44/visible-external';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
actions=[json.loads(x) for x in (v/'actions.jsonl').read_text(encoding='utf-8').splitlines()];assert len(actions)==1
p=Path(actions[0]['record_dir'])/'record.json';d=json.loads(p.read_bytes());project=v/'fixture-inputs/experiment.json';proj=json.loads(project.read_bytes())
assert proj['runInputMode']=='external' and d['status']=='passed' and 'package' not in d
assert d['result']['completed_events']==d['result']['planned_events']==3
launch=d['launch'];preview=(v/'05-completed-actual.txt').read_text(encoding='utf-8')
assert launch['working_directory'] in preview and launch['program'] in preview and all(x in preview for x in launch['arguments'])
assert launch['working_directory']!=proj['workspaceRoot']
assert all(x+'：未观测' in preview for x in ('字段与依赖','后端初始化','物理比较')) and '事件完成：通过' in preview
inputs=[]
for x in d['actual_inputs']:
 f=Path(x['path']);f=f if f.is_absolute() else Path(launch['working_directory'])/f
 assert sha(f)==x['sha256'] and f.stat().st_size==x['size_bytes'];inputs.append({'path':str(f),'sha256':sha(f)})
summaries=list(p.parent.rglob('run_summary.txt'));assert len(summaries)==1
fields=dict(x.split(' = ',1) for x in summaries[0].read_text().splitlines() if ' = ' in x)
assert fields['status']==fields['summary_write_status']=='completed' and fields['output_failure_status']=='none' and fields['run_0_completed_events']==fields['run_0_planned_events']=='3'
identity=json.loads((v/'identity.json').read_bytes());assert identity['head']=='4167c4421b13464dec54213ea7652ee321868c4e' and identity['git_status']=='' and not identity['module_overrides']
assert all(sha(root/f)==h for f,h in identity['gui_files'].items());assert json.loads((v/'launcher.json').read_bytes())['actual_process_exit']==0
receipt={'schema':'k1_sixth_external_native_supplement_v1','head':identity['head'],'operator':'parent assistant via actual Sky UI','input_mode_evidence':'UI selection plus saved project external; raw record has no package','input_mode':'external','record_id':d['record_id'],'record_path':str(p),'record_sha256':sha(p),'generated_project_snapshot_exists':False,'saved_project_path':str(project),'saved_project_sha256':sha(project),'package_key_present':False,'result':d['result'],'actual_inputs':inputs,'summary_path':str(summaries[0]),'summary_sha256':sha(summaries[0]),'launch':launch,'preview_matches_record_launch':True,'valid_completion_text':'05-completed-actual.txt','preview_text_sha256':sha(v/'05-completed-actual.txt'),'images':{f.name:sha(f) for f in v.glob('*.jpg')},'valid_distinct_images':['01-explicit-external-mode.jpg','05-completed-actual.jpg'],'mislabelled_duplicate_images':['02-external-paths-valid.jpg','03-external-run-pending.jpg','04-external-no-package-complete.jpg'],'duplicate_cause':'QA save closure retained earlier state; originals preserved. Actual final state still in node runtime was saved directly after real observation, with no new screenshot or rerun.','identity_sha256':sha(v/'identity.json'),'launcher_sha256':sha(v/'launcher.json'),'actual_process_exit':0,'other_three_levels':'not_observed','scope':'actual external/no-package completion and preview, not physics comparison','postcheck_attempts':['FileNotFoundError on incorrectly assumed generated project_snapshot','StopIteration on incorrectly labelled duplicate text; no receipt written in either attempt'],'independent_followup':'pending','phase_complete':False}
(v/'supplement-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'record':d['record_id'],'external':True,'package':False,'events':3,'inputs':len(inputs),'exit':0,'receipt_exists':(v/'supplement-receipt.json').is_file()}))
