# G4UniversalSim 状态（唯一入口页）

更新：2026-10-29。本页只做导航与快照；**阶段状态以 [docs/ROADMAP.md](docs/ROADMAP.md) 为准，支持等级以 [docs/功能支持矩阵.md](docs/功能支持矩阵.md) 为准**，两者冲突时先改事实再改文档。

## 一句话定位

配置驱动、可复现、可验证的 Geant4 桌面工作台（C++17 后端 + PySide6 前端 + 场景包/基准/测试平台）。
当前是"有真实物理验证的 Beta"，不是 1.0：核心链路可用，大量高级能力仍是实验性，产品完成度低于工程纪律。

## 当前计划入口（2026-10-29 编号整理）

统一工作项、排期波次、依赖、Q1 审查范围与提交节点均在 [ROADMAP](docs/ROADMAP.md) 的“统一代号与排期”一节。本对话作为 **Q1 完整可靠性审查、修复与验收**的主负责人；隔壁审查作为独立证据来源，不必等它全部结束。已有反例按代码基线复用；Q1 已在冻结范围完成验收，见[最终报告](docs/verification/q1-final-20261029/README.md)。

当前顺序：Q1（已完成）→ 2C/E6 → F1/F4/F5/K1（I1 可并行）→ I2/J1/F8 → L1/F2；其后科研波次 Q2/H2/H3、F3/F7、E7/J2，与 K2/L2 按依赖安排；H4–H9 和 M5 保留后续独立阶段。这是导航摘要，具体状态与默认顺序以 ROADMAP 为准。用户一次启动一个完整代号，阶段内的提交和专项测试由负责人连续推进。

2026-10-29 Q1已完成：九域审查、R01–R32闭合并交叉复核；验收代码 `8ecad66`。干净Windows **105 PASS / 0 FAIL / 0 SKIP**，83770个v3入口；旧同代98项基线79303，逐例/总数与原始日志门禁通过。Linux11.3.2/11.4.3真实CI各105（run40855144863），Windows/Ubuntu static+GUI各42（run40855144672），Windows实窗保存/生成/运行/取消/关窗通过。[完整收据](docs/verification/q1-final-20261029/README.md)；旧失败证据保留，历史偏置结果须重跑，原生交互迁移显式csh。

## 2026-10-29 隔离开发工作区与2C子集历史

用户授权 Astra 主导 2C 实现。当前工作区 `C:\Users\123\.codex\worktrees\effective-config\G4UniversalSim`，基线 `5465dbd`，分支 `roadmap/2c-effective-config`；原 D 盘工作区由 DSH 保留，禁止并发合并。实施契约见 [2C 开工回信](docs/collab/inbox/20261029-1010-astra-2c-execution.md)。DeepSeek 已通过 API 提供前端设计，采纳范围与纠偏见 [前端设计建议](docs/collab/outbox/20261029-1010-deepseek-effectiveconfig-ui-design.md)。

独立数据模型、配置阶段导出与只读查看器已接通；完整消费者覆盖、三阶段应用证据与 off/auto/on 尚未完成，不提升支持等级。原基线 87 项归档报告已在本轮通过严格证据门禁复核。

2C子集历史验收（旧探针计数，不与Q1 v3直接比较）：MSVC + Geant4 11.3.2 构建成功；最终两组覆盖统一平台全部 **89 PASS / 0 FAIL / 0 SKIP，117149 条断言**，另有独立模型 24 条。两组报告源码/测试指纹一致，逐用例断言非零，归档日志 SHA-256 与严格门禁通过；见 [验收记录](docs/verification/2c-configured-20261029/README.md)。初轮两项环境失败原样保留，已使用已有 GDML/数据根参数复测，未放宽测试。真实导出数据的浅色/深色/小窗口 offscreen 图已查看，不等同桌面与高 DPI 验收。

当前 2C 代码范围：`Config/EffectiveConfig` 类型化事务与不可变快照、`--dump-effective-config` 独占新文件/标准输出、GUI 第 9 页只读查看器；完整 2C 继续进行中。上轮收尾收到独立审查，csh 拒绝主配置切换后仍报成功（R-01，P1）、元数据写失败但文本摘要仍成功（R-02，P2）在 70a1aba 重新复现；旧反例见 [修前证据](docs/verification/m0-known-defects-20261029/README.md)。它们当时未被已有 89 项覆盖，本轮已补正式回归并修复，见下段。

