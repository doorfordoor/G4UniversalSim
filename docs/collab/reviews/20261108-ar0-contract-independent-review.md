# AR0合同独立审查

2026-11-08。r1结论：修订后复验，尚不冻结。主审及两条非网页只读审查线核对真实源码；本次无产品构建/模拟/性能测量。40份作者源码SHA全部一致，生产范围git diff HEAD无内容变化，见out/collab/20261108-ar0-ar2/independent/。

## r1发现与最小修订
1. GeometryManager.cc:234–267先替换树，再合并用户体积，之后才发布来源和dirty；草案时序/头文件引用错误。GUI为Python模型/PyVista，不直接共享C++ Manager。Manager拥有VolumeNode，Registry是非拥有Geant4指针索引；BuildWorld前后阶段影响不能一概写旧状态丢失，未运行不能称实测。
2. box/tubs的INI、直接builder、boolean工具入口语义有差别：分别核GeometryConfig:588–599、VolumeBuilder:496–534、SolidRegistry:29–40，需固定小表。
3. ActionInitialization::Build:78–104 sequential与worker都clone。自定义对象漏构造不能只讨论MT。ScoringManager.cc:235–273复制设置并EnsureDefaultScorers，不复制scorers_，该核心问题静态成立。
4. ROOT分析实例按当前线程及既有合并协议使用；DoseScorer本地events_不是metadata全run总数；计数对账按scope/run/thread，允许线程调度变化时先比较事件集合/归并量，不能强制每线程文件完全相同。
5. 主INI未消费字段有告警合同，不能全部改写fatal。无控件状态迁移属于AR4；本批交付验证按影响，不预先排除完整包。
6. G5/7/8/9继承现有公开合同，不另开schema/GUI功能；tracked dirty与含untracked总数不同不是矛盾；本地bridge拒绝不证明CI网络不可用。环境分清Geant4 Qt与GUI PySide6。
7. 比较矩阵需实际脚本/case/参数/fixture和科学判据路径，不能泛列测试家族。

上述修订以ar0-contract-review-r2-20261108请求交作者，round188已接收。r1合同和回执副本保留independent/ar0-contract-r1.md、author-receipt-r1.json。主审冻结方向：候选几何整体提交；可重建scorer工厂覆盖sequential/worker；公共格式不变；稳定候选更新模板，按影响补证；基线生产源以tag及实际文件SHA核对，既有文档dirty保留。AR1真实失败复现和AR2运行比较属于后续实现验收，不冒充AR0已做。
