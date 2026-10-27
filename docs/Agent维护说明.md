# G4UniversalSim Agent 维护说明

2026-10-21 M5 Python 后处理扩展：`scripts/output_extension_registry.py`（API v1 注册/装载）、`scripts/run_output_extension.py`（CLI/独占写出）、`scripts/extensions/dose_json_extension.py`（借用 `gui/g4usim_gui/output/dose_summary.py` 聚合）。`scripts/test_output_extensions.py` 为受控数据专项，`scripts/test_dose_scoring.py` 执行真实 Geant4 worker CSV → JSON 的双 run 核对；统一入口添加 `output_extensions`。加载 `.py` 即执行任意 Python 代码，当前只允许显式可信来源，无沙箱、无内核 C++ 扩展。人类文档见 `docs/输出扩展原型说明.md`。

整理日期：2026-07-11。本文件面向 Codex 这类代码 Agent，用于后续修改时快速找到事实来源。普通用户请优先读 `docs/中文使用手册.md`、`docs/中文几何配置说明.md` 和 `gui/docs/中文快速使用说明.md`。

## 1. 当前文档结构

仓库级开发约束见根目录 AGENTS.md，GUI 专项约束见 gui/AGENTS.md。功能状态见 docs/功能支持矩阵.md，开发顺序见 docs/开发路线图.md。

- `docs/中文使用手册.md`：后端命令行、主配置、材料、源、物理、计分、biasing、macro 命令和常见问题。
- `docs/中文几何配置说明.md`：几何模板、层级几何、形状参数、布尔操作和几何常见错误。
- `gui/docs/中文快速使用说明.md`：PySide6 GUI 的安装、页面、生成包、运行、输出和限制。
- `docs/Agent维护说明.md`：本文件，记录维护索引和易错点。
- `docs/当前开发交接.md`：当前 Git 基线、未提交工作区、开放问题、总体路线和新 Agent 接手步骤；它是带日期的现场快照，接手时必须重新核对 Git。

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
- STL 导入：路线图 A5 实验性 `shape = tessellated`（`Geometry/StlReader` 校验封闭流形）；GDML 仍因本机 Geant4 无 GDML/XercesC 而阻塞。
- 后端 `VolumeBuilder` 支持 `box`、`tubs`、`sphere`、`orb`、`cone`、`trd`、`trap`。
- GUI 层级/布尔几何校验目前只把 `box`、`tubs`、`sphere`、`orb`、`cone` 放在白名单里，且稳定预览主要是 `box` 和 `tubs`。后端已支持但 GUI 未放开的形状不要在 GUI 文档里写成 GUI 可编辑。
- `simple_box` 的 target 虽读取 `shape`，但 GUI writer 固定写 `shape = box`。
- `volume_fraction` 材料只支持材料组件。直接用元素作为体积分数组分会被后端拒绝。
- 多线程输出由 worker 写 `_tN` 文件，后端不自动合并。GUI 只是调用合并工具。
- M0-4 工作区候选：`scripts/merge_outputs.py` 是同表头 CSV 的稳定顺序拼接，不做事件聚合；先校验再发布，拒绝已有目标，失败不留半成品。`tools/mergeHistograms.cc` 读取后端带 `_MeV` 的五列及旧五列/三列，只有全部输入为 v3 时输出边界列带 `_MeV`；用私有临时文件及硬链接发布，拒绝覆盖已有目标。`scripts/plot_hist.py` 识别新旧原始与合并文件。测试入口为 `python -B scripts/test_merge_outputs.py` 和 `python -B scripts/test_merge_histograms.py --executable <新编译的 mergeHistograms>`。完整后端故障注入和 MT 统计未验收。
- M0-4 工作区 CSV 契约 v3：`OutputManager::SetRunId` 在每次 run 开始时切换文件，首轮沿用 `_tN`，后续使用 `_tN_rR`；hits/event 首列 `runID`，已验证的能量/长度列在 header 标 `_MeV`/`_mm`，不再写出旧 hits 的 LET 零值占位。Edep 直方图与分类汇总按 run 独立。关闭总计分时 `ScoringManager` 不写全零 event CSV。摘要写 `run_summary_schema_version=1`、`output_csv_schema_version=3` 和按实际表头区分 v2/v3/`unknown` 的逐文件结构标识；已知原生路径写出前转 UTF-8，Windows 中文 config/macro/output 路径由 `scripts/test_run_summary.py` 真实验证。能力清单同步；迁移说明见 `docs/输出数据契约.md`。通用直方图单位、自由文本编码、真实设备故障与物理基准尚缺。
- LET 仍不支持并 fail-fast；Dose 和 Track-Length Fluence 仅在受限敏感 physical touchable、默认 scorer 自动创建条件下支持实验性 Gy/mm^-2 CSV，Fluence 要求无 daughter 的敏感 solid。两者均缺独立物理 benchmark，不能依赖 scorer 注册或空输出表示已完成计分。
- process-level XS biasing 是推荐路径。旧 `[biasing.xs]` 和部分 `/AIHL/biasing/xs/...` 命令仍兼容但会提示 legacy。
- GUI 的 source rectangle 已允许生成 XY 平面 `shape=rectangle`、`center`、`halfx`、`halfy` 的实验性子集；annulus、cone、cosine、focused 仍会阻止生成。矩形方向与平面旋转是不同概念，目前不支持旋转平面。
- GUI 项目 JSON schema 在 HEAD `018345c` 中为 version 5；当前 C0A 工作区为 version 6，新增 `runInputMode=generated|external`，尚未提交。缺少该字段的旧项目按 config/macro 是否存在迁移，专项入口为 `gui/smoke_tests/smoke_run_input_modes.py`；设置 `G4USIM_EXE` 时还验证真实 QProcess 运行和实际事件数。
- 2026-10-03 审计发现 `gui/g4usim_gui/output/` 和部分 boolean fixture 尚未跟踪且被用户 staged `.gitignore` 忽略。本机 smoke 通过不能作为全新检出证据；独立审查所需源文件，不得修改保护 index blob。阶段现场以 `docs/开发审计与阶段目标.md` 为准，旧交接快照不自动更新。
- GUI 生成包不会覆盖原始 `materials.ini` 或 `geometry.ini`，只写入 run package。

