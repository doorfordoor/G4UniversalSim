# J3 第五阶段：导航时收起旧停靠页与结果页分析视图

- 状态：作者交付，等待独立审查；J3 未关闭。
- 报告：`report.json`（`schema=G4UniversalSimM0TestReport`、`version=2`、`profile=gui`、7 个用例、2022 条断言、`probe=settrace_assert_lines_v3`、`digest=sha256_raw_bytes_lf_v2`），逐用例日志在 `logs/`。
- 复现：`python -B scripts/check_report_evidence.py --report-root docs/verification/j3-analysis-docks-20261102`；用例本身用 `python -B scripts/run_m0_tests.py --profile gui --case gui_workspace_layout --case gui_main_window --case gui_command_palette --case gui_3d_view --case gui_config_editors --case gui_k1_panel --case gui_k1_history_scope --report-root <tmp>`。

## 这一阶段修了什么

1. `WorkspacePageStack.reveal_current()` 现在会在离开某个停靠页时隐藏该页的 dock。此前配置编辑器一旦在配置页被展示，就会在 Run Console、Results、Run History、Parameter Scans 页继续占据约 620–700 px，把中心内容压成不可读的窄条。
2. 导航到 Results 页时调用 `WorkspaceLayout.focus_analysis_view()`：收起 3D 预览与 AI 面板、显示日志 dock，让结果表与分析读数占满可用宽度。

## 边界与已知残留

- Results 页的停靠组合（结果视图在上、日志在下）仍不是最理想的最终布局，后续若要彻底重做需要改 workspace 面板归属，不在本阶段内。
- 本阶段只验证了脚本化 GUI 用例与离屏/实窗截图，未做 125%/150% 缩放、Linux 真实桌面与性能基线。
- 这些用例断言的是“导航后哪些 dock 可见”，不证明用户自有布局在所有显示器配置下都合理。

## 不证明什么

- 不证明全部停靠/浮动/恢复路径已闭环。
- 不证明 J3 的对比度、跨平台实窗与性能验收已通过。
