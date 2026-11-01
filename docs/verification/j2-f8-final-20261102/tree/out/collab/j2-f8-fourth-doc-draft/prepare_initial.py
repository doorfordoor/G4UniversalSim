"""Prepare four-file OUT draft; never freeze/apply before receipts are complete."""
import difflib,hashlib,json,subprocess
from pathlib import Path
R=Path.cwd();O=R/'out/collab/j2-f8-fourth-doc-draft';assert not O.exists();O.mkdir();(O/'proposed').mkdir();(O/'patches').mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert HEAD=='18c5858fd6e80a5cb6096beacebfef69c479ad49';status=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True);assert not status.strip()
B=R/'out/verification/j2-f8-18c5858';profiles=[]
for name in ['windows-static','windows-gui','windows113-backend','windows114-backend']:
 lp=B/name/'launch.json';l=json.loads(lp.read_text());assert l['status']=='passed' and l['runner_exit_code']==l['gate_exit_code']==0 and l['identity_errors']==[];p=Path(l['report']);r=json.loads(p.read_text());assert sha(p)==l['report_sha256'] and not r['git_dirty'];profiles.append({'profile':name,'cases':len(r['results']),'assertions':r['assertions_executed_total'],'report':p.relative_to(R).as_posix(),'report_sha256':sha(p),'launch_sha256':sha(lp)})
table='\n'.join('| '+x['profile']+' | '+str(x['cases'])+'/'+str(x['cases'])+' | '+str(x['assertions'])+' | 0 / 0 / [] |' for x in profiles)
notice='''## 2026-11-02 第四修复候选：18c5858证据快照

**阶段仍未关闭，完整新候选验收待进行。** 第三冻结为 `18c5858fd6e80a5cb6096beacebfef69c479ad49`。本段只登记该身份的Windows、真实CI和原生范围；第四候选针对两个测试平台断言修订，不预写尚不存在的新HEAD、新CI成功或新增运行事实。

| 18c5858本机profile | 通过/用例 | v3入口 | runner / strict / identity_errors |
| --- | ---: | ---: | --- |
TABLE
| windows113-integration | ⟦终态收据待补⟧ | ⟦待补⟧ | ⟦待补⟧ |
| windows114-integration | ⟦终态收据待补⟧ | ⟦待补⟧ | ⟦待补⟧ |

六profile合计：⟦待两integration终态后逐项算术及原SHA核对；不以目录存在推断完成⟧。上述四份已终态报告的identity_errors=[]、git_dirty=false。证据根文字为 `out/verification/j2-f8-18c5858/`，不把未归档OUT作为公共链接。

18c5858四项push/attempt1 CI均终态：Linux Geant4 `41344573528` 与M0 `41344573541`失败，Desktop `41344573534`与Full installation `41344573604`成功；八份profile报告strict4pass/4fail，release_accepted=false。Linux114、113及M0 Ubuntu各仅gui_f8_accessibility在659行QAccessible.Name断言失败；Windows M0另仅gui_j2_geometry在264行成功reload后的source_path字面相等断言失败（195入口），不是上一轮STL162。Linuxbackend/integration因上游GUI失败未执行，不能记为通过。首败、全部原log/ZIP及旧身份保持，专项归因或入口数增加不把原CI改绿。

两项修订只针对真实接口：成功Reload保存resolve后的规范来源锚点，用精确resolve、samefile及内容SHA验证；失败Reload保留此前原字面锚点与非法草稿的判据不删。真实8.3短路径原195fail、候选长/短各214pass提供本机反例，但原CI没打印路径，不能声称已经看见其具体TEMP拼写。Qt Unix ComboBox的QAccessible.Name反映currentText，标签由Label关系表达；测试应验证真实角色接口、明确buddy/关联标签和语言切换，并用丢buddy负向防止放宽；不为测试改正确产品。专项独审：⟦两项最终独审收据待齐⟧。

18c三档原生host/application均正常exit0，main实际观察排除QQ像素。150%为760×640下九页快捷键/F6、保留config+preview后Project完整name/Tab EXE、History三名称英/中/英与Search→Status、模板到Run/Back/取消及深色Project；125%为1200×800下F6/retained Project/Tab及History三名称/语言切换，没有扩写成九页或向导全流程。100%为实际新建blank、生产Save/Open、fields、初始化no_run/0事件、generate、run100/100、export及结果身份关联；导出manifest+7成员闭合、outputs_included=false/replay_verified=false，未执行CLI replay，零沉积world不代表物理响应基准。150/125 Harvey与100 Ptolemy均为纯文件审，不替代独立视觉复验或额外运行。

本轮全部86张原生原图仅本地保留，公开仅SHA/大小/观察文字，不把QQ原图带入Git。149项GUI产品字节及C++源码若与18c冻结身份精确一致，新test-only候选可沿用这些限定原生范围；身份映射仍须显式核对，不虚构新增操作，不无端重复同范围，但**新候选完整真实CI仍必须**。F6无法容纳完整joint的窄dock边界不在本修复内，不扩大物理/跨屏/热插拔结论。

下方“第三修复候选”实施快照保留原字节，仅作为当时2901f42等历史身份记录，不代表本段的新候选结论。

<details>
<summary>第三修复候选历史快照（原文保留）</summary>

'''.replace('TABLE',table)
records=[]
def propose(name,transform):
 p=R/name;raw=p.read_bytes();bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'';before=raw[len(bom):].decode().replace('\r\n','\n');after=transform(before);assert after!=before
 nl='\r\n' if b'\r\n' in raw and b'\n' not in raw.replace(b'\r\n',b'') else '\n';data=bom+after.replace('\n',nl).encode();q=O/'proposed'/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(data)
 diff=''.join(difflib.unified_diff((('\ufeff' if bom else '')+before).splitlines(True),(('\ufeff' if bom else '')+after).splitlines(True),fromfile='a/'+name,tofile='b/'+name));pp='patches/'+name.replace('/','__')+'.patch';(O/pp).write_bytes(diff.encode());records.append({'path':name,'original_sha256':sha(p),'proposed_sha256':sha(q),'patch':pp,'bytes':len(data)})
 return before,after

