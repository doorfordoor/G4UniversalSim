"""Freeze four OUT-only docs after six terminal receipts; no product/test execution."""
import datetime,difflib,hashlib,importlib.util,json,re,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
R=Path.cwd();B=R/'out/collab/j2-f8-fourth-doc-draft';O=B/'frozen-v1';assert not O.exists();O.mkdir();(O/'proposed').mkdir();(O/'patches').mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();j=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def put(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
HEAD='18c5858fd6e80a5cb6096beacebfef69c479ad49';assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD
allowed={'gui/smoke_tests/smoke_j2_geometry.py':'b3fefeac58f044c99021d1caf7812fd66c8fe41bd14fb94ebcf8facf0c1cb6bd','gui/smoke_tests/smoke_f8_accessibility.py':'5f234e69c00d602039cb8f2ebc7daadb4f69edc860e6010989628d06253b3814'}
def status():
 st=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True);assert {x[3:] for x in st.splitlines()}.issubset(allowed),st
 for n,h in allowed.items():assert sha(R/n)==h,(n,'main applied candidate mismatch')
 return st
before_status=status();initial=j(B/'manifest.draft.json');old_draft_pins={x['path']:x for x in initial['files']};raw_initial_pins={p.relative_to(B).as_posix():sha(p) for p in B.rglob('*') if p.is_file() and O not in p.parents}
root=R/'out/verification/j2-f8-18c5858';audit_path=root/'local-final-audit.json';audit=j(audit_path);assert sha(audit_path)=='bff2dd04d5143d33687b08a85ba80f68707d4297b6955e67cc50c640cbd51113';assert audit['head']==HEAD and audit['status']=='passed' and audit['errors']==[]
checker_path=R/'out/collab/j2-f8-final-local-audit-18c5858.py';assert sha(checker_path)=='ac0528c6b93adf74c4576598513cfb11ab19238580a608368660bac62c4c33ce'
sp=importlib.util.spec_from_file_location('_docs_receipt_log_locator',R/'scripts/check_report_evidence.py');ck=importlib.util.module_from_spec(sp);sp.loader.exec_module(ck)
profiles=[];facts_rows=[];total=0;assertions=0;log_count=0
for name,x in audit['profiles'].items():
 p=R/Path(x['report']);assert sha(p)==x['report_sha256'];lpath=p.parent.parent/'launch.json';assert sha(lpath)==x['launch_sha256'];l=j(lpath);r=j(p)
 assert l['status']=='passed' and l['runner_exit_code']==l['gate_exit_code']==0 and l['identity_errors']==[] and l['ending']['head']==HEAD
 assert r['git_head']==HEAD and not r['git_dirty'] and r['git_status_porcelain']=='' and r['assert_probe']=='settrace_assert_lines_v3';assert r['source_fingerprint']=='9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a';assert r['tests_content_fingerprint']=='d5a1691bb3ed613faae4db96405167c0f7ea0a35aa465444e2d260a36a7e67a9'
 assert len(r['results'])==x['cases'] and sum(c['assertions_executed'] for c in r['results'])==r['assertions_executed_total']==x['assertions'] and all(c['status']=='pass' for c in r['results'])
 for c in r['results']:
  q=ck.resolve_log(c,p);assert q and sha(q)==c['log_sha256'];log_count+=1
 total+=x['cases'];assertions+=x['assertions'];profiles.append(dict(profile=name,**x));facts_rows.append({'profile':name,'cases':x['cases'],'assertions':x['assertions'],'report_sha256':sha(p),'launch_sha256':sha(lpath),'git_head':r['git_head'],'git_dirty':r['git_dirty'],'runner':0,'gate':0,'identity_errors':[]})
