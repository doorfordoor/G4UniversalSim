"""OUT-only additive archive revision: immutable historical objects + terminal receipts."""
import collections,datetime,difflib,hashlib,importlib.util,json,os,re,shutil,subprocess,sys
from pathlib import Path
R=Path.cwd();A=R/'out/collab/j2-f8-archive-plan';V=A/'versions/v3-18c5858';S=A/'staging-v3-18c5858';OLD=A/'staging-v2';B=R/'out/verification/j2-f8-2901f42';HEAD='18c5858fd6e80a5cb6096beacebfef69c479ad49'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def j(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
assert not V.exists() and not S.exists(),'New revision paths required; preserve existing attempts'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD
status_before=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True);assert not status_before.strip()
V.mkdir(parents=True);S.mkdir();(S/'objects').mkdir();(S/'tree').mkdir()
base=j(A/'manifest-final.json');seal=j(OLD/'final-copy-receipt.json');assert sha(A/'manifest-final.json')==seal['source_manifest_sha256']
entries=[];bylogical={};locators={};skipped=[];pairs=[];privacy=collections.Counter();signals=[];closures=[]
def register(e,physical):
 logical=e['logical_path'];old=bylogical.get(logical)
 if old:
  assert old['sha256']==e['sha256'],('logical collision',logical)
  old['roles']=sorted(set(old['roles']+e['roles']));return old
 entries.append(e);bylogical[logical]=e;locators[logical]=physical;return e
for e in base['entries']:
 x=dict(e,group='inherited-original-v2',logical_path='tree/'+e['source'],payload_origin='sealed_staging_v2' if e['archive_action'].startswith('copy_') else 'metadata_only')
 if e['archive_action'].startswith('copy_'):
  p=OLD/e['object'];assert p.stat().st_size==e['bytes'];register(x,p)
 else:entries.append(x)
# Carry original planning and relocation receipts as a separate immutable group.
def scan(p,raw):
 if p.suffix.lower() in {'.png','.jpg','.jpeg','.zip','.exe','.dll','.pyd','.so'}:return
 try:t=raw.decode('utf-8-sig')
 except UnicodeDecodeError:privacy['opaque_non_utf8']+=1;return
 count=0
 for n,l in enumerate(t.splitlines(),1):
  kinds=[]
  if re.search(r'[A-Za-z]:[\\/]',l):kinds.append('authorized_task_or_tool_absolute_path')
  if re.search(r'FAKE|DUMMY|EXAMPLE|SYNTHETIC',l,re.I):kinds.append('explicit_synthetic_marker')
  if re.search(r'authorization|api[_-]?key|password|access[_-]?token|client[_-]?secret',l,re.I):kinds.append('credential_key_or_expression_context')
  secret=re.search(r'(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})',l)
  if secret:
   if any(k in p.as_posix().lower() for k in ['test','smoke']) or re.search(r'FAKE|DUMMY|EXAMPLE|SYNTHETIC',l,re.I):kinds.append('synthetic_secret_pattern_fixture')
   else:kinds.append('suspected_literal_secret_requires_context_review')
  for kind in kinds:
   privacy[kind]+=1;count+=1;signals.append({'path':p.relative_to(R).as_posix(),'line':n,'signal_type':kind,'value_recorded':False})
 if not count:privacy['text_files_no_signal_not_safety_review']+=1