def stat(s):
 anchor='## 2026-11-02 J2/F8 当前实施';assert s.count(anchor)==1;tail='## 一句话定位';assert s.count(tail)==1
 return s.replace(anchor,notice+anchor,1).replace(tail,'</details>\n\n'+tail,1)
b,a=propose('STATUS.md',stat);assert a.replace(notice,'',1).replace('</details>\n\n','',1)==b

def road(s):
 rows=s.splitlines(True);count=0
 for i,line in enumerate(rows):
  if line.startswith('| **F8** |'):
   rows[i]=line.rsplit('|',2)[0]+'| 第四修复候选：18c5858实际Windows/CI/三档原生按原身份登记；两项test-only平台接口断言修订；专项独审及六profile算术待齐，完整新候选验收待进行、阶段未关闭 |\n';count+=1
  if line.startswith('| **J2 编辑覆盖与几何往返** |'):
   rows[i]=line.rsplit('|',2)[0]+'| **第四修复候选，阶段未关闭**：18c实际reload来源规范化与Windows264测试断言分开；只调整成功路径测试、不删失败保留判据；同产品原生范围须精确身份映射，新候选完整CI仍必须 |\n';count+=1
 assert count==2;return ''.join(rows)
propose('docs/ROADMAP.md',road)
history='''
## 2026-11-02 J2/F8 第四修复候选：18c5858平台测试接口与证据映射

18c5858真实CI首败及Windows/原生均按冻结身份保存，不覆盖56b689f/2901f42旧报告或改绿。Linux41344573528/M0 41344573541失败，Desktop41344573534/安装41344573604成功；strict4pass/4fail。Linux三个GUI在F8:659失败，Windows M0是geometry:264成功reload字面锚点断言（195入口），不是旧STL:162；Linuxbackend/integration未执行。18c六份本机合计⟦待两integration终态及独立算术⟧，两项test-only最终独审⟦待齐⟧；不得用这些未齐字段宣告阶段完成。

成功reload的实际产品合同是expanduser().resolve()后的来源锚点，失败读取仍保留此前原锚点/文档/非法草稿。测试只改成功分支的精确规范身份预期，并保留失败/无源/非法草稿原判据；真实8.3原195fail与候选长/短各214pass是本机实证，不捏造原CI具体路径拼写。Qt Unix ComboBox Name=currentText而Label关系表达标签，测试按真实角色接口、明确buddy/关联标签及动态语言检查，且丢buddy必须失败；不通过改正确产品或删除关联判据迁就平台。

18c产品149GUI及C++字节完全一致时，新test-only冻结可明确映射原18c三档限定原生scope，不伪称新执行、完整视觉或物理基准；新完整真实CI仍须通过。150的九页/模板与125的有限导航范围区分；100生产Save/Open/init no_run/run100/100/export闭包与未CLI replay区分。三档main正常退出，Harvey/Ptolemy只做必要链路纯文件审。86原图含QQ，raw只本地保留，公开仅metadata及观察范围。F6窄dock边界不扩写成已修复。原trace/失败/缓存读数局限均保留；正文不引用未归档OUT为公共链接。
'''
b,a=propose('docs/agent-history.md',lambda s:s+('\n' if not s.endswith('\n\n') else '')+history);assert a.startswith(b)
intro='''第四修复候选按18c5858实际证据与两个test-only平台断言修订收口，阶段仍未关闭；正式状态见 [ROADMAP](ROADMAP.md)。成功Reload核对规范来源身份、失败Reload仍保留原文档和锚点；Unix ComboBox按Name/currentText与Label关系验证，buddy负向不得缺失。两项独审及六profile算术⟦待最终收据⟧，新完整CI仍必须。18c三档原生只在产品149GUI/C++精确同字节时映射其原限定scope；100%初始化no_run、run100/100与导出未CLI replay分别保留，125%不冒充九页/向导全流程，QQ原图不入公开raw包。\n\n'''
def guide(s):
 old='当前为第三修复候选，相关专项独审已完成，完整新候选验收待进行；正式状态见 [ROADMAP](ROADMAP.md)。本页说明接口、使用方法和验收边界，不把组件检查或界面预览当作完整模拟验收。\n\n';assert s.count(old)==1
 s=s.replace(old,intro+'本页说明接口、使用方法和验收边界，不把组件检查或界面预览当作完整模拟验收。\n\n',1)
 s=s.replace('第三修复候选包含已审History、spacer、STL路径测试与K1 policy修复，','此前第三修复候选历史快照（2901f42原身份）：第三修复候选包含已审History、spacer、STL路径测试与K1 policy修复，',1)
 return s
