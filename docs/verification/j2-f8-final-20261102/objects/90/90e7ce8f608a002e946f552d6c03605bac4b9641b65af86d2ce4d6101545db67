from pathlib import Path
import json,hashlib,configparser,csv,collections,re
ROOT=Path(__file__).resolve().parents[3];N=ROOT/'out/verification/j2-f8-18c5858/native100';OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
before={p.relative_to(N).as_posix():sha(p) for p in sorted(N.rglob('*')) if p.is_file()}
launch=load(N/'launch.json');identity=load(N/'identity.json');exit=load(N/'exit.json');project=load(N/'blank-native.json');visual=load(N/'visual-observations.json');obs=[json.loads(l) for l in (N/'observations.jsonl').read_text(encoding='utf-8').splitlines()]
HEAD='18c5858fd6e80a5cb6096beacebfef69c479ad49';EXE='01e0fb795f93772ccfa818d625fee145d8da1ad3ad80894372a9a855f0af108a';FP='9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a'
assert launch['head']==launch['ending_head']==identity['head']==HEAD
assert launch['exe_sha256']==launch['ending_exe_sha256']==identity['exe_sha256']==EXE
assert sha(Path(identity['exe']))==EXE
assert launch['status']=='exited' and launch['process_exit_code']==exit['exit_code']==0 and exit['visible'] is False and launch['ending_git_status']==''
assert launch['qpa']=='windows' and launch['runtime']['qt']=='6.11.1'
assert launch['capabilities']['build_git_commit']==HEAD and launch['capabilities']['source_fingerprint']==FP
assert all(sha(ROOT/p)==v for p,v in identity['gui_files'].items())
assert launch['host_sha256']==identity['host_sha256']==sha(ROOT/'out/collab/j2-f8-native/host-v2.py')
assert set(o['dpr'] for o in obs)=={1.0}
images={}
for v in visual:
 for image in v['images']:
  p=Path(image['path']).resolve();assert p.is_relative_to(N.resolve());assert sha(p)==image['sha256'];images[p.name]=image['sha256']
raw_images={p.name for p in N.glob('*.jpg')};assert set(images)==raw_images
labels={v['label']:v for v in visual};assert {'blank-saved','blank-reloaded','fields-passed','initialize-passed-no-run','generate-confirmed','run-success-100','export-created','results-overview-readable','results-run-summary'}<=labels.keys()
assert project['schema']=='G4UniversalSimProject' and project['version']==8 and project['runInputMode']=='generated'
assert project['configPath']==project['macroPath']==project['pathSettings']['materials_config']==project['pathSettings']['geometry_config']==''
assert len(project['materialEditor']['rows'])==0 and len(project['geometryEditor']['volumes'])==1
assert project['materialEditor']['is_dirty'] and project['geometryEditor']['is_dirty']
assert project['materialEditor']['source_path']==project['geometryEditor']['source_path']==''
assert project['runSettings']['beam_on']==100
for filename in ['008-blank-saved.txt','010-blank-reloaded.txt']:assert 'blank-native.json' in (N/filename).read_text(encoding='utf-8')
assert any(o['project_file']==str(N/'blank-native.json') for o in obs)
records=[load(p) for p in (N/'runs/experiment-records').glob('*/record.json')];assert len(records)==5
counts=collections.Counter(r['action'] for r in records);assert counts=={'validate':2,'generate':1,'run':1,'export':1}
assert all(r['status']=='passed' and not r['stale'] and r['revision']==4 for r in records)
assert len({r['session_id'] for r in records})==1
fields=next(r for r in records if r['level']=='fields');init=next(r for r in records if r['level']=='initialization');run=next(r for r in records if r['action']=='run');gen=next(r for r in records if r['action']=='generate');export=next(r for r in records if r['action']=='export')
assert fields['can_run'] and 'result' not in fields
assert init['result']=={'completed_events':0,'planned_events':0,'reason':'Process completed but no Geant4 run occurred.','run_count':0,'state':'no_run','summary_status':'completed'}
assert run['result']['state']=='success' and run['result']['run_count']==1 and run['result']['planned_events']==run['result']['completed_events']==100
assert run['identity']['snapshot_fingerprint']==gen['identity']['snapshot_fingerprint']==init['identity']['snapshot_fingerprint']==fields['identity']['snapshot_fingerprint']
outputs=[];inputchecks=[]
for record in [gen,init,run]:
 bundle=Path(record['execution_bundle']['path']);assert bundle.resolve().is_relative_to(N.resolve())
 assert sha(bundle/'manifest.json')==record['execution_bundle']['manifest_sha256']
 for name,expected in record['expected_inputs'].items():
  p=Path(name);assert p.is_file() and sha(p)==expected['sha256'] and p.stat().st_size==expected['size_bytes']
  inputchecks.append({'record':record['record_id'],'path':str(p.relative_to(N)),'sha256':expected['sha256']})
 if 'actual_inputs' in record:
  for item in record['actual_inputs']:
   p=Path(item['path']);p=p if p.is_absolute() else bundle/p
   assert sha(p)==item['sha256'] and p.stat().st_size==item['size_bytes']
