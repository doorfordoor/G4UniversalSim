# G4UniversalSim 命令说明文档

## 1. 文档目的

本文档系统说明当前 G4UniversalSim 支持的命令接口，包括：

- `G4UniversalSim.exe` 命令行启动参数；
- 当前默认 executable 已注册的 `/AIHL/...` UI macro 命令；
- 源码中已经实现但当前默认 executable 尚未接入的 messenger 命令；
- `main.ini`、材料 ini、几何 ini、biasing ini 等配置 parser 支持的 section/key；
- 命令在 `/run/initialize` 前后的推荐使用时机、重初始化方式和当前限制。

本文档只记录当前源码真实实现的命令。未在源码中注册或未接入的命令不会当作默认可用命令描述。

## 2. 命令来源与版本说明

检查来源：

- `main.cc`：命令行参数解析、UI/macro 启动流程；
- `src/*/*Messenger.cc` 和 `include/*/*Messenger.hh`：`/AIHL/...` UI 命令；
- `src/Core/SimulationManager.cc`：默认 messenger 接入情况、主配置读取流程；
- `src/Config/*`：通用 ini 解析；
- `src/Materials/*IniReader*`、`src/Templates/*Template*`、`src/Geometry/GeometryConfig.cc`、`src/Physics/PhysicsManager.cc`、`src/Source/SourceManager.cc`、`src/Scoring/ScoringManager.cc`、`src/Biasing/BiasingManager.cc`：各模块配置 parser；
- `MODULE_API_INDEX.md`、`README.md`、`docs/`、`macros/`、`config/`：说明和示例交叉核对。

当前默认 executable 在 `SimulationManager::BuildManagers()` 中注册的 `/AIHL/...` messenger：

- `MaterialMessenger`：`/AIHL/material/...`
- `GeometryMessenger`：`/AIHL/geometry/...`
- `PhysicsMessenger`：`/AIHL/physics/...`
- `SourceMessenger`：`/AIHL/source/...`
- `BiasingMessenger`：`/AIHL/biasing/...`
- `ScoringMessenger`：`/AIHL/scoring/...`

源码存在但当前默认 executable 未注册或未完整实现：

- `AppMessenger`：源码定义 `/AIHL/app/...`，但当前 `SimulationManager` 未实例化它，默认运行时不可用。
- `DetectorMessenger`：源码定义 `/AIHL/detector/...`，但当前 `DetectorConstruction` 创建后未创建对应 messenger，默认运行时不可用。
- `OutputMessenger`：类存在，但当前没有定义任何 `/AIHL/output/...` 命令。

## 3. G4UniversalSim.exe 启动命令

### 3.1 基本语法

```powershell
G4UniversalSim.exe [positional_macro]
G4UniversalSim.exe --config config/main.ini --macro macros/run_simple.mac
G4UniversalSim.exe --config config/main.ini --ui
G4UniversalSim.exe --macro macros/run_simple.mac --threads 4 --seed 12345
```

如果既没有 `--macro` 也没有 `--ui`，程序只打印 usage 并正常退出，不会自动 `/run/beamOn`。

相对路径均按当前工作目录解析。推荐从项目根目录运行，或使用绝对路径。

### 3.2 参数总览表

| 参数 | 短参数 | 是否带值 | 默认值 | 作用 |
|---|---|---:|---|---|
| positional macro | 无 | 是 | 空 | 位置参数形式指定 macro 文件；不能和另一个 macro 重复指定 |
| `--config` | `-c` | 是 | 空 | 主 ini 配置文件 |
| `--macro` | `-m` | 是 | 空 | 启动后执行的 Geant4 macro |
| `--output` | `-o` | 是 | context 默认 `output` | 覆盖输出目录 |
| `--run-name` | 无 | 是 | context 默认 run name | 覆盖 run 名称 |
| `--ui` | 无 | 否 | `false` | 启动交互 UI，并创建 `G4VisExecutive` |
| `--threads` | `-t` | 是 | `1` 或配置文件值 | MT Geant4 下设置 worker 线程数，必须大于 0 |
| `--seed` | 无 | 是 | unset | 设置随机数种子，必须为无符号整数 |
| `--check-overlaps` | 无 | 是 | context/config 默认 | 覆盖几何 overlap 检查开关 |
| `--dry-run` | 无 | 否 | `false` | 创建 managers 和 Geant4 user initialization objects，但跳过 macro/UI |
| `--help` | `-h` | 否 | `false` | 打印帮助并退出 |

当前 `main.cc` 没有实现 `--version`。传入 `--version` 会被当作未知命令行参数并报错。

### 3.3 参数详细说明

#### `-c` / `--config <file>`

加载主配置文件。文件必须存在，否则 `SimulationManager::LoadConfig()` 报错。

示例：

```powershell
G4UniversalSim.exe --config test/main_layered_device.ini --macro test/macros/test_layered_device_full.mac
```

#### `-m` / `--macro <file>`

指定启动后执行的 macro。程序内部执行：

```text
/control/execute <macroFile>
```

macro 文件路径按当前工作目录解析。也可以用位置参数指定 macro：

```powershell
G4UniversalSim.exe macros/run_simple.mac
```

不能同时提供多个 macro 位置参数。

#### `-o` / `--output <dir>`

覆盖输出目录，并传给 `OutputManager::SetOutputDir()`。当前没有 `/AIHL/output/...` macro 命令，因此运行时 output dir 主要通过命令行或 `[output]/dir` 设置。

#### `--run-name <name>`

覆盖 run name，写入 run summary。

#### `--ui`

启动 Geant4 交互 UI。只有传入 `--ui` 时，`main.cc` 才创建并初始化 `G4VisExecutive`。因此可视化 macro 如 `/vis/open ...` 通常需要配合 `--ui` 使用。

#### `-t` / `--threads <N>`

请求 worker 线程数。`N` 必须大于 0。MT 构建下传给 `G4MTRunManager::SetNumberOfThreads()`；非 MT 构建下该值保存在 context 中但不会创建 MT run manager。

#### `--seed <N>`

设置 `SimulationContext` seed，并在 `sim.Initialize()` 后调用 `CLHEP::HepRandom::setTheSeed()`。

#### `--check-overlaps <true|false>`

