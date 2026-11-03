# J3 第二次独立复验

审查检出 26cb37a5，产品修复 ce9b6283。与上次相比，**菜单重开 dock 的原反例通过**。两条正常用户入口仍有可重复的面板可见性问题，整体暂不签收。

1. Windows 原生 Qt 平台插件、隔离 QSettings 和恢复根、真实主窗口的程序化操作。1200 宽通过菜单的 toggleViewAction 打开 AI 和 preview，两者在 1205 仍可见。浮动 AI 并调至 1210，再停靠并调到 1420，两者均保持显示。另行重跑 gui_workspace_layout、gui_compact_panels，两项共 174 个断言入口，严格门禁通过。
2. **配置页显式打开 3D 失效。** 在 1200 宽进入 3D 标签，确认“Show 3D view”按钮 visible/enabled，调用按钮 click 后 preview 可见，调到 1205 后隐藏。workspace_layout.py:328–343 的点击入口直接 show/raise；189–191 仅监听 toggleViewAction；222–232 在下一次 resize 将其归为可收起项。修后应区分用户主动打开与页面自动显露。
3. **恢复布局的效果不持久。** 1205 宽通过菜单打开 AI、保存布局，手动关闭后恢复。恢复当下 AI 可见；轻调至 1211 后隐藏。workspace_layout.py:500–502 清除覆盖，restoreState 恢复可见性后下一次 resize 又收起。增加保存可见与保存隐藏两个方向的回归，且不破坏首次进入紧凑区间的收起行为。
4. 新候选三份归档逐份独立校验均通过。再用上一冻结 j3-close-20261103 相同 profile 作 baseline，static 与 gui 通过，integration 严格比较失败（6844 → 6843，唯一变化为 gui_theme_state_backend 的 33 → 32）。此差异本身不证明模拟出错；该用例有运行期回调内断言，应定位计数差并用稳定的回归判据解释或修正，保留原报告。

[独立 Windows 探针](../../verification/j3-independent-ce9b6283/windows-probe.py)及[原始观察](../../verification/j3-independent-ce9b6283/windows-observed.log.txt)。表中两列布尔依次为 AI、preview 的 isHidden()，False 表示未隐藏。D 盘根目录设 PYTHONPATH 为 gui;gui/smoke_tests、QT_QPA_PLATFORM 为 windows，用 GUI venv 运行探针。报告中的 Windows 窗口操作由 Qt 驱动，本次没有把它计作人工 125%/150% 或 Linux 视觉签收。[上一轮复验](20261103-j3-independent-retest-6b03317a.md)列出的跨平台视觉缺口仍须按候选身份补证。
