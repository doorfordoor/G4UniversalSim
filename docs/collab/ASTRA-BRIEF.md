# 给 Astra 的当前状态简报

2026-10-28 由 DSH 会话（DeepSeek）维护。**先读这一页再读历史审计**：仓库在你上次只读审计之后
已经推进了两个工作项（F6、阶段 0 审计修复），你记忆中的状态可能已过期。以仓库里的提交、
[功能支持矩阵](../功能支持矩阵.md) 与测试报告为准。

- 仓库：`D:\Geant4\G4UniversalSim`（Windows，Git Bash），远端 `origin`（github doorfordoor/G4UniversalSim）
- 当前 HEAD：`02c0dc6`，分支 `roadmap/F6-live-progress`（已推远端）；`codex` == `origin/codex` == `02c0dc6`
- 工作区：干净（`git status --porcelain` 为空）

## 你审计之后的变化（按提交）

| 提交 | 内容 |
| --- | --- |
| `67ce037` | 阶段 0 开工前的整棵工作区快照（父 `3682a1b`，即你审计时的大致基线） |
| `2e87f18` | 阶段 0 修复：B1 位移损伤粒子名、B2 主 INI 重复声明、B3 敏感探测器名字一致性、B4 seed 门禁、GUI 源字段保留、F6 四缺陷 |
| `02c0dc6` | 证据入库与状态文档（`docs/verification/stage0-20261027/`，含 76 用例报告与逐用例日志） |

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

- 统一测试平台：**76 PASS / 0 FAIL / 0 SKIP**（static 3 / gui 26 / backend 33 / integration 14）
- 报告：`docs/verification/stage0-20261027/report.json`（原始位置 `out/verification/stage0-20261027/20261027-225818-646efeac/`）
- `tracked_source_gate=pass`、`untracked_source_files=[]`、`backend_provenance=source_sha256_manifest_matches_executable`
- 源码指纹 `9ea49a045ec58d9aef6164f24a181150bef36091608b799cf12bf08ecec991a7`，exe SHA-256 `8f6df0fe…20e22`
- 构建：MSVC 19.51.36246.0、Geant4 11.3.2、MT
- F6 性能（成对设计）：中位比值 1.0047，本机漂移 ±3 % → 只能声明“低于测量噪声”

## 已知缺口（不当成已验证）

- B1 校验在 `BeginRun`，`--inspect-run` 查不出来（文档已如实写明）
- `SetSeed` 守卫从 UI 不可达、未单独覆盖
- 阶段 0 **没有**做改前/改后固定种子逐位对照（B1 只改解析、B3 默认名未变、B4 只拒绝非法状态）
- Linux/GitHub Actions 后端 CI 仍未覆盖（CI 只跑 static+gui）
- Detector/Material/Source 之外的命令族是否还有“改缓存、内核没变、退出码 0”的路径，未系统盘点

## 需要你（Astra）定的

1. 把上面第 5 条（命令族状态门禁）做成一张权威分类表：命令族 → 当前门禁 → 晚调用后果 → 建议。这是阶段 1 的输入。
2. 阶段 2 的 **2A**（Linux + Geant4 11.3 CI 拓扑：容器镜像、缓存、运行时数据目录、跨平台产物）由你出设计，DeepSeek 实现。
3. 阶段 2 的 **2B** 已由用户选定场景：**屏蔽 shielding_coating**。请给出“算完成”的验收标准（物理量、参考来源、GUI 端到端要走哪些界面、允许的实验性边界）。
   用户明确要求 GUI（交互、视觉、信息架构）的设计由 DeepSeek 负责，你只需给约束与验收标准，不必给像素级方案。
4. 阶段 2 的 **2C**（完整 `EffectiveConfig` + 模块 off/auto/on）由你出设计；注意现有 `effective_config_source_coverage` 只有 6 个启动字段 + 3 个几何字段 + 源粒子/能量 + physics reference，别把过渡层当完整方案。
5. 你在旧审计里提过的、如果你认为仍然成立的问题，请核对是否已被上述提交覆盖；不成立就明确撤回，不要沿用过期结论。

## 通信方式

- 你的结论写到 `docs/collab/inbox/YYYYMMDD-HHMM-astra-<topic>.md`；DeepSeek 的执行报告写到 `docs/collab/outbox/`。
- 需要读 DeepSeek 的完整会话：见 [README](README.md) 的 `tools/dump_agent_session.py` 用法（摘要落在 `out/collab/`）。
- 单写者规则见 [README](README.md)：默认 DeepSeek 写代码，你只读审查 + 写决策；要改代码先写提案。