支持值：`true/false`、`1/0`、`on/off`、`yes/no`。解析大小写敏感程度按 `main.cc::ParseBoolOption()`，当前只接受小写字符串和数字。

#### `--dry-run`

执行配置加载、manager 构建、Detector/Physics/Action initialization object 创建，但跳过 macro 和 UI。

#### `--help` / `-h`

打印 usage 并退出。当前无 `--version`。

### 3.4 常用启动示例

```powershell
# 使用 main.ini + macro
.\build_vs2026\Release\G4UniversalSim.exe --config config/main.ini --macro macros/run_simple.mac

# 仅使用自举 macro
.\build_vs2026\Release\G4UniversalSim.exe --macro macros/run_simple.mac

# 覆盖输出目录和随机种子
.\build_vs2026\Release\G4UniversalSim.exe --config config/main.ini --macro macros/run_simple.mac --output output/run01 --seed 12345

# 启动 UI，可执行可视化 macro
.\build_vs2026\Release\G4UniversalSim.exe --config test/main_layered_device.ini --macro test/macros/vis.mac --ui

# dry-run 检查对象创建链路
.\build_vs2026\Release\G4UniversalSim.exe --config config/main.ini --macro macros/run_simple.mac --dry-run
```

## 4. Macro 命令总览

当前默认可用的 `/AIHL/...` 命令前缀：

| 模块 | 前缀 | 默认 executable 是否注册 | 主要用途 |
|---|---|---:|---|
| Material | `/AIHL/material/` | 是 | 加载、创建、打印材料 |
| Geometry | `/AIHL/geometry/` | 是 | 设置几何模板、加载几何、添加用户体、overlap 开关 |
| Physics | `/AIHL/physics/` | 是 | reference/manual physics、cuts、biasing hook、MicroElec |
| Source | `/AIHL/source/` | 是 | GPS preset、粒子、能量、位置、方向 |
| Scoring | `/AIHL/scoring/` | 是 | hits、event edep、histogram、scorer 开关 |
| Biasing | `/AIHL/biasing/` | 是 | XS biasing 规则和 operator attachment 配置 |
| App | `/AIHL/app/` | 否 | 源码存在，但默认未实例化 |
| Detector | `/AIHL/detector/` | 否 | 源码存在，但默认未实例化 |
| Output | `/AIHL/output/` | 否 | 当前 `OutputMessenger` 为空，无命令 |

此外，Geant4 原生命令仍可使用，例如：

```text
/run/initialize
/run/beamOn 100
/run/reinitializeGeometry
/run/physicsModified
/control/execute macros/run_simple.mac
/gps/particle proton
/vis/open OGL
```

## 5. Material 模块命令

命令前缀：`/AIHL/material/`。默认已注册。

| 命令 | UI cmd 类型 | 参数格式 | 初始化时机 | 作用 |
|---|---|---|---|---|
| `/AIHL/material/load <file>` | `G4UIcmdWithAString` | 1 个材料 ini 路径 | 建议 `/run/initialize` 前 | 读取材料配置并 `BuildAll()` |
| `/AIHL/material/print` | `G4UIcmdWithoutParameter` | 无 | 任意 | 打印 isotope/element/material |
| `/AIHL/material/list` | `G4UIcmdWithoutParameter` | 无 | 任意 | 同 `print` |
| `/AIHL/material/addNist <kv>` | `G4UIcmdWithAString` | `nist=G4_Si [name=silicon]` | 建议初始化前 | 注册 NIST 材料，可设别名 |
| `/AIHL/material/addIsotope <kv>` | `G4UIcmdWithAString` | `name=U235 symbol=U z=92 n=235 a=235.0439 g/mole` | 初始化前 | 添加并构建 isotope |
| `/AIHL/material/addElement <kv>` | `G4UIcmdWithAString` | `name=Si symbol=Si z=14 a=28.0855 g/mole` | 初始化前 | 添加并构建元素 |
| `/AIHL/material/addElementFromIsotopes <kv>` | `G4UIcmdWithAString` | `name=U symbol=U isotopes=U235:0.05,U238:0.95` | 初始化前 | 从同位素构建元素 |
| `/AIHL/material/addMaterial <kv>` | `G4UIcmdWithAString` | `name=SiO2 density=2.2 g/cm3 components=Si:1,O:2 [mode=atom_count]` | 初始化前 | 添加并构建自定义材料 |
| `/AIHL/material/buildAll` | `G4UIcmdWithoutParameter` | 无 | 初始化前 | 构建所有已注册定义 |
| `/AIHL/material/setLocked <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前或诊断 | 锁定材料管理器，拒绝新定义 |
| `/AIHL/material/clear` | `G4UIcmdWithoutParameter` | 无 | 初始化前更安全 | 清空材料定义和已注册指针 |

示例：

```text
/AIHL/material/load test/materials/test_materials.ini
/AIHL/material/addNist nist=G4_Si name=silicon
/AIHL/material/addMaterial name=Si3N4 density=3.17 g/cm3 mode=atom_count components=Si:3,N:4
/AIHL/material/print
```

材料配置文件支持格式：

```ini
[Nist]
materials = G4_AIR, G4_Si

[world]
material = G4_AIR

[element.Si]
symbol = Si
z = 14
a = 28.0855 g/mole

