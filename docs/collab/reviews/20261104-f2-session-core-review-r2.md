# F2 第二后端候选限定独立复验

候选：513117f3b7d37c687e1aabc6797e7b02d8a71436；C++源码指纹d8e1081f98f485a5298c8410b33973d0533678f42551fd000c8f697d86124b91。C盘j3-final独立检出clean，重新构建Windows/MSVC与Linux/GNU 11.3.2，两个构建退出0，生成BuildInfo均记录513117f3/clean及同一源码指纹。首候选9f4的缺陷、失败报告和原件保留。

结论：**Windows/Linux11.3.2后端限定行为复验通过。Windows5/5、1266断言，Linux4/4、923断言，均0失败/0跳过并通过严格证据门禁；报告均为513117f3/clean、同一C++指纹及tests指纹bfd7cc666ad3…，tracked_source_gate=pass。** 已启动不冲突的GUI任务，C盘冻结源不变。本文件不表示完整F2通过；GUI、完整随机状态重放、最终正式矩阵/原生与云CI仍按固定清单继续。

## 首审A–E复核

| 原问题 | 修复核查 | 主审独立结果 |
| --- | --- | --- |
| A INI宏被静默忽略 | main.cc:750按Configure后实际context拒绝预置宏，未改旧入口 | 有效绝对几何及宏夹具，exit1、无welcome，不启动会话/事件；通过 |
| B 记录目录落入实际输出根 | main.cc:425、840对两目录作绝对/weakly_canonical比较，并处理Windows大小写 | 相对输出+绝对内嵌记录、大小写别名均exit1且无welcome；外部记录正例正常。未扩展旧K1/P1审查；通过本次反例 |
| C 非法取消实际生效 | SessionServer.cc:621、685读取线程检查revision/目标；主路径及快速路径指纹包含op/params | 错目标类型、合法目标+过期revision、错目标分别拒绝，ping仍running；随后合法取消及下一轮3事件均正常。正式专项另测缺失revision和幂等冲突；通过 |
| D 历史覆盖与记录流竞争 | SessionServer.cc:279记录互斥、失败快照/原子exitCode、每会话专属目录、最终close受同一锁及失败检查 | 两会话复用记录根，原记录全部SHA保持；7份实际记录日志56个服务端帧均可逐行解析。另将本轮收据目标预置为目录，真实写入失败后receipt_integrity=unavailable、路径null、进程exit4；不授予完整记录成功。关闭失败仅源码检查，未模拟真实磁盘close故障 |
| E 16worker缺失终态 | SessionServer.cc:997改有界薄终态，完整收据在关闭文件中并附大小/SHA | 独立16worker/16事件：唯一run_finished，16/16，644字节帧；收据47023字节、117产物，文件大小和SHA均核对，身份匹配，无frame_too_large；小载荷仍通过 |

## 正式专项与独立原件

- Windows正式：C盘out/collab/f2-repair-independent-windows/20261104-141127-50a79801/report.json，5通过/0失败/0跳过、1266断言；session_protocol、session_cancel_mt、command_state_gating、interactive_commands、random_command_semantics。严格证据门禁通过，报告源码/构建身份可对应冻结候选。
- 主审新反例原件：C盘out/collab/f2-review-repair/windows-attempt1；D盘原字节副本out/collab/f2-core-independent-r2/windows-edges。原驱动报告11通过/1失败：产品反例11项通过，最后日志解析误把合法eof_close当失败。驱动会主动关闭stdin，因此EOF收尾符合协议；未改原报告、日志或重跑全部，单独record-stream-interpretation.json复核7文件/56帧通过。该误判不是产品缺陷，也不把原报告伪改12/12。
- D盘Windows副本337文件已核对来源/目标SHA，windows-manifest.json给出清单；Windows构建日志和BuildInfo一并保存。原报告绝对路径仍指向原C盘，不重写摘要或身份。
- Linux构建首个跨WSL命令参数传递错误保留build-repair-r1.log；改为stdin脚本后build-repair-r1-attempt2.log退出0。测试第一次未激活conda数据变量，旧入口出现G4ENSDFSTATEDATA缺失；主审停止仅自己的runner/probe，exit143，日志保留。第二次数据根预检显示conda目录无G4前缀，未进入测试。第三次复用安装包既有activate-geant4-data-*.sh，required_complete=true，原runner已exit0；正式报告out/collab/f2-repair-independent-linux1132-attempt3/20261104-141812-54a9015f/report.json，4通过/0失败/0跳过、923断言，并在Linux原路径通过严格证据门禁。报告尾部Git扫描耗时较长，属原任务正常等待，未重复启动或判失败。未安装依赖、未修权限、未为环境故障改产品。

旧首候选run_summary等报告仅按原身份引用，不改称第二候选重测；当前改动与原主入口的隔离及短兼容已复核。最终全阶段矩阵仍会按最终候选运行。本轮未扩大物理验证或宣称科学结论。

## 接续

DeepSeek原会话round41已accepted=true/replayed=false，任务F2-GUI-SESSION-20261104；实施要求见inbox/20261104-f2-gui-session.md。保持D盘GUI单写、C盘后端冻结；主审已完成原Linux报告/门禁，平台构建、环境失败与成功证据已归档到D盘out/collab/f2-core-independent-r2，manifest.json逐文件记录原字节SHA。完整重放准备见inbox/20261104-f2-replay.md，尚未派发。用户选B已经生效，不再询问。
