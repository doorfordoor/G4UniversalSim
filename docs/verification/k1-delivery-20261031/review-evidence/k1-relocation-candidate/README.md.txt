# K1 搬移包 GUI 下一动作：P1 候选

基线 `11c92d361369cda4b2412451ff2841eff940f810`，分支 `roadmap/K1-trusted-workflow`。本写者只写本目录；未修改 tracked 文件、未操作 host74889/window528532、未触碰正式 Windows46966、未启动全矩阵或提交推送。

## 原因与修复范围

实际查看了 `out/verification/k1-11c92d3/visible-qt-dialog/03-relocated-initialization-rejected.jpg`：初始化被字段校验拒绝，材料/几何的 `resources/...` 被报不存在；原 actions/current-state 记录了失败，不能计为后端启动。

`load_bundle` 的现有 `_snapshot_paths` 已重定位规范 pathSettings/geometrySettings/源证据，但没有同步同一资源的 F5 raw draft。真实窗口 `apply_workspace` 后投 raw 控件，下一动作 `_finish_history_merge → capture_workspace → update_project` 又把相对路径写回规范模型。`project_file=None` 不是缺少一个应当伪造的项目文件名；正确锚点就是已验证包的当前根。

候选只替换 `gui/g4usim_gui/core/experiment_bundle.py`。在原加载重定位处保存四个资源控件的规范路径关联，随后只将确属同一资源的原草稿同步为当前包内路径：materials、geometry、external main config、macro。复用现有 `_resolve`/闭包语义，保留前后空白；空值、缺失/非法/不同于规范模型的草稿不覆盖，其原有拒绝语义保持。没有一概清空raw，没有硬编码原目录、改变cwd、增加事务或重写GUI collection。导出时保持相对便携路径，加载后UI与模型保持同一资源锚点。

配置解析/科学运行/输出定义/验证资格无新增能力。窗口仍走原MainWindow加载、F5、既有服务与runner；历史记录不因加载恢复当前资格。人类文档和AGENTS正式同步由主任务解冻集成时完成。

## 交付文件与真实SHA

- `files/gui/g4usim_gui/core/experiment_bundle.py`：r3带lexical guard的完整替换文件，SHA-256 `5c1dff0338e80a673ba8f3427aeb7bfe1abe9d2b5315efca564310be8118385a`。
- `files/gui/smoke_tests/smoke_k1_relocation.py`：新专属窄回归，SHA-256 `4fddfec77f40d00e0f052b147386aaf3d3adddd305bc656fe57f480fdf0732ad`。
- `files/scripts/test_k1_staging_alias.py`：最终跨平台staging专项，SHA-256 `0e33fc7c8990cfe9d5aed535561420f7c34e38b225872ce33056a179f9672d8d`。
- `candidate.diff`：r3 SHA-256 `7d4857e251d4087baece733b7fb08d43e2e1b2913ecca2d33ce69372ca96f22d`。
- `manifest.json`：基线原字节SHA、候选SHA、patch与只读 `git apply --check` 收据；未执行 apply。
- `validation-receipt.json`：逐命令、退出码、探针入口数、实际落盘原始日志SHA。它是候选专项收据，不是全矩阵报告。

## 回归方式与边界

新smoke默认 `components`：无真实后端，使用真实MainWindow和EditSession/服务，三次文件选择仅由mock自动返回。通过真实 `experiment_panel.action_requested` 调用 import/validate；验证UI收集、字段、编辑、Undo/Redo、普通保存到另一父目录并重新打开、快照编解码。自生成夹具还通过真实GUI export，逐SHA复制后隐藏原输入和原导出目录，避免原路径可读掩盖问题。

`--mode backend` 明确依赖最终真实EXE；在同一MainWindow链路执行初始化、3/3，再编辑/Undo/Redo、保存重开后再次3/3。所有行动继续走原服务和runner。对话框mock只是离屏自动化，不冒称实窗；本轮未显示/操作原生窗口，没有新增物理正确性验证。

原始输入的反例包括非法seed、空材料路径、缺失材料路径，都保留原文且真实GUI字段动作失败；匹配的材料/几何以及external主配置/macro路径保留空白格式并正确搬移。原包和搬移副本所有成员SHA在测试前后不变。首次本地环境选择后可能收集补齐私有控件草稿并产生新revision；回归要求稳定后的重复无编辑收集不再变化，不以压制revision隐藏输入变动。