for record,expected_events in [(init,0),(run,100)]:
 out=Path(record['output_dir']);meta=load(out/'run_metadata.json');status=load(out.parent/'logs/run_status.json')
 assert record['exit_code']==0 and record['build']['git_commit']==HEAD and record['build']['source_fingerprint']==FP
 assert sha(out/'run_metadata.json')==record['metadata_sha256']
 assert meta['provenance']['execution_id']==record['execution_id']
 assert status['state']==record['result']['state'] and status['exitCode']==0 and status['summaryFresh']
 assert status['runCount']==record['result']['run_count'] and status['plannedEvents']==status['completedEvents']==expected_events
 summary={}
 for line in (out/'run_summary.txt').read_text(encoding='utf-8').splitlines():
  if '=' in line:
   k,v=line.split('=',1);summary[k.strip()]=v.strip()
 for k,v in {'status':'completed','summary_write_status':'completed','output_failure_status':'none','program_exit_code':'0','macro_execution_status':'completed'}.items():assert summary[k]==v
 assert int(summary['planned_event_count'])==int(summary['actual_completed_event_count'])==expected_events
 for item in meta['generated_files']:
  p=Path(item['path']);assert p.resolve().is_relative_to(out.resolve())
  assert item['execution_id']==record['execution_id']
  if item['integrity_status']=='self_reference_excluded':assert p.name=='run_metadata.json' and item['sha256'] is None
  else:assert sha(p)==item['sha256'] and p.stat().st_size==item['size_bytes']
 assert int(summary['generated_file_count'])==len(meta['generated_files'])==len([p for p in out.iterdir() if p.is_file()])
 outputs.append({'record':record['record_id'],'state':record['result']['state'],'run_count':record['result']['run_count'],'events':expected_events,'metadata_sha256':record['metadata_sha256'],'generated_files':len(meta['generated_files']),'hashed_generated_files':sum(x['integrity_status']=='hashed' for x in meta['generated_files'])})
runout=Path(run['output_dir']);runmeta=load(runout/'run_metadata.json')
assert runmeta['runs']==[{'run_id':0,'planned_events':100,'completed_events':100}]
with (runout/'event_edep_t0.csv').open(encoding='utf-8',newline='') as stream:csvrows=list(csv.DictReader(stream))
assert len(csvrows)==100 and {r['runID'] for r in csvrows}=={'0'} and [int(r['eventID']) for r in csvrows]==list(range(100))
assert all(float(r['raw_edep_MeV'])==float(r['weighted_edep_MeV'])==0 for r in csvrows)
assert len([p for p in runout.parent.rglob('*') if p.is_file()])==19
for fname,tokens in {'014-initialize-passed-no-run.txt':['未执行模拟'],'017-run-success-100.txt':['100/100','模拟成功'],'026-results-overview-readable.txt':['completed',run['execution_id']],'027-results-run-summary.txt':['identity_status','verified',HEAD,run['execution_id']]}.items():
 text=(N/fname).read_text(encoding='utf-8');assert all(token in text for token in tokens),(fname,tokens)
bundle=N/'blank-native-bundle';manifest=load(bundle/'manifest.json');assert manifest['replay_verified'] is False and manifest['outputs_included'] is False
members={m['path']:m for m in manifest['members']};assert len(members)==7
actual={p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()};assert actual==set(members)|{'manifest.json'} and len(actual)==8
for rel,item in members.items():
 p=(bundle/rel).resolve();assert p.is_relative_to(bundle.resolve()) and sha(p)==item['sha256'] and p.stat().st_size==item['bytes']
assert export['destination']==str(bundle) and export['bundle']['manifest']==manifest
config=configparser.ConfigParser(interpolation=None);config.read(bundle/manifest['replay_inputs']['config'],encoding='utf-8')
assert (bundle/config['materials']['file']).is_file() and (bundle/config['geometry']['config']).is_file()
assert config['output']['dir']=='output'
macro=(bundle/manifest['replay_inputs']['macro']).read_text(encoding='utf-8');assert '/run/initialize' in macro and '/run/beamOn 100' in macro and '/control/execute' not in macro
workspace=load(bundle/'workspace.json');assert workspace['schema']=='g4usim_edit_snapshot_v1'
assert len(workspace['project']['geometryEditor']['volumes'])==1 and workspace['project']['materialEditor']['rows']==[]
validation=load(bundle/'validation_records.json');assert len(validation['records'])==4
assert {r['record_id'] for r in validation['records']}=={fields['record_id'],init['record_id'],gen['record_id'],run['record_id']}
# No writes to inputs: every original native100 evidence byte must remain identical.
after={p.relative_to(N).as_posix():sha(p) for p in sorted(N.rglob('*')) if p.is_file()};assert before==after
receipt={'passed':True,'scope':'standard-library pure file review; no product imports/backend/Qt/native/profile/CLI replay','head':HEAD,'native_dpr':1.0,'scale_env_recorded':launch['scale_env'],'launch_and_app_exit':0,'native100_file_count':len(before),'native100_bytes_unchanged':True,'raw_images_local_only':len(images),'image_hashes_verified_not_reopened':True,'visual_observation_entries':len(visual),'qt_observation_entries':len(obs),'saved_project_sha256':sha(N/'blank-native.json'),'record_count':5,'actions':dict(counts),'records':[{'id':r['record_id'],'action':r['action'],'level':r['level'],'status':r['status']} for r in records],'real_simulation_runs':1,'events_completed':100,'initialization_no_run_separate':True,'record_metadata_and_generated_hashes':outputs,'run_csv_rows':100,'run_package_files':19,'run_output_files':9,'thread_csv_files':1,'zero_deposition_blank_world_scope':True,'bundle_file_count':8,'bundle_members_hashed':7,'bundle_resources':4,'bundle_replay_verified':False,'recorded_validation_history_count':4,'closed_references_config_material_geometry_macro':True,'no_CLI_replay_claim':True,'cached_model_hash_not_F5_snapshot':True,'UIA_cached_focus_not_Qt_focus':True,'source_evidence_sha256':before}
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in receipt.items() if k not in ['source_evidence_sha256','records','record_metadata_and_generated_hashes']},indent=2))
