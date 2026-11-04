# F2 协议合同首审与修正范围

2026-11-04。首轮实验8例独立通过，详见20261104-f2-baseline-independent.md。合同v1是设计材料，不是实现。主审推荐版本化方案B的方向；以下六组具体矛盾修正文档后交既定协议选择，不新增阶段清单或泛化工具。

1. **执行线程须改正（确定为缺陷）**。合同§4.2/§3.9认为“threads=1时EventAction在主线程”，但main.cc:567–574在MT构建无条件创建G4MTRunManager，再设worker数量；1 worker不是G4RunManager串行模式。不能把worker上的AbortRun当成主线程操作。按实际MT run-manager类型设计事件边界取消；若安全路径待实测，明确记录未实现，不写已可用。也不能悄悄切成串行run-manager再用旧batch MT路径宣称逐位重放通过。给出来源与实施时的单/多worker原验收路径即可，不先写产品、不要求现在另造试验平台。
2. **请求去重和终态归属须封口（确定为缺陷）**。§3.4仅缓存最近16条，未说明旧ID被淘汰如何处理：过期旧请求必须明确stale/expired，不能再次执行；同ID不同body必须冲突，同body重复应在revision/busy判断前去重。统一id/request_id定义并补齐样例。原run请求的唯一run_finished必须仍归属run请求，cancel有自己的ack及cancel_request_id，不能像第126行把run终态改挂cancel请求或发两份。
3. **应用层级与输入代次分开（确定为缺陷）**。第107行status=applied/gps_updated但kernel_evidence=E1 manager_state，第238–243行又禁止如此显示，互相矛盾。仅Manager接受应是configured/accepted，不能作GPS更新证据；真正GPS/消费者证据用现有EffectiveConfig application_status/evidence_level表达，逐run绑定，不要求任意科学配置自动生成相空间。GUI编辑revision与后端state_revision属于不同域，只记录映射，不直接相等。未知内部执行异常若发生于可变状态更新之后，除非能证明恢复，否则终止会话并保留unknown/failed，不能返回可继续的rejected并留下被改缓存。
4. **输出与现有合同相容（确定为缺陷）**。run样例有run_name/threads参数，表却说不能改；第184行每轮换round-b/output违反现有输出目录PreInit守卫。首版每进程固定线程/输出根，沿用现有_rN产物；若run_label只是GUI/会话元数据要明确不冒后端run_name。每轮终态须在worker/master输出关闭后绑定本轮真实文件，不能提前引用仅会话退出才写的最终run_summary。replay/收据放输出根外的记录目录，不依赖“logs子目录一定豁免”假设，不改变F1 generated_files规则。
5. **运行中控制与关闭（需实验，设计应明确）**。主线程beamOn阻塞时谁负责busy/error/ping/cancel应答须写清；按队列处理而不记录到达状态，会让运行中set在下一轮被悄悄执行。reader只按不可变协议状态拒绝/入队，Geant4调用仍由其所有者执行；延迟处理时重验run/revision。协议锁不能保证G4cout使用同一锁，不能承诺任意日志都绝不插帧；保留现有进度，写帧完整串行并对损坏帧明确失败/未知。stdin阻塞读线程在shutdown后即使父进程还保持管道也必须有有界正常join/清理方法，不用detach存活线程规避。说明实际解析器的选择与有限/重复键/超长帧错误，不必扩通用通信库。
6. **重放判据（需实验，不降标）**。主审额外两次固定seed1904、1worker的A/B/A比较：24个CSV中21个原字节相同；另3个scorer_statistics只fom_per_s/run_wall_time_s不同，所有剩余物理字段严格相同。原始全字节比较失败保留，不是产品缺陷；原F2计划已允许去除时间等非确定元数据。比较器只显式排除这些时间/性能字段，不删除物理统计列、不用容差冒逐位。完整引擎初态尚未捕获，本实验不代表最终重放。MT仍须按原计划实测及列差异，不以无事件键为由自动豁免能精确比较的聚合统计。

允许本修正文档：docs/collab/outbox/20261104-f2-protocol-contract.md。v1由主审保存原字节。可补最少的原源码定位，不重扫仓库，不改产品/测试/CI、不提交Git、不新建工具。保持原三提交节点及16类验收，将上述原要求在现有条目中明确；不要扩成新验收阶段。停止条件是内部一致、能提交用户选择的文档，不实施生产入口。

你是本轮执行负责人，请有信心把这个高级科研项目做完整、清晰、美观、快速、易用。unlimited Token，不限子智能体数量，充分发挥设计和工程能力，充分实现与验证。实际平台限制以系统为准，不为消耗而重复工作。完成约定范围，范围外想法记入建议。