### 3.1 M0-1/M0-1b 配置优先级

当前启动字段的约定优先级为：

`默认值 < 主配置文件 < macro 运行时命令 < 显式 CLI 参数`

`main.cc` 将显式启动参数集中放入 `SimulationCommandLineOverrides`，先调用 `SimulationManager::Configure()` 生成最终上下文，再决定 dry-run、interactive、macro 或用法输出。显式 CLI 的 `--output`、`--threads`、`--seed`、`--check-overlaps`、`--run-name` 和 `--macro` 会阻止低优先级入口覆盖。

macro 执行前由 `Core/MacroPreflight` 递归解析静态 `/control/execute`，并将同一份规范化命令序列交给 `G4UImanager::ApplyCommand()` 执行。嵌套相对路径按当前 macro 文件目录解析；解析器统一处理 Windows 路径、带空格路径、`../` 和引号外行尾 `#` 注释。遇到首个非零 Geant4 命令状态立即停止并返回失败。已知项目命令和原生命令 `/run/numberOfThreads`、`/random/...` 在对应 CLI 锁存在时会因冲突而失败；`/control/alias`、`/control/loop`、`/control/foreach` 等动态场景直接标记为不支持。

M0-3C0B 的独立接口 `--inspect-macro --macro <file>` 可附带 `--output`、`--threads`、`--seed`、`--check-overlaps`，应用与运行相同的显式 CLI 锁。JSON `G4UniversalSimMacroPlan` v1 记录规范化命令顺序和来源，`configuration_evaluated=false` 明确尚无有效主配置；传 `--config` 会拒绝。查询不创建 Geant4 运行对象，不证明命令可执行；专项回归 `python -B scripts/test_macro_plan.py`。嵌套 `/control/execute` 的 UTF-8 文件名使用 `std::filesystem::u8path` 解析，避免 Windows 系统编码误读。