2026-10-29 R-01/R-02阶段历史验收：Release 构建、**89 PASS / 0 FAIL / 0 SKIP，117833 条断言**，严格证据门禁通过，见 [修复报告与日志](docs/verification/reliability-r01-r02-20261029/README.md)。维持拒绝配置热切换；metadata 异常纠正可写文本摘要并排除失败产物，不承诺跨文件原子性。该节点当时未做Linux/11.4/安装包验收；后续当前源码Linux/11.4证据见上方Q1，安装器扩展仍归I2。

R03–R32现已完成修复与回归，旧[反例证据](docs/verification/r03-r04-current-20261029/README.md)和提案保留为历史。V01方法边界已裁决，统计适用范围后续归Q2。下一完整工作项是[2C](docs/EffectiveConfig.md)，五项新增目标与E/F/H依赖继续遵循[ROADMAP](docs/ROADMAP.md)；不因Q1通过宣布这些阶段完成。

## 原 DSH 集成基线（2026-10-28 归档，2C 新工作区见上节）

- 分支 `roadmap/F6-live-progress`，集成分支 `codex`（快进合并后推送）；`main` 为早期历史分支。
- 阶段 0 审计修复已交付：提交 `67ce037`（工作区快照）→ `2e87f18`（静默失败路径）→ `02c0dc6`（验收证据与状态）→ `48f566b`（跨代理协作信箱）→ `8b7721b`（阶段 1 文档与仓库卫生）→ `c80a9cf`（历史审计对照表）→ `5c6ea1d`（阶段 1.4 报告 v2 与证据门禁）→ `f1dad9d`（阶段 1b 零断言清零与 writer 边界用例）→ `48d8c68`（阶段 1b 证据与状态收尾）→ `7f5dc48`（阶段 1d 证据门禁自洽性与日志摘要按落盘字节）→ `32736c9`（阶段 1e 命令失败传播 D-4/D-5/D-6）→ `de1ea93`（Linux 构建与 CI workflow、双平台验证）→ `976ce9e`（CI workflow 的 `runner` 上下文修复）→ `dc03a1b`（D-7 屏蔽场景证据语义）→ `dbd72cf`（失败用例公开注解）→ `a5970ff`（Qt 插件修复，GitHub Actions 转绿）→ `3291145`（GUI 路径比较）→ `b45d325`/`088761d`（四 profile 绿记录与 Astra 信）→ `960d683`（2B 场景模型）→ `f00bb30`（headless 驱动 + `analyze(output_dir)`）→ `a96d957`（Scenario 页）→ `719f1df`（端到端 smoke）→ `7834784`（NIEL 溯源）→ `402a9f2`（2B CI 回归修复）→ `45891c3`（2B 证据与文档、`platform_paths` 守门）→ `2feddfc`（记录双 workflow 全绿）→ `92bb98a`（2C 现状测绘）→ `5d6b94e`（STATUS 指向测绘）→ `97036df`（Geant4 11.4 数据集表与版本无关测试）→ `6a8b237`（Linux CI 版本矩阵）→ 本提交（11.4 结论与证据）。HEAD 以 `git log` 为准。
- 最近一次完整回归（Geant4 11.4 支持 + CI 版本矩阵，严格证据门禁）：**87 PASS / 0 FAIL / 0 SKIP**，`profile=all`，`version=2`，`assertions_executed_total=116677`、`assert_sites_total=2702`、`cases_with_zero_assertions=[]`、`assert_probe=settrace_assert_lines_v2`、`log_digest_algorithm=sha256_raw_bytes_lf_v2`、`skip_policy=failure`、`tracked_source_gate=pass`、`untracked_source_files=[]`、`backend_provenance=source_sha256_manifest_matches_executable`。
  - 报告与 87 个逐用例日志：[docs/verification/stage-11d4-20261028/README.md](docs/verification/stage-11d4-20261028/README.md)（2B 交付基线见 [stage2b](docs/verification/stage2b-20261028/README.md)、F6 `sequence` 基线见 [stage2b-f6](docs/verification/stage2b-f6-20261028/README.md)）；更早证据见 [stage1j](docs/verification/stage1j-20261028/README.md)、 [stage1f](docs/verification/stage1f-20261028/README.md)、[stage1e](docs/verification/stage1e-20261028/README.md)、[stage1d](docs/verification/stage1d-20261028/README.md)、[stage1b](docs/verification/stage1b-20261028/README.md)（旧摘要口径，只能加 `--allow-legacy-digest` 复核）、[stage1](docs/verification/stage1-20261028/README.md)、[stage0-20261027](docs/verification/stage0-20261027/README.md)。
  - 源码指纹 `3ad03f2d62c354323f86edeb57c4479219ad75ca568ce3f8b3037c3c5d49aca9`、测试/夹具内容指纹 `4eca0c97e22d4e45310b13e8ae3d556d2ceb8e1bfeb63906a43b4dd9cb857d02`；后端 `G4UniversalSim.exe` SHA-256 `f78fa2fb06c08dbebd590bf7457f306ec85d9d6a7a8c0f0b30f5b7daeb6b45e1`（1734656 B）；构建身份 MSVC 19.51.36246.0 + Geant4 1132 + MT。
  - 报告运行时 `git_head=6a8b237`、`git_dirty=true`（本轮 `src/Core/Geant4DataLocator.cc` 的 11.4 分支在运行前未提交）。
