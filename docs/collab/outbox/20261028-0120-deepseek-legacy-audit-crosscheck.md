# 历史审计结论对照表：当时说了什么 / 现在还成不成立

核验时间：2026-10-28（UTC+9），核验基线：提交 `8b7721b`（`roadmap/F6-live-progress`，`codex` 已快进）。
执行：DeepSeek（本仓库 DSH 会话）。性质：只读核验，不改被审对象；本文件本身是记录。
判定词表：**仍成立** / **已修复**（当时是缺陷，现在代码与回归已覆盖）/ **部分成立**（方向对，边界或范围已变）/ **已过时**（前提变了，结论不再适用）。

## 0. 先澄清一件事：仓库里没有“Astra 全仓库审计报告”

用户在 2026-10-28 提到“项目最初由 Astra 负责、之前应该做过审计”。实际可查证的是：

| 可能的来源 | 是否存在落盘记录 | 说明 |
| --- | --- | --- |
| Astra 参与的 E2 只读审计（2026-10-27） | 有，`docs/E2多模型审计试运行.md` | Astra 审架构与兼容边界，Sol 审 GUI 校验/生成，主负责人复核 |
| Astra 参与的 F6 设计 + 两次审查（2026-10-27） | 有，`docs/F6接续检查点.md` | 设计协议/架构，审查抓出两个真 bug |
| “Astra 完整读仓库，建立架构图、模块职责和当前问题清单”（2026-10-24 Codex 会话里的建议） | **没有对应产物** | 该建议写在 Codex 会话中，但仓库里没有它的输出；可能只在网页端发生过、未落盘 |
| 更早的阶段规划（A 阶段之前） | 部分，散落在 `docs/多模型协作约定.md` 与 Codex 会话 | 属分工/规划讨论，不是审计结论 |

因此本表把仓库内**所有**历史审计类结论都纳入对照：`总体判断.md`（2026-07-11，用户）、`docs/archive/开发审计与阶段目标.md`（2026-10-03，Codex 现场）、E2（2026-10-27，Astra+Sol）、F6（2026-10-27，Astra 设计+审查）、阶段 0 主审计（2026-10-27，DeepSeek）。若 Astra 在网页端另有一份未落盘的审计，需要它重做或用户提供原文，本表无法替它背书。

## A. `总体判断.md`（2026-07-11，用户旧审计）

