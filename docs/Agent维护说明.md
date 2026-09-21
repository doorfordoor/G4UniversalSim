# G4UniversalSim Agent 维护说明

整理日期：2026-07-11。本文件面向 Codex 这类代码 Agent，用于后续修改时快速找到事实来源。普通用户请优先读 `docs/中文使用手册.md`、`docs/中文几何配置说明.md` 和 `gui/docs/中文快速使用说明.md`。

## 1. 当前文档结构

仓库级开发约束见根目录 AGENTS.md，GUI 专项约束见 gui/AGENTS.md。功能状态见 docs/功能支持矩阵.md，开发顺序见 docs/开发路线图.md。

- `docs/中文使用手册.md`：后端命令行、主配置、材料、源、物理、计分、biasing、macro 命令和常见问题。
- `docs/中文几何配置说明.md`：几何模板、层级几何、形状参数、布尔操作和几何常见错误。
- `gui/docs/中文快速使用说明.md`：PySide6 GUI 的安装、页面、生成包、运行、输出和限制。
- `docs/Agent维护说明.md`：本文件，记录维护索引和易错点。

原则：面向人类阅读的整理后文档使用中文。代码标识符、命令、文件名和配置 key 保留原样。

## 2. 代码事实来源

| 主题 | 主要文件 |
| --- | --- |
| CLI 参数 | `main.cc` |
| 主配置加载 | `src/Core/SimulationManager.cc` |
| App 命令 | `src/Core/AppMessenger.cc` |
| Output 命令和输出文件 | `src/Output/OutputMessenger.cc`、`src/Output/OutputManager.cc` |
| 材料 INI | `src/Materials/MaterialIniReader.cc`、`src/Materials/MaterialFactory.cc` |
| 几何模板入口 | `src/Templates/TemplateFactory.cc` |
| 通用层级几何 | `src/Geometry/GeometryConfig.cc`、`src/Geometry/VolumeBuilder.cc` |
| 几何命令 | `src/Geometry/GeometryMessenger.cc` |
| 物理配置和命令 | `src/Physics/PhysicsManager.cc`、`src/Physics/PhysicsMessenger.cc`、`src/Physics/PhysicsFactory.cc` |
| 源配置和命令 | `src/Source/SourceManager.cc`、`src/Source/SourceMessenger.cc` |
| 计分配置和命令 | `src/Scoring/ScoringManager.cc`、`src/Scoring/ScoringMessenger.cc` |
| hit 链路 | `src/Hits/SensitiveDetector.cc`、`src/Scoring/EdepScorer.cc` |
| biasing | `src/Biasing/BiasingManager.cc`、`src/Biasing/BiasingMessenger.cc` |
| GUI 入口 | `gui/g4usim_gui/main_window.py`、`gui/g4usim_gui/app.py` |
| GUI 项目 JSON | `gui/g4usim_gui/core/project.py` |
| GUI 生成包 | `gui/g4usim_gui/writers/package_writer.py` |
| GUI main.ini 生成 | `gui/g4usim_gui/writers/main_ini_writer.py` |
| GUI 几何生成 | `gui/g4usim_gui/writers/geometry_ini_writer.py` |
| GUI 材料生成 | `gui/g4usim_gui/editors/material_editor_model.py`、`gui/g4usim_gui/writers/materials_ini_writer.py` |
| GUI source/physics/scoring 模型 | `gui/g4usim_gui/editors/source_physics_scoring_model.py` |
| GUI 输出合并 | `gui/g4usim_gui/output/merge_plan.py`、`scripts/merge_outputs.py`、`tools/mergeHistograms.cc` |

## 3. 维护时的高风险事实

- CLI 没有 `--version`。无 `--macro` 且无 `--ui` 时通常只打印帮助并退出；`--dry-run` 是例外，会执行配置和 Geant4 对象注册但跳过 macro/UI。
- `gdml` 模板当前未支持，后端配置校验和 GUI validator 会在进入 Geant4 构建前拒绝。
- STL 导入未实现。
- 后端 `VolumeBuilder` 支持 `box`、`tubs`、`sphere`、`orb`、`cone`、`trd`、`trap`。
- GUI 层级/布尔几何校验目前只把 `box`、`tubs`、`sphere`、`orb`、`cone` 放在白名单里，且稳定预览主要是 `box` 和 `tubs`。后端已支持但 GUI 未放开的形状不要在 GUI 文档里写成 GUI 可编辑。
- `simple_box` 的 target 虽读取 `shape`，但 GUI writer 固定写 `shape = box`。
- `volume_fraction` 材料只支持材料组件。直接用元素作为体积分数组分会被后端拒绝。
- 多线程输出由 worker 写 `_tN` 文件，后端不自动合并。GUI 只是调用合并工具。
- LET、Dose、Fluence 当前未支持；开启时 fail-fast，不能依赖 scorer 注册或空输出表示支持。
- process-level XS biasing 是推荐路径。旧 `[biasing.xs]` 和部分 `/AIHL/biasing/xs/...` 命令仍兼容但会提示 legacy。
- GUI 的 source rectangle、annulus、cone、cosine、focused 等模式属于预览或实验，当前 main.ini writer 会阻止不被后端支持的模式生成。
- GUI 项目 JSON schema 当前是 `G4UniversalSimProject`，version 为 5。
- GUI 生成包不会覆盖原始 `materials.ini` 或 `geometry.ini`，只写入 run package。

