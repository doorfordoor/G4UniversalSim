# J3 独立复验 · 2026-11-03

**裁决：退回修订，保持 J3 未关闭。** 审查 D 盘 HEAD 6b03317a，对应产品候选 a1a64ead。复验开始时已有 gui/AGENTS.md 的本地修改，未纳入本结论或提交。旧审查按原时点保留。

## 已复现的阻断项

紧凑布局会覆盖用户刚作出的停靠区选择。以 Qt offscreen、真实主窗口及仓库的 gui_test_window 夹具启动，设宽 1200、高 800，显示窗口并处理事件。若 AI dock 隐藏，通过其 toggleViewAction 打开，处理事件并读取 isHidden() 为 False。保持同一布局，仅把主窗口拉宽 5 个逻辑像素并处理事件，实测宽 1205、isHidden() 为 True。两次尺寸都在同一紧凑区间。此为 Qt resize 事件复现，未冒充手动拖拽观察。

入口为 gui/g4usim_gui/main_window.py:89–97 和 gui/g4usim_gui/window/workspace_layout.py:189–209。每次 resize 都调用 adapt_to_width，compact 分支会隐藏 ai、preview，且没有在已处于紧凑布局时保留用户显式显示的选择。实际复现的是 ai；preview 位于同一源码分支。

修后判据：初入紧凑布局仍可收起可选区；手动重新打开 AI 或 3D 后，在紧凑范围内多次微调宽度和高度仍保持用户选择。跨阈值、复位、浮动和恢复布局应分别按明确契约验证。新增永久回归并经实际菜单和窗口缩放复查。

## 证据核对

- 对 [冻结归档](../../verification/j3-close-20261103/README.md) 中的 static、gui、integration 三个 report.json 分别运行 check_report_evidence.py，三份均通过。分别为 49/5615、75/10297、33/6844（用例/断言入口）。这是原报告复核。
- 独立新跑 theme_registry（1/587）以及 gui_j1_appearance、gui_theme_response、gui_theme_state（3/97），无失败或跳过。均使用 require-tracked-sources、fail-on-skip 并通过严格证据门禁。新报告在本机 out/verification/j3-independent-nov03-static 和 j3-independent-nov03-gui。
- 作者已提交新的截图、语义色表、菜单提示与冻结记录，旧审查的“无候选冻结”“circuit 无截图”不再适用于此次提交。截图覆盖与尚缺场景见[作者修正记录](../../verification/j3-visual-checks-20261102/README.md)第 7 节。
- 本次在可重复的产品行为反例处判退。Windows 125%/150% 的独立实窗四项任务、Linux 实际桌面、窄面板和待批准等状态的完整视觉签收仍待完成。下一次送审保留此次失败，并将更新后的候选身份、专项和跨平台操作收据分别登记。
