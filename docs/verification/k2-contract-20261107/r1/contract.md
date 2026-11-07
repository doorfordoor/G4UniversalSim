# K2-1 独立 Geant4 工程导出合同（草案 r1，待独审冻结）

2026-11-07。范围：固定清单 `docs/collab/decisions/20261107-k2-closeout.md` 的 K2-1，只提出可独立审查冻结的消费者清单、支持子集、导出产物/身份契约与验收用例；**本文件不含实现，不构建、不导出实际工程、不启动 Geant4。** 首稿即本文件，无被退版本。

身份绑定：D 工作区 HEAD `e44fb444c81aa8cd787b8ad23d106bb12344c4ab`（分支 `roadmap/Q2-scientific-baselines`，102 项既有 dirty；ROADMAP/CURRENT 属监督端，本项只读）；程序科学基线 f812 / exe `2ff536c5…` / canonical `fc498cc7…` 保持，不用于 K2-1 任何执行。可复核材料：`out/collab/20261107-k2-contract/author/`（`closure-files.sha256` 314 行、`parameters.json`、`receipt.md`）。

---

## 0. 状态、门禁与不变量

| 项 | 值 |
|---|---|
| 阶段 | K2-1（真实消费者与独立工程导出合同） |
| 本任务交付 | 本合同 + `author/parameters.json` + `author/closure-files.sha256` + `author/receipt.md` |
| created_utc | 2026-11-07T05:47:47Z（实际 UTC，不是本地时间加 Z） |
| 已执行 | 只读：清单/ROADMAP/AGENTS 读取、真实代码与资源定位、git 身份与文件 SHA-256 计算；**未构建、未导出、未运行 Geant4、未改产品** |
| 冻结门禁 | `ready_for_contract_review=true`；主审独审冻结前不得进入 K2-2 实现 |
| 不可变（冻结后） | 支持子集与拒绝边界、导出产物布局、manifest/身份算法、正反例判据、双平台验收观察量；实现中不得放宽 |
| 例外/不前置 | F3 性能批结论与 5% 门不作为 K2 前置；K2 不新增高级物理能力；H3/H2/Q2 不重开 |
| 单写者 | 本项只写 `docs/collab/outbox/20261107-k2-contract.md` 与 `out/collab/20261107-k2-contract/author/`；不碰 closeout/CURRENT/ROADMAP/STATUS |

冻结后 K2-2/K2-3 只能按本合同实现与验收；若实现中发现合同事实错误，必须停写并申请合同修订（记录 r2），不得先实现再改合同。

---

## 1. 目的与边界

K2 目标（ROADMAP 目标 3 源码部分 / K2 条目）：交付一份导出后**脱离本工具安装目录**也能审阅、构建、运行、继续修改的 Geant4 C++/CMake 工程。本 K2-1 合同回答五个可独立复核的问题：

1. 现有 K1 配置包、运行包生成、资源物化、安装/SDK 打包、CMake、运行时身份与 GUI 入口这些真实消费者到底已有什么、缺什么（§2）；
2. 当前支持子集是什么、用什么真实代表项目和资源冻结（§3）；
3. 导出产物长什么样、manifest 与文件/模板/输入身份怎么算、许可与运行依赖怎么表达（§4）；
4. 哪些输入必须拒绝、失败怎样保证不损坏已有文件、怎样证明没有暗中依赖旧工具目录（§5、§8）；
5. 六链（解析、校验拒绝、包内源码/CMake/资源/许可、运行、GUI/CLI 入口、测试与文档）里 K2-2/K2-3 各要实现什么、扩展点与受控 C++ 修改怎样验收（§6–§10）。

不包含：Geant4 SDK 与数据集打包（已有 `packaging/build_sdk_package.py`，K2 不复用其捆绑 SDK 形态）、GUI 源码导出（GUI 是 Python 工具，只作导出入口）、通用打包/进程/验收平台、新物理模型、所有 H 项等待、跨平台逐位一致、把配置包称独立工程。

---

## 2. 现有真实消费者（已核实代码/函数/身份）

