# AR0 迁移基线冻结合同（草案）

- 状态：**草案 r2**，提交主审复验冻结。本文件只用于冻结 AR1/AR2 的迁移基线、责任边界与比较合同；不授权开始 AR1/AR2 实施。
- 修订：r2 依据主审 2026-11-08 对 r1 的独审意见修订（r1 已由主审归档，合同 SHA-256 `86ee166f779f1c5843ce7ba2d270ec3d3ba99b7638a9f23a6bf7d47e3ea83c13`，回执 SHA-256 `30769521c2fd5e47126b39e9bf5ddd72583bca984a20eb18e81868a05454a2dd`）；逐项对照见附录 D。修订后的回执位于 `out/collab/20261108-ar0-ar2/author-ar0/r2/receipt.json`。
- 作者：DSH（DeepSeek Harness）执行端；创建时间见作者回执 `created_utc`。
- 基线（已核实，详见 §1）：仓库 HEAD `25487eb13432c5f4e968aa405607056f6a8febce`（分支 `roadmap/Q2-scientific-baselines`，tag `k2-closed-pre-architecture-20261108`）；K2 闭合提交 `55ef3d62`；正式工程/测试基线 `64bacb3e412ace7bf82fa9cf5969af679112c61b`；产品源基线 `b1a7ffbc0519a29cb37b458e2e1542640956976a`；模板身份 `b2285d117a557614782eb8656593c2a64b9caba4538de91410126d7db35ba878`（309 成员，3,820,084 B）。
- 本文件与作者回执的 SHA-256 由回执登记；合同冻结后，任何数值判决都不得以"看到新结果后再调容差"的方式修改（见 §10）。

## 0. 门禁、范围与停止条件

| 项目 | 内容 |
| --- | --- |
| 本切片交付 | 真实生产者/消费者/线程/所有者/阶段/失败语义/旧格式/回退点表；输入、源码、环境、既有证据身份；有限比较矩阵、自然变化白名单与原数值/科学判据；当前 scorer 扩展触及模块；待冻结项 |
| 本切片允许写入 | `docs/collab/decisions/20261108-ar0-contract-draft.md`（本文件）与 `out/collab/20261108-ar0-ar2/author-ar0/` 下的作者回执/证据（r2 使用 `author-ar0/r2/`） |
| 本切片禁止 | 修改产品源码、测试、模板、manifest、schema；构建；运行模拟或性能测量；覆盖 dirty 文件或 `independent` 证据；调用网页模型；提交/推送 |
| 冻结门禁 | 主审按本文件与源码逐项核验并书面冻结；只补"确实缺失且能约束迁移"的合同测试，不重复 K2 全矩阵 |
| 停止条件 | 所需科学标准或接口兼容决策未定义时，相关改造不得开始；遇到缺标准只记缺口（§12），不猜容差 |
| AR1/AR2 授权 | 本文件不是授权；AR1/AR2 由主审在冻结后逐项派工；第一批完成整批后停并汇报 |

## 1. 身份与证据基线

### 1.1 源码、构建与交付身份

| 对象 | 值 | 备注 |
| --- | --- | --- |
| 仓库 HEAD | `25487eb13432c5f4e968aa405607056f6a8febce` | `git rev-parse HEAD`，AR0 只读起点 |
| 分支 / tag | `roadmap/Q2-scientific-baselines` / `k2-closed-pre-architecture-20261108` | tag 指向 K2 闭合提交 |
| K2 闭合提交 | `55ef3d62` | K2 交班快照 |
| 正式工程/测试基线 | `64bacb3e412ace7bf82fa9cf5969af679112c61b` | K2 最终验收提交 |
| 产品源基线 | `b1a7ffbc0519a29cb37b458e2e1542640956976a` | 受控修改对比的基准产品源码 |
| 模板身份 | `b2285d117a557614782eb8656593c2a64b9caba4538de91410126d7db35ba878` | 309 成员，3,820,084 B，`sha256_sorted_sha256_path_lines_v1` |
| K2 产品 source_fingerprint | `3d414de07b3d95e6e1c8f669e2fcb26d8109021eb5b23d805d2a49a4c982ed07` | K2-3 r6 原生基线；受控修改后 `4d09a8324605b32656cbaa570bab0cd759ceadbb64c28d1ba31a54b1c7018fa6` |
| 当前工作区既有二进制 | `build_vs2026/Release/G4UniversalSim.exe` SHA-256 `42b37beba7de2f1cb2547a148052216b779b5b74b6a7d6b88139026969061e30`，2,984,960 B | 2026-11-07 既有构建，**非 AR0 构建，不作验收身份** |
| 模板 manifest | 记录于 K2-3 回执 `58af4b22…` | 本文件不重复声明其 SHA |

**基线取用规则（主审 r2 口径）**：AR0/AR1/AR2 的源码基线采用 tag `k2-closed-pre-architecture-20261108` 指向的生产源码，加上每个文件的真实工作区状态；已存在的监督端文档 dirty 保留、不清洗、不提交；`tracked` 修改数与未跟踪文件数是两个不同量纲，不构成冲突（见 §1.4）；比较前用文件 SHA-256 与 `git diff <baseline> -- <product paths>` 核对即可，不要求把工作区清成干净树。

### 1.2 环境身份

| 对象 | 值 |
| --- | --- |
| 操作系统 | Windows 11 桌面（本项目主开发/验证机；K2 Linux 证据为 WSL2 Ubuntu 24.04，GNU 13.3.0，conda-forge Geant4 11.3.2，`micromamba run -p /home/u123/g4env`） |
| 编译器 | MSVC 19.51.36246（VS 18 2026 BuildTools） |
| Geant4 | 11.3.2，前缀 `D:/ProgramFiles/Geant4` |
| CMake | 4.3.2 |
| Python | 3.11.9 |
| Geant4 可视化 Qt | Qt 5.15.2（`D:/ProgramFiles/Qt/5.15.2/msvc2019_64`，供 Geant4 VIS/驱动） |
| Python GUI Qt 绑定 | PySide6 6.11.1（Qt 6 ABI；`gui/requirements.txt` 约束 `PySide6>=6.11.1,<6.12`） |
| 环境差异规则 | 上面两个 Qt 来源相互独立，不能笼统写作 "Qt5"；跨平台/跨编译器数值不预设 bitwise 相同；同平台同编译配置同数据才允许要求可确定部分逐项相同（§10） |

### 1.3 既有证据身份

| 对象 | 值 |
| --- | --- |
| K2 最终验收 | `docs/collab/decisions/20261107-k2-final-acceptance.md`（SHA-256 `14938cb5f12ac59e7db23dcb720568856228b6902085e4264f15bfeacb083a56`）：K2-1/K2-2/K2-4 通过，K2-3 限制签收；12 原报告 734 用例、376,754 断言、0 失败、0 跳过 |
| K2-3 回执 | `58af4b22d970172a539be995ce647156e6aa34e92050437de07cf6f5941cc703` |
| K2-4 最终回执 / outbox | `cfbdf1072eec68a6aa57120bd0c80f1fdd84e9d847a02274682da372af8e2da2` / `0dde3f0f7b43379d…` |
| K2-4 repair receipt | `53d3129013277c2ff48d0d3bf264003fa6c3ac5fd0982984b36299a9a71b7833` |
| K2-4 observation receipt | `e717870c…` |
| AR0 r1 合同 / 回执 | 合同 `86ee166f…`（主审已归档） / 回执 `30769521…` |
| 本阶段依据文件 | `docs/架构优化规划.md` `d17fb81a82e987ab9f0d0061de87aebfe6f970114af527765d44a8002144dca5`；`docs/collab/decisions/20261108-ar0-ar2-closeout.md` `6b29c19e88cea5189bfe141e0e4087abb8a5be9b2eca7cdb3cdc88fb8834695b`；`AGENTS.md` `5a0e26bf23a12550821233838464c1cc988a276d18e3b8ebbaac610e49130d1d`；`docs/collab/CURRENT-SUPERVISION.md` `1df932164b97d506427fff4648a307da3e9e2c74d8bbece691ce5b773c475d13` |
| H2 科学合同 | `docs/collab/decisions/20261106-h2-contract-freeze.md`（SHA-256 `02a86b1aba435222183d0d24e18ee57f04b57e05d0607f08552ef4cd2eafa5b2`）；证据根 `docs/verification/h2-final-20261106/` |
| H3 科学合同 | `docs/collab/decisions/20261106-h3-contract-freeze.md`（SHA-256 `4e6a961eaca78695231d81ab9cd27b7f1049231be99e417a103d2909a54ed79c`）、网格导航最小修复决定 `20261107-h3-grid-navigation-minimal-repair.md`（SHA-256 `0c6f4928739d498081af1509ba6e889d31a9bbe41d5e1f1585e11090ab549b12`）；证据根 `docs/verification/h3-final-20261107/` |
| F3 性能合同（不参与本批） | `docs/collab/decisions/20261107-f3-contract-freeze.md`；AR0/AR1/AR2 不执行 F3 时间/内存批次 |

### 1.4 工作区状态

本文件写作时实测（命令与输出记录在作者 r2 回执；写入本文件不改变已跟踪文件数量）：

- `git status --porcelain` 共 **115** 项：已跟踪修改 **13** 项（其中 `gui/g4usim_gui/core/export_project.py`、`scripts/run_m0_tests.py` 两项为 stat-only：`git hash-object` 与 `HEAD:path` 相同，内容未变；其余 11 项为监督端文档修改），未跟踪 **102** 项（监督端/协作文档，不属 AR0）。
- 规划 §8 记载的"五项 tracked dirty"与当前未跟踪数量不冲突：tracked dirty 指已跟踪文件的修改，未跟踪数是未入索引的监督端文档；两者量纲不同，且部分 tracked 差异产生于规划写作之后。
- 基线规则见 §1.1：以 tag 生产源 + 逐文件真实状态为准，保留既有文档 dirty，不清理工作区；比较前用文件 SHA-256 与产品路径 `git diff` 核对。
- AR0 未构建、未运行模拟、未运行性能测量、未修改产品/测试/模板/schema/manifest。

## 2. 外部兼容基线（迁移不得破坏）

