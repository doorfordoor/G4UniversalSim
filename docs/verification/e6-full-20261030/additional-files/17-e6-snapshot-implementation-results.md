# E6 专用snapshot适配交付

实现文件稳定：新增`gui/g4usim_gui/core/project_snapshot.py`，`core/project.py`仅导出lazy `load_project_snapshot`入口；新增`scripts/test_project_snapshot_compat.py`；既有integration `test_config_migration_backend.py`追加包快照真实闭环。未改frontend、C++、schema或duplicate writer，未commit/归档。

API见`e6-package-snapshot-api.md`，前端已按`.project/.notes/.package_root`接线。legacy无envelope普通JSON保留strict普通project分支；任一envelope key出现即完整适配，不partial fallback。普通loader/普通新副本迁移继续拒绝envelope。

标准包资源只读当前同包规范layout，检查缺失/escape和symlink出包；旧duplicate两条旧资源仅接受来自同一旧包标准后缀的成对遗留值，不读取旧位置。metadata闭合嵌套type/key/计数验证；材料摘要不伪造配方或禁用草稿。返回当前材料/几何引用及重读几何，run flat镜像对齐记录runSettings；generated、清config/macro/output、runsRoot用当前包父目录，历史结果不发布为当前运行成功。

测试与会话终态：

- `test_project_snapshot_compat.py`退出0；真实writer自定义混合材料+edited几何、改原外部输入、专用load/save/reload/regenerate、普通loader/plan拒绝、未知/future/duplicate/type/nonfinite/partial envelope、缺文件、旧成对遗留路径不读旧包、真实duplicate只读新包、当前几何文件优先均覆盖。symlink escape谓词使用明确resolver故障注入，不声称测试了Windows symlink创建权限。
- `test_config_migration.py`退出0；此前迁移反例均保留。
- 完整`test_config_migration_backend.py`会话11819已结束、exit0；原10类几何/迁移对照继续通过，新增真实包快照链2run×2events通过。
- 当前显式main版本writer专项又单独执行exit0：`out/verification/e6-snapshot-current-writer/snapshot-roundtrip/runs/`保存原包和重建包。两个main.ini均有`[general] schema_version=1`，材料/几何文件字节相同，源proton/5MeV与seed12345保持，事件与dose行相同、summary各2/2 completed。这是工程等价对照，不是物理基准。
- `smoke_project_snapshot_restore.py`与`smoke_project_import_projection.py`exit0（修复者接线自测，不替代独立审查）。compileall gui及所改文件diff --check通过。

日志：`out/collab/e6-snapshot-static-final.log`、`e6-migration-after-snapshot.log`、`e6-snapshot-backend-first.log`、`e6-snapshot-backend-current-writer.log`、`e6-snapshot-gui-core-check.log`、`e6-projection-with-snapshot.log`。没有本agent未结束会话。

root需登记static `project_snapshot_compat`；backend已归既有integration，不令static/GUI依赖实际exe。等待不同写者用真实writer/duplicate与保留raw反例独立复核；不扩大F1/K1/J2。