修前 `baseline-actual-final.log` 在真实加载当前实窗导出包后复现字段失败：10入口、exit1，准确到材料/几何missing后的显示链断言，未启动后端。首轮候选真实包组件130入口通过；加入external路径反例后，真实包组件136、自生成搬移组件138入口通过。仅加载修复的r1已完整通过：真实后端初始化及两次3/3共161入口，原资源包组件529、原K1窗口38、GUI副本205文件compileall exit0。r1产品ab29491a、manifest/patch/收据保存在 `archive-r1/`；原日志保持。合并r2的最终状态以 `revision2-validation-receipt.json` 和 PROGRESS 为准，不用r1报告冒充新字节验收。

## r2：Windows staging别名身份

按主任务追加分派，继续由本写者独占同一产品文件，纳入Tesla报告的第二个路径缺陷。`export_bundle` 会主动清除writer中间文件；但writer receipt使用canonical长拼写，而staging可能来自真实8.3 TEMP别名，原 `path.is_relative_to(staging)` 误判外部资源并在清理后重读已经删除的main.ini。

最小修复只把该归属比较变为 `path.resolve().is_relative_to(staging.resolve())`，不改变清理时机、文件创建入口、摘要或验证资格。外部资源仍有原发布前SHA复核分支，原读取入口的link/reparse拒绝代码未修改；比较前是否需要额外复核由本轮独审检查。

读到的Tesla证据为 `../k1-win-ci-candidate/path-diagnostics.json` 与 `k1-short-file-trace-r2.log`：314 UTF16单元main.ini实际曾存在，清理后被重读；lexical归属false/canonical归属true。自己的专项使用真实GetShortPathNameW和samefile，在同一canonical父目录先跑长拼写control、再跑8.3拼写。原实现不足260字符也复现同类误读；扩展>260字符反例 `alias-baseline-r2.log` 准确失败到“writer已存在、清理后不应误读”的断言，候选 `alias-candidate-r2.log` exit0/13，源文件SHA保持。第一次反例的长度门槛不满足日志也保留，不冒充>260验证。

这些是本机同类反例，**原CI未归档完整temp路径，精确因果仍未知**，不能以本例追改原CI结论。新专项是Windows特定测试，缺少真实8.3别名时拒绝，不能把skip算通过；不跑后端。

合并r2已完成本写者全部窄验：默认GUI组件138、真实后端161（初始化及两次3/3）、既有资源包组件529、候选副本compileall exit0。原alias反例exit1/9、候选exit0/13。原始日志及SHA统一在 `revision2-validation-receipt.json`；正式git状态为空。r1窗口38入口证据保持r1范围，不冒充r2新增测试。

## r3：已确认的late-reparse回归与独审中断

Bohr中断前的部分独立证据已确认：外部receipt捕获后变为指向staging的目录reparse point时，base拒绝发布，r2的直接resolve比较却跳过了原拒绝入口并发布。证据在 `../k1-relocation-independent-validation/late-reparse-exits.json` 及两个原始日志；不能因两个观察脚本都exit0就把候选行为算通过，日志明确区分base拒绝/candidate发布。

因此r2不能直接集成。r3只在规范化前沿用已有 `_no_links` 检查，比较为 `_no_links(path).resolve().is_relative_to(_no_links(staging).resolve())`，先拒绝lexical link/reparse组件，再比较8.3/canonical归属。r2原件及收据固定在 `archive-r2/`，r3真实别名专项已exit0/13。r3正常功能专项终态见 `revision3-validation-receipt.json`，不把旧r2报告冒充r3。

Bohr最终独审返回服务端errored：`This content was flagged for possible cybersecurity risk.` 无最终签字，事件完整错误/时间见 `independent-review-incident.json`。未重试、未换agent或改名重投，也未重新执行中断的late-reparse复核脚本。当前r3修复需要进一步独立裁决，不能称完整签字或正式P1关闭。

## 独立复核与集成方案

所有测试均从 `validate.py` 的进程内模块路径overlay加载候选，正式源码不替换。核心/GUI既有测试原断言不删改。主任务解冻后应用一个产品文件、两个专属新测试的patch，登记GUI组件、后端integration及Windows别名专项的准确依赖；各自分配全新证据根。随后在新冻结下补真实Qt加载→初始化→3/3→编辑Undo→保存/恢复观察，不能用本离屏mock代替原P1实窗关闭证据。