def add(p,role,expected=None,group='second-candidate-2901f42',force=False):
 p=Path(p);assert p.is_file(),p;source=p.relative_to(R).as_posix();size=p.stat().st_size
 if p.suffix.lower() in {'.exe','.dll','.pyd','.so','.zip'} or size>8*1024*1024:
  skipped.append({'source':source,'bytes':size,'sha256':expected,'sha_policy':'reuse supplied producer receipt SHA; not rehashed' if expected else 'not rehashed; provenance receipt retained separately','reason':'binary/opaque container/large evidence metadata only','payload_in_git_candidate':False});return None
 raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest();assert expected is None or h==expected,('source SHA drift',source,h,expected)
 logical='tree/'+source
 if logical in bylogical and bylogical[logical]['sha256']!=h:logical='tree/groups/'+group+'/'+source
 e={'source':source,'logical_path':logical,'bytes':len(raw),'sha256':h,'object':'objects/'+h[:2]+'/'+h,'roles':[role],'group':group,'archive_action':'copy_local_authorized_verified_bytes','payload_origin':'workspace_terminal_snapshot','source_mtime_ns':p.stat().st_mtime_ns,'publication_scope':'authorized_local_archive_candidate_not_public_upload','privacy':{'status':'new_text_signal_scan_or_explicit_image_scope_not_safety_clearance','no_signal_is_not_safety_review':True}}
 if logical not in bylogical:scan(p,raw)
 return register(e,p)
def tree(d,role,group='third-candidate-reviewed-repair',all_images=False):
 for p in sorted(d.rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts:continue
  if p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'} and not all_images and not re.search(r'history-label|spacer|layout|natural-start',p.name,re.I):
   skipped.append({'source':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p),'reason':'nonessential diagnostic screenshot metadata only; no new visual review','payload_in_git_candidate':False});continue
  add(p,role,group=group)
for name in ['manifest-final.json','relocation-pairs.json','privacy-review-final.json','resolved-credential-signals.json','image-selection.json','metadata-only-omissions.json','historical-review-chains.json','first-candidate-coverage.json','README.md']:
 add(A/name,'original_v2_plan_receipt',group='inherited-plan-v2')
for p in sorted((A/'relocated-verification').glob('*.json')):add(p,'original_v2_relocation_receipt',group='inherited-plan-v2')
for p in sorted((A/'relocated-verification').glob('*.log')):add(p,'original_v2_strict_replay_log',group='inherited-plan-v2')
# A frozen checker is evidence tooling only; no product/profile is executed.
check=R/'scripts/check_report_evidence.py';add(check,'strict_checker_frozen_source');spec=importlib.util.spec_from_file_location('_archive_checker',check);checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
def report(p,role,expected=None):
 obj=add(p,role,expected);x=j(p);logs=[]
 for c in x['results']:
  q=checker.resolve_log(c,p);assert q is not None,(p,c['name']);o=add(q,role+'_raw_case_log',c['log_sha256']);logs.append(o['logical_path'])
 closures.append({'report':obj['logical_path'],'report_sha256':obj['sha256'],'cases':len(x['results']),'assertions':x['assertions_executed_total'],'original_git_head':x.get('git_head'),'original_git_dirty':x.get('git_dirty'),'pass':sum(c['status']=='pass' for c in x['results']),'fail':sum(c['status']=='fail' for c in x['results']),'skip':sum(c['status']=='skip' for c in x['results']),'logs':logs});return obj
local=j(B/'local-final-audit.json');assert local['status']=='passed' and not local['errors'];add(B/'local-final-audit.json','six_formal_terminal_audit')
for name,x in local['profiles'].items():
 p=R/Path(x['report']);cur=report(p,'second_local_formal_report',x['report_sha256']);lp=p.parent.parent/'launch.json';add(lp,'second_local_terminal_launch',x['launch_sha256']);l=j(lp);assert l['status']=='passed' and l['runner_exit_code']==l['gate_exit_code']==0 and l['identity_errors']==[]
 cmd=l['gate_command'];baseline=Path(cmd[cmd.index('--baseline')+1]);bo=report(baseline,'matching_historical_baseline');pairs.append({'lane':'second-'+name,'current':cur['logical_path'],'baseline':bo['logical_path'],'expected_exit':0,'group':'second_local_formal'})
 # Root-level gate/runner/launch logs, identities and first-failure receipts; never backend output trees.
 for q in sorted(lp.parent.iterdir()):
  if q.is_file():add(q,'second_local_launcher_gate_receipt')
 for q in sorted(p.parent.iterdir()):
  if q.is_file() and q.name!='report.json':add(q,'second_local_report_adjacent_evidence')
