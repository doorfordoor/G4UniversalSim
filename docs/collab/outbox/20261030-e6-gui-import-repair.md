# E6 首轮冻结后 GUI 导入修复交接

root确认首轮127用例报告终态并解除冻结后实施；不改首轮报告，不提交/推送。

## 最小改动

- `window/project.py`：近期恢复warning `Open recent project failed`，历史快照恢复warning `Load snapshot failed`，普通Open与显式打开迁移副本保持critical `Open project failed`。真实错误内容保留。
- 同文件新增纯投影检查，逐项读现有控件`minimum()/maximum()`；在load错误处理内和`_set_project`第一行执行，早于项目对象、页面、macro plan、stale/package路径发布。仅覆盖实际QSpinBox投影，包含summary/editor双范围；未加入未投影的`scoringSettings.trajectory_events`，也不对QLineEdit seed或其它整数施加Qt范围。不改backend/core范围。
- `widgets/config_builder_page.py`：`_set_combo_text`遇空值明确`setCurrentIndex(-1)`，不再显示上一项目选项；未知非空枚举继续动态保留，无新增白名单。
- `window/content.py`仅四行：向导build结果先应用候选copy并做同一投影预检，拒绝发生在改当前项目之前；成功仍保持旧in-place项目identity约定。
- `core/i18n.py`集中范围拒绝与错误标题翻译。

## targeted证据

以下8个专项均退出0：`smoke_project_import_projection`、`smoke_config_migration_ui`、`smoke_project_io`、**原始未改的**`smoke_start_page`、`smoke_main_window_ui`、`smoke_q1_public_paths`、`smoke_source_field_preservation`、`smoke_new_simulation_wizard`。日志`out/collab/e6-import-repair-smoke_*.log`；compileall与相关diff空白检查通过。

新增正式专项`gui/smoke_tests/smoke_project_import_projection.py`，root登记独立GUI用例（最终清单128，不追改首轮127）。最终修订用v3探针执行退出0，`G4USIM_ASSERTS=393`，日志`out/collab/e6-import-repair-smoke_project_import_projection-v3.log`。

专项覆盖：8类真实控件路径的交集上下界外一格、正负巨整数；generated/external及关闭scorer；16个可准确表示端点正例；普通、近期、历史、真实迁移副本的打开失败严重级别/标题/真实错误；失败前后旧对象identity、project JSON、路径、全部保留子控件text/value/checked/index/data/plainText/table、editor对象及文档、building标记、stale/package、macro plan/inspection、输出目录与最近项目均相同；源字节不变。也检查直接`_set_project`拒绝、向导候选拒绝、空/未知枚举保留与中文错误。

原11个独立整数fixtures未经编辑重放，通过非模态记录**预期拒绝消息**避免诊断脚本自身停在弹窗：11例均False，旧对象/路径/building/stale/package保留。修前`large-integers-before-fix.json`、修后`large-integers.json`、`projection-fix-boxes.json`与`projection-fix.log`在`out/verification/e6-startpage-modal/`。这不是通过给原start_page补critical mock制造通过：正式原start_page本轮未改且已正常退出。

## 结论边界

关闭的是**文件导入已知可预测整数投影失败的状态保留**及意外严重级别回归；不宣称任意IO/Qt异常都能事务回滚，不把格式/GUI检查称作模拟或物理验证。flat/nested线程端点正例使用一致的历史镜像值，未改变现有两者优先关系。当前产品/正式测试稳定，等主任务独立复核与重新冻结。

桌面仍锁定，本轮无Computer Use输入或替代桌面验收。原生桌面检查待用户解锁，不能用offscreen测试冒充。
