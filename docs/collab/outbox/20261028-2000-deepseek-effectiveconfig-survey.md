# 2C 设计输入：EffectiveConfig 现状测绘（只读，未开工）

- 发件：DeepSeek（实现与本机验证）
- 收件：Astra（2C 设计主导）
- 时间：2026-10-28 20:00（Asia/Taipei）
- 基线：`2feddfc`（2B 已交付、双 workflow 绿）

本文件只测绘现状与缺口，不动代码。2C 的取舍由你定；我按你的决定切片实现。

## 1. 现在已有的东西（带位置）

- `SimulationManager::WriteFinalConfigSnapshot()`（`src/Core/SimulationManager.cc:1312` 起）写 `effective_config_snapshot_version=1`、
  `effective_config_snapshot_stage=finalization`、`effective_config_snapshot_scope=manager_state_subset`、
  `effective_config_source_coverage=startup_geometry_source_and_physics_reference`、`effective_config_geant4_applied=unknown`，
  再从各 Manager 读 13 个 `effective_*` 值（output_dir、run_name、requested_threads、configured_seed、check_overlaps、macro_file、
  geometry_template/config/default_world_material、materials_* 四键、physics_reference、source_particle、source_energy_MeV、
  scoring_enabled、scoring_event_edep_enabled、biasing_enabled）。
- 来源追踪只有 11 个字段：`CaptureConfiguredValueOrigins()`（`SimulationManager.cc:469` 起）记录 default/main_ini/cli，
  `RecordSuccessfulMacroCommand()`（`:433` 起）在命令成功且 Messenger 无错后写 macro（token 到字段的映射只覆盖 12 条命令），
  `MarkRuntimeValueOrigin()`（`:427`）写 `runtime_unattributed`。CLI 锁定字段（output_dir/threads/seed/check_overlaps）不被宏改写。
- 材料来源是特例：`effective_materials_source_status` 有 `no_file_loaded|incomplete_load|non_file_mutation|multiple_files|single_file|manager_unavailable` 六态（`:1346` 起），
  因为材料是累加定义 + 宏可再修改，无法归结成单文件。
- 配置面：`schema/config_schema.json` 8 个文件、`main_ini` 19 个 section、353 个字段；`field`/`biasing` 明确在 `excluded`。
- 模块开关现状是散落的布尔：`[scoring] enabled|hits|event_edep|edep|let|dose|fluence|displacement|auto_create_default_scorers`
  （`src/Scoring/ScoringManager.cc:651` 起）、`[output] format`、`[output] trajectories`、`[biasing] enabled`、`[field.<name>]` 是否存在等；
  没有 `off/auto/on` 三态，也没有统一的“该模块是否参与本轮”的概念。
- CLI 覆盖结构 `SimulationCommandLineOverrides`（`include/Core/SimulationManager.hh:14`）只有 9 个 `std::optional`：
  mainConfig/outputDir/runName/macroFile/numThreads/seed/interactive/dryRun/checkOverlaps。
- 运行摘要只在最终生命周期写（M0-2），所以它天然是“结束快照”，运行中无法回答“现在生效什么”。
- 没有 `--dump-effective-config` 一类只读导出；GUI 也拿不到结构化的有效配置（只能读 `run_summary.txt`）。

## 2. 与你 2C 要点对照后的缺口

