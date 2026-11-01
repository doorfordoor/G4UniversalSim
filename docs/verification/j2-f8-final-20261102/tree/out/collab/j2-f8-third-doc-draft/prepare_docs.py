"""Prepare nine Markdown-only third-candidate proposals, never apply."""
import difflib,hashlib,json,re,subprocess,time
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'out/collab/j2-f8-third-doc-draft';HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
NATIVE=ROOT/'out/collab/j2-f8-native-second-audit/v2/native-audit.json';native=json.loads(NATIVE.read_text());assert native['audit_integrity_status']=='verified' and native['overall_native_acceptance'] is False
BASE=ROOT/'out/verification/j2-f8-2901f42';ci=json.loads((BASE/'ci/collected-files-final.json').read_text());assert ci['release_accepted'] is False
profile_rows=[]
for name in ['windows-static','windows-gui','windows113-backend','windows114-backend','windows113-integration','windows114-integration']:
 d=BASE/name;reports=list(d.glob('*/report.json'));row={'profile':name,'status':'not_terminal_at_snapshot','report':None}
 if reports:
  p=reports[0];r=json.loads(p.read_text());l=json.loads((d/'launch.json').read_text());row.update(report=str(p.relative_to(ROOT)).replace('\\','/'),report_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),cases=len(r['results']),assertions=r['assertions_executed_total'],pass_count=sum(x['status']=='pass' for x in r['results']),fail_count=sum(x['status']=='fail' for x in r['results']),skip_count=sum(x['status']=='skip' for x in r['results']),launcher_status=l.get('status'),runner_exit=l.get('runner_exit_code'),gate_exit=l.get('gate_exit_code'),identity_errors=l.get('identity_errors'),git_dirty=r['git_dirty'])
  if l.get('status')=='passed' and l.get('runner_exit_code')==l.get('gate_exit_code')==0 and not l.get('identity_errors') and not r['git_dirty']:row['status']='verified_terminal_pass'
 profile_rows.append(row)