| 外部格式 | 版本/标识 | 生产入口 | 消费入口 | 兼容规则 |
| --- | --- | --- | --- | --- |
| 主 INI | `[general] schema_version = 1` | GUI `main_ini_writer` / 用户手写 | `ConfigManager`（IniReader 保留 file/section/key/原始值/行号） | 现有字段/默认值/单位/别名不变；新增字段只能向后兼容；**未知/未消费字段沿用现有 warning 语义**（`ConfigManager::GetUnconsumedWarnings` → `[ConfigWarning]`、`config_warning_count`），不是 fatal；真正非法的语法/越界/缺依赖仍拒绝（§6） |
| 几何 INI | `[global] version = 1`（legacy）或 `2`（strict） | `GeometryManager::LoadGeometryConfig` / GUI `geometry_ini_writer` | `GeometryConfig` 解析 + `VolumeBuilder` 构造；GUI 预览/导出 | v1 保持 historical warning 语义；v2 strict 继续拒绝重复 section/key 与未知 section/key；单位/别名/参数个数契约不变（§3 I2 表） |
| 材料 INI | 闭合 schema（`[material.<name>]` 等） | GUI `materials_ini_writer` / 用户手写 | `MaterialManager` | 未知 section/key 在对象创建前失败；`type = material` 仅兼容 deprecation，不得影响定义 |
| macro | Geant4 命令子集 | 用户 / GUI `macro_writer` | batch/csh preflight 与执行 | preflight 全量保留；既有交互命令拒绝语义不变；不得靠新增命令绕过 PreInit 门禁 |
| CLI | `--config/-c`、`--macro/-m`、`--output/-o`、`--run-name`、`--ui`、`--ui-session`、`--threads`、`--seed`、`--dry-run`、`--check-overlaps`、`--capabilities`、`--check-geant4-data`、`--inspect-macro`、`--inspect-run`、`--dump-effective-config`、`--session-*`、`--working-directory` | `main.cc` | 用户/GUI 外部运行/CI | 参数名/语义/退出码不破坏；新增必须可选 |
| 项目 JSON | `schema = G4UniversalSimProject`，`version = 8`；读端接受 int `1..8`，`version < 7` 或缺少 `pathSettings`/`runSettings` 走 legacy | `project.py` 写端 | GUI 打开/保存/迁移 | 迁移只能通过版本升级 + 旧版本读取测试 + 新副本，不覆盖用户原文件 |
| 项目快照封套 | `ENVELOPE = {runPackage, materialsSourceMode, geometrySourceMode, materialDocument, geometryDocument, materialsSummary, geometrySummary}`；`REQUIRED` 见 `project_snapshot.py:120`；`LAYOUT` 固定包内路径 | `project_snapshot.py` | K1 bundle、运行历史、导出 | 封套/必填键/固定布局不变；未知键处理规则不变 |
| K1 实验包 | `schema = g4usim_experiment_bundle`，`version = 1` | `experiment_bundle.py` | 外部工具、K2 导出复用 | manifest 字段/成员校验/replay 语义不变 |
| K2 导出清单 | `schema = g4usim_export_project`，模板清单 `g4usim_export_template_manifest`，身份算法 `sha256_sorted_sha256_path_lines_v1` | `export_project.py` | 独立工程构建/验收 | 字段/枚举/身份算法不变；模板身份由作者在每个稳定候选重新生成、主审 check/冻结；不得硬编码旧值（§12 G6） |
| 运行输出 | hits/event CSV `output_csv_schema_version=3`；dose v1/v2、fluence v1/v2、displacement v1、let v1/v2、histogram v3、edep summary v3/v4、mesh CSV v2、ROOT `g4usim_root_v4`、`scorer_statistics` v2、phase-space v1、trajectories v1、`run_summary` v1、`run_metadata_json_v1`、provenance `g4usim_provenance_v1`、effective config `g4usim_effective_config_v1` | 各 scorer/`OutputManager`/`RunSummary`/`SimulationManager` | GUI 结果页、绘图、扫描、场景分析、自动合并、扩展 API、外部消费者 | 列名/单位/表头语义/版本标识不得破坏；新增列必须升版本并保留旧读端；身份/来源字段只增不删 |
| 线程/文件命名 | 首轮 `*_tN`，后续 `*_tN_rR`；master/worker 分离 | `OutputManager` | 证据核对/合并工具 | 命名与后缀语义不变；不得并发覆盖 |
| GUI 支持面 | 现有页面/动作/编辑器交互 | GUI | 用户 | 本批不改变 GUI 支持面；无控件状态迁移属于 AR4，AR1/AR2 只验证受影响的现有消费者 |

统一规则（来自规划 §8）：外部 INI/macro/CLI/项目格式默认不变；内部 typed 数据由适配器形成；确需持久化 schema 变更时单独加版本、旧格式读取测试与迁移副本；旧/新读写不得永久并行；每组字段先契约测试，再切换一个真实消费者，比较通过后删除临时路径；生产的对比不得靠双运行模拟完成；**内部工厂/描述类不引入新的公开 schema**。

## 3. 迁移接口清单

以下 I1–I10 是 AR1/AR2 允许触及的接口面。每项冻结"生产者 / 消费者 / 线程 / 所有者 / 阶段 / 失败语义 / 旧格式 / 输出证据 / 回退点"九元组；未列入者不得在本批顺手重构。

### I1 几何源加载与配置应用（事务边界）

| 维度 | 内容 |
| --- | --- |
| 生产者 | `ConfigManager` 读取 `[geometry] config`；`GeometryConfig::Load/LoadFromConfigManager`（`ParseVolumeSection`、`ValidateShapeContract`、`ValidateGeometryMaterials`、`ValidateVolumeProperties`）；`GeometryManager::LoadGeometryConfig`（`src/Geometry/GeometryManager.cc:234-266`）按以下**真实顺序**执行：①`:240-254` 解析与校验（`ResetCreatedGeometryObjectCount`、`configDiagnostics_.clear()`、`TemplateFactory::Create(templateName_)`、`BuildNodesFromFile`、`GetDiagnostics`、`ValidateRootNode`；此阶段尚未改动树，但会改动诊断与构造计数）；②`:255-256` 先替换 `templateRootNode_`、`rootNode_` 两棵树；③`:258-261` 若 `preserveUserVolumesOnLoad_` 关闭则清空用户体积，否则 `ApplyUserAddedVolumes()`（可能抛错）；④`:262-266` 最后才发布 `geometryConfigFile_`、`effective_->reader`、`inputFiles_`、`effective_->Accept(...)` 并 `MarkDirty()`。不能表述为"全部同时替换"。`SetPreserveUserVolumesOnLoad`（:462）与 `ApplyUserAddedVolumes`（:481）只在保留模式生效 |
| 消费者 | `DetectorConstruction::Construct` → `GeometryManager::BuildWorld`（`src/Geometry/GeometryManager.cc:539-566`）；GUI 几何编辑器/预览是**独立 Python 模型**（`geometry_editor_model` + `preview3d` 场景构建，PyVista/VTK 可选，缺依赖时 fallback 预览；不直接调用 C++ Manager）；有效配置注册表/收据（geometry 字段与 material/parallel 来源）；`run_summary`（`effective_geometry_*`、`geometry_config_warning_count`）；`VolumeBuilder`/Geant4 stores；H3 并行世界文件（独立入口 `ParallelWorldConfig`，不共享本事务） |
| 线程 | master 单线程：pre-init 解析/应用、`Construct()` 内建树；worker 不重建几何（MT 下 Geant4 分发已构建几何）。GUI 侧是独立 Python 数据流，不参与 C++ Manager 的三棵树状态 |
| 所有者 | `GeometryManager`（master）以 `std::unique_ptr<VolumeNode>` 拥有 `templateRootNode_`/`rootNode_`，并拥有 `userAddedVolumes_`、`geometryConfigFile_`、`shared_ptr<ConsumerState> effective_`；`GeometryRegistry` 只保存 `G4LogicalVolume*`/`G4VPhysicalVolume*` 指针索引（**非拥有**）；`VolumeBuilder` 拥有创建中的 helper 资源，最终 solids/logical volumes 由 Geant4 拥有 |
| 阶段 | pre-init（configure/load/macro 修改允许）；`Construct()` 时 kernel-constructed；初始化完成后几何修改命令必须拒绝（`GeometryMessenger` PreInit 门禁，`src/Geometry/GeometryMessenger.cc:154-176`） |
| 失败语义 | ①阶段解析/校验异常在对象创建前抛出（诊断已替换，树未换）；②两棵树替换后、发布前（`:258-261`）若 `ApplyUserAddedVolumes` 失败，会留下"新树 + 旧文件名/旧 reader/旧 inputFiles/旧 effective/dirty 未置位"的**部分提交**；③`BuildWorld` 先 `ValidateRootNode`，随后 `ResetCreatedGeometryObjectCount`、`registry_.Clear()`（:546）、`volumeBuilder_.Clear()`（:547），失败时旧 registry/索引已被清空——这是**静态阅读得出的风险**，AR0 未运行、未实测；④当前无事务回滚合同，M0 阶段保护只保证"运行前拒绝"。AR1 先在真实接口验证该部分失败/清理顺序，再按 §13 决策实现候选提交 |
| 旧格式 | 几何 INI v1 legacy（未知 section/key 为 warning）、v2 strict（重复声明/未知 section/key 错误，`src/Geometry/GeometryConfigDiagnostic.cc:295-317` 支持 v1/v2，:129/:140 拒绝重复）；别名（`SolidRegistry` 16 条，见 I2）；`box` 的 `size` 为全长（builder 转半长）；`tubs` INI 恰好 5 个参数（builder 兼容 >=5 与 size 简写，INI 禁止 size）；`metadata.*` 仅 `[A-Za-z0-9_.-]+` |
| 输出证据 | 几何诊断（`[GeometryConfigWarning] file:line [section]/key = value: ...`）；`run_summary` 几何字段；有效配置 geometry/材料来源；GUI 生成包中 `geometry.ini` 的 source mode；导出模板闭包中的 `config`/`schema`/`src` 成员 |
| 回退点 | 按切片提交回退生产改动；保留反例与失败日志；回退后旧 INI 文件必须可重新加载成功；不得把用户项目原地改写为失败状态 |