### 3.1 M0-1/M0-1b 配置优先级

当前启动字段的约定优先级为：

`默认值 < 主配置文件 < macro 运行时命令 < 显式 CLI 参数`

`main.cc` 将显式启动参数集中放入 `SimulationCommandLineOverrides`，先调用 `SimulationManager::Configure()` 生成最终上下文，再决定 dry-run、interactive、macro 或用法输出。显式 CLI 的 `--output`、`--threads`、`--seed`、`--check-overlaps`、`--run-name` 和 `--macro` 会阻止低优先级入口覆盖。

macro 执行前由 `Core/MacroPreflight` 递归解析静态 `/control/execute`，并将同一份规范化命令序列交给 `G4UImanager::ApplyCommand()` 执行。嵌套相对路径按当前 macro 文件目录解析；解析器统一处理 Windows 路径、带空格路径、`../` 和引号外行尾 `#` 注释。遇到首个非零 Geant4 命令状态立即停止并返回失败。已知项目命令和原生命令 `/run/numberOfThreads`、`/random/...` 在对应 CLI 锁存在时会因冲突而失败；`/control/alias`、`/control/loop`、`/control/foreach` 等动态场景直接标记为不支持。

M0-1 回归入口：

```powershell
python scripts/test_config_precedence.py
```

`scripts/test_config_precedence.py` 覆盖配置-only、配置 macro、配置 dry-run/interactive、CLI-only、配置/CLI 冲突、macro preflight、真实 `beamOn`、带空格路径、重复 CLI、无效参数、缺失路径和嵌套 macro 不得回退到 CWD。`scripts/test_run_summary.py` 覆盖 dry-run、单次和多次 `beamOn`、macro 中间失败、preflight 失败、无 run、输出目录切换、固定 seed、成功 `/random/setSeeds`、非修改随机命令、覆盖写入文件、生成文件和摘要写入失败。M0-2 后 `run_summary.txt` 在最终生命周期阶段写入，保留原有计划配置字段，并增加实际状态、每次 run、事件汇总、实际线程、配置/引擎 seed 区分、seed 修改、最终输出目录、生成文件和失败命令位置；worker 文件登记目前通过最终文件扫描和时间变化检测汇总，尚未采用共享线程安全登记表，仍需在多线程输出审计中继续验证。

M0-3A 回归入口：

```text
python scripts/test_unsupported_features.py
```

M0-3A 只增加误导防护，不实现新 Geant4 能力。`placement=replica|parameterised|assembly`、GDML、材料 `temperature`/`pressure`、`[physics.region.*]` 和 LET/Dose/Fluence 开启会在构建或运行前 fail-fast；错误消息必须包含能力名称和替代方案。false 或缺失字段保持兼容，GUI validator 对同类配置返回 `can_run = false`。

### 3.3 M0-3B1 主配置字段消费追踪

主配置只经过 `IniReader`/`ConfigManager` 链路追踪。成功的 `GetString`、`GetInt`、`GetDouble`、`GetBool`、`GetVector` 会标记实际字段已消费；`HasKey` 和 `HasSection` 仅探测，不会掩盖未消费字段。`SimulationManager::Configure()` 在各 Manager 完成后按文件和行号输出 `[ConfigWarning]`，未知 section 也会报告；warning 不改变退出码或既有运行结果。`run_summary.txt` 的 `config_warning_count` 和 `[Warnings]` 保存同一明细。材料文件和几何文件的独立解析器不在本轮范围内。

### 3.6 M0-3B2B2 几何来源诊断

几何文件使用 `GeometryConfigDiagnostic` 结构化报告 `unknown_section`、`unconsumed_key`、`legacy_metadata` 和 `ignored_boolean_key`。诊断保留原始来源并稳定排序去重，格式为 `[GeometryConfigWarning] file:line [section]/key = value: message; suggestion`，同时进入控制台和 `run_summary.txt`；`geometry_config_warning_count` 与主配置 `config_warning_count` 独立。

canonical `metadata.<非空名称>` 不进入 Geant4 语义；hierarchical/layered 的旧式无前缀属性只保留并 warning，simple/array/shielding 的未知字段继续忽略并 warning。严格 `version=2`、自动迁移和完整 round-trip 仍留给 M0-3B3。

专项回归入口：`python scripts/test_geometry_config_diagnostics.py`。同时运行
`python scripts/test_unconsumed_config.py`，确认主配置 warning 统计未被几何 warning 混入。

### 3.4 M0-3B2A 材料独立配置 schema

