"""Read existing files only; no application imports or execution."""
from pathlib import Path
import json, hashlib, subprocess, datetime

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
HEAD = '18c5858fd6e80a5cb6096beacebfef69c479ad49'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == HEAD
evidence = {}

def ref(key, path, kind):
    p = ROOT / path
    assert p.is_file(), path
    evidence[key] = dict(path=path, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), size=p.stat().st_size, kind=kind)

documents = {
    'contract': 'docs/collab/inbox/20261101-j2-f8-execution.md',
    'roadmap': 'docs/ROADMAP.md',
    'guide': 'docs/J2编辑覆盖与F8验收.md',
    'main-scope': 'out/collab/j2-f8-18c5858-main-acceptance-scope.md',
    'native100-review': 'out/collab/native100-file-independent/review.md',
    'native100-receipt': 'out/collab/native100-file-independent/receipt.json',
    'native125150-review': 'out/collab/j2-f8-18c5858-native-file-audit/README.md',
    'native125150-receipt': 'out/collab/j2-f8-18c5858-native-file-audit/summary.json',
    'builds': 'out/verification/j2-f8-18c5858/identity/build-identities.json',
    'ci-first': 'out/verification/j2-f8-18c5858/ci/first-failure.md',
    'ci-current': 'out/verification/j2-f8-18c5858/ci/report-gates-current.json',
    'ci-windows': 'out/verification/j2-f8-18c5858/ci/windows-m0-failure.md',
    'linux-test-fix': 'out/collab/f8-linux-qt-name-18c5858/HANDOFF.md',
    'linux-test-patch': 'out/collab/f8-linux-qt-name-18c5858/candidate-test-only/fix.patch',
    'legacy-review-index': 'out/collab/j2-f8-review-index/README.md',
}
for key, path in documents.items():
    ref(key, path, 'existing_scope_or_receipt')

products = {
    'blank': ['gui/g4usim_gui/core/project.py', 'gui/g4usim_gui/window/project.py', 'gui/g4usim_gui/widgets/new_simulation_wizard.py', 'gui/g4usim_gui/writers/package_writer.py', 'gui/g4usim_gui/core/experiment_bundle.py'],
    'materials': ['gui/g4usim_gui/editors/material_editor_model.py', 'gui/g4usim_gui/widgets/config/materials.py', 'gui/g4usim_gui/parsers/materials_parser.py', 'gui/g4usim_gui/core/nist_elements.py', 'src/Materials/MaterialManager.cc', 'src/Materials/MaterialFactory.cc'],
    'sources': ['gui/g4usim_gui/core/run_editor_model.py', 'gui/g4usim_gui/widgets/config/j2_run_editors.py', 'src/Source/SourceManager.cc', 'src/Source/PrimaryGeneratorAction.cc'],
    'physics': ['src/Physics/PhysicsFactory.cc', 'src/Physics/PhysicsManager.cc'],
    'geometry': ['include/Geometry/SolidRegistry.hh', 'src/Geometry/SolidRegistry.cc', 'gui/g4usim_gui/core/solid_registry_data.py', 'gui/g4usim_gui/editors/geometry_editor_model.py'],
    'f8': ['gui/g4usim_gui/core/accessibility.py', 'gui/g4usim_gui/widgets/start_page.py', 'gui/g4usim_gui/main_window.py', 'gui/g4usim_gui/window/shell.py', 'gui/g4usim_gui/window/workspace_layout.py', 'gui/g4usim_gui/widgets/run_history_page.py'],
}
for group, paths in products.items():
    for i, path in enumerate(paths):
        ref(f'{group}-product-{i+1}', path, '18c_product_raw_bytes')

profiles = {}
for profile in ['windows-static', 'windows-gui', 'windows113-backend', 'windows114-backend', 'windows113-integration']:
    reports = list((ROOT / 'out/verification/j2-f8-18c5858' / profile).rglob('report.json'))
    assert len(reports) == 1, reports
    path = reports[0]
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    assert data['git_head'] == HEAD
    ref(profile+'-report', path.relative_to(ROOT).as_posix(), 'existing_formal_report')
    selected = []
    for row in data['results']:
        if not ('j2' in row['name'] or 'solid_registry' in row['name'] or row['name'] in ['gui_f8_accessibility', 'gui_f4_layout', 'gps_sources', 'physics_a6', 'fields_a7', 'biasing_targets', 'biasing_worker_runtime', 'max_step_scope', 'material_numeric', 'k1_bundle']):
            continue
        sid = 'test-'+Path(row['script']).stem
        if sid not in evidence:
            ref(sid, row['script'], '18c_permanent_test_raw_bytes')
        lid = profile+'-'+row['name']+'-log'
        ref(lid, Path(row['log']).relative_to(ROOT).as_posix(), 'existing_formal_case_log')
        assert evidence[lid]['sha256'] == row['log_sha256'], lid
        selected.append({**{k: row.get(k) for k in ['name', 'script', 'status', 'exit_code', 'assertions_executed', 'evidence_directory']}, 'log_ref': lid, 'script_ref': sid})
    profiles[profile] = dict(report_ref=profile+'-report', head=data['git_head'], source_fingerprint=data['source_fingerprint'], tests_content_fingerprint=data['tests_content_fingerprint'], cases=len(data['results']), assertions_executed_total=data['assertions_executed_total'], selected_cases=selected)