GUI 当前使用联合入口 `--inspect-run`，复用实际 Configure 解析主配置/CLI，随后递归 preflight；JSON `G4UniversalSimRunPlan` v1 明确为 `before_macro`，报告初始值和来源。Inspect inputs 和外部 Run 均异步查询，失败或输入变化时不启动。查询不执行 Initialize、macro 或 Geant4 run，不写摘要或输出目录；需匹配新版后端。C0B 专项覆盖中文主配置路径的 UTF-8 JSON、config-only 里的 macro、无输出副作用、来源行号以及 GUI 自动阻断；全模块 EffectiveConfig 仍未完成。M0-1/M0-2 脚本使用临时 fixture 工作区，避免把失败摘要与随机引擎文件写到仓库。

M0-1 回归入口：

```powershell
python scripts/test_config_precedence.py
```

`scripts/test_config_precedence.py` 覆盖配置-only、配置 macro、配置 dry-run/interactive、CLI-only、配置/CLI 冲突、macro preflight、真实 `beamOn`、带空格路径、重复 CLI、无效参数、缺失路径和嵌套 macro 不得回退到 CWD。`scripts/test_run_summary.py` 覆盖 dry-run、单次和多次 `beamOn`、macro 中间失败、preflight 失败、无 run、输出目录切换、固定 seed、成功 `/random/setSeeds`、非修改随机命令、覆盖写入文件、生成文件和摘要写入失败。M0-2 后 `run_summary.txt` 在最终生命周期阶段写入，保留原有计划配置字段，并增加实际状态、每次 run、事件汇总、实际线程、配置/引擎 seed 区分、seed 修改、最终输出目录、生成文件和失败命令位置。M0-4 工作区中 master 与 worker 的 `OutputManager` 共享互斥保护的生成文件登记表，只有显式关闭成功的 hits/event CSV、写出成功的直方图和分类汇总才登记，不再扫描目录或对比时间戳；新增真实双线程 5000 事件、运行中外部文件注入回归。共享登记表也锁存首个输出错误的 run/thread/stage/message；worker 回调捕获写入/关闭异常，batch `beamOn` 结束后传给主线程拒绝成功，摘要写 `output_failure_status/run_id/thread_id/stage/message`、失败状态及非零退出码。`G4USIM_TEST_OUTPUT_FAULT` 的 `event_row_t0` 和 `summary_close_t0` 两种测试注入已由真实双线程测试覆盖，正常运行不得设置该变量。物理基准、磁盘满/设备断连及 GUI 交互路径尚未验收。

2026-10-16 M0-4 工作区补充：主线程 `FinalizeRunSummary()` 的 `Flush` 和 `Close` 独立容错，保留首个输出失败并尽力落盘失败摘要；函数返回是否无输出失败，`main.cc` 正常路径据此返回非零状态。`final_flush_master` / `final_close_master` 只在真实最终化调用后注入测试异常，既验证了失败摘要与返回码，又不宣称真实介质故障已复现。Release 编译、摘要专项测试、四层统一 32/32 回归通过；测试报告 `D:\Temp\g4usim-m0-tests\20261016-083940-d8b6d28b\report.json` 的 `tracked_source_gate=fail`（24 个未跟踪源码），M0 仍未通过全量验收。

