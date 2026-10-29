# E6 迁移底层 API（实施接口）

前端可直接依赖以下接口；仅接受磁盘源文件，不修改当前项目对象。

- `core.project_migration.plan_project_migration(source: str | Path) -> MigrationPlan`
- `core.geometry_migration.plan_geometry_migration(source: str | Path, template_name: str, *, metadata_mapping: dict[str, str] | None = None) -> MigrationPlan`
- `core.config_migration.publish_migration(plan: MigrationPlan, destination: str | Path) -> MigrationResult`
- `MigrationPlan`：`kind`、`source_path`、`source_sha256`、`input_version`、`output_version`、`changes: tuple[str, ...]`、`validation: tuple[str, ...]`、`payload: bytes`；计划构造失败抛 `ValueError`，不生成文件。
- `MigrationResult`：`destination: str`、`sha256: str`、`plan: MigrationPlan`。
- 发布成功后的清理失败仍返回成功结果，`MigrationResult.cleanup_warning: str | None = None` 提供临时链接清理提示；`os.link`是提交点，不能在已发布后把清理失败报告为迁移失败，更不删除目标做回滚。
- `MigrationPlan.destination_parent: str | None = None` 为末尾可选字段；主 INI 设置源目录可强制同目录复制，发布时比较规范路径，不允许跨目录。

`metadata_mapping` 的键为 `[section]/LegacyKey`，值为 `metadata.LegacyKey`；只允许对实际识别出的非运行 legacy metadata 做显式映射，冲突或未使用映射拒绝。无映射时遇此类字段拒绝并返回精确字段位置。

发布同目录临时文件，写完 flush/fsync，发布前重查源 SHA，使用 `os.link` 原子独占发布（不支持硬链接的文件系统明确失败）；已有目标和链接别名均拒绝。失败不更改 GUI 内存，不覆盖源和目标。几何计划把支持的相对资源路径改为源文件目录下的绝对原目标。项目文件已知路径按当前加载语义保留；迁移不把项目文件目录偷偷当运行工作目录。

`validation` 明确格式/结构检查范围。几何计划只检查严格 schema 与歧义；完整后端语义仍由 Inspect inputs/真实后端决定，超出现有 GUI 编辑子集不会获编辑授权。

2026-10-30 实施里程碑：共用 API、project/geometry 计划与独占发布已实现，`scripts/test_config_migration.py`、`gui/smoke_tests/smoke_project_io.py` 已通过。真实后端专项为 `scripts/test_config_migration_backend.py`，读取 `G4USIM_EXE`/`--executable`，可选 `G4USIM_BASELINE_EXE`/`--baseline`；主负责人可登记 static `config_migration` 与 integration `config_migration_backend`。目前正以保留的2C后端做脚本验证，不代表E6候选验收。几何完整语义在专项真实初始化+网格对照+2事件运行证明，产品计划仍显式要求后续Inspect inputs；几何迁移不调用后端、不自动生成可运行认证。

2026-10-30 后续：C++诊断代码已稳定，排序与相等使用同一完整身份，定义移入GeometryConfigDiagnostic.hh供独立组件实测；新增`scripts/test_geometry_diagnostic_identity.py`（static/cxx），请登记。GUI GeometrySummary增加结构化source诊断身份，code/severity/规范路径/行/section/key/value去重、不含显示文案；core专项覆盖三次源重载、每次三次validate+snapshot reload，计数不增长且字段位置不丢。已处理LF/CRLF扫描与裸CR/Unicode分隔符拒绝。2C后端真实10类对照已结束全通过；不再修改C++，候选重建可开始。
