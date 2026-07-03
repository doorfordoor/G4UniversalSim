# G4UniversalSim Agent 维护说明

整理日期：2026-07-03。本文件面向 Codex 这类代码 Agent，用于后续修改时快速找到事实来源。普通用户请优先读 `docs/中文使用手册.md`、`docs/中文几何配置说明.md` 和 `gui/docs/中文快速使用说明.md`。

## 1. 当前文档结构

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

- CLI 没有 `--version`。无 `--macro` 且无 `--ui` 时只打印帮助并退出。
- `gdml` 模板目前只是占位。`VolumeBuilder` 遇到 GDML 占位属性会抛未实现错误。
- STL 导入未实现。
- 后端 `VolumeBuilder` 支持 `box`、`tubs`、`sphere`、`orb`、`cone`、`trd`、`trap`。
- GUI 层级/布尔几何校验目前只把 `box`、`tubs`、`sphere`、`orb`、`cone` 放在白名单里，且稳定预览主要是 `box` 和 `tubs`。后端已支持但 GUI 未放开的形状不要在 GUI 文档里写成 GUI 可编辑。
- `simple_box` 的 target 虽读取 `shape`，但 GUI writer 固定写 `shape = box`。
- `volume_fraction` 材料只支持材料组件。直接用元素作为体积分数组分会被后端拒绝。
- 多线程输出由 worker 写 `_tN` 文件，后端不自动合并。GUI 只是调用合并工具。
- `LETScorer` 只有轻量直方图输出条件；`DoseScorer`、`FluenceScorer` 当前是 no-op。
- process-level XS biasing 是推荐路径。旧 `[biasing.xs]` 和部分 `/AIHL/biasing/xs/...` 命令仍兼容但会提示 legacy。
- GUI 的 source rectangle、annulus、cone、cosine、focused 等模式属于预览或实验，当前 main.ini writer 会阻止不被后端支持的模式生成。
- GUI 项目 JSON schema 当前是 `G4UniversalSimProject`，version 为 5。
- GUI 生成包不会覆盖原始 `materials.ini` 或 `geometry.ini`，只写入 run package。

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
