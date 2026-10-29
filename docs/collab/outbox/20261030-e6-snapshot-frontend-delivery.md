# E6 真实运行包快照前端接线交接

本轮仅前端文件与GUI专项，未改core/history、未提交/推送、未操作桌面。

## 接线与用户说明

- `window/project.py`仅snapshot=True调用`core.project.load_project_snapshot`，取`restored.project`后先做现有投影preflight，再发布。普通Open/recent/迁移项目读取仍是严格普通loader。
- 失败仍warning `Load snapshot failed`且保留旧对象、页面、路径、editor、stale/package等状态；不因metadata可读而跳过投影/配置校验。
- 成功**无新增information/exec模态**：简短状态栏，完整中文范围+package_root+core notes写入配置页“消息与文件”的可见详情，并追加到有界运行日志。当前页面切到该详情，用户可立即查看；长说明不依赖状态栏时限。
- 固定说明：恢复当前包材料/几何和快照编辑参数，须重新校验/生成；不恢复手改主配置/宏、未输出草稿或历史成功。当前hash不证明与历史run字节一致。普通旧式project-only快照按API的空package_root分支，明确只载入设置、原资源/历史结果未核验，不误称包内输入已恢复。
- `core/i18n.py`收录固定说明及core当前5类notes；原始错误token继续原样显示。

## 新正式GUI专项

`gui/smoke_tests/smoke_project_snapshot_restore.py`供root登记独立GUI用例。本轮最终v3退出0，**61断言**，日志`out/collab/e6-snapshot-smoke_project_snapshot_restore-v3.log`。

真实`create_run_package`生成编辑混合材料配方、编辑几何及S/P/S参数，含未输出disabled草稿；随后改原源文件、手改包main/macro，再通过真实history signal载入。断言包内实际配方/几何与snapshot参数恢复、草稿不伪造恢复、flat run镜像对齐、config/macro/output清空及stale、无成功结果；保存规范项目、第二窗口普通load、重新生成，材料/几何字节与S/P/S参数相符，包及源不改。普通入口仍拒绝envelope。

负例使用同一真实writer snapshot，unknown root/nested metadata、巨整数、缺包材料均在发布前拒绝并保留全部旧状态；真实错误内容和warning标题均断言。另断言详情实际可见、日志保留、恢复成功未触发warning/critical/information。

## 受影响既有验证

v3通过：`smoke_project_import_projection`393、`smoke_config_migration_ui`74、`smoke_project_io`6、原始`smoke_start_page`74、`smoke_q1_public_paths`32；日志`out/collab/e6-snapshot-smoke_*-v3.log`。compileall gui及相关diff空白检查通过。

API实现期间一次targeted投影测试以旧的“先要求标准snapshot文件名”错误文本为预期，遇新API“先读文件/兼容plain-project”行为而失败；已恢复真实缺文件/范围错误的准确预期，最终393通过。该次是测试预期与新增明确兼容入口的调整，不是通过吞critical变绿；原stage冻结失败报告未改。

本轮验证是格式/GUI真实writer往返，不执行Geant4或证明物理正确；真实后端两事件往返由migration/root另记。产品/GUI测试现已稳定，可交叉审查与重新冻结。