[material.Si3N4]
density = 3.17 g/cm3
mode = atom_count
components = Si:3,N:4
state = solid
```

支持 `mode = atom_count`、`mass_fraction`；`volume_fraction` 可被 parser 识别但 `MaterialFactory` 当前明确未实现。

## 6. Geometry 模块命令

命令前缀：`/AIHL/geometry/`。默认已注册。

| 命令 | UI cmd 类型 | 参数格式 | 初始化时机 | 作用 |
|---|---|---|---|---|
| `/AIHL/geometry/setTemplate <name>` | `G4UIcmdWithAString` | `simple_box`、`layered_device`、`hierarchical`、`array`、`shielding`、`gdml` | `/run/initialize` 前 | 设置几何模板 |
| `/AIHL/geometry/loadConfig <file>` | `G4UIcmdWithAString` | 几何 ini 路径 | `/run/initialize` 前 | 加载几何配置 |
| `/AIHL/geometry/checkOverlaps <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前；初始化后需重建几何 | 设置 placement overlap 检查 |
| `/AIHL/geometry/setDefaultWorldMaterial <name>` | `G4UIcmdWithAString` | 材料名 | 初始化前 | 设置 world fallback 材料 |
| `/AIHL/geometry/addBox <kv>` | `G4UIcmdWithAString` | key=value 整行 | 初始化前；初始化后需重建几何 | 添加用户 box 体 |
| `/AIHL/geometry/addTubs <kv>` | `G4UIcmdWithAString` | key=value 整行 | 初始化前；初始化后需重建几何 | 添加用户 tubs/cylinder 体 |
| `/AIHL/geometry/addVolume <kv>` | `G4UIcmdWithAString` | `shape=box` 或 `shape=tubs` | 初始化前；初始化后需重建几何 | 添加通用用户体 |
| `/AIHL/geometry/removeUserVolume <name>` | `G4UIcmdWithAString` | 用户体名称 | 初始化前；初始化后需重建几何 | 删除用户添加的体及子树 |
| `/AIHL/geometry/print` | `G4UIcmdWithoutParameter` | 无 | 任意 | 打印 GeometryManager 摘要 |
| `/AIHL/geometry/printTree` | `G4UIcmdWithoutParameter` | 无 | 任意 | 打印当前 VolumeNode 树 |
| `/AIHL/geometry/clear` | `G4UIcmdWithoutParameter` | 无 | 初始化前更安全 | 清空 geometry state |
| `/AIHL/geometry/clearUserVolumes` | `G4UIcmdWithoutParameter` | 无 | 初始化前；初始化后需重建几何 | 清空用户添加体 |
| `/AIHL/geometry/listUserVolumes` | `G4UIcmdWithoutParameter` | 无 | 任意 | 列出用户添加体 |
| `/AIHL/geometry/preserveUserVolumesOnLoad <bool>` | `G4UIcmdWithABool` | `true/false` | 加载 geometry 前 | 控制 loadConfig 后是否保留用户体 |
| `/AIHL/geometry/markModified` | `G4UIcmdWithoutParameter` | 无 | 初始化后 | 调用 `G4RunManager::GeometryHasBeenModified()` |

`addBox` / `addTubs` / `addVolume` 的共同 key：

- 必需：`name`、`parent`、`material`；
- 可选：`position`、`rotation`、`sensitive`、`bias`、`region`、`color`、`alpha`、`visible`、`wireframe`；
- `addBox` 必需：`size="x,y,z"`；
- `addTubs` 必需：`rmax`、`halfz`；可选 `rmin`、`startphi`、`deltaphi`；
- `addVolume shape=box` 必需 `size`；
- `addVolume shape=tubs` 必需 `parameters="rMin,rMax,halfZ,startPhi,deltaPhi"`。

示例：

```text
/AIHL/geometry/setTemplate layered_device
/AIHL/geometry/loadConfig test/geometry/layered_device_test.ini
/AIHL/geometry/checkOverlaps true
/AIHL/geometry/addBox name=Extra parent=world material=G4_Si size="1 cm,1 cm,1 mm" position="0 mm,0 mm,2 cm" sensitive=true region=SV
/AIHL/geometry/printTree
```

初始化后修改几何的典型流程：

```text
/AIHL/geometry/addBox name=Extra parent=world material=G4_Si size="1 cm,1 cm,1 mm"
/AIHL/geometry/markModified
/run/reinitializeGeometry
```

### 6.1 几何模板配置字段

可用模板名称：`simple_box`、`layered_device`、`hierarchical`、`array`、`shielding`、`gdml`。

`simple_box`：

- `[world]`：`size`、`material`；
- `[target]`：`name`、`shape`、`size`、`material`、`position`、`rotation`、`sensitive`、`bias`、`region`、`cut.gamma`、`cut.e-`、`cut.e+`、`cut.proton`；
- `[visual.world]` / `[visual.target]`：`color`、`alpha`、`visible`、`wireframe`。

`layered_device`：

- `[world]`：`size`、`material`；
- `[layers]`：`count`、`names`、`auto_stack`、`axis`、`gap`、`z_start`；当前 `axis` 只支持 `z`；
- `[layer.<name>]`：`thickness`、`xy`、`material`、`position`（仅 `auto_stack=false` 时使用）、`rotation`、`sensitive`、`bias`、`region`、`cut.*`、`vis.color`、`vis.alpha`、`vis.visible`、`vis.wireframe`。

`hierarchical`：

- 使用通用 `[world]` 和 `[volume.<name>]`；
- 支持 key：`name`、`parent`、`shape`、`size`、`parameters`、`material`、`position`、`rotation`、`sensitive`、`bias`、`region`、`placement`、`vis.color`、`vis.alpha`、`vis.visible`、`vis.wireframe`、`cut.*`；
- 未知 key 会作为 `userProperties` 保存；`copyNo` 会被 `VolumeBuilder` 用作 placement copy number。

`array`：

- `[world]`：`size`、`material`；
- `[array]`：`name`、`counts`、`element_size`、`pitch`、`center`、`shape`、`material`、`sensitive`、`bias`、`region`。

`shielding`：

- `[world]`：`size`、`material`；
- `[shielding]`：`axis`（当前只支持 `z`）、`area`、`gap`、`start`、`layers`；
- `[shield.<name>]`：`thickness`、`material`、`bias`、`sensitive`、`region`；
- 可选 `[detector]`：`size`、`position`、`material`、`sensitive`、`region`。

`gdml`：

- `[gdml]`：`file`、`world_name`、`sensitive_volumes`、`bias_volumes`；
- 当前 `GDMLTemplate` 是 placeholder，`VolumeBuilder` 对 GDML import 明确未实现，不能作为真实 GDML 导入使用。

## 7. Physics 模块命令

命令前缀：`/AIHL/physics/`。默认已注册。

