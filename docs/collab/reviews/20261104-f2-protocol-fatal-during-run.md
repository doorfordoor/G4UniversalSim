# F2 原合同坏帧/EOF失败传播：必须最小修复

阻断原固定清单第三项及GUI错误/断线验收。不是新增功能或提高标准；20261104-f2-session-core-implementation.md已明确“shutdown/EOF/损坏帧须有界关闭reader并保留可核对终态”“协议错误非零退出”。A–E的限定通过结果保留，但不能扩大为所有协议错误路径均完成。

## 真实反例（确定为缺陷）

C盘独立冻结513117f3/clean、C++指纹d8e1081f…，2worker真实run计划200000事件。收到run_started后写入损坏行`{"kind":\n`并关闭stdin：实际完成2事件，run_finished=cancelled，**进程exit0，无任何protocol_error帧**；最终摘要aborted/exit0。模拟部分完成事实未伪造，但坏帧失败被EOF路径吞掉。

原始输入、输出、收据、报告及探针已逐SHA复制到D盘out/collab/f2-protocol-fatal-r1/，manifest.json登记原字节。report.json的passed=false是产品反例；驱动退出0仅表示观察完成，不算验收通过。探针借用现有测试的传输client，反例操作/判据由主审独立编写。

同一EOF路径另有最小截断反例：hello后发送未换行短残片`{"kind":`并EOF，仍exit0、无协议错误；原件short-fragment-eof/。这属于原合同的截断帧处理，不新增协议模式；EOF不能静默丢弃未解析残片。

定位：src/Core/SessionServer.cc:478–559的ReaderLoop只将Fatal放队列，运行中未立即锁存协议失败/中止意图；EOF分支设置eofShutdown，而1442的返回绕过尚未消费的Fatal队列，最终main.cc:845按sessionCode=0结束。超长未换行分支也会入队后直接退出reader，当前BeamOn可继续很久。

## 最小范围、动作与停止条件

- 只允许修改src/Core/SessionServer.cc及scripts/test_session_protocol.py/必要的scripts/test_session_cancel_mt.py新增此组回归；必要的SessionServer.hh仅声明小辅助。当前GUI任务继续，主审明确授权此一个原合同缺陷的C++补丁，不扩其它后端工作。
- 读取线程发现致命坏帧/超长帧时立即锁存协议失败，按已有原子取消标志令当前worker在自身事件边界受控结束；reader仍不得调用Geant4。复用已串行化的记录和发送；坏帧须留输入原文，协议错误至少一次可见，不能被EOF或普通取消覆盖。不要复制一套协议框架或重构Reader。
- 同时核对有换行坏帧、超长未换行和短残片后EOF这些既有坏帧路径；有当前run时保留唯一终态和实际部分计数，最终明确failed/非零退出，不执行后续合法run。正常EOF与用户取消保持原有区别和行为。
- 永久回归覆盖“坏帧+EOF”“超长帧（stdin保持打开）”的实际有限退出、协议错误及无后续run；普通EOF/合法取消正例不回退。不得通过测试端主动kill冒充后端有界退出；若失败，保留原输出。
- 修复后只重建实际受影响目标、相关新/兼容专项；GUI继续用修后的真实exe。CPP修完后不扩新工具/功能，立即回原GUI清单，完整候选交付后由主审独立复验。

本项停止条件：上述反例非零退出并可归因、有界清理/唯一轮次终态、正常取消/EOF回归通过。磁盘压力、更多源模式、一般重构一律不插入。
