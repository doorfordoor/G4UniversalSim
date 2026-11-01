"""Create immutable OUT-only v3 after the reviewer's consolidated correction list."""
import difflib,hashlib,json,subprocess,datetime
from pathlib import Path
R=Path.cwd();B=R/'out/collab/j2-f8-third-doc-draft';P=B/'v2';O=B/'v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def writej(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
assert not O.exists(),'Do not overwrite frozen v3'
m=json.loads((P/'manifest.json').read_text());assert sha(P/'docs.patch')==m['docs_patch_sha256'];assert m['frozen']
original_v2={str(p.relative_to(P)):sha(p) for p in P.rglob('*') if p.is_file()}
changes=json.loads((B/'v3-confirmed-changes.json').read_text())
assert changes['reviewer_consolidated_confirmed'], 'Await consolidated reviewer feedback'
status_before=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True)
allowed_main={'gui/g4usim_gui/core/accessibility.py','gui/g4usim_gui/core/experiment_bundle.py','gui/g4usim_gui/widgets/run_history_page.py','gui/smoke_tests/smoke_f8_accessibility.py','gui/smoke_tests/smoke_j2_geometry.py','scripts/test_k1_bundle.py'}
assert {line[3:] for line in status_before.splitlines()}==allowed_main,status_before
main_before={n:sha(R/n) for n in allowed_main}
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==m['base_head']
O.mkdir();(O/'patches').mkdir();rows=[];patches=[];changed=[]
for row in m['files']:
 name=row['path'];src=R/name;assert sha(src)==row['original_sha256']
 raw=src.read_bytes();v2=(P/'proposed'/name).read_bytes();assert hashlib.sha256(v2).hexdigest()==row['candidate_sha256']
 data=v2
 for c in changes['changes']:
  if c['path']==name:
   a=c['before'].encode();b=c['after'].encode();assert data.count(a)==1,(name,c['before']);data=data.replace(a,b,1)
 if data!=v2:changed.append(name)
 dest=O/'proposed'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 before=raw.decode().replace('\r\n','\n');after=data.decode().replace('\r\n','\n')
 patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+name,tofile='b/'+name)).encode()
 (O/row['patch']).write_bytes(patch);patches.append(patch);rows.append(dict(row,candidate_sha256=sha(dest),bytes=len(data)))
 if name=='STATUS.md':assert before[before.index('## 一句话定位'):]==after[after.index('## 一句话定位'):]
 if name=='docs/agent-history.md':assert after.startswith(before)
(O/'docs.patch').write_bytes(b''.join(patches))
p=subprocess.run(['git','-c','core.longpaths=true','apply','--check',str(O/'docs.patch')],capture_output=True);(O/'apply-check.log').write_bytes(p.stdout+p.stderr);assert p.returncode==0,p.stderr
assert subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True)==status_before
assert all(sha(R/n)==h for n,h in main_before.items())
assert all(sha(P/k)==s for k,s in original_v2.items())
(O/'evidence-snapshot.json').write_bytes((B/'v3-evidence-snapshot.prepared.json').read_bytes())
writej(O/'corrections.json',changes)
v={'status':'pass','changed_proposals_from_v2':changed,'all_other_proposed_bytes_identical_to_v2':True,'nine_original_source_SHA_pins':True,'v2_all_files_unchanged':True,'history_prefix_and_STATUS_historical_tail_exact':True,'apply_check_exit':0,'tracked_before_after':'same six main-authorized code/test diffs; nine doc sources unchanged','main_authorized_diff_paths':sorted(allowed_main),'main_diff_SHA_before_after_unchanged':main_before,'tests_build_native_formal_commands_started_or_stopped':False,'unchanged_validation_inherited':'v2/validation.json; new corrections limited to listed prose identity replacements'}
writej(O/'validation.json',v)
n=dict(m,schema='j2_f8_third_candidate_docs_frozen_v3',files=rows,docs_patch_sha256=sha(O/'docs.patch'),docs_patch_bytes=(O/'docs.patch').stat().st_size,frozen=True,frozen_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),applied=False,previous_draft={'path':str(P.relative_to(R)).replace('\\','/'),'docs_patch_sha256':sha(P/'docs.patch'),'manifest_sha256':sha(P/'manifest.json'),'all_files_unchanged':True},corrections_sha256=sha(O/'corrections.json'),validation_sha256=sha(O/'validation.json'),facts_sha256=sha(O/'evidence-snapshot.json'),before_main_apply=['Nine doc source SHA pins and frozen v3 delta review must match','Six authorized main code/test diffs already applied; doc generator leaves them byte-identical','New candidate full formal/native/CI acceptance required; old failures retained'])
writej(O/'manifest.json',n)
(O/'README.md').write_bytes(('''# 第三候选九文件文档冻结 v3（仅OUT，未apply）

v2全目录原字节保留；本版仅合并corrections.json中经main及Feynman集中确认的身份措辞。正文面向统一应用提交后的契约，新候选完整验收待进行，阶段未关闭。本版快照已纳入2901f42六份本机终态passed：300/300、180992入口、local-final-audit errors=[]；旧CI失败保持。其余范围、历史保护、新链接及证据边界沿用v2。

冻结HEAD：`'''+m['base_head']+'`\n\ndocs.patch SHA256：`'+sha(O/'docs.patch')+'`\n\nmanifest.json SHA256：`'+sha(O/'manifest.json')+'`\n\nvalidation.json：9源SHA匹配，v2未改，非列出文件候选字节相同，STATUS历史tail及history原prefix保持，git apply --check退出0，九doc来源未改、六已授权main代码/测试diff前后字节不变。未apply，未启动或停止任何产品测试/build/native/正式命令。\n').encode())
print(json.dumps({'directory':str(O),'patch_SHA':sha(O/'docs.patch'),'manifest_SHA':sha(O/'manifest.json'),'patch_bytes':(O/'docs.patch').stat().st_size,'changed_files':changed},ensure_ascii=False))
