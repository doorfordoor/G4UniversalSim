# J3 第二阶段：外壳层级、命令面板与外观状态（2026-11-02，作者交付，未验收）

本目录是 J3 第二阶段的自查证据。它不是独立验收，也不代表 J3 已完成；区域层级改造、对比度实测表、
125%/150% 与 Linux 桌面实窗、切换性能基线仍按 [J3 设计任务](../../collab/decisions/20261102-j3-desktop-skins.md)
的验收表待做并需由未参与实现的人复核。

## 本阶段交付

- **导航分组**：侧栏从单一 `WORKFLOW` 段改为 `WORKFLOW`（Start/Project/Configuration/Scenario/Effective Configuration）
  与 `RUN & ANALYZE`（Run Console/Results/Run History/Parameter Scans）两组，组间留白；选中项带强调色轨道。
- **页头层级**：页头改为“面包屑 + 页标题 + 说明 + 项目/运行状态 chip + 外观/语言按钮”，面包屑随区域在
  `Workflow` / `Run & analyze` 之间切换；项目 chip 保持单行并带完整 tooltip。
- **命令面板（Ctrl+K）**：`gui/g4usim_gui/widgets/command_palette.py` 提供键盘优先的启动器，条目按
  Pages / Actions / Appearances 分组；输入先按标签严格匹配，仅当标签没有命中时才回退到类别与说明；
  Up/Down 跳过分组标题，Enter 运行、Esc 关闭；选择外观条目会激活它所属的明暗组。
- **状态栏外观状态**：状态栏右侧常驻 `Appearance: <皮肤名>`，tooltip 给出皮肤描述；切换模式或皮肤即时更新。
- **外壳配色统一**：菜单栏、编辑历史工具条与状态栏统一使用皮肤自身的浅表面色与细分隔线，不再出现与画布割裂的纯白条。
- **i18n 与回归**：新增页面分组、命令面板、外观状态等中文词条；新增 Qt 用例 `gui_command_palette`
  （40 条已执行断言），覆盖分组、面包屑、过滤严格性、键盘与外观切换。

## 证据

| 项目 | 结果 | 位置 |
| --- | --- | --- |
| 完整 GUI profile | **72 / 72 通过、10227 条断言** | 本报告 `report.json` 与 `logs/` |
| 命令面板专项 | `gui_command_palette` 通过，40 条断言 | `logs/gui_command_palette.log` |
| 报告门禁 | `check_report_evidence.py` 通过（版本 2、`settrace_assert_lines_v3`、`sha256_raw_bytes_lf_v2`） | 见下命令 |
| 源码指纹 | `9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a` | 与工作区 EXE 同一身份 |
| 测试内容指纹 | `9fae4a78a362ee74e69fd730a795649ba1a265c1738c86f40386d8abc5c5c882` | 报告运行时快照 |

截图（Windows 实窗 1560×980 逻辑像素、125% 缩放）：`screens/after-{B,C,paper,midnight}-page{0,2}.png`
与同皮肤的 `-palette.png`。离屏（offscreen）在 Windows 下没有字体数据库，截图会出现方块字形，因此截图脚本用
`QT_QPA_PLATFORM=windows` 抓取；这属于外观记录，不是独立可访问性验收。

## 复现

```bash
export PATH="/d/msys64/ucrt64/bin:$PATH"   # 本机 static 用例需要正确的 libstdc++/libgcc DLL
gui/.venv/Scripts/python.exe -B scripts/run_m0_tests.py --profile gui   --report-root out/verification/j3-shell-gui
python -B scripts/check_report_evidence.py --report-root out/verification/j3-shell-gui
```

## 不证明什么

- 只覆盖本机 Windows 与离屏/实窗截图，不代表 125%/150%、Linux 桌面与键盘可访问性验收。
- 命令面板的过滤与键位有自动断言，但“好用”仍需要未参与者在正常入口实际完成目标任务。
- 未重跑 backend/integration：本阶段只改 GUI 与文档，后端身份未变；全平台矩阵仍以各自证据为准。