| 命令 | UI cmd 类型 | 参数格式 | 初始化时机 | 作用 |
|---|---|---|---|---|
| `/AIHL/physics/setEM <option>` | `G4UIcmdWithAString` | EM option/alias | 初始化前 | 设置手动 EM；reference 模式下尝试修改 EM suffix |
| `/AIHL/physics/setReferenceList <name>` | `G4UIcmdWithAString` | 如 `FTFP_BERT_EMZ` | 初始化前 | 设置 Geant4 reference physics list |
| `/AIHL/physics/clearReferenceList` | `G4UIcmdWithoutParameter` | 无 | 初始化前 | 回到 manual 模式 |
| `/AIHL/physics/setBaseReferenceList <name>` | `G4UIcmdWithAString` | 如 `FTFP_BERT` | 初始化前 | 设置 reference base |
| `/AIHL/physics/addModule <option>` | `G4UIcmdWithAString` | module alias | 初始化前 | manual 模式添加 module；reference 模式转为 extra module |
| `/AIHL/physics/removeModule <option>` | `G4UIcmdWithAString` | module alias | 初始化前 | 删除 module |
| `/AIHL/physics/clearModules` | `G4UIcmdWithoutParameter` | 无 | 初始化前 | 清空 module |
| `/AIHL/physics/addHadronic <option>` | `G4UIcmdWithAString` | hadronic alias | 初始化前 | 添加 hadronic 模块 |
| `/AIHL/physics/addOther <option>` | `G4UIcmdWithAString` | other alias | 初始化前 | 添加非 hadronic 模块 |
| `/AIHL/physics/addExtraModule <option>` | `G4UIcmdWithAString` | module alias | 初始化前 | reference 模式添加 extra module |
| `/AIHL/physics/removeExtraModule <option>` | `G4UIcmdWithAString` | module alias | 初始化前 | 删除 extra module |
| `/AIHL/physics/clearExtraModules` | `G4UIcmdWithoutParameter` | 无 | 初始化前 | 清空 extra modules |
| `/AIHL/physics/setDefaultCut <value unit>` | `G4UIcmdWithAString` | 长度，如 `1 mm` | 初始化前；初始化后需 `/run/physicsModified` | 设置全局 production cut |
| `/AIHL/physics/setCut <particle> <value unit>` | `G4UIcmdWithAString` | 如 `e- 100 nm` | 初始化前；初始化后需 `/run/physicsModified` | 设置粒子 cut |
| `/AIHL/physics/setRegionCut <region> <particle> <value unit>` | `G4UIcmdWithAString` | 如 `SV e- 100 nm` | 初始化前 | 保存 region cut 配置 |
| `/AIHL/physics/enableBiasing <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前 | 注册 generic biasing physics hook 的开关 |
| `/AIHL/physics/enableMicroElec <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前 | 启用 MicroElec 扩展 |
| `/AIHL/physics/setMicroElecRegion <region>` | `G4UIcmdWithAString` | region 名 | 初始化前 | 设置 MicroElec region |
| `/AIHL/physics/enableElectronCapture <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前 | 启用 electron capture helper |
| `/AIHL/physics/setElectronCaptureThreshold <value unit>` | `G4UIcmdWithAString` | 能量，如 `16.7 eV` | 初始化前 | 设置电子捕获阈值 |
| `/AIHL/physics/verbose <level>` | `G4UIcmdWithAnInteger` | 整数 >= 0 | 任意 | 设置 physics verbose |
| `/AIHL/physics/print` | `G4UIcmdWithoutParameter` | 无 | 任意 | 打印 physics 摘要 |
| `/AIHL/physics/listAvailableReferences` | `G4UIcmdWithoutParameter` | 无 | 任意 | 列出可用 reference list |
| `/AIHL/physics/listAvailableEMReferences` | `G4UIcmdWithoutParameter` | 无 | 任意 | 列出可用 EM reference suffix/option |

示例：

```text
/AIHL/physics/setReferenceList FTFP_BERT_EMZ
/AIHL/physics/setDefaultCut 1 mm
/AIHL/physics/setCut proton 10 um
/AIHL/physics/setRegionCut SV e- 100 nm
/AIHL/physics/enableBiasing true
/AIHL/physics/print
```

配置文件支持：

```ini
[physics]
reference = FTFP_BERT_EMZ
em = option4
modules = decay, ion
extra_modules = optical
default_cut = 1 mm
biasing = true
verbose = 1

[physics.cuts]
gamma = 1 mm
e- = 100 nm
proton = 10 um

[physics.region.SV]
e- = 100 nm