| # | 消费者 | 真实入口（文件与函数） | 现状与能做什么 | K2 缺口 |
|---|---|---|---|---|
| C1 | K1 配置包导出 | `gui/g4usim_gui/core/experiment_bundle.py:export_bundle/inspect_bundle/_publish_directory`（SHA `f1150873…`）；`core/experiment_workflow.py:1101 export()`；`experiment_cli.py:346`；`window/experiment.py:195` | schema `g4usim_experiment_bundle` v1；14 种输入角色；staging 前缀 `.<name>.k1-`；manifest 记录 `members[].sha256`、`integrity=sha256_not_signature`、`replay_verified=false`；`replay.py` 只委托已安装 GUI 的 `python -m g4usim_gui.experiment_cli --bundle`；原子发布、不覆盖 | 只有配置/资源输入，**无源码、无 CMake、无构建说明**；replay 依赖已安装工具；无模板身份、无许可清单、无独立构建/运行入口 |
| C2 | 运行包生成 | `writers/package_writer.py:51 create_run_package`、`_allocate_package`、`_copy_or_generate_inputs`、`_package_paths_text`（SHA `a0b79625…`） | 生成 `config/{materials,geometry}`、`macros/`、`logs/`、`output/`；materials/geometry 按 dirty/source_copy/editable 规则生成或复制；`_package_paths_text` 记录所选输入原绝对路径与复制清单 | `main_ini_writer.py` 写 `dir/file/config` 的**绝对路径**；无源码/CMake/许可/文档；包只在工具内可复现 |
| C3 | 资源物化 | `core/run_editor_resources.py:resource_fields/materialize_run_resources/materialize_geometry_file`（SHA `51a5e11c…`） | phase_space/spectrum/field_map 与 geometry 的 `file/copies_file` 复制进运行包并改路径（保留 BOM）；角色覆盖 K1 `_ROLES` | 仅运行期资源，不含静态源码闭包；复制后路径仍可能指向包外 |
| C4 | 安装与资源定位 | `core/install_layout.py:application_root/default_backend_executable/default_runs_root/scripts_dir/script_python`（SHA `b7988fc5…`） | 唯一路径判断：frozen→exe `parents[1]`；dev→`__file__` `parents[3]`；含 runs root/recovery root/scripts/python 探测 | 安装版无源码模板资源；导出必须新增可随包发布的模板，而非读开发检出 |
| C5 | 应用打包（K1 安装包） | `packaging/build_package.py:RESOURCES`（SHA `12c9e0ae…`）；`packaging/build_linux_package.py`（`12b4cea5…`）；`packaging/installer.iss`（`5295d200…`） | 包布局 bin/gui/config/scenarios/scripts/test/geometry/docs/examples/licenses；`RESOURCES=[config,scenarios,scripts,docs,examples,test/geometry,test/macros]`；Inno 单条递归源；两平台同源 | 没有 `export-template/` 资源；没有模板构建器；安装版因此无法导出 |
| C6 | SDK 打包（真实源码组装器） | `packaging/build_sdk_package.py:build_sdk/copy_development_tree`（SHA `5819b0ce…`） | 校验 Geant4 前缀、`_no_links`；复制 Geant4 include/lib/bin/libexec/mkspecs/plugins(+Qt)；源码树 `sdk/g4usim-source`=src,include,cmake,config,schema,scripts,tools,macros,test+main.cc+CMakeLists.txt；consumer probe；catalog components `geant4_sdk/g4usim_backend_source/sdk_consumer_probe` | 捆绑 vendor SDK、含 GUI/test/scripts、一揽子 zip；非通用导出、无事务 manifest、非 GUI 可触发 |
| C7 | CMake 构建系统 | `CMakeLists.txt`（`9fb42be1…`）、`cmake/BuildIdentity.cmake`（`8d9a2d06…`）、`cmake/WindowsRuntime.cmake`（`48ea39ac…`）、`include/Core/BuildInfo.hh.in`（`1886acb1…`） | C++17、Geant4 required ui_all vis_all、逐文件 SHA256→`G4USIM_SOURCE_FINGERPRINT`、目标 G4UniversalSim/mergeHistograms/GDML 条件组件/scoringNumericCheck/randomCommandGuardCheck/h2VolumeScoringCheck/parallelScoringCheck；CTest `h2_volume_scoring_check`、`parallel_scoring_component` 标签 `component`，`m0_*` 四个依赖 GUI/scripts；POST_BUILD 复制 config/macros/scripts；install bin+config+macros | `m0_*` 与 POST_BUILD scripts 依赖 GUI 树；无 stand-alone 开关；源码指纹已防“源档案继承无关仓库身份”（`BuildIdentity.cmake` 注释与实现），但未声明导出形态 |
| C8 | 后端运行时/身份 | `main.cc`（`a9dfdbb1…`）CLI；`src/Core/SimulationManager.cc`（`ddc95e5b…`）capabilities `:84-86`、summary.Set `:713-731`、`:779-780`；`src/Output/RunSummary.cc`（`3c6a5bf5…`）`[Values]` `:204-207`、`run_metadata_json_v1` `:472-478`；`src/Core/Geant4DataLocator.cc`（`027a444c…`） | `--config/--macro/--output/--threads/--seed/--dry-run/--capabilities/--check-geant4-data/...`；summary 记录 source_fingerprint/build_git_commit/失败状态；数据定位 | 配置路径是绝对路径消费方式；导出需相对闭包 + 独立构建身份（`build_git_commit=unknown` 必须可表达） |
| C9 | GUI 项目/快照/示例 | `core/wizard.py:40 SCENARIOS`（`36d0f4cf…`）、`core/examples.py`、Project 页与 `window/experiment.py` | 打开项目/生成运行包/保存快照/5 个向导场景；示例 07/08 为 tracked 项目目录 | 无“导出 Geant4 工程”动作；无模板可用时的禁用与错误提示；GUI 不能定义支持，只能暴露本合同子集 |
| C10 | 复用测试 | `scripts/test_k1_bundle.py`（`80726fb8…`，882 行）、`scripts/test_j2_resource_bundle.py`（`67bf4ba3…`）、`packaging/test_installer.py`（`59fda741…`）、`packaging/verify_installation_flow.py`（`a6527b59…`） | 资源策略/晚到链接守卫/无发布物/私密泄漏/replay_verified=false；安装包布局与安装流 | 无导出测试；K2 新增用例只补缺口，不重建框架 |

结论：现有链条能**生成配置包**、**组装捆绑 SDK**，但没有任何路径产出“纯源码 + CMake + 配置/资源 + 许可 + 构建说明 + manifest”的可独立项目；C4/C5 也没有导出模板资源。K2-2 的缺口是明确的，不是 stub 判定问题。

---

## 3. 冻结的支持子集

### 3.1 两个真实代表项目（必须一起支持）

**S-A 打开式项目 = `examples/07_parallel_world_box/`**（6 个 tracked 文件，SHA 见附录 A）：

- `main.ini`：`[run] threads=1 seed=20261400`、`[output] dir=output format=csv`、`[materials] file=materials.ini`、`[geometry] template=hierarchical config=geometry.ini default_world_material=galactic`、`[physics] reference=FTFP_BERT default_cut=0.1 mm`、`[scoring] dose+fluence+auto_create_default_scorers`、`[source] proton 10 MeV point 0,0,-20 mm direction 0,0,1`、`[parallel_world] enabled=true name=ScoringWorld geometry_config=parallel.ini`；
- 几何：world 100 mm box（G4_Galactic）+ Slab 20×20×2 mm（water，非敏感）；并行世界同位置 Slab 敏感；材料别名 `galactic/water`；`run.mac` = `/run/initialize` + `/run/beamOn 200`。

