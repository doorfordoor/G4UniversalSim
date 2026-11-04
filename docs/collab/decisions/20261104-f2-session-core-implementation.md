# F2 方案 B 主审实施合同与后端派工

任务ID：F2-SESSION-CORE-20261104。用户已选择B，见20261104-f2-protocol-choice.md；本文件是主审具体实施裁定，优先于outbox/20261104-f2-protocol-contract.md的参考描述。沿用固定清单，不加阶段前置。本任务落实第三项“后端会话与重放”的后端部分；后续GUI与完整重放按原节点继续，不再次请用户确认方向。

## 已接受的设计与直接修正

作者v2已澄清请求过期、终态归属、应用层级、输出根及MT事实。仍有以下矛盾，直接按本裁定实现和测试，不再写第三轮只读提案：

- 原生/gps/*、reset/isotropic/preset及未证高级源**在新协议中拒绝**，不是“允许但不可审计”；旧csh仍按原行为。每进程固定输出根/线程/实际后端run_name，run_label仅记录元数据，不混成配置。PreInit与内核Idle单独记录；首次初始化时机明确，不能把未初始化Idle冒充可执行point/plane状态。
- 取消不能等BeamOn返回后才由主线程处理队列。reader在收到合法、匹配当前run的控制请求时原子登记cancel目标；事件所有者在事件边界读取，回执取实际run终态。busy到达时的set/run不得悄悄在下一轮执行。worker只能用其线程本地RunManager；不能从reader调用Geant4或跨线程改master状态，不把MT的1worker换成串行模式掩盖问题。
- 可候选路径：各worker的EventAction在完成本事件记账后，对自身TLS G4RunManager调用soft AbortRun(true)，每个worker见共享的当前run取消标志后自行停止；必须实际验证1及多worker、取消后下一轮、迟到取消与计数，未验证不发布cancel支持。该路径是待实测指导，不是现成成功证据。参考官方v11.3.2 G4RunManager.cc:636、G4WorkerRunManager.cc:255附近，文末链接。
- 旧请求缓存淘汰后明确expired；进行中及终态的重复run都不能再次执行。id/request_id/body冲突与最高已接收序号均要有定义，不只缓存“已完成请求”。run_finished始终归属原run_request_id，取消只附自己的ack/来源；每run唯一终态。
- 不能用event_edep的结果证明源energy已应用。配置接受、GPS对象、真实消费者、事件结果及物理验证分开；复用2C实际consumer/application_status/evidence_level，概念E0–E3不替换现有枚举。没有源消费者证据的字段保持unknown，不为本协议强制给任意用户几何增加相空间。GUI草稿revision与后端revision明确分域。
- 产物基于OutputManager真实登记的scope/run ID，逐run数据关闭后发布收据，不只靠猜文件名/目录glob或提前引用最终摘要。指定记录目录在输出根外；需要逐轮证据时记录失败必须明确使会话/记录失败，不只warning却给成功资格。模拟完成事实与记录失败事实分开。shutdown/EOF/损坏帧须有界关闭reader并保留可核对终态，不detach活线程。支持的事件数沿用现有合法范围，不无故硬限100000。
- 输入使用可靠、固定版本的JSON解析器。仓库无现成解析器时允许引入一个有明确官方来源/版本/SHA256/许可证的单头解析器（如nlohmann/json）；纳入include/ThirdParty/*.hh及构建身份，必要时补CMake头文件输入。处理合法Unicode转义、重复键、非有限/越界数字、超长/截断、未知字段；不写仅支持几种转义的“约200行JSON子集”冒标准协议。不要安装系统依赖或引入通用通信框架。
- 重放仍是本次F2实施范围，不能引用v2第243行“非本阶段实施”。本节点先完成可核对的会话请求/逐轮记录及初态保存接口；完整生成/严格比较在后续原节点完成。完整随机引擎初态/线程/构建/数据及执行顺序须可核对。已允许的时间/性能字段排除见../reviews/20261104-f2-protocol-contract-review.md，不删物理统计列或用容差。

## 目标及可写文件

在现有D盘roadmap/F2-controlled-session实施最小完整后端会话：版本协商、有限源编辑、三轮、逐请求拒绝/去重、逐轮身份和原产物绑定、运行中控制/取消、正常关闭/EOF/异常及旧入口保持。GUI在后续内部节点接入，本任务不做UI或布局改造。

允许修改：main.cc；新增include/Core/SessionServer.hh、src/Core/SessionServer.cc、include/Core/SessionJson.hh、src/Core/SessionJson.cc；必要的include/Core/BackendCapabilities.hh、include/Core/SimulationManager.hh、src/Core/SimulationManager.cc；include/Source/SourceManager.hh、src/Source/SourceManager.cc仅增会话安全校验/实际读回，不改旧行为；include/Actions/RunProgress.hh、src/Actions/RunProgress.cc、src/Actions/EventAction.cc、src/Actions/RunAction.cc；include/Output/OutputManager.hh、src/Output/OutputManager.cc、include/Output/RunSummary.hh、src/Output/RunSummary.cc；CMakeLists.txt；如需可靠解析器，新增include/ThirdParty/SessionJsonDependency.hh及docs/licenses/session-json.md；新增scripts/test_session_protocol.py、scripts/test_session_cancel_mt.py、scripts/run_m0_tests.py只注册新例；docs/会话协议.md；docs/collab/outbox/20261104-f2-session-core.md。调试/构建/自测原件放out/collab/f2-session-core-20261104/。复用当前已就绪构建环境、Geant4数据。

禁止修改几何/物理/计分公式、旧csh/batch命令守卫及语义、现有测试断言/阈值、CI、GUI、首轮实验原件、原阶段通过报告。不同源模式/单位/非有限值要预校验，拒绝不变缓存；不可证明恢复的执行异常终止会话。需要最小增补文件时先在回执说明对应原目标及理由，不泛化工具。

## 自测和交付条件

1. 可构建，真实同一进程A/B/A三轮及每个允许字段的内核消费/收据身份；独立原始行可核查。新后端的source_fingerprint及实际exe SHA明确。
2. 非法/未知/多源/延迟高级源/运行中set/run等请求被明确拒绝且不改变配置；下一次合法run仍按原配置。未知/非法数字/重复键/Unicode/管道分片与超长错误有实际断言。
3. 重复run（进行中、终态、过期）、body冲突、revision冲突、唯一终态/来源实际验证，不靠人工日志确认。
4. 当前实际MT构建下1worker及至少2worker取消、迟到取消、下一轮、Idle cancel、EOF、父端保持stdin打开时shutdown有界退出，检查所有自有进程。真实错误保留；不写skip、不伪造cancel能力。
5. 输出F1登记不被附加收据污染，逐run文件真实关闭/身份存在；记录失败、输出失败、最终摘要与单run收据分别核对；旧csh/批处理/随机状态及摘要相关专项回归通过。只跑相关专项，自测不代替主审正式矩阵和实际窗口。
6. 报告列修改文件、问题/限制、实际执行命令、用例结果、失败原件、代码/构建/配置身份和下一GUI/重放对接契约。tests按现有断言探针与证据门禁接线，不造新平台。

不提交Git、不推送、不切分支。完成后冻结文件并回信，等待主审独立复验；主审会继续下一内部节点，不要求用户逐项继续。不要先扩展GUI/重放比较器/新框架；本节点结束条件为上述后端与相关正反例完成。

你是本轮执行负责人，请有信心把这个高级科研项目做完整、清晰、美观、快速、易用。unlimited Token，不限子智能体数量，充分发挥设计和工程能力，充分实现与验证。实际平台限制以系统为准，不为消耗而重复工作。完成约定范围，范围外想法记入建议。

官方源码定位（只作为实施指导，实际取消须本项目验证）：[G4RunManager::AbortRun](https://github.com/Geant4/geant4/blob/v11.3.2/source/run/src/G4RunManager.cc#L636)、[worker事件循环](https://github.com/Geant4/geant4/blob/v11.3.2/source/run/src/G4WorkerRunManager.cc#L255)。