assert total==audit['cases']==300 and assertions==audit['assertions']==181295 and log_count==300
geom=R/'out/collab/j2-geometry-path-independent/receipt.json';assert j(geom)['passed'] and j(geom)['candidate_sha256']==allowed['gui/smoke_tests/smoke_j2_geometry.py']
f8=R/'out/collab/f8-linux-name-independent';assert all(j(f8/n)['passed'] for n in ['windows-receipt.json','linux-receipt.json','static-receipt.json']);assert all(j(f8/n)['candidate_sha256']==allowed['gui/smoke_tests/smoke_f8_accessibility.py'] for n in ['windows-receipt.json','linux-receipt.json'])
ci=j(root/'ci/collected-files-final.json');g=j(root/'ci/report-gates-current.json');assert ci['workflow_completion']=='all_completed' and g['strict_pass']==g['strict_fail']==4 and g['release_accepted'] is False
mp=R/'out/collab/f8-linux-qt-name-18c5858/product-gui-byte-map.json';mapping=j(mp);assert mapping['gui_count']==len(mapping['gui_files'])==149
for name,h in mapping['gui_files'].items():assert sha(R/name)==h,name
for k,x in mapping['native_identity_references'].items():assert sha(R/x['identity_path'])==x['identity_sha256']
# Existing18c source-byte observation only; future committed-HEAD map remains pending.
put(O/'evidence-snapshot.json',{'base_head':HEAD,'snapshot_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'aggregate':audit,'aggregate_sha256':sha(audit_path),'frozen_audit_checker_sha256':sha(checker_path),'independent_receipt_checks':facts_rows,'raw_case_logs_SHA_verified':log_count,'geometry_independent_receipt_sha256':sha(geom),'F8_independent':{n:sha(f8/n) for n in ['windows-receipt.json','linux-receipt.json','static-receipt.json','review.md']},'applied_test_candidates':allowed,'existing18c_GUI149_map_sha256':sha(mp),'existing18c_current149_all_match':True,'future_newHEAD_final_mapping':'pending after tests+docs commit; not a docs freeze prerequisite','additional_representative_native':'pending after fourth GUI terminal;100/125 chosen by main; I1/I2 open cancel + Import existing offline package +template Finish/reenter Back/Esc; separate newHEAD/build','CI_runs':ci['runs'],'CI_strict_pass':4,'CI_strict_fail':4,'CI_release_accepted':False,'main_scope_sha256':sha(R/'out/collab/j2-f8-18c5858-main-acceptance-scope.md'),'product_formal_native_or_CI_execution_by_doc_preparer':False})
repls={
'STATUS.md':[
('**阶段仍未关闭，完整新候选验收待进行。**','**第四修复候选，两项test-only专项独审已完成；阶段仍未关闭，完整新候选验收待进行。**'),
('| windows113-integration | ⟦终态收据待补⟧ | ⟦待补⟧ | ⟦待补⟧ |','| windows113-integration | 31/31 | 6790 | 0 / 0 / [] |'),
('| windows114-integration | ⟦终态收据待补⟧ | ⟦待补⟧ | ⟦待补⟧ |','| windows114-integration | 31/31 | 6780 | 0 / 0 / [] |'),
('六profile合计：⟦待两integration终态后逐项算术及原SHA核对；不以目录存在推断完成⟧。上述四份已终态报告的identity_errors=[]、git_dirty=false。','18c六profile均已终态passed，合计300/300、181295入口；local-final-audit的status=passed、errors=[]，六份原report/launch SHA及逐项算术已核对。六份原报告的identity_errors=[]、git_dirty=false；这些是18c冻结的本机结果，不替代第四候选新CI或阶段验收。'),
('Qt Unix ComboBox的QAccessible.Name反映currentText，标签由Label关系表达；测试应验证真实角色接口、明确buddy/关联标签和语言切换，并用丢buddy负向防止放宽；不为测试改正确产品。专项独审：⟦两项最终独审收据待齐⟧。','Qt6.11.1/6.11.3官方Combo实现的Unix分支解释了本轮Linux Name/currentText行为，Windows Name仍为标签；语义标签由实际Label关系表达，空文本依Qt回退。测试在本次Windows/Linux目标上严格核对角色、真实interface.object、Name/Value、确切Label/buddy及动态语言；丢buddy、同文异label、错误control接口三类负向在两端各9次均须拒绝，不推广为macOS/所有Unix验收。两项test-only专项独审均PASS；Linux作者完整655绿例与独立微Qt检查分开，不为测试改正确产品。'),
('149项GUI产品字节及C++源码若与18c冻结身份精确一致，新test-only候选可沿用这些限定原生范围；身份映射仍须显式核对，不虚构新增操作，不无端重复同范围，但**新候选完整真实CI仍必须**。','现有18c149项GUI逐文件映射及三档原identity已核对，C++源码指纹仍按18c冻结报告记录；这只是原身份的相同产品字节证据。两test与本文档提交得到新HEAD后，最终产品/C++身份映射仍为pending，完成后才能按原限定scope映射，不虚构新增操作或重复三档；**新候选完整真实CI仍必须**。'),
('F6无法容纳完整joint的窄dock边界不在本修复内，不扩大物理/跨屏/热插拔结论。','第四候选GUI终态后还计划补一轮100%或125%代表性native，覆盖I1/I2打开取消、Import已有offline包、template Finish后再次重入Back/Esc；该项为pending，按届时新HEAD/build独立记录，不提前算作旧三档覆盖，也不作为本文档冻结前置。F6无法容纳完整joint的窄dock边界不在本修复内，不扩大物理/跨屏/热插拔结论。')],
'docs/ROADMAP.md':[
('专项独审及六profile算术待齐，完整新候选验收待进行、阶段未关闭','两项专项独审已PASS；18c本机300/181295，原CI4pass/4fail保留；未来HEAD映射及单轮补native pending，完整新候选验收待进行、阶段未关闭'),
('同产品原生范围须精确身份映射，新候选完整CI仍必须','两test专项独审已PASS；18c六profile300/181295，未来HEAD原生身份映射及单轮补验pending，新候选完整CI仍必须')],
'docs/agent-history.md':[
('18c六份本机合计⟦待两integration终态及独立算术⟧，两项test-only最终独审⟦待齐⟧；不得用这些未齐字段宣告阶段完成。','18c六份本机均已终态passed，合计300/300、181295入口，原report/launch SHA及算术核对通过，local-final-audit的errors=[]。两项test-only专项独审均已PASS，仍不宣告阶段完成。'),
('Qt Unix ComboBox Name=currentText而Label关系表达标签，测试按真实角色接口、明确buddy/关联标签及动态语言检查，且丢buddy必须失败；不通过改正确产品或删除关联判据迁就平台。','Qt6.11.1/6.11.3的Unix Combo实现说明本轮Linux Name使用currentText（空字符串走Qt回退），Windows Name仍为标签；语义标签由实际Label关系表达。测试仅按本轮Windows/Linux真实provider严格验证Name/Value、Role、interface.object、确切Label/buddy及动态语言，不将其泛化为macOS/所有Unix验收。两端各三类9负向（丢buddy、同文本异label、错误control接口）都拒绝；原property/buddy、F5/完整joint/滚动与spacer断言保留。作者Linux完整655不冒充独审全量重跑，不改正确产品。'),
('18c产品149GUI及C++字节完全一致时，新test-only冻结可明确映射原18c三档限定原生scope，不伪称新执行、完整视觉或物理基准；新完整真实CI仍须通过。','现有18c149GUI逐文件/三identity映射已经核对，C++源码指纹按原18c报告保留；新HEAD必须在两test与docs提交后才产生，最终产品/C++映射仍pending，完成后才能映射原三档限定scope，不是docs冻结前置，不伪称新执行、完整视觉或物理基准；新完整真实CI仍须通过。'),
('原trace/失败/缓存读数局限均保留；正文不引用未归档OUT为公共链接。','第四候选GUI终态后补一轮100/125择一的代表性native（I1/I2打开取消、Import已有offline包、template Finish及重入Back/Esc）仍pending，须按新HEAD/build单独记录，不扩大原18c三档范围、不重做三档，也不是docs冻结前置。原trace/失败/缓存读数局限均保留；正文不引用未归档OUT为公共链接。')],
'docs/J2编辑覆盖与F8验收.md':[
('Unix ComboBox按Name/currentText与Label关系验证，buddy负向不得缺失。两项独审及六profile算术⟦待最终收据⟧，新完整CI仍必须。','本轮Windows/Linux ComboBox按各实际Name/currentText及Label关系验证，确切buddy/标签/接口负向不得缺失，不推广为所有Unix/macOS。两项test-only专项独审均PASS；18c六profile已passed300/300、181295入口且原SHA/算术核对通过，原真实CI4pass/4fail保留，新完整CI仍必须。'),
('18c三档原生只在产品149GUI/C++精确同字节时映射其原限定scope；','现有18c149GUI原字节映射已核对；两test与docs提交新HEAD后最终产品/C++映射仍pending，只能在精确同字节后映射旧三档原限定scope，不是docs冻结前置；'),
('QQ原图不入公开raw包。','QQ原图不入公开raw包。第四候选GUI终态后计划100/125择一补I1/I2打开取消、Import已有offline包及template Finish后重入Back/Esc，仍pending、按新HEAD/build独立记录，不扩写旧三档覆盖，也不是docs冻结前置。')]
}
records=[];diffs=[];newlinks=[];deleted=[]
for name,changes in repls.items():
 raw=(R/name).read_bytes();assert sha(R/name)==old_draft_pins[name]['original_sha256'];old_raw=(B/'proposed'/name).read_bytes();assert sha(B/'proposed'/name)==old_draft_pins[name]['proposed_sha256'];bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'';before=raw[len(bom):].decode().replace('\r\n','\n');after=old_raw[len(bom):].decode().replace('\r\n','\n')
 for old,new in changes:assert after.count(old)==1,(name,old);after=after.replace(old,new,1)
 assert '⟦' not in after and '⟧' not in after,name
 nl='\r\n' if b'\r\n' in raw and b'\n' not in raw.replace(b'\r\n',b'') else '\n';data=bom+after.replace('\n',nl).encode();dest=O/'proposed'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 diff=''.join(difflib.unified_diff((('\ufeff' if bom else '')+before).splitlines(True),(('\ufeff' if bom else '')+after).splitlines(True),fromfile='a/'+name,tofile='b/'+name));pp='patches/'+name.replace('/','__')+'.patch';(O/pp).write_bytes(diff.encode());diffs.append(diff)
 added=[l[1:] for l in diff.splitlines() if l.startswith('+') and not l.startswith('+++')];deleted.extend({'file':name,'text':l[1:]} for l in diff.splitlines() if l.startswith('-') and not l.startswith('---'))
 for line in added:
  assert line==line.rstrip();assert not any(z in line for z in ['待统一应用','⟦','专项独审及六profile算术待齐','两项最终独审收据待齐'])
  for target in re.findall(r'\]\(([^)]+)\)',line):
   z=target.split('#')[0].strip('<>');assert not z.startswith('out/')
   if z and not re.match(r'[a-z]+:',z):assert ((R/name).parent/z).resolve().exists();newlinks.append({'file':name,'target':target,'exists':True})
 if name=='STATUS.md':
  start=after.index('## 2026-11-02 J2/F8 当前实施');end=after.index('</details>\n\n## 一句话定位');assert after[start:end]==before[before.index('## 2026-11-02 J2/F8 当前实施'):before.index('## 一句话定位')]
  assert after[after.index('## 一句话定位'):]==before[before.index('## 一句话定位'):]
 if name=='docs/agent-history.md':assert data.startswith(raw)
 if name=='docs/J2编辑覆盖与F8验收.md':assert after[after.index('## 从空白开始'):]==before[before.index('## 从空白开始'):]
 records.append({'path':name,'original_sha256':sha(R/name),'candidate_sha256':sha(dest),'bytes':len(data),'patch':pp,'BOM_preserved':bool(bom),'line_endings':'CRLF' if nl=='\r\n' else 'LF'})
patch=''.join(diffs).encode();(O/'docs.patch').write_bytes(patch)
p=subprocess.run(['git','-c','core.longpaths=true','apply','--check',str(O/'docs.patch')],capture_output=True);(O/'apply-check.log').write_bytes(p.stdout+p.stderr);assert p.returncode==0,p.stderr
assert all(sha(B/k)==v for k,v in raw_initial_pins.items());after_status=status();assert all(sha(R/x['path'])==x['original_sha256'] for x in records)
put(O/'validation.json',{'status':'pass','source_docs4_SHA_unchanged':True,'initial_draft_all_bytes_unchanged':True,'STATUS_old_current_snapshot_and_dated_tail_exact':True,'agent_history_entire_original_raw_prefix_exact':True,'J2_usage_body_exact_after_blank_start_heading':True,'ROADMAP_only_two_current_status_rows':True,'new_links_checked':newlinks,'deleted_lines':deleted,'no_placeholder_or_stale_review_gate':True,'apply_check_exit':p.returncode,'tracked_expected_main_changes_before':before_status,'tracked_expected_main_changes_after':after_status,'only_two_reviewed_test_diffs_allowed':allowed,'no_product_native_or_formal_execution':True,'futureHEAD_map_not_freeze_gate':True,'additional_native_not_freeze_gate':True})
manifest={'schema':'j2_f8_fourth_candidate_docs_frozen_v1','frozen':True,'applied':False,'stage_complete':False,'base_head':HEAD,'files':records,'docs_patch_sha256':sha(O/'docs.patch'),'docs_patch_bytes':len(patch),'evidence_snapshot_sha256':sha(O/'evidence-snapshot.json'),'validation_sha256':sha(O/'validation.json'),'native_existing_scope_only':True,'futureHEAD_mapping':'pending after tests+docs commit; not a docs freeze prerequisite','representative_new_native':'pending after new GUI terminal; not a docs freeze prerequisite','new_candidate_HEAD':None,'new_CI_success':False,'original_18c_six_profile_sum':{'cases':total,'assertions':assertions,'errors':[]},'historical_policy':'All old dated history exact; STATUS older current section wrapped unchanged as historical; history append-only; ROADMAP only2 current rows; J2 only active intro/history label','public_evidence_links':'No new unarchived OUT Markdown public links; raw QQ images excluded','apply_policy':'Main apply only after Feynman narrow review; verify exact proposed bytes after apply to catch core.autocrlf conversions'}
put(O/'manifest.json',manifest)
readme=f'''# 第四候选四文件文档冻结 v1（仅OUT，未apply）

frozen=true，base HEAD `{HEAD}`。两项test-only独审已PASS；18c六份正式报告实际300/300、181295、aggregate errors=[]。audit SHA `{sha(audit_path)}`，冻结checker SHA `{sha(checker_path)}`。逐report/launch原SHA、HEAD、tracked-clean原报告、300原log SHA与算术已独立读取核对；未重跑产品/native/profile。

仅STATUS、ROADMAP、agent-history、J2/F8验收页四文件，另外五页不做无意义同步。旧初稿所有字节保留。STATUS旧实施快照及后方历史精确保留，history整原文raw-prefix保持；ROADMAP仅2当前行，J2使用正文保持。正文面向两test+docs本次提交后契约，相关独审完成而新完整CI/验收待进行，不写待统一应用。18c旧CI4pass/4fail不改绿；三档native按原身份和限定scope，86 QQ图raw只本机，公开metadata/观察文字。

未来HEAD最终映射必须在两test+docs提交后执行，正文写pending，不是本docs冻结前置。现有18c149GUI/三identity核对可如实记录。新增代表性native100/125择一，在新GUI终态后补I1/I2打开取消、Import已有包、template Finish/重入Back/Esc，仍pending、新HEAD/build独立，不扩旧三档，不重复三档；阶段关闭另做。

docs.patch SHA256：`{sha(O/'docs.patch')}`，{len(patch)} bytes。
manifest.json SHA256：`{sha(O/'manifest.json')}`。

read-only git apply --check退出0；四doc来源SHA未改，仅main两份已审test diff允许存在且SHA精确。未写tracked。main应用后仍须核proposed原字节，避免autocrlf造成LF转CRLF。请Feynman仅窄审文档scope/历史/链接/证据身份与边界；不重跑产品/native。
'''
(O/'README.md').write_bytes(readme.encode());print(json.dumps({'directory':str(O),'patch_sha256':sha(O/'docs.patch'),'manifest_sha256':sha(O/'manifest.json'),'patch_bytes':len(patch),'files':len(records),'actual_sum':[total,assertions],'tracked_changes':'only2 reviewed tests; docs unchanged','validation':'pass'},ensure_ascii=False))
