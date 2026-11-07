# H3-4 网格计分差异最小前置诊断（2026-11-07）

阻断项：固定清单H3-4（A2/A2f四量守恒）；H3保持未完成，不作限制签收。

反例：现有9daf3d22后端、源码指纹9523b987，冻结4x4x1网格/10MeV质子/seed20261465的20事件接线诊断：质量世界加权沉积200MeV，网格四命中单元合计143.08371916006MeV（少28.45814041997%）；长度24.7737095206mm对14.60995595524mm。A2f质量proton hits独立和199.999999999993161764MeV，与质量量一致。输入、18文件源码/CSV/原摘要SHA与独立复算保留out/collab/h3-4-grid-diagnosis-r1。此为诊断，不冒充2000事件正式基准。

允许最小文件范围：临时诊断仅src/ParallelWorld/ParallelScoringDetector.cc、src/ParallelWorld/ScoringParallelWorld.cc及本证据目录。先保留两文件和程序原字节/SHA，再作一次有明确假设的步级观察：cell与ghost world收到的event/track/step、pre/post体积与位置、edep/length，确定缺失是否出现在未挂SD的ghost world。临时world SD只记证据，不进入生产计分、不伪造可用物理结果。不得改ScoringManager/Dose/Fluence算法或正式输入来掩盖差异。

停止条件：原20事件/原seed/原网格最多一次此诊断，给可独立求和的证据并停止等待主审定位结论；不继续尝试移动源/改grid/换种/放宽容差，不新增通用跟踪或验收框架。主审核实后另给最小产品修复范围，临时trace必须从最终候选移除。修复后回到原固定H3-4批次与判据，所有旧失败/诊断保留。