[physics.microelec]
enabled = false
region = SV
electron_capture = false
electron_capture_threshold = 16.7 eV
```

## 8. Source 模块命令

命令前缀：`/AIHL/source/`。默认已注册。底层使用 `G4GeneralParticleSource`，Geant4 原生 `/gps/...` 仍可使用。

| 命令 | UI cmd 类型 | 参数格式 | 初始化时机 | 作用 |
|---|---|---|---|---|
| `/AIHL/source/preset <name>` | `G4UIcmdWithAString` | preset 名 | 建议初始化前 | 应用源 preset |
| `/AIHL/source/particle <particle>` | `G4UIcmdWithAString` | Geant4 粒子名 | 初始化前；初始化后下次事件使用新 GPS 状态 | 设置粒子 |
| `/AIHL/source/energy <value unit>` | `G4UIcmdWithAString` | 能量，如 `10 MeV` | 初始化前或 beamOn 前 | 设置单能 |
| `/AIHL/source/point <x y z unit>` | `G4UIcmdWithAString` | `0 0 -1 mm` 或 `0 mm,0 mm,-1 mm` | 初始化前或 beamOn 前 | 点源位置 |
| `/AIHL/source/direction <x y z>` | `G4UIcmdWithAString` | 无单位方向向量 | 初始化前或 beamOn 前 | 定向束流方向 |
| `/AIHL/source/isotropic` | `G4UIcmdWithoutParameter` | 无 | 初始化前或 beamOn 前 | 各向同性角分布 |
| `/AIHL/source/planeBeam <args>` | `G4UIcmdWithAString` | key=value 或位置参数 | 初始化前或 beamOn 前 | 圆形平面束斑 |
| `/AIHL/source/print` | `G4UIcmdWithoutParameter` | 无 | 任意 | 打印 source 摘要 |
| `/AIHL/source/reset` | `G4UIcmdWithoutParameter` | 无 | beamOn 前更安全 | 重置 GPS 和缓存配置 |

支持 preset：

- `mono_proton`
- `proton_beam`
- `neutron_beam`
- `gamma_beam`
- `isotropic_neutron`
- `plane_proton_beam`

`planeBeam` 示例：

```text
/AIHL/source/planeBeam radius=1 mm z=-1 mm direction=+z
/AIHL/source/planeBeam 1 mm -1 mm +z
```

配置文件支持：

```ini
[source]
preset = proton_beam
particle = proton
energy = 10 MeV
position_type = point
position = 0,0,-1 mm
direction = 0,0,1
isotropic = false
radius = 1 mm
center = 0,0,-1 mm
verbose = 1
```

`position_type = plane` 时使用 `radius` 和 `center` 的 z 分量。

## 9. Scoring 模块命令

命令前缀：`/AIHL/scoring/`。默认已注册。

| 命令 | UI cmd 类型 | 参数格式 | 初始化时机 | 作用 |
|---|---|---|---|---|
| `/AIHL/scoring/enable <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前或 run 前 | scoring 总开关 |
| `/AIHL/scoring/hits <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前或 run 前 | 是否写 hit CSV |
| `/AIHL/scoring/eventEdep <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前或 run 前 | 是否写 event edep CSV |
| `/AIHL/scoring/edep <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前或 run 前 | 是否启用 EdepScorer |
| `/AIHL/scoring/let <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前或 run 前 | 启用 LETScorer stub |
| `/AIHL/scoring/dose <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前或 run 前 | 启用 DoseScorer stub |
| `/AIHL/scoring/fluence <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前或 run 前 | 启用 FluenceScorer stub |
| `/AIHL/scoring/autoCreateScorers <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前或 run 前 | BeginRun 自动创建默认 scorer |
| `/AIHL/scoring/setEdepHistogram <args>` | `G4UIcmdWithAString` | `bins=100 min=0 eV max=10 MeV` 或 `100 0 eV 10 MeV` | run 前 | 设置 raw edep histogram |
| `/AIHL/scoring/setWeightedEdepHistogram <args>` | `G4UIcmdWithAString` | 同上 | run 前 | 设置 weighted edep histogram |
| `/AIHL/scoring/verbose <level>` | `G4UIcmdWithAnInteger` | 整数 >= 0 | 任意 | scoring verbose |
| `/AIHL/scoring/print` | `G4UIcmdWithoutParameter` | 无 | 任意 | 打印 scoring 摘要 |

histogram 参数形式：

```text
/AIHL/scoring/setEdepHistogram bins=100 min=0 eV max=10 MeV
/AIHL/scoring/setEdepHistogram bins=100 min=0*eV max=10*MeV
/AIHL/scoring/setEdepHistogram bins=100 min=0eV max=10MeV
/AIHL/scoring/setEdepHistogram 100 0 eV 10 MeV
```

配置文件支持：

```ini
[scoring]
enabled = true
hits = true
event_edep = true
edep = true
let = false
dose = false
fluence = false
auto_create_default_scorers = true
verbose = 1

[scoring.edep]
raw_histogram = true
weighted_histogram = true
bins = 200
min = 0 eV
max = 10 MeV
volume_summary = true
particle_summary = true
```

注意：`hits_t0.csv` 只有在 sensitive detector 收到非零 `edep` 或 `ndep` hit 时才会创建。零能量 step 默认被 `SensitiveDetector` 跳过，当前没有 macro 命令打开 zero-edep hit 输出。

## 10. Biasing 模块命令

命令前缀：`/AIHL/biasing/`。默认已注册。

当前 biasing 以 cross-section biasing 为主。新版源码支持 process-level 规则，旧的 particle-level 写法仍兼容但会打印 warning。

### 10.1 总开关和诊断命令

| 命令 | UI cmd 类型 | 参数格式 | 初始化时机 | 作用 |
|---|---|---|---|---|
| `/AIHL/biasing/enable <bool>` | `G4UIcmdWithABool` | `true/false` | 初始化前 | 启用 BiasingManager |
| `/AIHL/biasing/validate` | `G4UIcmdWithoutParameter` | 无 | 初始化前或诊断 | 校验当前规则 |
| `/AIHL/biasing/print` | `G4UIcmdWithoutParameter` | 无 | 任意 | 打印规则和 attachment 状态 |
| `/AIHL/biasing/clear` | `G4UIcmdWithoutParameter` | 无 | 初始化前更安全 | 清空规则和 operators |
| `/AIHL/biasing/xs/printRules` | `G4UIcmdWithoutParameter` | 无 | 任意 | 打印 XS rules |

还必须配合：

```text
/AIHL/physics/enableBiasing true
```

或者在 `[physics]/biasing = true` 和 `[biasing]/enabled = true` 中配置。否则只配置 BiasingManager 不一定注册 generic biasing physics hook。

### 10.2 推荐的 process-level 命令

| 命令 | 参数格式 | 作用 |
|---|---|---|
| `/AIHL/biasing/xs/addRule <particle> <process>` | 2 个参数 | 创建或获取粒子+过程规则 |
| `/AIHL/biasing/xs/setRuleFactor <particle> <process> <factor>` | 3 个参数 | 设置该过程的 factor，必须 > 0 |
| `/AIHL/biasing/xs/setRuleOnlyPrimary <particle> <process> <bool>` | 3 个参数 | 设置只作用 primary |
| `/AIHL/biasing/xs/setRuleApplyToSecondaries <particle> <process> <bool>` | 3 个参数 | 设置作用 secondaries；与 onlyPrimary 互斥 |
| `/AIHL/biasing/xs/setRuleMinWeight <particle> <process> <value>` | 3 个参数 | 设置 min weight，当前允许 >= 0 |
| `/AIHL/biasing/xs/setRuleMaxInteractions <particle> <process> <n>` | 3 个参数 | 设置 max interactions，允许 `-1` 或 >= 0 |
| `/AIHL/biasing/xs/addRuleVolume <particle> <process> <volume>` | 3 个参数 | 为该过程规则添加 target volume |

示例：

```text
/AIHL/biasing/enable true
/AIHL/physics/enableBiasing true

