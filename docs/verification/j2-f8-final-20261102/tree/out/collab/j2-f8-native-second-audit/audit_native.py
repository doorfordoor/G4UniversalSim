"""Independent file-only native evidence audit. No Qt/app/backend execution."""
import argparse,ast,hashlib,importlib.metadata,json,os,re,subprocess,time
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--workspace',type=Path,required=True);ap.add_argument('--expected-head',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
ROOT=args.workspace.resolve();BASE=args.root.resolve();OUT=args.output.resolve();artifacts={};errors=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.resolve().relative_to(ROOT).as_posix()
def evidence(p,role):
 p=Path(p)
 if not p.is_file():errors.append({'kind':'missing_file','path':str(p),'role':role});return None
 key=rel(p);raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest();e=artifacts.setdefault(key,{'path':key,'bytes':len(raw),'sha256':h,'roles':[]})
 if role not in e['roles']:e['roles'].append(role)
 return h
def read(p,role):evidence(p,role);return json.loads(p.read_text(encoding='utf-8-sig'))
def expect(ok,kind,detail):
 if not ok:errors.append({'kind':kind,'detail':detail})
def dump(name,obj):(OUT/name).write_bytes((json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())
def git(*opts):return subprocess.check_output(['git','-c','core.longpaths=true',*opts],cwd=ROOT,text=True).strip()
head_before=git('rev-parse','HEAD');status_before=git('status','--porcelain');expect(head_before==args.expected_head,'workspace_head',head_before);expect(not status_before,'workspace_dirty',status_before)
current_gui={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in (ROOT/'gui/g4usim_gui').rglob('*.py')};groups={};gui_maps=[];host_sources={};exe_hashes={}
for name in ['native100','native125','native150']:
 folder=BASE/name;launch=read(folder/'launch.json','native_launch');identity=read(folder/'identity.json','native_identity');exitrow=read(folder/'exit.json','native_exit');visual=read(folder/'visual-observations.json','main_direct_visual_observations');evidence(folder/'observations.jsonl','passive_Qt_observation_rows');observations=[json.loads(s) for s in (folder/'observations.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
 for f in ['host.stdout.log','host.stderr.log','history.json']:evidence(folder/f,'host_auxiliary_log_or_history')
 expect(launch['head']==launch['ending_head']==identity['head']==args.expected_head,'host_head_identity',name)
 expect(launch['status']=='exited' and launch['process_exit_code']==exitrow['exit_code']==0,'host_exit',name)
 expect(launch['ending_git_status']=='','host_ending_git_status',name)
 caps=launch['capabilities'];expect(caps['build_git_commit']==args.expected_head and caps['build_git_source_state']=='clean','backend_build_identity',name)
 exe=Path(identity['exe']);actual=exe_hashes.setdefault(str(exe),sha(exe));expect(actual==identity['exe_sha256']==launch['exe_sha256']==launch['ending_exe_sha256'],'executable_sha',name)
 expect(identity['gui_files']==current_gui,'GUI_source_map',{'group':name,'mismatch':[p for p,h in identity['gui_files'].items() if current_gui.get(p)!=h],'extra_files':sorted(set(current_gui)-set(identity['gui_files']))})
 gui_maps.append(identity['gui_files']);command=launch['command'];host=Path(command[2]);hosthash=sha(host);expect(hosthash==launch['host_sha256']==identity['host_sha256'],'host_source_sha',name);evidence(host,'current_native_host_setup_and_passive_observer');host_sources[str(host)]=host.read_text(encoding='utf-8-sig')
 runtime=launch['runtime'];prefix=Path(runtime['prefix']);expect(Path(command[0])==Path(identity['python']) and Path(identity['python']).parent==prefix/'Scripts','full_venv_python_identity',name)
 expect(launch['qpa']=='windows','native_qpa',name);expect(Path(runtime['executable']).parent==prefix/'Scripts','runtime_executable_prefix',name)
 required=['PySide6','shiboken6','pyvista','pyvistaqt','vtk','qtpy'];module_checks=[]
 distributions={re.sub('[-_.]+','-',d.metadata['Name']).lower():d.version for d in importlib.metadata.distributions(path=[str(prefix/'Lib/site-packages')]) if d.metadata['Name']}
 for module in required:
  info=runtime['modules'][module];p=Path(info['file']);installed=distributions.get(module.lower());ok=p.is_file() and p.resolve().is_relative_to(prefix.resolve()) and installed==info['version'];expect(ok,'full_venv_module_metadata',{'group':name,'module':module,'recorded':info['version'],'installed':installed});module_checks.append({'name':module,'recorded_version':info['version'],'installed_metadata_version':installed,'recorded_file_exists_in_full_venv':p.is_file() and p.resolve().is_relative_to(prefix.resolve())})
 expect(runtime['qt']==runtime['modules']['PySide6']['version']==runtime['modules']['shiboken6']['version'],'Qt_binding_versions',name)
 expect(identity['pyvista']['file']==runtime['modules']['pyvista']['file'] and identity['pyvista']['version']==runtime['modules']['pyvista']['version'],'actual_host_pyvista_identity',name)
 images=[];covered=set();visual_items=[]
 for item in visual:
  row={'label':item['label'],'main_observation_note':item['note'],'recorded_time':item['time'],'image_files':[],'observed_by':'main direct screenshot inspection as explicitly supplied by user','auditor_new_pixel_inspection':False}
  t=item['time']/1000 if item['time']>1e12 else item['time'];expect(launch['started']<=t<=launch['ended']+5,'visual_time_outside_host_window',{'group':name,'label':item['label']})
  for image in item['images']:
   p=Path(image['path']);expect(p.resolve().is_relative_to(folder.resolve()),'visual_png_wrong_root',{'group':name,'path':str(p)});h=evidence(p,'original_main_observed_PNG');expect(p.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'),'not_PNG_signature',str(p));covered.add(p.resolve());row['image_files'].append({'path':rel(p),'sha256':h,'bytes':p.stat().st_size});images.append({'path':rel(p),'sha256':h,'visual_label':item['label']})
  for p in folder.glob(item['label']+'.txt'):evidence(p,'optional_UIA_snapshot')
  visual_items.append(row)
 png_files=list(folder.glob('*.png'));unreferenced=[rel(p) for p in png_files if p.resolve() not in covered]
 for p in png_files:
  if p.resolve() not in covered:evidence(p,'unreferenced_PNG_not_promoted_to_observed')
 expect(not unreferenced,'PNG_without_visual_observation_reference',{'group':name,'files':unreferenced})
 dprs=sorted({x['dpr'] for x in observations});target={'native100':1.0,'native125':1.25,'native150':1.5}[name];expect(dprs==[target],'effective_DPR',{'group':name,'recorded':dprs})
 viewport_rows=sum(len(x.get('project_viewports',[])) for x in observations);groups[name]={'recorded_host_exited_zero':True,'head':identity['head'],'exe_sha256':actual,'source_fingerprint':caps['source_fingerprint'],'GUI_file_count':len(identity['gui_files']),'GUI_map_matches_current_source':identity['gui_files']==current_gui,'host_sha256':hosthash,'launch_supervisor_pid':launch['pid'],'actual_python_host_pid':identity['pid'],'PID_boundary':'venv redirector/child PIDs kept distinct; not assumed equal','runtime_prefix':str(prefix),'runtime_modules':module_checks,'observed_effective_DPR':dprs,'scale_environment':launch['scale_env'],'passive_rows':len(observations),'observed_pages':sorted({x['page'] for x in observations}),'project_raw_hash_count':len({x['project_sha'] for x in observations}),'edit_history_states':list({json.dumps(x['edit_history'],sort_keys=True) for x in observations}),'visual_items':visual_items,'original_PNG_count':len(png_files),'referenced_PNG_count':len(covered),'passive_viewport_geometry_rows':viewport_rows,'geometry_is_not_unobscured_visual_proof':True,'QQ_overlay_pixels_excluded':True,'observed_scope_only':True}
# Passive host source scope: construction deliberately sets a test project/path,
# history, theme, size and position before show; timers only read application state.
passive=[]
for host,source in host_sources.items():
 tree=ast.parse(source);calls={n.name:sorted({c.func.attr for c in ast.walk(n) if isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute)}) for n in tree.body if isinstance(n,ast.FunctionDef)};forbidden={'setFocus','setValue','ensureWidgetVisible','ensureVisible','scrollTo','click','keyPress','mousePress'}
 expect(not any(forbidden.intersection(names) for names in calls.values()),'observer_mutates_UI',host)
 passive.append({'host':rel(Path(host)),'sha256':sha(Path(host)),'observer_method_names':calls,'setup_boundary':'Before show, sets actual MainWindow executable/runs paths, isolated settings/history/recovery, initial project, edit-history reset, language/theme/position/size. This setup is not a user-action test. After show observer/timer reads only; external real UI inputs are main-owned.','direct_run_generate_export_focus_or_scroll_dispatch_from_observer':False})
# native100 actual saved blank, workflow records, input/metadata hashes and export.
f=BASE/'native100';saved=read(f/'blank-native.json','actual_saved_and_reopened_blank_project');expect(saved['schema']=='G4UniversalSimProject' and saved['version']==8,'saved_blank_schema',None);expect(len(saved['materialEditor']['rows'])==0,'blank_material_rows',None);volumes=saved['geometryEditor']['volumes'];expect(len(volumes)==1 and volumes[0]['name']=='world' and not volumes[0]['sensitive'],'blank_world_only',None);expect(saved['runSettings']['beam_on']==100,'blank_planned_event_count',None)
passive100=[json.loads(s) for s in (f/'observations.jsonl').read_text().splitlines() if s.strip()];expect(any(Path(x.get('project_file') or '').resolve()==(f/'blank-native.json').resolve() for x in passive100 if x.get('project_file')),'blank_project_file_observed',None)
records=[]
def bundle_check(folder,manifest_expected=None):
 p=folder/'manifest.json';manifest=read(p,'bundle_or_execution_input_manifest');h=sha(p);expect(not manifest_expected or h==manifest_expected,'bundle_manifest_sha',str(folder));checked=[]
 for member in manifest['members']:
  name=member['path'];candidate=folder/name;expect(not Path(name).is_absolute() and '..' not in Path(name).parts and candidate.resolve().is_relative_to(folder.resolve()),'bundle_resource_escape',name);actual=evidence(candidate,'bundle_member_'+member['role']);expect(actual==member['sha256'] and candidate.stat().st_size==member['bytes'],'bundle_member_hash_or_bytes',name);checked.append({'path':rel(candidate),'role':member['role'],'bytes':member['bytes'],'sha256':actual})
 return {'manifest':rel(p),'sha256':h,'members':checked,'history_trust':manifest['history_trust'],'replay_verified':manifest['replay_verified'],'outputs_included':manifest['outputs_included']}
for p in sorted((f/'runs').rglob('record.json')):
 rec=read(p,'native100_actual_workflow_record');expect(rec['status']=='passed' and rec['stale'] is False,'workflow_record_status',rec['record_id']);row={k:rec.get(k) for k in ['action','level','record_id','revision','session_id','status','stale','can_run','events','execution_id','result','exit_code']};row['path']=rel(p);row['sha256']=sha(p)
 if rec.get('identity'):expect(rec['identity']['backend']['sha256']==groups['native100']['exe_sha256'],'workflow_backend_identity',rec['record_id'])
 expected=[]
 for path,entry in rec.get('expected_inputs',{}).items():
  fp=Path(path);actual=evidence(fp,'native100_expected_input');expect(actual==entry['sha256'] and fp.stat().st_size==entry['size_bytes'],'expected_input_hash',path);expected.append({'path':rel(fp),'sha256':actual,'bytes':fp.stat().st_size})
 row['expected_inputs_checked']=expected
 if rec.get('execution_bundle'):row['execution_bundle_checked']=bundle_check(Path(rec['execution_bundle']['path']),rec['execution_bundle']['manifest_sha256'])
 for observed in rec.get('actual_inputs',[]):
  fp=Path(observed['path']);actual=evidence(fp,'native100_backend_observed_input');expect(actual==observed['sha256'] and fp.stat().st_size==observed['size_bytes'],'actual_input_hash',observed['path'])
 if rec.get('build'):expect(rec['build']['git_commit']==args.expected_head and rec['build']['git_source_state']=='clean' and rec['build']['source_fingerprint']==groups['native100']['source_fingerprint'],'workflow_build_identity',rec['record_id'])
 if rec.get('output_dir'):
  output=Path(rec['output_dir']);s=output/'run_summary.txt';evidence(s,'native100_original_run_summary');values={k.strip():v.strip() for line in s.read_text().splitlines() if '=' in line for k,v in [line.split('=',1)]};expect(values['status']=='completed' and values['summary_write_status']=='completed' and values['output_failure_status']=='none','workflow_output_summary',rec['record_id']);row['run_summary_facts']={k:values.get(k) for k in ['status','run_count','run_0_planned_events','run_0_completed_events','summary_write_status','output_failure_status']}
  metadata=output/'run_metadata.json';md=read(metadata,'native100_original_run_metadata');expect(sha(metadata)==rec['metadata_sha256'],'metadata_sha',rec['record_id']);expect(md['provenance']['execution_id']==rec['execution_id'],'execution_id_crosscheck',rec['record_id'])
  if rec['level']=='initialization':expect(rec['result']['state']=='no_run' and rec['result']['run_count']==0 and rec['events']=='unobserved','initialization_not_event_proof',None)
  if rec['action']=='run':expect(rec['result']['state']=='success' and rec['result']['planned_events']==rec['result']['completed_events']==100 and values['run_0_planned_events']==values['run_0_completed_events']=='100','actual_100_of_100',None)
 if rec.get('initialization_mesh'):
  mesh=Path(rec['initialization_mesh']);expect(evidence(mesh,'native100_initialized_backend_geometry')==rec['initialization_mesh_identity']['sha256'],'initialization_mesh_sha',None)
 if rec['action']=='export':row['export_checked']=bundle_check(Path(rec['destination']),rec['bundle']['manifest_sha256']);expect(row['export_checked']['history_trust']=='stale_requires_revalidation' and row['export_checked']['replay_verified'] is False and row['export_checked']['outputs_included'] is False,'offline_trust_boundary',None)
 records.append(row)
expect(any(x['action']=='generate' for x in records) and any(x['level']=='initialization' for x in records) and any(x['action']=='run' for x in records) and any(x['action']=='export' for x in records),'workflow_record_chain_incomplete',None)
head_after=git('rev-parse','HEAD');status_after=git('status','--porcelain');expect(head_after==head_before and status_after==status_before,'source_identity_changed_during_audit',None)
receipt={'schema':'j2_f8_second_candidate_native_file_audit_v1','candidate_head':args.expected_head,'audit_integrity_status':'verified' if not errors else 'errors','audit_errors':errors,'observed_groups':groups,'same_GUI_identity_all_three':all(x==gui_maps[0] for x in gui_maps),'passive_host_scope':passive,'native100_saved_blank':{'path':rel(f/'blank-native.json'),'sha256':sha(f/'blank-native.json'),'projectName':saved['projectName'],'schema_version':8,'custom_material_rows':0,'world_only':True,'planned_events':100},'native100_actual_record_chain':records,'open_items':[{'id':'F6_narrow_preview_dock_boundary','status':'open','evidence':'native150/017-f6-preview-observation-0.png','note':'Main reports right-edge/text clipping. No rect-containment shortcut or overall pass.'},{'id':'History_name_label_accessibility_omission','status':'open','evidence':['native125/005-history-0.png','native150/023-page8-history-0.png'],'note':'Main reports missing History name/label/accessibility coverage; retain open.'}],'overall_native_acceptance':False,'stage_complete':False,'visual_evidence_attribution':'Main explicitly directly inspected each supplied observation screenshot; this agent only audits files, hashes, recorded scope and actual records. Does not re-inspect pixels or assert unobscured from rectangle containment.','native125_QQ_boundary':'before-move and moved observations still partly occluded; only wizard-geometry-clear and subsequent explicit notes claim unobscured dialog after natural drag. QQ pixels excluded.','native150_project_retained':'Main directly observes fixed Project label/full field at retained-dock steps; does not close the distinct F6 or History issues.','followup_all_three_effective_DPRs':[{'DPR':d,'status':'pending_after_new_repair','scope':['three explicit History buddies and dynamic language','real-layout-only QLayout traversal','F6 narrow-dock limitation observed, no claim repaired']} for d in [1.0,1.25,1.5]],'offline_bundle_boundary':'Export member SHA and stale history checked only; no offline replay or transport physics validation performed.','native_actions_by_this_auditor':False,'product_or_tracked_changes_by_this_auditor':False,'head_before':head_before,'head_after':head_after,'git_status_after':status_after,'audit_finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
dump('native-audit.json',receipt);dump('artifact-manifest.json',{'schema':'j2_f8_native_second_artifacts_v1','candidate_head':args.expected_head,'artifacts':sorted(artifacts.values(),key=lambda x:x['path']),'source_raw_files_unchanged':True,'overall_native_acceptance':False,'observed_scope_only':True});print(json.dumps({'audit_integrity_status':receipt['audit_integrity_status'],'errors':errors,'PNG_counts':{k:v['original_PNG_count'] for k,v in groups.items()},'workflow_records':len(records),'overall_native_acceptance':False,'artifacts':len(artifacts)},ensure_ascii=False));raise SystemExit(0 if not errors else 1)