### I2 几何形状描述与构造工厂

| 维度 | 内容 |
| --- | --- |
| 生产者 | `VolumeNode`（值类型，字段：name/parentName/shape/shapeName/materialName/position/rotation/size/parameters/sensitive/bias/regionName/productionCuts/visual/placementType/userProperties/children）；`GeometryConfig` 的 shape 契约；`SolidRegistry` 条目（16 种，见下表别名）；`VolumeBuilder` 的 `BuildWorld/BuildVolume/BuildLogicalVolume/CreateSolid` 与 `Create*Solid`，布尔组合 |
| 消费者 | `DetectorConstruction`（构造）；GUI（`solid_registry_data.py` 驱动形状参数表、预览 sketch）；`schema/config_schema.json`（形状属性）；H3 并行世界（同一 builder/registry 复用）；导出模板（schema/config 成员） |
| 线程 | 构造仅 master/pre-init；`SolidRegistry` 为只读静态表；`Describe()` 派生 capability 不依赖 Geant4 状态 |
| 所有者 | `VolumeBuilder` 拥有创建中的 solids/helper 资源；`GeometryRegistry`/Geant4 拥有最终对象（registry 只是非拥有索引）；registry 数据编译期只读 |
| 阶段 | configure 校验 → pre-init 构造；未初始化或初始化后非法状态按 Messenger 规则拒绝；并行世界在初始化前注册 |
| 失败语义 | 未知 shape、参数个数/单位/范围错误按现有错误消息在前置校验或构造时拒绝；a5 形状不得作为 boolean 工具；tessellated 需 `file`/`file_unit` 且 STL 校验失败即拒绝；不得用空实现/占位构造冒充支持 |
| 旧格式 | 别名表：`box`(cube)、`tubs`(tube,cylinder)、`cone`(cons)、`trd`(trapezoid)、`eltube`(elliptical_tube)、`para`(parallelepiped)、`tessellated`(stl)；`shape` 空默认 `box`（GUI writer 行为）；v2 strict 下未知 property 拒绝 |
| 输出证据 | `test_geometry_a5`、`test_geometry_safety_contract`、geometry roundtrip backend、K2 S-A/S-B 导出构建（若受影响） |
| 回退点 | 保留旧 builder 分支/别名入口；先加 adapter 再切换；失败可按提交回退且旧 INI 仍可构建 |

**box/tubs 实际入口小表（r2 新增，逐入口区分）**

| 入口 | box | tubs | 代码依据 |
| --- | --- | --- | --- |
| 几何 INI（`GeometryConfig::ParseVolumeSection`/`ValidateShapeContract`） | 必须且只能有 `size`：恰好三个正长度，全长语义；出现 `parameters` 即拒绝（`box does not accept parameters`） | 必须恰好 5 个 `parameters`：`rMin,rMax,halfZ,startPhi,deltaPhi`（并做半径/角跨度校验）；出现 `size` 即拒绝（`this shape does not accept size shorthand`） | `src/Geometry/GeometryConfig.cc:588-599`（box :588-593；tubs :598-600） |
| 直接 builder（`VolumeNode`，如 GUI/代码路径） | `ValidateBoxSize(node.size)`：三个正长度；`G4Box` 使用 `size.x*0.5`/`size.y*0.5`/`size.z*0.5`（全长→半长） | `parameters.size()>=5` 时取前 5 个；否则若 `size.x/y/z>0` 使用简写 `rMin=0, rMax=size.x*0.5, halfZ=size.z*0.5, startPhi=0, deltaPhi=2π`；两者都没有则抛 `requires 5 tubs parameters or positive size shorthand`；最后统一 `ValidateTubsParameters` | `src/Geometry/VolumeBuilder.cc:496-534` |
| boolean tool（`SolidRegistry::ValidateBooleanTool`） | 需要三个正 `size`，否则抛 `box requires positive size x,y,z` | **至少 5 个 parameters**，否则抛 `tubs requires 5 parameters: rMin,rMax,halfZ,startPhi,deltaPhi`；boolean 路径**不套用 size 简写**（先被该检查拒绝） | `src/Geometry/SolidRegistry.cc:29-40`；提示注释 :27-28 |

其他形状的 INI 严格参数个数与 builder 兼容差异（sphere 6、orb 1、cone 7、trd/trap 显式字段、ellipsoid 3/5、torus 5、para 6、hype 5、polycone 2+列表、polyhedra 3+列表、tessellated 文件）在本批保持现有语义不变；AR1 只把 box/tubs 作为可实施切片，其余保留现有入口与明确适配，不得借机改语义。

### I3 几何 GUI 投影与文件生成

| 维度 | 内容 |
| --- | --- |
| 生产者 | `gui/g4usim_gui/editors/geometry_editor_model.py`：`HierarchicalVolumeRow`、`BooleanOperationRow`、`SimpleBoxGeometryModel`、`LayerRow`、`LayeredDeviceGeometryModel`、`GeometryDocument(EditableDocument)`；`gui/g4usim_gui/preview3d/`：`scene_builder`/`sketch_geometry`/`geometry_primitives` 由文档构建预览场景，`pyvista_preview_widget` 为可选 3D（缺 `pyvista`/`vtk` 时用 `fallback_preview_widget`）；`gui/g4usim_gui/writers/geometry_ini_writer.py::_generate_hierarchical`（头注释、`[world]`/`[volume.<name>]`、parent 默认 world、shape 默认 box、box size、parameters、shape properties、placement、material、position/rotation、sensitive/bias/region/copyNo、cuts、vis、`metadata.<name>`、`[volume.<target>.boolean.<i>]`、`_resource_value` 资源绝对路径）；`run_editor_model.py` 的 GPS/Region/Field/BiasRule 数据类 |
| 消费者 | 项目快照 `geometryDocument`/`geometrySummary`；`validate_geometry_document`/诊断；`main.ini` 的 `[geometry]` 与材料/并行配置；预览 3D/模型树；导出包 |
| 线程 | GUI 主线程；独立 Python 数据流，不调用 C++ `GeometryManager`；预览是编辑器模型的派生视图，不取代后端构建 |
| 所有者 | `G4USimProject`/`GeometryDocument`（编辑器草稿）；生成文件由写盘事务短暂持有；`RunPackage` 持有生成结果 |
| 阶段 | 编辑/生成发生在运行前；生成包为不可变快照；运行期不得改写 |
| 失败语义 | 校验错误阻止生成（`PackageValidationError`/报告）；round-trip blocker 阻止 editable 模式；资源缺失抛 `ValueError`；不得静默丢失版本标记或元数据；**本批不迁移 GUI 无控件状态，也不改变 GUI 支持面（AR4）** |
| 旧格式 | 项目 v8（读端 1..8，legacy <7）；几何 v1/v2 版本标记必须保留；shape property 键集合与 GUI 生成保持一致 |
| 输出证据 | GUI smokes（geometry editor、boolean、roundtrip backend）、K1 snapshots、`test_k2_project_export`（若模板/内容受影响） |
| 回退点 | 生成器/编辑器按提交回退；快照 schema 变更必须新版本，不允许旧快照被新读端误解 |

### I4 Scorer 配置、注册与内置能力

| 维度 | 内容 |
| --- | --- |
| 生产者 | `ConfigManager`（`[scoring]`、`[scoring.edep]`、`[scoring.displacement]`、`[scoring.filter.*]`、`[scoring.spectrum.*]`）；`ScoringManager::LoadFromConfig`（`include/Scoring/ScoringManager.hh:118`）配置开关/直方图/NIEL 表/过滤与谱 spec；`EnsureDefaultScorers`（:85）与 `RegisterScorer`（:84，空/空名/重复名拒绝）；GUI `ScoringEditableModel` → `main_ini_writer`；CMake 内置 scorer 编译成员 |
| 消费者 | `SensitiveDetector`/`SteppingAction`/`EventAction`/`RunAction` 的计分路由与生命周期；`OutputManager` 写出；`HistoryStatistics`；`run_summary`/有效配置导出；GUI 结果模型/绘图层；H2 volume filter/spectrum；H3 并行 detector |
| 线程 | master pre-init 配置；**每个 worker（`ActionInitialization::Build`，`src/Actions/ActionInitialization.cc:78-104`）和 sequential 运行都走 `CloneForThread(outputManager, threadId)`（`ScoringManager.hh:29`）**：复制开关/NIEL 引用/过滤/谱/直方图/相空间/轨迹设置并 `EnsureDefaultScorers`；**当前不复制 `scorers_` 自定义实例（G1），因此 sequential 与 MT 一样会丢失外部注册的 scorer**。NIEL 表按共享只读暴露 |
| 所有者 | `ScoringManager`（master 与每 worker/sequential clone）拥有 scorer 实例与配置 spec；`ScoringNumeric`/`HistoryStatistics` 为进程级静态工具或共享互斥存储；Geant4 拥有 master 构建的分母几何/材料信息 |
| 阶段 | PreInit 配置；BeginRun 解析延后粒子名（NIEL）并开 run；Begin/EndEvent 与 per-hit；run 前 `ValidateVolumeConfigsForRun`（:143）预检；运行期计分命令拒绝 |
| 失败语义 | 配置错误在配置阶段抛出（如 dose/fluence/displacement 需要启用独立 scorer；NIEL 文件缺失；粒子名不能解析）；运行期 SD 异常 `ReportScoringFailure`（:161）→ 中止 run；未知/未观察事实必须保持 unknown，不得伪装成功 |
| 旧格式 | `[scoring]` 键名与单位不变；`[scoring.edep]` 直方图配置语义不变；`[scoring.filter.*]`/`[scoring.spectrum.*]` 仅在 scoring 启用且 auto-create 下生效；`[scoring.displacement]` 粒子名为小写、表路径相对主配置目录 |
| 输出证据 | `test_scoring_numeric`、dose/fluence/let/ddd 测试、H2 volume 测试、H3 测试、`run_summary`、K2 导出与科学比较 |
| 回退点 | 迁移只加描述/适配器层，保留内置实现直接路径；旧配置读取测试必须通过；可按提交回退 |