2026-10-16 M0-4 运行开始阶段补充：`RunAction::BeginOfRunAction()` 已对输出 run 切换、开始摘要、初始化与 worker 计分启动逐阶段捕获，调用共享错误登记并中止 run；在旧 run 切换失败时可显式登记尝试启动的新 run ID。`OutputManager::Flush()` 对不同 CSV writer 逐项刷新，保留首个错误。`G4USIM_TEST_OUTPUT_FAULT=begin_set_run_id_t0|begin_scoring_t0` 是第二轮真实 Geant4 回调人工故障注入；专项断言首轮完成事件、输出文件保留、非零退出和失败摘要，不能推及磁盘断连或任意多线程交互场景。

2026-10-17 M0-4 输出运行时命令补充：批处理 `/AIHL/output/setDir` 异常可能被 Geant4 Messenger 降为 warning，导致 `ApplyCommand()` 返回 0；`OutputMessenger` 因此单独登记命令失败，macro 执行器每条命令后检查此事实并按实际来源文件、行号失败收尾。`SimulationManager::SetOutputDir()` 只有在 `OutputManager::SetOutputDir()` 成功之后才更新上下文和来源快照，避免 setter 异常留下虚假的有效路径。真实后端专项测试覆盖 `G4USIM_TEST_OUTPUT_FAULT=messenger_set_dir|manager_set_dir`，断言非零退出、失败摘要、原始有效路径及来源不变；该变量仅用于测试，不代表真实磁盘故障，也不覆盖交互 UI 的逐条失败传播。

M0-5 工作区统一入口为 `python -B scripts/run_m0_tests.py --profile <static|gui|backend|integration|all>`；同一分层在 CTest 中注册。它将每项的 pass/fail/skip、日志、耗时写到系统临时目录；只要有 skip 就不以退出码 0 冒充完整通过。构建产物的 `--capabilities.source_fingerprint` 是当前 C++ 路径/内容 SHA-256，runner 要求与工作区一致，否则后端测试不执行。详见 `docs/测试平台说明.md`；该指纹不能替代编译器/Geant4 数据集身份、干净检出和物理基准。

2026-10-17 M0-5 构建工具链注意事项：中文版 MSVC 配合 Ninja 的 CMake 自动探测可能把 `/showIncludes` 前缀误识别为乱码，造成 Ninja 完全不记录头文件依赖；源码指纹更新也不会自动触发包含它的 `main.cc` 重编译。`CMakeLists.txt` 在检测到该特定乱码前缀时作定向覆盖，并显式声明 `main.cc` 对 `generated/BuildInfo.hh` 的对象依赖。独立构建目录中增量重编及 414 项头依赖已验证；此修复只解决增量构建真实性，不能替代源码已纳入 Git、CI 或物理结果验证。

2026-10-16 M0 有效配置工作区候选：`WriteFinalConfigSnapshot()` 在最终摘要中记录 `manager_state_subset`，其来源覆盖标记 `startup_fields_only`、Geant4 已应用标记 `unknown`。启动字段 `output_dir`、`run_name`、`threads`、`seed`、`macro_file`、`check_overlaps` 的 `_origin_kind/file/line/section/key` 区分默认值、主 INI、CLI、成功执行的受支持宏命令和无法归属的运行时 setter。只有宏命令执行成功且 Messenger 错误检查通过才记为宏来源；CLI 锁定的字段不被宏覆盖。`MaterialManager::LoadMaterials()` 为每次成功完成构建的材料文件记载绝对路径，加载进入构建阶段后发生异常则锁存 `incomplete_load`；`MaterialMessenger` 的显式 add/Clear 标记为 `non_file_mutation`。`effective_materials_loaded_file_count` 与 `effective_materials_loaded_file_N` 记录追加历史；`effective_materials_file` 仅单文件且未有宏修改/失败时可引用。原 `materials_file` 仍为主配置初始值。batch macro 初始化后的材料写命令在 `main.cc` 先于 `ApplyCommand` 拒绝；材料 Messenger 捕获的普通异常另记录失败计数和消息，batch 即使收到 `ApplyCommand` 状态 0 也会按当前宏来源失败收尾。交互 UI 的全部材料命令、其他 Messenger warning 失败传播与真实应用状态仍未闭合，不能凭摘要快照宣称 M0 完成。

