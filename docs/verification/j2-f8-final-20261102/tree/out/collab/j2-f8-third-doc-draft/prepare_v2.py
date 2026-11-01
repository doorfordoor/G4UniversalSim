import difflib,hashlib,json,re,subprocess,datetime
from pathlib import Path
R=Path.cwd(); B=R/'out/collab/j2-f8-third-doc-draft'; O=B/'v2'
assert not O.exists(), 'v2 already exists; do not overwrite frozen artifact'
O.mkdir(); (O/'proposed').mkdir(); (O/'patches').mkdir()
def sha(b): return hashlib.sha256(b).hexdigest()
def js(p,x): p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
m=json.loads((B/'manifest.json').read_text()); assert sha((B/'docs.patch').read_bytes())==m['docs_patch_sha256']
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(); assert head==m['base_head']
status=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True); assert not status.strip(), status
frozen_old={str(p.relative_to(B)):sha(p.read_bytes()) for p in B.rglob('*') if p.is_file() and O not in p.parents}
# Only replace exact new draft passages; historical source is never edited.
replacements={
'STATUS.md':[
('**阶段未关闭，正在准备第三修复候选。**','**第三修复候选，相关专项独审已完成，完整新候选验收待进行；阶段未关闭。**'),
('第三修复尚须统一应用、生成新提交及完整复验，不能把专项或本机通过改写成整阶段验收。','本候选包含下述已审修复，仍须以新提交身份完成完整复验，不能把专项或本机通过改写成整阶段验收。'),
('第三修复准备包括History三显式buddy及动态语言名称、仅真实QLayout的递归兼容、geometry路径测试精确resolve/samefile比较（不改geometry产品）；History+spacer组合595专项已独审，尚不替代新candidate的CI/原生。','第三修复候选包含History三显式buddy及动态语言名称、仅真实QLayout的递归兼容、geometry路径测试精确resolve/samefile比较（不改geometry产品）；History、spacer及STL专项独审均通过，History+spacer组合595专项亦已独审，尚不替代新candidate的CI/原生。'),
('K1 final-v1 policy规范身份及原拼写首尾guard已有冻结候选，**独审与新candidate复验仍待完成**，不提前判闭合。','K1 final-v1 policy规范身份及原拼写首尾guard专项独审已通过603入口／13组，原短路径30入口及junction 3+5反例保留；**完整新候选验收待进行**，专项关闭不等于CI或阶段关闭。')],
'docs/ROADMAP.md':[
('2026-11-02 第三修复候选准备，阶段未关闭；','2026-11-02 第三修复候选，相关专项独审已完成，完整新候选验收待进行；'),
('**2026-11-02 第三修复候选准备，未验收**','**2026-11-02 第三修复候选，相关专项独审已完成，完整新候选验收待进行**'),
('新增K1 policy契约候选尚待独审/新candidate全复验','K1 policy final-v1专项独审已通过603入口，完整新candidate验收仍待进行')],
'AGENTS.md':[
('J2/F8第三修复候选准备：','J2/F8第三修复候选：相关专项独审已完成，完整新候选验收待进行；')],
'gui/AGENTS.md':[
('J2/F8第三修复候选准备：','J2/F8第三修复候选：相关专项独审已完成，完整新候选验收待进行；'),
('K1 policy最终候选需先独审再统一应用，','K1 policy final-v1专项独审已通过603入口，完整新候选验收仍待进行；')],
'docs/agent-history.md':[
('## 2026-11-02 J2/F8 第三修复候选准备（阶段未关闭）','## 2026-11-02 J2/F8 第三修复候选（专项独审完成，阶段未关闭）'),
('第三修复统一应用前，main须确认本轮六份本机报告全部终态；新candidate仍需新提交、必要构建身份、同版本/同profile/v3历史strict门禁、真实CI和原生复验。','第三修复候选包含下述已审产品及测试修复；截至文档快照，113 integration已通过31/31、6790入口及gate0，114 integration仍运行中。完整新候选验收待进行，仍须以新提交及必要构建身份完成同版本/同profile/v3历史strict门禁、真实CI和原生复验。'),
('History候选只为','History修复只为'),
('QLayout兼容候选须先判','QLayout兼容修复先判'),
('两产品和组合595专项独审不能冒充已应用或新候选CI/native通过。','两产品及组合595专项独审均已通过，仍不能冒充新候选CI/native通过。'),
('K1 final-v1候选以','K1 final-v1修复以'),
('该final-v1补丁f705dc96及其产品4990d9f4/测试80726fb8已有作者收据，独审与新candidate全复验仍待完成，正文不宣告其已闭合。','该final-v1补丁f705dc96及其产品4990d9f4/测试80726fb8专项独审已通过：完整603入口／13组、原短路径30入口、真实junction 3+5。该专项已闭合，完整新candidate验收仍待进行，不能据此将旧CI或阶段改为通过。'),
('几何STL file路径回归只做','几何STL file路径回归专项独审已通过；该测试只做')],
'docs/J2编辑覆盖与F8验收.md':[
('当前为实施候选，正式状态见','当前为第三修复候选，相关专项独审已完成，完整新候选验收待进行；正式状态见'),
('当前正在准备第三修复候选，J2/F8阶段仍未关闭。','第三修复候选包含已审History、spacer、STL路径测试与K1 policy修复，J2/F8阶段仍未关闭。'),
('第三修复的独审/新candidate完整复验仍待完成。','113 integration已通过31/31、6790入口及gate0；114 integration在本快照仍运行中，完整新candidate验收待进行。')],
'gui/docs/中文快速使用说明.md':[
('第三修复候选准备中，阶段未关闭。已审History标签关联／语言切换及布局spacer兼容仍待统一应用和复验；','第三修复候选，相关专项独审已完成，完整新候选验收待进行，阶段未关闭。本候选包含History标签关联／语言切换及布局spacer兼容修复；')],
'docs/功能支持矩阵.md':[
('当前准备第三修复候选，阶段状态未关闭：','当前为第三修复候选，相关专项独审已完成，完整新候选验收待进行，阶段状态未关闭：'),
('History／真实QLayout修复已专项独审，K1 policy最终候选待独审及新candidate全复验','History／真实QLayout、STL路径测试及K1 policy final-v1修复专项独审均通过；完整新candidate验收待进行')],
'docs/开发路线图.md':[
('正准备J2/F8第三修复候选','J2/F8第三修复候选，相关专项独审已完成，完整新候选验收待进行'),
('History／QLayout组合已专项独审，K1 policy终稿待独审和新candidate完整复验。','History／QLayout组合、STL路径测试与K1 policy final-v1专项独审已通过；完整新candidate验收仍待进行。')]
}
records=[]; patches=[]; added=[]; deleted=[]; link_checks=[]
for row in m['files']:
 name=row['path']; raw=(R/name).read_bytes(); assert sha(raw)==row['original_sha256'],name
 v1raw=(B/'proposed'/name).read_bytes(); assert sha(v1raw)==row['candidate_sha256'],name
 bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
 before=raw[len(bom):].decode().replace('\r\n','\n'); after=v1raw[len(bom):].decode().replace('\r\n','\n')
 # For history, operate only on appended suffix and preserve the full original prefix.
 if name=='docs/agent-history.md':
  assert after.startswith(before.rstrip()); prefix=before; work=after[len(before.rstrip()):]; work='\n'+work.lstrip('\n')
 else: prefix='';work=after
 for a,b in replacements[name]:
  assert work.count(a)==1,(name,a,work.count(a)); work=work.replace(a,b,1)
 after=prefix+work
 if name=='STATUS.md': assert before[before.index('## 一句话定位'):]==after[after.index('## 一句话定位'):]
 if name=='docs/agent-history.md': assert after.startswith(before)
 newline='\r\n' if b'\r\n' in raw and b'\n' not in raw.replace(b'\r\n',b'') else '\n'
 data=bom+after.replace('\n',newline).encode();dest=O/'proposed'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 patch=''.join(difflib.unified_diff((('\ufeff' if bom else '')+before).splitlines(True),(('\ufeff' if bom else '')+after).splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 pp='patches/'+name.replace('/','__')+'.patch';(O/pp).write_bytes(patch.encode());patches.append(patch)
 ins=[l[1:] for l in patch.splitlines() if l.startswith('+') and not l.startswith('+++')];dels=[l[1:] for l in patch.splitlines() if l.startswith('-') and not l.startswith('---')]
 added.extend((name,l) for l in ins); deleted.extend((name,l) for l in dels)
 for l in ins:
  assert l==l.rstrip(),(name,'trailing whitespace')
  assert not any(x in l for x in ['待统一应用','独审待完成','独审与新candidate复验仍待完成','需先独审','待独审','正在准备第三','第三修复候选准备']), (name,l)
  for target in re.findall(r'\]\(([^)]+)\)',l):
   target=target.split('#')[0].strip('<>');assert not target.startswith('out/'),(name,target)
   if target and not re.match(r'[a-z]+:',target):
    found=((R/name).parent/target).resolve(); assert found.exists(),(name,target);link_checks.append({'file':name,'target':target,'exists':True})
 records.append(dict(row,candidate_sha256=sha(data),bytes=len(data),patch=pp))
patch_bytes=''.join(patches).encode();(O/'docs.patch').write_bytes(patch_bytes)
# Read-only git applicability check. Never invokes apply without --check.
p=subprocess.run(['git','-c','core.longpaths=true','apply','--check',str(O/'docs.patch')],capture_output=True)
(O/'apply-check.log').write_bytes(p.stdout+p.stderr); assert p.returncode==0,(p.returncode,p.stderr.decode(errors='replace'))
assert not subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True).strip()
assert all(sha((B/k).read_bytes())==v for k,v in frozen_old.items())
evidence=json.loads((B/'evidence-snapshot.json').read_text());evidence['snapshot_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();evidence['local_profile_snapshot_policy']='Original v1 snapshot retained: five profiles passed; windows114-integration explicitly running per main at freeze; do not wait/rewrite historical report.'
review=R/'out/collab/j2-policy-final-v1-independent';ex=json.loads((review/'execution.json').read_text());assert ex['status']=='pass'
evidence['policy_independent_review']={'status':'pass','execution':'out/collab/j2-policy-final-v1-independent/execution.json','sha256':sha((review/'execution.json').read_bytes()),'review':'out/collab/j2-policy-final-v1-independent/review.md','review_sha256':sha((review/'review.md').read_bytes()),'full_assertions':603,'groups':13,'original_short_path_assertions':30,'junction_groups':[3,5]}
evidence['STL_review']={'status':'pass','source':'main explicitly confirmed accepted independent review; exact resolve/samefile test-only; no product semantics changes'}
js(O/'evidence-snapshot.json',evidence)
validation={'status':'pass','source_head':head,'tracked_status_before':'clean','tracked_status_after':'clean','original_9_SHA_pins':True,'v1_artifacts_unchanged':True,'status_historical_tail_exact':True,'agent_history_original_full_prefix_exact':True,'new_lines_no_stale_pending_apply_review_phrases':True,'new_link_checks':link_checks,'patch_apply_check_exit':p.returncode,'added_lines':len(added),'deleted_lines':len(deleted),'deleted_lines_for_narrow_review':[{'path':n,'text':l} for n,l in deleted],'no_product_tests_build_native_or_formal_commands_started':True}
js(O/'validation.json',validation)
manifest=dict(m,schema='j2_f8_third_candidate_docs_frozen_v2',files=records,docs_patch_sha256=sha(patch_bytes),docs_patch_bytes=len(patch_bytes),frozen=True,frozen_at_utc=evidence['snapshot_utc'],applied=False,stage_completed=False,previous_draft={'path':str(B.relative_to(R)).replace('\\','/'),'docs_patch_sha256':m['docs_patch_sha256'],'unchanged':True},before_main_apply=['Read-only narrow documentation review; source SHA pins must still match','114 integration explicitly pending at snapshot; no need to wait for documentation freeze','New candidate complete formal/native/CI acceptance required; old failures stay failed'],validation_sha256=sha((O/'validation.json').read_bytes()),facts_sha256=sha((O/'evidence-snapshot.json').read_bytes()))
js(O/'manifest.json',manifest)
readme=f'''# J2/F8 第三候选九文件文档冻结 v2（仅 OUT）

冻结标记：`frozen=true`，不是以 stage_completed=false 代替冻结。尚未 apply；未改 tracked，未启动/停止正式命令、产品测试、构建或 native。

- 基线 HEAD：`{head}`，九文件原字节 SHA 均匹配，前后 tracked clean。
- docs.patch：`{sha(patch_bytes)}`，{len(patch_bytes)} bytes。
- manifest.json：`{sha((O/'manifest.json').read_bytes())}`。
- 旧初稿及7b90cae3补丁原字节保留，v2不覆盖原版。

正文按与产品一起应用提交后的第三修复候选描述；History/spacer/STL/K1专项独审均完成，K1完整603入口/13组，113 integration31/6790/gate0；114仍运行中是本快照事实，不阻塞文档冻结，也不承诺其终态。五份本机通过与四份CI原终态各按原身份，旧失败不改绿。新candidate完整验收、三档新repair相关原生范围及阶段关闭仍待进行。

范围固定为manifest列出的九个Markdown文件。STATUS只替换当前段；agent-history严格追加且保留原全文前缀；其余添加当前说明并仅最小更新当前ROADMAP行、J2页首及schema v8句，有日期的旧段不重写。没有未归档OUT公共链接，没有提高物理支持等级。K1写明原拼写no_links先于resolve、规范身份重复/未用拒绝和collect/export末端复核；不承诺任意并发替换安全。原生2901f42开放项按原快照保留，已审修复不冒充新候选通过。

validation.json记录九SHA、历史保护、新链接、空白及git apply --check只读通过；未apply。Feynman只需审范围/历史/链接/新契约错误边界/证据不过度结论，不重跑产品或native。若需修改保留本版并另起v3。
'''
(O/'README.md').write_bytes(readme.encode())
print(json.dumps({'frozen_directory':str(O),'docs_patch_sha256':sha(patch_bytes),'manifest_sha256':sha((O/'manifest.json').read_bytes()),'files':len(records),'patch_bytes':len(patch_bytes),'validation':'pass','tracked':'clean'},ensure_ascii=False))
