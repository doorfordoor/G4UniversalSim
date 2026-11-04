# F2 首轮实验独立复验

2026-11-04。主审独立驱动与解析，作者冻结交付见../outbox/20261104-f2-session-baseline.md。此为F2第一清单项的限定签收，不是完整F2验收或物理验证。

## 身份与方法

- 产品基线92134da062e8e3a203a39ff59fcd2b87bd0ffef1。D盘当前5ee240fc仅后续文档；对gui/src/include/main.cc/scripts/.github/CMakeLists.txt执行相对基线diff，退出0、无变化。
- 实际后端SHA256：18d58fab815b91e96c6c4b2c94704518d42885f163b54803072164a8a4f9c837；成功/受控失败摘要自报source_fingerprint=9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a、build_git_commit=625cfee22ab612b3e3829e7b6149c56036943d50，保留原构建身份，不谎称本轮重编译。
- 在C盘j3-final独立工作区的out/collab/f2-independent-20261104-r1生成独立驱动、复制配置并运行；没有调用作者的分析器来代替复验。每例独立Popen，原始stdin及stdout/stderr按字节保存，receipt记真实PID/退出码/文件摘要；作者的原目录未改写。
- 逐run直接读实际CSV，核对runID、trackID=1、parentID=0、eventID完整集合、入射面z=-10 mm及逐事件粒子/能量/坐标；不是从Manager缓存或沉积均值推断。
- 全部C盘原件与作者冻结包复制至../../verification/f2-baseline-20261104/，405文件/16733190字节逐文件SHA256比对一致，manifest.json记录。归档不删除源数据。

## 实际结果

| 例 | 独立PID | 进程退出 | 核对结果 |
| --- | --- | --- | --- |
| A/B/A三轮 | 72328 | 0 | 同一进程，run0/1/2各10事件，proton边界能量100/200/100 MeV，合计30/30 |
| particle/energy/point/direction/planeBeam | 70252 | 0 | 同一进程五轮50/50；e-切换不改原100 MeV，后50 MeV；位置x=5；方向归一化且x=5+40*(0.1/0.995)；圆面x²+y²≤25 |
| 原生GPS交错 | 67028 | 0 | 两轮各5；第二轮实际2 MeV，但两次Manager monoEnergy及摘要仍100 MeV |
| PreInit缓存回放 | 68680 | 0 | 初始化前设置300 MeV/e-，5/5初级边界行实际采用 |
| 多命名源拒单字段命令 | 50488 | 3221226505 | AIHL_SOURCE_001致命中止；无摘要、无hits/相空间、拒后哨兵未执行。保留硬中止事实 |
| Idle改输出目录拒绝 | 65096 | 1 | status=failed/run_count=0，geant4_illegal_application_state；无后续事件、无新目录、无哨兵 |
| 待延迟离子＋直接GPS覆盖 | 独立收据记录 | 0 | PreInit /gps/particle proton覆盖待应用离子；5/5实际proton、100 MeV，不被延迟离子重放覆盖 |
| 待延迟离子＋嵌套execute | 独立收据记录 | 1 | pending ion/confinement审计拒绝，failed/0轮，追加初始化/beamOn/哨兵均未继续 |

独立6例report.json为6通过/0失败，补充delayed-report.json为2通过/0失败，两个驱动进程均退出0。预期失败案例的非零后端退出保留，不能写成“所有模拟成功”。这些是定向真实进程实验，不冒充M0正式profile或逐位重放。

## 源码核对与结论

- src/Source/SourceMessenger.cc:100、106、220：源setter异常会转G4Exception/FatalException；外围try/catch不能保证结构化失败或会话继续。多源现有拒绝没有后续事件，符合本基线拒令停止要求；新协议必须另设计安全校验入口，不能泛化修改旧csh/batch失败合同。
- src/Source/SourceManager.cc:314：多命名源禁止单字段定位；405、417：待应用离子/限制体积由实际源身份维护，动态/别名分派明确拒绝。两类源模式不能合并成“所有源都支持单字段编辑”。
- src/Actions/SteppingAction.cc:54附近与src/Scoring/PhaseSpace.cc:49：相空间是目标入射边界记录，包含初级和次级轨迹ID，不是原始生成顶点。本例真空传输、主轨迹身份及完整事件集合均核对，才支持上述受控消费判定。
- src/Actions/EventAction.cc:41：当前事件结束记录计分与RunProgress；未发现现成的完整会话取消控制器，提案不得把“有进度钩子”说成“取消已经实现”。

第一项结论：**通过本阶段基线实验范围**。初版候选白名单仅为已实证的普通单源单能配置之粒子/能量、点位置、固定方向、圆形平面；PreInit只实证粒子/能量。run name没有当前会话setter，输出/线程/几何/物理/计分仍要求新包/进程；高级、未证及多源模式不进入可编辑白名单，协议实现须明确拒绝或要求重启。方向/源形状的高级组合、MT/其它系统/重放属于后续原清单，不以本结果覆盖。

## 对作者报告的限定修正（不改原件）

1. 报告第28行及driver开头“主顶点”改以本报告的“初级目标入射边界记录”解释；CSV记录器本来允许次级和再次入射，不能泛称每行都是顶点。
2. 报告第67行x=9.020对应5+40*(0.1/0.995)，不是括号中的5+0.1*40。方向要归一化。本轮主审已逐行核对实际值。
3. analyze.py:26从index.json生成汇总，不是每次直接重读所有原始CSV；实际CSV读取在f2_session.py:171。作者的“重新从原文件汇总”需要按该中间索引链解释。主审本次确实独立直接读取CSV，不依赖该措辞。
4. f2_session.py:267以text=True捕获文本再write_text，不是未变换字节流；本次主审独立原始流按bytes保存。两者不冒同一种原始字节证据。
5. 原生/gps反例证明缓存不能代表其实际应用，不能单独证明有限白名单受控csh毫无价值。方案B仍有逐请求错误、状态及取消方面的明确价值，但须交具体线程/消息/安全入口合同供选择。

## 下一步

清单第二项正在执行：F2-PROTOCOL-CONTRACT-20261104，原桌面绑定round35、request f2-protocol-contract-5ee240fc-20261104已accepted且非重放。指导见../inbox/20261104-f2-protocol-contract-review.md。仅设计交付，不改生产文件；主审复核后按开发接续计划§6既定决策点交具体选择，不空泛索要确认。
