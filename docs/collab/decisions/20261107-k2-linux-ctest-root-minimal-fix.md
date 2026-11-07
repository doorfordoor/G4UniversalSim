# K2-3 Linux默认CTest根目录定位最小修复

2026-11-07，阻断固定清单K2-3。候选56b1da77：原合同Linux默认single-config build_linux/h2VolumeScoringCheck的CTest先因SDK数据环境失败，激活SDK后仍因夹具根目录推导失败。主审核tools/h2VolumeScoringCheck.cc:755–759：缺第二参数时固定从exe取三层parent，Windows build/Release/exe成立，Linux build/exe却多上一层。CMakeLists.txt对h2只传输出目录，未传已有受支持的第二个repository参数。证据原bridge hb1128-transcript.json的73862–73926；原错误与中间脚本exit0误读均保留，不算通过。

最小修复只改CMakeLists.txt的h2_volume_scoring_check COMMAND一行：在原输出目录参数后加显式${PROJECT_SOURCE_DIR}，复用现有argv[2]，不改tools/h2VolumeScoringCheck.cc、不删断言、不复制表到导出树外、不修改输出目录布局或SDK。scripts/test_k2_project_export.py只增加原导出CMake命令包含该根参数的窄回归；packaging/export_template_manifest.json按新真实CMake字节重算，必要构建说明只同步实际事实。其余产品文件、科学实现、契约标准、K1/writer保持。

新CMake属于编译身份输入，必须真实记录新source_fingerprint/产物身份；旧编译/运行只按原身份保留，不伪造为新构建。复用既有SDK/构建环境并只补受影响的configure/增量build/CTest；主审独审冻结修复后回原K2-3。已启动Ninja Multi-Config job bash-fd7cfb85db404a26可正常结束收据，不打断、不重启；其结果仅作额外诊断，不替代原默认single-config命令通过。停止扩大验收脚本/生成器尝试。

停止条件：仅此一行产品修复与原窄专项自测、author-r6回执/outbox完成即停写，主审独核冻结后恢复原K2-3剩余有限矩阵。原Windows依赖捕获exit=null不能冒0；已正常完成的直接运行与模块路径观察可分别保留，不反复重写启动器。F3禁止新批次，网页模型保持用户暂停。