/AIHL/biasing/xs/addRule proton protonInelastic
/AIHL/biasing/xs/setRuleFactor proton protonInelastic 3.0
/AIHL/biasing/xs/setRuleOnlyPrimary proton protonInelastic false
/AIHL/biasing/xs/setRuleApplyToSecondaries proton protonInelastic true
/AIHL/biasing/xs/setRuleMinWeight proton protonInelastic 0.02
/AIHL/biasing/xs/setRuleMaxInteractions proton protonInelastic 8
/AIHL/biasing/xs/addRuleVolume proton protonInelastic sensor_1
```

### 10.3 兼容的 legacy particle-level 命令

这些命令仍可用，但属于兼容写法；多个 process 共享同一套参数。

| 命令 | 参数格式 | 作用 |
|---|---|---|
| `/AIHL/biasing/xs/addParticle <particle>` | 1 个参数 | 创建 legacy 粒子规则 |
| `/AIHL/biasing/xs/addProcess <process>` | 1 个参数 | 向唯一 legacy 规则添加 process；多规则时歧义报错 |
| `/AIHL/biasing/xs/addProcessForParticle <particle> <process>` | 2 个参数 | 向指定粒子 legacy 规则添加 process |
| `/AIHL/biasing/xs/setFactor <particle> <factor>` | 2 个参数 | 设置 legacy 粒子规则 factor |
| `/AIHL/biasing/xs/onlyPrimary <particle> <bool>` | 2 个参数 | 设置 legacy onlyPrimary |
| `/AIHL/biasing/xs/applyToSecondaries <particle> <bool>` | 2 个参数 | 设置 legacy secondaries |
| `/AIHL/biasing/xs/setMinWeight <particle> <value>` | 2 个参数 | 设置 legacy minWeight |
| `/AIHL/biasing/xs/setMaxInteractions <particle> <n>` | 2 个参数 | 设置 legacy maxInteractions |
| `/AIHL/biasing/xs/addVolume <volume>` | 1 个参数 | 添加全局 target volume |
| `/AIHL/biasing/xs/addVolumeForParticle <particle> <volume>` | 2 个参数 | 添加 legacy 粒子规则 volume |

部分 legacy 命令现在也支持 process-level 参数数量：

```text
/AIHL/biasing/xs/setFactor proton protonInelastic 3.0
/AIHL/biasing/xs/onlyPrimary proton protonInelastic false
/AIHL/biasing/xs/applyToSecondaries proton protonInelastic true
/AIHL/biasing/xs/setMinWeight proton protonInelastic 0.02
/AIHL/biasing/xs/setMaxInteractions proton protonInelastic 8
/AIHL/biasing/xs/addVolume proton protonInelastic sensor_1
```

但为清晰起见，推荐使用 `setRule*` 和 `addRuleVolume` 命令。

### 10.4 Biasing 配置文件

推荐 process-level ini：

```ini
[biasing]
enabled = true

[biasing.xs.proton.protonInelastic]
factor = 3.0
volumes = sensor_1, shield
only_primary = false
apply_to_secondaries = true
min_weight = 0.02
max_interactions = 8

[biasing.xs.neutron.neutronInelastic]
factor = 5.0
volumes = shield
only_primary = true
apply_to_secondaries = false
min_weight = 0.05
max_interactions = 5
```

section 名称格式必须是：

```ini
[biasing.xs.<particle>.<process>]
```

process 名中包含 `.` 当前不支持。section 内可选 `particle` 和 `process` 覆盖 section 名，但通常不建议这样写。

兼容 legacy ini：

```ini
[biasing]
enabled = true

[biasing.xs]
particles = proton, neutron
processes = protonInelastic, neutronInelastic
factor = 3.0
volumes = sensor_1, shield
only_primary = false
apply_to_secondaries = true
min_weight = 0.02
max_interactions = 8
```

legacy 写法会扩展为粒子+过程组合：每个 listed particle 会使用所有 listed processes，并共享同一套 `factor/volumes/only_primary/apply_to_secondaries/min_weight/max_interactions`。显式 process-level rule 会覆盖同一粒子+过程的 legacy expansion。

## 11. Output 模块命令

当前 `OutputMessenger` 没有定义任何 `/AIHL/output/...` 命令。输出目录和输出行为来自：

- 命令行 `--output <dir>`；
- 主配置 `[output]/dir`；
- `ScoringManager` 的 hits/event_edep/scorer/histogram 开关；
- `OutputManager` 自动按线程后缀写文件，如 `_t0`。

常见输出文件：

| 文件 | 创建条件 |
|---|---|
| `run_summary.txt` | `SimulationManager::Initialize()` 和 run end 写入 |
| `event_edep_t0.csv` | `scoring.event_edep` 启用，event 结束时写 |
| `hits_t0.csv` | `scoring.hits` 启用，且 sensitive volume 有非零 hit |
| `hist_edep_raw_t0.csv` | EdepScorer raw histogram 启用，run end 写 |
| `hist_edep_weighted_t0.csv` | EdepScorer weighted histogram 启用，run end 写 |
| `edep_volume_summary_t0.csv` | volume summary 启用，run end 写 |
| `edep_particle_summary_t0.csv` | particle summary 启用，run end 写 |

## 12. Detector / Sensitive Detector 模块命令

`DetectorMessenger` 源码中定义了 `/AIHL/detector/...` 命令，但当前默认 executable 没有实例化 `DetectorMessenger`，因此这些命令默认不可用。

源码已实现命令如下，仅供后续接入参考：

| 命令 | UI cmd 类型 | 参数格式 | 作用 |
|---|---|---|---|
| `/AIHL/detector/enableSD <bool>` | `G4UIcmdWithABool` | `true/false` | 启用/禁用 `ConstructSDandField()` 中的 SD 绑定 |
| `/AIHL/detector/setSDName <name>` | `G4UIcmdWithAString` | 1 个名称 | 设置 SD 名称 |
| `/AIHL/detector/printRegistry` | `G4UIcmdWithoutParameter` | 无 | 打印 GeometryRegistry 摘要 |
| `/AIHL/detector/printSensitiveVolumes` | `G4UIcmdWithoutParameter` | 无 | 打印 sensitive volume 名称 |
| `/AIHL/detector/printBiasVolumes` | `G4UIcmdWithoutParameter` | 无 | 打印 bias volume 名称 |
| `/AIHL/detector/setVerbose <level>` | `G4UIcmdWithAnInteger` | 整数 | 设置 DetectorConstruction verbose |
| `/AIHL/detector/printWorld` | `G4UIcmdWithoutParameter` | 无 | 打印 worldVolume 是否已构建 |

Sensitive detector 当前由 `SimulationManager::CreateSensitiveDetectorFactory()` 自动创建，名称为 `AIHLParticleSD`，并绑定到 GeometryRegistry 中标记为 sensitive 的 logical volume。

当前没有命令控制 `SensitiveDetector::EnableZeroEdepHits()`，所以零能量 step 默认不写 hits。

## 13. Run / Simulation 控制相关命令

### 13.1 当前默认可用的 Geant4 原生命令

这些不是 `/AIHL/...` 命令，但在 macro 中常用：

| 命令 | 作用 |
|---|---|
| `/run/initialize` | 初始化 geometry、physics、actions |
| `/run/beamOn <N>` | 执行 N 个 event |
| `/run/reinitializeGeometry` | 重新初始化几何 |
| `/run/physicsModified` | 通知 Geant4 physics 已修改 |
| `/run/verbose <level>` | Geant4 run verbose |
| `/event/verbose <level>` | event verbose |
| `/tracking/verbose <level>` | tracking verbose |
| `/control/execute <file>` | 执行 macro |
| `/gps/...` | Geant4 GPS 原生命令 |
| `/vis/...` | Geant4 visualization 原生命令 |

### 13.2 AppMessenger 源码命令

`AppMessenger` 源码中定义了 `/AIHL/app/...`，但当前默认 executable 未注册，默认不可用。

已实现命令：

| 命令 | UI cmd 类型 | 参数格式 | 作用 |
|---|---|---|---|
| `/AIHL/app/setMainConfig <file>` | `G4UIcmdWithAString` | 路径 | 设置主配置文件 |
| `/AIHL/app/setOutputDir <dir>` | `G4UIcmdWithAString` | 路径 | 设置输出目录 |
| `/AIHL/app/setNumThreads <N>` | `G4UIcmdWithAnInteger` | `N > 0` | 设置线程数 |
| `/AIHL/app/setSeed <N>` | `G4UIcmdWithAnInteger` | `N >= 0` | 设置 seed |
| `/AIHL/app/setVerbose <level>` | `G4UIcmdWithAnInteger` | 整数 | 设置 verbose |
| `/AIHL/app/setCheckOverlaps <bool>` | `G4UIcmdWithABool` | bool | 设置 overlap 开关 |
| `/AIHL/app/printSummary` | `G4UIcommand` | 无 | 打印 SimulationManager 摘要 |

## 14. 推荐 macro 执行顺序

推荐顺序：

```text
/run/verbose 1
/event/verbose 0
/tracking/verbose 0

