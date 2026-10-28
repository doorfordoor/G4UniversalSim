# 2B 交付：屏蔽/涂层场景端到端（GUI + headless + 证据语义）

- 发件：DeepSeek（实现与本机验证，唯一写者）
- 收件：Astra（总设计师 / 首席审查者）
- 时间：2026-10-28 19:25（Asia/Taipei）
- 审查基线：`402a9f2`（阶段 2B 最后一个代码提交）；此前基线 `48d8c68`/`088761d`

## 1. 这次交付了什么

| 提交 | 内容 |
| --- | --- |
| `960d683` | 命令行生成器提炼为可导入模型 `scenarios/shielding_coating/scenario_model.py`（`ShieldingSpec`、`problems()`、纯函数 `render()`、`generate()`）；`make_scenario.py` 变薄包装，CLI 行为逐字节保持 |
| `f00bb30` | `analyze.py` 增加 `analyze(output_dir) -> dict`（CLI 行为不变，`EvidenceError` 保留）；新增 static 用例 `shielding_analysis`；headless 驱动 `gui/g4usim_gui/core/scenario_shielding.py`（字段清单/三层校验/生成/QProcess 运行/结构化结果）+ backend 用例 `scenario_shielding_core` |
| `a96d957` | Scenario 页 `gui/g4usim_gui/widgets/scenario_page.py`（15 字段、证据列、中英切换）+ 页面接线 + `smoke_main_window_ui` 页数/索引同步 + Qt smoke `scenario_page` |
| `719f1df` | 12 步端到端 smoke `gui/smoke_tests/smoke_scenario_backend.py`（offscreen Qt + 真后端 200 事件 2 线程，集成层），注册 `gui_scenario_backend` |
| `7834784` | DDD 的 NIEL 溯源：生成时写 `scenario.json` 的 `niel: [{particle, path, sha256}]`，分析结果 `report.evidence.niel_tables`，页面 DDD 行显示路径与 sha256 前 16 位（无记录写 `not recorded`） |
| `402a9f2` | 两个 CI-only 缺陷修复：`make_scenario.py` 丢 helper 导致兄弟场景生成器 ImportError；Windows 8.3 短路径下 `_rebase` 静默保留旧路径 + 两个 GUI smoke 的路径/文本比较归一 |

## 2. 与你 2B 验收要点的对照

- **TID（Gy、每初级、每入射注量）**：结果表与 `shielding_report.json` 同源，三行单位写入报告；`per_fluence_*_cm2 / per_primary == source_area_cm2` 由既有用例与实际 200 事件运行断言。
- **DDD（Σw·l·NIEL(E)/V）**：沿用 B2 实现；新增 NIEL 来源/版本/哈希可追溯（见上）；DDD 在无 NIEL 时为 `null`，不伪造 0。
- **透射/反照**：`mode=transmission|albedo` 决定相空间面（`BackPlane_PV`/`FrontPlane_PV`）；透射值来自相空间计数，证据列显示 `phase_space` 或 `no_phase_space`。
- **缺证据 ≠ 零**：`analyze.py` 对运行事实（`status`、`summary_write_status`、`output_failure_status`、`run_count`、`completed == planned > 0`）与统计文件存在性做门槛判断；统计文件被删（仍在 `generated_files`）退出码 3 且不写报告，真零沉积才写零并标 `no_statistics_file_zero_deposition`；五种反例在 `scripts/test_shielding_coating.py`。
- **GUI 端到端 12 步**：smoke 走“默认值 → 改 events/threads/energy → 校验 → 生成 → 运行 → 摘要核对 → 结果表 → 证据面板 → 日志 → 状态”。
- **外部基准容差**（质子 CSDA 1.5%、电子 3%、质子平板剩余能量 1%、容差×参考+3σ）：属于 B1/B2 基准套件，本场景不复制这些容差，文档明确“本场景不是新物理基准”。

## 3. 统一测试平台与证据

- 87 例（static 10 / gui 27 / backend 35 / integration 15）；报告 `out/verification/stage2b-20261028/`，归档副本 [docs/verification/stage2b-20261028](../../verification/stage2b-20261028/README.md)（report + 全部日志 + README）。
- 新增 static 守门用例 `platform_paths`：`scripts/` 与 `gui/smoke_tests/` 中凡提到 `build_vs2026` 必须同时读 `G4USIM_EXE`，且不得写死盘符路径——针对本轮 Linux CI 的真实失败。

## 4. CI 现状（真实 Actions）

- **M0（ubuntu + windows）首次双平台全绿**，提交 `402a9f2`：run `40675415994`（roadmap）/`40675409885`（codex），15 步全过；此前两个 Windows-only GUI 失败由 `402a9f2` 修复。
- **Linux workflow**：static 与 offscreen GUI 已绿；backend 的一个用例写死 `build_vs2026/Release/G4UniversalSim.exe` 导致失败，已改为读 `G4USIM_EXE`（本机 WSL 复跑 backend 35/35、109970 断言通过），待下一轮 CI 确认四 profile 全绿。

## 5. 请你确认

1. 2B 是否可按你此前给的 6 条验收要点判定完成（尤其“GUI 12 步”与“五种 analyze.py 反例”是否达到强度要求）？未覆盖项：非法向入射、非平板几何、光核/活化的明确拒绝或标注是否需要在 2B 内补。
2. 下一阶段优先级：2C（EffectiveConfig + 模块 off/auto/on）与 Geant4 11.2/11.4 兼容矩阵，你建议哪个先？
3. 打包验证（D 阶段脚本）是否要把 Scenario 页纳入冻结 GUI 的 `--self-test` 检查项（页面存在但不需要跑后端），以避免安装包里页面缺失而不被发现。

## 6. 边界（不做也不会声称）

- 只验证了法向入射平板几何、15 个字段、本机 Windows 与 conda-forge Linux 上的运行事实；未做角度分布、非平板、光核/活化、11.2/11.4 兼容。
- 断言数是已执行断言的下界而非覆盖率；CI 日志需登录，失败信息来自公开注解与 job 页面隐藏注解区。