for q in sorted((B/'identity').rglob('*')):
 if q.is_file():
  expected=None
  if q.suffix.lower()=='.exe':
   fs=j(B/'identity/frozen-binaries/receipt.json')['files'];f=next(a for a in fs if Path(a['copy'])==q.relative_to(R));expected=f['sha256']
  add(q,'second_frozen_build_identity',expected)
# CI original terminal summaries, eight complete decoded job logs, strict reports and exact baselines.
ci=B/'ci';c=j(ci/'collected-files-final.json');assert c['workflow_completion']=='all_completed';assert len(c['runs'])==4
for q in sorted(ci.iterdir()):
 if q.is_file():add(q,'second_ci_original_terminal_or_collection_receipt')
for x in c['files']:add(ci/Path(x['path']),x['role'],x['sha256'])
g=j(ci/'report-gates-current.json');assert (g['strict_pass'],g['strict_fail'],g['release_accepted'])==(5,3,False)
bx={x['id']:x for x in j(R/'out/collab/j2-f8-baselines.json')['baselines']}
for a in g['artifacts']:
 for x in a['reports']:
  cur=report(ci/Path(x['report']),'second_ci_original_profile_report',x['report_sha256']);bp=R/Path(bx[x['baseline_id']]['original_report']);bo=report(bp,'matching_CI_historical_baseline',x['baseline_report_sha256']);pairs.append({'lane':'second-ci-'+a['name']+'-'+x['profile'],'current':cur['logical_path'],'baseline':bo['logical_path'],'expected_exit':0 if x['strict_gate']=='pass' else 1,'group':'second_CI_original'})
# Main observed images retained as bytes, no rectangle/pixel or physics acceptance inferred.
for name in ['native100','native125','native150']:tree(B/name,'second_native_original_file','second-native-observed-scope',True)
nd=R/'out/collab/j2-f8-native-second-audit';tree(nd,'second_native_independent_file_audit','second-native-audit',True)
for x in j(nd/'v2/artifact-manifest.json')['artifacts']:add(R/Path(x['path']),'second_native_audit_pinned_artifact',x['sha256'],group='second-native-observed-scope')
# Final and superseded author/independent versions remain separate; do not promote superseded drafts.
roots=['j2-resource-policy-path-review','j2-policy-final-v1-independent','f8-history-label','f8-history-label-independent','f8-layout-item-compat','f8-layout-item-compat-independent','f8-history-spacer-combined','f8-history-spacer-combined-independent','j2-f8-third-integration-plan','j2-f8-third-doc-draft','j2-f8-third-doc-independent-review','j2-f8-third-repair-applied']
for name in roots:tree(R/'out/collab'/name,'third_reviewed_repair_apply_freeze_or_original_failure')
# The fifteen applied code/doc source bytes are a separate 18c5858 identity group.
dm=j(R/'out/collab/j2-f8-third-doc-draft/v3/manifest.json');names=[x['path'] for x in dm['files']]+['gui/g4usim_gui/core/accessibility.py','gui/g4usim_gui/core/experiment_bundle.py','gui/g4usim_gui/widgets/run_history_page.py','gui/smoke_tests/smoke_f8_accessibility.py','gui/smoke_tests/smoke_j2_geometry.py','scripts/test_k1_bundle.py']
for name in names:add(R/name,'third_applied_source_18c5858',group='third-applied-source-18c5858')
for q in sorted((A/'supplements').glob('*.json')):add(q,'archive_scope_supplement')
# Preserve original ten failed strict pairs as part of the new relocation verification.
for x in j(A/'relocation-pairs.json')['pairs']:pairs.append({'lane':'first-'+x['lane'],'current':'tree/'+x['current'],'baseline':'tree/'+x['baseline'],'expected_exit':x['expected_current_gate_exit'],'group':'first_failed_original'})
put(V/'report-closures.json',{'closures':closures,'local_2901f42_cases':sum(x['cases'] for x in closures if '/j2-f8-2901f42/windows' in x['report']),'original_report_bytes_rewritten':False})
put(V/'strict-pairs.json',{'pairs':pairs,'original_failures_expected_to_remain_failed':True})
put(V/'privacy-signals.json',{'scope':'new text only; inherited v2 classifications preserved','counts':privacy,'locations_no_values':signals,'suspected_literals':[x for x in signals if x['signal_type']=='suspected_literal_secret_requires_context_review'],'no_signal_is_not_safety_review':True,'public_upload':False,'image_scope':'main second-native observations plus selected third-repair evidence; no new visual review','opaque_boundary':'new ZIP/binaries metadata only; inherited small opaque ZIPs retain old scope'})
assert not [x for x in signals if x['signal_type']=='suspected_literal_secret_requires_context_review'],'Review candidate secret locations before staging; never print values'
put(V/'metadata-only.json',{'omissions':skipped,'large_dependency_policy':'No SDK/data file walks or hashes; no giant CSV rehash; producer receipt digests reused where provided; binary originals remain local'})
put(V/'pending.json',{'candidate':HEAD,'stage_complete':False,'slots':[{'scope':'third candidate 18c5858 configure/build/formal six profiles','status':'pending; running session27318 not touched; no unterminated result directory read as final'},{'scope':'third candidate real CI complete jobs/artifacts/gates','status':'pending Sagan independent collection'},{'scope':'third candidate native repair-scope observations at three DPRs','status':'pending; old 2901f42 native overall false retained'},{'scope':'final public/archive-to-tracked destination','status':'main after complete acceptance; no public upload; no blanket safety certification'}]})
objects={}
for x in entries:
 if x['archive_action'].startswith('copy_'):objects.setdefault(x['sha256'],x)
