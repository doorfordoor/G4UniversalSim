from pathlib import Path
import json,hashlib,collections
ROOT=Path(__file__).resolve().parents[3];N=ROOT/'out/verification/j2-f8-2ec5b14/native125';OUT=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={p.relative_to(N).as_posix():sha(p) for p in sorted(N.rglob('*')) if p.is_file()}
launch=load(N/'launch.json');identity=load(N/'identity.json');exit=load(N/'exit.json');sync_original=load(N/'terminal-sync.json');sync=load(N/'terminal-sync-r2.json');visual=load(N/'visual-observations.json');obs=[json.loads(l) for l in (N/'observations.jsonl').read_text(encoding='utf-8').splitlines()]
HEAD='2ec5b14fc823ad837dce3ea6f5d7c5ae3f66a3c8';EXE='fe5d23d309106d9fca7ad179f6c0cb39fa8b98c6ef35286a0b21866b90d89f89';OLD='01e0fb795f93772ccfa818d625fee145d8da1ad3ad80894372a9a855f0af108a'
assert launch['head']==launch['ending_head']==identity['head']==HEAD
assert launch['exe_sha256']==launch['ending_exe_sha256']==identity['exe_sha256']==EXE
assert sha(Path(identity['exe']))==EXE
assert launch['capabilities']['build_git_commit']==HEAD and launch['capabilities']['build_git_source_state']=='clean'
assert launch['status']=='exited' and launch['process_exit_code']==exit['exit_code']==sync['observed_session_exit_code']==0 and exit['visible'] is False
assert sync['launch_exit_code']==launch['process_exit_code']==0
assert sync_original['launch_exit_code'] is None
assert sync['session_id']==6497 and sync['remaining_count']==0 and sync['remaining']==[] and sync['launch_status']=='exited'
assert launch['ending_git_status']=='' and launch['qpa']=='windows'
assert len(identity['gui_files'])==149 and all(sha(ROOT/p)==digest for p,digest in identity['gui_files'].items())
assert sha(ROOT/'out/collab/j2-f8-native/host-v2.py')==launch['host_sha256']==identity['host_sha256']
assert {o['dpr'] for o in obs}=={1.25}
assert len(visual)==24 and [v['index'] for v in visual]==list(range(1,25))
images={}
for v in visual:
 for image in v['screenshots']:
  p=N/image['file'];assert p.resolve().is_relative_to(N.resolve()) and sha(p)==image['sha256'] and p.stat().st_size==image['bytes']
  assert image['raw_local_only_other_application_pixels_possible'] is True
  images[image['file']]=image['sha256']
assert set(images)=={p.name for p in N.glob('*.jpg')}
labels={v['label']:v for v in visual}
assert all(s in labels for s in ['i1-discovered','i2-open','i2-closed','i1-closed','imported-awaiting-validation','import-saved','template-run-default','template-run-unchecked','template-finished','template-saved','reentry-start','reentry-geometry','reentry-back','reentry-cancelled'])
oldbundle=ROOT/'out/verification/j2-f8-18c5858/native100/blank-native-bundle';oldreceipt=load(ROOT/'out/collab/native100-file-independent/receipt.json');manifest=load(oldbundle/'manifest.json')
files={p.relative_to(oldbundle).as_posix():sha(p) for p in oldbundle.rglob('*') if p.is_file()};assert len(files)==8
for rel,digest in files.items():assert digest==oldreceipt['source_evidence_sha256']['blank-native-bundle/'+rel],rel
for m in manifest['members']:
 p=oldbundle/m['path'];assert sha(p)==m['sha256'] and p.stat().st_size==m['bytes']
assert manifest['replay_verified'] is False
imported=load(N/'imported-18c-bundle.json');template=load(N/'template-finished.json')
for project in [imported,template]:
 assert project['schema']=='G4UniversalSimProject' and project['version']==8 and project['runInputMode']=='generated'
 assert Path(project['executable']).resolve()==Path(identity['exe']).resolve()
 assert Path(project['workspaceRoot']).resolve()==oldbundle.resolve()
 assert Path(project['runsRoot']).resolve()==(N/'import-runs').resolve()
 assert project['configPath']==project['macroPath']==project['outputDir']==''
 assert project['pathSettings']['materials_config']==project['pathSettings']['geometry_config']==''
 assert project['materialEditor']['source_path']==project['geometryEditor']['source_path']==''
 assert project['materialEditor']['is_dirty'] and project['geometryEditor']['is_dirty']
 assert project['materialEditor']['rows']==[]
