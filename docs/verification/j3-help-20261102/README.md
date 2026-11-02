# J3 第七阶段：帮助菜单、快捷键表与关于对话框（2026-11-02）

状态：**作者交付，待独立验收**。J3 未关闭。

## 本阶段交付（可用性增强）

- 新增 **Help 菜单**：「Keyboard shortcuts」（F1）与「About G4UniversalSim」。
- 快捷键表（`ShellMixin.build_shortcut_dialog()` / `show_shortcuts()`）按 `shortcut_rows()` 稳定顺序列出：
  F1 帮助、Ctrl+K 命令面板、Ctrl+Shift+L 按页面适配工作区、Ctrl+Alt+1…9 九个页面、F6 / Shift+F6 区域焦点、
  Ctrl+Shift+N 空白仿真、Ctrl+N 新建向导、Ctrl+O/Ctrl+S/Ctrl+Shift+S 项目读写、Ctrl+Alt+E/I/O 环境与配置包。
  表格用滚动区，中英文即时切换，浅色/深色主题均可读。
- 关于对话框（`about_text()` / `show_about()`）显示 GUI 版本、PySide6 与 Qt 版本、应用根目录、后端可执行文件路径；
  便于用户与审查者在报告问题时提供环境事实。
- 侧栏导航按钮补 tooltip（“打开 <页面>（Ctrl+Alt+N）”），与快捷键表、无障碍描述一致。

## 证据

- 自动化：`docs/verification/j3-help-20261102/report.json`（GUI profile，5 例，211 断言）：
  `gui_help_menu`、`gui_main_window`、`gui_command_palette`、`gui_theme_response`、`gui_j1_appearance`；日志在 `logs/`。
- 截图（`screens/`）：`shortcuts-paper.png`、`shortcuts-midnight.png`（作者侧实窗，`QT_QPA_PLATFORM=windows`；
  截图前未做独立复核）。

## 复现

```bash
export PATH="/d/msys64/ucrt64/bin:$PATH"
gui/.venv/Scripts/python.exe -B scripts/run_m0_tests.py --profile gui   --case gui_help_menu --case gui_main_window --case gui_command_palette   --case gui_theme_response --case gui_j1_appearance --report-root out/verification/j3-help-gui
python -B scripts/check_report_evidence.py --report-root docs/verification/j3-help-20261102
```

## 不证明什么

- 不构成独立验收：快捷键表与关于文本仅由作者检查。
- 快捷键表是**文档**，不证明每个快捷键在所有平台/输入法下可用（已有各自用例覆盖功能，未覆盖组合键冲突）。
- 未覆盖 Linux 实际桌面与 150% 缩放下的对话框可读性；J3 其余未闭合项（150% 最小宽度、切换性能基线、Linux 实窗、独立复验）不变。