它覆盖：hierarchical 几何、NIST 别名、并行计分世界（H3）、dose/fluence、CSV、点源与固定方向、1 线程确定性。**所有路径都在项目目录内。**

**S-B 生成式项目 = 向导 `single_target` 默认 spec**（`wizard.py:default_spec`）：G4_WATER 10 mm 目标、50 mm 横向、proton 100 MeV pencil、`FTFP_BERT_EMZ`、1000 事件、2 线程、seed 12345、`event_edep+dose`。它经 `validate_config_builder → create_run_package` 生成 main/materials/geometry/macro，是 GUI 主流程的真实产物。

### 3.2 冻结特性白名单

导出只接受以下组合；白名单以外一律在写任何目标文件前拒绝（§5 R6）：

- `[geometry] template` ∈ `{hierarchical}`；形状仅 `box`（hierarchical 普通体积）；无 boolean、无 assembly、无 STL/tessellated、无 GDML、无 parameterised/replica；
- 材料：NIST 名或 `materials.ini` 的 NIST 别名（S-A/S-B 实际用法）；不含温度/压力；
- `[physics] reference` ∈ 向导/示例使用的 reference 列表（S-B=FTFP_BERT_EMZ，S-A=FTFP_BERT）；`em` 不设自定义 EM 选项；
- `[source]`：point（固定方向或各向同性）或 plane rectangle；无多源、无 ion、无相空间文件；
- `[scoring]`：hits/event_edep/edep/dose/fluence/LET/volume filter/spectrum 中仅允许 S-A/S-B 实际出现的键；禁止 mesh scoring、DDD/displacement、trajectories；
- `[parallel_world]` 仅 S-A 形态（1 个并行世界、box 敏感体积）；
- `[output] format=csv`；`[run] macro` 仅单 macro 一整文件；1 个主 INI；无 `[field]`、无 biasing、无 region、无 radioactive_decay 之外的高级段（实际子集不含）；
- 输入文件全部位于项目目录内，且无符号链接/junction/8.3 别名（§5 R3/R5）。

S-B 的 2 线程允许导出，但 K2-3 的确定性观察只用 S-A（1 线程）；S-B 只验“能构建、能完成 1000 事件、summary 与输出齐全”。

### 3.3 文件闭包（冻结模板 + 项目输入）

模板闭包 = 314 个 tracked 文件 − `examples/07_parallel_world_box/` 6 个 = **308 文件**：
`main.cc` 1、`CMakeLists.txt` 1、`CMakePresets.json` 1、`cmake/` 2、`include/` 119、`src/` 107、`config/` 30、`macros/` 28、`tools/` 9、`schema/` 2、`README.md` 1、`docs/` 4、`packaging/licenses/` 3。

- 模板身份：对 308 个文件按相对路径排序，行格式 `"{sha256}  {relpath}\n"`，拼接后 SHA-256 = **`1862a858a532f0ff9178c77631308cb2c689bc3dd5f4e683faf2217cdc2110c8`**（blob 30292 B）。
- 314 文件清单身份（含 S-A 六文件）= `c8e2a0b79cb4164fc6ea43d6cfda65ea2ac52f7c5fbadc9facd9ee2bc2fd9157`（`closure-files.sha256` 本身即该 blob，30941 B）。
- 导出时模板必须逐文件复制并核 SHA；打包模板与开发检出模板必须同身份（K2-2 P4）。
- 不进入模板/导出的目录：`gui/`（Python 工具）、`scenarios/`、`packaging/`（除 licenses）、`test/`、`scripts/`、`docs/verification/`（39601 tracked）、`docs/collab/`（379 tracked）、`out/`、`.github/`、`examples/` 其余示例、`_backup_git_*`。排除理由：属工具/证据/协作资产，不属于独立后端工程，且会把旧工具目录或历史身份带进导出。

---

## 4. 导出产物布局与 manifest v1

### 4.1 布局（冻结）

```
<name>/
  CMakeLists.txt                 # 模板原样，配 -DG4USIM_STANDALONE_EXPORT=ON
  CMakePresets.json              # 模板原样（Windows 可选）
  cmake/{BuildIdentity.cmake,WindowsRuntime.cmake}
  main.cc
  include/**                     # 119 个头文件
  src/**                         # 107 个源文件
  tools/**                       # 9 个组件工具源
  schema/**                      # 2 个 JSON schema（审阅/工具用）
  config/**                      # 模板默认配置 30（POST_BUILD/install 需要）
  macros/**                      # 模板默认 macro 28
  docs/{Linux构建与验证.md,中文使用手册.md,功能支持矩阵.md,输出数据契约.md}
  README.md                      # 模板原 README（工具视角），README-EXPORT.md 为导出视角
  licenses/{Geant4-LICENSE.txt,Xerces-C-LICENSE.txt,Xerces-C-NOTICE.txt}
  THIRD_PARTY_NOTICES.md         # 生成：依赖未捆绑声明
  project/
    README.md                    # S-A 时复制示例 README；S-B 时生成
    main.ini                     # 改写后主配置（相对路径）
    config/{materials.ini,geometry.ini[,parallel.ini]}
    macros/run.mac
    resources/**                 # 仅白名单资源（本子集实际为空）
  README-EXPORT.md               # 生成：构建/运行/修改/测试说明（含禁用声明）
  export-manifest.json           # 生成：身份与输入审计
```