| 当时结论 | 现在判定 | 现在证据 | 归入 |
| --- | --- | --- | --- |
| 1. CLI 覆盖顺序有误：`--output/--threads/--seed` 先应用，随后被 INI 覆盖 | **已修复** | M0-1/M0-1b 引入 `SimulationCommandLineOverrides`，`Configure()` 后重应用显式 CLI，并由 Manager 阻止低优先级入口改写；`scripts/test_config_precedence.py` 覆盖配置-only、macro、dry-run、CLI-only、冲突等场景 | — |
| 2. `run_summary.txt` 不是最终有效配置（macro 前写摘要） | **已修复** | 摘要改为只在最终生命周期阶段写，区分计划与实际、记录 `effective_*` 来源快照（`src/Core/SimulationManager.cc` 的 `FinalizeRunSummary`/`effective_config_snapshot_*`），`scripts/test_run_summary.py` 覆盖多次 `beamOn`、失败收尾、目录切换、摘要写入失败 | — |
| 3a. `replica/parameterised/assembly` 解析但永远用 `G4PVPlacement` | **部分成立** | A5 已实现 `replica`/`parameterised`（含切片尺寸、`count×width`、phi 校验）与配套回归 `scripts/test_geometry_a5.py`；`assembly` 仍拒绝，但现在是**配置阶段显式 fail-fast**，不是静默忽略 | 矩阵已如实标注 |
| 3b. region cut 被保存却没应用到 region | **已修复** | A6：`[physics.region.<名称>]` + `cut.gamma|e-|e+|proton` 由 `GeometryManager::ApplyRegionPhysics()` 施加，`scripts/test_physics_a6.py` 覆盖 | — |
| 3c. 材料 `temperature/pressure` 被读取但未传给 `G4Material` | **部分成立** | 仍未实现，但已从“静默忽略”变为闭合 schema 的显式拒绝（M0-3A 专用错误 + 替代建议，`scripts/test_material_schema.py`）；能力等级仍“未支持” | 未做，且有明确边界 |
| 3d. `DoseScorer`/`FluenceScorer` 空实现，`LETcalc` 没有计算来源 | **已过时** | `DoseScorer`/`FluenceScorer`/`LETScorer` 均已实现（实验性），CSV v3 不再输出 `LETcalc`/`LETstep` 零值占位列；回归 `test_dose_scoring.py`、`test_fluence_scoring.py`、`test_let_scoring.py` | — |
| 4. 模块开关没有依赖解析（关 scoring 仍建 hit collection；`enabled=false`+`event_edep=true` 可能输出全零） | **仍成立** | 没有 `off/auto/on`，`scoring.enabled` 与各 scorer 开关之间无依赖推导；只有 PreInit 生命周期门禁，没有一致性校验 | 阶段 2C |
| 5. 输出契约不严（CSV 无单位；`px/py/pz` 在 SD 与 step 路径含义不同） | **已修复** | CSV v3：表头带 `_MeV`/`_mm`，hits 的 `px/py/pz` 明确为方向并写入 `docs/输出数据契约.md`；`--capabilities` 暴露 `csv_units_in_header=true` | — |
| 6. `.gitignore` 忽略整个 `config/`、`macros/`、`test/` 并跟踪 `.o`/ZIP/旧输出 | **已修复** | `.gitignore` 已重写；`git ls-files` 中无 build 产物；`config/`、`macros/`、`test/` 正常跟踪 | — |
| 建议：统一 `EffectiveConfig`（默认 < Profile < main.ini < CLI < macro） | **部分成立** | 优先级次序已落地并有回归，但**不是**完整 `EffectiveConfig`：只有 `effective_config_snapshot_scope=manager_state_subset`、覆盖 12 个启动/几何/源/物理字段，`effective_config_geant4_applied=unknown` | 阶段 2C |
| 建议：模块 `off/auto/on` | **仍成立（未做）** | 无此概念 | 阶段 2C |
| 建议：`--validate-only` / `--print-plan` / `--dump-effective-config` | **部分成立** | `--inspect-run` 提供运行前清单（`G4UniversalSimRunPlan` v1，含主 INI 原文与行号）≈ print-plan；dry-run 覆盖部分 validate；没有导出“每个值来自哪一层”的 `--dump-effective-config` | 阶段 2C |
| 建议：INI 加 `schema_version` 与迁移机制 | **部分成立** | 几何文件支持 `version = 2` 严格模式；主 INI 无 `schema_version` | 阶段 2C |
| 建议：统一 `SolidRegistry`，GUI 从后端能力清单读 | **仍成立（未做）** | 仍是按模板/实体逐个创建；GUI 侧由生成的 `schema_data` 提供部分元数据，但不是 solid 注册表 | 阶段 2B |
| 建议：先做 G4PVReplica/Parameterised，再补 Para/CutTubs/Torus/Ellipsoid/ElTube/Polycone/Polyhedra/Tessellated、GDML | **已完成** | A5 全数落地（实验性）；GDML 经 `GdmlIO` 导入/导出 | — |
| 建议：GUI 拆分 `config_builder_page.py`（>2000 行） | **已修复** | E5：`config_builder_page` 2411→383 行、`main_window` 997→115 行；最大真实 GUI 文件 832 行 | — |
| 建议：主题（浅色/深色/跟随系统）与 i18n（`QTranslator` 运行时切换） | **部分成立** | 主题与 i18n 已实现并有 smoke；但仍有 92 处界面字面量不在 `ZH_CN` 翻译表（集中在 `QFormLayout.addRow` 标签），且无翻译覆盖率断言 | 阶段 2B |
| 建议：“简单/高级”模式 | **仍成立（未做）** | 无此模式 | 阶段 2B |