- Linux 验证：①本机 WSL（Ubuntu 24.04.4 + conda-forge Geant4 11.3.2 + g++ 13.3）backend **35/35**、integration **14/14** 全通过（backend 在 2B 后按 `G4USIM_EXE` 修复重跑，109970 断言），证据 [docs/verification/linux-wsl-20261028/README.md](docs/verification/linux-wsl-20261028/README.md)；③**Geant4 11.4（实验性）**：本机 WSL 11.4.3 构建成功、四个 profile 87/87 全过（backend 109,942、static 391、GUI 1,877、integration 4,364 断言），见 [docs/Linux构建与验证.md](docs/Linux构建与验证.md) §8；`linux-geant4.yml` 已加版本矩阵（11.3.2 / 11.4.3）。②**GitHub Actions 四 profile 全绿**（`3291145` 的 `codex` run [40640355033](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40640355033) 与 roadmap run [40640350911](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40640350911)，`ubuntu-24.04` 上 static / offscreen GUI / backend / integration 各自过证据门禁，另有篡改副本负向对照；更早的 `a5970ff` 只覆盖 backend+integration），构建过程、两个 GCC-only 缺陷、PySide 退出 `SIGSEGV` 与五个 CI-only 缺陷的修法见 [docs/Linux构建与验证.md](docs/Linux构建与验证.md)。
- 测试平台：`python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip`；87 个用例 = static 10 / gui 27 / backend 35 / integration 15，所有用例都报告非零断言数；报告是 `version: 2` 证据（逐用例断言数、双指纹、`log_sha256` 按落盘字节），`scripts/check_report_evidence.py` 为 CI 门禁（逐项断言 ≥1、求和/计数/零断言列表一致、摘要与磁盘字节一致、发布报告无 fail/skip，归档旧报告需 `--allow-legacy-digest`）。
- CI 现状：`.github/workflows/linux-geant4.yml` 现用 Geant4 版本矩阵（`11.3.2` / `11.4.3`，每版本独立前缀、报告根与 artifact；11.4 leg 传 expat/zlib/freetype 的六个 `-D*` 参数），`6a8b237` 上 `ubuntu-24.04 / Geant4 11.3.2` 与 `ubuntu-24.04 / Geant4 11.4.3` 两个 job 各 26 步全绿（run [40690078563](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690078563) / [40690070991](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690070991)）。更早的事实：`ubuntu-24.04` + conda-forge Geant4 11.3.2，构建后依次跑 static / offscreen GUI / backend / integration 四个 profile（各自 `--report-root`、`--fail-on-skip`、证据门禁、`if: failure()` 注解），随后用篡改副本验证门禁必须拒绝，最后 `if: always()` 上传 artifact；跨平台指纹一致。`.github/workflows/m0-static-gui.yml`（Windows/Ubuntu 的 static+gui）已由仓库所有者启用，`402a9f2` 上 **ubuntu 与 windows 双平台全绿**（run [40675415994](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40675415994) / [40675409885](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40675409885)，各 15 步）；此前 2026-10-23 的失败是 Windows-only GUI 断言比较错误，已由 `402a9f2` 修好。**两条 workflow 在 `45891c3` 上同时全绿**：M0 run [40680571889](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40680571889) / [40680563877](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40680563877)（ubuntu + windows 的 static 与 offscreen GUI），Linux run [40680571833](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40680571833) / [40680563958](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40680563958)（static / offscreen GUI / backend / integration 四 profile + 证据门禁 + 篡改负向对照 + artifact）。Linux backend 首次包含 2B 的 `scenario_shielding_core` 并通过。

