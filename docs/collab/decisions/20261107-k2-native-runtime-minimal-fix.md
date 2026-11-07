# K2-3 原始独立运行失败的最小前置修复

2026-11-07。阻断清单K2-3，候选42be987e。原固定验收标准不变；仅纠正真实消费者语义与已约定component测试所缺闭包。原K2-1合同e27f5a81及freeze文件原字节保留，以下准确字段定义取代其冲突解释，不重写历史合同或旧报告。

反例一：原S-A导出原命令exit1，ParallelWorldConfig.cc真实ResolveRelative(mainConfigFile_, configured)把project/config/parallel.ini解析成project/project/config/parallel.ini。材料/主几何仍按cwd，平行世界则按主INI父目录；此前统一cwd结论错误。导出文件位置仍project/config/parallel.ini，只有main.ini的[parallel_world] geometry_config值应为config/parallel.ini。主审核真实代码及原错误；手工main-fixed成功只作定位，不作原包验收。

反例二：原两个component名称/数目正确，但ctest exit8，h2因缺scenarios/semiconductor/niel/si_proton.csv失败。该文件是已承诺真实组件的直接运行依赖；应仅将此精确文件纳入规范模板/清单/分发，保留CSV原有来源头及NIEL未物理评价边界。不得整体打包scenarios，不得删DDD断言、跳过组件、或验收时手工从工具仓库补文件。not_included文案须说明这个唯一例外。

最小文件范围：gui/g4usim_gui/core/export_project.py（parallel值重写与唯一样例表成员、排除说明）、scripts/test_k2_project_export.py（原对应语义断言/精确闭包），packaging/export_template_manifest.json重算；仅必要导出说明或支持文档的相同事实同步。CMake/物理实现/原CSV内容/K1/writer/其它功能不改。补丁通过定向自测、主审独核后冻结新候选，再只补受影响导出/运行/组件观察，复用原编译环境与不受影响原报告但保留原身份。

另：复制的build_vs2026缓存仍指向原sa树，原受控副本的第一次build返回0但指纹/产物不变，不能算修改重建。现有重新configure/build诊断允许完成，保留原失败，不中断在途任务。后续新源码副本必须配置自己的新build目录，核CMAKE_HOME_DIRECTORY/MSBuild真实来源再建，不需要产品修复或增加第二行C++修改。记录与原日志索引out/collab/20261107-k2-build/independent/original-42be-failures/identity.json。

停止条件：只完成上述两个阻断缺陷与原专项自测，独立author-r5回执及outbox交付停写，主审核定新候选后回K2-3。已开始旧候选构建可收集终态，不重复启动已知会失败的旧S-A/CTest或将诊断副本当原包通过。原S-B/SDK/依赖事实按真实范围保留；不扩大矩阵、不追加F3批次、不调整验收门限。