# 1. materials
/AIHL/material/load test/materials/test_materials.ini

# 2. geometry
/AIHL/geometry/setTemplate layered_device
/AIHL/geometry/loadConfig test/geometry/layered_device_test.ini
/AIHL/geometry/checkOverlaps true

# 3. physics
/AIHL/physics/setReferenceList FTFP_BERT_EMZ
/AIHL/physics/setDefaultCut 1 mm
/AIHL/physics/enableBiasing true

# 4. source
/AIHL/source/preset proton_beam
/AIHL/source/energy 10 MeV

# 5. biasing
/AIHL/biasing/enable true
/AIHL/biasing/xs/addRule proton protonInelastic
/AIHL/biasing/xs/setRuleFactor proton protonInelastic 3.0
/AIHL/biasing/xs/addRuleVolume proton protonInelastic Sensor

# 6. scoring
/AIHL/scoring/enable true
/AIHL/scoring/hits true
/AIHL/scoring/eventEdep true
/AIHL/scoring/edep true
/AIHL/scoring/setEdepHistogram bins=100 min=0 eV max=10 MeV

# 7. initialize and run
/run/initialize
/run/beamOn 100
```

更推荐将 physics、biasing、geometry 等会影响 Geant4 user initialization 的内容写入 main ini，让 `SimulationManager` 在创建 Geant4 initialization objects 前完成配置。macro 中再用于打印、轻量调整或运行。

## 15. 初始化前后命令使用规则

### 15.1 必须或强烈建议在 `/run/initialize` 前执行

- 材料定义和加载：`/AIHL/material/load`、`add*`、`clear`；
- 几何模板和主几何加载：`/AIHL/geometry/setTemplate`、`loadConfig`；
- 物理列表选择：`/AIHL/physics/setReferenceList`、`clearReferenceList`、`setEM`、`addModule`、`addExtraModule`；
- biasing physics hook：`/AIHL/physics/enableBiasing`；
- biasing 规则：`/AIHL/biasing/...`；
- MicroElec / ElectronCapture 相关 physics 配置；
- scoring 默认 scorer 和 histogram 配置建议在 run 前完成。

### 15.2 初始化后可配合重初始化使用

几何修改后：

```text
/AIHL/geometry/addBox ...
/AIHL/geometry/markModified
/run/reinitializeGeometry
```

physics 修改后：

```text
/AIHL/physics/setDefaultCut 0.1 mm
/run/physicsModified
```

source 和 scoring 开关通常可在下一次 `/run/beamOn` 前调整，但已经写出的文件和当前 run 内 scorer 状态不会自动回滚。

### 15.3 不建议运行中修改

- 已绑定的 biasing operators；
- 已构建 geometry 中使用的材料定义；
- 已创建 physics list 的 reference/manual 结构；
- output dir。当前没有 output messenger，运行中改 output 主要靠代码或重新启动。

## 16. 多线程模式注意事项

- `--threads N` 只在 Geant4 MT 构建中创建多 worker。
- `OutputManager` 不保证线程安全；设计倾向是每个 worker 写独立文件。
- 文件名默认带 `_t<threadId>` 后缀，如 `hits_t0.csv`、`event_edep_t0.csv`。
- 后处理可使用 `scripts/merge_outputs.py` 或 `mergeHistograms`。
- 当前 `SimulationManager::ConfigureOutputManager()` 设置主 `OutputManager` thread id 为 0；多线程下输出设计仍需按实际 worker 行为验证。

## 17. 常见错误与排查

### 17.1 Unknown command

如果 `/AIHL/app/...`、`/AIHL/detector/...` 或 `/AIHL/output/...` 报 unknown command：

- `/AIHL/app/...` 和 `/AIHL/detector/...` 源码存在但默认 executable 未注册；
- `/AIHL/output/...` 当前没有实现命令。

### 17.2 `--version` 报未知参数

当前 `main.cc` 没有实现 `--version`。使用 `--help` 查看可用参数。

### 17.3 `Material not found`

先加载材料：

```text
/AIHL/material/load config/materials/material.ini
```

确认 geometry 中使用的是 NIST 材料名或已注册别名。

### 17.4 `root node is not set` 或 geometry 构建失败

确认：

```text
/AIHL/geometry/setTemplate simple_box
/AIHL/geometry/loadConfig config/geometry/simple_box.ini
/AIHL/geometry/printTree
```

并检查几何配置是否满足对应模板必需字段。

### 17.5 biasing 没有 attach

确认：

- `[biasing]/enabled = true` 或 `/AIHL/biasing/enable true`；
- `[physics]/biasing = true` 或 `/AIHL/physics/enableBiasing true`；
- 至少有有效 process-level rule；
- rule 的 volume 名称存在于 `GeometryRegistry`，或者 geometry 中有 `bias = true` 的 volume；
- 修改 biasing 后需要重新初始化 physics/geometry 或重新启动。

### 17.6 没有 `hits_t0.csv`

`hits_t0.csv` 只有第一次写入 hit 时才创建。若 event edep 全为 0，或 sensitive volume 没有非零 `edep/ndep`，就不会生成。当前没有 macro 命令打开 zero-edep hit 输出。

### 17.7 Qt / 可视化命令无效

只有传 `--ui` 时 `main.cc` 才创建 `G4VisExecutive`。batch 模式下直接执行 `/vis/open ...` 可能无效或缺少 viewer。

## 18. 附录：全部 `/AIHL` 命令索引

### 18.1 默认 executable 已注册

```text
/AIHL/material/load
/AIHL/material/print
/AIHL/material/list
/AIHL/material/addNist
/AIHL/material/addIsotope
/AIHL/material/addElement
/AIHL/material/addElementFromIsotopes
/AIHL/material/addMaterial
/AIHL/material/buildAll
/AIHL/material/setLocked
/AIHL/material/clear