独审中断后未再次派发审查；r3未签字，未让Tesla并发写产品文件。父任务实际preflight使用 `out/collab/k1-preflight-visible-inputs/experiment_bundle.py` 固定34db09d9副本，identity记录module_override34与旧HEAD11c92d3；此前旧ab预期被SHAguard正确拒绝，保留原拒绝记录。host session26945、证据 `out/verification/k1-fourth-preflight-visible`，不能把候选覆盖冒称正式冻结或r3。父任务回告geantino零沉积fixture的fields/init已通过、3events进行中；本写者未操作该host，也不据该回告扩大物理验证结论。

复现（仓库根，证据始终在本目录，默认组件模式不使用真实EXE）：

```powershell
$cand = 'C:\Users\123\.codex\worktrees\effective-config\G4UniversalSim\out\collab\k1-relocation-candidate'
$evidence = Join-Path $cand ('evidence\component-review-' + [guid]::NewGuid().ToString('N'))
python "$cand\validate.py" candidate "$cand\files\gui\smoke_tests\smoke_k1_relocation.py" --evidence-root $evidence
$evidence = Join-Path $cand ('evidence\backend-review-' + [guid]::NewGuid().ToString('N'))
python "$cand\validate.py" candidate "$cand\files\gui\smoke_tests\smoke_k1_relocation.py" --mode backend --executable 'C:\Users\123\.codex\worktrees\effective-config\G4UniversalSim\out\build-k1\Release\G4UniversalSim.exe' --source-bundle 'C:\Users\123\.codex\worktrees\effective-config\G4UniversalSim\out\verification\k1-11c92d3\relocated-clean\k1-qt-clean-export' --evidence-root $evidence
```

把加载模式 candidate 换为 baseline、另选新证据根、加 `--counterexample --source-bundle <上面的实窗导出包>` 可复现旧失败。`run_validation.py` 记录本轮全部窄检查；首次执行时要求各证据目录未存在，避免覆盖既有收据。实际消耗未知。


## 两个新增测试最终定稿（仅测试变化，产品5c未改）

父任务已集成固定5c产品及五个旧tests，tracked非clean是预期；本交付基线仍11c，不要求清空父任务修改。只集成 `new-tests.diff` 或复制 `files/` 内两个新测试，**不要重apply基于11c的全产品patch**。`manifest.json` 为最终原始SHA，`final-tests-receipt.json` 为最终日志/退出码/探针收据。父普通测试质量已独立读审通过，最终SHA据本manifest核对；被拒late-reparse独审未完成且未重试/再委托。

两个脚本都可无参数重复运行。未给 `--evidence-root` 时使用独立TemporaryDirectory并完整清理；runner若设置G4USIM_TEST_EVIDENCE_DIR，则在其下生成UUID新目录；显式证据根保留原先不覆盖规则。GUI smoke默认components，只有显式--mode backend才运行实际后端。

最终已执行日志（不重复）：Windows跨平台staging exit0/16；Linux WSL Python3.11.18/PySide6 6.11.1无参数staging exit0/14，实际POSIX symlink拒绝；Windows旧版受控等价staging反例exit1/6，在writer中间文件被误重读处失败；GUI无参数两次均exit0/138。Windows日志明确有真实junction拒绝和真实可用8.3导出；无8.3环境会记录未覆盖8.3，用真实junction拒绝而不伪称8.3。等价staging正例是控制mkdtemp返回真实存在的parent_navigation/..拼写，调用实际exporter，未复制containment算法或放开link策略；不声称它是原Linux/CI生产原因。

此前Windows限定、必须显式根的旧专项脚本已保留在archive-windows-only/test_k1_staging_alias.py；原严格8.3、>260字节长度证据及13入口收据不改。旧r1/r2/r3收据保持各自当时测试字节，不重贴最终wrapper身份；产品5c正常后端161/资源包529的既有验证也保留原范围。

建议父登记：GUI新smoke默认模式到gui层（qt依赖），其--mode backend单列integration（qt/exe依赖）；staging专项可跨平台登记（qt依赖，因复用实际package writer），不再声明Windows-only。未修改正式registry，父任务负责统一冻结。
