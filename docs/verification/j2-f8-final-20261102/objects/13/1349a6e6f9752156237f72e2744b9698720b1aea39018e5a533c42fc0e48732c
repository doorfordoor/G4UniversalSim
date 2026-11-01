"""Narrow OUT increment: only terminal third-candidate evidence, no pending peers."""
import collections,hashlib,importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
R=Path.cwd();A=R/'out/collab/j2-f8-archive-plan';P=A/'versions/v3-18c5858';O=A/'versions/v4-18c5858-incremental-draft';S=A/'staging-v4-18c5858-incremental-draft';B=R/'out/verification/j2-f8-18c5858';HEAD='18c5858fd6e80a5cb6096beacebfef69c479ad49'
assert not O.exists() and not S.exists();O.mkdir();S.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def j(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD
status=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True);assert not status.strip()
pm=j(P/'effective-manifest.json');prefix={x['logical_path']:x for x in pm['entries']};prefix_lines=''.join(x['logical_path']+'\t'+x['sha256']+'\t'+str(x['bytes'])+'\n' for x in pm['entries']).encode();anchor={'predecessor':'versions/v3-18c5858','predecessor_staging':'staging-v3-18c5858','manifest_sha256':sha(P/'effective-manifest.json'),'final_seal_sha256':sha(P/'final-seal.json'),'entry_count':len(pm['entries']),'ordered_prefix_sha256':hashlib.sha256(prefix_lines).hexdigest(),'rule':'Original prefix entries/order/raw SHA stay immutable. A later changed source is a distinct version group, never replace an older logical identity.'};put(O/'old-prefix-anchor.json',anchor)
items={};images=[];metadata=[];groups=[];pairs=[]
ck=R/'scripts/check_report_evidence.py';sp=importlib.util.spec_from_file_location('_incremental_evidence_checker',ck);mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
def add(p,role,expected=None):
 p=Path(p);rel=p.relative_to(R).as_posix();size=p.stat().st_size
 if p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:
  h=sha(p);assert expected is None or expected==h;images.append({'source':rel,'bytes':size,'sha256':h,'local_raw_original_retained':True,'staging_action':'metadata_only','public_action':'metadata_only_no_raw_Git_image','contains_other_application_pixels':'main explicitly declared all third-native originals contain QQ','visual_claim':'Main excludes overlay pixels; inventory does not elevate acceptance'});return None
 if p.suffix.lower() in {'.exe','.dll','.pyd','.so','.zip'} or size>8*1024*1024:
  metadata.append({'source':rel,'bytes':size,'sha256':expected,'digest_provenance':'producer receipt only; no SDK/data/binary rehash','payload':'omitted'});return None
 h=sha(p);assert expected is None or h==expected,(rel,h,expected);logical='tree/'+rel
 if logical in prefix:
  assert prefix[logical]['sha256']==h,('Old-prefix identity collision requires separate version',rel)
  items[logical]={'source':rel,'logical_path':logical,'sha256':h,'bytes':size,'role':role,'payload':'reuse_sealed_predecessor_object','object':prefix[logical]['object']};return logical
 old=items.get(logical)
 if old:assert old['sha256']==h;return logical
 obj='objects/'+h[:2]+'/'+h;dst=S/obj;dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():shutil.copyfile(p,dst)
 assert sha(dst)==h
 q=S/logical;q.parent.mkdir(parents=True,exist_ok=True);os.link(dst,q)
 items[logical]={'source':rel,'logical_path':logical,'sha256':h,'bytes':size,'role':role,'payload':'copied_incremental_local_only','object':obj};return logical

def report(p,role,expected=None):
 logical=add(p,role,expected);x=j(p)
 for c in x['results']:
  q=mod.resolve_log(c,p);assert q;add(q,role+'_raw_case_log',c['log_sha256'])
 return logical,x
# Four Windows local profiles are read only after terminal launch status/identity checks.
for name in ['windows-static','windows-gui','windows113-backend','windows114-backend']:
 d=B/name;l=j(d/'launch.json');assert l['status']=='passed' and l['runner_exit_code']==l['gate_exit_code']==0 and l['identity_errors']==[];assert l['ending']['head']==HEAD
 p=Path(l['report']);logical,x=report(p,'third_windows_terminal_formal',l['report_sha256']);assert not x['git_dirty'] and all(c['status']=='pass' for c in x['results'])
 for q in d.iterdir():
  if q.is_file():add(q,'third_windows_terminal_launch_gate_receipt')
 baseline=Path(l['gate_command'][l['gate_command'].index('--baseline')+1]);bl,_=report(baseline,'matching_historical_baseline');pairs.append({'current':logical,'baseline':bl,'expected_exit':0,'group':name})
 groups.append({'group':name,'status':'terminal_passed','cases':len(x['results']),'assertions':x['assertions_executed_total'],'runner':0,'gate':0,'identity_errors':[],'original_head':HEAD})