### I5 Scorer 生命周期、输出与统计归并

| 维度 | 内容 |
| --- | --- |
| 生产者 | `ScorerBase` 虚接口（`BeginRun/EndRun/BeginEvent/EndEvent/ScoreHit/Write/Reset` + `name/enabled`，`include/Scoring/ScorerBase.hh`）；内置 `Edep/Dose/Fluence/LET/DisplacementScorer` 各自 per-thread 累计 map、filter/spectrum 与该线程该 run 的 history 事件计数（如 `DoseScorer.hh:39 events_`，`BeginRun` 清零、`EndEvent` 递增、`Write` 写入 CSV/ROOT/谱）；`HistoryStatistics`（逐事件 history-by-history `sum/sumSq/entries`、`RelativeError`、delta 法比值、`FigureOfMerit`、`UncertaintyStatus`、进程级 `Submit/Take/Clear`）；`OutputManager` 的 CSV/ROOT/统计写出；`RunSummary`/run_metadata |
| 消费者 | `OutputManager`（hits/event/直方图/统计/网格）；GUI 结果页/绘图/扫描/场景分析/合并工具；`output/provenance.py` 消费者；外部 CSV/ROOT 读者；K2/H2/H3 证据 |
| 线程 | 每 worker（以及 sequential）独立 scorer clone 与输出 clone（threadId）；worker `EndRun` 提交统计；master/主线程在 worker 之后取合并结果；共享登记表互斥；`HistoryStatistics` 不共享累计器。ROOT 走 **Geant4 analysis manager 的每线程实例 + 既有合并协议**（`include/Output/AnalysisOutput.hh:1-10`：每 run 一个文件，worker 填充的直方图/ntuple 由 Geant4 合并；无 per-thread ROOT 文件、无手工合并步骤），**不是 master 独占** |
| 所有者 | worker clone 拥有本线程累计状态与 writer；master `OutputManager` 拥有合并 writer 与登记表；Geant4 analysis manager 每线程各一份，由 Geant4 负责合并 |
| 阶段 | BeginRun → BeginEvent/ScoreHit → EndEvent → Write（worker）→ master 合并/统计 → finalize/summary |
| 失败语义 | 写出失败 `RecordOutputFailure` + `AbortRun`；首个失败锁存（stage/message）并进入 `output_failure_*`；统计不足/零总量按 `UncertaintyStatus` 标 unknown/insufficient；失败 run 仍可能留下部分文件，summary 必须 failed 并非零退出 |
| 旧格式 | 输出 schema 版本不变（§2）。`n_events` 分三层：①scorer 的每线程 CSV/ROOT 行 `n_events` = 该 scorer 在该线程该 run 的 **history 事件计数**（如 `DoseScorer::events_`），不是 metadata 总量；②合并后的 `scorer_statistics.csv` 中 `n_events` = 该 run 完成事件数（`RunAction` 以 `run->GetNumberOfEvent()` 传入），并按 `entries/events` 可对账；③`run_metadata.json` 的完成事件数是 run 完成的权威值，但不得用它替换①的线程级计数。合并后要求 `Σ(每线程 history events) == run 完成事件数`（固定线程分配的可控用例直接断言；调度可变时按事件键比较，见 §9） |
| 输出证据 | `test_dose_scoring`、`test_fluence_scoring`、`test_let_scoring`、`test_displacement_damage`、`test_statistical_uncertainty`、`test_h2_volume_scoring`、`test_parallel_world`、`test_run_summary`、H2/H3/K2 证据 |
| 回退点 | 输出算法/格式保持，任何迁移只发生在配置/构造层；如必须改输出，另立带版本与旧读测试的切片（本批不授权） |

### I6 Worker 构造与线程所有权

| 维度 | 内容 |
| --- | --- |
| 生产者 | `ActionInitialization::BuildForMaster`（`src/Actions/ActionInitialization.cc:55-68`）为 master 建 RunAction；`Build`（:78-104）在**worker 与 sequential 都会执行**：检查 SourceManager 非空 → `PrimaryGeneratorAction` → `WorkerRunContext`（`threadId=CurrentThreadIdOrZero()`）→ `masterOutputManager_->CloneForThread(threadId)`（无 master 时新建并 SetThreadId）→ `EnableThreadSuffix(true)` → `masterScoringManager_->CloneForThread(output,threadId)`（无 master 时新建）→ `SetCurrentThreadScoringManager` → 建 RunAction/EventAction/SteppingAction/TrackingAction。`DetectorConstruction::ConstructSDandField` 先 threadBiasing callback、FieldSetup，再按 `GeometryRegistry::GetSensitiveLogicalVolumes` 以单一 SD 工厂名绑定；并行世界在初始化前 `RegisterParallelWorld`，`ParallelScoringDetector` 三 Scope |
| 消费者 | 每 worker 的 SD/Step/Event/Run 动作；worker 输出文件；H3 并行 ghost step 路由；有效配置 thread-level 收据 |
| 线程 | master：几何/物理/源/共享只读表；worker：SD 实例、TLS scoring manager、output clone；sequential：同样走 `Build` 的 clone 路径（不是无 clone 的特殊分支） |
| 所有者 | TLS manager 指向本线程拥有的 clone；SD 实例由 Geant4 该线程拥有；并行 SD 每线程构造；master 不持有 worker 私有对象 |
| 阶段 | pre-init 注册/工厂；初始化期 `Construct/ConstructSDandField`；run/event/step |
| 失败语义 | TLS 缺失 → `ReportMissingThreadManager`；H3 归属解析失败 → `Failure`（无 owner 时不伪造）；SD transport 异常 → boundary failure + abort；worker 初始化失败必须传播到运行失败，不允许 master 继续报成功 |
| 旧格式 | 线程后缀命名；per-thread CSV 列语义；ROOT 合并对象名 |
| 输出证据 | `test_parallel_world`、`test_parallel_scoring_component`、`test_run_summary`（MT 双 run）、K2 受控矩阵 |
| 回退点 | 先加"描述→工厂"适配器并保持现有 clone 路径；自定义 scorer 无法提供可重建合同时，必须显式拒绝**该 API 的所有运行模式（含 sequential）**，不得只拒绝 MT 而静默丢 sequential 注册（G1） |

### I7 描述、能力与有效配置证据

| 维度 | 内容 |
| --- | --- |
| 生产者 | `SolidRegistry::Describe()`（deterministic capability JSON）；`EffectiveScoring`/各模块 `ExportEffectiveConfigFields`；`EffectiveConfigSupport::ConsumerState`（`Accept/Confirm/Record/Clone`）、`Field`（requested/resolved/origins/application_status/evidence_level/revision/configuration_generation）、`Registry`（Commit/ReplaceModule/Capture）；`config_schema.json`/生成表；GUI 能力表/支持矩阵 |
| 消费者 | 有效配置 JSON（configure/run/final/finalization）、`run_summary`、GUI 能力展示、K2 导出 manifest/build 信息、schema 驱动编辑器 |
| 线程 | 主要 master；field mutation 收据与 stage 绑定；worker 侧 thread_applied 证据由 run 收据表达 |
| 所有者 | `EffectiveConfig::Registry` 持有字段状态；模块 manager 只通过 state 句柄写；GUI 只读展示，不定义支持 |
| 阶段 | 枚举 `None/ManagerAccepted/KernelConstructed/ThreadApplied/RunValidated`；`configuration_generation` 随每次成功配置提交递增 |
| 失败语义 | 未确认值应用状态保持 unknown/not_applied；校验失败不得写 accepted；不得把"Manager 接受"当"内核已应用"；schema 生成表不得手改 |
| 旧格式 | effective config v1 字段只增不删；`config_schema.json` 覆盖文件/字段与 `excluded` 语义不变 |
| 输出证据 | `test_effective_lifecycle`、各 effective module 测试、`run_summary` 摘要键、schema coverage 检查 |
| 回退点 | 新增描述字段可选；旧消费者必须先兼容；schema 变更走生成器与版本 |

### I8 构建成员与导出闭包

| 维度 | 内容 |
| --- | --- |
| 生产者 | `CMakeLists.txt` targets（`G4UniversalSim`、`mergeHistograms`、GM/组件检查 targets）、逐文件 SHA256 → `G4USIM_SOURCE_FINGERPRINT`、BuildInfo；导出模板闭包 309 成员（`src/include/config/schema/docs/packaging/licenses/CMakeLists/CMakePresets` 等）与 `export_template_manifest.json` |
| 消费者 | 独立构建/CMake/CTest；K2 导出与安装包；CI；`run_m0_tests.py` cases；`export_template.py --check`；K2 manifest |
| 线程 | 构建工具链并行；不涉运行线程 |
| 所有者 | 仓库/模板清单；打包脚本（build_package/build_linux_package/build_export_template） |
| 阶段 | 构建/导出；模板身份由作者在每个稳定候选生成，主审 check/冻结后才可发布 |
| 失败语义 | 源文件缺失/不一致、依赖缺失、模板身份不匹配必须失败，不得静默降级；CMake target 失败不产出可用产物 |
| 旧格式 | 模板身份算法（双空格行、按路径排序）不变；`G4USIM_STANDALONE_EXPORT=ON` 时禁用 m0_* 注册与 scripts 运行目录、保留组件检查集合（`h2_volume_scoring_check`、`parallel_scoring_component`） |
| 输出证据 | `test_k2_project_export`、模板 check、CMake/CTest 日志、K2-3 回执、source_fingerprint |
| 回退点 | 源码改动导致 source_fingerprint 与模板身份变化属预期；旧证据保留原 SHA，不复用、不混用；模板重生成仅在候选稳定后统一进行；**包构建/安装验证按实际影响决定是否补充，不预先全面排除** |

### I9 输出身份、来源与可信消费