propose('docs/J2编辑覆盖与F8验收.md',guide)
patch=b''.join((O/x['patch']).read_bytes() for x in records);(O/'docs.draft.patch').write_bytes(patch)
facts={'source_head':HEAD,'known_terminal_Windows':profiles,'pending_profiles':['windows113-integration','windows114-integration'],'pending_independent_reviews':['Windows reload test-only candidate','Linux Qt interface test-only candidate'],'CI_scope':'actual4pass4fail preserved; no Linuxbackend/integration executed','native_scope_source':'out/collab/j2-f8-18c5858-main-acceptance-scope.md','native_scope_sha256':sha(R/'out/collab/j2-f8-18c5858-main-acceptance-scope.md'),'native100_review_sha256':sha(R/'out/collab/native100-file-independent/receipt.json'),'new_candidate_head':None,'new_CI_success':False,'product_identity_mapping':'conditional on exact149 GUI andCPP identity, not yet approved by this draft'}
(O/'facts-at-preparation.json').write_bytes((json.dumps(facts,ensure_ascii=False,indent=2)+'\n').encode())
m={'schema':'j2_f8_fourth_docs_preparation_draft','frozen':False,'applied':False,'stage_complete':False,'base_head':HEAD,'files':records,'patch_sha256':sha(O/'docs.draft.patch'),'scope_count':4,'pending_freeze_requirements':['both test-only independent receipts final and exact candidate identities','all six18c profile terminal report/launch rawSHA and summed counts','explicit149 GUI/CPP mapping proof before claiming native reuse','main accepted final wording then Feynman narrow review'],'history_protection':'STATUS old current section preserved exact inside historical details; all original old historical tail untouched; history full prefix exact; ROADMAP only two current rows; J2 active introduction + historical label only','new_public_OUT_links':False}
(O/'manifest.draft.json').write_bytes((json.dumps(m,ensure_ascii=False,indent=2)+'\n').encode())
assert subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True)==status
print(json.dumps({'path':str(O),'files':4,'frozen':False,'placeholder_fields_intentional':True,'tracked_unchanged':True},ensure_ascii=False))