## 阶段状态（摘要，详表见 ROADMAP）

- A 核心功能、B 场景包与基准、C 向导/绘图/扫描、D 安装包、G 3D 预览：已完成。
- E 修复：E1（GUI 与后端规则一致）、E2（配置 schema）、E3（Linux CI，含 Geant4 11.3.2 / 11.4.3 版本矩阵）、E5（GUI 拆分）已完成（E3 见 ROADMAP 的“done for Linux”；M0 workflow 已由所有者启用并在 `402a9f2` 双平台全绿；11.2 未测）；E4 已做部分规范迁移和链接检查，仍需收尾；新增 E6/E7 的范围见 ROADMAP。
- F 优化：F6（实时运行进度）已完成，2026-10-28 追加可选 `sequence`（进程级单调、跨 run 不重置，GUI 拒绝重复/回退行；旧后端仍可解析），契约见 [docs/实时运行进度.md](docs/实时运行进度.md)；F1 输出与来源、F2 运行会话、F3 性能/tasking、F4 校验定位、F5 undo/autosave、F7 二维扫描、F8 GUI 收尾未做。
- H 增量：H1（径迹输出）已完成；H2–H9（过滤计分、平行世界、方差降低、光学、活化、DNA、体素体模、通用直方图）未做。
- M0 全模块 EffectiveConfig / 模块开关归 2C（已有子集）；SolidRegistry 归 E7，仍未实现。M0–M5 是长期目标汇总，不与新工作项重复计算完成度。

## 阶段 2B（屏蔽/涂层场景 GUI 端到端，已完成 2026-10-28）

- 命令行生成器提炼为 `scenarios/shielding_coating/scenario_model.py`（`ShieldingSpec`、`problems()`、`render()`、`generate()`），`make_scenario.py` 保持 CLI 契约；分析侧 `analyze.analyze(output_dir)` 供 GUI 复用。
- 新增 Scenario 页（15 字段三层校验、生成、QProcess 运行、结果表五列带证据、DDD 行显示 NIEL 表路径与 sha256、中英切换）与 headless 驱动 `gui/g4usim_gui/core/scenario_shielding.py`；12 步端到端 smoke 走 offscreen Qt + 真后端 200 事件。
- NIEL 溯源写入 `scenario.json` 的 `niel: [{particle, path, sha256}]` 并进入分析报告 `evidence.niel_tables`；缺证据仍沿用 D-7 语义（退出码 3，不写零报告）。
- 新增用例 `shielding_scenario_model`、`shielding_analysis`、`scenario_shielding_core`、`scenario_page`、`gui_scenario_backend`，并加 static 守门 `platform_paths`。契约与限制见 [docs/屏蔽涂层场景端到端.md](docs/屏蔽涂层场景端到端.md)。

## 正在做 / 下一步

阶段 1（文档与仓库卫生，进行中）：

