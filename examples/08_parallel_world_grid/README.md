# H3 平行世界计分：规则 box 网格示例

本示例在质量几何的水薄层上叠加一个**平行世界规则网格**：质量几何保持原样（薄层
`sensitive = false`），平行世界声明 `[grid.SlabGrid]`，把 20×20×2 mm 区域切成
`4×4×1 = 16` 个 5×5×2 mm 计分单元，只有平行单元计分。

## 运行

Windows PowerShell（在本目录执行）：

```powershell
& "C:\path\to\G4UniversalSim.exe" --config main.ini --macro run.mac --output output
```

Linux：

```bash
/path/to/G4UniversalSim --config main.ini --macro run.mac --output output
```

GUI 运行方式与 `examples/07_parallel_world_box` 相同：Project 页设为
`Use external files` 并选择 `main.ini` / `run.mac`；GUI 只读取并诊断外部主 INI，
不编辑 `[parallel_world]`，3D 预览只绘制质量几何。

## 文件

| 文件 | 作用 |
|---|---|
| `main.ini` | 外部主配置：材料、质量几何、物理、dose+fluence、源、`[parallel_world]` |
| `materials.ini` | 材料别名：`galactic → G4_Galactic`、`water → G4_WATER` |
| `geometry.ini` | 质量几何：100 mm G4_Galactic 世界 + 20×20×2 mm 水薄层（`sensitive = false`） |
| `parallel.ini` | 平行计分几何：`[grid.SlabGrid]`，`size = 20 mm, 20 mm, 2 mm`、`bins = 4, 4, 1` |
| `run.mac` | `/run/initialize` 与 `/run/beamOn 200` |

`parallel.ini` 的 `geometry_config` 相对主 INI 目录解析。网格单元命名
`SlabGrid_<ix>_<iy>_<iz>`，ix 变化最快；单元中心 = 区域中心 + 每轴
`(i + 0.5)·d − size/2`；每单元体积 5×5×2 = 50 mm³、水质量 `5e-05 kg`。

## 期望输出（200 事件，1 线程）

- `run_summary.txt`：`parallel_world_enabled = true`、`parallel_world_volume_count = 16`、
  `parallel_world_total_mass_kg ≈ 0.0008`、`status = completed`、完成事件 200。
- `dose_volume_summary_t0.csv`：**稀疏**——点源束流打在原点附近，只有中央 4 个单元
  （`SlabGrid_1_1_0`、`SlabGrid_1_2_0`、`SlabGrid_2_1_0`、`SlabGrid_2_2_0`）有贡献行，
  其余 12 个单元不写 0 行；每行 `mass_kg = 5e-05`、`volume_path = /ScoringWorld#0/<unit>#0`、
  `n_events = 200`。
- `fluence_volume_summary_t0.csv`：同样只有这 4 个单元，`volume_mm3 = 50`。
- `effective_config_*.json` 中 `parallel_world_volume_count = 16`、每个单元都有
  `material_matches_mass_world = true`（16 个单元都完全落在水薄层内部，材料对应可证明）。

单位：能量 MeV，长度 mm，剂量 Gy，注量 mm⁻²，质量 kg。体积路径是完整 touchable
含 `#copy`（根为平行世界名 `ScoringWorld`）。

## 稀疏输出与多 run/线程

- 构造收据（`parallel_world_volume_count`、`effective_config_*.json`）证明 16 个单元
  全部创建；CSV 只输出有命中的单元，不伪造 16 行 0。
- 多线程时每个 worker 写自己的 `_tN` 文件；同一进程第 2 个 `/run/beamOn` 起文件名
  带 `_rR`。跨 worker 的分母（`n_events`）是本线程本轮完成事件数，合并规则见
  `docs/并行世界计分.md`。
- 网格上限：`nx·ny·nz ≤ 4096`；超出、非法 bins、非 box 或声明名/派生名冲突都会在
  构造 Geant4 几何前拒绝。

## 支持范围与拒绝

- v1 只支持 box 体积与规则 box 网格；不支持嵌套体积、旋转/placement、
  布尔/装配/GDML/STL、region/cuts/visual/bias 键。
- 与平行世界计分同时使用时后端拒绝：`[output] format = root`、`[biasing] enabled = true`、
  非空 `[field]`、`[scoring.mesh.*]`、LET 与位移损伤计分。

配置语法、材料 true/unknown 口径、两阶段校验与输出契约见 `docs/并行世界计分.md`，
回归见 `scripts/test_parallel_world.py`。