`project/` 与模板 `config/`/`macros/` 并存：模板目录保持 CMake POST_BUILD/install 的既有假设，`project/` 是用户所选工程。导出 README 中的运行命令一律显式传 `--config project/main.ini --macro project/macros/run.mac --output runs/...`，不依赖复制到 exe 旁的默认 config（那只是模板演示）。

### 4.2 路径改写（冻结）

S-A：复制原文件字节到 `project/`，仅对 `project/main.ini` 的下列键改值（其余字节、注释、顺序、BOM 不变）：
`[materials] file = config/materials.ini`；`[geometry] config = config/geometry.ini`；`[parallel_world] geometry_config = config/parallel.ini`；`[output] dir = runs/default/output`。`run.mac` 原样。
S-B：用既有 writers 生成（`main_ini_writer`/`write_materials_ini`/`write_geometry_ini`/`macro_writer`）后写入 `project/`，生成时即以相对路径为目标；不得把工具包绝对路径写进导出。
导出完成后做静态扫描：`project/` 下任何 INI/macro 出现 `D:/`、`D:\`、`/d/Geant4`、`build_vs2026`、`out/collab`、`gui_runs`、仓库根绝对路径 → 拒绝（R7），并保留 staging 供诊断（不发布）。

### 4.3 manifest v1（schema `g4usim_export_project`，version 1）

必填字段：

- `schema`、`version`、`created_utc`（UTC，ISO 8601 Z）；
- `tool`：`name=G4UniversalSim`、`version=1.0.0`、`git_head`、`git_source_state`、`template_origin ∈ {packaged,checkout}`、`template_root_label`、`template_digest`；
- `identity`：`algorithm=sha256_sorted_sha256_path_lines_v1`（= 对除 `export-manifest.json` 外的全部导出文件按相对路径排序、行 `"{sha256}  {relpath}\n"` 拼接再 SHA-256）、`file_count`、`digest`、`template_file_count`、`template_digest`；
- `project`：`name`、`selection ∈ {opened_project,generated_package}`、`entry{config,macro,output}`（相对）、`original_project_root_audit`（绝对路径；仅审计，禁止被运行时读取）；
- `files[]`：`{path,role,sha256,bytes}`；role ∈ `{source,header,cmake,tool,schema,template_config,template_macro,doc,license,notice,project_config,project_macro,readme_export,example}`；
- `inputs[]`：`{role,original_path(绝对，审计),copied_to,sha256_before,sha256_after,rewrite ∈ {verbatim,path_rewrite,generated}}`；
- `build`：`requirements[]`、`standalone_flag=G4USIM_STANDALONE_EXPORT=ON`、`docs[]`、`commands{windows[],linux[]}`；
- `tests`：`component_ctest_regex="component"`、`smoke_runs[]`（config/macro/output/events）；
- `licenses[]`：Geant4（随工程声明的宿主依赖，不捆绑）、Xerces-C（仅 GDML 启用时相关，本子集不含）、`project_code` 状态 `not_declared_in_repository`（仓库无根 LICENSE；不得由实现者臆造许可证文本）；
- `limits`：子集 ID/输出格式/线程/物理/源/计分白名单；
- `not_included[]`：Geant4 SDK、数据集、Qt、编译器、Python、GUI、scenarios、test 框架、docs/verification、docs/collab、其他 examples。

禁止：manifest 记录签名或“可复现构建保证”；`integrity` 只允许 `sha256_not_signature` 语义（与 K1 一致），不声称来源可信。

### 4.4 许可与依赖（冻结）

- 导出工程**不捆绑** Geant4/Qt/XercesC/编译器/Python/数据集；`THIRD_PARTY_NOTICES.md` 明示“宿主需自备 Geant4 11.3.2（含 Qt5 可视化组件所需的 Qt5 开发文件；GDML 启用时含 XercesC）与数据集”。
- 复制 `packaging/licenses/*` 三个文本作参考；不新增或翻译许可证。
- 项目自身代码无仓库许可证记录：manifest 与 README-EXPORT 必须原样说明，**不得**写 MIT/Apache 等未声明许可；若将来需要再分发，属主审/用户决定。
- 构建依赖全集（README-EXPORT 必须逐条给出）：C++17 编译器、CMake ≥ 3.21（README 声明；CMakeLists 自身 min 3.10）、Geant4 11.3.2（Windows 本机前缀 `D:/ProgramFiles/Geant4`，Linux conda-forge 等价前缀）、Qt5（Geant4 ui_all/vis_all 所需）、XercesC（Geant4 GDML 组件；本机在 Geant4 前缀内并由 CMakeLists 自动推导 `XercesC_ROOT`）、Geant4 数据集（`GEANT4_DATA_DIR`/`geant4-data.txt` 或环境变量；不捆绑）。版本必须与构建验证记录一致，不承诺跨 Geant4 版本 ABI。

---

## 5. 输入选择、拒绝与事务（冻结）

### 5.1 选择来源

- S-A：GUI 已打开项目目录（main.ini + 引用文件），或 CLI `--project <dir>`；
- S-B：当前项目为 generated 模式（编辑器/向导产生 dirty 模型），导出器复用 `create_run_package` 在 staging 内先生成运行包，再取其 main/materials/geometry/macro 作为项目输入（K1 同法）；
- 两种模式都必须解析并解析失败即拒绝：主 INI 语法/未知 section、材料/几何文件缺失、macro 不存在或为空、路径越出项目目录。

### 5.2 拒绝案例（必须实现为可测试错误码，全部在写目标目录前或 staging 内完成，不改已有文件）

| ID | 条件 | 错误码 | 目标目录 | staging |
|---|---|---|---|---|
| R1 | destination 已存在（文件/目录/链接） | `destination_exists` | 不动 | 不创建 |
| R2 | destination 父目录不存在或非目录 | `destination_parent_missing` | 不动 | 不创建 |
| R3 | 输入或 destination 路径含符号链接/junction/8.3 别名或无法规范化 | `linked_or_ambiguous_path` | 不动 | 删除 |
| R4 | 无项目/未打开且非 generated，或 main INI 缺失 | `selection_unavailable` | 不动 | 不创建 |
| R5 | 引用文件缺失、不可读、位于项目目录外、或经链接指向外部 | `external_or_missing_input` | 不动 | 删除 |
| R6 | 命中 §3.2 白名单外特性 | `unsupported_feature` | 不动 | 删除 |
| R7 | 改写/生成后 `project/` 仍含绝对路径或旧工具目录标记 | `absolute_path_remaining` | 不动 | 删除并保留诊断 |
| R8 | 模板不可用（安装版无 `export-template/` 且非开发检出） | `export_template_unavailable` | 不动 | 不创建 |
| R9 | destination 位于被导出项目/模板树内 | `destination_inside_source` | 不动 | 不创建 |
| R10 | 复制过程中输入字节变化（前后 SHA 不一致） | `input_changed_during_export` | 不动 | 删除 |
| R11 | 模板文件 SHA 与冻结身份不符（打包模板损坏/漂移） | `template_identity_mismatch` | 不动 | 删除 |
| R12 | 写入/磁盘/权限失败 | `write_failed` | 不动（若已发布前失败） | 删除 |

失败时返回结构化结果（错误码、信息、涉及的输入/文件、staging 路径），不发布、不删除已有目标；staging 清理失败不得改错为成功。

### 5.3 正例

| ID | 用例 | 期望 |
|---|---|---|
| P1 | S-A（example 07）完整导出 | 文件集合/manifest/identity 符合 §4；不改源目录 |
| P2 | S-B（向导 single_target 生成）完整导出 | 同上；main.ini 无绝对路径 |
| P3 | 同一输入连续导出到两个不同 destination | 除 `created_utc`/`original_project_root_audit` 外，全树与 identity 完全一致 |
| P4 | 开发检出模板 vs `build_export_template` 产出的打包模板 | `template_digest` 均等于 `1862a858…`；导出树 `identity.digest` 相同 |
| P5 | 导出树内 CMake 配置 + 构建 + 组件 CTest（K2-2 冒烟） | `-DG4USIM_STANDALONE_EXPORT=ON` 下无 m0_* 测试、无 scripts 复制，component 测试可配置 |
| P6 | 导出树内 `--dry-run` 与 200 事件运行（K2-2 集成冒烟） | dry-run 通过；运行完成 200/200，summary/output 齐全（用已冻结 exe 或 K2-2 自建 exe，记录实际身份） |

事务规则：staging 目录 `<destination 父>/.g4usim-export-<name>-<pid>-<rand>`，完整写出并逐文件核 SHA 后一次 rename 发布；发布前目标必须不存在（R1）；任何失败 rmtree staging，目标前缀残留不得冒充导出；源目录只读打开，导出前后对每个输入核 SHA（R10）。

---

## 6. 六链矩阵（合同冻结的“实现完成”定义）

| 链 | K2-1 现状 | K2-2 必须实现 | K2-3 必须验收 |
|---|---|---|---|
| 1 配置解析 | 后端可解析 INI/macro（C8） | 导出器读取/校验主 INI 与引用文件（复用后端 schema 键表/现有 writers，不自造解析器） | 导出 `--dry-run` 通过；无效 INI 被后端拒绝 |
| 2 校验拒绝 | 无导出边界 | R1–R12 全部可测；错误码稳定 | 拒绝时不产生半成品、不改已有目标 |
| 3 包内源码/CMake/资源/许可 | C7 有 CMake；C6 有捆绑 SDK；无导出形态 | 模板闭包 308 文件 + CMake standalone 开关 + config/macros + licenses/NOTICES + README-EXPORT | 独立目录构建成功；文件集合/身份与 manifest 一致 |
| 4 运行 | 后端可运行（C8） | 导出 README 给出显式相对路径命令 | 两平台各完成 S-A 200 事件与 S-B 1000 事件；summary/输出身份记录 |
| 5 GUI/CLI 入口 | C1/C9 无导出动作 | GUI Project 菜单 `Export Geant4 project…`（禁用时有原因）+ CLI `export-project`；只暴露本合同子集，保留原行为 | 真实 GUI/CLI 操作观察；无模板/越界子集时被禁用或拒绝 |
| 6 测试与文档 | C10 有 K1/安装测试 | 新增 static 导出测试 + GUI smoke + 打包模板构建器；`docs/独立工程导出.md` + 手册小节 + 打包 README 资源说明 | 正式回归、证据/回执、文档链接检查 |

---

## 7. 扩展点与受控 C++ 修改验收（冻结）

### 7.1 扩展点（导出 README 与 K2-2 文档必须列，行号为当前基线）

| 扩展对象 | 位置 |
|---|---|
| 新计分器 | `src/Scoring/ScoringManager.cc:496-524`（注册）与 scorer 配置键解析 |
| 新实体/布尔 | `src/Geometry/VolumeBuilder.cc:354-480`（`CreateSolid`，布尔 464-472） |
| 新几何模板 | `src/Templates/TemplateFactory.cc:14`（`Create`） |
| 新物理列表/模块 | `src/Physics/PhysicsFactory.cc:345`（`CreateReferencePhysicsList`）、`456/540/551`（`RegisterPhysics`） |
| 新命令（Messenger） | `src/Core/SimulationManager.cc:1117-1140`（Manager/Messenger 实例化）；`src/Detector/DetectorConstruction.cc:25`（DetectorMessenger） |

扩展说明只描述“改哪个文件、加什么注册、要哪些测试”，不承诺新物理正确性。

### 7.2 一处受控 C++ 修改（K2-3 验收，只改导出副本）

- 文件：导出树 `src/Core/SimulationManager.cc`；
- 补丁：在 `FinalizeRunSummary` 的 `summary.Set(...)` 块（基线 `:713-731`）内新增一行 `summary.Set("k2_export_probe", "k2-controlled-change-v1");`
- 只允许这一文件、这一行新增（diff 必须恰好 1 insertion，无删除/重排）；
- 观察量：
  1. 重建成功、exe/组件 SHA 与修改前不同；
  2. `--capabilities` 的 `source_fingerprint` 改变（逐文件指纹覆盖该源文件），`build_git_commit=unknown`/源码状态按 `BuildIdentity.cmake` 语义（导出树无 .git，不得复制工具仓库身份）；
  3. 运行 S-A 200 事件，`run_summary.txt` `[Values]` 出现 `k2_export_probe = k2-controlled-change-v1`；
  4. 物理输出（hits/edep/dose/fluence/statistics CSV）与修改前同平台同 seed 运行**逐字节一致**（补丁不影响物理）；若不一致 → 失败保留，不得调容差；
  5. 修改前后运行都不得读取工具安装目录/旧 exe。

---

## 8. 双平台独立构建/运行/修改矩阵（K2-3 冻结）

### 8.1 隔离与身份采集

- 在仓库外的独立工作目录（建议 `D:/k2-work/<id>` 与 Linux `$HOME/k2-work/<id>`）；不得在 D:\\Geant4\\G4UniversalSim 内 build/run。
- 清空/不继承的工具环境：`G4USIM_*`、`GEANT4_DATA_DIR`（除非作为明示 SDK 输入重新设置）、旧 build 目录 PATH 注入；不使用 D 工作区 exe/`build_vs2026`/`out/collab` 任何产物。
- 每次构建/运行记录：导出 identity、模板 digest、平台/编译器/CMake/Geant4/Python 版本、`--capabilities` JSON（SHA 记录）、exe 与组件 SHA、`run_summary.txt` SHA、CSV 文件 SHA 集合、日志。
- 依赖证据：Windows `dumpbin /DEPENDENTS` + 运行前实际加载的 Geant4/Qt DLL 路径（允许系统/SDK 前缀，不得指向旧工具 build）；Linux `ldd` 全路径（只允许系统 + conda/SDK 前缀，不得出现 D 工作区、`build_vs2026`、`out/collab`）。

### 8.2 Windows（本机原生 SDK）

```
cmake --preset vs2026-x64 -DG4USIM_STANDALONE_EXPORT=ON
    -DGeant4_DIR=D:/ProgramFiles/Geant4/lib/cmake/Geant4
    -DQt5_DIR=D:/ProgramFiles/Qt/5.15.2/msvc2019_64/lib/cmake/Qt5
cmake --build build_vs2026 --config Release --target G4UniversalSim parallelScoringCheck h2VolumeScoringCheck
ctest --test-dir build_vs2026 -C Release -R "component" --output-on-failure
build_vs2026/Release/G4UniversalSim.exe --check-geant4-data
build_vs2026/Release/G4UniversalSim.exe --config project/main.ini --macro project/macros/run.mac --output runs/k2a
```

（`Geant4_DIR` 显式传入，使 `CMakeLists` 的 XercesC 自动推导生效；Qt5 为 Geant4 ui_all/vis_all 链接依赖。若某机器缺少，记录为环境阻塞，不删组件规避。）

### 8.3 Linux（conda-forge 等价 Geant4 11.3.2）

```
cmake -S . -B build_linux -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$CONDA_PREFIX"
    -DG4USIM_STANDALONE_EXPORT=ON
cmake --build build_linux -j"$(nproc)" --target G4UniversalSim parallelScoringCheck h2VolumeScoringCheck
ctest --test-dir build_linux -R "component" --output-on-failure
./build_linux/G4UniversalSim --check-geant4-data
./build_linux/G4UniversalSim --config project/main.ini --macro project/macros/run.mac --output runs/k2a
```

数据与依赖按 `docs/Linux构建与验证.md` 的 conda 配方（expat/zlib/freetype 版本门槛只在 Geant4 11.4 时需要，本子集用 11.3.2）。

### 8.4 判据

- 构建：0 error，无 m0_* CTest 注册，component 两个测试通过；
- 运行：S-A 200/200 与 S-B 1000/1000 completed，`run_summary.txt` 状态成功，输出文件与 manifest 一致；
- 独立性：两平台构建/运行均在仓库外，依赖证据无旧工具路径；导出树内无绝对工具路径；
- 确定性：S-A 同命令两次运行到不同 output，CSV/统计文件逐字节一致（1 线程）；S-B 不要求逐位；
- 受控修改：按 §7.2；两平台都必须做（Linux 也做一次，证明可继续开发；若某平台修改失败保留失败原因，不得只做 Windows）；
- 允许差异：exe/组件 SHA、`source_fingerprint`、build identity、耗时、日志细节因平台/编译器不同；**不允许**把不同平台结果混写成同一身份。

---

## 9. 精确实现文件范围（K2-2 / K2-3）

### 9.1 K2-2 新增

- `gui/g4usim_gui/core/export_project.py`：选择/校验/改写/manifest/事务（Qt-free，可 CLI 直接调用）；
- `packaging/export_template.py`：冻结模板清单（308 文件，按本合同的目录规则枚举）与身份计算/校验；
- `packaging/build_export_template.py`：从仓库工作区构建 `export-template/` 到打包目录（单源复制、`_no_links`、逐文件 SHA 核验；不手改源文件）；
- `scripts/test_k2_project_export.py`（static，无 Qt/无 Geant4）：P1–P4、R1–R12 的纯文件系统测试与 manifest/identity 断言；
- `gui/smoke_tests/smoke_export_project.py`（gui/offscreen）：GUI 动作启用/禁用、目标目录选择、错误显示、导出文件存在；不运行后端；
- `docs/独立工程导出.md`（人类文档，中文）：子集/限制/命令/许可/依赖/证据入口。

### 9.2 K2-2 修改

- `gui/g4usim_gui/core/experiment_bundle.py`：若需共享 helper，只允许把现有 staging/发布/摘要函数**原样**抽到新 `core/export_support.py` 并保留 re-export；K1 测试必须全绿（不允许改变 K1 行为/格式）；
- `gui/g4usim_gui/experiment_cli.py`：新增 `export-project --project <dir> --destination <dir>`（或等价参数）；
- `gui/g4usim_gui/window/experiment.py` + `main_window.py`（菜单/动作接线）：Project 菜单 `Export Geant4 project…`，禁用原因可见；
- `gui/g4usim_gui/window/project.py`（可选同动作按钮）；
- `CMakeLists.txt`：新增 `option(G4USIM_STANDALONE_EXPORT ... OFF)`，包裹 `m0_*` add_test 与 POST_BUILD `scripts` 复制（config/macros 复制与 install 保持）；默认 OFF 时行为逐字不变；
- `packaging/build_package.py`：`RESOURCES` 增加 `export-template`，并调用 `build_export_template`；`build_linux_package.py` 随同源清单自动覆盖；`packaging/installer.iss` 无需改（递归源）；
- `scripts/run_m0_tests.py`：注册 `Case("k2_project_export", "scripts/test_k2_project_export.py", "static")` 与 `Case("k2_export_gui", "gui/smoke_tests/smoke_export_project.py", "gui", ("qt",))`；
- `docs/中文使用手册.md` 增导出小节；`docs/Linux构建与验证.md` 交叉引用；`packaging/README-package.md` 记录 `export-template/` 资源与用途。

### 9.3 K2-3 新增（证据，不进产品）

- `out/collab/20261107-k2-build/`：`windows/`、`linux/`（构建日志、ctest 日志、capabilities、run summary、CSV SHA、依赖证据）、`controlled-change.patch`、`identity.json`、`before-after-files.sha256`、`README.md`。

### 9.4 不得修改

`src/`、`include/`、`main.cc`、GUI 既有非导出相关代码、`docs/collab/decisions/*`、`docs/ROADMAP.md`、`docs/collab/CURRENT-SUPERVISION.md`、`STATUS.md`、F3 任何文件/证据、H8 用户改动、`.gitignore`、全局环境/用户项目。K2-1 仅写合同与 author 证据；K2-2 才允许改上述 9.2 清单内文件。

---

## 10. 验收证据与复用环境

- **复用**：C1 staging/发布语义与 K1 测试、C2 writers、C3 资源物化、C7 CMake/组件测试、`packaging/test_installer.py`/`verify_installation_flow.py` 的安装布局判据；不新建通用平台。
- **K2-2 证据**：static 测试日志（P1–P4、R1–R12）、GUI smoke 日志、模板构建器日志、导出树身份（manifest/closure digest）、打包布局清单、doc_links 结果；不改产品以外的证据目录。
- **K2-3 证据**：两平台环境清单（版本/前缀/命令/缓存关键变量）、构建日志、ctest 日志、导出树 identity、exe/组件 SHA、`--capabilities` JSON、两次运行日志与 summary、CSV SHA 集合、依赖证据、受控修改 patch/前后 SHA/输出对比；环境不可得必须写“未验证+复现命令”，不得以退出码冒充科学验证。
- **入口**：K2-2 完成后由主审复核合同符合性，再交 K2-3 双平台执行；K2-3 通过后才进入 K2-4 正式验收与交班。
- **复用旧环境**：Windows 本机 `D:/ProgramFiles/Geant4`（11.3.2 + GDML）、`D:/ProgramFiles/Qt/5.15.2`；Linux 用 conda-forge 11.3.2（README 配方）；不要求重装 SDK，但 K2-3 必须记录实际前缀与版本。

---

## 11. 待实现、未验证、风险与否决项

| 项 | 状态 |
|---|---|
| 导出器/模板构建器/GUI 入口/CLI/测试 | **未实现**（K2-2） |
| 打包 `export-template/` 资源与安装版可用性 | **未实现**（K2-2） |
| CMake `G4USIM_STANDALONE_EXPORT` 开关 | **未实现**（K2-2） |
| Windows/Linux 独立构建运行/受控修改 | **未验证**（K2-3） |
| 本合同的模板身份 `1862a858…` 与 314 文件清单 | 由当前 worktree 计算；实现若改动模板文件必须同步合同 r2 并重算 |
| 许可：仓库无项目根 LICENSE | 风险已知；manifest/README 只陈述事实，不臆造；再分发需用户决定 |
| Windows Qt5/XercesC 依赖 | 依赖已知（CMake 自动推导 XercesC；Qt5 需显式 `Qt5_DIR`）；缺依赖记阻塞不绕过 |
| S-B 2 线程确定性 | 不承诺；只用 S-A 1 线程做确定性观察 |
| 导出后 GUI 继续开发（Python 侧） | 不属于 K2 子集；GUI 是工具，导出工程只含后端 C++/CMake |
| `scripts/`、`test/` 不随导出 | 会失去 m0 Python 回归；导出 README 明示“组件 CTest + 后端运行”为验收路径，不承诺 Python 测试框架 |

**范围外建议（不实现，仅记录）**：可选的 `export-project --verify-build` 自检子命令；Linux 上以 `-sdk` 方案导出 vendored Geant4（已有 C6 可参考）；把导出工程接入 L2 独立执行/CI；对 `examples/08_parallel_world_grid` 等更多示例的导出扩展。以上都不得进入 K2-1/K2-2 验收，需另立清单项。

---

## 附录 A：代表项目与闭包身份

**S-A `examples/07_parallel_world_box/` 文件 SHA-256**：

```
3b910234669554b98ef69f2170a793ff1de2d5e3f79419b2cda1cfd231f21ad4  main.ini
ac7b7488c25c297fe053ee780d7700bdd101720566a4c3b57f9c4c9b342e78aa  geometry.ini
34b49e7d980fd90ab3758452479f9c0b78aad540e1360cc1b3f9448fe2cd49c6  materials.ini
3350c6c662c872acf660c0ad5a1eafa48478c338b0136be8492dbbb41f4e440c  parallel.ini
9ae3ca2b7ff8a3c51a775be5d03905ba5d6baaeac540a89e116b8ad9c54eb8a2  run.mac
31f14e2fedd981a3391bd81ba6ca7638708ed74ca5a6448e62c23d318da0c486  README.md
```

**闭包**（`author/closure-files.sha256`，314 行 = 模板 308 + S-A 6）：

- 模板身份（308 文件）：`sha256_sorted_sha256_path_lines_v1` = `1862a858a532f0ff9178c77631308cb2c689bc3dd5f4e683faf2217cdc2110c8`（blob 30292 B）；
- 全清单身份（314 文件）：`c8e2a0b79cb4164fc6ea43d6cfda65ea2ac52f7c5fbadc9facd9ee2bc2fd9157`（blob 30941 B，即 `closure-files.sha256` 文件本身）；
- 目录计数：main.cc 1、CMakeLists.txt 1、CMakePresets.json 1、cmake 2、include 119、src 107、config 30、macros 28、tools 9、schema 2、examples/07 6、README.md 1、docs 4、packaging/licenses 3。

## 附录 B：冻结消费者身份（SHA-256 前缀）

| 文件 | SHA-256 |
|---|---|
| `gui/g4usim_gui/core/experiment_bundle.py` | `f1150873…` |
| `gui/g4usim_gui/core/experiment_workflow.py` | `4efcf4f0…` |
| `gui/g4usim_gui/writers/package_writer.py` | `a0b79625…` |
| `gui/g4usim_gui/writers/main_ini_writer.py` | `6390d5ed…` |
| `gui/g4usim_gui/writers/macro_writer.py` | `984034b3…` |
| `gui/g4usim_gui/core/run_editor_resources.py` | `51a5e11c…` |
| `gui/g4usim_gui/core/install_layout.py` | `b7988fc5…` |
| `gui/g4usim_gui/core/wizard.py` | `36d0f4cf…` |
| `gui/g4usim_gui/experiment_cli.py` | `20d7bb87…` |
| `gui/g4usim_gui/window/experiment.py` | `404d4324…` |
| `packaging/build_sdk_package.py` | `5819b0ce…` |
| `packaging/build_package.py` | `12c9e0ae…` |
| `packaging/build_linux_package.py` | `12b4cea5…` |
| `packaging/installer.iss` | `5295d200…` |
| `CMakeLists.txt` | `9fb42be1…` |
| `cmake/BuildIdentity.cmake` | `8d9a2d06…` |
| `cmake/WindowsRuntime.cmake` | `48ea39ac…` |
| `include/Core/BuildInfo.hh.in` | `1886acb1…` |
| `main.cc` | `a9dfdbb1…` |
| `src/Core/SimulationManager.cc` | `ddc95e5b…` |
| `src/Output/RunSummary.cc` | `3c6a5bf5…` |
| `src/Scoring/ScoringManager.cc` | `711d23dd…` |
| `src/Geometry/VolumeBuilder.cc` | `acdbadfd…` |
| `src/Physics/PhysicsFactory.cc` | `15a00794…` |
| `src/Templates/TemplateFactory.cc` | `84ee5550…` |
| `src/Detector/DetectorConstruction.cc` | `c3405154…` |
| `src/Core/Geant4DataLocator.cc` | `027a444c…` |
| `docs/collab/decisions/20261107-k2-closeout.md` | `3dbd9629…` |
| `README.md` | `f8a7ade2…` |
| `docs/Linux构建与验证.md` | `b3ae6f5f…` |
| `docs/中文使用手册.md` | `6de98165…` |
| `docs/功能支持矩阵.md` | `0d42e8cd…` |
| `docs/输出数据契约.md` | `d8bd0296…` |
| `scripts/test_k1_bundle.py` | `80726fb8…` |

## 附录 C：正反例与六链映射

| 用例 | 链 | 判据摘要 |
|---|---|---|
| P1/P2 导出 | 1/3 | 文件集合、manifest、identity、无绝对路径 |
| P3 确定性 | 3 | 两次导出全树 identity 一致 |
| P4 模板一致 | 3/5 | 打包模板与检出模板 `template_digest` 均 `1862a858…` |
| P5 CMake standalone | 3/4 | 配置成功、无 m0_*、component 可跑 |
| P6 dry-run/200 事件 | 4 | 完成 200/200、summary 身份齐全 |
| R1–R12 | 2 | 稳定错误码、目标与已有文件零变化 |
| GUI 禁用/CLI 拒绝 | 5 | 越界子集/无模板不可导出且提示原因 |
| 受控修改 | 4/5 | 1 行 diff、可重建、summary 新增键、物理输出一致 |

## 附录 D：错误码与失败面

错误码全集：`destination_exists`、`destination_parent_missing`、`linked_or_ambiguous_path`、`selection_unavailable`、`external_or_missing_input`、`unsupported_feature`、`absolute_path_remaining`、`export_template_unavailable`、`destination_inside_source`、`input_changed_during_export`、`template_identity_mismatch`、`write_failed`。K2-2 的测试必须逐码命中至少一次，并断言目标目录不存在/未变、staging 已清理、源输入 SHA 前后一致。
