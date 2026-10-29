# E6 root 文件独立审查（2026-10-30）

通过：test_main_config_version.py --component（真实g++编译ConfigManager/IniReader事务测试）、test_main_ini_migration.py、候选out/build-e6上的test_main_config_version.py。MainConfigVersion基于GetFields的winning记录检查，成功后只消费候选；主reader由ConfigManager在验证后替换。EffectiveSimulation新增格式字段resolved为int1、requested保留字符串/缺失、重复来源shadowed/accepted，由现有ConsumerState.Make维护，未发现误判。

当前确认缺陷 P2：main_ini_migration.py:22/28/34 使用Python Unicode strip，与C++ StringUtils::Trim的ASCII/C-locale逐字节空白不同。

反例1：nbsp-version.ini内容是 [general]\nschema_version=1\u00a0\n。plan_main_ini_migration报告input_version=1、changes=()并宣称winning版本通过；原payload不变。候选真实后端对复制件普通非零拒绝：schema version raw值为1+NBSP。证据nbsp-version-candidate.log。

反例2：nbsp-section.ini内容是 [general\u00a0]\nverbose=1\n。迁移把此section当general并在其下插入schema_version=1；真实后端把NBSP作为section名的一部分，完整快照 /configuration/main_ini_schema_version 无requested（仍为未声明legacy）。迁移声称已打标1，实际未打标。证据nbsp-section-candidate.log。

建议：为后端兼容扫描显式采用ASCII空白集合，保持按LF分行；新增NBSP值/section/key及Unicode空白反例，用真实后端或IniReader组件核对winning节/键/值。不要归一化用户原文。

已修旧反例：最初splitlines把U+2028当行分隔，版本插入run而非general；当前共享代码已改split('\n')，新候选复核真实requested=1，此项不再列未修。旧日志unicode-line-source/copy保留，不冒充当前缺陷。

source文件symlink在本机因WinError1314无法创建，未实测。代码path.resolve会把文件symlink输入改成被指向文件路径，理论上应审查相对主INI资源是否仍依据用户选择的symlink目录；此项只作为待核边界，未列实证缺陷。

未修改root文件，无提交/推送。
