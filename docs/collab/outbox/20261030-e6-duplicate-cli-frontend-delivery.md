# E6 复制入口 CLI 覆盖修复终态

前端正式targeted已终态，产品/GUI专项稳定，无运行会话，无commit/push。不同写者原8payload复核issues=0由root另存证据。

## 稳定文件

- `window/project.py`：`duplicate_history_package`只在候选copy中接收新副本`read_generated_run_settings`结果，对齐flat/runSettings三字段后做投影preflight；成功才发布。继续使用当前所选backend，工作目录对齐副本；不取snapshot陈旧flat或runSettings作CLI依据。seed缺失为None→空CLI seed，显式0为`"0"`，不混淆。
- `widgets/project_page.py`及`widgets/config/setup_panel.py`各**一行**：仅runName/run_name读回改为ASCII空白trim，与严格INI规则一致；不改路径、其他字段或快照恢复语义，保留尾NBSP及内部Unicode。
- `core/i18n.py`：pre-copy拒绝仍“复制失败”；成功复制后GUI拒绝明确“副本已创建，未载入、未运行”，含副本路径与真实错误。旧current全状态保留，副本可保留，不把文件复制成功说成失败。
- 新`gui/smoke_tests/smoke_duplicate_history_cli.py`供root登记独立GUI用例。

## 最终targeted

v3最终均退出0：duplicate_history_cli **254**、project_snapshot_restore **61**、project_import_projection **393**、main_window_ui **46**、new_simulation_wizard **60**、start_page **74**。日志`out/collab/e6-duplicate-cli-smoke_*-v3.log`。最后新用例日志已对应ASCII普通空白与内部Unicode/尾NBSP正例。compileall/diff空白检查已通过；最后修改仅补正例测试，产品未再变。

新用例使用真实writer，当前UI7/999/unrelated对main2/43/writer_run；种子0/缺失、snapshot陈旧flat、手改main参数优先、内部Unicode/尾NBSP、ASCII外围空白、仅复制及复制并运行两入口。走真实start_run和inspection完成回调，截获最终runner.start命令；inspection回复是明确的合成单元测试数据，**inspect/backend进程均未执行**，不能称真实模拟成功。

负例含pre-copy非法seed、已完成copy后线程不可投影、真实post-copy main被改坏再由严格helper拒绝。均断言旧对象/路径/widgets/editor/stale/package/日志完整保留、不启动进程；已创建副本与源字节保留，并区分对应提示。

底层严格helper及真实后端2事件由schema/root独立留证，本报告不扩展为任意main反向导入、不变更物理范围。快照恢复路径未改。现在停止产品/正式测试编辑，交root stage/commit/freeze。
