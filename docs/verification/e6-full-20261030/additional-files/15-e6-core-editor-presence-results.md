# E6 显式editor与source别名core修复结果

只修改`core/project.py`、`core/project_migration.py`和`test_config_migration.py`；未改前端/C++/schema/原独立复现脚本，没有commit或归档。

`project.py:134-139`仅在editor整个对象缺失时从Settings派生。显式source particle空、physics reference空（包括manual_modules有效的manual配置）、scoring bins0/负数均保留其他显式设置；迁移副本/正常保存重载不再换实验。GUI可表示范围仍由前端preflight拒绝。

`project_migration.py:112-119`按显式presence处理position_mode/type：二者都出现且不同立即拒绝，单字段历史数据将同一原值复制给缺失字段。缺省/版本1–6、plane/未来token/空token正例覆盖，不新增枚举白名单。

原`smoke_source_editor_v2.py`公开构造`SourceEditableModel(position_mode="plane")`后立即save；模型的旧alias初始仍point。project_to_dict在**导出副本**按已有_sync语义写一致alias，保留此公开用法且不修改caller；原始JSON两alias冲突仍在load/plan前拒绝。新增正式正例证明保存后原对象alias没有被修改。

已执行通过：迁移底层专项、source_editor_v2、source_field_preservation、project_io、geometry诊断GUI专项、migration UI smoke、compileall gui、所改文件diff --check。新增`editor_presence_contract`保留独立审查的显式对象原例、缺对象与空dict差异、单字段旧格式和冲突JSON源字节不变。

跨写者接口见`out/collab/e6-core-import-contract.md`；请前端/独立schema审查者用原始18例审查脚本在新输出路径复核，避免覆盖修前cases.json。当前结果是修复者自测，不替代不同写者关闭复核。