| 维度 | 内容 |
| --- | --- |
| 生产者 | `run_metadata.json`（`g4usim_provenance_v1`）：`execution_id`（每进程一次 32 hex 随机，不与 run/seed/revision 混用）、`build`（git_commit/git_source_state/source_fingerprint/编译器/构建配置/Geant4 + `git_state_scope=cpp_build_inputs`）、`inputs[]`（sequence/sha256/size/status，`input_coverage=project_readers_observed`、`input_observation=bytes_read_not_semantic_acceptance`）、`generated_files[]`（execution_id/scope/run/thread/sha/size/integrity_status） |
| 消费者 | `output/provenance.py` 驱动的 GUI/绘图/扫描/场景分析/自动合并/输出扩展；外部工具；K2/H3 对账 |
| 线程 | master/worker 共享登记表互斥；metadata 由 master 最终写 |
| 所有者 | `OutputManager` 登记表与 metadata writer；`execution_id` 进程级；scorer/summary 只读消费 |
| 阶段 | run 开始登记 inputs，写出时登记 generated_files；finalization 汇总 |
| 失败语义 | 登记文件丢失 → `artifact_integrity` 首因锁存并最终非零；metadata 自身 `self_reference_excluded` 唯一例外；缺失/未知版本不得降级 glob 可信消费 |
| 旧格式 | 无 metadata（legacy）与 v1 有清单无 provenance 的读取语义保持；mtime/size 不能替代 SHA |
| 输出证据 | `output_provenance`/`f1_output_identity`、`test_run_summary`、GUI provenance 测试、K2 科学比较 |
| 回退点 | 只增字段不改语义；旧消费者按版本分支；如改哈希算法须升版本并保留旧读测试 |

### I10 GUI 项目/快照持久化

| 维度 | 内容 |
| --- | --- |
| 生产者 | `G4USimProject`（schema v8）、`project_snapshot` 封套、`RunPackage` 布局、`main.ini`/`geometry.ini`/`materials.ini`/macro 生成器、K1 bundle 快照 |
| 消费者 | GUI 打开/保存/迁移/恢复、运行历史、导出/打包、测试夹具 |
| 线程 | GUI 主线程 |
| 所有者 | 项目对象/快照对象；不变量由 `_closed_object/_lexical_path/_read_inside` 校验 |
| 阶段 | 编辑/保存/生成包/导出；运行期只读 |
| 失败语义 | 不完整/未知版本/越界路径拒绝；不覆盖源文件；生成包失败清理 staging 并保留旧目标 |
| 旧格式 | project v1–8 读取；bundle v1；snapshot LAYOUT 固定 |
| 输出证据 | `gui_project_io`/F5 tests、K1 bundle 测试、K2 导出测试 |
| 回退点 | schema 变更必须版本+旧读测试+新副本；生成器按提交回退且旧工程可打开 |

## 4. 当前 scorer 扩展触及模块（责任模块清单）

> 用于回答"改一个 scorer / 编辑字段 / 构建成员要碰哪些责任模块"；文件行数仅作导航，不作架构评分。

| 组 | 文件 | 责任 |
| --- | --- | --- |
| F1 接口与注册 | `include/Scoring/ScorerBase.hh`、`include/Scoring/ScoringManager.hh` + `src/Scoring/ScoringManager.cc` | 虚接口、注册/去重/默认创建/克隆/生命周期分发 |
| F2 内置实现 | `include|src/Scoring/{Edep,Dose,Fluence,LET,Displacement}Scorer.*`、`EffectiveScoring.*` | 各 scorer 累计、配置适配、有效字段 |
| F3 配置解析 | `src/Config/*`（IniReader/ConfigManager）、`src/Core/SimulationManager.cc`（LoadFromConfig 顺序、校验、effective 捕获）、`src/Scoring/ScoringMeshConfig.*`、`schema/config_schema.json` | 字段读取/单位/默认值/拒绝语义 |
| F4 运行接线 | `src/Hits/SensitiveDetector.cc`、`src/ParallelWorld/ParallelScoringDetector.*`、`src/Actions/{ActionInitialization,EventAction,SteppingAction,RunAction,WorkerRunContext}.*`、`include/Scoring/ThreadLocalScoringContext.hh` | 每线程 manager、SD 路由、事件/步钩子、TLS |
| F5 输出/统计 | `include/Output/OutputManager.hh` + `src/Output/*`、`RunSummary`、`HistoryStatistics`、`ScoringMeshExport.*`、`AnalysisOutput`、provenance | 文件写出、统计合并、ROOT 合并协议、元数据/身份 |
| F6 GUI 模型/生成 | `gui/g4usim_gui/editors/source_physics_scoring_model.py`、`gui/g4usim_gui/writers/main_ini_writer.py`、`core/run_editor_import.py`、`widgets/config/run_config.py`、`core/run_editor_model.py` | 编辑字段→设置→INI；校验镜像 |
| F7 GUI 结果消费 | `gui/g4usim_gui/core/output/provenance.py`、结果模型、绘图层、扫描、场景分析 | 可信读取、列语义、版本拒绝 |
| F8 构建/测试 | `CMakeLists.txt`（targets/add_test）、`scripts/run_m0_tests.py`、`scripts/test_*scoring*`、`gui/smoke_tests/*scoring*`、C++ `scoringNumericCheck`/`h2VolumeScoringCheck`/`parallelScoringCheck` | 编译成员、回归入口、证据 |
| F9 导出/模板 | `gui/g4usim_gui/core/export_project.py`、`packaging/{export_template,build_export_template,build_package,build_linux_package}.py`、`packaging/export_template_manifest.json` | 源码闭包身份、独立工程导出 |
| F10 文档/矩阵 | `docs/功能支持矩阵.md`、`AGENTS.md` §0、`docs/agent-history.md`、`docs/输出数据契约.md`、`docs/输出身份与来源.md`、schema 生成器 | 支持等级与契约声明同步 |
| F11 科学基准 | `scripts/test_{dose_scoring,fluence_*,let_*,statistical_uncertainty,parallel_world,h2_volume_scoring}.py`、`scenarios/benchmarks/*`、Q2/H2/H3 证据 | 数值语义/容差/旧失败保留 |

变更映射（示例，AR0 记录事实）：
- 新增/修改一个 scorer 类型：F1+F2（实现与注册）→ F3（配置键/校验）→ F4（路由/构造，若需要）→ F5（输出列/统计）→ F6/F7（GUI 编辑与读取，若暴露）→ F8/F10/F11（测试、矩阵、基准）；若进入模板闭包，还涉及 F9 身份重生成。
- 仅编辑 GUI 字段：F6+F3（writer 校验镜像）+F8（smoke）+F10（支持矩阵状态）；不改变运行语义。
- 构建成员变化（CMake target/source list）：F8+F9（source_fingerprint/模板身份）+K2 导出证据；不改变物理语义但改变所有身份。

## 5. 线程、所有者与阶段矩阵

| 对象 | 创建线程 | 所有者 | 生命周期阶段 | 跨线程共享 |
| --- | --- | --- | --- | --- |
| geometry tree / registry | master | GeometryManager（`unique_ptr` 树）/ GeometryRegistry（非拥有指针索引） | configure→Construct | 几何构建后只读 |
| materials | master | MaterialManager | configure | 只读 |
| physics list | master | PhysicsManager/Geant4 | configure→init | 只读 |
| source manager / RNG | master | SourceManager/Geant4 | configure→BeginRun | phase-space 事件按 k 重放 |
| scoring config（flags/specs/NIEL） | master | ScoringManager | PreInit→BeginRun | clone 复制设置，NIEL 共享只读 |
| scorer instances | master 默认创建；worker/sequential clone | ScoringManager clone | BeginRun→EndRun | 不共享累计器；自定义注册实例不会进入 clone（G1） |
| OutputManager | master 创建；worker/sequential clone | 各自 writer；共享登记表 | initialize→finalize | 登记表互斥 |
| ROOT analysis manager | Geant4 每线程实例 | Geant4（每线程一份） | 文件打开→合并 | 由 Geant4 合并直方图/ntuple；无 per-thread 文件、无手工合并 |
| SD / parallel SD | worker（master 也构造 SD 供 sequential） | Geant4 该线程 | ConstructSDandField | 无 master 回退 |
| TLS scoring manager | 每 worker/sequential | 当前线程 | Build→run | 线程局部 |
| HistoryStatistics 合并 | 进程级互斥 | 静态存储 | EndRun worker→master | 共享互斥 |
| execution_id / metadata | master | OutputManager | initialize→finalize | 全进程一致 |
| effective config registry | master | 各模块 ConsumerState | configure→run validated | run 期只读 |
| GUI geometry document / preview | GUI 主线程 | 编辑器/项目对象（Python） | 编辑/预览/生成 | 不跨进程；不进入 C++ Manager 状态 |

## 6. 失败语义契约

1. **非法**配置（语法错误、越界值、缺依赖、未知枚举/shape）：在 Geant4 对象创建或 `beamOn` 前拒绝，退出码非零；不得"解析通过即视为支持"。**未知/未消费字段**按各格式现有规则：主 INI 为 warning（`ConfigManager::GetUnconsumedWarnings` → `[ConfigWarning]`、`config_warning_count`，见 `src/Core/SimulationManager.cc:1040-1075`），几何 INI v1 为 warning、v2 strict 为错误；本批不得把 warning 升级为 fatal 或反之。
2. 运行期计分/写出失败：锁存首个失败（stage/message/run/thread），请求中止；`run_summary` 必须 `status=failed` 并带 `output_failure_*`；进程非零退出；已写文件可保留但不得标记成功。
3. 线程初始化失败：必须传播为 run 失败，不允许 master 继续或摘要成功；worker 异常不得穿出回调。
4. 归属/材料/分母未知：保持 `unknown`/`not_applied`，不得默认 0 或伪造成功；H3 并行 owner 解析失败不得绕过。
5. legacy 读取：无 metadata/旧版本必须按既有 legacy 语义处理（可用但内容未验证），不得自动升级为已验证。
6. 失败证据：旧失败日志/报告保留原 SHA，不回写、不覆盖；同一失败不得用固定文件名反复覆盖。
7. AR1/AR2 维护失败语义：迁移不得把拒绝变成 warning，也不得把 failed/unknown 变成 success；任何变化须在比较矩阵中逐条登记。
8. 几何部分提交（I1 ②③阶段）与 `BuildWorld` 清空顺序是**静态阅读风险**，AR0 未实测；AR1 必须先用真实接口验证，再按 §13 决策处理，不得在合同中写成已实测失败。

