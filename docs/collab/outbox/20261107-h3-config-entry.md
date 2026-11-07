# H3-3 配置与文档入口：交付回执

日期：2026-11-07
任务：固定清单 H3-3（m22956）。范围=现有 GUI/schema/配置生成与可用性一致、示例可复演、
更新数据契约与支持矩阵、不新增前端框架。H3-2 后端业务代码冻结未改。
证据：`out/collab/20261107-h3-3-config-entry/`（README、identities.json、product.diff、
tests.diff、verification 报告）。

## 改动清单

| 文件 | 改动 |
|---|---|
| `schema/config_schema.json` | 新增独立 `geometry_parallel_ini`（world/volume/grid 三节，external_only）；`[parallel_world]/name` 补 `gui.editable=external_only` |
| `schema/config_schema_coverage.json` | 生成物（+237 行） |
| `include/Config/ConfigSchemaTable.hh` | 生成物（+21 行，需重建） |
| `gui/g4usim_gui/core/config_schema_data.py` | 生成物（+212 行） |
| `docs/功能支持矩阵.md` | GENERATED 段新增平行几何三节；顶部 H3 状态行改为 H3-2 已验收/H3-3 入口 |
| `gui/g4usim_gui/core/parallel_world_scope.py` | 新增只读视图：解析外部主 INI 的 `[parallel_world]`、按主 INI 目录解析几何、状态行、诊断与拒绝组合；生成输入模式下已启用的段报 `parallel_world_generated_mode`（警告，不阻断）并指引切回 External（+约 270 行） |
| `gui/g4usim_gui/core/project_diagnostics.py` | 把 scope issue 转为 Project 诊断错误 |
| `gui/g4usim_gui/widgets/project_page.py` | Project 页状态追加平行世界行与「只读/GUI 只画质量几何」提示，状态区最小高度 150 |
| `gui/g4usim_gui/core/run_editor_import.py` | editable 导入遇 `[parallel_world]` 明确失败并指向外部配置入口（不静默丢弃） |
| `gui/g4usim_gui/core/experiment_bundle.py` | `_ROLES` 增 `parallel_geometry`；`geometry_config` 按主 INI 目录解析并进入闭包；`ref_main_relative`（bundle 内写同级 basename） |
| `gui/g4usim_gui/core/i18n.py` | 新增状态/诊断/提示中文条目 |
| `docs/并行世界计分.md` | 状态行更新；新增 §11（GUI/schema 入口、K1 闭包与身份、示例、范围声明） |
| `examples/07_parallel_world_box/` | 新增完整闭包 6 文件（main/materials/geometry/parallel/macro/README） |
| `examples/08_parallel_world_grid/` | 同上，4×4×1 规则网格 |
| `gui/smoke_tests/smoke_parallel_world_entry.py` | 新增回归（Qt 状态/诊断/保存不丢段/editable 拒绝/生成模式不可承载诊断/K1 闭包/身份/20 事件真实后端） |
| `scripts/run_m0_tests.py` | 注册 `gui_parallel_world_entry`（integration，qt+exe） |

## 命令与真实结果

- 生成器：`python scripts/generate_config_schema.py`（重跑写入上表四个生成物）。
- 重建：`env -u no_proxy -u http_proxy -u https_proxy -u ALL_PROXY cmake --build build_vs2026 --config Release --target G4UniversalSim parallelScoringCheck` 成功（仅既有 C4996 警告）。
- 受影响用例（`out/collab/20261107-h3-3-config-entry/verification/20261107-024554-34286906/report.json`，
  SHA-256 `678dd623…`）：config_schema 309 断言、gui_parallel_world_entry 41、parallel_world 2411、
  parallel_scoring_component 8、gui_project_io 6、gui_project_import_projection 393、
  gui_project_snapshot_restore 62、gui_main_window 51；**8 pass / 0 fail / 0 skip，
  3281 assertions**，`cases_with_zero_assertions=[]`。