for profile in ['windows113-integration', 'windows114-backend']:
    ref(profile+'-terminal', 'out/verification/j2-f8-18c5858/'+profile+'/terminal-sync.json', 'existing_terminal_receipt')
for scale in ['100', '125', '150']:
    for name in ['launch.json', 'identity.json', 'observations.jsonl', 'visual-observations.json', 'exit.json']:
        path = f'out/verification/j2-f8-18c5858/native{scale}/{name}'
        if (ROOT/path).is_file():
            ref(f'native{scale}-{name}', path, 'native_raw_local_only_no_new_visual_review')

manifest = dict(schema='j2_f8_18c_scope_map_v1', created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), head=HEAD, activity='read/hash existing files only; no Qt/backend/native/test/build/launcher; writes only this OUT directory', phase_status='not_closed; future candidate CI pending', pending=['114 integration terminal not credited by this map', 'two test-only repairs not applied here; actual-patched F8 125/150 later', 'future candidate CI and main final closure'], product_groups=products, profiles=profiles, evidence=evidence)
(OUT/'evidence-index.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

def link(key):
    entry = evidence[key]
    return f"[{key}](../../../{entry['path']}) (`{entry['sha256'][:12]}`)"

intro = f'''# 18c J2/F8 六链路范围映射（阶段未关闭）

冻结 `{HEAD}`。依据 {link('contract')}、{link('roadmap')}、{link('guide')}。本任务只读已有文件/哈希，写本OUT目录；未运行Qt/backend/native/profile/build/launcher，未改产品、测试、runner或阶段状态。完整相对路径与原始字节SHA256见 [evidence-index.json](evidence-index.json)。下列断言数引用旧正式报告，不是物理指标，也不是本任务重跑。

| 六链路 | 18c实现／解析校验边界 | 永久smoke／真实backend证据 | 本轮原生限定scope／未包含 |
|---|---|---|---|
| 1 空白／模板／导入／身份 | project/window.project、wizard、package_writer、experiment_bundle；world+空材料内存文档；无源Reload/Revert保留；旧源变化、非法草稿与资源闭包仍拒绝。 | GUI blank29、workspace21、CURRENT import208；static resources101、K1 bundle603；113真实E2E674（真实Qt/K1、保存重载、搬移CLI replay）。blank入口遍历五模板生成。 | 100实际直接New blank→Save/Open→fields→Initialize(no_run)→Generate→Run100/100→Export→Results。150先直接New blank，后另开template wizard并取消，未Finish；125不冒称重复该链。100导出replay_verified=false，不能套用E2E重放结果。 |
| 2 NIST／同位素／多敏感体 | material model/parser/widgets+有限SDK元素表；custom优先、拼错拒绝、isotope保留；volume_fraction只接受有密度材料。真实后端据MaterialManager元素解析及MaterialFactory，GetElement不被假定自动NIST查询。 | materials GUI499；113 materials_backend28：kernel_constructed组成/Si30及1事件，typo/元素体积分数负例；E2E674核两个敏感体run/event/track关联与步长。密度UnitParser词法/换算有限性模型及material_numeric永久反例另保留。 | 100只有world无敏感体，100行零沉积不是探测器响应证明；原生未逐项编辑NIST/同位素。多体积输出不等于独立SD电子学/多体积脉冲谱验证。 |
| 3 命名多源／强度／球面 | run_editor_model/j2_run_editors→SourceManager/PrimaryGeneratorAction；强度选源与每事件同发分开，球面/球内、活动资源有校验。 | GUI run_editors223、CURRENT import208；双版本j2_source_physics各4853：真实初级顶点、球面vs球内、强度选源、同发权重、谱/离子/回放及拒绝；gps_sources各219。 | 150源页/wizard到达不算真实多源输运；100blank运行不代替该专项。sensitive hit不是源顶点；有限样本分布检查不证明一般无偏性。 |
| 4 物理组合／替换／region | PhysicsManager/Factory+运行编辑模型；reference附加/替换、manual、同类冲突及跨macro选择器拒绝；actual constructor/process/带电StepLimiter。 | 双版本j2_source_physics各4853含旧EM消失、新constructor/process实际存在、macro冲突及region带电限步/中性对照；physics_a6各71、max_step_scope各54；E2E核actual inventory/步长。 | 原生blank初始化/运行不是逐组合复验；不认证任意constructor组合、H7微观径迹或物理准确度。 |
| 5 E7／高级实体／vis／场偏置 | SolidRegistry及GUI生成元数据；15既有原语/7布尔工具不扩实体集；geometry model/writer含shape、placement、vis、资源。场/偏置沿已有真实实现。 | static registry248、geometry GUI212；双版本registry_backend各288及geometry_a5正反例；fields_a7各336、biasing_targets各80、worker runtime等旧合同回归；资源闭包由resources/E2E另证。 | 3D预览不证明几何可运行；registry数值/CSG检查不等于所有高级实体、vis像素或STL科学可信度认证；无场/偏置新物理基准。 |
| 6 F8跨项入口／焦点／DPI | accessibility、start_page、main_window/shell/workspace_layout、History标签；同步+延后owned当前焦点最小平移，fit joint完整/超宽reading anchor；stale/foreign/deleted取消；wizard按钮动态语言，不改runner所有权。 | Windows正式F8 583、F4layout265；保留旧416合同及History/spacer永久函数。环境发现使用受控注入，只证明入口/单实例/取消/snapshot不变，不是真实安装。原Linux Name与Windows路径断言失败保留。 | 150九页/F6/保留docks→Project/Tab、History en/zh/en、wizard三Return/Back/Esc、dark；125仅Config/F6→Project/Tab、History三Name/自然Tab、finalProject；100真实K1链/中文History。三档正常关闭；无全功能读屏器或多屏热插拔认证。 |

## 原始身份与证据入口

'''
extra = [
    '- 构建：'+link('builds')+'；113 EXE `01e0fb795f93772ccfa818d625fee145d8da1ad3ad80894372a9a855f0af108a`，C++ fingerprint `9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a`。双版本EXE/能力完整身份见原收据。',
    '- 正式报告：'+', '.join(link(p+'-report') for p in profiles)+'。113integration终态/gate0 '+link('windows113-integration-terminal')+'；114backend终态/gate0 '+link('windows114-backend-terminal')+'。不提前计入114integration。',
    '- 原生事实边界：'+link('main-scope')+'；100独审 '+link('native100-review')+' / '+link('native100-receipt')+'；125/150独审 '+link('native125150-review')+' / '+link('native125150-receipt')+'。149 GUI源身份沿原identity/独审；新test候选未冒充本轮已执行。',
    '- 产品与永久入口逐文件SHA在JSON product_groups/evidence；各case的script/status/exit/计数及原log SHA在profiles.selected_cases。本任务重哈日志匹配既存report，不重跑或冒充重新执行strict gate。',
    '- '+link('legacy-review-index')+' 只供历史发现/修复追踪；旧开放/通过、旧fingerprint不覆盖18c或未来候选。',
    '', '## 尚待收口／严格边界', '',
    '1. 两类已实证test-only失败仍保留原CI失败：Linux Combo Unix Name/Value及真实Label关系合同；Windows8.3路径字面相等。原件 '+link('ci-first')+'、'+link('ci-current')+'、'+link('ci-windows')+'；Name自然复现/冻结候选 '+link('linux-test-fix')+' / '+link('linux-test-patch')+'。产品未因此改变；未来候选CI仍pending，不先判阶段完成。',
    '2. 本轮18c原生没有实际I1/I2环境入口cancel、导入、五模板Finish与重复重入全套人工复验。入口/重入/取消有永久offscreen覆盖，五模板有组件生成覆盖；这是证据类型差异，不能写成原生已覆盖。是否补人工项由main按约定裁决；本任务未发现新确认产品缺陷。',
    '3. 150窄preview按钮82px>内部56px、History oversized joint的reading anchor是既定边界，不声称全文/超宽joint同容纳。125不写成独立九页/wizard。QQ/边缘浮层raw local-only，未复制/上传/重新目视；焦点以被动Qt为准，UIA旧FOCUSED缓存不作新事实。',
    '4. 150导航Scan raw投影、直接New blank替换、随后wizard取消分三段。取消前后raw相同及cached Undo/Redo/modified不变不冒称完整F5载荷指纹。100Initialize为no_run/0事件，Run才100/100；world零沉积不升级物理范围。',
    '5. 不包含新H2过滤/能谱、H7微观径迹、Q2偏置/剂量等独立物理基准、任意动态Geant4命令、多屏热插拔或读屏器全功能认证。适用版本/平台仍等实际矩阵终态和main阶段判定。actual-patched F8 Dvenv125/150待main统一apply后另交，本任务未执行。', '',
]
(OUT/'README.md').write_text(intro+'\n'.join(extra), encoding='utf-8', newline='\n')
receipt = dict(head=HEAD, outputs={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'README.md', OUT/'evidence-index.json', Path(__file__)]}, indexed_files=len(evidence), case_logs_rehashed=sum(len(p['selected_cases']) for p in profiles.values()), missing=[], ran_qt_backend_native_tests_build=False, author_process='synchronous standard-library Python mapper; git rev-parse only')
(OUT/'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(receipt, ensure_ascii=False))