policy=ROOT/'out/collab/j2-resource-policy-path-review/final-v1';pr=json.loads((policy/'receipt.json').read_text());assert pr['patch_sha256']==hashlib.sha256((policy/'fix.patch').read_bytes()).hexdigest()
proof={'base_head':HEAD,'snapshot_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'local_profiles':profile_rows,'CI_runs':ci['runs'],'CI_release_accepted':False,'native_audit_sha256':hashlib.sha256(NATIVE.read_bytes()).hexdigest(),'native_overall_pass':False,'policy_final_v1_patch_sha256':pr['patch_sha256'],'policy_independent_review':'pending per main at preparation time','History_spacer_combination_independent_review':{'receipt':'out/collab/f8-history-spacer-combined-independent/receipt.json','sha256':hashlib.sha256((ROOT/'out/collab/f8-history-spacer-combined-independent/receipt.json').read_bytes()).hexdigest(),'author_counts_each_125_150':595},'applied':False}
(OUT/'evidence-snapshot.json').write_bytes((json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode())
passed=[r for r in profile_rows if r['status']=='verified_terminal_pass'];pending=[r['profile'] for r in profile_rows if r['status']!='verified_terminal_pass']
table='\n'.join('| '+r['profile']+' | '+str(r['pass_count'])+'/'+str(r['cases'])+' | '+str(r['assertions'])+' | 0 / 0 / [] |' for r in passed)
current='''## 2026-11-02 J2/F8 当前实施

**阶段未关闭，正在准备第三修复候选。** 工作区 effective-config、分支 roadmap/J2-F8-editing；首轮冻结为 `56b689f`，第二冻结为 `2901f42`。第三修复尚须统一应用、生成新提交及完整复验，不能把专项或本机通过改写成整阶段验收。当前约定见[开工契约](docs/collab/inbox/20261101-j2-f8-execution.md)和[J2/F8说明](docs/J2编辑覆盖与F8验收.md)。

`2901f42` 的 C++ 源码指纹仍为 `9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a`。截至本次文档候选快照，以下本机正式报告已通过 runner 和 matching 历史 strict 门禁，identity_errors 为空、report git_dirty=false；未用内部SKIP代替完整PyVista路径。

| 本机 profile | 通过/用例 | v3入口 | runner / strict / identity_errors |
| --- | ---: | ---: | --- |
TABLE

尚未取得终态的 profile：PENDING。证据根文字登记为 `out/verification/j2-f8-2901f42/`；最终归档入库后另补稳定链接，当前不以未归档out作为公共证据链接。

第二候选四个真实push CI（均attempt1）已终态：Linux Geant4 `41336912644` 与 M0 `41336912651` **失败**，Desktop `41336912646` 与 Full installation `41336912645` 双平台成功。Linux GUI暴露QSpacerItem被当成layout递归的问题；Windows M0 GUI保留K1 policy别名身份拒绝及geometry文件路径断言首败。整体release_accepted=false；未运行的下游profile不记通过，安装/桌面成功不替代功能CI。

第二候选原生有效DPR 1.0/1.25/1.5的host均exit0，三档149项GUI SHA与当前源码相符、使用完整D盘venv。main逐条观图，QQ覆盖像素排除；125%向导经自然拖动后另留完整无遮挡dialog观察。100%实际保存/重载blank-native.json、完成生成/初始化/100事件/导出，初始化no_run与100/100事件分开；7成员offline-native资源SHA匹配，历史仍stale、未执行离线replay。150%Project retained问题在相应视觉范围已消失，但F6窄dock边界与History名称/标签遗漏保持开放，**不升overall native pass**。后续三档对新repair范围仍需补验；物理跨屏/热插拔与物理正确性不由这些观察推出。

第三修复准备包括History三显式buddy及动态语言名称、仅真实QLayout的递归兼容、geometry路径测试精确resolve/samefile比较（不改geometry产品）；History+spacer组合595专项已独审，尚不替代新candidate的CI/原生。F6窄dock界限不修改，不声称不可容纳的整组标签/控件可以同时放入窄视口。K1 final-v1 policy规范身份及原拼写首尾guard已有冻结候选，**独审与新candidate复验仍待完成**，不提前判闭合。

首轮 `56b689f` 六份本机报告300次执行、286通过/14失败/0跳过、179468入口及严格失败保持原件；GUI自身git_dirty=true/73条长路径表象不追改。原M0 `41330577407`、Linux `41330577426` 失败，安装 `41330577328`、桌面 `41330577359` 成功；本轮新结果不替换原run或旧失败。源码、构建、报告、截图及独审各按原身份保留。完整新候选矩阵/native/CI全部终态并经独审后才考虑阶段关闭；当前归档只是OUT候选，不是最终公开发布。

'''.replace('TABLE',table).replace('PENDING','、'.join(pending) if pending else '本快照六份均已终态；仍须按各自记录及第三修复新身份复验')
records=[]
def propose(file,change):
 path=ROOT/file;raw=path.read_bytes();bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'';body=raw[len(bom):].decode('utf-8');before=body.replace('\r\n','\n');after=change(before);assert after!=before,file
 nl='\r\n' if b'\r\n' in raw and b'\n' not in raw.replace(b'\r\n',b'') else '\n';data=bom+after.replace('\n',nl).encode();dest=OUT/'proposed'/file;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 diff=''.join(difflib.unified_diff((('\ufeff' if bom else '')+before).splitlines(True),(('\ufeff' if bom else '')+after).splitlines(True),fromfile='a/'+file,tofile='b/'+file));patch=OUT/'patches'/(file.replace('/','__')+'.patch');patch.parent.mkdir(exist_ok=True);patch.write_bytes(diff.encode());records.append({'path':file,'original_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(data).hexdigest(),'patch':str(patch.relative_to(OUT)).replace('\\','/'),'bytes':len(data),'BOM_preserved':bool(bom),'line_endings_preserved':nl=='\r\n' or '\r\n' not in before})
 return before,after
before_status,after_status=propose('STATUS.md',lambda s:s[:s.index('## 2026-11-02 J2/F8 当前实施')]+current+s[s.index('## 一句话定位'):]);assert before_status[before_status.index('## 一句话定位'):]==after_status[after_status.index('## 一句话定位'):]
def roadmap(s):
 lines=s.splitlines(True)
 for i,line in enumerate(lines):
  if line.startswith('| **F8** |'):lines[i]=line.rsplit('|',2)[0]+'| 2026-11-02 第三修复候选准备，阶段未关闭；2901f42本机已过范围、CI失败及原生开放边界见STATUS，History/QLayout专项不代替新冻结复验 |\n'
  if line.startswith('| **J2 编辑覆盖与几何往返** |'):lines[i]=line.rsplit('|',2)[0]+'| **2026-11-02 第三修复候选准备，未验收**：保留56b689f及2901f42原失败；新增K1 policy契约候选尚待独审/新candidate全复验，几何路径仅修严格同文件测试；不提高物理支持等级 |\n'
 result=''.join(lines);result=result.replace('v7保存材料/几何及原始草稿','v8保存材料/几何及原始草稿，完整v7编辑快照仅补枚举的新字段');return result
propose('docs/ROADMAP.md',roadmap)
index_line='- 2026-11-02 J2/F8第三修复候选准备：2901f42本机已过范围不代表CI/原生整体通过；History三显式buddy/动态语言、QLayout类型递归、K1 policy规范身份与原拼写首尾guard的候选边界见 docs/agent-history.md 同名新条目。原失败与旧身份保留，未宣告阶段关闭。\n\n'
propose('AGENTS.md',lambda s:s[:s.index('- 2026-11-02 J2/F8候选')]+index_line+s[s.index('- 2026-11-02 J2/F8候选'):])
gui_line='2026-11-02 J2/F8第三修复候选准备：History只用三个明确buddy及既有语言刷新链，真实QLayout才可递归count/itemAt；F6窄dock界限不修、不放宽可容纳joint判据。K1 policy最终候选需先独审再统一应用，原拼写安全检查不得被canonical匹配替代。详见 ../docs/agent-history.md 同名条目；2901f42旧raw不改，新修复三档原生补验仍待完成。\n\n'
propose('gui/AGENTS.md',lambda s:s.replace('# G4UniversalSim GUI Agent 开发约束\n\n','# G4UniversalSim GUI Agent 开发约束\n\n'+gui_line,1))
history='''
## 2026-11-02 J2/F8 第三修复候选准备（阶段未关闭）

第二冻结2901f42的已过本机profile、真实CI及原生范围按各自原report/launch/visual-observations登记，详见STATUS当前段。当前CI四run均attempt1：Linux41336912644/M0 41336912651失败，安装41336912645/桌面41336912646成功；首轮56b689f四run及旧失败另保留，不拼接报告或改绿。第三修复统一应用前，main须确认本轮六份本机报告全部终态；新candidate仍需新提交、必要构建身份、同版本/同profile/v3历史strict门禁、真实CI和原生复验。

History候选只为Runs root→runs_root、Search→search、Status→status_filter建立三个显式buddy，复用现有语言刷新链，使QWidget及QAccessible名称随en/zh/en更新；不新增全局QHBox猜配、翻译表或业务事务。QLayout兼容候选须先判真实QLayout再按count/itemAt遍历，区分QSpacerItem/QWidgetItem，不把item.layout()的任意绑定返回值当layout。原CI异常、自然环境与受控返回值负向证据分别保留；两产品和组合595专项独审不能冒充已应用或新候选CI/native通过。

F6窄preview dock不在本修复中扩大尺寸/改变布局。可容纳标签+完整控件时仍要求joint完整可见；确实不可同容纳的宽度边界不能伪装成全joint通过，也不得强制滚动归零或更换dock实例。main直接视觉观察排除QQ覆盖；被动矩形containment不能证明无遮挡。2901f42三档原生host退出0及100%真实100事件不关闭150%F6/History开放项；新repair相关scope在三档仍须补验。

K1 final-v1候选以policy规范身份匹配同一普通文件，但不改变closure节点、资源读取路径或source_receipts。原policy绝对拼写必须先_no_links再resolve，并保存原拼写；资源匹配方向也先拒链接再resolve。相同普通文件的重复policy入口明确拒绝，无关/相对unused入口仍拒绝，restricted默认拒绝与显式允许裁决不放宽。collect返回前、export原收据核验后且_publish_directory前，均重新按原policy拼写_no_links→resolve并核对身份，不能入口resolve后丢掉原拼写。真实晚junction反例只改policy原组件也须拒绝，export不发布并清理自身staging；这些确定时点检查不承诺任意并发替换安全。该final-v1补丁f705dc96及其产品4990d9f4/测试80726fb8已有作者收据，独审与新candidate全复验仍待完成，正文不宣告其已闭合。

几何STL file路径回归只做规范resolve及samefile的精确同文件断言，不能用endswith/文件名/存在性代替身份，也不为测试改geometry产品语义。当前项目格式v8；普通旧项目及完整v7编辑快照仍按已知枚举迁移，损坏旧字段不泛化默认，有日期历史v7文本不追改。

证据根文字登记为out/verification/j2-f8-2901f42及out/collab中的各冻结独审目录，尚未归档为公共链接；最终入库后由main另链。Native独立文件审计仅核launch/GUI149/SHA/原图引用/记录/离线manifest，overall=false。旧raw、原CI失败、JPEG编码的原图字节以及旧copy/review首败均保留，不以本段更新历史身份。当前条目是第三候选实施契约，不是阶段状态改为完成。
'''
old_history,new_history=propose('docs/agent-history.md',lambda s:s.rstrip()+'\n'+history);assert new_history.startswith(old_history.rstrip())
guide_intro='当前正在准备第三修复候选，J2/F8阶段仍未关闭。2901f42本机已过范围、CI明确失败及原生边界见[状态入口](../STATUS.md)；第三修复的独审/新candidate完整复验仍待完成。本页不将专项或界面预览升级为整体验收。\n\n'
def guide(s):
 s=s.replace('## 从空白开始\n',guide_intro+'## 从空白开始\n',1)
 anchor='external 模式的 Inspect 使用实际主配置/宏及后端检查'
 extra='第三修复候选为历史页“运行包根目录／搜索／状态”建立明确标签关联并沿既有语言刷新链更新名称；布局遍历只处理真实QLayout，避免把spacer当layout。组合专项已独审，仍须新candidate复验。F6预览dock过窄时不保证完整按钮文本或不可容纳的joint同时可见；可增宽dock或主窗，此项边界没有被修复或降低标准。\n\n'
 s=s.replace(anchor,extra+anchor,1)
 return s
propose('docs/J2编辑覆盖与F8验收.md',guide)
def quick(s):
 # Preserve all dated historical paragraphs; add a new current candidate notice.
 insert='第三修复候选准备中，阶段未关闭。已审History标签关联／语言切换及布局spacer兼容仍待统一应用和复验；窄预览dock不能容纳完整按钮时可增宽dock或窗口，不将其称作整体可访问性通过。完整本机／CI／原生状态以[状态入口](../../STATUS.md)为准。\n\n'
 s=s.replace('# G4UniversalSim GUI 中文快速使用说明\n\n','# G4UniversalSim GUI 中文快速使用说明\n\n'+insert,1)
 s=s.replace('当前 version 为 6。','当前 version 为 8；普通旧项目按已知版本迁移，完整v7编辑快照只补枚举的新字段，损坏快照仍拒绝。')
 return s
propose('gui/docs/中文快速使用说明.md',quick)
propose('docs/功能支持矩阵.md',lambda s:s.replace('# G4UniversalSim 功能支持矩阵\n\n','# G4UniversalSim 功能支持矩阵\n\n当前准备第三修复候选，阶段状态未关闭：2901f42已有本机通过范围但M0/Linux CI仍失败；原生Project retained观察已修复，F6窄dock与History遗漏不升overall。History／真实QLayout修复已专项独审，K1 policy最终候选待独审及新candidate全复验；本段不提高任何后端或物理支持等级。见[状态入口](../STATUS.md)。\n\n',1))
propose('docs/开发路线图.md',lambda s:'当前接续：2026-11-02 正准备J2/F8第三修复候选；第二冻结2901f42的本机已过范围不代替明确失败的M0/Linux CI及原生开放项，阶段仍未关闭。History／QLayout组合已专项独审，K1 policy终稿待独审和新candidate完整复验。下方有日期的旧段保留当时状态，当前以[STATUS](../STATUS.md)与[ROADMAP](ROADMAP.md)为准。\n\n'+s)
assert len(records)==9
patch=b''.join((OUT/r['patch']).read_bytes() for r in records);(OUT/'docs.patch').write_bytes(patch)
manifest={'schema':'j2_f8_third_candidate_docs_out_draft_v1','base_head':HEAD,'applied':False,'stage_completed':False,'files':records,'docs_patch_sha256':hashlib.sha256(patch).hexdigest(),'facts':'evidence-snapshot.json','before_main_apply':['Confirm all six 2901f42 local profiles terminal; refresh current matrix paragraph if needed','K1 final-v1 independent review still pending at this draft snapshot','New candidate commit/build/formal/native/CI required; no historical status promotion'],'historical_policy':'Only STATUS current section replaced; dated historical paragraphs elsewhere preserved; agent-history append-only; roadmap undated current F5 version line minimally v8; quick current schema sentence v6->v8','public_links':'No new unarchived out Markdown links; local evidence roots are prose/code only'}
(OUT/'manifest.json').write_bytes((json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'files':len(records),'patch_bytes':len(patch),'patch_sha256':manifest['docs_patch_sha256'],'passed_local_profiles':[(r['profile'],r.get('cases'),r.get('assertions')) for r in passed],'pending_local_profiles':pending,'K1_review_pending':True},ensure_ascii=False))
