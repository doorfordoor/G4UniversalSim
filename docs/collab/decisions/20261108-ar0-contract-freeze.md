# AR0基线与比较合同独立验收及冻结

2026-11-08：AR0通过。作者r1未通过独审，修订r2与以下主审权威附注共同构成冻结合同；冲突处以本文件为准。不是产品实现、运行时或物理验证验收。

## 身份与证据
基线25487eb13432c5f4e968aa405607056f6a8febce，固定标签k2-closed-pre-architecture-20261108不移动。最终r2 SHA-256：c873566f74e5d7f247cb02fe484375d493f4a22798479c4b97ce60705a084a2d，71226字节/492行/LF。作者receipt与最终文件一致；round188/turn137 completed、task idle见out/collab/20261108-ar0-ar2/task-final.json。审阅期间中间文件发生换行及行号修订，早期f3d4175b/c15b18c9/4bf06177不作为最终冻结身份。最终原件存independent/ar0-contract-r2-final.md。

主审已核40份源码哈希、生产者/消费者/线程/所有者/失败语义，几何与计分两路独立只读复审已完成。原r1及拒绝记录保留；源码关键依据GeometryManager.cc:234–266、VolumeBuilder.cc:496–534、SolidRegistry.cc:29–40、ActionInitialization.cc:78–104、ScoringManager clone、HistoryStatistics.cc:11–18、ScoringParallelWorld.cc:74–102。最终r2修正主要事实，下述残留由主审核源码后直接定稿，不增加验收范围。

## 权威附注（实施前必读）
1. I2所有权：Geant4管理solids/logical volumes生命周期；GeometryRegistry是运行时可变的非拥有索引；VolumeBuilder持有辅助资源。只有SolidRegistry描述表为静态只读，不能把整个registry称编译期只读或最终对象所有者。
2. H3 ScoringParallelWorld直接构造G4Box/G4LogicalVolume并维护自身索引，不是质量世界VolumeBuilder/GeometryRegistry直接消费者。仅按共享语义实际影响补验证。Python GUI预览也不直接调用C++ builder；box/tubs表的“如GUI/代码路径”按“C++ VolumeNode代码路径”理解。
3. geometry_safety既有测试不能证明新事务保证；A→失败B后的树/覆盖/effective/revision/dirty对照由AR1新增实际接口探针覆盖。LoadGeometryConfig候选提交范围不扩为任意Geant4热重建回滚。
4. §9严格相等受§10限定：同配置、同算术顺序的可确定量才严格比较；其它沿用原数值/科学判据。entries为非零贡献history数，n_events含零贡献history，不能要求entries等于完成事件数。history按scope/run/thread归属，正确合并后对账。
5. §8.6拆分H3工程与科学入口：scripts/test_parallel_world.py只覆盖工程语义，不执行B/C预注册科学批次。B/C沿用docs/collab/reviews/20261107-h3-benchmarks-acceptance.md及docs/verification/h3-final-20261107/README.md的原72项manifest/程序身份、输入种子和完整99%区间；AR2若实际影响这些量，先从原out/collab/h3-4-independent-r3定位完整可执行入口并写入该项任务，再按原判据验证。不得用parallel_world工程通过替代B/C科学等价，也不因此在AR0重跑科学批次。
6. 模板309成员是旧身份，不是改造后固定数量；稳定候选重新生成实际manifest并独核。Q2通配引用仅索引，受影响任务须落到原具体合同/报告，不创造或放宽科学阈值。

## 验收与下一步
真实接口表、现有输入/源码/环境/报告身份、有限比较矩阵、自然差异白名单、数值与科学边界、回退和范围决策均已具备。冻结合同为r2加本附注；AR0不要求提前完成AR1事务探针或AR2工厂。未新增构建/运行/性能批次，产品内容未改，旧测试仅按原SHA引用。
允许新主审从AR1开始，先实证A→失败B，再最小事务与box/tubs切片；AR2随后。第一批完整验收后向用户汇报并暂停。AR3以后、网页模型恢复、F3追加测量均未授权。本对话在此交班，不另行派AR1。
