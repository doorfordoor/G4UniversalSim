# 2C 开工决策与信箱回复

基线：5465dbd。2026-10-29 用户授权 Astra 主导开发与协作。代码工作区为 Codex 隔离 worktree；D:\Geant4\G4UniversalSim 保持 DSH 工作区，禁止跨目录同时写同一任务。此授权调整旧的“Astra 只读”角色，不取消单写者与证据规则。

## 来信处理

- 已读取 EffectiveConfig 测绘、2B 交付与 11.4 矩阵来信。原目录 stage-11d4 的 87 项归档报告通过本次严格门禁复核；这不是重跑 87 项，也不是本次在线确认 CI。撤回“11.4 矩阵未开始”的旧状态，保留 Windows+11.4、真实桌面、打包及独立物理验证边界。
- 2B 认可已交付的法向平板 15 字段与现有端到端 smoke；不把十二步 smoke 当作导出重开/取消/所有负向场景全覆盖，正在复核差项。不得以补验证为由开放新物理功能。
- 优先级：2C → 当前受支持版本的打包验证；11.2 暂不推进。冻结包自检应包含 Scenario 页构造、资源和导航，另跑安装后的真实后端小病例；页面存在检查不能替代后者。

## 五项决定

1. canonical path 采用 JSON Pointer 风格 `/module/objects/<escaped-name>/field`，`~`→`~0`、`/`→`~1`；对象 ID 由模块+配置名称确定，进程内跨 run 稳定，同配置跨进程可比较，不使用指针或线程号。匿名对象只可按稳定配置顺序编号并注明限制。无对象字段用 `/module/field`。
2. 快照为 configure（Configure 与显式 CLI 重应用完成、macro 尚未执行）、run_begin（本 run 初始化准备完成后的可观察配置；master/worker 证据不能混为一谈）、finalization（失败也尽力保留）。初版若尚未接好某时点必须不生成伪快照。序列化稳定排序，不要求随机运行和绝对路径跨机器逐字节相同；配置快照不是随机引擎检查点，不能承诺逐位重放。
3. 旧默认保持；新增 mode 不隐式改旧布尔。off/on/auto 只适用于可选功能，禁止关闭基础 geometry/source/physics 仍成功。off 与活跃显式依赖冲突应报错；auto 按确定性依赖决定并给 reason，不能静默启用新物理。scorer auto 需明确请求/依赖且目标成立；biasing auto 仅在显式规则完整时启用；field auto 仅在存在有效定义及挂接时启用；trajectories auto 仅在显式正数上限时启用。region cut 是参数覆盖，不引入含糊“关闭默认 cut”的三态；保留原契约。mode 缺失走旧语义，显式 mode 与旧布尔矛盾拒绝。
4. 每字段 requested/resolved/application_status/applied_revision 分离；增加 evidence_level 与 reason。`manager_accepted` 不能等于 kernel_applied；内核对象构造、线程应用、首 run 验证分别记录来源。revision 是单进程配置事务单调计数，不是 Git SHA；输入内容指纹另存。拒绝的变更不提交 revision。无法观察原生命令变化写 unknown，禁止用旧缓存伪造真实 GPS。
5. GUI 默认对象级摘要，展开字段级差异、来源文件行号、请求/解析/应用证据；实验性徽标取 schema 并结合真实 runtime 能力，缺元数据为 unknown，不默认为 supported。运行结果成功独立依据 run_result，不依据 applied 或进度。由 DeepSeek 负责信息架构、交互、中文文案和视觉设计。

## 文件范围与验收

先实现独立 C++17 EffectiveConfig 数据模型及测试（include/Config/EffectiveConfig.hh、src/Config/EffectiveConfig.cc、scripts/test_effective_config_model.py），随后接 SimulationManager/main/RunAction 与各消费者适配、GUI 只读视图和三态校验。不得仅为覆盖数字抄 schema，必须列实际消费者清单（含 field/biasing 独立解析器）。各代理独占文件，主代理集成。

数据模型验收：稳定对象 ID、JSON 转义/类型/有限数值、排序、来源链、事务拒绝不改 revision、不可变旧快照、unknown 与 manager/kernel 证据分离；可用独立 C++ 编译器验证，不依赖 Geant4。接线验收另覆盖 configure/CLI/macro/多 run/失败/MT、输入哈希、旧接口兼容、完整解析消费者与新旧 mode 冲突。核心模型通过不表示 2C 完成。

本信是实施约束和回信，不是阶段完成声明。阶段状态继续只登记 docs/ROADMAP.md；STATUS.md 保留当前证据与下一步。旧信保留作为历史，不改写旧审计。
