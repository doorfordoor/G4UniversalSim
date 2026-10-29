# E6 migration agent 对主版本实现的独立审查

1. `MigrationPlan.destination_parent` 已按主负责人的消息加在末尾并落实发布前规范目录比较；main_ini_migration可以使用。
2. 迁移底层API稳定，详见同目录 `20261030-e6-migration-api.md`。核心专项、project_io、GUI几何诊断、compileall通过；`test_config_migration_backend.py`使用保留的out/build-2c后端，10类source/migrated真实初始化/mesh/2事件对照及4类project/writer链全部通过。候选后端仍待主负责人构建验证。
3. **需裁决版本检查范围：** 当前`ConfigManager::LoadMainConfigBytes`统一调用`ValidateMainIniFormat`，而`src/Templates/GeometryTemplate.cc::BuildNodesFromFile`也用这个入口读独立几何文件。因此legacy几何文件中原先只会产生`unknown_section`警告的`[general]/schema_version=2`会触发“主INI版本拒绝”，改变几何v1兼容路径，并把主版本规则传播到独立文件。建议为ConfigManager提供明确的独立几何load入口/参数跳过主INI格式判定，或者只在真正main输入边界做校验。请补一条legacy独立几何中`[general]/schema_version`依原几何语义处理的回归。不要把几何[global]/version与主INI schema_version混合。
4. `ValidateMainIniFormat`先候选后发布、winning source字段/精确词法及消费标记设计符合约定；`main_ini_migration`同目录边界、后值生效与保留原字节符合约定。需要后端测试确认重复section/key winning field来源是最后声明；本审查不把源码阅读当真实运行通过。

2026-10-30 独立复核补记：第3项已由主负责人修复。`ConfigManager.cc:121`新增`LoadGeometryConfigBytes`，保留独立几何原读取语义；`GeometryTemplate.cc:17`改用它，主INI两个入口仍先candidate+Validate后发布（109/117行）。`test_main_config_version.py --component`在本审查回合真实通过，覆盖geometry `[general]/schema_version=2`不触发main判定。后端正式修复验证由主负责人build02后跑；本补记不将未跑候选的结果写为通过。源代码范围检查未发现遗漏的模板旁路。

build02独立后端复验已补跑：`test_main_config_version.py`退出0，包含独立geometry反例及future/duplicate/精确词法拒绝；测试用executable SHA256=dcd96ad49c1c3756a4be4175c7182681de93979c7c5cbc354b1941d4eee2c785。第3项修复独立复核通过；这不替代最终冻结全量验收。
