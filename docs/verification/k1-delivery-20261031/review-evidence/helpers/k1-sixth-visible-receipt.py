"""Bind already observed native actions to their original run evidence."""
from pathlib import Path
import hashlib,json
root=Path.cwd();v=root/'out/verification/k1-4167c44/visible'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ident=json.loads((v/'identity.json').read_bytes())
assert ident['head']=='4167c4421b13464dec54213ea7652ee321868c4e'
assert ident['git_status']=='' and ident['qt_platform']=='windows' and not ident['module_overrides']
assert all(sha(root/p)==h for p,h in ident['gui_files'].items())
assert sha(Path(ident['backend']))==ident['backend_sha256']
launcher=json.loads((v/'launcher.json').read_bytes());assert launcher['actual_process_exit']==0
actions=[json.loads(x) for x in (v/'actions.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(actions)==9 and all(x['status']=='passed' for x in actions)
records=[]
for a in actions:
 p=Path(a['record_dir'])/'record.json';d=json.loads(p.read_bytes())
 assert d['record_id']==a['record_id'] and d['status']==a['status']
 records.append({'record_id':d['record_id'],'action':d['action'],'level':d.get('level'),'status':d['status'],'record':str(p.relative_to(root)),'sha256':sha(p)})
runs=[]
for rid,txt in [('957da62967d84033b90ddc942f43c991','05-generated-run-complete.txt'),('4580680808784da59c690e8491568acb','08-external-run-complete.txt')]:
 row=next(x for x in records if x['record_id']==rid);p=root/row['record'];d=json.loads(p.read_bytes());launch=d['launch']
 tree=(v/txt).read_text(encoding='utf-8');preview=next(x for x in tree.splitlines() if '65 编辑 Value:' in x)
 assert launch['program'] in preview and launch['working_directory'] in preview
 assert all(x in preview for x in launch['arguments'])
 assert launch['launch_working_directory']==launch['working_directory'] and launch['launch_route']=='direct'
 assert d['result']['state']=='success' and d['result']['planned_events']==d['result']['completed_events']==3
 inputs=[]
 for x in d['actual_inputs']:
  f=Path(x['path']);f=f if f.is_absolute() else Path(launch['working_directory'])/f
  assert sha(f)==x['sha256'] and f.stat().st_size==x['size_bytes']
  inputs.append({'path':str(f.relative_to(root)),'sha256':sha(f),'role':x['role']})
 summaries=[]
 for s in p.parent.rglob('run_summary.txt'):
  fields=dict(line.split(' = ',1) for line in s.read_text().splitlines() if ' = ' in line)
  assert fields['status']==fields['summary_write_status']=='completed'
  assert fields['output_failure_status']=='none' and fields['run_count']=='1'
  assert fields['run_0_planned_events']==fields['run_0_completed_events']=='3'
  summaries.append({'path':str(s.relative_to(root)),'sha256':sha(s),'fields':{k:fields[k] for k in ('status','summary_write_status','output_failure_status','run_count','run_0_planned_events','run_0_completed_events')}})
 assert len(summaries)==1
 runs.append({'record_id':rid,'launch':launch,'actual_inputs':inputs,'result':d['result'],'summary':summaries[0],'preview_text':txt,'preview_sha256':sha(v/txt),'preview_matches_actual_launch':True})
comparison=json.loads((root/next(x['record'] for x in records if x['action']=='evaluate')).read_bytes())['comparisons']
assert len(comparison)==1 and comparison[0]['passed'] and comparison[0]['sample_count']==3
assert comparison[0]['observed']==comparison[0]['standard_error']==0
stale=(v/'06-import-history-stale.txt').read_text(encoding='utf-8')
assert all(x+'：陈旧' in stale for x in ('字段与依赖','后端初始化','事件完成','物理比较'))
images={p.name:sha(p) for p in sorted(v.glob('*.jpg'))};assert len(images)==11
receipt={'schema':'k1_sixth_native_receipt_v1','head':ident['head'],'operator':'parent assistant via @oai/sky, not user','native_scope':'generated and external completion previews; pending; relocated import stale; initialize/run/explicit comparison/reexport/save/normal close','images':images,'records':records,'runs':runs,'comparison':comparison,'actual_process_exit':0,'launcher_sha256':sha(v/'launcher.json'),'source_identity_sha256':sha(v/'identity.json'),'backend_sha256':ident['backend_sha256'],'import_all_four_stale_observed':True,'file_dialog_variant':ident['file_dialog_variant'],'unverified':['default Windows system chooser','new cancellation/force sequence on sixth; fifth evidence keeps fifth identity','general radiation physics or Q2','resource-boundary independent review remains incomplete'],'phase_complete':False}
(v/'targeted-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'actions':len(actions),'runs':len(runs),'images':len(images),'exit':0,'receipt':str(v/'targeted-receipt.json')}))
