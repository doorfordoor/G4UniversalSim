# G4UniversalSim 状态（唯一入口页）

更新：2026-10-28。本页只做导航与快照；**阶段状态以 [docs/ROADMAP.md](docs/ROADMAP.md) 为准，支持等级以 [docs/功能支持矩阵.md](docs/功能支持矩阵.md) 为准**，两者冲突时先改事实再改文档。

## 一句话定位

配置驱动、可复现、可验证的 Geant4 桌面工作台（C++17 后端 + PySide6 前端 + 场景包/基准/测试平台）。
当前是"有真实物理验证的 Beta"，不是 1.0：核心链路可用，大量高级能力仍是实验性，产品完成度低于工程纪律。

## 当前快照

- 分支 `roadmap/F6-live-progress`，集成分支 `codex`（快进合并后推送）；`main` 为早期历史分支。
- 阶段 0 审计修复已交付：提交 `67ce037`（工作区快照）→ `2e87f18`（静默失败路径）→ `02c0dc6`（验收证据与状态）→ `48f566b`（跨代理协作信箱）→ `8b7721b`（阶段 1 文档与仓库卫生）→ `c80a9cf`（历史审计对照表）→ `5c6ea1d`（阶段 1.4 报告 v2 与证据门禁）→ `f1dad9d`（阶段 1b 零断言清零与 writer 边界用例）→ `48d8c68`（阶段 1b 证据与状态收尾）→ `7f5dc48`（阶段 1d 证据门禁自洽性与日志摘要按落盘字节）→ `32736c9`（阶段 1e 命令失败传播 D-4/D-5/D-6）→ `de1ea93`（Linux 构建与 CI workflow、双平台验证）→ `976ce9e`（CI workflow 的 `runner` 上下文修复）→ `dc03a1b`（D-7 屏蔽场景证据语义）→ `dbd72cf`（失败用例公开注解）→ `a5970ff`（Qt 插件修复，GitHub Actions 转绿）。HEAD 以 `git log` 为准。
- 最近一次完整回归（阶段 1j 报告 v2 + 严格证据门禁）：**81 PASS / 0 FAIL / 0 SKIP**，`profile=all`，`version=2`，`assertions_executed_total=116226`、`assert_sites_total=2440`、`cases_with_zero_assertions=[]`、`assert_probe=settrace_assert_lines_v2`、`log_digest_algorithm=sha256_raw_bytes_lf_v2`、`skip_policy=failure`、`tracked_source_gate=pass`、`untracked_source_files=[]`、`backend_provenance=source_sha256_manifest_matches_executable`。
  - 报告与 81 个逐用例日志：[docs/verification/stage1j-20261028/README.md](docs/verification/stage1j-20261028/README.md)；更早证据见 [stage1f](docs/verification/stage1f-20261028/README.md)、[stage1e](docs/verification/stage1e-20261028/README.md)、[stage1d](docs/verification/stage1d-20261028/README.md)、[stage1b](docs/verification/stage1b-20261028/README.md)（旧摘要口径，只能加 `--allow-legacy-digest` 复核）、[stage1](docs/verification/stage1-20261028/README.md)、[stage0-20261027](docs/verification/stage0-20261027/README.md)。
  - 源码指纹 `5bd97ec5e96e85f83b35b6d33d82ea12493e9d2eb4d78902c8d2ba5165d13206`、测试/夹具内容指纹 `637f211e5944ebdc726fac091b08bc6c52e3aaaef4a4ef8b2022e8c90a9b31e8`；后端 `G4UniversalSim.exe` SHA-256 `dd62fd8748fba532a12842881b0a680dff11816a6031724fd4caf9ecd83cde1f`（1734656 B）；构建身份 MSVC 19.51.36246.0 + Geant4 1132 + MT。
  - 报告运行时 `git_head=a5970ff`、`git_dirty=true`（同一批改动已暂存未提交时运行，提交内容与运行内容一致；`src/` 自 `a5970ff` 起未变）；Linux 报告与 Windows 报告的 `source_fingerprint` 相同，测试/夹具指纹按各自目录内容独立计算。