## 7. 旧格式与版本索引

- 主 INI `[general] schema_version=1`；几何 INI `[global] version=1|2`（v1 legacy warning，v2 strict）；材料 INI 闭合 schema；macro Geant4 命令子集。
- 项目 JSON `G4UniversalSimProject` v8（读 1..8，<7 legacy）；项目快照封套/REQUIRED/LAYOUT；K1 bundle `g4usim_experiment_bundle` v1；K2 导出/模板清单 schema 与身份算法。
- 输出：hits/event CSV v3、dose v1/v2、fluence v1/v2、displacement v1、let v1/v2、histogram v3、edep summary v3/v4、mesh CSV v2、ROOT v4、统计 v2、phase-space v1、trajectories v1、run_summary v1、run_metadata/provenance、effective config v1。
- 旧读端要求：任何 schema/版本变化必须同时提供旧格式读取测试与迁移副本；新读端不得静默丢弃未知字段。

## 8. 有限比较矩阵（真实入口；AR0 只登记，不实施）

> 说明：下表只列**已注册**的 `scripts/run_m0_tests.py` Case 与真实命令/夹具入口；"新增（实现期）"列是 AR1/AR2 在实施时按需补的真实反例/探针，不属于 AR0 交付，AR0 不先实现。运行环境与身份见 §1；全部旧证据按原 SHA 引用。

### 8.1 G 几何加载/构造

| 入口（注册 case / 脚本 / 参数） | 输入夹具 | 迁移后必须比较 | 判据来源 |
| --- | --- | --- | --- |
| `geometry_safety` → `scripts/test_geometry_safety_contract.py --layer backend`（backend, exe）；`gui_geometry_safety` → 同脚本 `--layer gui`（gui, qt） | 临时生成的主 INI + `test/geometry/hierarchical_test.ini`；helper `main_config(template, geometry, output)` 构造合法/非法目录 | 配置接受/拒绝与错误消息、`created_geometry_object_count`（构造前失败必须为 0）、诊断码/文件行号、用户体积保留、effective/revision/dirty 状态 | 脚本内既有断言；合同 §3 I1/I2；M0-3B2B1/B2 既有决定 |
| `geometry_diagnostics` → `scripts/test_geometry_config_diagnostics.py --layer backend`；`gui_geometry_diagnostics` → `--layer gui` | `test/main_hierarchical.ini`、`test/main_layered_device.ini`、`test/geometry/*.ini`、临时 v1/v2 几何文件 | `[GeometryConfigWarning]` 文本与计数、v1 warning/v2 拒绝语义、未知/未消费 key、重复 section/key 行号 | 同上；AGENTS §7/§8 |
| `geometry_a5` → `scripts/test_geometry_a5.py`（backend, exe） | 临时几何文件（hierarchical 的 ellipsoid/eltube/torus/para/hype/polycone/polyhedra/tessellated；replica/parameterised） | 各形状接受/拒绝、参数个数契约、a5 不可作 boolean tool、STL 封闭性、体积/材料/放置 | 脚本内既有断言；合同 I2 表 |
| `geometry_roundtrip` → `scripts/test_geometry_roundtrip_backend.py`（integration, exe+qt） | 真实后端 + GUI 写盘器生成几何 | 生成 INI 与后端接受语义、源文件不被覆盖、版本/元数据保留 | 脚本内既有断言；I3 |
| `default_geometry` → `scripts/test_default_geometry_batch.py`（backend） | `test/main_hierarchical.ini` 默认几何 | 默认批运行完成、输出文件集合 | 脚本内既有断言 |
| `geometry_diagnostic_identity` → `scripts/test_geometry_diagnostic_identity.py`（static, cxx） | 编译期诊断码表 | 诊断码/身份稳定 | 脚本内既有断言 |
| 新增（实现期） | — | A→B 半失败反例（重复用户体积名、缺 parent、第二个附加节点失败）前后树/来源/revision/inputFiles/dirty 状态 | §3 I1；主审 r2 决策 |

### 8.2 S 计分/统计

| 入口 | 输入夹具 | 必须比较 | 判据来源 |
| --- | --- | --- | --- |
| `scoring_numeric` → `scripts/test_scoring_numeric.py`（backend, exe+uproot） | 临时主 INI/几何/材料 + 真实后端 | 数值累计（sum/sumSq/entries）、Estimator、事件数对账、CSV/ROOT 数值语义 | 脚本内既有断言；`docs/输出数据契约.md` |
| `dose_scoring` → `scripts/test_dose_scoring.py`（backend, exe） | 敏感体水/硅夹具（临时生成） | 质量分母、Gy 值、per-run CSV 行、统计列、`n_events` 线程语义 | 脚本内既有断言；I5 |
| `fluence_scoring` → `scripts/test_fluence_scoring.py`；`let_scoring` → `scripts/test_let_scoring.py`；`displacement_damage` → `scripts/test_displacement_damage.py`（后端 + uproot 视用例） | 各自临时夹具与 NIEL 表（`scenarios/semiconductor/niel/si_*.csv`） | 通量/长度语义、LET 比值与 delta 法、DDD 折积、零沉积分支 | 脚本内既有断言；AGENTS 2026-10-22 记录 |
| `statistical_uncertainty` → `scripts/test_statistical_uncertainty.py`（backend, exe+uproot） | 真实多次 run | `RelativeError`、`entries`、`n_events`、delta 法与 20 次独立 run 的离散对账 | 脚本内既有断言；`docs/输出数据契约.md` |
| `h2_volume_scoring` → `scripts/test_h2_volume_scoring.py`（backend, exe） | 文件内构造：1 MeV 光子穿过 10×10×0.1 mm `G4_Galactic` slab；V5（100 事件、0.1 mm / 10 mm³ = 1.0 mm⁻²、能量落入 [0.5,1.5) 第 5 bin）、边界值、V7 非法配置 | 过滤/谱分区、权重只计一次、bin 边界、V7 在 configuration/run begin 前失败 | H2 合同冻结 `20261106-h2-contract-freeze.md`（`02a86b1a…`）；证据 `docs/verification/h2-final-20261106/` |
| `parallel_world` → `scripts/test_parallel_world.py`（backend, exe；timeout 2400） | 文件内构造：default-off、单 box、规则 grid、材料别名、Stage A 拒绝矩阵、R-RUNTIME（mass 层非灵敏 + hits/event_edep 开）、R-SAME（mass 层与 parallel 副本同时灵敏）、Case M（两线程两 run） | 并行路由只进 dose/fluence、不写 hits/不进 event Edep、材料/分母/ghost 归属、Stage A 拒绝、空 hits 表头 | H3 合同冻结 `20261106-h3-contract-freeze.md`（`4e6a961e…`）+ 网格修复 `20261107-h3-grid-navigation-minimal-repair.md`（`0c6f4928…`）；证据 `docs/verification/h3-final-20261107/` |
| `h2_benchmarks`、`root_output`、`scoring_mesh`、`sd_context_failure`、`gui_h2_volume_config`、`gui_h2_volume_editor_ui`、`gui_dose_results`、`gui_fluence_results` | 各自既有夹具/临时输出 | 基准判据、ROOT 对象集合/类型/计数、网格 CSV、SD 边界失败、GUI 显示语义 | 各自脚本内既有断言；`docs/功能支持矩阵.md` |
| C++ 组件：`ctest -L "^component$"`（配置按 §8.5 E 行） | `h2VolumeScoringCheck`（component output dir + `${PROJECT_SOURCE_DIR}`）、`parallelScoringCheck`（component output dir） | 两组件测试名称/退出码/断言；H2 分区/权重/boundary；H3 专用入口只路由 dose/fluence | `CMakeLists.txt:141-162`（add_test/labels）；K2 组件合同 |
| 新增（实现期） | — | 自定义 scorer 1/2/4 worker + 两 run 隔离、sequential 注册不丢失；工厂失败不冒成功；零事件/缺 TLS | §3 I4/I6、G1 |

### 8.3 L 来源/生命周期

| 入口 | 输入夹具 | 必须比较 | 判据来源 |
| --- | --- | --- | --- |
| `effective_lifecycle` → `scripts/test_effective_lifecycle.py`（integration, exe）；`effective_receipt_view` → 同脚本 `--component`（static, cxx） | 真实后端 configure/run/final 流程；component 夹具 | `Accept/Confirm/Record` 阶段、`application_status`/`evidence_level`/`revision`/`configuration_generation`、非法时点修改拒绝 | 脚本内既有断言；§3 I7 |
| `effective_consumer_state`、`effective_geometry_materials`、`effective_source_physics`、`effective_output_mesh`、`effective_biasing`、`effective_scoring`、`effective_modules`、`effective_config_export` | 各模块默认/覆盖配置与真实运行 | 字段 requested/resolved/origins、manager/kernel/thread 阶段、summary 键、导出 JSON 语义 | 各脚本既有断言；`docs/输出数据契约.md` |
| `run_summary` → `scripts/test_run_summary.py`（backend, exe）；`command_state_gating` → `scripts/test_command_state_gating.py` | 多 run/失败收尾/无 run/目录切换等夹具 | summary 计划/完成/失败字段、状态、退出码、命令门禁 | 脚本内既有断言；M0 记录 |
| `output_provenance`/`output_provenance_backend` → `scripts/test_output_provenance.py`；`f1_output_identity`/`f1_input_provenance`/`f1_artifact_model`；`gui_output_provenance` | 真实输出目录 + 合成/真实 metadata | `execution_id`、inputs 账本、generated_files、integrity_status、缺失/损坏拒绝、legacy/v1 语义 | 脚本内既有断言；`docs/输出身份与来源.md` |
| 新增（实现期） | — | 迁移计划与真实应用不混写的收据比较；部分运行失败与输出错误可区分 | §3 I5/I7 |

### 8.4 U GUI/项目（本批只验证受影响的现有消费者）

