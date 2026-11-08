# AR3 连续实施切片（2026-11-09）

用户已授权连续推进，不逐项等待确认。AR2主审签收及回退提交4efaf9837f056f551aa230db1598403745eab061已完成；本决定启动AR3，不代表AR3或MR1通过。合同沿AR0 r3 §5及architecture-principles-adoption，审计映射沿后续开发总规划。

## 第一片：已加载配置协调

采用只读准备 `out/collab/20261108-ar0-ar6/ar3-preparation/config-coordinator-plan.md` 的有限边界。将SimulationManager::Configure中已加载INI的配置协调移到无持久状态的ConfigurationCoordinator，保留公共外观、Manager及字段唯一拥有者。非拥有引用束只在同步栈调用内有效，不接整个SimulationManager、不新建配置状态副本/服务注册器/DI容器。

保持运行/输出输入、材料/几何、物理/region、场、源、计分/mesh、偏置、parallel与兼容字段消费的实际顺序和首异常停止行为；LoadConfig、BuildManagers、CLI重应用、模块模式、effective来源与configured发布仍在原合法时点。不是一次新的全局强事务，不暗中增加全局回滚。

Jason拥有新增include/Core/ConfigurationCoordinator.hh、src/Core/ConfigurationCoordinator.cc及src/Core/SimulationManager.cc；必要的共享兼容键助手可抽为单个有名Config头，但须先报告具体路径/消费者，不复制别名规则。其它产品/测试由主审持有；不在第一片更改main、SessionServer、Action、Output或Scoring。

实际移出语句/副作用逐项映射，真实source/模板闭包、构建、CLI/macro优先级/状态守卫、受影响effective及运行摘要/csh有限矩阵，独立审查后收口。纯移动不能冒称新的行为功能，后续target/include边界仍需AR5实证。

## 后续切片及最迟出口

1. 运行会话/收尾协调与资源结果：保首因、最终化最多一次、configure-only/inspect/dry-run/batch/csh/session分流；ROOT Write抛出仍须尝试Close，早bias拒绝不得发布未启动计时。有限资源适配和真实异常负控，不造通用清理框架。
2. 审计：AUD03缓存扫描/会话互斥及所有者释放；AUD09 B4低能低计数；AUD10相空间实际离子电荷及旧CSV兼容策略；AUD16 B3证据信任；R2-11空白负seed。AUD02共享证据与R2-10发布结果先完成服务合同，AR4消费者必须接线。
3. 每个公开格式变化先写精确兼容决定；禁止从PDG猜缺失charge可无损恢复。不得为通过临时放宽统计或输出身份标准。

具体切片作者/文件、测试和影响分析随实现登记。每片验证深度由实际改动决定，保留失败、不把旧身份套新候选。AR3整体独立验收后，当前主审对AR1–3累计diff/运行证据/修复做MR1，再进入AR4；MR1不得交由子代理签发。
