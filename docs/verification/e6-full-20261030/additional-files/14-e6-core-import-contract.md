# E6 导入最小core修复对前端的稳定契约

保持现有`load_project`/`project_from_dict`/`plan_project_migration`签名，无新增前端API。

- editor对象**缺失**时，仍按既有SourceSettings/PhysicsSettings/ScoringSettings派生历史默认。
- editor对象**显式出现**（包括空dict）时保留显式值及其余设置，不再因particle为空、reference_list为空、hist_bins<=0重建整对象。对象里的错误/无效状态交给现有验证/GUI表示预检，不能先变成另一份实验。
- sourceEditor同时显式给position_mode和position_type且不完全相同，构造前抛ValueError并带两个字段路径；不在活UI校验时偷偷以mode覆盖type。
- 仅给其中一个的历史JSON，在纯候选归一阶段把同一原值复制到缺失另一字段；未知枚举、空值原义保持，不新增封闭枚举白名单。不改变_source model_既有beam等校验兼容映射。
- 既有`smoke_source_editor_v2`使用`SourceEditableModel(position_mode="plane")`构造后直接保存，此时模型另一alias仍是dataclass默认point。为保留这个实际公开构造用法，`project_to_dict`只在导出副本按既有`_sync_source_legacy_fields`语义规范两个别名，不修改caller、不运行全validator。原始JSON同时声明冲突仍在构造前拒绝；这不是放宽JSON导入。
- 前端应继续按实际送到Qt控件的候选值预检；显式hist_bins=0现在不会被默认100掩盖，将由GUI投影边界明确拒绝。manual physics的空reference_list不是切换成reference模式的理由。

仅修改core/project.py、project_migration.py与底层迁移正式反例；未改前端文件、物理schema或标量全局相等规则。等待不同写者用原始audit脚本复核。