/AIHL/geometry/setTemplate
/AIHL/geometry/loadConfig
/AIHL/geometry/checkOverlaps
/AIHL/geometry/setDefaultWorldMaterial
/AIHL/geometry/addBox
/AIHL/geometry/addTubs
/AIHL/geometry/addVolume
/AIHL/geometry/removeUserVolume
/AIHL/geometry/print
/AIHL/geometry/printTree
/AIHL/geometry/clear
/AIHL/geometry/clearUserVolumes
/AIHL/geometry/listUserVolumes
/AIHL/geometry/preserveUserVolumesOnLoad
/AIHL/geometry/markModified

/AIHL/physics/setEM
/AIHL/physics/setReferenceList
/AIHL/physics/clearReferenceList
/AIHL/physics/setBaseReferenceList
/AIHL/physics/addModule
/AIHL/physics/removeModule
/AIHL/physics/clearModules
/AIHL/physics/addHadronic
/AIHL/physics/addOther
/AIHL/physics/addExtraModule
/AIHL/physics/removeExtraModule
/AIHL/physics/clearExtraModules
/AIHL/physics/setDefaultCut
/AIHL/physics/setCut
/AIHL/physics/setRegionCut
/AIHL/physics/enableBiasing
/AIHL/physics/enableMicroElec
/AIHL/physics/setMicroElecRegion
/AIHL/physics/enableElectronCapture
/AIHL/physics/setElectronCaptureThreshold
/AIHL/physics/verbose
/AIHL/physics/print
/AIHL/physics/listAvailableReferences
/AIHL/physics/listAvailableEMReferences

/AIHL/source/preset
/AIHL/source/particle
/AIHL/source/energy
/AIHL/source/point
/AIHL/source/direction
/AIHL/source/isotropic
/AIHL/source/planeBeam
/AIHL/source/print
/AIHL/source/reset

/AIHL/scoring/enable
/AIHL/scoring/hits
/AIHL/scoring/eventEdep
/AIHL/scoring/edep
/AIHL/scoring/let
/AIHL/scoring/dose
/AIHL/scoring/fluence
/AIHL/scoring/autoCreateScorers
/AIHL/scoring/setEdepHistogram
/AIHL/scoring/setWeightedEdepHistogram
/AIHL/scoring/verbose
/AIHL/scoring/print

/AIHL/biasing/enable
/AIHL/biasing/validate
/AIHL/biasing/print
/AIHL/biasing/clear
/AIHL/biasing/xs/addParticle
/AIHL/biasing/xs/addProcess
/AIHL/biasing/xs/addProcessForParticle
/AIHL/biasing/xs/addRule
/AIHL/biasing/xs/setFactor
/AIHL/biasing/xs/setRuleFactor
/AIHL/biasing/xs/onlyPrimary
/AIHL/biasing/xs/setRuleOnlyPrimary
/AIHL/biasing/xs/applyToSecondaries
/AIHL/biasing/xs/setRuleApplyToSecondaries
/AIHL/biasing/xs/setMinWeight
/AIHL/biasing/xs/setRuleMinWeight
/AIHL/biasing/xs/setMaxInteractions
/AIHL/biasing/xs/setRuleMaxInteractions
/AIHL/biasing/xs/addVolume
/AIHL/biasing/xs/addRuleVolume
/AIHL/biasing/xs/addVolumeForParticle
/AIHL/biasing/xs/printRules
```

### 18.2 源码存在但当前默认 executable 未注册

```text
/AIHL/app/setMainConfig
/AIHL/app/setOutputDir
/AIHL/app/setNumThreads
/AIHL/app/setSeed
/AIHL/app/setVerbose
/AIHL/app/setCheckOverlaps
/AIHL/app/printSummary

/AIHL/detector/enableSD
/AIHL/detector/setSDName
/AIHL/detector/printRegistry
/AIHL/detector/printSensitiveVolumes
/AIHL/detector/printBiasVolumes
/AIHL/detector/setVerbose
/AIHL/detector/printWorld
```

### 18.3 当前不存在

```text
/AIHL/output/...
```

当前 `OutputMessenger` 为空实现，没有 output macro 命令。