M0-3A 回归入口：

```text
python scripts/test_unsupported_features.py
```

M0-3A 最初只增加误导防护。`placement=replica|parameterised|assembly`、GDML、材料 `temperature`/`pressure`、`[physics.region.*]` 和 LET 开启仍会在构建或运行前 fail-fast；错误消息必须包含能力名称和替代方案。Dose 与 Fluence 后续已有受限敏感体实验性实现，均需默认 scorer；Fluence 只对没有 daughter 的敏感 solid 定义 track-length/volume。false 或缺失字段保持兼容，GUI validator 对尚未支持的配置仍返回 `can_run = false`。

### 3.3 M0-3B1 主配置字段消费追踪

主配置只经过 `IniReader`/`ConfigManager` 链路追踪。成功的 `GetString`、`GetInt`、`GetDouble`、`GetBool`、`GetVector` 会标记实际字段已消费；`HasKey` 和 `HasSection` 仅探测，不会掩盖未消费字段。`SimulationManager::Configure()` 在各 Manager 完成后按文件和行号输出 `[ConfigWarning]`，未知 section 也会报告；warning 不改变退出码或既有运行结果。`run_summary.txt` 的 `config_warning_count` 和 `[Warnings]` 保存同一明细。`IniReader` 还记录重复 section 头与同一 section 内重复键的首次声明行号（`IniDuplicateInfo`），`ConfigManager::GetDuplicateWarnings()` 把它们转成同格式 warning（`suggestion` 说明后值覆盖前值、删除其中一处），摘要另计 `config_duplicate_count`；重复声明仍按最后值生效，几何文件 `version = 2` 的严格拒绝与此独立。材料文件和几何文件的独立解析器不在本轮范围内。

### 3.6 M0-3B2B2 几何来源诊断

几何文件使用 `GeometryConfigDiagnostic` 结构化报告 `unknown_section`、`unconsumed_key`、`legacy_metadata` 和 `ignored_boolean_key`。诊断保留原始来源并稳定排序去重，格式为 `[GeometryConfigWarning] file:line [section]/key = value: message; suggestion`，同时进入控制台和 `run_summary.txt`；`geometry_config_warning_count` 与主配置 `config_warning_count` 独立。

canonical `metadata.<非空名称>` 不进入 Geant4 语义；hierarchical/layered 的旧式无前缀属性只保留并 warning，simple/array/shielding 的未知字段继续忽略并 warning。严格 `version=2`、自动迁移和完整 round-trip 仍留给 M0-3B3。

M0-3B3 工作区子链路已让 hierarchical 普通体积的四种已知 `vis.*`、四种合法 `cut.*` 和 `trd` 五参数进入 GUI parser、模型、snapshot 和 writer；`trd` 五字段可在层级体积表格编辑，未知字段仍是 blocker。`python -B gui/smoke_tests/smoke_geometry_editor.py` 校验读取、编辑和再解析；`python -B scripts/test_geometry_roundtrip_backend.py` 验证小型 fixture 和默认复杂源的源/生成文件真实后端运行；设置 `G4USIM_EXE` 后运行 `smoke_geometry_backend_package.py` 验证 GUI package 3/3 事件。严格 B3 schema/迁移仍不得提前标绿。

B3 诊断去重仅完成 GUI 局部闭环：`ConfigBuilderPage` 的工作区总数以几何文档合并后的诊断为准，材料源 warning 仍从 parser 单独加入；`validate_config_builder` 遇到与当前源文件内容一致的脏编辑模型时不重复加入源解析错误。源文件加载后若内容或路径变化，则阻断生成并要求重新加载；`smoke_geometry_editor.py` 覆盖重复校验与变化源。跨层完整诊断去重仍未验收。