## B. `docs/archive/开发审计与阶段目标.md`（2026-10-03，Codex 现场审计）

| 当时结论 | 现在判定 | 现在证据 |
| --- | --- | --- |
| `gui/g4usim_gui/output/` 六个 Python 源文件未跟踪、被 `output/` 规则忽略，全新检出不可用 | **已修复** | 现 10 个文件被跟踪（`csv_preview.py`、`dose_summary.py`、`extension_runner.py`、`merge_runner.py` 等） |
| 部分 boolean 配置 fixture 被 `config/` 规则忽略 | **已修复** | `config/geometry/boolean_*.ini` 4 个文件均被跟踪，且 `git check-ignore` 不再命中 |
| `.gitignore` 是唯一暂存文件、不得混入功能提交 | **已过时** | `.gitignore` 早已提交；当前工作区无未提交改动 |
| 旧 `当前开发交接.md`（2026-08-07 快照，`59b24e6`）保留现场 | **已过时** | 已归档 `docs/archive/当前开发交接.md`，加归档 banner 与索引；状态入口改为 `STATUS.md` |
| `总体判断.md` 未跟踪、受保护、保持原样 | **部分成立** | 文件内容未改；但 0.1 快照提交 `67ce037` 把它纳入了 git（当时 `git add -A`）。如需移出版本库请明确指示，我不擅自动它 |

## C. `docs/E2多模型审计试运行.md`（2026-10-27，Astra + Sol）

| 当时结论 | 现在判定 | 现在证据 |
| --- | --- | --- |
| Astra 重点静态审查“未发现可确认的 P0–P2 缺陷” | **部分成立** | 在其声明范围（重点静态审查）内未发现；但 2026-10-27 阶段 0 主审计与后端全量扫描在**动态行为**上找到 5 个同级别缺陷：`[scoring.displacement]` 拼错粒子名静默 DDD=0、主 INI 重复键静默后值覆盖、SD 工厂硬编码名字、`setSeed` 初始化后只重种 master、GUI 编辑 Setup 栏静默重置源几何。前四项已修（`2e87f18`），GUI 项已修（同提交）。教训：静态审查不能替代“跑一遍并断言输出”的反例测试 |
| “没有逐项证明 353 个字段描述/默认值与运行时一致” | **仍成立** | 到现在也没有逐字段运行时对照；`scripts/test_config_schema_context.py --probe-scalars` 只覆盖启动标量 |
| Sol：把 writer 边界检查（单位换算溢出、零半径、直方图边界）纳入正式回归 | **仍成立（未做）** | 那 7 项临时检查没有变成套件用例（无对应 `scripts/test_*.py`）；相邻边界仅由 `gui/smoke_tests/smoke_source_editor_v2.py` 覆盖非有限输入 |
| “未测量 token/费用，不能据此宣称节省成本” | **仍成立** | 跨模型协作至今没有成本量化记录 | 

## D. `docs/F6接续检查点.md`（2026-10-27，Astra 设计 + 两次审查）

| 当时结论 | 现在判定 | 现在证据 |
| --- | --- | --- |
| 行内 marker 会被普通未换行日志前缀吞掉（Astra 抓的 bug 1） | **已修复** | parser 改为跨 chunk 行缓冲，反例在 `scripts/test_live_progress.py` 与 `gui/smoke_tests/smoke_live_progress.py` |
| 零事件缺退出码/摘要、故障终值缺字段可能假通过（Astra 抓的 bug 2） | **已修复** | 终值取 `G4Run::GetNumberOfEvent()`，零事件不补造消息；`docs/实时运行进度.md` 写明“进度不替代 run_result” |
| 性能开销未测 | **已修复（有限结论）** | 阶段 0 成对采样 `performance-final.json`：中位比值 1.0047（min 0.9706 / max 1.0519）；本机漂移约 ±3 %，只能声明“低于测量噪声”，旧 1.068 是漂移假象 |
| 遗留：F2 未启动、旧 1.0.0 安装包早于 F6 不得引用 | **仍成立** | 安装包仍是 2026-10-22 产物；F2 未开始 |