1. 已完成：修文档里的反向错误（README 与中文使用手册中“LET/GDML/STL/自动合并未实现”的旧说法）；
2. 已完成：`STATUS.md` 单一入口 + 5 份过期快照归档 `docs/archive/`（含 [归档索引](docs/archive/README.md)）；
3. 已完成：`_backup_git_*` 进 `.gitignore`、25 个本地分支推远端（CI 从零变为逐分支可触发）；
4. 已完成：`AGENTS.md` 48.5 KB → 33.5 KB（29 条日期条目全文迁入 `docs/agent-history.md`，只留索引）、`docs/Agent维护说明.md` 文档地图重写、新增 static 用例 `doc_links`（53 个 Markdown 文件 100 条相对链接全部可解析）；
5. 已完成：历史审计结论对照表 [docs/collab/outbox/20261028-0120-deepseek-legacy-audit-crosscheck.md](docs/collab/outbox/20261028-0120-deepseek-legacy-audit-crosscheck.md)（`总体判断.md`、2026-10-03 现场审计、E2、F6、阶段 0 逐条判定为仍成立/已修复/部分成立/已过时，仍成立的 9 条按阶段归位）；
6. 已完成：报告加断言级计数与工作区/测试内容双哈希、默认报告目录改 `out/verification`、CI 把 skip 当失败（`--fail-on-skip` + `check_report_evidence.py` 门禁）；顺带修复 `.gitattributes` 让 checkout 换行改变源码指纹的真实缺陷；
7. 已完成：支持矩阵第 2–3 节每条功能标注证据类型（外部表 / 解析式 / 同源自洽 / 自测 / 未验证），第 1 节给出判定口径；
8. 已完成：E2-S1 六个 editor→writer 边界升级为 static 用例 `writer_boundary`；9 个零断言用例改写成 `assert` 表达（断言证据从 115305 增至 116133，零断言列表清空）。
9. 已完成：Astra 2026-10-28 审查的 6 条缺陷全部闭合（D-1 证据门禁可篡改绕过、D-2 日志摘要与磁盘字节不符、D-3 文档漂移、D-4 交互偏置拒绝只告警、D-5 材料交互无生命周期门禁、D-6 `ParseStrictDouble` 接受 inf/nan）。
10. 已完成：D-7（`scenarios/shielding_coating/analyze.py` 缺证据当零结果）闭合——运行事实不达标即退出码 3 且不写报告，统计文件用 `run_metadata.json` 的 `generated_files` 区分“被删”与“真零”，相空间跨轮次/越界为证据错误，报告新增 `evidence` 段，回归含五种反例。
11. 已完成：E3 Linux CI 在真实 Actions 上转绿（四 profile + 注解 + 篡改负向对照），并顺带修掉三个 CI-only 缺陷（job 级 `env` 上下文、conda Qt5 插件遮蔽 PySide6 Qt6 插件、公开仓库日志不可读）。

阶段 2（2B 场景已定为**屏蔽 shielding_coating**）：

- 2A：Linux + Geant4 11.3/11.4 CI（E3）——已完成（Actions 双版本矩阵绿，见上）；遗留 11.2 兼容性；
- 2B：屏蔽场景 GUI 端到端 + schema 驱动编辑器——**已完成（2026-10-28，见上节）**；
- 2C：完整 EffectiveConfig + 模块 off/auto/on（Astra 主导设计）——原 DSH 基线的**只读测绘**见 [docs/collab/outbox/20261028-2000-deepseek-effectiveconfig-survey.md](docs/collab/outbox/20261028-2000-deepseek-effectiveconfig-survey.md)：
  现状（13 个 `effective_*` 标量、11 个来源字段、materials 六态、19 个 main_ini section、散落布尔开关、缺 `--dump-effective-config`）、
  六条缺口（无对象 ID、无 requested/resolved/applied 四元组、缺 BeginOfRun 快照、无 off/auto/on 语义、GUI 无结构化入口、验收只能数 353 字段），
  以及当时的切片建议与五个待 Astra 决定的问题。隔离分支现已实现 configured 子集，见本页开头；不能再将当时“未写代码”的状态应用于当前隔离分支。
- 铁律：阶段 2 冻结新功能，目标是压低 `experimental` 比例，而不是扩大分母。

## 已知缺口（不要把以下当作已完成）