| 入口 | 输入夹具 | 必须比较 | 判据来源 |
| --- | --- | --- | --- |
| `gui_geometry`、`gui_preview`、`gui_preview_primitives`、`gui_model_tree`、`gui_geometry_safety`、`gui_geometry_diagnostics` | offscreen QSettings 临时目录 + `GeometryDocument` 夹具/示例几何 | 编辑→生成文件语义、预览从文档派生（不调 C++ Manager）、校验/诊断显示、3D 缺依赖 fallback | 各 smoke 既有断言；§3 I3 |
| `gui_project_io`、`gui_project_snapshot_restore`、`project_snapshot_compat`、`gui_j2_*` | 项目 v8 / 旧版本 / 快照夹具 | v8 读写、快照闭合、legacy 读取、生成包失败清理 | 各脚本既有断言；§3 I10 |
| `k1_workflow`/`k1_roundtrip`/`k1_relocation_backend`/`gui_k1_*`、`gui_export_project` | K1 包/项目夹具；S-A/S-B 导出 | manifest/成员/重放/搬迁语义；导出动作入口与错误码 | 各脚本既有断言；K1/K2 交付 |
| 边界 | — | GUI 无控件状态迁移属于 AR4，本批**不**新增该类测试；不改变 GUI 支持面 | 主审 r2 决策 |

### 8.5 E 导出/交付

| 入口 | 输入夹具 | 必须比较 | 判据来源 |
| --- | --- | --- | --- |
| `k2_project_export` → `scripts/test_k2_project_export.py`（static） | `examples/07_parallel_world_box`（S-A）；wizard `single_target` 生成项目（S-B）；私有 portable fixture | P1–P8/R1–R12：闭包成员、manifest 字段、payload identity、模板身份、路径/链接拒绝、S-B staging→白名单重写 | K2 合同/冻结（`20261107-k2-contract-freeze.md`）；脚本断言 |
| `PYTHONPATH=gui python -B packaging/export_template.py --check --root .`；`packaging/build_export_template.py` | 仓库检出模板 | 310→当前 309 成员数、逐文件 SHA、identity、问题列表为空；打包模板与 checkout 同身份 | K2-3/`docs/verification/k2-build-20261107/README.md` |
| 独立 CMake/CTest：`cmake --preset vs2026-x64 -DG4USIM_STANDALONE_EXPORT=ON ...`；`ctest --test-dir build_vs2026 -C Release -L "^component$"` | 导出树 | 组件测试恰为 `h2_volume_scoring_check`、`parallel_scoring_component`；无 m0_*；构建/运行 200/1000 事件命令 | K2-3 冻结矩阵与回执 `58af4b22…` |
| `gui_export_project` | offscreen GUI + S-A 导出 | 菜单/动作入口、S-A 导出 identity、错误码显示 | K2-4 证据 |

### 8.6 Q 科学等价（只复用已冻结判据）

| 入口 | 输入/判据来源 | 必须比较 |
| --- | --- | --- |
| H2：`h2_volume_scoring`（V5/边界/V7） | `docs/collab/decisions/20261106-h2-contract-freeze.md`（`02a86b1a…`）；`docs/verification/h2-final-20261106/` | 分区/权重/bin 边界与原 V5/边界/V7 判据 |
| H3：`parallel_world` 的 default-off/box/grid/别名/Stage A/R-RUNTIME/R-SAME/Case M | `docs/collab/decisions/20261106-h3-contract-freeze.md`（`4e6a961e…`）、`20261107-h3-grid-navigation-minimal-repair.md`（`0c6f4928…`）；`docs/verification/h3-final-20261107/` | 薄层剂量/无扰动对照：B 相对区间边界 ±1%、C ±0.5%（原 99% 区间与限定病例，输入/N/种子/方法以原合同为准）；不得移植为其它物理量万能容差 |
| Q2：`docs/verification/q2-final-20261105/` + `docs/collab/decisions/20261105-q2-*-freeze-*.json` | Q2 各冻结决定 | 仅当 AR2 实际触及该物理量的计分/步/线程语义时，按原限定协议执行一个预先限定比较任务；不是 F3 性能测量、不新增 F3 批次、不改旧失败 |

## 9. 自然变化白名单（必须先冻结，实施时逐项核验）

| 字段/对象 | 允许自然变化 | 仍需核验 |
| --- | --- | --- |
| `execution_id` | 每进程随机 32 hex | 合法格式/唯一性；不与 run/seed/revision 混用 |
| 时间戳：`created_utc`、`summary_generated_at`、文件时间 | 实际运行时间 | 单调/合理；与执行记录一致；不写入计划未来时间 |
| 绝对路径：输出目录、输入原路径、GUI 源路径 | 机器相关 | 路径存在且与登记一致；导出/搬迁测试中不得残留本机绝对前缀 |
| `build.git_commit`/`git_source_state` | 构建时仓库状态 | 与实际源码清单一致；unknown 保持 unknown |
| `source_fingerprint`/模板身份 | 源码/模板变更导致 | 与实际文件一致；新身份必须由同一算法重算，旧证据只按原 SHA 引用 |
| `scorer_statistics.run_wall_time_s`/`fom_per_s` | 机器/负载相关 | 其余统计列/行数严格一致；FOM 与 wall time 数学一致；entries 与 run 完成事件数对账 |
| ROOT 文件字节布局 | 平台/编译器/版本相关 | 对象集合、分支类型、计数、数值语义一致；不要求整文件逐字节相同 |
| 线程调度/归并顺序 | 调度相关（线程数可固定，但分块/执行序不保证） | 按 **run/event（必要时 track/step）** 比较事件集合与合计：无缺失、无重复、归并量正确；**只有受控固定线程分配的用例**才逐线程严格相等；不要求跨线程行级顺序相同 |
| 每线程/scorer `n_events` | 该线程实际处理的 history 事件数 | 与 `EndEvent` 计数一致；合并后 `Σ 每线程 == run 完成事件数`（可控用例断言；可变调度按事件键核验） |
| PE/ELF 可执行文件身份 | 构建不可复现 | 记录实际产物 SHA；不跨构建冒充复现；Linux 仅在相同编译输入下预期相等 |
| 日志文本/进度行落点 | 时序相关 | 关键阶段/计数/失败行存在且与摘要一致；`sequence` 单调 |
| `template_identity`/`export-manifest` 的 `created_utc` | 导出时间 | 其他字段逐项一致；文件内容与身份可由文件重算 |
| K2/CI artifact 名称与运行 ID | 外部环境 | 与提交 SHA、报告目录和证据一致；不得把旧运行当新证据 |
| Geant4 Qt（Qt5）与 Python GUI（PySide6/Qt6） | 两个独立环境 | 记录各自版本来源；不能混为同一 "Qt5" 身份 |

## 10. 科学标准与容差（引用，不新造）

- 只允许复用既有已冻结判据；本文件不定义通用浮点容差。
- H3 薄层剂量/无扰动对照：B 相对区间边界 ±1%、C ±0.5%（对应原 99% 区间与限定病例）；输入/N/种子/方法以 `20261106-h3-contract-freeze.md` 与网格修复决定为准，不移植为其它物理量万能容差。
- H2 分区/权重/bin 边界以 `20261106-h2-contract-freeze.md` 的 V5/边界/V7 为准；Q2 各量以 `docs/collab/decisions/20261105-q2-*-freeze-*` 与 `docs/verification/q2-final-20261105/` 为准。
- 确定性比较：同平台、同编译配置、同 Geant4 数据、同种子、同线程模式；**只有同配置同运算顺序且可确定的量**才要求严格相同；多线程归并/跨平台不预设 bitwise，其余一律复用原判据。
- CSV/ROOT/JSON 按各自语义比较；ROOT 只比较对象结构/类型/计数/数值语义。
- `n_events` 语义见 §3 I5 与 §9：scorer/线程级用 history 计数，run 级合并统计用完成事件数并对账；完成事件数的权威值仍是 `run_metadata.json`，但不得用它替代线程级计数。
- 任何新数值容差必须在看新结果前写入独立冻结决定，否则记缺口并停止该改造。

## 11. 回退点与证据隔离

| 回退点 | 内容 |
| --- | --- |
| 仓库 tag | `k2-closed-pre-architecture-20261108`（K2 闭合快照） |
| 正式基线 commit | `64bacb3e`（K2 最终验收） |
| 产品源基线 | `b1a7ffbc` |
| 模板身份 | `b2285d11…`（309 成员） |
| AR0 身份 | r1 合同 `86ee166f…`（主审归档）、r2 合同与回执 SHA 见 r2 回执 |
| 证据引用 | K2-3 `58af4b22…`、K2-4 `cfbdf107…`、repair `53d31290…`、observation `e717870c…`；H2 `20261106-h2-contract-freeze.md`/`docs/verification/h2-final-20261106/`；H3 两决定/`docs/verification/h3-final-20261107/`；旧失败目录与报告按原 SHA 保留 |
| 切片回退 | AR1/AR2 各自独立提交；回退生产提交时保留新增测试、反例与失败日志；旧 INI/项目不得被原地改写 |
| 隔离 | `independent` 目录只读，作者不得写；作者只写约定 author 目录；K2 `out/collab/20261107-*` 证据不改不覆盖；r1 证据不覆盖 |

## 12. 缺口、已冻结项与证据边界

### 12.1 仍开放的缺口（不得猜）

- **G1 自定义 scorer 的注册与重建合同**：`RegisterScorer` 接受外部实例，但 `CloneForThread` 不复制 `scorers_`；`ActionInitialization::Build` 在 worker **与 sequential** 都走 clone 路径，因此外部注册在两种模式下都会丢失。**冻结方向（主审 r2）**：提供可重建描述/工厂覆盖 worker 与 sequential；旧对象 API 按真实消费者适配，或对缺少工厂构造的使用显式拒绝；不得只拒绝 MT 而静默丢 sequential。内部类名由作者设计，不引入公开 schema。具体工厂接口/失败语义须在 AR2 合同测试中冻结。
- **G2 几何加载事务语义**：`LoadGeometryConfig` 的真实顺序见 I1（解析→换树→合并用户体积→发布元数据），失败窗口会产生部分提交；`BuildWorld` 先校验、再清 registry/辅助资源，失败时旧索引已清空（静态风险，未实测）。**冻结方向（主审 r2）**：AR1 采用"候选树/用户覆盖/来源/revision 整体提交"；**不承诺 Geant4 任意重建回滚**；失败保留旧有效状态；先用真实接口验证 A→失败 B 反例或证明不可达。
- **G3 通用浮点/统计容差未冻结**：除 H2/H3/Q2 等限定判据外，没有可移植容差；跨编译器/跨平台只允许语义比较。新容差须单独冻结。
- **G4 其余形状兼容矩阵**：box/tubs 已在 §3 I2 表内枚举；sphere/orb/cone/trd/trap/ellipsoid/eltube/torus/para/hype/polycone/polyhedra/tessellated 保持现有 INI 与 builder 语义，AR1 不改；若未来要放宽，须另立切片。
- **E1 云/网络证据可用性**：本地 bridge 连接拒绝**不构成云 CI 网络证据**，也不得据此推断 CI 通过/失败；云证据只依据主审提供的已发布工件或明确日志，缺失时记 unknown。不得用"未连上"当作通过或阻塞理由。

