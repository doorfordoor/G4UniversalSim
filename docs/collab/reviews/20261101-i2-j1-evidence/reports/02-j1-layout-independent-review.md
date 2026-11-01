# J1 布局候选独立审查（2026-11-01）

结论：发现1项P2首次3D展示自动后端预览遗漏；其余本轮限定契约未发现新阻断问题。未编写布局实现，未改产品/正式测试；未重复正式大矩阵、未操作实窗。

## P2：新停靠入口显示3D后未安排自动Geant4几何预览

定位window/workspace_layout.py:89-98、211-217，widgets/config/preview3d.py:111-124；关联main_window.py:99-100旧tab currentChanged触发器。

默认Start首次进入配置页时，_first_navigation_docks确实显示preview dock，preview3d_tab_visible也正确返回True，但dock.visibilityChanged只处理隐藏状态、清除首次导航，不在显示时调用schedule_backend_geometry。配置页首次展示没有切到原3D tab，所以原currentChanged调度也不发生。勾选“自动显示Geant4几何”的视图因此不会按原约定打开后自动更新；用户必须改字段、切换旧3D占位标签或手动显示后端几何才恢复。

独立实际Qt探针：默认Start show/processEvents，停止任何初始化遗留timer以观测本次激活，再进入配置index2。实际dock_visible=True、auto_checked=True，但_backend_timer inactive；pump1.5s后export_backend_geometry调用0。切到旧3D tab后timer active、再pump1.5s调用1。导出方法使用mock拦截，避免启动后端；证明调度入口差异，不宣称真实模拟。

证据out/collab/j1-layout-review-first-preview-confirmed.json，脚本review_j1_first_preview_confirmed.py；早一轮只等待旧tab0.3s的探针保留，不引用其export0作为错误。建议在实际preview显示转换上使用现有auto guard调度，覆盖首次、隐藏后重显、restore的真实入口；保持auto关闭、隐藏和正在构造时不启动，不能通过取消勾选auto或只修改文档掩盖缺失。

## 已查通过范围

- 单实例所有权：WorkspacePageStack保留九个逻辑page身份；Config/Results改用anchor和原对象dock，3D原scroll从旧tab搬到同一host，无重建编辑器/runner/experiment；Logs同一tab和progress控件搬移。父子与页面身份专项覆盖实际对象is而非只按标题。
- 九页导航：widget/indexOf/currentWidget/setCurrentWidget映射原page；导航重新显示所选dock，restore_current_index不把保存的隐藏dock强行打开。首次配置preview仅一次默认显示；manual hide和保存恢复覆盖first-navigation标志，未发现再次导航把手动隐藏冲掉。
- QSettings：本机version/checksum、严格页码/版本类型、Qt字节和hosts完整性；坏JSON/状态/版本、大小限制与屏幕变化回退保留原控件。_fit_window约束主窗，屏幕改变时所有float redock；不把本机布局放进project/F5/K1。
- F5：FocusIn/Out pending_only只在已有真实编辑timer时capture；无等待时间屏蔽。预设/浮动/隐藏/主题不触发settingsChanged、项目更新/保存/runner动作或revision改变；真实QTest键入紧邻float前后原始非法seed保留，Undo/Redo恢复。未发现更改历史分支或默认records_root，前次错误的pre-resolve保持撤回。
- F4：只有workspaceDock显式允许reveal；独立隐藏字段仍拒绝，readonly/disabled检查保持。适配后的stdout检查实际dock祖先中心可见，与旧reach中心契约等价；原表格full_cell断言保留。reach中重复一次horizontal setValue属冗余，不影响已验契约，不单列缺陷。
- 浮动结果：WorkspaceDock._closing weakref读取真正MainWindow关闭标志；没有第二业务closing owner。专项实际将Results float后emit late merge错误，关闭中不弹框；恢复停靠后原页面继续单实例。
- 关窗：MainWindow在现有业务owner/恢复/experiment收尾接受后才save layout、remove filter；已独审_close_self_test_window按拒绝/等待/接受销毁契约，不靠改历史根通过。当前回归含defaultNone和env override真实history pending生命周期。

## 独立执行

原D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe，QT_QPA_PLATFORM=offscreen：
- smoke_workspace_layout.py全专项退出0，日志j1-layout-review-workspace.log（含两种实际default-start子进程、F5相邻编辑和floating callback）。
- smoke_f4_layout.py退出0，日志j1-layout-review-f4.log，768px/narrow、主题语言、值保持与表格完整可见保留。
- 上述独立first-preview窄反例退出0并明确记录调度遗漏。

仍需root继续native拖拽/中文/DPI/真实运行中操作、CI/frozen及正式矩阵；本轮不把组件专项外推为完整J1关闭，也不涉及物理验证。