- 后端名字校验类错误可能在"首个事件前"才发现（例如 `[scoring.displacement]` 的粒子名在 `BeginRun` 校验，`--inspect-run` 查不出）。
- 配置面 353 个字段中 supported 59 / experimental 287 / deprecated 5 / unsupported 2；有 `gui` 元数据的 57 个字段（generated 17 / generated_subset 30 / external_only 5 / legacy_external 2 / fixed_or_blocked 2 / fixed_false 1），其余 296 个字段没有任何 GUI 编辑路径。
- 探测器响应、Dose/Fluence/DDD 等基准多为"同源自洽"或"解析式"，缺少第三方独立数据与实测效率对照。
- 偏置只有 process-level XS 路径；importance、weight-window、splitting、Russian roulette 未实现。
- 交互命令审计只覆盖 `--ui --ui-session csh`；Qt UI 与部分嵌套/动态命令不受审计保证。
- 安装包 `out/` 中 1.0.0 早于 F6/阶段 0 改动，不可作为当前版本引用。
- 屏蔽/涂层场景只覆盖法向入射平板几何与 15 个字段：未做角度分布、非平板几何、光核/活化；TID/DDD 沿用 B2/B3 定义，不是新的物理基准。
- 测试脚本的跨平台约束靠 static 用例 `platform_paths` 守门（提到 `build_vs2026` 必须同时读 `G4USIM_EXE`），不保证其它手工脚本。
- 命令族的“改了缓存、内核没变、退出码 0”三条路径已闭合（Astra 2026-10-28 审查 D-4/D-5/D-6）：交互会话里的 biasing 修改被拒绝时计入 csh 失败（`interactive_command_failure_kind = biasing`）并停止会话、material 的 9 个变更命令只允许 `PreInit`（初始化后由 Geant4 拒绝 → `geant4_illegal_application_state`）、`ParseStrictDouble` 拒绝 `inf`/`nan`/溢出。只覆盖脚本化 `--ui --ui-session csh`；Qt UI 内的同类操作仍未自动化验收。
- Geant4 版本：11.4.3 已进 Linux CI 矩阵并在 Actions 上绿，但本机 Windows 只有 11.3.2——Windows + 11.4 与 11.4 下的真实桌面 GUI（非 offscreen）、ROOT/uproot、打包流程均未验证；Geant4 11.2 未测。
- Actions 日志需登录才能下载：失败用例只能靠公开注解（`scripts/ci_annotate_failures.py`）与 artifact 诊断，注解不是完整日志。
- 断言证据是**已执行 `assert` 的下界**（`sys.settrace` 计数），不是覆盖率；证据门禁只证明“报告与日志自洽且未被篡改”，不证明断言写得好。
- F6 进度协议的可选 `sequence` 已补（2026-10-28）：`[G4USimProgress]` 每条消息带进程级单调序号（跨 run 不重置），GUI 拒绝重复/回退的行，旧后端不带该字段时仍按旧行为解析；它只是顺序证据，不判定成功。

## 文档地图

| 文档 | 职责 |
| --- | --- |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 阶段状态与进度日志（唯一登记处） |
| [docs/功能支持矩阵.md](docs/功能支持矩阵.md) | 支持等级基线：什么能解析、能运行、物理验证到哪一步 |
| [docs/开发路线图.md](docs/开发路线图.md) | M0–M5 长期目标与历史验收记录 |
| [docs/开发接续计划.md](docs/开发接续计划.md) | 后续工作包的范围、依赖、验收标准与待决事项 |
| [docs/测试平台说明.md](docs/测试平台说明.md) | `run_m0_tests.py` 分层、报告字段、证据与限制 |
| [docs/中文使用手册.md](docs/中文使用手册.md) | 面向用户的操作手册（INI、命令、输出、限制） |
| [docs/输出数据契约.md](docs/输出数据契约.md) | CSV/ROOT/摘要字段与版本迁移 |
| [docs/collab/README.md](docs/collab/README.md) | 跨代理协作：信箱、单写者规则、会话互读 |
| [docs/archive/README.md](docs/archive/README.md) | 已归档的历史快照清单 |
| [AGENTS.md](AGENTS.md) / [gui/AGENTS.md](gui/AGENTS.md) | 仓库/前端开发约束（实现口径、测试要求、禁止事项） |

## 协作与工作约定

- **单写者**：同一工作区默认只有本会话写代码；Astra（Codex 侧）作为总设计师/首席审查者只读审查并写提案，双方通过 `docs/collab/` 文件信箱交接，不粘贴整段对话、不导出密钥。
- **提交节奏**：`roadmap/<item>` 分支 → 全量回归 → 更新 ROADMAP/矩阵/CHANGELOG → 提交 → `codex` 快进 → 推送；不改写历史、不强制推送。
- **证据**：结论必须能落到"报告 + 日志 + 指纹/哈希"三件套；"命令成功退出"不等于物理正确。

## 接手阅读顺序（约 30 分钟）

1. 本页；
2. `AGENTS.md`（严格口径）与 `gui/AGENTS.md`；
3. `docs/ROADMAP.md` 状态表；
4. `docs/功能支持矩阵.md` 你关心的模块行；
5. `git log --oneline -15` 与 `git status`；
6. 需要动后端时跑 `python -B scripts/run_m0_tests.py --profile backend --require-tracked-sources`（需要本机 Geant4 与已构建 exe）。
