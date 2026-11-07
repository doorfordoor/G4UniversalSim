# H3-4 网格漏计逐步定位独立复核（2026-11-07）

定位结论：计分实现未覆盖 ghost pre-volume 仍为world、但预步位置处于已声明网格边界/内部的步骤。旧world未挂SD，Geant4不会将该步送到项目ScoreParallelHit；不是CSV简单加总选错。此为修复定位，不是H3-4科学验收通过。

主审独立读取trace.csv（SHA256 9c36d6b3b3baf89f42ff81f82fcfc040614baeab3b54863bb0f58bdfd4efb37a）：329行event/track/step键无重复，W79行/C250行；W中59行预步在薄层参考范围内，能量56.916280MeV、长度10.163753mm。原缺口分别56.91628083994MeV与10.16375356536mm，落在逐行六位小数±0.5e-6的求和打印区间内；world外部步沉积为0，20个事件均含漏计world正沉积。

原trace只保留六位小数，不能称12位有效数字精确闭合；本复核按其实际打印精度，未重跑模拟。独立计算与源码恢复核对为out/collab/h3-4-grid-diagnosis-r1/independent-trace-check.json。该诊断程序SHA5f43e9e35fefeb57be5adfaad062520e345cdf23e1c4cb0bb82ec2e00767f80c，不是旧9daf候选。两源文件已恢复并与原快照一致；重建后二进制SHA06626dfa1e0c31c29c10ddf17750cfe5ae9d2b7cb3a4da4540d67dac3a0dce10，不能冒充旧9daf字节相等。

允许的产品修复：保持全部输运几何/源/种子/物理/质量定义/既有PV层级与名字、copy号及输出字段不变；对world ghost步只在实际已构造计分box内恢复唯一预步归属，引用真实PV/变换得到路径，明确处理边界，保留专用计分路由与权重一次、事件N原语义；world外部/gap不计分，已正常leaf步不重复计分。不得拷贝质量剂量、补比例、移动源/网格、增加单元重叠或伪造touchable字符串。路径恢复语义须在现有中文文档诚实说明。

最小范围为src/include下ParallelScoringDetector、ScoringParallelWorld四文件，现有scripts/test_parallel_world.py与必要组件回归、docs/并行世界计分.md及本项证据。若需改动其它产品算法，先给具体反例和最小理由。原A2/A2f20事件同seed复演及域外负控、受影响既有专项后立即停写独审；随后回到原H3-4正式输入/判据。原所有诊断/失败保留。临时trace不得留进正式候选。
