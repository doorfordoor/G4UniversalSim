# E6 项目类型反例修复交接

独立前端审查P1/P2的原始五个payload逐字保留在`scripts/test_config_migration.py::project_type_contract`。项目加载、迁移计划与原始输入不变三条路径均断言拒绝；补充nested布尔、int、路径、数组元素、boolean index等反例。

实现：`project_migration.py`通过dataclass类型声明检查实际JSON类型，拒绝bool/int混用、float截断、字符串truthiness、null路径、错误数组/元素类型；只允许明确已有的flat `threads`正整数字符串、flat seed null→空串、geometry旧1/2字符串version归一，正常整数/null可选字段照常保留。构造发生在类型检查之后；GeometryDocument直接重载也检查，显式空layer列表保持为空，不再自动补默认层。

`same_json_value`递归比较实际类型，false与0、1与1.0均不同；冗余preview仅实际结构和值及类型相同时可省略，未知preview子字段继续拒绝。

本轮已执行通过：`test_config_migration.py`、`smoke_project_io.py`、`smoke_geometry_editor.py`、`test_geometry_config_diagnostics.py --layer gui`、`smoke_config_migration_ui.py`、`python -m compileall -q gui`。未修改C++。请独立前端审查者用原始out/verification反例脚本复核；不能将本修复者自测冒充独立复核。