2026-10-06 B3 补充：后端严格 `version=2` 现在拒绝重复 section/key 并在错误中给出来源；GUI 的 `parse_geometry` 对空未知 section、孤立 `[layer.*]` 和重复声明建立 blocker，editable writer 必须拒绝。旧版重复声明仍采用原有后值覆盖前值语义；不能在迁移前宣称来源无歧义。专项入口为 `scripts/test_geometry_config_diagnostics.py` 和 `gui/smoke_tests/smoke_geometry_editor.py`。

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
# M0-3C4 工作区候选：运行结果语义

GUI `core/run_result.py` 是 Runner 和历史页的共享结果判定器。不得再用 `exitCode == 0`、摘要文件存在或旧版 `state=finished` 单独推断成功。Runner 在启动前记录摘要指纹，结束后核对本次新摘要、QProcess 退出状态、摘要 `status`/`program_exit_code`/`macro_execution_status`/`run_count`/计划与完成事件数；`run_status.json` 记录 `resultVersion=1` 与摘要指纹，历史页复核同一事实。旧历史没有新鲜度证据时显示未证实。dry-run、交互无 run、普通无 run 不属于模拟成功。该实现仍在未提交工作区，不能写成 Git 基线或 M0 阶段完成。

# M0-3D 工作区候选：默认场景边界

复杂演示场景 `test/geometry/hierarchical_test.ini` 的冷却管现位于主腔体内；`VolumeBuilder::ParseColour` 为 `aqua`、`brown`、`darkgray`、`lime` 映射 RGB，不再回退灰色。无 UI 批处理请用 `test/macros/run_hierarchical_batch.mac` 与 `python scripts/test_default_geometry_batch.py`，不得将 `test/macros/vis.mac` 的 Qt/OpenGL 命令插入 batch `beamOn` 前。旧 `test/main_hierarchical.ini` 曾因 `sensor_1` 未注册而在事件前失败；工作区已改为 `[biasing.xs.proton.protonInelastic]` 和 `[biasing.xs.neutron.neutronInelastic]`，并在各段显式写 `process` 以保留 Geant4 大小写。主配置加 batch/full macro 分别真实完成 3/3、100/100 事件及 2/2 process 匹配；`biasing_effect_observed=unknown`，不证明实际偏置或物理结果。

# M0-3E 工作区候选：目标 process 与生命周期

`BiasingXS::ValidateActiveProcessRule` 读取实际粒子 process manager，只有目标在 `G4BiasingProcessInterface` 的 wrapped process 中才算匹配；普通 process 存在但未被 wrapper 包裹不算有效。batch macro 的 physics/biasing 配置在首次初始化前重绑物理列表，初始化后修改会拒绝；显式 `/run/initialize` 和隐式 `/run/beamOn` 均在事件前校验并产生失败摘要。`RunAction` 在 master/sequential run 开始时再校验一次，但交互命令与重建链路仍须独立验证。`biasing_matched_process_rule_count` 和 `biasing_process_match_status` 表达匹配事实，`biasing_effect_observed=unknown` 不代表偏置已实际发生。执行 `python -B scripts/test_biasing_target_contract.py` 进行后端专项；GUI generated 勾选无规则 hook 必须阻断生成，external 可以传入显式规则。

真实回归确认 `/run/physicsModified` 后 `/run/initialize` 可重新验证；但 biasing operator 已挂接时 `/run/reinitializeGeometry` 曾造成访问违例。batch macro 现对该组合在执行前失败并写摘要，建议新进程重建。`--ui` 与配置中已启用的 biasing 或修改 biasing 的 macro 组合会在 UI 启动前失败；交互会话内的 biasing 修改命令被明确忽略并发出 warning，不能借交互命令绕过 batch 限制。专项覆盖前两种启动拒绝，但尚未自动化驱动实际 UI 命令；不得删去几何重建负例测试。