# Real CI terminal collection: keep all failures, including the separately recorded Windows path assertion.
ci=B/'ci';c=j(ci/'collected-files-final.json');assert c['workflow_completion']=='all_completed' and all(x['status']=='completed' for x in c['runs'])
for q in sorted(ci.iterdir()):
 if q.is_file():add(q,'third_CI_original_terminal_receipt')
for x in c['files']:add(ci/Path(x['path']),x['role'],x['sha256'])
g=j(ci/'report-gates-current.json');assert (g['strict_pass'],g['strict_fail'],g['release_accepted'])==(4,4,False);bx={x['id']:x for x in j(R/'out/collab/j2-f8-baselines.json')['baselines']}
for a in g['artifacts']:
 for x in a['reports']:
  logical,raw=report(ci/Path(x['report']),'third_CI_original_profile_report',x['report_sha256']);base=R/Path(bx[x['baseline_id']]['original_report']);bl,_=report(base,'matching_CI_historical_baseline',x['baseline_report_sha256']);pairs.append({'current':logical,'baseline':bl,'expected_exit':0 if x['strict_gate']=='pass' else 1,'group':a['name']+'-'+x['profile']})
# All native hosts normal-exited; file audits remain individually scoped.
for name in ['native100','native125','native150']:
 d=B/name;launch=j(d/'launch.json');ex=j(d/'exit.json');assert ex['exit_code']==0 and launch['process_exit_code']==0 and launch['ending_head']==HEAD
 before_images=len(images)
 for q in sorted(d.rglob('*')):
  if q.is_file() and '__pycache__' not in q.parts:add(q,'third_native_normalexit_raw_file')
 groups.append({'group':name,'host_exit':0,'source_head':HEAD,'image_count':len(images)-before_images,'public_raw_images':False,'scope':'observed task pixels only; normalexit not overall acceptance','independent_file_review':'Harvey150/125 available; Ptolemy100 receipt pending'})
nd=R/'out/collab/j2-f8-18c5858-native-file-audit'
for q in sorted(nd.rglob('*')):
 if q.is_file() and '__pycache__' not in q.parts:add(q,'Harvey_150_125_file_audit')
put(O/'incremental-manifest.json',{'schema':'j2_f8_narrow_incremental_draft_v4','draft':True,'head':HEAD,'old_prefix_anchor_sha256':sha(O/'old-prefix-anchor.json'),'entries':list(items.values()),'image_metadata':images,'opaque_metadata':metadata,'CI_runs':c['runs'],'CI_strict_pass':4,'CI_strict_fail':4,'release_accepted':False,'groups':groups,'stage_complete':False,'publication':'No upload/Git writes; all third-native raw images local originals only; public metadata/observation text only'})
put(O/'strict-pairs-draft.json',{'pairs':pairs,'status':'inventory_only; original strict verdicts copied from terminal receipts; no new checker replay yet','no_original_failures_promoted':True})
put(O/'pending-slots.json',{'pending':['windows113-integration terminal receipt','windows114-integration terminal receipt','Ptolemy native100 file-audit handoff','Harvey OUT-only Linux QAccessible.Name diagnosis / fourth candidate review','Any new fourth-candidate docs only after coordinated diagnosis/decision','Final archive consolidation by main'],'not_executed':['Linux backend','Linux integration'],'limits':'Do not infer pending results from directories; no official command interruption, no product/native run, no stage closure. Windows M0 CI geometry line264 separate failure retained.'})
assert subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True)==status
# Recheck each already sealed prefix object, without reading mutable build/data source paths.
old_objects={x['sha256']:x for x in pm['entries']}
for h,x in old_objects.items():assert sha(A/'staging-v3-18c5858'/x['object'])==h
assert sha(P/'effective-manifest.json')==anchor['manifest_sha256'] and sha(P/'final-seal.json')==anchor['final_seal_sha256']
put(O/'old-prefix-verification.json',{'status':'passed','ordered_prefix_sha256':anchor['ordered_prefix_sha256'],'manifest_and_final_seal_unchanged':True,'sealed_objects_SHA_rechecked':len(old_objects),'tracked_unchanged':True,'pending_profile_directories_read':False})
for q in O.iterdir():
 if q.is_file():dest=S/'plan'/q.name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(q,dest)
print(json.dumps({'draft':str(O),'new_payload_files':sum(x['payload']=='copied_incremental_local_only' for x in items.values()),'inherited_references':sum(x['payload']=='reuse_sealed_predecessor_object' for x in items.values()),'third_native_images_metadata_only':len(images),'CI_strict':[4,4],'old_prefix_objects_verified':len(old_objects),'groups':groups},ensure_ascii=False))
