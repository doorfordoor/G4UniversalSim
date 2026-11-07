# H3-1 独审冻结决定（2026-11-06）

状态：通过。冻结修订稿 docs/collab/outbox/20261106-h3-contract.md，SHA256 07b71b010c74df19b09cb475e9cb94b14c1e87c4d3a0552cb7993107897d7c34，原件out/collab/desktop-bridge/h3-contract-r2.md。本决定与修订稿共同构成合同；有冲突以本决定为准。首稿失败与8点独审保留，未运行正式病例、未看到结果调整判据。

## 独审结论
真实消费者复核：ScoringManager.cc:685的既有ScoreHit包含事件累计/hits/全scorer广播，修订稿专用ScoreParallelHit限定dose/fluence可避免污染；ActionInitialization.cc:98绑定线程本地manager。Geant4 worker调用ConstructParallelSD事实已在首轮独审确认。规则grid、参考质量、Stage A/B验证、完整Welch区间与离轴探针已补齐。采用box质量世界与box/grid平行几何作为本阶段最小范围；其它组合显式拒绝，不据此声称物理机制不支持。

## 主审定稿细节（实施与基准直接遵守）
1. 线程：每线程创建SD，不在共享对象保存可变SD/manager指针；Hit只取当前线程manager，缺失即失败，不回退master。Case M固定同一进程200/50事件、2线程，独立worker累计与跨run隔离必须通过。重复进程仍按合同执行，但逐worker SHA仅诊断，不以调度变化判inconclusive或失败；用每run完整事件集合/计数无重复无遗漏、各worker同一事件N以及合并四量/事件矩检验。run N对每个worker只计一次，不能把不同volume或scorer行的N再次相加。无命中worker允许header-only，不能强求非空体积行。该规则解决草案§5.9/§8.6残存逐文件哈希门槛。
2. 隔离反例：R-SAME使用同一次运行的质量侧hits复算event_edep，不能拿另一次mass-only随机轨迹作精确比较。Case A的hits=true用于该断言，另有hits=false正常自测；物理输入不变。R-RUNTIME沿用Case A的源/物理/单worker/2000事件/seed20261400，仅质量层sensitive=false且hits/event_edep=true。R-COMP须保存真实专用入口负控。无需新测试框架。
3. 输出：路径一律按touchable完整路径，所有层含#copy，例如/ScoringWorld#0/SlabGrid_0_0_0#0。声明名称与派生单元名称冲突、不同grid/volume空间交叠必须预检拒绝；相邻边界接触允许。计数乘法/单元长度、质量/体积数值有限与溢出检查在构造前完成。上限4096为本阶段工程边界。
4. 空贡献：沿用H2稀疏输出，不为满足Case A2的16行字样伪造命中。构造收据必须证明16单元全创建；汇总时明确缺失单元贡献为零并验证无相关记录，已出现体积行N必须完整。已出现谱使用现有10bin+上下溢桶规则。事件矩/零贡献计入N不改变。
5. 质量材料：只在整个计分box与质量材料域对应已被证明时可写material_matches_mass_world=true；只查中心点或材料名同名不足以证明整个box一致，无法证明记unknown。Case C真空探针为诊断，不称水剂量病例。实际world必须为G4Box，采用真实半长与位置做包含复核，避免任意非凸solid包围盒假通过。
6. 统计：B/C整段Welch99%差值区间须在既定±1%/±0.5%均值域内。均值分母必须正且有限；SE=0两组常量按退化区间[Δ,Δ]明确处理，不能NaN通过。Case A/A2/A2f失败先修接线，修复保留失败并以新身份复验，不以禁止重跑为由卡住。不可改种子/加批/改阈值追通过，科学inconclusive不算通过。
7. 配置拒绝在batch/csh/受控session所有入口实际BeamOn前保持，包括初始化期出现的失败；已有输入SHA快照必须记录真正使用字节。配置/schema消费者、摘要和测试各自接线，不只生成字段。不启用保持旧科学输出语义。

## H3-2授权范围
只实施后端、配置/schema及对应自动测试与必要接口说明。允许include/src下Detector/Geometry或新ParallelWorld模块、Core/Physics/Scoring、Config/Output相关接线、CMakeLists、schema生成物、scripts/tests/tools与小型示例。不要重构无关模块，不改H8 ROADMAP、CURRENT、固定清单和GUI。H3-3随后单独派工；H3-4正式统计批次随后按冻结合同运行，本次只组件/小型运行/错误路径自测。回执docs/collab/outbox/20261106-h3-backend.md，记录diff、构建身份、测试命令及真实结果、剩余问题。完成即停等待独审，不自行宣称H3阶段通过。