assert imported['projectName']=='new_simulation' and imported['sourceEditor']['particle']=='gamma' and imported['sourceEditor']['energy']=='1 MeV'
assert len(imported['geometryEditor']['volumes'])==1 and imported['runSettings']['beam_on']==100 and imported['runSettings']['threads']==1
assert template['projectName']=='single_target' and template['sourceEditor']['particle']=='proton' and template['sourceEditor']['energy']=='100 MeV'
assert template['runSettings']['beam_on']==1000 and template['runSettings']['threads']==2
assert [(v['name'],v['material']) for v in template['geometryEditor']['volumes']]==[('world','G4_Galactic'),('Target','G4_WATER')]
records=[load(p) for p in (N/'import-runs').rglob('record.json')];assert len(records)==5
historical=[r for r in records if r['stale']];current=[r for r in records if not r['stale']]
assert len(historical)==4 and len(current)==1 and current[0]['action']=='import_history' and current[0]['imported_count']==4 and current[0]['status']=='passed'
assert collections.Counter(r['action'] for r in historical)=={'validate':2,'generate':1,'run':1}
for r in historical:
 assert r['status']=='stale' and r['history_trust']=='historical_requires_local_revalidation' and r['stale_reason']=='imported_history_requires_revalidation'
 assert r['identity']['backend']['sha256']==OLD
 assert 'output_dir' not in r and 'package' not in r and 'command' not in r
assert not any(not r['stale'] and r['action'] in ['validate','generate','run'] for r in records)
assert not list((N/'import-runs').rglob('run_metadata.json')) and not list((N/'import-runs').rglob('run_summary.txt'))
# Textual UIA evidence only; no new pixel inspection claims.
for filename,tokens in {'003-i1-discovered.txt':['11.3.2'],'004-i2-open.txt':['关闭'],'010-imported-awaiting-validation.txt':['待验证','new_simulation'],'012-import-saved.txt':['待验证'],'016-template-run-default.txt':['完成后生成运行包并运行'],'017-template-run-unchecked.txt':['完成后生成运行包并运行'],'020-template-saved.txt':['single_target'],'024-reentry-cancelled.txt':['single_target']}.items():
 text=(N/filename).read_text(encoding='utf-8');assert all(t in text for t in tokens),(filename,tokens)
assert all(o['runner_state']=='ProcessState.NotRunning' for o in obs)
assert any(o['modal']=='环境发现与诊断' for o in obs) and any(o['modal']=='安装 Geant4 环境' for o in obs)
assert any(o['project_file']==str(N/'imported-18c-bundle.json') for o in obs) and any(o['project_file']==str(N/'template-finished.json') for o in obs)
last=obs[-1];assert last['modal'] is None and last['project_file']==str(N/'template-finished.json')
assert last['edit_history']=={'undo':True,'redo':False,'modified':False}
saved=next(o for o in obs if o['project_file']==str(N/'template-finished.json'))
assert all(o['project_sha']==saved['project_sha'] for o in obs if o['time']>=saved['time'])
after={p.relative_to(N).as_posix():sha(p) for p in sorted(N.rglob('*')) if p.is_file()};assert before==after
assert (N/'host.stdout.log').stat().st_size==(N/'host.stderr.log').stat().st_size==0
result={'passed':True,'main_visual_scope_sha256':sha(ROOT/'out/collab/j2-f8-2ec5b14-main-native-scope.md'),'terminal_sync_original_summary_null_retained':True,'terminal_sync_r2_matches_actual_launch_field':True,'scope':'fourth native125 narrow standard-library file review only; no product/Qt/native/backend/CI/profile/CLI replay','head':HEAD,'exe_sha256':EXE,'actual_dpr':1.25,'scale_env':launch['scale_env'],'GUI_files_matched':149,'session':6497,'session_launch_app_exits':0,'terminal_sync_remaining':0,'terminal_sync_launch_exit_summary_field':sync['launch_exit_code'],'raw_visual_records':24,'raw_images_hash_verified_local_only':len(images),'native_evidence_files_unchanged':len(before),'original_bundle8_files_unchanged_against_previous_independent_receipt':True,'import_current_history_record_count':1,'imported_stale_history_count':4,'new_current_validation_or_run_records':0,'two_saved_projects':{'imported':{'sha256':sha(N/'imported-18c-bundle.json'),'name':imported['projectName'],'events_planned':100,'volumes':1},'template':{'sha256':sha(N/'template-finished.json'),'name':template['projectName'],'events_planned':1000,'volumes':2}},'passive_sample_count':len(obs),'all_observed_runner_states_NotRunning':True,'cached_project_and_edit_flags_not_live_F5_snapshot':True,'UIA_cached_focus_not_Qt_focus':True,'checkbox_check_state_not_exposed_in_text_snapshots':True,'QQ_refused_coordinate_then_Return_completion_per_main_record_not_new_pixel_claim':True,'no_new_CLI_replay_or_simulation_success_claim':True,'evidence_sha256':before,'bundle_sha256':files}
(OUT/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ['evidence_sha256','bundle_sha256']},indent=2))