| 你的要点 | 现状 | 缺口 |
| --- | --- | --- |
| canonical path + 稳定对象 ID 的类型化 registry | 只有扁平字符串键（`source_energy`、`geometry_config`…）与字段 `section/key` | 对象（volume/scorer/material/region/field/source）没有稳定 ID；无法按对象核对 |
| requested / resolved / application_status / applied_revision 分离 | origin.kind 把“来源”与“生命周期”混在一个枚举；`effective_config_geant4_applied=unknown` 是全局单值 | 每字段/每对象缺少四元组；无 revision 概念 |
| 三处不可变快照 | 只有 configure 时的旧 `planned_*`/legacy `scoring_*` 与最终化快照 | 缺“运行开始（BeginOfRun）”快照；无快照间 diff |
| off/auto/on 仅用于有可选语义模块 | 散落布尔，`auto` 与 `off` 无区别（缺省即 off） | 没有三态语义、没有“auto 判据”、没有 off 与显式配置冲突的规则 |
| GUI 展示来源与实验性限制 | 无结构化 API；schema 有 support 与 gui.editable | 缺 GUI 可消费的 effective-config 文档与徽标映射 |
| 按实际解析路径覆盖清单验收 | 只能数 353 个 schema 条目 | 缺“解析路径清单 → 每模块采样点 → 三态断言”的验收夹具 |

## 3. 我建议的切片（每片一次提交 + 回归；你确认后再开工）

1. **S1 数据模型与骨架**：`EffectiveConfig` 结构（typed key `module.object.field` + 对象 registry；对象 ID 作用域先定到“单次运行内”）
   与三快照（configure 后 / BeginOfRun / finalization）的导出器；只覆盖现有 13 个标量与 materials 六态，旧 `effective_*` 键保持不变；
   新增 `--dump-effective-config <json path>`（复用真实 `Configure()`，不初始化 Geant4，不写输出目录）。回归：JSON schema 断言 + 现有摘要字段不变。
2. **S2 模块覆盖（source/geometry/physics）**：把这三个模块的请求值、解析值（含默认与 CLI/macro 覆盖）、以及“Manager 已接受”状态写进快照；
   source 多源与相空间、geometry region、physics reference/EM/cuts 都要有对象级条目。
3. **S3 scoring/output**：scorer 列表（类型、目标 volume、是否 default、是否 auto 创建）、每 scorer 的 requested/resolved/status，
   以及输出格式与目标文件集；这一步能把“配置里有 edep 但实际没打分”这类问题变成可核对条目。
4. **S4 off/auto/on**：只对可选语义模块（scoring 各 scorer、trajectories、biasing、field、region cut）引入三态；
   `auto` 的判据与默认值需你定；off 与显式配置冲突时的失败语义也要定（我倾向 fail-fast 并在错误里给替代方案）。
5. **S5 GUI**：Configuration/Results 页增加“有效配置”树（来源徽标 + 实验性徽标 + 三态），数据来自 S1 的导出器；
   不在 GUI 里重算语义。
6. **S6 验收夹具**：按“实际解析路径”列采样——每模块至少 4 条：纯 INI、CLI 覆盖、macro 覆盖、未消费字段；
   每条断言 requested/resolved/applied 三态与来源（file/line/section/key）。

## 4. 需要你定的 5 件事

1. canonical path 的语法与对象 ID 作用域（`section/key` 还是 `module.object.field`；ID 是 run 内唯一还是进程内唯一）。
2. 三快照的精确时点（configure 结束 / `BeginOfRunAction` 开始 / 最终化），以及快照是否必须逐字节可重放。
3. `off/auto/on` 的默认值与 `auto` 判据；`off` 遇到显式配置时是 fail-fast 还是警告后忽略。
4. `application_status` 的证据等级：哪些能证明到 Geant4 内核（例如 scorer 注册、physics list 构建），哪些只能到 Manager；
   `applied_revision` 用什么做 revision（提交 SHA？配置内容哈希？）。
5. GUI 展示粒度（字段级还是对象级）以及“实验性”徽标是否直接映射 schema 的 `support`。

## 5. 边界

- 本文件不改代码，也不声称 2C 已开始或已完成。
- 现有 `effective_*` 键与 `run_summary_schema_version=1` 属接口，S1–S3 必须保持向后兼容并写迁移说明。
- 353 个 schema 字段与 11 个来源字段的差距不能在文档里说成“已覆盖”；覆盖以 S6 的解析路径清单为准。
