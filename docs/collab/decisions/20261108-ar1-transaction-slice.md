# AR1 第一切片：几何加载事务

2026-11-08，依据[AR0 r3冻结](20261108-ar0-r3-freeze.md)。本轮只实施加载事务及真实反例；box/tubs规范参数为下一小切片。完成本切片后先冻结候选独验，再接续AR1；不把单个切片完成称AR1整体通过。

## 范围与单写者

实现者可写`include/Geometry/GeometryManager.hh`、`src/Geometry/GeometryManager.cc`及必要的真实组件探针`tools/geometryTransactionCheck.cc`、注册/包装`CMakeLists.txt`、`scripts/test_geometry_transaction.py`和`scripts/run_m0_tests.py`中的本项注册。若必须增加其他生产文件，先说明真实调用依赖与最小差异。主审负责docs状态和independent证据；实现者只写`out/collab/20261108-ar0-ar6/author-ar1-transaction/`中的自测记录，C独审区保持不动。

保留D盘既有dirty；不全仓暂存/提交/推送，不改模板到半成品，不调用DS/web。现有公共格式/别名/诊断语义保持；不改物理构造、统计、J4/F3。需要CMake组件接线是本真实接口探针的依赖，不借此提前重构AR5目标。

## 反例与观测合同

用真实GeometryManager/模板公共接口建立A和用户体积，再调用LoadGeometryConfig(B)：

1. B本身合法，但用户体积与B已有体积重名。
2. A上合法的用户体积，其parent在B中不存在。
3. 两个用户体积中，第一个可叠加，第二个失败，证明不会留部分树。

先在未修复生产实现上执行，保存输入/探针/源码身份、原输出与失败断言；若某路径不可达，明确真实拒绝点，不用静态推测作失败实测。脚本默认报告回归通过与否，不把预期发现旧bug的非零退出洗成绿色。

每例捕获加载前/失败后的模板树、最终树、用户体积/保留策略、成功文件路径、accepted inputFiles/effective reader/字段/generation、dirty和registry身份。优先现有只读接口；确需测试访问未公开的模板/reader时只用窄范围只读探针，不让快照调用创建Geant4对象/修改状态。调用前可用ClearDirty建立false对照；完整A树和来源须相等，不只比较root指针。当前真实Registry可保持空；该测试不冒充已构造Geant4世界的热重建回滚。

失败诊断允许更新；全局bytes-read ledger保留B实际读取条目且不能升级成accepted/applied。全局registry revision在本调用没有有效提交时不推进；不虚构Manager本无的revision。此前成功SetTemplate/用户编辑独立保留。

正控：有效C成功时模型与来源整体更新、generation按原合同推进、dirty为true；保留/清空用户体积策略分别覆盖。非法解析/早期校验维持created_geometry_object_count=0。状态和输入字节证据均来自本次实际调用。

## 实现与自测

先构造候选模板树、叠加后的最终树、用户集合、路径/输入/reader及effective接受字段；所有可抛异常准备完成后再整体发布。ConsumerState::Accept含分配，不能在换树后调用未保护的Accept。避免临时交换进有效对象再依靠可能抛异常的回滚；失败保留所有有效状态，成功保持原来源/运行证据语义。只处理LoadGeometryConfig边界，不把SetRootNode/AddVolume/Geant4热重建全部纳入本轮。

组件目标不改变standalone现有两个component集合；新测试若需仓库专有工具，置于相应非standalone条件。自测先反例/成功/来源断言，再当前候选几何安全/诊断和effective_geometry_materials等直接受影响入口。实际构建使用已核D根的CMake cache和真实Geant4；长命令保留session/日志，不重复启动。新源码、测试及候选二进制/输入/报告SHA均入收据。原失败保留；交付后冻结文件，主审在C树同步明确候选后独立复验。

交付：完整改动清单、反例修前/修后证据、实际命令/退出/断言、剩余限制和运行中进程。实现者不自签阶段验收；主审通过后再形成可回退切片提交并启动box/tubs。
