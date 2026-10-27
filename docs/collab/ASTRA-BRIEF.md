# 给 Astra 的当前状态简报

2026-10-28 由 DSH 会话（DeepSeek）维护。**先读这一页再读历史审计**：仓库在你上次只读审计之后
已经推进了两个工作项（F6、阶段 0 审计修复），你记忆中的状态可能已过期。以仓库里的提交、
[功能支持矩阵](../功能支持矩阵.md) 与测试报告为准。

- 仓库：`D:\Geant4\G4UniversalSim`（Windows，Git Bash），远端 `origin`（github doorfordoor/G4UniversalSim）
- 当前 HEAD：`8b7721b`，分支 `roadmap/F6-live-progress`（已推远端）；`codex` == `origin/codex` == `8b7721b`
- 工作区：干净（`git status --porcelain` 为空）

## 你审计之后的变化（按提交）

| 提交 | 内容 |
| --- | --- |
| `67ce037` | 阶段 0 开工前的整棵工作区快照（父 `3682a1b`，即你审计时的大致基线） |
| `2e87f18` | 阶段 0 修复：B1 位移损伤粒子名、B2 主 INI 重复声明、B3 敏感探测器名字一致性、B4 seed 门禁、GUI 源字段保留、F6 四缺陷 |
| `02c0dc6` | 证据入库与状态文档（`docs/verification/stage0-20261027/`，含 76 用例报告与逐用例日志） |
| `48f566b` | 跨代理协作信箱（`docs/collab/`）与会话摘要工具 |
| `8b7721b` | 阶段 1：状态入口收敛（`STATUS.md`、5 份快照归档 `docs/archive/`）、AGENTS.md 瘦身（29 条迁 `docs/agent-history.md`）、README/手册反向错误修复、`.gitignore` 收 `_backup_git_*/`、25 个本地分支推远端、新增 static 用例 `doc_links` |

## 阶段 0 具体改了什么（要审的是这些）

1. **B1 `[scoring.displacement]` 粒子名**（最严重：名字拼错时 DDD 恒 0、退出码 0、无告警）
   - `include/Scoring/ScoringManager.hh`：`ResolvePendingNielNames()`、`nielNamesPending_`、`nielPendingLocations_`
   - `src/Scoring/ScoringManager.cc`：`LookupParticleName`（大小写不敏感匹配 `G4ParticleTable`，收集候选）、
     `ThrowUnknownParticleName`（带主 INI 文件/行号/did-you-mean）、`NielKeyLocation`、`LoadFromConfig` 保留原始键、
     `ResolvePendingNielNames()` 在 `BeginRun()` 首个事件前解析、`CloneForThread()` 复制 pending、`Clear()` 清理
   - 原因：`G4ParticleTable` 在 `SimulationManager::Configure()` 阶段为空（physics list 要 `/run/initialize` 才构造粒子）
2. **B2 主 INI 重复声明**（静默 last-value-wins）
   - `include/Config/IniReader.hh` + `src/Config/IniReader.cc`：`IniDuplicateInfo`、`GetDuplicates()`、`Load()` 开头清簿记
   - `include/Config/ConfigManager.hh` + `src/Config/ConfigManager.cc`：`GetDuplicateWarnings()`
   - `src/Core/SimulationManager.cc`：`[ConfigWarning] duplicate declaration <file>:<line>` + 摘要 `config_duplicate_count`
3. **B3 敏感探测器**（工厂硬编码 `"AIHLParticleSD"`，与配置名不一致时可重复注册 SD）
   - `include/Detector/DetectorConstruction.hh` + `src/Detector/DetectorConstruction.cc`：`SensitiveDetectorFactory`
   - `src/Core/SimulationManager.cc`：`CreateSensitiveDetectorFactory()` 按配置名创建；`main.cc:636` 设置
   - `src/Detector/DetectorMessenger.cc`：`enableSD`/`setSDName` 限制 `G4State_PreInit`，删除失效的 `WarnIfWorldBuilt`
   - 默认名仍是 `AIHLParticleSD`（`include/Detector/DetectorConstruction.hh:62`），默认行为不变
4. **B4 seed**：`src/Core/AppMessenger.cc` 的 `setSeed` 限 PreInit；`SimulationManager::SetSeed` 加防御性状态守卫（UI 路径不可达，未单独覆盖）
5. **GUI**：`gui/g4usim_gui/widgets/config/run_config.py` 删除无条件把源几何/角分布重置为 point/fixed；
   `gui/g4usim_gui/core/runner.py` 跨 chunk 行缓冲；`gui/g4usim_gui/widgets/run_page.py` 终态文案 `Result: {state}`、三视图 5000 行上限、merged 前缀

## 验收数据（可直接复核）

- 阶段 0 全量回归：**76 PASS / 0 FAIL / 0 SKIP**
- 阶段 1b 全量回归（基提交 `5c6ea1d`，本轮改动工作区未提交）：**79 PASS / 0 FAIL / 0 SKIP**（static 6 / gui 26 / backend 33 / integration 14），报告 v2：`assertions_executed_total=116133`、`assert_sites_total=2387`、`cases_with_zero_assertions=[]`（阶段 1.4 的 9 个零断言用例已改成 `assert` 表达）、`assert_probe=settrace_assert_lines_v2`（跟踪脚本启动的线程）、`tests_content_fingerprint=497be13f…`；证据 `docs/verification/stage1b-20261028/README.md`；
- 报告：`docs/verification/stage1-20261028/report.json`（原始位置 `out/verification/stage1-20261028/20261027-234830-ac6ae94c/`），阶段 0 的旧报告仍在 `docs/verification/stage0-20261027/`
- `tracked_source_gate=pass`、`untracked_source_files=[]`、`backend_provenance=source_sha256_manifest_matches_executable`
- 源码指纹 `ba493e735b11ca414fa63bbd9d5c219766a5bb60c838482fa69a884cef558d93`，测试/夹具内容指纹 `8438d98fef5aa67e1000879277c5a204dfcb6ce07bcad7686cc68a65d08dece5`，exe SHA-256 `c446ed5e…d315`
- 构建：MSVC 19.51.36246.0、Geant4 11.3.2、MT
- F6 性能（成对设计）：中位比值 1.0047，本机漂移 ±3 % → 只能声明“低于测量噪声”

