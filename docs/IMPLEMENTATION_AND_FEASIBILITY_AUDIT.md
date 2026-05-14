# G4UniversalSim Implementation and Geant4 Feasibility Audit

审计日期：2026-05-13  
审计范围：当前仓库 `D:\Geant4\G4UniversalSim` 的源码、配置、macro、文档和构建脚本。  
审计性质：实现状态审计 + Geant4 可行性评估。本文不修改源码，只记录可追溯结论和建议。

更新说明：本文主体是 Round 0 前的审计快照。Round 1 已实现并注册 `OutputMessenger`、`AppMessenger`、`DetectorMessenger`；Round 2 已实现 `trd/trapezoid` -> `G4Trd`、`trap` -> `G4Trap`，并补齐 `layered_device copyNo/metadata` 透传。下方 Executive Summary、Mismatch Table、Roadmap 和 Test Recommendations 已按当前状态修正；详细源码证据章节仍保留原审计时点的追踪记录。

## 1. Executive Summary

| ID | Feature | Current Implementation | Runtime Availability | Geant4 Feasibility | Recommended Priority | Final Recommendation |
|---|---|---|---|---|---|---|
| 1 | `MaterialFactory` `volume_fraction` | Parser only | Not runnable | Feasible with moderate work | P2 medium-term | parser 可识别但后端明确抛异常；不要在可运行配置中使用，后续可按密度换算为质量分数实现 |
| 2 | GDML 输入 | Placeholder | Not runnable | Feasible with moderate work | P2 medium-term | 当前只生成 placeholder `VolumeNode`，`VolumeBuilder` 明确报错；建议作为 world replacement 优先实现 |
| 3 | STL 输入 | Planned only | Not runnable | Needs external dependency | P3 future work | 当前无接口；Geant4 可用 `G4TessellatedSolid`，但 STL 质量和材料/层级缺失风险高，不建议优先内建 |
| 4 | `LETScorer` / `DoseScorer` / `FluenceScorer` | Stub | Partially runnable | Risky / requires physics validation | P2 medium-term | `Dose`/`Fluence` 是 no-op，`LET` 只读未填充字段；应先补 dose/fluence，LET 需先定义物理口径 |
| 5 | `ParticleAggregator` | Stub | Not runnable | Straightforward | P3 future work | 类为空且未接入；适合作为后处理或 scoring/run 层统计，不应抢在输出/MT 修复前做 |
| 6 | 多线程输出与自动 merge | Partial | Partially runnable | Feasible with moderate work | P1 near-term implementation | 有 `_t0` 后缀和外部 merge 工具，但当前共享 `OutputManager`/`ScoringManager`，没有自动 merge，MT 有 race 风险 |
| 7 | `trap` / `trapezoid` | Implemented | Runnable | Straightforward | Completed in Round 2 | `trd/trapezoid` 已接入 `G4Trd`，`trap` 已接入完整 `G4Trap`；trap 参数仍需满足 Geant4 solid 约束 |
| 8 | Qt UI 界面 | Not implemented | Not runnable | Feasible but high complexity | Do not implement now | 当前只有 Geant4 UI/Vis 支持，未实现项目级 Qt UI target；先稳定 CLI/macro |
| 9 | `OutputMessenger` 与 `/AIHL/output/...` | Implemented | Runnable | Straightforward | Completed in Round 1 | 已注册最小命令集合：`setDir`、`setThreadSuffix`、`print`、`flush`、`close`；hits/scoring 开关仍归 `/AIHL/scoring/...` |
| 10 | 高级 biasing：importance / weight-window / splitting / Russian roulette | Planned only | Not runnable | Feasible but high complexity | P3 future work | 当前只实现 XS process-level biasing；高级几何/权重 biasing 与当前 XS 架构不是同一层，需单独设计和验证 |
| 11 | `layered_device` copy number / metadata | Implemented | Runnable | Straightforward | Completed in Round 2 | `copyNo` 已进入 `userProperties` 并传给 placement；`metadata.*` 已保存但不自动输出 CSV |
| 12 | `AppMessenger` / `DetectorMessenger` 默认注册 | Implemented | Runnable | Straightforward | Completed in Round 1 | 默认 executable 已注册 `/AIHL/app/...` 与 `/AIHL/detector/...`；运行后危险重配置仍需 warning/reinitialize |

## 2. Source Inspection Method

检查目录和文件：

- `include/`
- `src/`
- `main.cc`
- `CMakeLists.txt`
- `config/`
- `macros/`
- `test/`
- `docs/`
- `README.md`
- `MODULE_API_INDEX.md`

判断方法：

```text
I traced parser -> manager -> builder/action/output -> Geant4 backend.
```

具体检查方式：

- 使用 `rg` 搜索 12 项功能名、类名、配置 key、macro 命令和 Geant4 后端类名。
- 对每项功能追踪 `config / macro -> parser / messenger -> manager -> SimulationManager / main.cc -> DetectorConstruction / VolumeBuilder / Action / Output -> Geant4 backend`。
- 将源码证据与 `docs/COMMAND_REFERENCE.md`、`docs/中文使用手册.md`、`docs/中文几何配置说明.md`、`docs/未实现功能.md`、`MODULE_API_INDEX.md`、`config/` 和 `macros/` 示例交叉核对。
- 未执行完整物理 runtime validation；运行行为结论基于源码调用链，标注了需要 runtime test 的部分。

## 3. Geant4 Reference Sources

联网资料已可访问。本报告优先引用 Geant4 官方 Application Developers Guide、官方 examples/API reference 和 Geant4 官方 forum。

主要资料：