## E. 阶段 0 主审计（2026-10-27，DeepSeek）——已全部闭环，仅作留痕

| 当时结论 | 现在判定 | 证据 |
| --- | --- | --- |
| B1 `[scoring.displacement]` 拼错粒子名 → DDD 恒 0、退出码 0 | **已修复** | `2e87f18`；两阶段校验（配置期能解析就解析，否则 `BeginRun` 用 `G4ParticleTable` 解析），`he3 → He3` 与未知名字带候选失败均有断言 |
| B2 主 INI 重复 section/key 静默后值覆盖 | **已修复** | `[ConfigWarning] duplicate declaration` + `config_duplicate_count`；`scripts/test_config_duplicate_declarations.py` |
| B3 SD 工厂硬编码 `AIHLParticleSD`、detector 命令无状态门禁 | **已修复** | 工厂按配置名创建；`enableSD/setSDName` 仅 PreInit；`scripts/test_command_state_gating.py` |
| B4 `setSeed` 初始化后只重种 master | **已修复** | `AvailableForStates(PreInit)` + `SimulationManager::SetSeed` 防御守卫 |
| GUI Setup 栏编辑静默重置源几何/角分布 | **已修复** | 删掉 `run_config.py` 无条件重置；`gui/smoke_tests/smoke_source_field_preservation.py`（10 个触发点） |
| F6 终态显示 “Progress frozen: success” 等 4 处 | **已修复** | 终态改用 `Result: {state}`；日志三视图行数上限；merged 前缀与 runner 跨 chunk 缓冲 |
| 文档反向错误（README/手册称 LET/GDML/STL/自动合并未实现） | **已修复** | `8b7721b`；`docs/功能支持矩阵.md` 维持“实验性/部分支持”口径 |
| 验收证据全在 gitignore 的 `out/` 里，不可 review | **已修复** | `docs/verification/stage0-20261027/`（report.json、76 个逐用例日志、性能结果、中文 README、exe SHA-256） |

## F. 汇总：仍然成立的旧结论（按阶段归位）

| 编号 | 结论 | 现在状态 | 归入 |
| --- | --- | --- | --- |
| 1 | 模块开关无依赖解析（`scoring.enabled` 等） | 未做 | 阶段 2C |
| 2 | 完整 `EffectiveConfig` 与 `--dump-effective-config` | 只有 12 字段来源快照 | 阶段 2C |
| 3 | INI `schema_version` 与迁移机制 | 未做（几何有 `version=2`） | 阶段 2C |
| 4 | `SolidRegistry` + GUI 从后端能力清单读 | 未做 | 阶段 2B |
| 5 | GUI 翻译覆盖 92 处缺失 + 覆盖率断言 | 未做 | 阶段 2B |
| 6 | “简单/高级”模式 | 未做 | 阶段 2B |
| 7 | writer 边界检查（溢出/零半径/直方图边界）进套件 | 未做 | 阶段 1 剩余项 |
| 8 | 353 字段逐项运行时对照 | 未做 | 阶段 2C |
| 9 | 物理基准多为同源自洽（detector_response、device_dose DDD） | 未做（矩阵已如实标注） | 阶段 2B 屏蔽场景验收时顺带补外部表 |

## G. 请 Astra 确认/撤回（三条）

1. **E2 的“未发现 P0–P2”是否需要补充限定**：现在已知同级别缺陷存在于动态行为而非静态代码面。请确认是否同意“E2 结论只覆盖重点静态审查范围”，并撤回任何被引申为“项目无 P0/P1 缺陷”的解读。
2. **命令族“改缓存、内核没变、退出码 0”的权威分类表**是否仍按原计划输出（这是阶段 1/2 的后端门禁依据；已知已闭合 `detector/enableSD|setSDName`、`app/setSeed`，其余族未审）。
3. **阶段 2B 屏蔽场景（`shielding_coating`）的验收标准**：请给“算到可发布”的最低判据（外部参考表、统计量、剂量率归一化口径、GUI 端到端要证明什么），GUI 交互与视觉由 DeepSeek 负责，不在此列。