- Linux 验证：①本机 WSL（Ubuntu 24.04.4 + conda-forge Geant4 11.3.2 + g++ 13.3）backend **34/34**、integration **14/14** 全通过，证据 [docs/verification/linux-wsl-20261028/README.md](docs/verification/linux-wsl-20261028/README.md)；②**GitHub Actions 四 profile 全绿**（`3291145` 的 `codex` run [40640355033](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40640355033) 与 roadmap run [40640350911](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40640350911)，`ubuntu-24.04` 上 static / offscreen GUI / backend / integration 各自过证据门禁，另有篡改副本负向对照；更早的 `a5970ff` 只覆盖 backend+integration），构建过程、两个 GCC-only 缺陷、PySide 退出 `SIGSEGV` 与五个 CI-only 缺陷的修法见 [docs/Linux构建与验证.md](docs/Linux构建与验证.md)。
- 测试平台：`python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip`；81 个用例 = static 7 / gui 26 / backend 34 / integration 14，所有用例都报告非零断言数；报告是 `version: 2` 证据（逐用例断言数、双指纹、`log_sha256` 按落盘字节），`scripts/check_report_evidence.py` 为 CI 门禁（逐项断言 ≥1、求和/计数/零断言列表一致、摘要与磁盘字节一致、发布报告无 fail/skip，归档旧报告需 `--allow-legacy-digest`）。
- CI 现状：`.github/workflows/linux-geant4.yml` 在真实 Actions 上转绿——`ubuntu-24.04` + conda-forge Geant4 11.3.2，构建后依次跑 static / offscreen GUI / backend / integration 四个 profile（各自 `--report-root`、`--fail-on-skip`、证据门禁、`if: failure()` 注解），随后用篡改副本验证门禁必须拒绝，最后 `if: always()` 上传 artifact；跨平台指纹一致。`.github/workflows/m0-static-gui.yml`（Windows/Ubuntu 的 static+gui）仍是 `disabled_manually`——10-28 之前所有 push 只触发 Linux workflow，历史 2026-10-23 的 M0 runs 在 ubuntu 与 windows 上都失败在 `Run offscreen GUI tests` 步骤（需 job 日志才能定位，公开仓库日志需登录），恢复需仓库所有者启用。

## 阶段状态（摘要，详表见 ROADMAP）

- A 核心功能、B 场景包与基准、C 向导/绘图/扫描、D 安装包、G 3D 预览：已完成。
- E 修复：E1（GUI 与后端规则一致）、E2（配置 schema）、E3（Linux + Geant4 11.3 CI）、E5（GUI 拆分）已完成（E3 见 ROADMAP 的“done for Linux”，遗留：M0 workflow 待所有者恢复、11.2/11.4 矩阵未开始）；E4（轻量化流程）未做。
- F 优化：F6（实时运行进度）已完成；F1 输出与来源、F2 运行会话、F3 性能/tasking、F4 校验定位、F5 undo/autosave、F7 二维扫描、F8 GUI 收尾未做。
- H 增量：H1（径迹输出）已完成；H2–H9（过滤计分、平行世界、方差降低、光学、活化、DNA、体素体模、通用直方图）未做。
- M0 全模块 EffectiveConfig / 模块开关 / SolidRegistry 仍未实现（长期欠账）。

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

- 2A：Linux + Geant4 11.3 CI（E3）——已完成（Actions 绿，见上）；遗留 M0 workflow 恢复与 11.2/11.4 矩阵；
- 2B：屏蔽场景 GUI 端到端 + schema 驱动编辑器（GUI 设计归我）；
- 2C：完整 EffectiveConfig + 模块 off/auto/on（Astra 主导设计）。
- 铁律：阶段 2 冻结新功能，目标是压低 `experimental` 比例，而不是扩大分母。

## 已知缺口（不要把以下当作已完成）

- 后端名字校验类错误可能在"首个事件前"才发现（例如 `[scoring.displacement]` 的粒子名在 `BeginRun` 校验，`--inspect-run` 查不出）。
- 配置面 353 个字段中 supported 59 / experimental 287 / deprecated 5 / unsupported 2；有 `gui` 元数据的 57 个字段（generated 17 / generated_subset 30 / external_only 5 / legacy_external 2 / fixed_or_blocked 2 / fixed_false 1），其余 296 个字段没有任何 GUI 编辑路径。
- 探测器响应、Dose/Fluence/DDD 等基准多为"同源自洽"或"解析式"，缺少第三方独立数据与实测效率对照。
- 偏置只有 process-level XS 路径；importance、weight-window、splitting、Russian roulette 未实现。
- 交互命令审计只覆盖 `--ui --ui-session csh`；Qt UI 与部分嵌套/动态命令不受审计保证。
- 安装包 `out/` 中 1.0.0 早于 F6/阶段 0 改动，不可作为当前版本引用。
- 命令族的“改了缓存、内核没变、退出码 0”三条路径已闭合（Astra 2026-10-28 审查 D-4/D-5/D-6）：交互会话里的 biasing 修改被拒绝时计入 csh 失败（`interactive_command_failure_kind = biasing`）并停止会话、material 的 9 个变更命令只允许 `PreInit`（初始化后由 Geant4 拒绝 → `geant4_illegal_application_state`）、`ParseStrictDouble` 拒绝 `inf`/`nan`/溢出。只覆盖脚本化 `--ui --ui-session csh`；Qt UI 内的同类操作仍未自动化验收。
- `M0 static and GUI regression` workflow（Windows/Ubuntu 的 static+gui）仍 `disabled_manually`：没有 Windows CI 绿灯，历史 2026-10-23 的 GUI offscreen 失败原因仍未定位（需要所有者启用后读日志）；Geant4 11.2/11.4 兼容矩阵未开始。
- Actions 日志需登录才能下载：失败用例只能靠公开注解（`scripts/ci_annotate_failures.py`）与 artifact 诊断，注解不是完整日志。
- 断言证据是**已执行 `assert` 的下界**（`sys.settrace` 计数），不是覆盖率；证据门禁只证明“报告与日志自洽且未被篡改”，不证明断言写得好。
- F6 进度协议缺 `sequence` 字段，无法拒绝重复/乱序/上一轮残留的进度消息（待 Astra 决策，未擅改协议）。

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