- [Geant4 Book For Application Developers 11.4](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/index.html)
- [How to Specify Materials in the Detector](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/GettingStarted/materialDef.html)
- [Importing XML Models Using GDML](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/Geometry/geomXML.html)
- [Hits, Sensitive Detectors, `G4MultiFunctionalDetector`, `G4VPrimitiveScorer`](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/hit.html)
- [Analysis Manager Classes and Parallel Processing](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Analysis/managers.html)
- [Touchables: Uniquely Identifying a Volume](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/Geometry/geomTouch.html)
- [Event Biasing Techniques](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Fundamentals/biasing.html)
- Geant4 official examples: `examples/extended/persistency/gdml`, `examples/extended/biasing`, `examples/basic/B3/B4` as referenced by the official documentation.
- Geant4 classes / APIs: `G4Material`, `G4NistManager`, `G4GDMLParser`, `G4TessellatedSolid`, `G4TriangularFacet`, `G4Trap`, `G4Trd`, `G4VPrimitiveScorer`, `G4MultiFunctionalDetector`, `G4PSEnergyDeposit`, `G4PSDoseDeposit`, `G4PSCellFlux`, `G4AnalysisManager`, `G4AutoLock`, `G4VTouchable`, `G4VBiasingOperator`, `G4GeometrySampler`.
- Geant4 forum references for CAD/STL practical caveats:
  - [Importing CAD geometries into Geant4: practical notes and common pitfalls](https://geant4-forum.web.cern.ch/t/importing-cad-geometries-into-geant4-practical-notes-and-common-pitfalls/14912)
  - [Import .stp files in geant4](https://geant4-forum.web.cern.ch/t/import-stp-files-in-geant4/10480)

## 4. Detailed Findings

## 1. MaterialFactory 中 `volume_fraction` 材料模式

### 1.1 Current implementation status

当前是 parser 可识别、后端明确未实现。`mode = volume_fraction` 不能作为可运行材料配置使用。

### 1.2 Evidence from project source

- File: `src/Materials/MaterialCommandParser.cc`
- Class: `MaterialCommandParser`
- Function: `ParseMode`
- Evidence: `volume` / `volume_fraction` 被解析为 `MaterialComponentMode::ByVolumeFraction`。

- File: `src/Materials/MaterialFactory.cc`
- Class: `MaterialFactory`
- Function: `BuildCustomMaterial`
- Evidence: `ByAtomCount` 调用 `G4Material::AddElement(element, atomCount)`；`ByMassFraction` 调用 `AddElement` / `AddMaterial`；其他模式直接抛出 `volume_fraction mode is reserved but not implemented`。

- File: `docs/中文使用手册.md`, `docs/COMMAND_REFERENCE.md`, `docs/未实现功能.md`
- Evidence: 当前中文文档多数已经标注 `volume_fraction` 是预留/未实现功能。

### 1.3 Call-chain analysis

```text
config parser: yes, MaterialCommandParser::ParseMode accepts volume_fraction
manager storage: yes, MaterialDefinition can carry component mode
MaterialFactory backend: no, BuildCustomMaterial throws
SimulationManager wiring: yes, material config can reach MaterialManager/Factory
Geant4 backend call: no for volume_fraction
调用链中断位置：MaterialFactory::BuildCustomMaterial
原因：ByVolumeFraction 分支未换算为 G4Material 支持的质量分数或原子数
```

### 1.4 Runtime behavior

用户在材料 ini 或 `/AIHL/material/addMaterial` 中使用 `mode=volume_fraction` 时，parser 会通过，但材料构建阶段抛出异常，运行不能继续。当前不安全。

### 1.5 Geant4 feasibility

Geant4 支持通过 `G4Material` 定义材料密度、元素/材料组分；官方材料示例中给出按原子数定义水分子、按质量分数定义空气，并使用 `G4NistManager` 获取 NIST 材料。官方文档明确 `G4Material` 是 tracking、geometry、physics 使用的材料对象，包含密度、状态、温度、压强等宏观信息。

Source:

- Geant4 Application Developers Guide: [How to Specify Materials in the Detector](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/GettingStarted/materialDef.html)
- Geant4 class: `G4Material`
- Geant4 class: `G4NistManager`

可行性判断：

- Geant4 原生常用接口是按 `natoms` 或 `fractionmass` 添加元素/材料，不是直接按体积分数混合。
- `volume_fraction` 不能简单等同于 `mass_fraction`。
- 若组分是材料，推荐按体积分数 `v_i` 和组分密度 `rho_i` 计算混合密度 `rho_mix = sum(v_i * rho_i)`，再计算质量分数 `w_i = v_i * rho_i / rho_mix`，然后调用 `G4Material::AddMaterial(subMaterial, w_i)`。
- 若组分是元素而不是材料，缺少元素体积密度语义，除非用户额外提供元素密度或把元素包装成材料，否则不应允许按体积分数添加元素。
- 对多孔材料、合金、复合材料、化学收缩/膨胀体系，简单理想体积混合可能不物理，需要文档声明近似。

### 1.6 Is it necessary for this project?

Recommended。

通用模拟框架中混合材料需求常见，尤其屏蔽、复合层、填充材料。该功能值得做，但必须避免把体积分数当质量分数。

### 1.7 Limitations and risks

- 体积分数需要组分材料密度，不能对任意元素直接生效。
- 混合体积非理想时，`rho_mix = sum(v_i*rho_i)` 只是工程近似。
- 体积分数总和必须校验为 1。
- 用户可能混用材料和元素；应强制 `volume_fraction` 组件必须可解析为 `G4Material` 或提供显式密度。

### 1.8 Recommended implementation plan

最小实现：

- 在 `MaterialFactory::BuildCustomMaterial` 中为 `ByVolumeFraction` 增加分支。
- 仅允许 component 解析为已知 `G4Material` 或 NIST material。
- 校验体积分数和为 1。
- 用每个 sub-material 的 `GetDensity()` 计算 `rho_mix`。
- 若用户配置的 `density` 与计算值差异超过容忍值，报 warning 或要求 `density = auto`。
- 调用 `new G4Material(def.name, rho_mix, ncomponents, state)` 和 `AddMaterial(subMaterial, massFraction)`。

后续增强：

- 支持 `density = auto`。
- 增加 `porosity` 或 void/air 体积分数便利配置。
- 增加单元测试：同一材料用质量分数与体积分数换算后成分一致。

### 1.9 Documentation correction

当前文档基本已经正确标注。建议保持如下措辞：

```text
`mode = volume_fraction` is parsed but not implemented by MaterialFactory.
Do not use it in runnable configurations. Volume fractions require component
densities and must be converted to mass fractions before constructing G4Material.
```

## 2. GDML 输入实现状态

### 2.1 Current implementation status

当前是 placeholder。配置和模板入口存在，但不会调用 `G4GDMLParser`，`/run/initialize` 会在 `VolumeBuilder` 抛出异常。

### 2.2 Evidence from project source

- File: `config/geometry/gdml_import.ini`
- Evidence: 文件存在，并声明 `file`、`world_name`、`sensitive_volumes`、`bias_volumes`。

- File: `src/Templates/GDMLTemplate.cc`
- Class: `GDMLTemplate`
- Function: `BuildNodes`
- Evidence: 创建一个 `shapeName = "gdml_placeholder"` 的 box world，并把 `gdml_file`、`gdml_world_name`、`sensitive_volumes`、`bias_volumes` 写入 `userProperties`。

- File: `src/Geometry/VolumeBuilder.cc`
- Class: `VolumeBuilder`
- Function: `CreateSolid`
- Evidence: 若 node 有 `gdml_file` 或 `template == gdml_placeholder`，直接抛出 `GDML geometry import is not implemented in VolumeBuilder yet`。

- File: `macros/run_gdml.mac`
- Evidence: macro 加载 `gdml` 模板并含 `/run/initialize`。注释说不要 initialize，但文件实际包含 `/run/initialize`，这是高风险示例。

### 2.3 Call-chain analysis

```text
config parser: yes, [gdml] is parsed by GDMLTemplate
template: placeholder only
manager storage: partial, values stored in VolumeNode::userProperties
DetectorConstruction/VolumeBuilder: no, G4GDMLParser is not called
Geant4 backend call: no
调用链中断位置：VolumeBuilder::CreateSolid
原因：GDML placeholder 被明确拒绝构建
```

### 2.4 Runtime behavior

使用 `gdml` 模板并执行 `/run/initialize` 会失败。`file`、`world_name`、`sensitive_volumes`、`bias_volumes` 当前只被保存为属性，不映射到真实 GDML volume，不会注册 sensitive/bias volume。

### 2.5 Geant4 feasibility

Geant4 官方文档说明 GDML parser 是 Geant4 可选组件，依赖 XercesC，可用于导入/导出 detector geometry。官方 examples 位于 `examples/extended/persistency/gdml`。典型用法是 `G4GDMLParser::Read(file)` 后通过 `GetWorldVolume()` 取得 world physical volume。

Source:

- Geant4 Application Developers Guide: [Importing XML Models Using GDML](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/Geometry/geomXML.html)
- Geant4 official examples: `examples/extended/persistency/gdml`
- Geant4 class: `G4GDMLParser`
- Geant4 class: `G4LogicalVolumeStore`, `G4PhysicalVolumeStore`

可行性判断：

- Geant4 支持 GDML 导入，但需要构建时启用 GDML/XercesC。
- GDML 通常更适合作为完整 world 导入，而不是塞进现有 `VolumeNode -> VolumeBuilder` CSG 树。
- 要给 GDML volume 追加 SD、region、biasing，需要在 parser 读入后遍历 `G4LogicalVolumeStore` / `G4PhysicalVolumeStore`，根据 volume 名称或 GDML auxiliary 信息映射。
- GDML 的材料定义、unit、重名 volume、auxiliary 信息和 overlap 检查都需要明确策略。

架构建议：

1. 优先选择“替换整个 world 的独立导入方式”。当前 `DetectorConstruction::Construct()` 只需要返回 `G4VPhysicalVolume* world`，这与 `G4GDMLParser::GetWorldVolume()` 最匹配。
2. 挂载为某个 parent volume 下的 imported sub-tree 难度更高，需要处理 imported world 的 mother/placement 和名称冲突。
3. 通过 template 生成特殊 `VolumeNode` 目前已经证明不合适，因为 `VolumeBuilder` 的职责是 CSG solid 构建，不是 GDML parser 管理。

### 2.6 Is it necessary for this project?

Recommended。

GDML 是 Geant4 官方路径，作为通用模拟框架的 geometry import 很有价值，优先级高于 STL。

### 2.7 Limitations and risks

- 构建依赖 XercesC/Geant4 GDML 组件。
- 名称映射复杂，GDML 可能自动重命名。
- `sensitive_volumes` / `bias_volumes` 需要匹配 logical volume 还是 physical volume，必须统一。
- GDML 导入后是否仍使用 `GeometryRegistry` 是架构关键点。
- 当前 `config/geometry/gdml_import.ini` 中 `region.SV1` 这类 key 未被 `GDMLTemplate` 消费。

### 2.8 Recommended implementation plan

最小实现：

- 新增 `GDMLGeometryLoader` 或在 `DetectorConstruction` 增加 GDML mode。
- `GeometryManager` 保存 `geometryTemplate == "gdml"` 和 GDML config。
- `DetectorConstruction::Construct()` 中若是 GDML mode，调用 `G4GDMLParser parser; parser.Read(file, validate); return parser.GetWorldVolume();`。
- 读入后遍历 logical/physical stores，向 `GeometryRegistry` 注册可匹配名称。
- 用 `sensitive_volumes` 标记 logical volume 并接入现有 `ConstructSDandField()`。
- 用 `bias_volumes` 标记 logical volume，以便 `BiasingManager::AttachOperators()` 复用。

后续增强：

- 支持 GDML auxiliary 信息映射 region/sensitive/bias。
- 支持 GDML world name 验证。
- 支持 `checkOverlaps` 后处理。
- 添加小型 GDML fixture 和 batch test。

### 2.9 Documentation correction

需要修正 `macros/run_gdml.mac` 的风险示例：它注释说不要 `/run/initialize`，但实际执行了 `/run/initialize`。

Suggested wording:

```text
GDML import is experimental and not runnable. This macro intentionally stops
before /run/initialize until G4GDMLParser is wired into DetectorConstruction.
```

## 3. STL 输入实现状态

### 3.1 Current implementation status

当前完全没有可用 STL import。没有 parser、template、mesh config、`G4TessellatedSolid` 构建逻辑或 macro 命令。

### 3.2 Evidence from project source

- Search evidence: `rg` 未发现 `G4TessellatedSolid`、STL parser、STL template、mesh geometry config 的实现。
- File: `docs/未实现功能.md`
- Evidence: 文档把 STL 输入列为规划功能，说明当前没有完整 parser、template、VolumeBuilder 接入或 Geant4 solid 构建流程。

### 3.3 Call-chain analysis

```text
config parser: no
template: no
manager storage: no
VolumeBuilder backend: no
Geant4 backend call: no
调用链中断位置：入口不存在
```

### 3.4 Runtime behavior

当前没有任何安全可用的 STL 配置或 macro 命令。用户写 `shape = stl` 或类似配置会被 `GeometryUtils::ParseShape()` 判为 unknown 或后续失败。

### 3.5 Geant4 feasibility

Geant4 可用 `G4TessellatedSolid` 表示三角/四边形 facet 组成的 solid，并通过 `AddFacet()` 和 `SetSolidClosed(true)` 建立闭合网格。官方/社区实践通常把 CAD/mesh 格式转成 tessellated solids，或通过 CADMesh、ASSIMP、FreeCAD/pyg4ometry、STEP-to-GDML 等外部路线导入。

Source:

- Geant4 class: `G4TessellatedSolid`
- Geant4 class: `G4TriangularFacet`
- Geant4 Application Developers Guide: Geometry / Tessellated Solids
- Geant4 Forum: [Importing CAD geometries into Geant4: practical notes and common pitfalls](https://geant4-forum.web.cern.ch/t/importing-cad-geometries-into-geant4-practical-notes-and-common-pitfalls/14912)
- Geant4 Forum: [Import .stp files in geant4](https://geant4-forum.web.cern.ch/t/import-stp-files-in-geant4/10480)

可行性判断：

- STL 只含表面三角网格，通常不含材料、层级结构、region、sensitive 信息。
- STL mesh 必须闭合、无自交、法线一致、无非流形边，否则容易出现导航错误或 stuck tracks。
- 大型 tessellated solids 会影响 tracking/navigation 性能。
- 若要导入复杂 CAD，GDML 或 STEP-to-GDML 通常比直接内建 STL 更适合作为第一路线。

### 3.6 Is it necessary for this project?

Optional。

对芯片/层状器件和屏蔽测试，CSG/GDML 更重要。STL 适合复杂机械壳体，但维护和验证成本高。

### 3.7 Limitations and risks

- STL 无材料和层级信息。
- 网格质量直接影响几何导航稳定性。
- 需要外部解析库或自研 ASCII/binary STL parser。
- 大 mesh 可视化和 tracking 性能风险高。

### 3.8 Recommended implementation plan

若后续实现，建议最小方案：

- 新增 `mesh` / `stl` geometry config，只支持单个 closed STL solid。
- 引入明确的 `material`、`parent`、`position`、`rotation`、`scale`、`sensitive`、`region` 字段。
- 先支持 binary STL + ASCII STL 读取到三角面。
- 构建 `G4TessellatedSolid`，逐个 `G4TriangularFacet`，最后 `SetSolidClosed(true)`。
- 在导入前做 mesh sanity check：facet count、bounding box、重复点、退化三角形、边界边计数。
- 运行 overlap check 和小步长 tracking smoke test。

更推荐路线：

- 优先实现 GDML 真导入。
- 对 CAD/STL 推荐外部转换到 GDML，或单独可选依赖 CADMesh/ASSIMP。

### 3.9 Documentation correction

当前 `docs/未实现功能.md` 已经正确标注。建议所有 README/手册只写：

```text
STL import is planned only. No stable user-facing parser or G4TessellatedSolid
backend is available in the current executable.
```

## 4. LETScorer / DoseScorer / FluenceScorer

### 4.1 Current implementation status

三者类存在并可被 `ScoringManager` 注册，但 `DoseScorer` 和 `FluenceScorer` 是 no-op；`LETScorer` 只在 `HitRecord::LETcalc > 0` 时填 histogram，本项目当前没有真实 LET 计算路径。

### 4.2 Evidence from project source

- File: `include/Scoring/LETScorer.hh`, `src/Scoring/LETScorer.cc`
- Class: `LETScorer : public ScorerBase`
- Function: `ScoreHit`
- Evidence: 只检查 `histogramEnabled_ && hit.LETcalc > 0.0`，填 `letHist_`；不从 `G4Step` 计算 LET。

- File: `src/Scoring/DoseScorer.cc`
- Class: `DoseScorer : public ScorerBase`
- Function: `ScoreHit`, `Write`, `Reset`
- Evidence: `ScoreHit` 注释说明需要 volume mass 或 material/geometry 信息，目前 intentionally no-op；`Write` 空。

- File: `src/Scoring/FluenceScorer.cc`
- Class: `FluenceScorer : public ScorerBase`
- Function: `ScoreHit`, `Write`, `Reset`
- Evidence: `ScoreHit` 注释说明需要 surface/area 或 track-length scoring definition，目前 no-op；`Write` 空。

- File: `src/Scoring/ScoringManager.cc`
- Function: `EnsureDefaultScorers`, `LoadFromConfig`, `ScoreHit`, `WriteAll`
- Evidence: 可根据 `let`、`dose`、`fluence` 开关注册 scorer；但真实计算依赖各 scorer。

- File: `src/Scoring/ScoringMessenger.cc`
- Evidence: `/AIHL/scoring/let`、`dose`、`fluence` guidance 明确称为 stub。

### 4.3 Call-chain analysis

```text
config parser: yes, [scoring] let/dose/fluence
messenger command: yes, /AIHL/scoring/let|dose|fluence
ScoringManager registration: yes
SD/Stepping path: partial, HitRecord reaches ScoringManager::ScoreHit
physical calculation: no for dose/fluence, no native LET calculation
OutputManager write: LET histogram only if manually enabled and LETcalc nonzero; dose/fluence no output
线程安全：no, shared ScoringManager/OutputManager in MT
调用链中断位置：Scorer implementation
```

### 4.4 Runtime behavior

- `DoseScorer` / `FluenceScorer`：命令和 config 可以开启，但不会产生物理输出。
- `LETScorer`：可注册，但默认没有公开 macro/config 设置 LET histogram，也没有真实填充 `LETcalc` 的计算逻辑；通常输出为空。
- `EdepScorer` 和 hit/event edep 输出是当前更可靠的 scoring 路径。

### 4.5 Geant4 feasibility

Geant4 官方 scoring 框架提供 `G4MultiFunctionalDetector` 和 `G4VPrimitiveScorer`，包括 `G4PSEnergyDeposit`、`G4PSDoseDeposit`、track length/current/flux scorers。官方文档说明 `G4PSDoseDeposit` 用每 step energy deposit 的和除以 cell mass，cell mass 来自 `G4VSolid` 和 `G4LogicalVolume`；`G4PSEnergyDeposit` 会按权重乘能量沉积。Flux/current 有 surface 和 volume 定义差异。

Source:

- Geant4 Application Developers Guide: [Hits / Concrete classes of `G4VPrimitiveScorer`](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/hit.html)
- Geant4 class: `G4VPrimitiveScorer`
- Geant4 class: `G4MultiFunctionalDetector`
- Geant4 class: `G4PSEnergyDeposit`, `G4PSDoseDeposit`, `G4PSCellFlux`, `G4PSFlatSurfaceCurrent`

可行性判断：

- Dose：实现相对直接，建议优先复用或对齐 `G4PSDoseDeposit` 定义。
- Fluence：必须先选择 track-length estimator、surface current、surface flux 或 passage flux，定义不同，结果含义不同。
- LET：物理定义风险最高。常见定义包括 track-averaged LET 和 dose-averaged LET；还要区分 restricted/unrestricted LET、按粒子类型、材料、step 长度、能量沉积口径。不能只用 `edep / stepLength` 就宣称完整 LET。

### 4.6 Is it necessary for this project?

Recommended for Dose/Fluence, Useful but not urgent for LET。

剂量和通量是通用模拟常用输出，值得补齐。LET 需要先写物理定义和 validation 方案。

### 4.7 Limitations and risks

- LET 定义不唯一，物理 validation 必须先行。
- Dose 需要 volume mass；复杂 geometry、replica、parameterisation 和 copy number 下要谨慎。
- Fluence 需要面积或 track-length 定义。
- 当前 scoring/output 在 MT 下不是线程安全设计。

### 4.8 Recommended implementation plan

最小实现：

- Dose：新增 volume mass 查询接口，或引入 `G4MultiFunctionalDetector + G4PSDoseDeposit` 路线；输出 per-volume dose 和 event/run dose。
- Fluence：先实现 `track-length fluence = sum(trackLength * weight) / volume`，命名明确为 `track_length_fluence`；后续再加 surface current/flux。
- LET：新增文档定义，至少区分 `LET_track = sum(LET_i * dl_i) / sum(dl_i)` 与 `LET_dose = sum(LET_i * edep_i) / sum(edep_i)`；先在 `SensitiveDetector::ProcessHits` 或 scorer 中填充中间量，不直接宣称医学 LET。
- 为三者增加 regression test：单体积、已知能量沉积、固定粒子。

### 4.9 Documentation correction

建议所有用户手册保留 stub 标注：

```text
LETScorer, DoseScorer and FluenceScorer are registerable placeholders.
Dose and fluence currently do not compute physical quantities. LETScorer only
consumes HitRecord::LETcalc when it is already filled by another component.
```

## 5. ParticleAggregator / 粒子分组高级分析

### 5.1 Current implementation status

`ParticleAggregator` 是空类，未被 Action、Scoring 或 Output 调用。

### 5.2 Evidence from project source

- File: `include/Scoring/ParticleAggregator.hh`
- Class: `ParticleAggregator`
- Evidence: 只有构造/析构声明，无字段和方法。

- File: `src/Scoring/ParticleAggregator.cc`
- Evidence: 构造/析构空实现。

- Search evidence: 未发现 `ParticleAggregator` 被 `ActionInitialization`、`EventAction`、`SteppingAction`、`SensitiveDetector`、`ScoringManager` 或 `OutputManager` 调用。

### 5.3 Call-chain analysis

```text
config parser: no
messenger command: no
manager storage: no
Action/Scoring integration: no
OutputManager integration: no
调用链中断位置：类为空且无引用
```

### 5.4 Runtime behavior

用户无法启用该功能；不会输出按粒子名、PDG、charge、category 分组统计。

### 5.5 Geant4 feasibility

Geant4 的 `G4Track` / `G4ParticleDefinition` 提供粒子名、PDG encoding、charge、particle type/subtype 等信息；`G4Step` 在 sensitive detector 或 stepping action 中可访问 track，因此按粒子类型聚合是工程上直接可行的。

Source:

- Geant4 Application Developers Guide: Tracking / Access to Track and Step Information
- Geant4 class: `G4Track`
- Geant4 class: `G4ParticleDefinition`
- Geant4 class: `G4Step`

### 5.6 Is it necessary for this project?

Useful but not urgent。

对分析很有用，但不应优先于输出线程安全、Dose/Fluence、GDML 等基础能力。

### 5.7 Limitations and risks

- 与 MT merge 强相关。
- 粒子分类口径需要定义：粒子名、PDG、charge、lepton/hadron/ion/gamma/neutron 等。
- 若在 stepping 层逐 step 聚合，会增加事件处理开销。

### 5.8 Recommended implementation plan

推荐位置：

- 最小：作为 `ScoringManager` 的可选 per-event/per-run 聚合器，输入 `HitRecord`。
- 输出：由 `OutputManager` 写 `particle_summary_tN.csv`，后处理 merge。
- 后续：支持 `G4Track` 层 ancestor grouping，需要 `TrackInformation` 完整接入。

建议字段：

```text
particleName, pdg, charge, category, nHits, rawEdep, weightedEdep, trackLength, nTracks(optional)
```

### 5.9 Documentation correction

建议文档只写：

```text
ParticleAggregator is a placeholder class and is not connected to the runtime
scoring or output chain.
```

## 6. 多线程输出与自动 merge

### 6.1 Current implementation status

当前是部分实现且有 MT 风险。有 `_t0` 文件名机制、`merge_outputs.py` 和 `mergeHistograms`，但没有 thread-local manager、mutex、`G4AutoLock` 或自动 merge。

### 6.2 Evidence from project source

- File: `src/Output/OutputManager.cc`
- Class: `OutputManager`
- Evidence: `threadId_`、`EnableThreadSuffix`、`MakeThreadFilename` 支持 `_tN` 后缀；无 mutex / `G4AutoLock` / thread-local storage。

- File: `src/Core/SimulationManager.cc`
- Function: `ConfigureOutputManager`
- Evidence: 固定 `outputManager_->SetThreadId(0)` 和 `EnableThreadSuffix(true)`。

- File: `src/Actions/ActionInitialization.cc`
- Function: `BuildForMaster`, `Build`
- Evidence: master 和 worker action 都用同一个传入的 `ScoringManager*` / `OutputManager*`。

- File: `src/Scoring/ScoringManager.cc`
- Function: `ScoreHit`, `EndEvent`
- Evidence: 更新 `currentEventRawEdep_`、`currentEventWeightedEdep_` 并写 output，无锁。

- File: `scripts/merge_outputs.py`
- Evidence: 后处理 merge 脚本存在。

- File: `tools/mergeHistograms.cc`, `CMakeLists.txt`
- Evidence: `add_executable(mergeHistograms tools/mergeHistograms.cc)`，独立构建。

- File: `docs/MODULE_OVERVIEW.md`
- Evidence: 明确写 `OutputManager` is not thread-safe。

### 6.3 Call-chain analysis

```text
per-thread file naming: partial, suffix mechanism exists but threadId fixed to 0
thread-local OutputManager: no
mutex/G4AutoLock: no
auto merge at EndRun: no
external merge tools: yes
race-free MT output: no
调用链中断位置：ActionInitialization / OutputManager ownership model
原因：同一 OutputManager/ScoringManager 指针被多线程 action 共享
```

### 6.4 Runtime behavior

单线程通常可用。多线程下，多个 worker 可能写同一个 `hits_t0.csv`、`event_edep_t0.csv`、histogram 文件，并竞争修改 `ScoringManager` 当前事件累计字段，存在数据竞争和输出损坏风险。没有自动 merge。

### 6.5 Geant4 feasibility

Geant4 官方分析管理器支持 MT：worker 上的 histogram 在 `Write()` 时自动合并到 master file，并用 `G4AutoLock` 保护；ntuple 默认每线程文件，ROOT ntuple 可 `SetNtupleMerging(true)` 合并，CSV/HDF5/XML 有限制。Geant4 MT 是 master-worker 模型，事件在 worker 线程处理。

Source:

- Geant4 Application Developers Guide: [Analysis Manager Classes / Parallel Processing](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Analysis/managers.html)
- Geant4 class: `G4AnalysisManager`
- Geant4 class: `G4AutoLock`
- Geant4 Toolkit Developer Guide: multithreading master-worker model

方案比较：

| 方案 | 优点 | 缺点 | 推荐度 |
|---|---|---|---|
| A：per-thread files + explicit merge | 保留 CSV 简单性；容易排查；适合当前工具 | 需要正确 thread id；用户要 merge 或 EndRun 自动 merge；文件多 | 短期推荐 |
| B：使用 `G4AnalysisManager` 合并能力 | Geant4 官方 MT 支持；hist 自动合并；ROOT ntuple 可合并 | 需要重构输出；CSV ntuple 不提供合并；格式约束 | 中长期推荐用于 histogram/ROOT |
| C：集中式锁保护输出 | 改动小；保证单文件不乱写 | 高并发性能差；仍要保护 scoring state；容易引入锁粒度问题 | 只适合临时修补 |

### 6.6 Is it necessary for this project?

Highly recommended。

这是数据可信度问题，应优先于高级功能。

### 6.7 Limitations and risks

- 当前 `ScoringManager` 状态也非线程安全，只锁 `OutputManager` 不够。
- Geant4 `G4AnalysisManager` 对 CSV ntuple merge 有限制。
- 自动 merge 若在 master EndRun 做，需要知道 worker 文件列表和生命周期。

### 6.8 Recommended implementation plan

P1 最小方案 A：

- 在 `ActionInitialization::Build()` 为每个 worker 创建或获取 thread-local `OutputManager`/`ScoringManager`。
- 用 `G4Threading::G4GetThreadId()` 设置 thread id。
- 每个 worker 写 `*_tN.csv`。
- `RunAction::EndOfRunAction` 在 master 上仅写 summary，不写 worker 文件。
- 提供 `--auto-merge` 或 `[output] auto_merge = true`，run 结束后调用内部 merge 函数或提示脚本命令。

P2 方案 B：

- histogram 改为 `G4AnalysisManager`。
- 对 ROOT 输出启用 ntuple merge。
- CSV hit 明细仍保留 per-thread files。

### 6.9 Documentation correction

建议补充：

```text
Multi-thread output is not currently race-free. Use single-thread runs for
production-grade CSV output until per-thread OutputManager/ScoringManager
instances or explicit locking are implemented.
```

## 7. Geometry 中 `trap` / `trapezoid` 实现状态

### 7.1 Current implementation status

更新：Round 2 后已实现。`trd/trapezoid` 由 `VolumeBuilder::CreateTrdSolid()` 创建 `G4Trd`；`trap` 由 `VolumeBuilder::CreateTrapSolid()` 创建完整 `G4Trap`。

### 7.2 Evidence from project source

- File: `src/Geometry/GeometryUtils.cc`
- Function: `ParseShape`
- Evidence at audit time: `trap` / `trapezoid` 返回 `VolumeShape::Trapezoid`。Round 2 后已改为 `trd/trapezoid -> VolumeShape::Trd`，`trap -> VolumeShape::Trap`。

- File: `src/Geometry/VolumeBuilder.cc`
- Function: `CreateSolid`
- Evidence at audit time: switch 只支持 `Box`、`Tubs`、`Sphere`、`Orb`、`Cone`；默认抛出 unsupported shape。Round 2 后已增加 `Trd` / `Trap` 分支。

- File: `docs/中文几何配置说明.md`, `docs/未实现功能.md`
- Evidence at audit time: 文档已说明 `trap` / `trapezoid` 只解析不构建。Round 2 后当前文档已改为可用但需满足 Geant4 参数约束。

### 7.3 Call-chain analysis

```text
config parser: yes, trd/trapezoid -> VolumeShape::Trd, trap -> VolumeShape::Trap
manager storage: yes
VolumeBuilder backend: yes, CreateTrdSolid/CreateTrapSolid
Geant4 backend call: yes, G4Trd/G4Trap
调用链中断位置：none after Round 2
```

### 7.4 Runtime behavior

Round 2 后，`shape = trd/trapezoid` 和 `shape = trap` 可运行。`trap` 参数若不满足 Geant4 `G4Trap` 几何约束，仍会在 solid 构建阶段失败。

### 7.5 Geant4 feasibility

Geant4 提供 `G4Trap` 表示通用 trapezoid，也提供 `G4Trd` 表示较简单的梯形体。官方 Book For Application Developers 的 Solids 章节说明 `G4Trd` 参数是 `dx1, dx2, dy1, dy2, dz`，`G4Trap` 支持 `dz, theta, phi, dy1, dx1, dx2, alpha1, dy2, dx3, dx4, alpha2` 等完整参数。

Source:

- Geant4 Application Developers Guide: Geometry / Solids
- Geant4 class: `G4Trap`
- Geant4 class: `G4Trd`

### 7.6 Is it necessary for this project?

Recommended。

实现成本低，对屏蔽和探测器几何表达有用。

### 7.7 Limitations and risks

- `trap` 参数复杂，用户易错。
- 需要明确 `dx*`、`dy*`、`dz` 是 half-length。
- 简化 `trapezoid` 和完整 `trap` 应分开，避免参数混乱。

### 7.8 Recommended implementation plan

推荐支持两种格式：

简化 alias：

```ini
shape = trd
dx1 = 5 mm
dx2 = 10 mm
dy1 = 4 mm
dy2 = 8 mm
dz = 2 mm
```

完整 `G4Trap`：

```ini
shape = trap
dz = ...
theta = ...
phi = ...
dy1 = ...
dx1 = ...
dx2 = ...
alpha1 = ...
dy2 = ...
dx3 = ...
dx4 = ...
alpha2 = ...
```

实现位置：

- `GeometryTypes.hh` 增加 `Trd` 或复用 `Trapezoid` 并通过 `shapeName` 区分。
- `GeometryConfig::ParseVolumeSection` 读取 named parameters 到 `userProperties` 或新增专门字段。
- `VolumeBuilder::CreateSolid` 增加 `CreateTrdSolid` / `CreateTrapSolid`。
- 增加 unit tests 和一个 geometry smoke macro。

### 7.9 Documentation correction

Round 2 后文档应保持：

```text
trd/trapezoid use G4Trd, and trap uses full G4Trap. All length fields are half-lengths. Trap parameters must satisfy Geant4 solid constraints.
```

## 8. Qt UI 界面实现状态

### 8.1 Current implementation status

当前没有项目级 Qt UI。`CMakeLists.txt` 要求 Geant4 `ui_all vis_all`，`main.cc --ui` 创建 `G4VisExecutive` 和 `G4UIExecutive`，但没有 Qt 源码、Qt CMake target 或自定义 Qt 控制界面。

### 8.2 Evidence from project source

- File: `CMakeLists.txt`
- Evidence: `find_package(Geant4 REQUIRED ui_all vis_all)`；无 `find_package(Qt...)`，无 Qt libraries 链接，只有 `G4UniversalSim` 和 `mergeHistograms` targets。

- File: `main.cc`
- Function: `main`
- Evidence: `--ui` 时创建 `G4VisExecutive`，然后 `G4UIExecutive ui(argc, argv); ui.SessionStart();`。

- Search evidence: 未发现 Qt widget/window/controller 源码。

### 8.3 Call-chain analysis

```text
Qt source files: no
CMake Qt target: no
find_package(Qt): no
SimulationManager GUI integration: no
Geant4 UI/Vis session: yes, via --ui and Geant4 build
调用链中断位置：项目级 UI 不存在
```

### 8.4 Runtime behavior

如果本地 Geant4 启用了 Qt UI/Vis，`--ui` 可以进入 Geant4 的 UI/visualization session；这不是 G4UniversalSim 自己实现的 Qt UI。不能通过项目级 Qt 界面加载 config、控制 run、reinitialize geometry 或管理输出。

### 8.5 Geant4 feasibility

Geant4 官方支持多种 UI/visualization driver，包括 Qt/OpenGL，应用通常通过 `G4VisExecutive` 和 `G4UIExecutive` 接入。自定义 Qt GUI 可行，但会显著增加 CMake、运行时依赖、事件循环和状态管理复杂度。

Source:

- Geant4 Application Developers Guide: Visualization / UI sessions
- Geant4 class: `G4UIExecutive`
- Geant4 class: `G4VisExecutive`

### 8.6 Is it necessary for this project?

Not recommended now。

当前项目更需要 CLI/macro、输出、几何 import、scoring 和 MT 稳定性。Qt UI 应晚于这些基础能力。

### 8.7 Limitations and risks

- Qt/Geant4/编译器 ABI 组合在 Windows 上容易增加构建复杂度。
- Geant4 UI session 已有事件循环，自定义 Qt 控制面板要处理 run state。
- 运行中修改 geometry/physics 需要严格遵守 Geant4 state machine。

### 8.8 Recommended implementation plan

若未来实现：

- 作为独立 target：`G4UniversalSimQt`。
- 复用 `SimulationManager`，不要把 Qt 依赖放进默认 CLI executable。
- 第一版只做 config/macro 选择、运行日志显示、启动/停止 run；不要一开始做在线编辑 geometry。

### 8.9 Documentation correction

建议区分：

```text
`--ui` starts a Geant4 UI/visualization session. G4UniversalSim does not yet
provide a custom Qt application GUI.
```

## 9. OutputMessenger 与 `/AIHL/output/...` 命令

### 9.1 Current implementation status

更新：Round 1 后 `OutputMessenger` 已继承 `G4UImessenger` 并注册 `/AIHL/output/...` 最小命令集合，且由 `SimulationManager` 持有。

### 9.2 Evidence from project source

- File: `include/Output/OutputMessenger.hh`
- Class: `OutputMessenger`
- Evidence at audit time: 只有构造/析构，不继承 `G4UImessenger`。Round 1 后已实现为 `G4UImessenger`。

- File: `src/Output/OutputMessenger.cc`
- Evidence at audit time: 构造/析构空实现。Round 1 后已定义 `setDir`、`setThreadSuffix`、`print`、`flush`、`close`。

- File: `include/Core/SimulationManager.hh`, `src/Core/SimulationManager.cc`
- Evidence at audit time: 没有 `OutputMessenger` 成员；`BuildManagers()` 只创建 Material/Geometry/Physics/Source/Biasing/Scoring messengers。Round 1 后 `SimulationManager` 已持有并创建 `OutputMessenger`。

- File: `docs/COMMAND_REFERENCE.md`
- Evidence at audit time: 已说明 `/AIHL/output/...` 当前不存在。Round 1 后命令文档已列出最小真实命令。

### 9.3 Call-chain analysis

```text
messenger class: yes, G4UImessenger after Round 1
command definition: yes, minimal output commands
SimulationManager wiring: yes
OutputManager backend: partial, has setters for outputDir/thread suffix
macro runtime: yes
调用链中断位置：none for minimal commands after Round 1
```

### 9.4 Runtime behavior

Round 1 后，macro 中可使用 `/AIHL/output/setDir`、`setThreadSuffix`、`print`、`flush`、`close`。hits/scoring 开关仍属于 `/AIHL/scoring/...`。

### 9.5 Geant4 feasibility

Geant4 UI command 通过 `G4UImessenger` 和 `G4UIcmd*` 实现，项目已有多个 Messenger 可复用模式。`OutputManager` 适合暴露运行前配置，但 run 中途修改打开的文件名、格式和开关风险高。

Source:

- Geant4 Application Developers Guide: Control / User Interface - Defining New Commands
- Geant4 class: `G4UImessenger`, `G4UIcmdWithAString`, `G4UIcmdWithABool`

### 9.6 Is it necessary for this project?

Recommended。

输出是用户最常配置的模块之一，最小 `OutputMessenger` 很有价值。

### 9.7 Limitations and risks

- 输出文件一旦打开，不应中途改目录/文件名。
- MT 输出策略会影响命令语义。
- hits/event edep enable 目前属于 `ScoringManager`，不要在 OutputMessenger 重复开关造成冲突。

### 9.8 Recommended implementation plan

最小命令集合：

```text
/AIHL/output/setDir <dir>
/AIHL/output/setThreadSuffix <bool>
/AIHL/output/print
/AIHL/output/flush
/AIHL/output/close
```

谨慎命令：

```text
/AIHL/output/setFilePrefix <prefix>   # 仅 run 前
/AIHL/output/autoMerge <bool>         # 需先实现 MT 策略
```

不建议重复：

```text
/AIHL/output/enableHits
/AIHL/output/enableScoring
```

这些开关当前由 `/AIHL/scoring/...` 管理，除非重构责任边界。

### 9.9 Documentation correction

Round 1 后文档应保持：

```text
OutputMessenger is registered with setDir, setThreadSuffix, print, flush, and close. Hits/scoring switches remain under /AIHL/scoring.
```

## 10. 高级 biasing：importance / weight-window / splitting / Russian roulette

### 10.1 Current implementation status

当前只实现 cross-section process-level biasing。importance、weight-window、splitting、Russian roulette 没有可运行 parser、messenger 命令或 Geant4 backend 接入。

### 10.2 Evidence from project source

- File: `include/Biasing/BiasingImportance.hh`, `src/Biasing/BiasingImportance.cc`
- Class: `BiasingImportance`
- Evidence: 空构造/析构，stub。

- File: `include/Biasing/BiasingConfig.hh`
- Evidence: `BiasingType` enum 包含 `Importance`，但实际 config 结构只有 `XSBiasRule` 和 `XSProcessBiasRule`。

- File: `src/Biasing/BiasingManager.cc`
- Function: `LoadFromConfig`, `AttachOperators`
- Evidence: parser 处理 `[biasing.xs.<particle>.<process>]` 和 legacy `[biasing.xs]`；`AttachOperators()` 只创建 `BiasingMultiParticleXS` 并 attach 到 logical volume。

- File: `src/Biasing/BiasingMultiParticleXS.cc`, `src/Biasing/BiasingXS.cc`
- Evidence: 后端是 `G4VBiasingOperator` / XS occurrence biasing 路线，不是 importance/weight-window sampler。

- File: `src/Biasing/BiasingMessenger.cc`
- Evidence: 命令全在 `/AIHL/biasing/xs/...`，没有 importance/weight-window/splitting/RR 命令。

### 10.3 Call-chain analysis

```text
XS biasing parser: yes
XS biasing messenger: yes
XS biasing manager/backend: partial to runnable, uses BiasingMultiParticleXS/BiasingXS
importance parser: no
weight-window parser: no
splitting/Russian roulette parser: no
Geant4 importance/WW sampler backend: no
调用链中断位置：高级 biasing 没有 parser/messenger/backend
```

### 10.4 Runtime behavior

用户只能使用当前 XS process-level biasing。配置 importance、weight-window、splitting 或 Russian roulette 不会被识别或不会产生效果，取决于写在哪个 section；没有宏命令可用。

### 10.5 Geant4 feasibility

Geant4 官方支持多种 biasing 技术，包括 geometrical splitting/Russian roulette、weight roulette、importance sampling、weight window、generic biasing。官方文档说明 importance/weight-window 常通过 sampler、cell importance、weight window store 等机制实现，并与 mass geometry 或 parallel geometry cell 绑定。官方 examples 位于 `examples/extended/biasing`。

Source:

- Geant4 Application Developers Guide: [Event Biasing Techniques](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Fundamentals/biasing.html)
- Geant4 official examples: `examples/extended/biasing/B01`, `B02`, `GB01`
- Geant4 classes: `G4GeometrySampler`, `G4IStore`, `G4VWeightWindowStore`, `G4WeightWindowAlgorithm`, `G4VBiasingOperator`

分别评估：

| Method | Current status | Geant4 support mechanism | Difficulty | Physics risk | Recommendation |
|---|---|---|---|---|---|
| importance biasing | Not implemented | `G4GeometrySampler`、importance store、cell importance | High | High，权重守恒和边界处理需验证 | P3，先不要做 |
| weight-window | Not implemented | `G4VWeightWindowStore`、weight window algorithm | High | High，需要能量-空间权重窗定义 | P3 |
| splitting | Not implemented | importance sampling / generic biasing 可实现 | High | High，二次粒子权重和统计误差 | P3 |
| Russian roulette | Not implemented | importance/weight roulette/cutoff | High | High，权重下限和偏差验证 | P3 |

这些功能与当前 XS biasing 架构不是同一层。XS biasing 针对 physics process occurrence；importance/WW/RR 是几何 cell 和 track weight 抽样控制。

### 10.6 Is it necessary for this project?

Useful but not urgent。

高级 variance reduction 对屏蔽问题有价值，但当前应先稳定 XS biasing、MT 输出和基础 scoring。

### 10.7 Limitations and risks

- 权重管理错误会直接造成物理偏差。
- 需要严格 validation：analog run vs biased run、权重守恒、统计误差。
- 常依赖 parallel geometry 或 cell importance 结构，当前 geometry registry 不足以表达。
- 与带电粒子 multiple scattering、边界行为的组合复杂。

### 10.8 Recommended implementation plan

路线：

1. P0/P1：把文档中高级 biasing 全部标为 future work。
2. P1：完善 XS biasing validation。
3. P2：设计 `BiasingCell` / `BiasingStore` 数据模型，明确 mass geometry 还是 parallel geometry。
4. P3：先实现一个官方 example 对齐的 importance sampling demo，只支持 neutron/gamma shielding。
5. P3：再增加 weight-window 和 splitting/RR。

### 10.9 Documentation correction

建议：

```text
Advanced biasing methods such as importance sampling, weight-window,
splitting and Russian roulette are future work only. The current runnable
biasing backend is process-level cross-section biasing.
```

## 11. `layered_device` 对 copy number / metadata 的支持

### 11.1 Current implementation status

更新：Round 2 后，`layered_device` 已读取 `copyNo`，并将 `metadata.*` 与未知 key 透传到 `VolumeNode::userProperties`；`copyNo` 会被 `VolumeBuilder` 用作 `G4PVPlacement` copy number。metadata 仍仅为内部标签，不自动输出到 CSV。

### 11.2 Evidence from project source

- File: `src/Templates/LayeredDeviceTemplate.cc`
- Class: `LayeredDeviceTemplate`
- Function: `BuildNodes`
- Evidence at audit time: 只读取 `thickness`、`xy`、`material`、`position`、`rotation`、`sensitive`、`bias`、`region`、cuts、visual；没有读取 `copyNo` 或 metadata，也没有保存未知 key。Round 2 后已新增 `ApplyUserProperties()`。

- File: `src/Geometry/GeometryConfig.cc`
- Class: `GeometryConfig`
- Function: `ParseVolumeSection`
- Evidence: unknown keys 被写入 `node.userProperties[item.first] = item.second`。

- File: `src/Geometry/VolumeBuilder.cc`
- Function: `ReadCopyNumber`, `BuildVolume`
- Evidence: 从 `node.GetProperty("copyNo")` 读取 copy number，并传给 `G4PVPlacement`。

- File: `test/geometry/hierarchical_test.ini`
- Evidence: 使用 `copyNo` 和 `metadata.role`。Round 2 后也新增 `config/geometry/layered_metadata_test.ini` 覆盖 layered_device。

- File: `test/geometry/layered_device_test.ini`
- Evidence at audit time: 未使用 `copyNo` / metadata。Round 2 后新增 layered metadata 测试配置。

### 11.3 Call-chain analysis

```text
layered_device parser copyNo: yes after Round 2
layered_device parser metadata: yes, stored as userProperties after Round 2
VolumeNode storage from layered_device: yes
hierarchical parser copyNo/metadata: yes, via userProperties
VolumeBuilder copyNo backend: yes, reads userProperties["copyNo"]
metadata backend: storage only, no runtime behavior
调用链中断位置：none for copyNo/storage after Round 2; CSV output still not connected to metadata
```

### 11.4 Runtime behavior

- 在 layered_device 的 `[layer.*]` 写 `copyNo` 会影响 placement copy number；写 `metadata.*` 会保存为内部标签。
- 在 hierarchical 的 `[volume.*]` 写 `copyNo` 会影响 placement copy number。
- hierarchical 的 `metadata.*` 会保存在 `VolumeNode::userProperties`，但当前不会进入 output tagging、SD、scoring selection。

### 11.5 Geant4 feasibility

Geant4 touchable/physical volume 提供 `GetCopyNumber()` / `GetReplicaNumber()`，用于唯一识别 detector element。copy number 是物理 placement 层属性，不是 logical volume 属性。

Source:

- Geant4 Application Developers Guide: [Touchables: Uniquely Identifying a Volume](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/Geometry/geomTouch.html)
- Geant4 class: `G4PVPlacement`
- Geant4 class: `G4VTouchable`

### 11.6 Is it necessary for this project?

Recommended。

layered device 经常需要按层/像素/器件编号识别 hits；copy number 和 metadata 对输出分析很有用。

### 11.7 Limitations and risks

- copy number 只在 physical placement 层生效；同一 logical volume 复用时要注意。
- metadata 是项目内部语义，不会自动进入 Geant4。
- 若 metadata 参与 output tagging，需要扩展 `GeometryRegistry` 或 hit conversion。

### 11.8 Recommended implementation plan

最小实现：

- `LayeredDeviceTemplate::BuildNodes` 读取 `copyNo` 并写 `layer.userProperties["copyNo"]`。
- 将所有未知 `layer.*` key 存入 `userProperties`，但排除已知 key。
- 文档声明 `metadata.*` 仅存储，不影响几何，除非 output/scoring 明确消费。

后续增强：

- `GeometryRegistry` 保存 metadata map。
- `SensitiveDetector` / `ParticleHit` / `HitRecord` 增加 copy number 和可选 metadata tag。
- 输出 CSV 增加 `copyNo` 和 `metadata.role`。

### 11.9 Documentation correction

Round 2 后主文档应保持：

```text
layered_device propagates copyNo, metadata.*, and unknown layer keys into
VolumeNode::userProperties. copyNo is used for G4PVPlacement; metadata is
not automatically written to HitRecord or CSV output.
```

## 12. AppMessenger 和 DetectorMessenger 默认注册情况

### 12.1 Current implementation status

更新：Round 1 后，`AppMessenger` 和 `DetectorMessenger` 已默认注册。`/AIHL/app/...` 由 `SimulationManager` 持有的 messenger 提供；`/AIHL/detector/...` 由 `DetectorConstruction` 持有的 messenger 提供。

### 12.2 Evidence from project source

- File: `include/Core/AppMessenger.hh`, `src/Core/AppMessenger.cc`
- Class: `AppMessenger : public G4UImessenger`
- Evidence: 定义 `/AIHL/app/setMainConfig`、`setOutputDir`、`setNumThreads`、`setSeed`、`setVerbose`、`setCheckOverlaps`、`printSummary`。

- File: `include/Detector/DetectorMessenger.hh`, `src/Detector/DetectorMessenger.cc`
- Class: `DetectorMessenger : public G4UImessenger`
- Evidence: 定义 `/AIHL/detector/enableSD`、`setSDName`、`printRegistry`、`printSensitiveVolumes`、`printBiasVolumes`、`setVerbose`、`printWorld`。

- File: `include/Core/SimulationManager.hh`
- Evidence at audit time: 成员中只有 `MaterialMessenger`、`GeometryMessenger`、`PhysicsMessenger`、`SourceMessenger`、`BiasingMessenger`、`ScoringMessenger`，没有 `AppMessenger` / `DetectorMessenger`。Round 1 后已新增相应持有关系。

- File: `src/Core/SimulationManager.cc`
- Function: `BuildManagers`
- Evidence at audit time: 只实例化 Material/Geometry/Physics/Source/Biasing/Scoring messengers。Round 1 后 `BuildManagers()` 已创建 `AppMessenger`，`DetectorConstruction` 创建 `DetectorMessenger`。

- File: `main.cc`
- Evidence: `main.cc` 仍不直接实例化这些 messenger；Round 1 后实例化位置位于 `SimulationManager` / `DetectorConstruction`。

### 12.3 Call-chain analysis

```text
messenger class implementation: yes
G4UI command definitions: yes
SimulationManager wiring: yes for AppMessenger after Round 1
DetectorConstruction wiring: yes for DetectorMessenger after Round 1
main.cc wiring: not direct, by design
lifetime across UI session: yes
runtime command availability: yes
调用链中断位置：none after Round 1
```

### 12.4 Runtime behavior

Round 1 后，默认 executable 启动后 `/AIHL/app/...` 和 `/AIHL/detector/...` 可用；若 unknown command，通常是未重新构建或运行了旧 executable。

### 12.5 Geant4 feasibility

Geant4 messenger 命令只要对象生命周期覆盖 UI session 即可使用。本项目已有多个 messenger 的注册模式，接入技术上直接。

Source:

- Geant4 Application Developers Guide: Control / User Interface - Defining New Commands
- Geant4 class: `G4UImessenger`

### 12.6 Is it necessary for this project?

Recommended。

`DetectorMessenger` 对诊断 sensitive/bias volume 有用；`AppMessenger` 可提供 config/output/verbose 命令，但要注意初始化状态。

### 12.7 Limitations and risks

- `AppMessenger::setMainConfig` 如果在 `/run/initialize` 后调用，需要明确是否允许 reconfigure。
- `DetectorMessenger::enableSD` 在几何已初始化后切换，需要 `/run/reinitializeGeometry` 或重建 SD，不能只改 bool。
- `DetectorMessenger` 绑定到 `DetectorConstruction`，而 `SimulationManager` 目前在 `CreateDetectorConstruction()` 后把 ownership 交给 `G4RunManager`，生命周期和指针归属要设计清楚。

### 12.8 Recommended implementation plan

最小接入：

- `AppMessenger`：作为 `SimulationManager` 成员，在 `BuildManagers()` 实例化，生命周期覆盖程序。
- `DetectorMessenger`：更适合由 `DetectorConstruction` 持有，在构造时创建 `std::unique_ptr<DetectorMessenger>`，这样命令生命周期与 detector 一致。
- 文档标注 detector 命令多为初始化前或诊断用；运行中改 SD 需要 reinitialize。

### 12.9 Documentation correction

Round 1 后文档应标注默认已注册，并说明哪些命令是初始化前配置命令、哪些是 geometry 构建后的诊断命令。

## 5. Mismatch Table

| Feature | Appears Supported In | Actual Status | Risk | Suggested Wording |
|---|---|---|---|---|
| `mode = volume_fraction` | `MaterialCommandParser`, docs examples/说明 | Parser only; `MaterialFactory` throws | 用户以为可运行，材料构建失败 | `volume_fraction` is reserved and parsed, but not implemented by `MaterialFactory`. |
| GDML import | `config/geometry/gdml_import.ini`, `macros/run_gdml.mac`, template name `gdml` | Placeholder; `VolumeBuilder` throws | `/run/initialize` 失败；`file`/`sensitive_volumes` 不生效 | GDML is a placeholder template only; no `G4GDMLParser` backend yet. |
| `macros/run_gdml.mac` | macro 文件 | 注释说不要 initialize，但实际包含 `/run/initialize` | 用户直接运行会失败 | Remove `/run/initialize` or rename as parser-only demo. |
| STL import | `docs/未实现功能.md` future mention | Not implemented | 用户误以为有 mesh import | STL import is planned only; no parser/backend exists. |
| LET/Dose/Fluence | `/AIHL/scoring/let|dose|fluence`, config keys | Registerable stubs/no-op | 输出为空但用户误以为得到物理量 | LET/Dose/Fluence are placeholders; only Edep/hits/event edep are operational. |
| ParticleAggregator | class name and docs future mention | Empty class | 用户误以为有高级粒子统计 | ParticleAggregator is a placeholder not connected to runtime. |
| Multi-thread output | `_t0` suffix, merge tools | Partial; shared manager, no auto merge | MT race / corrupted CSV / no merge | Use single-thread for production CSV until per-thread output is implemented. |
| `trap` / `trapezoid` | `ParseShape()` and docs | Implemented in Round 2 with `G4Trd/G4Trap` | `trap` 参数不合法时仍会构建失败 | `trd/trapezoid` use `G4Trd`; `trap` uses full `G4Trap` and must satisfy Geant4 solid constraints. |
| Qt UI | README/toolchain notes mention Qt; `--ui` | Geant4 UI/Vis only; no custom Qt app | 用户误解为项目 GUI | `--ui` starts Geant4 UI/Vis; no custom Qt GUI target exists. |
| `/AIHL/output/...` | `OutputMessenger` class name | Implemented in Round 1, minimal command set | 用户可能误以为含 hits/scoring 开关 | Output commands cover dir/thread suffix/status/flush/close only; use `/AIHL/scoring/...` for scoring switches. |
| importance / weight-window / splitting / Russian roulette | docs future list, `BiasingImportance` class | Not implemented | biasing 配置无效或误导 | Advanced biasing is future work; current backend is XS process biasing only. |
| `layered_device` copyNo/metadata | test goals / docs contrast with hierarchical | Implemented in Round 2 for storage/copyNo | metadata 不会自动进入 CSV | `copyNo` is used for placement; metadata is stored in `userProperties` only. |
| `/AIHL/app/...`, `/AIHL/detector/...` | source and `MODULE_API_INDEX.md` | Registered in Round 1 | 运行后重配置可能需要 reinitialize | Default executable registers these messengers; diagnostic commands are safe after geometry build. |

## 6. Implementation Value Matrix

| Feature | User Value | Implementation Difficulty | Physics Risk | Maintenance Cost | Recommended Priority |
|---|---|---|---|---|---|
| `volume_fraction` | Medium | Medium | Medium | Medium | P2 medium-term |
| GDML import | High | Medium | Medium | Medium | P2 medium-term |
| STL import | Medium | High | High | High | P3 future work |
| LETScorer | Medium | High | High | Medium | P3 future work |
| DoseScorer | High | Medium | Medium | Medium | P2 medium-term |
| FluenceScorer | Medium | Medium | Medium | Medium | P2 medium-term |
| ParticleAggregator | Medium | Low | Low | Medium | P3 future work |
| MT output + merge | High | Medium | Low | Medium | P1 near-term implementation |
| `trap` / `trapezoid` | Medium | Low | Low | Low | Completed in Round 2 |
| Qt UI | Low/Medium | High | Low | High | Do not implement now |
| OutputMessenger | High | Low | Low | Medium | Completed in Round 1 |
| Advanced biasing | Medium/High | High | High | High | P3 future work |
| layered copyNo/metadata | Medium | Low | Low | Low | Completed in Round 2 |
| App/Detector messenger registration | Medium | Low | Medium | Medium | Completed in Round 1 |

## 7. Recommended Roadmap

### P0: Documentation and test safety

- 修正 `macros/run_gdml.mac`：不要在 placeholder macro 中执行 `/run/initialize`，或明确该 macro 预期失败。
- 在所有测试配置中避免 `mode = volume_fraction`、GDML 真运行、STL、advanced biasing。`trd/trapezoid/trap` 与最小 `/AIHL/output/...` 命令已可用，但应遵守各自限制。
- 对 `LETScorer`、`DoseScorer`、`FluenceScorer` 保留 stub 标注，不把它们写成物理量已实现。
- 在命令文档中标注 `/AIHL/app/...`、`/AIHL/detector/...` 已默认注册，并说明初始化后危险重配置需要 reinitialize/warning。
- 在 README 或中文手册明确：多线程 CSV 输出当前不保证 race-free，生产数据建议单线程。

### P1: Low-risk useful features

- Round 1 已完成：实现 `OutputMessenger` 最小命令集合：`setDir`、`print`、`flush`、`close`、`setThreadSuffix`。
- Round 1 已完成：接入 `AppMessenger`，但限制运行后重配置。
- Round 1 已完成：让 `DetectorConstruction` 持有 `DetectorMessenger`，并明确运行中改 SD 需要 reinitialize。
- Round 2 已完成：实现 `trap` / `trd` / `G4Trap` 构建。
- Round 2 已完成：补齐 `LayeredDeviceTemplate` 的 `copyNo` 和 metadata 透传。
- 修复 MT 输出基本安全：至少做到 per-thread `OutputManager` 和正确 thread id。

### P2: Medium-complexity core features

- 实现 `volume_fraction`，按组分密度换算质量分数并支持 `density = auto`。
- 实现 GDML world replacement 模式，接入 `G4GDMLParser` 和 `GeometryRegistry` 映射。
- 引入 per-thread output + explicit merge，或部分迁移到 `G4AnalysisManager`。
- 补齐 `DoseScorer` 和明确口径的 `FluenceScorer`。

### P3: High-complexity or future features

- LET scoring：先写物理定义和 validation 文档，再实现。
- STL import：优先建议外部转换到 GDML；内建 STL 作为可选依赖或实验功能。
- Advanced biasing：先稳定 XS biasing，再做 importance / weight-window / RR。
- ParticleAggregator：等输出和 MT merge 稳定后实现。
- Qt UI：作为独立 target，晚于 CLI/macro 稳定版本。

## 8. Test Recommendations

### Safe to use now

- NIST 材料加载和 `mass_fraction` / `atom_count` 自定义材料。
- `simple_box`、`layered_device`、`hierarchical`、`array`、`shielding` 中已由 `VolumeBuilder` 支持的 CSG shapes：`box`、`tubs`、`sphere`、`orb`、`cone`、`trd/trapezoid`、`trap`。
- `layered_device` 的 `thickness`、`xy`、`material`、`position`、`rotation`、`sensitive`、`bias`、`region`、production cuts、visual fields、`copyNo`、`metadata.*` 和未知 key 透传。
- `hierarchical` 的 unknown key 保存、`copyNo` placement copy number。
- 当前 `/AIHL/material/...`、`/AIHL/geometry/...`、`/AIHL/physics/...`、`/AIHL/source/...`、`/AIHL/scoring/...`、`/AIHL/biasing/xs/...` 默认注册命令。
- hits CSV、event edep CSV、Edep histogram，前提是有真实 sensitive volume 和实际 hits。
- 单线程运行的 CSV 输出。
- XS process-level biasing，但需要 physics biasing enabled、目标 logical volume 注册、runtime validation。

### Avoid for now

```text
mode = volume_fraction
GDML import with /run/initialize
STL import
importance biasing
weight-window
splitting
Russian roulette
多线程生产级 CSV 输出
DoseScorer / FluenceScorer 作为物理量输出
LETScorer 作为真实 LET 输出
```

说明：`shape = trd/trapezoid`、`shape = trap`、最小 `/AIHL/output/...`、`/AIHL/app/...`、`/AIHL/detector/...` 已分别在 Round 1/Round 2 后可用；仍需遵守各自文档限制。

### Needs manual runtime verification

- XS process-level biasing 在目标 volume 上是否确实改变对应 process occurrence，需 analog vs biased run 对比。
- `hits_tN.csv` 是否生成，取决于粒子是否在 sensitive volume 中有 step / edep，以及 scoring/hits 开关。
- Region cuts 是否被正确应用到 `G4Region`，建议用 `/run/initialize` 后 Geant4 输出和小型物理测试确认。
- 多线程运行当前输出是否损坏，需要 race test；在修复前不建议作为生产输出。
- `--ui` + Qt/OpenGL visualization 取决于本地 Geant4 构建和运行时环境。

## 9. Final Recommendations

- 马上修正文档/测试安全项：`run_gdml.mac` 的 `/run/initialize` 风险、MT 输出不安全提示、stub scorer 说明；Round 1 后 messenger 注册状态需标为已注册并保留初始化前后限制。
- 近期值得实现：`OutputMessenger` 最小命令、`trap`/`trapezoid`、`layered_device` copyNo/metadata、App/Detector messenger 接入、per-thread 输出。
- 中期核心能力：`volume_fraction`、GDML 真导入、Dose/Fluence scorer、多线程 merge。
- 推迟：STL import、Qt UI、ParticleAggregator 高级分析。
- 高物理风险需先 validation：LET 定义、高级 biasing、带权重的 XS biasing 结果解释。
- 运行验证优先级：先做单线程 E2E macro，再做 XS biasing analog comparison，最后做 MT output stress test。
