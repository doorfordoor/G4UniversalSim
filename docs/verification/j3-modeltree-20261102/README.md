# J3 第六阶段：3D 模型树与体积筛选（2026-11-02）

状态：**作者交付，待独立验收**。J3 未关闭。

## 本阶段交付

新增 `gui/g4usim_gui/preview3d/model_tree.py`：从编辑器几何文档（`GeometryDocument`）构建纯数据模型树
（`ModelNode` / `build_model_tree` / `flatten`），覆盖 hierarchical 体积父子链、simple_box、layered_device；
禁用行跳过，父缺失挂根，父链成环不挂死且该行不参与选中。模型自带 `world` 行时把它合并为树根。

`PyVistaPreviewWidget` 的图例列新增「Model tree」：

- 树节点按体积名与 3D 视图双向联动（点树 → `select_volume`；3D 点选 → 树定位）；
- 「Filter volumes」按名称过滤并自动展开命中的父链；
- 双击节点 = 选中 + 隔离；双击根 = 全部显示；
- 右键菜单：在 3D 视图中选中 / 隔离 / 隐藏 / 全部显示；
- 打开「3D Preview」标签自动绘制当前几何（`_on_workspace_tab_changed`），不再必须先点 Refresh。

## 证据

- 自动化：`docs/verification/j3-modeltree-20261102/report.json`（GUI profile，7 例，1965 断言）：
  `gui_model_tree`、`gui_3d_view`、`gui_config_editors`、`gui_workspace_layout`、`gui_main_window`、
  `gui_command_palette`、`gui_k1_panel`。逐例日志在 `logs/`。
- 作者侧额外实测（Windows 平台、真实字体）：`gui/.venv/Scripts/python.exe -B tools/test_assert_probe.py
  gui/smoke_tests/smoke_model_tree.py` → 27 断言（含 widget 联动；`QT_QPA_PLATFORM=windows`）。
- 截图（`screens/`）：`tree-paper.png`、`tree-midnight.png`，纸墨/午夜蓝皮肤下配置页的 3D 停靠面板。
  截图由作者侧脚本生成，非独立验收。

## 复现

```bash
export PATH="/d/msys64/ucrt64/bin:$PATH"
gui/.venv/Scripts/python.exe -B scripts/run_m0_tests.py --profile gui   --case gui_model_tree --case gui_3d_view --case gui_config_editors   --case gui_workspace_layout --case gui_main_window --case gui_command_palette   --case gui_k1_panel --report-root out/verification/j3-modeltree
python -B scripts/check_report_evidence.py --report-root docs/verification/j3-modeltree-20261102
```

Windows 平台额外的 widget 联动实测：`QT_QPA_PLATFORM=windows gui/.venv/Scripts/python.exe -B
tools/test_assert_probe.py gui/smoke_tests/smoke_model_tree.py`（离屏 runner 下 pyvista 不可用，widget 部分打印 SKIP）。

## 不证明什么

- 不构成独立验收：截图与交互由作者本人操作，未经第二人复验。
- 离屏 runner 中 `gui_model_tree` 只覆盖纯函数（21 断言）；widget 联动由作者侧 Windows 平台直接运行覆盖（27 断言）。
- 未覆盖：Linux 真实桌面实窗、125%/150% 缩放下的模型树可读性、超大几何（数百体积）下的树构建耗时。
- 模型树只反映编辑器配置的父子关系；它不校验几何重叠、不影响 Geant4 内核，也不替代 3D 视图的几何证据。