- `python -B scripts/check_doc_links.py`：1463 链接 / 453 文件 / 0 断链。
- 示例真实运行（本机 MSVC，1 线程）：box 例 200 事件 exit 0，dose 行
  `/ScoringWorld#0/Slab#0`、`mass_kg=0.0008`、`weighted_dose_Gy≈3.99e-07`、`n_events=200`；
  grid 例 exit 0、16 单元稀疏 4 行（束流中央四格）、每格 `5e-05 kg`、
  `parallel_world_volume_count=16`、`total_mass_kg=0.0008`。
- K1 闭环（在 smoke 内断言）：bundle 资源含 `parallel_geometry`；导出主 INI 的
  `geometry_config` 改写为同级 basename 且目标存在；`load_bundle` 可恢复；修改平行几何
  字节后 `capture_identity(...).fingerprint` 变化。

## 验证记录说明

最终候选只以 `verification/20261107-024554-34286906/report.json` 为准（8 pass /
3281 assertions，SHA-256 `678dd623…`）。定稿前因把「生成输入模式不可承载」的诊断由 error
降为 warning 而重跑过两次，中间报告（3276、3280 assertions）在生成最终身份前已被清理，
**不补造，也不作为验收依据**；其命令/日志结构与本报告相同，差异仅为严重级别与断言计数。
之后不再整体清理 `verification/`，runner 自带的时间-UUID 子目录并存保留。

## 身份

- HEAD `83c0b1399584031f82d7d1fe38443ed2d1713e4f`，`git_dirty=true`（任务前已有
  `docs/ROADMAP.md`、`docs/collab/CURRENT-SUPERVISION.md` 等 supervisor 修改未触碰；
  H3-2 产品改动仍未提交）。
- 后端 exe SHA-256 `9daf3d22…`、组件 `parallelScoringCheck.exe` `8e015327…`
  （完整值见 `out/collab/20261107-h3-3-config-entry/identities.json`）；
  嵌入 source fingerprint `9523b9874ebb813cca321184a10269db4c76f4a7b9cbbdcd96e262a85bab6379`，
  与重建后 `--capabilities` 一致；MSVC 19.51 / Release / Geant4 11.3.2 MT。
- `product.diff` SHA-256 `c54c7314…`、`tests.diff` SHA-256 `43ddb3cf…`；
  差异基线为主审保存的 `out/collab/h3-independent-r4/source/`（不在快照中的 GUI 文件以
  `git show HEAD:<path>` 为基线）。

## 未覆盖 / 待裁定

1. GUI 只显示平行世界状态与诊断，不编辑 `[parallel_world]`/平行几何；3D 预览只画质量几何
   （符合 external_only 策略与本任务「不新增前端框架」要求）。
2. 未执行 H3-4 固定统计基准；未跑全量物理矩阵；未做 H3-5 双平台正式回归与云 CI。
3. 保存/恢复项目本身只保存路径，已启用段不会丢失；生成模式无 `[parallel_world]` 编辑器，
   本轮以 editable 导入明确拒绝、生成模式诊断（`parallel_world_generated_mode` 警告）+ 外部
   配置入口指引覆盖，不静默改写、不阻断生成模式运行。
4. 示例为演示用（20 mm 薄层、10 MeV 质子、200 事件），不构成物理正确性验收。
5. Linux：仅文档命令，未在本轮重跑真实 Linux 后端。

## 复现

```powershell
python scripts/generate_config_schema.py
python -B scripts/run_m0_tests.py --profile all --case config_schema ^
  --case gui_parallel_world_entry --case parallel_world ^
  --case parallel_scoring_component --case gui_project_io ^
  --case gui_project_import_projection --case gui_project_snapshot_restore ^
  --case gui_main_window --fail-on-skip ^
  --report-root out/collab/20261107-h3-3-config-entry/verification
python -B scripts/check_doc_links.py
# 示例：在 examples/07_parallel_world_box 下
G4UniversalSim.exe --config main.ini --macro run.mac --output output
```

完
