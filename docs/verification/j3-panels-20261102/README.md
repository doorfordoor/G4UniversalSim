# J3 第三阶段证据：工作区面板与外壳细节（2026-11-02，作者交付，未独立审查）

状态：**作者交付，等待独立审查；J3 阶段未关闭，不能据此宣称 J3 验收完成。**

## 本阶段改了什么

1. **3D 视图面板不再溢出裁剪**（`gui/g4usim_gui/preview3d/pyvista_preview_widget.py`）：视点按钮行与“正交/世界”
   投影开关拆成两行网格；材料/粒子图例宽度 190→168；剖切滑块最小宽 110→80。此前右侧 dock 变窄时
   “World / Show Labels / Load Tracks…” 会被窗口右缘裁掉，控件不可点。
2. **3D 预览标签页选项分行**（`gui/g4usim_gui/widgets/config/preview3d.py`）：自动后端几何、Show Source 一行，
   Show Labels 一行；窄 dock 下不再压掉最后一个复选框。
3. **配置编辑器停靠面板宽度**（`gui/g4usim_gui/window/workspace_layout.py`）：setup 面板最小宽 260→300，
   分栏 300/680→330/650；路径输入行右侧 “Browse” 按钮不再被裁。
4. **状态栏恢复提示单行化**（`gui/g4usim_gui/window/recovery.py`）：`Recovery copy: …` 不再折成两行后被窗口右缘裁切
   （最大宽 320，完整文本在 tooltip）。
5. **配置标签更紧凑**（`gui/g4usim_gui/core/theme.py`）：`QTabBar::tab` padding 8/14→7/11、右边距 4→3，
   六个配置标签不需要滚动按钮压住标签文字。
6. **键盘焦点可见**（同文件）：`QToolButton:focus` 使用 `focus_ring` 描边、侧栏导航 focus 使用 `sidebar_hover`
   背景；这是 J3 验收表中“焦点与关键控件边界可辨识”的最低要求，尚未做对比度实测。
7. **撤消/重做图示化**（`gui/g4usim_gui/core/icons.py` 的 `undo`/`redo`、`gui/g4usim_gui/window/shell.py` 的
   `_refresh_icons`、`gui/g4usim_gui/window/transactions.py`）：编辑历史工具栏改用主题色 SVG 图标，随外观切换重绘。

截图脚本 `out/skin_shots2.py` 与截图目录属于临时验证工具，不随提交入库（`out/` 被忽略）。

## 证据

| 项目 | 值 |
| --- | --- |
| 测试平台 | `python -B scripts/run_m0_tests.py --profile gui --report-root out/verification/j3-panels-gui2` |
| 报告 | `out/verification/j3-panels-gui2/20261102-225535-090e83e1/report.json`（副本 `report.json`） |
| 用例 | **72 pass / 0 fail / 0 skip**（profile gui） |
| 已执行断言 | **10227**（72 例全部有断言，0 个零断言用例） |
| 证据门禁 | `python -B scripts/check_report_evidence.py --report-root out/verification/j3-panels-gui2` 通过（version 2、probe `settrace_assert_lines_v3`、digest `sha256_raw_bytes_lf_v2`） |
| 源码指纹 | `9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a` |
| 测试内容指纹 | `e8c6272783613a79d4d976efcaa570e597c17fc181f9ae7b52443e38f02a09f7` |
| 后端可执行文件 | `build_vs2026/Release/G4UniversalSim.exe`，2466304 字节，SHA-256 `18d58fab815b91e96c6c4b2c94704518d42885f163b54803072164a8a4f9c837` |
| 日志 | `logs/` 下 72 个用例日志，摘要与 `report.json` 逐项一致 |

定向复跑（改布局时先跑的一轮）：`--case gui_3d_view --case gui_config_editors --case gui_main_window
--case gui_theme_response --case gui_workspace_layout --case gui_command_palette` → 6/6 通过、368 断言。

截图（`screens/`）：`B-page2.png`、`paper-page2.png`、`midnight-page2.png` 分别为晶格、纸墨、午夜蓝在配置页
（工作区含 3D dock）的实窗截图；`*-palette.png` 为命令面板；`before-*-page2.png` 是同一窗口尺寸下阶段 2
提交 `46241a3d` 的截图副本，用来看“溢出裁剪 → 可完整操作”的差异。

## 复现

```
export PATH=/d/msys64/ucrt64/bin:$PATH      # 静态用例的 g++/DLL 必须来自同一个 ucrt64 前缀
gui/.venv/Scripts/python.exe -B scripts/run_m0_tests.py --profile gui --report-root out/verification/j3-panels-gui2
gui/.venv/Scripts/python.exe -B scripts/check_report_evidence.py --report-root out/verification/j3-panels-gui2
```

截图需要真实字体数据库，离屏在 Windows 上只有方块：

```
QT_QPA_PLATFORM=windows gui/.venv/Scripts/python.exe -B out/skin_shots2.py "B,paper,midnight" "2" "pa"
```

## 不证明什么

- 未做独立审查，也未做 125%/150% 缩放、Linux 真实桌面、WSLg 的实窗复验。
- 本阶段没有改调色板与对比度数值，因此没有重测 23 项对比度表；焦点描边只是“可见”，不等于可辨识度达标。
- 截图是作者自己抓的，不是独立验收；不能替代任务书要求的“未参与设计者按正常入口完成四件事”。
- gui profile 通过只说明这 72 个用例、在这些断言上通过，不证明 J3 或界面整体已验收。
