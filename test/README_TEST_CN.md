# G4UniversalSim 端到端测试套件
本文件夹包含适用于当前 G4UniversalSim 程序的独立端到端测试输入。这些测试**无需依赖** `config/`、`macros/`、`docs/` 目录以及项目根目录下的任何示例文件。

## 目录结构
- `main_layered_device.ini`：分层设备运行的主配置文件。
- `main_hierarchical.ini`：层级结构运行的主配置文件。
- `materials/test_materials.ini`：材料别名定义及一种简易自定义材料配置。
- `geometry/layered_device_test.ini`：`LayeredDeviceTemplate`（分层设备模板）几何结构配置。
- `geometry/hierarchical_test.ini`：`HierarchicalVolumeTemplate`（层级体模板）几何结构配置。
- `biasing/*.ini`：偏置配置文件，内容与主配置文件保持一致，用于文档留存与复用。
- `macros/*.mac`：完整命令驱动式宏测试文件。
- `output/*/.gitkeep`：输出目录；脚本会将 `run.log` 日志写入此处。
- `scripts/run_tests.ps1`、`run_tests.bat`、`run_tests.sh`：便捷运行脚本。

## 运行方式
在代码仓库根目录执行：

```powershell
.\test\scripts\run_tests.ps1 -Executable .\build\Release\G4UniversalSim.exe
```

若使用 Visual Studio 2026 预设编译，脚本可自动识别路径：

```powershell
.\build_vs2026\Release\G4UniversalSim.exe
```

或使用：

```cmd
test\scripts\run_tests.bat build\Release\G4UniversalSim.exe
```

在 Linux/macOS 类终端环境：

```bash
bash test/scripts/run_tests.sh ./build/G4UniversalSim
```

每次运行会加载对应的主 ini 配置与宏文件，并将控制台日志输出至以下路径：
- `test/output/layered_device/run.log`
- `test/output/hierarchical/run.log`

主 ini 配置文件中刻意内置了与宏文件所调用**一致**的物理过程、偏置设置、粒子源及计数统计状态。在当前程序启动流程中，Geant4 用户初始化对象会在宏文件执行前完成创建，因此通过配置文件初始化是物理列表与通用偏置注册的可靠方式。宏文件仍会调用真实信使命令，在执行 `/run/initialize` 初始化前完成相关命令接口的覆盖与打印输出。

## 已验证的接口规范
测试文件基于现有源码实现编写，支持如下接口规则：
- 材料配置 ini 支持写法：`[Alias] material = G4_*`、`[element.NAME]` 元素定义、`[material.NAME]` 材料定义。
- 几何相关命令支持：`/AIHL/geometry/setTemplate`、`/AIHL/geometry/loadConfig`、`/AIHL/geometry/checkOverlaps`、`/AIHL/geometry/print`、`/AIHL/geometry/printTree`。
- `layered_device` 分层设备配置采用 `[world]`、`[layers]`、`[layer.NAME]` 配置段；支持参数：厚度、xy尺寸、材料、仅`auto_stack=false`时可设位置、旋转、灵敏体、偏置、区域、生成截断、可视化配置 `vis.*`。
- `hierarchical` 层级结构配置采用通用 `[world]` 与 `[volume.NAME]` 配置段；支持参数：父级体、几何体形状、尺寸、参数集、材料、位置、旋转、灵敏体、偏置、区域、生成截断、可视化配置 `vis.*`，未知配置键将作为用户自定义属性保留。
- `copyNo` 副本编号仅可通过 `VolumeBuilder` 读取通用几何用户属性实现配置；因此仅在层级结构测试中使用，分层设备测试暂不支持。
- 物理过程命令支持：`/AIHL/physics/setReferenceList`、`/AIHL/physics/setDefaultCut`、`/AIHL/physics/setCut`、`/AIHL/physics/setRegionCut`、`/AIHL/physics/enableBiasing`、`/AIHL/physics/verbose`、`/AIHL/physics/print`。
- 粒子源命令支持：`/AIHL/source/preset`、`/AIHL/source/particle`、`/AIHL/source/energy`、`/AIHL/source/planeBeam`、`/AIHL/source/print`。
- 计数统计命令支持：`/AIHL/scoring/enable`、击中计数、事件能量沉积、能量沉积、线性能量转移、剂量、通量、自动创建统计器、直方图相关命令、日志详细等级、信息打印。
- 偏置宏命令目前支持通过 `/AIHL/biasing/xs/...` 实现截面偏置配置。

## 当前已知功能限制
- `OutputMessenger` 输出信使暂未实现 `/AIHL/output/...` 系列命令，因此输出目录需通过主 ini 配置文件及运行脚本 `--output` 参数指定。
- 偏置功能已支持 `[biasing]`、`[biasing.xs]` 配置段解析，但暂无独立宏命令可加载外部偏置 ini 文件；因此偏置配置文件内容直接整合至两份主配置中，并在宏文件中展开为实际可执行命令。
- 重要性偏置、权重窗口偏置、分裂/俄罗斯轮盘抽样，在当前版本中暂无可用信使命令及 ini 配置解析支持，仅做文档说明，暂不支持配置启用。
- `LayeredDeviceTemplate` 分层设备模板不识别自定义元数据键与副本编号，因此分层几何配置文件刻意规避了这类暂不支持的元数据及副本编号字段。
- 通用层级结构解析器支持自定义用户属性，因此可在其中使用 `metadata.role`、`purpose`、`copyNo` 等自定义字段。