`MaterialIniReader` 对材料文件执行闭合 schema 校验。允许的 section 是 `[NIST]`、`[isotope.<name>]`、`[element.<name>]`、`[material.<name>]` 和 legacy `[Alias] material = G4_*`；隐式 `global` 不允许字段。旧 GUI run package 可能在 `[material.<name>]` 中包含 `type = material`，该字段已弃用但继续按大小写不敏感、首尾空白忽略的规则兼容读取，不改变 `MaterialDefinition`，新 writer 不再生成；空值、其他值及其他 section 中的 `type` 都会失败。未知 section、空动态后缀、未知 key 和 legacy alias 多余字段都会在 Geant4 初始化前失败，错误包含文件、行号、原始 section/key/value，并在可判断时给出保守拼写建议。`temperature`/`pressure` 保留 M0-3A 专用错误，替代方案是 density、state 和 composition。材料文件不使用 M0-3B1 主配置 warning 机制。

回归入口：`python scripts/test_material_config_schema.py`。测试设置 `G4USIM_TEST_MATERIAL_LIFECYCLE=1`，后端只在 schema 全部通过、即将进入 `MaterialManager::BuildAll()` 时输出 `[MaterialLifecycle] build_started`；所有 schema 失败用例都必须确认该标记尚未出现，以证明失败发生在首个材料对象构建前。该环境变量只用于测试可观察性，不改变材料定义或构建行为。

### 3.5 M0-3B2B1 几何安全闭环

`GeometrySafety` 负责非 hierarchical 模板的 production cut 与固定 box 校验；`GeometryConfig` 负责 hierarchical 普通 volume/boolean tool 的逐 shape 契约、shape-specific 字段、`copyNo` 和 placement 前置校验。`VolumeBuilder::GetCreatedGeometryObjectCount()` 提供真实创建计数，失败测试必须断言 `created_geometry_object_count=0`。

GUI `GeometryDocument` 分开保存 source/validation diagnostics，并通过 `round_trip_blockers` 阻止当前模型不能无损表达的源配置被 writer 改写。`source_copy_mode` 只复制原文件，并明确声明未由 Geometry Editor 验证。回归入口：`python scripts/test_geometry_safety_contract.py`。

本阶段不实现严格 `version=2`、自动 metadata 迁移或完整无损 round-trip；这些仍属于 M0-3B3。

## 4. 修改代码后同步文档

修改后端 CLI 或配置：

1. 更新 `docs/中文使用手册.md` 的命令行、主配置和常见问题。
2. 如果新增或删除 `/AIHL/...` 命令，同步“常用 `/AIHL` macro 命令”。
3. 如果影响 GUI 生成的 main.ini，同步 `gui/docs/中文快速使用说明.md`。
4. 若事实来源或边界改变，同步本文件。

修改几何后端：

1. 更新 `docs/中文几何配置说明.md` 的模板、shape、参数和错误说明。
2. 若 GUI 也支持该能力，同步 `gui/docs/中文快速使用说明.md` 的几何编辑器章节。
3. 若后端支持但 GUI 尚不支持，在 GUI 文档中明确区分。

修改 GUI：

1. 更新 `gui/docs/中文快速使用说明.md`。
2. 若 GUI 会生成新的后端配置字段，同步 `docs/中文使用手册.md` 或 `docs/中文几何配置说明.md`。
3. 更新本文件中的高风险事实和测试命令。

## 5. 建议校验命令

文档整理本身可以只做文件列表和链接检查。涉及代码变更时建议按范围选择：

```powershell
python -m compileall gui
python gui/smoke_tests/smoke_project_io.py
python gui/smoke_tests/smoke_parsers.py
python gui/smoke_tests/smoke_output_tools.py
python gui/smoke_tests/smoke_history.py
python gui/smoke_tests/smoke_geometry_editor.py
python gui/smoke_tests/smoke_source_editor_v2.py
python gui/smoke_tests/smoke_preview3d_primitives.py
```

需要真实后端可执行文件时：

```powershell
$env:G4USIM_EXE="D:\Geant4\G4UniversalSim\build_vs2026\Release\G4UniversalSim.exe"
python gui/smoke_tests/smoke_geometry_backend_package.py
python gui/smoke_tests/smoke_hier_boolean_geometry_editor.py
```

后端 smoke 示例：

```powershell
.\build_vs2026\Release\G4UniversalSim.exe --macro macros/run_hit_smoke.mac --threads 1 --output test/output/hit_smoke_st
.\build_vs2026\Release\G4UniversalSim.exe --macro macros/run_biasing_process_level_smoke.mac --threads 1 --output test/output/biasing_process_level_smoke
.\build_vs2026\Release\G4UniversalSim.exe --macro macros/run_volume_fraction_test.mac --threads 1 --output test/output/volume_fraction_test
```

## 6. 目录整理说明

本次整理删除了旧的英文参考、阶段审计、P0-P3 路线图、Round checkpoint 和 GUI 补充文档。它们的稳定信息已合并进三份中文手册；开发路线和历史状态不再作为用户文档保留，避免后续误读为当前能力。