### 12.2 已冻结/继承（不再作为 AR0 前置）

- **G5 effective config 证据等级映射**：继承现有 `EffectiveConfigSupport` 合同与既有 effective 测试；AR1/AR2 迁移只按既有阶段语义写收据，不新造映射。
- **G6 模板身份重生成协议**：已冻结——作者在每个稳定候选生成新 manifest，主审 `check`/冻结；只对受影响交付补测；禁止硬编码旧身份（`b2285d11` 为基线，`75ac99a9` 仅历史）。
- **G7 描述 API 版本化**：继承现有 `SolidRegistry::Describe()`/capability 语义；本批内部工厂不引入公开 schema 版本。
- **G8 输出 schema 演进规则**：继承 `docs/输出数据契约.md` 与既有版本规则；本批不改输出 schema。
- **G9 GUI 未知/不支持 scorer 展示**：本批不改变 GUI 支持面；无控件状态迁移属 AR4。
- **G10 工作区基线**：已冻结——tag 生产源 + 逐文件真实状态；保留既有文档 dirty；tracked 修改数与 untracked 数量不冲突；用文件 SHA 与 `git diff` 核对，不清洗工作区。
- **G12 K1/K2 导出与安装边界**：模板按稳定候选重生成、主审冻结；包构建/安装验证按实际影响决定，不预先全面排除；不因每次源码改动重开合同。

## 13. 已冻结口径与复验请求

主审 r2 已书面给出的口径（本文件据此修订，不再作为待决问题）：

| # | 冻结口径 |
| --- | --- |
| 1 | AR1 采用候选树/用户覆盖/来源整体提交；**不承诺 Geant4 任意重建回滚**（G2） |
| 2 | 公共 INI/项目/输出 schema 与 GUI 支持面本批保持；内部工厂不引入公开 schema |
| 3 | G5/G7/G8/G9 继承现有合同或留作未来任务，不作 AR0/AR1/AR2 额外前置 |
| 4 | 模板由作者在每个稳定候选生成，主审 check/冻结；只对受影响交付补测 |
| 5 | 基线 = tag 生产源 + 逐文件真实状态；保留既有文档 dirty；tracked 5 与总 untracked 数量不冲突；源 hash 与 `git diff` 核对即可，不要求清理工作区 |
| 6 | G11 本地 bridge 拒绝不是云 CI 网络证据，撤掉该推断（改为 E1 证据边界） |
| 7 | 环境 Qt 分列：Geant4 可视化用 Qt 5.15.2；Python GUI 用 PySide6 6.11.1（Qt6），不得笼统称 Qt5 |
| 8 | 自定义 scorer 冻结方向见 G1（可重建描述/工厂覆盖 worker 与 sequential；旧 API 适配或显式拒绝缺工厂用法） |

**复验请求**：请主审核验 r2 的 I1 真实时序、I2 box/tubs 入口小表、I4/I6 的 sequential clone 与 ROOT 合并协议、I5 的 `n_events` 分层、§6 的 warning/fatal 区分、§8 真实比较矩阵、§9 白名单与 §12 的缺口/继承划分，并据此冻结 AR0；冻结后按 closeout 逐项派工 AR1/AR2。

## 14. AR1/AR2 预置验收要点（来源：closeout；本文件不授权）

- AR1：先用真实接口验证 A→失败 B 反例或证明不可达；候选树、用户覆盖、来源与 revision 整体提交；失败保留旧有效状态（不承诺 Geant4 任意重建回滚）；box/tubs 单位/别名兼容按 §3 I2 表，其它类型保留现有语义；受影响几何/H3/K2 消费者通过；独立报告与回退提交。**新增事务反例属于实现期**，AR0 不先实现。
- AR2：真实消费者迁移；注册空值/重复/未知负控；1/2/4 worker 与两个 run 隔离、无丢失/串值；**sequential 注册不得静默丢失**；工厂失败不冒成功；确定性测试 scorer 不改主入口/中央内置分支；Edep/Dose/Fluence/LET/DDD 与 H2/H3 受影响数值/语义保持；若实际触及计分语义，按 H2/H3 原限定协议执行一个预先限定比较任务（**不是 F3 性能测量**）。
- 第一批交班：冻结最终源码/测试/模板身份；按影响完成原正式门禁及必要双平台/独立导出验证；未影响旧证据保留原 SHA 复用；报告改善事实/失败/限制/回退与第二批建议；更新状态后自动任务 PAUSED，先汇报。

## 附录 A：本次只读核查的源码/文档范围（摘要）

- 架构规划、AR 冻结合同、K2 最终验收、AGENTS/CURRENT、输出数据契约/输出身份与来源、K2 交接 README、H2/H3 冻结决定与证据目录。
- 几何：`include/Geometry/*`、`src/Geometry/*`（Manager/Config/Diagnostic/SolidRegistry/VolumeBuilder/Messenger/STL/GDML/Export）、GUI 编辑器/写盘器/预览。
- 计分：`include|src/Scoring/*`（ScorerBase/各 scorer/ScoringManager/ScoringMesh*/EffectiveScoring/Messenger/ThreadLocalScoringContext/HistoryStatistics）、`SensitiveDetector`、`ParallelScoringDetector`、`DetectorConstruction`、`ActionInitialization`、`OutputManager`、`AnalysisOutput`、`RunSummary`。
- 输出/身份：`docs/输出数据契约.md`、`docs/输出身份与来源.md`、`run_metadata`/provenance/effective config 消费代码。
- GUI/项目：`project.py`、`project_snapshot.py`、`geometry_editor_model.py`、`preview3d/*`、`source_physics_scoring_model.py`、`main_ini_writer.py`、`geometry_ini_writer.py`、`run_editor_model.py`。
- 构建/导出：`CMakeLists.txt`、`scripts/run_m0_tests.py`、`gui/g4usim_gui/core/export_project.py`、`packaging/*`、schema 生成器。
- 本附录只记录范围；逐文件 SHA-256 与读取清单见作者 r2 回执。

## 附录 B：证据与命令

- `git rev-parse HEAD`、`git tag --points-at <K2 closed>`、`git status --porcelain`、`git diff`（只读）。
- 既有证据：`docs/verification/k2-build-20261107/README.md`、K2-3/K2-4 receipts、`out/collab/20261107-k2-final/**`（只读）、`out/collab/20261107-k2-build/**`（只读）、`docs/verification/h2-final-20261106/`、`docs/verification/h3-final-20261107/`。
- 只读核对命令示例：`PYTHONPATH=gui python -B packaging/export_template.py --check --root .`；`python -B scripts/check_doc_links.py`；`grep -n` 定位源码行。
- 本阶段不构建、不运行模拟/性能测量；命令与输出只读记录在作者 r2 回执。

## 附录 C：本文件未包含的内容（明确边界）

- 不包含 AR1/AR2 的代码设计或实现计划，不包含新 API 命名定稿（仅记录候选边界）。
- 不包含新容差、新测试批次、新构建/安装产物、云 CI 结论。
- 不修改、不重生成任何模板/manifest；不提交、不推送。

## 附录 D：r2 对 r1 独审意见的修订对照

| 主审 r1 意见 | r2 处理位置 |
| --- | --- |
| 1 几何真实时序（`.cc:234-267`；头文件引用错误；不能称全部同时替换；GUI 独立 Python/PyVista；树由 Manager unique_ptr 持有；registry 非拥有；builder 辅助资源与 Geant4 生命周期；BuildWorld 未运行只能写静态风险） | I1 生产者/消费者/所有者/失败语义；I2 所有者；I3 线程；§5 矩阵；§6 第 8 条 |
| 2 box/tubs 实际入口小表（INI/builder/boolean tool；参数个数/单位/简写差异） | I2 "box/tubs 实际入口小表"（含代码行） |
| 3 `Build:78-104` sequential 也 clone；G1 不能只拒绝 MT；冻结方向为可重建描述/工厂覆盖两者；旧 API 适配或明确拒绝缺工厂；ROOT G4AnalysisManager 是每线程实例/合并协议 | I4 线程、I6 生产者/线程/回退点、G1、I5 线程/所有者 |
| 4 scorer `n_events` 按 scope/run/thread 的 history 计数（DoseScorer events_）；合并后与 run 完成数对账；白名单按 run/event 比较集合；固定线程才逐线程相等；浮点仅同配置同顺序严格 | I5 旧格式、§9 白名单、§10 |
| 5 主 INI 未知/未消费字段是 warning（GetUnconsumedWarnings）不是 fatal；保留各格式真实规则；GUI 无控件状态归 AR4；包构建按实际影响决定 | §2 主 INI、§6 第 1 条、I3 失败语义、I8 回退点、§8.4/§8.5 |
| 6 主审冻结决策（AR1 整体提交、无任意重建回滚承诺；公共 schema/GUI 支持面不变；G5/7/8/9 继承；模板作者生成/主审冻结；基线 tag+逐文件状态；G11 撤掉云推断；Qt 分列） | §1.1 基线规则、§1.2 环境、§12.2、§13 表、§14、E1 |
| 7 比较矩阵要真实脚本/注册 case/参数/fixture/比较量/判据来源；AR1 反例属实现期；H2/H3 精确文件引用；AR2 触及计分执行原限定协议（非 F3） | §8 全表、§14、§10；附录 B |