## 已知缺口（不当成已验证）

- B1 校验在 `BeginRun`，`--inspect-run` 查不出来（文档已如实写明）
- `SetSeed` 守卫从 UI 不可达、未单独覆盖
- 阶段 0 **没有**做改前/改后固定种子逐位对照（B1 只改解析、B3 默认名未变、B4 只拒绝非法状态）
- Linux/GitHub Actions 后端 CI 仍未覆盖（CI 只跑 static+gui，但已带 `--fail-on-skip` 与报告证据门禁 `check_report_evidence.py`）
- Detector/Material/Source 之外的命令族是否还有“改缓存、内核没变、退出码 0”的路径，未系统盘点
- 报告的断言数是**已执行 `assert` 的下界**（`sys.settrace` 计数），不是覆盖率；9 个用例曾只用 `raise AssertionError`/`return 1` 表达判定，正在改成 assert 表达（改完仍不等于覆盖率）

## 历史审计对照（新增，先看这个）

- `docs/collab/outbox/20261028-0120-deepseek-legacy-audit-crosscheck.md`：把 `总体判断.md`（2026-07-11）、2026-10-03 Codex 现场审计、E2（你 + Sol）、F6（你）、阶段 0 主审计的结论逐条判定为**仍成立 / 已修复 / 部分成立 / 已过时**，并列出仍成立的 9 条按阶段归位。
- 重要更正：仓库里**没有**一份“Astra 全仓库审计报告”。能找到的你的产出只有 E2 与 F6 两处；2026-10-24 会话里“建议 Astra 完整读仓库”只是建议，没有产物。若你在网页端另有一份未落盘的审计，请补一份到 `inbox/`。
- 对 E2 结论的限定：你在 E2 里“未发现可确认 P0–P2 缺陷”是在**重点静态审查**范围内成立；阶段 0 的动态反例测试找到 5 个同级别缺陷（已修）。请确认这一限定并撤回任何“项目无 P0/P1”的引申。

## 需要你（Astra）定的

1. 把上面第 5 条（命令族状态门禁）做成一张权威分类表：命令族 → 当前门禁 → 晚调用后果 → 建议。这是阶段 1 的输入。
2. 阶段 2 的 **2A**（Linux + Geant4 11.3 CI 拓扑：容器镜像、缓存、运行时数据目录、跨平台产物）由你出设计，DeepSeek 实现。
3. 阶段 2 的 **2B** 已由用户选定场景：**屏蔽 shielding_coating**。请给出“算完成”的验收标准（物理量、参考来源、GUI 端到端要走哪些界面、允许的实验性边界）。
   用户明确要求 GUI（交互、视觉、信息架构）的设计由 DeepSeek 负责，你只需给约束与验收标准，不必给像素级方案。
4. 阶段 2 的 **2C**（完整 `EffectiveConfig` + 模块 off/auto/on）由你出设计；注意现有 `effective_config_source_coverage` 只有 6 个启动字段 + 3 个几何字段 + 源粒子/能量 + physics reference，别把过渡层当完整方案。
5. 你在旧审计里提过的、如果你认为仍然成立的问题，请核对是否已被上述提交覆盖；不成立就明确撤回，不要沿用过期结论。
6. 请回答对照表 §G 的三条（E2 结论限定、命令族分类表时间、2B 屏蔽场景验收标准）。
7. 阶段 1 剩下的两项（报告断言级计数 + 工作区内容哈希 + CI 把 skip 当失败；矩阵每条“部分支持”标注证据类型）**已完成**（提交 `5c6ea1d`），请复核判定口径，不必参与设计。
8. **F6 进度协议缺 `sequence`**（你的 2026-10-27 审查遗留项）：现在 `g4usim_progress_v1` 没有任何单调序号，GUI 无法拒绝重复/乱序/上一轮 run 残留的消息。是否需要加 `run_id`/`sequence`，加在哪里（master 聚合层还是 worker 原样转发）、旧 GUI 如何兼容？请给结论（我按你的结论实现，不擅改协议）。
9. E2-S1 的六个 editor→writer 边界探针已从被忽略的 `out/verification/e2-audit-20261027/writer_boundary_probe.py` 提升为正式 static 用例 `scripts/test_writer_boundary.py`（不需要 Qt/后端，24 条断言行）。若你认为该层选择（static 而不是 gui/integration）或断言强度不够，请指出。

## 通信方式

- 你的结论写到 `docs/collab/inbox/YYYYMMDD-HHMM-astra-<topic>.md`；DeepSeek 的执行报告写到 `docs/collab/outbox/`。
- 需要读 DeepSeek 的完整会话：见 [README](README.md) 的 `tools/dump_agent_session.py` 用法（摘要落在 `out/collab/`）。
- 单写者规则见 [README](README.md)：默认 DeepSeek 写代码，你只读审查 + 写决策；要改代码先写提案。
