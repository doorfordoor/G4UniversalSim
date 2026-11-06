# H3 平行世界计分：单 box 示例

本示例用**同一块水薄层**演示平行世界计分：质量几何中的薄层不设敏感体，另一个
平行世界（ghost world）里声明同尺寸的计分体积，只有平行体积计分。两者材料一致，
因此材料对应关系可证明，`material_matches_mass_world = true`。

## 运行

需要已安装 Geant4 数据与后端可执行文件（Windows 安装包、源码构建或 Linux 构建均可）。

Windows PowerShell（在本目录执行）：

```powershell
& "C:\path\to\G4UniversalSim.exe" --config main.ini --macro run.mac --output output
```

Linux：

```bash
/path/to/G4UniversalSim --config main.ini --macro run.mac --output output
```

也可以从 GUI 运行：Project 页把 `Current Run Defaults` 设为 `Use external files`，
选择本目录的 `main.ini` 与 `run.mac`，Project 页状态会显示
`Parallel world: enabled, name ScoringWorld; ghost geometry ...\parallel.ini`。
GUI 只读取并诊断外部主 INI，不编辑 `[parallel_world]`，3D 预览只绘制质量几何。

## 文件

| 文件 | 作用 |
|---|---|
| `main.ini` | 外部主配置：材料文件、质量几何、物理、dose+fluence、源、`[parallel_world]` |
| `materials.ini` | 材料别名：`galactic → G4_Galactic`、`water → G4_WATER` |
| `geometry.ini` | 质量几何（hierarchical）：100 mm G4_Galactic 世界 + 20×20×2 mm 水薄层（`sensitive = false`） |
| `parallel.ini` | 平行计分几何（独立文件）：同尺寸水 box，`sensitive = true` |
| `run.mac` | `/run/initialize` 与 `/run/beamOn 200` |

`main.ini` 中的 `geometry_config` **相对主 INI 目录**解析（与 `[materials] file`、
`[geometry] config` 相对进程工作目录的规则不同）。

## 期望输出（200 事件）

输出文件（`--output output`）：

- `run_summary.txt`：`status = completed`、`run_0_completed_events = 200`，并含
  `parallel_world_enabled = true`、`parallel_world_name = ScoringWorld`、
  `parallel_world_volume_count = 1`、`parallel_world_total_mass_kg ≈ 0.0008`、
  `parallel_world_geometry_sha256`、`parallel_world_physics_constructor = G4ParallelWorldPhysics`、
  `parallel_world_process = G4ParallelWorldProcess`、`parallel_world_step_source = ghost_step`、
  `parallel_world_dose_normalization = declared_material_reference_mass`。
- `dose_volume_summary_t0.csv`：一行 `/ScoringWorld#0/Slab#0`，`mass_kg = 0.0008`，
  `n_events = 200`，`weighted_dose_Gy` 约 `4e-07`（10 MeV 质子 200 事件）。
- `fluence_volume_summary_t0.csv`：一行同一路径，`volume_mm3 = 800`，
  `weighted_fluence_mm-2` 非零。
- `scorer_statistics.csv`、`run_metadata.json`、`effective_config_*.json`。

单位：能量 MeV，长度 mm，剂量 Gy，注量 mm⁻²，质量 kg（CSV 列名带 `_MeV`/`_mm`）。
体积路径是完整 touchable 含 `#copy` 后缀：`/ScoringWorld#0/Slab#0`（根为平行世界名）。

## 稀疏输出与多 run/线程

- 只输出有贡献的体积行；没有命中的体积不会写 0 行（构造收据里的
  `parallel_world_volume_count` 才是声明体积/单元总数）。本示例只有 1 个体积。
- 多线程时每个 worker 写自己的 `_tN` 文件（如 `dose_volume_summary_t0.csv`、
  `dose_volume_summary_t1.csv`），行按 worker 分开。
- 同一进程多次 `/run/beamOn` 时第二轮起文件名带 `_rR`（如 `_t0_r1`）。

## 支持范围与拒绝

- v1 只支持 box 体积与规则 box 网格（`[grid.<name>]`，`nx·ny·nz ≤ 4096`）。
- 与平行世界计分同时使用时，后端拒绝：`[output] format = root`、`[biasing] enabled = true`、
  非空 `[field]`、`[scoring.mesh.*]`、LET 与位移损伤计分。
- 平行几何文件是闭合 schema：未知 section/key、重复声明、非法名字、内部体积交叠
  （面/边/点接触允许）都会在构造 Geant4 几何前拒绝。

配置语法、校验、材料 true/unknown 口径与输出契约见 `docs/并行世界计分.md`，
回归见 `scripts/test_parallel_world.py`。
