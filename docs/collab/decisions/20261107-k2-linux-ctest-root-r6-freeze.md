# K2-3 r6显式CTest根参数独审冻结与剩余矩阵

2026-11-07。最小修复已独审签收，K2-3尚未整项通过。产品b1a7ffbc0519a29cb37b458e2e1542640956976a；模板36324640f5222558eca67919f42829fed8fa68815c128afe07f9ce85dc566e74/309成员，manifest 51d76103…；D/C同产品，旧56b1/1fa4与失败均保留。

作者turn131已completed/停写（74585），r6回执6b312d80…；四文件SHA、14原证据SHA、309模板规范成员全部主审独核。产品唯一行为改动为CMake测试命令追加现有${PROJECT_SOURCE_DIR}参数，无物理源码修改；原测试仅一条窄断言，说明及模板身份同步。D的export_project.py/run_m0_tests.py虽status显示dirty，主审实读规范字节与HEAD完全相等，只是检出换行/元数据差异，未混入r6提交；用户ROADMAP/H8与F3讨论保留未提交。

C真实检出template check exit0；主审固定Git覆盖快照的原静态专项exit0/3552执行断言。原r6默认Unix Makefiles构建job bash-43e1e957150d4ca8已真实completed/exit0（74336），主审核实际CMAKE_HOME_DIRECTORY/SDK/生成器、生成CTest恰好两个测试且h2显式root、新exe/两组件SHA。原CTest两个均通过，log SHA987e21d2…；主审另以相同r6组件/SDK在独立输出目录直接运行两组件均exit0，不覆盖作者原组件输出。详见out/collab/20261107-k2-implementation/independent/r6/。此前默认布局失败保留，Ninja诊断不替代默认配方。

下一步仅完成K2-3剩余有限闭合：Windows对新CMake实际配置/增量构建/精确两CTest，Linux/Windows新基线实际运行、受控一行CPP及产物身份、Linux依赖路径，汇总既有S-A/S-B/确定性/P7/P8/模块加载证据。科学算法与应用链接定义均未改，未受影响旧报告按原SHA及源字节映射复用，不循环整套实验或重写取证脚本。受控修改中不直接依赖SimulationManager的h2组件若SHA不变，必须按真实依赖登记并报主审，不额外改源码造变化，不虚称所有组件变更。主审最终按原限制签收规则处理观察范围，不自动降标签收。

GUI代码/原窗口入口未改，r5原GUI33断言按影响复用，作者r6窄GUI自测保留；正式profile/严格门禁/云CI仍属K2-4，均未由此次专项冒称通过。F3不追加批次，网页模型持续用户暂停。
