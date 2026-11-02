# J3 第四阶段：按当前页面适配工作区（作者交付，未验收）

状态：**作者交付，待独立审查**。J3 未关闭；本目录只证明下列用例在本机通过，以及“适配”动作按预期切换布局。

## 改了什么

工作区预设（`Configuration editors` / `3D view` / `Results view` / `Execution logs` 四个停靠面板）原先只能从
View → Workspace layout 手动切换，用户从配置页跳到运行页或结果页时，配置面板仍占 700px 宽，运行页只能挤在
中心 ~330px 里，按钮和 “Unobserved” 行被裁。现在：

- `WorkspaceLayout.preset_for_page(index)`：页面 0–4（Start/Project/Configuration/Scenario/Effective Configuration）→
  `configuration`，页面 5（Run Console）→ `running`，页面 6–8（Results/Run History/Parameter Scans）→ `analysis`。
- `WorkspaceLayout.focus_current_page()`：应用该预设并 `reveal_current()`，只改停靠面板，不改页面内容、项目状态或运行状态。
- View → Workspace layout 新增 **Fit workspace to current page**（`Ctrl+Shift+L`，objectName `workspaceFocusPage`）；
  命令面板新增同名 Action 条目（Actions 7→8）。
- 手动选择预设、隐藏面板仍然有效，本动作不会自动触发（避免覆盖用户自定义布局）。

## 证据

- GUI 用例 7/7 通过、399 断言（报告 `out/verification/j3-focus/20261102-231056-4659a9b9/report.json` 的副本）：
  `gui_command_palette` 42、`gui_workspace_layout` 149、`gui_main_window` 51、`gui_theme_response` 55、
  `gui_j1_appearance` 29、`gui_3d_view` 35、`gui_config_editors` 38。
- 源码指纹 `9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a`；测试内容指纹 `2742617507aadf33503be1931cc607a8908156de59cab03e3bfc4ff5d656e296`；探针 `settrace_assert_lines_v3`；日志摘要 `sha256_raw_bytes_lf_v2`；
  `python -B scripts/check_report_evidence.py --report-root docs/verification/j3-focus-20261102` 通过。
- 复现：`gui/.venv/Scripts/python.exe -B scripts/run_m0_tests.py --profile gui --case gui_command_palette
  --case gui_workspace_layout --case gui_main_window --case gui_theme_response --case gui_j1_appearance
  --case gui_3d_view --case gui_config_editors --report-root out/verification/j3-focus`

## 不证明什么

- 没有做真实鼠标点击的实窗操作录像，也没有第二人独立复验；
- 未覆盖 125%/150% DPI、Linux 桌面、浮动/隐藏面板组合下的同样 4 类区域辨认；
- 只证明“按页面切预设”这个动作的映射与通过性，不证明工作区对所有页面都最优。