manifest={'schema':'j2_f8_additive_archive_snapshot_v3','source_root':str(R),'planning_head':HEAD,'historical_heads_not_rewritten':True,'frozen':True,'base_manifest_sha256':sha(A/'manifest-final.json'),'base_staging_seal_sha256':sha(OLD/'final-copy-receipt.json'),'entries':entries,'logical_copy_files':sum(x['archive_action'].startswith('copy_') for x in entries),'unique_objects':len(objects),'unique_object_bytes':sum(x['bytes'] for x in objects.values()),'not_stage_completion':True,'new_formal_results_pending':True,'public_upload':False}
put(V/'manifest.json',manifest)
print(json.dumps({'inventory':'frozen','entries':len(entries),'copy_files':manifest['logical_copy_files'],'objects':len(objects),'object_bytes':manifest['unique_object_bytes'],'strict_pairs':len(pairs),'new_signal_counts':dict(privacy)},ensure_ascii=False),flush=True)
# Copy objects; no hardlinks to originals or prior staging. Logical links only target this staging.
for h,x in objects.items():
 p=locators[x['logical_path']];dst=S/x['object'];dst.parent.mkdir(parents=True,exist_ok=True);st=p.stat();shutil.copyfile(p,dst);assert sha(dst)==h and p.stat().st_size==st.st_size and p.stat().st_mtime_ns==st.st_mtime_ns,('copy drift',x['source'])
for x in entries:
 if not x['archive_action'].startswith('copy_'):continue
 dst=S/x['logical_path'];dst.parent.mkdir(parents=True,exist_ok=True);assert not dst.exists();os.link(S/x['object'],dst)
for q in V.iterdir():
 if q.is_file():dst=S/'plan'/q.name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(q,dst)
assert subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True)==status_before
put(S/'copy-receipt.json',{'status':'copied_and_raw_SHA_verified','manifest_sha256':sha(V/'manifest.json'),'logical_files':manifest['logical_copy_files'],'unique_objects':len(objects),'unique_bytes':manifest['unique_object_bytes'],'old_staging_unmodified':True,'source_bytes_or_tracked_modified':False,'originals_removed':False,'upload':False,'stage_complete':False})
print(json.dumps({'stage':str(S),'status':'copy_verified','manifest_sha256':sha(V/'manifest.json')},ensure_ascii=False),flush=True)
