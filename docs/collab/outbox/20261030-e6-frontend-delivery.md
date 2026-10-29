# E6 前端实施交接

基线 `c6bf8ad`；前端未提交/推送。DeepSeek真实一次咨询及取舍见 `20261029-deepseek-e6-design.md`，未重复调用。

## 实现

- `window/project.py`：普通/最近/历史加载复用先load再发布流程，拒绝时保留当前状态；Save As仅写成功后切`project_file`；迁移成功默认不切换项目。
- `window/shell.py`：文件菜单新增“配置迁移副本…”及连接，仅两行。
- `widgets/migration_dialog.py`：项目JSON/主INI/几何分别选源并展示输入/输出版本、改动、已执行检查与验证边界、候选全文。几何模板稳定token及显式metadata映射由core校验，不扩大J2编辑支持。写出走`publish_migration`；项目副本成功后提供显式打开，INI副本不自动替换当前路径。
- `core/i18n.py`：集中中文文案；原始错误与配置token保留原样。
- `gui/smoke_tests/smoke_config_migration_ui.py`：新增Qt专项，建议runner登记gui profile。

## 已执行验证

`python -m compileall -q gui`、新`smoke_config_migration_ui.py`及既有`smoke_project_io.py`、`smoke_main_window_ui.py`、`smoke_q1_public_paths.py`均退出0。日志`out/collab/e6-smoke_*.log`。新专项验证三类计划/副本、原件字节、已有目标/硬链接/缺目录/源变化拒绝、future项目拒绝、几何metadata显式映射、主INI同目录限定、中英文、菜单入口、加载失败与另存失败路径保留、显式打开副本后才切状态。

这些是GUI/格式与状态测试，不构成Geant4模拟或物理验证。后端往返和完整冻结回归由主任务另记证据。

## 实窗边界

启动本轮独占`E6 migration visible check`原生Windows窗口；Computer Use返回辅助功能树，版本5→6、改动、三标签与按钮状态符合预期。返回屏幕图像却是Windows锁屏，已按技能停止桌面输入，没有尝试解锁或操作其他窗口。

`out/collab/e6-migration-qt-layout-zh.png`是自身Qt windows平台窗口渲染图，已用图像工具观察：中文、版本、源路径、三条改动、验证边界及按钮无截断。它是应用渲染证据，**不是解锁后的真实桌面交互验收**。offscreen平台曾显示方框字体，最终图使用windows平台重新生成；未用方框图冒充通过。自有测试进程已明确停止，无遗留会话。

## 待主任务

登记GUI专项、同步人类文档/GUI约束与阶段总证据；独立审查和完整回归；解锁后补自身窗口桌面操作。当前不宣称整E6完成。
