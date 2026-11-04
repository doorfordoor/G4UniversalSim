# F2 受控多轮运行会话：最终验收

2026-11-04，独立复验完成，**F2本轮固定范围验收通过并关闭**。协议采用已决定的B：新增版本化会话接口，保留原csh/批处理。下一阶段为E4文档与开发规范收尾。

## 冻结身份

- 产品及正式云测试：`864bc036d6d7752475e52db4efd2b950cabfcc3d`，分支`roadmap/F2-controlled-session`。D盘交付、C盘j3-final干净检出独立编译；后续记录提交为docs-only，不冒充新构建。
- C++原始字节指纹：`e7de615d4e342114104f970688a7ea5f9789f7b70240b2562a388a50a45704e7`。Windows Release exe SHA-256：`f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f`。
- 最终6个声明文件相对上一候选冻结提交；跨Windows检出换行的产品映射按LF归一化核对，原始构建指纹不改写。详见D盘`out/collab/f2-final-candidate/freeze.json`及原报告。
- [归档逐文件SHA/来源](copy-manifest.json)；归档保留原报告、日志与原生收据字节，不追改原SHA、dirty事实或失败。

## 固定清单结果

| 清单项 | 状态 | 完成证据 |
| --- | --- | --- |
| 三轮隔离实验与白名单 | 通过 | [独立基线](../../collab/reviews/20261104-f2-baseline-independent.md)，同进程三轮、拒后不继续及有限白名单 |
| 协议与证据设计 | 通过 | [B决定](../../collab/decisions/20261104-f2-protocol-choice.md)、[实施合同](../../collab/decisions/20261104-f2-session-core-implementation.md)、[协议](../../会话协议.md) |
| 后端会话与重放 | 通过 | Windows/Linux专项、真实首轮无编辑对照、单线程及固定双worker重放、损坏/取消计划拒绝；原件在counterexamples及local |
| GUI下一轮面板 | 通过 | Windows125%/150%、Linux独立X11/xcb真实生产GUI，自然操作、逐轮收据、取消/拒绝重放、正常重放及退出 |
| 独审与正式矩阵 | 通过 | 最终云12份原报告708用例、255163断言，逐报告严格门禁通过；本机相关专项及原失败/恢复均保留 |
| 冻结集成与交班 | 通过 | 本报告及状态/路线图/支持矩阵同步；集成与定时任务读回、E4启动收据见[交班](../../collab/reviews/20261104-f2-integration-receipt.md) |

## 正式测试与云证据

| 平台/profile | 用例 | 已执行断言 |
| --- | ---: | ---: |
| Linux Geant4 11.3.2 static / GUI / backend / integration | 49 / 78 / 66 / 34 | 5665 / 10911 / 92116 / 6881 |
| Linux Geant4 11.4.3 static / GUI / backend / integration | 49 / 78 / 66 / 34 | 5665 / 10911 / 82948 / 6881 |
| M0 Ubuntu static / GUI | 49 / 78 | 5665 / 10911 |
| M0 Windows static / GUI | 49 / 78 | 5668 / 10941 |
| **合计** | **708** | **255163** |

12份均为最终候选864，逐例非零断言、无失败/跳过、日志摘要及总量严格一致。[门禁原件](cloud/strict-gates.json)、[门禁日志](cloud/strict-gates.log)、[4个ZIP与官方API摘要对照](cloud/download-manifest.json)。Windows实际VTK用例执行35条断言，日志无内部跳过。

真实云：[Linux双版本](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41820515533)、[M0双平台](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41820515013)、[桌面打包](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41820515045)、[原生runtime/SDK安装](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41820515620)均success，实际head864。[最终API元数据](ci-runs-final.json)。Windows/Linux保持统一版本、分别构建打包，不混用安装包。

本机独立Windows受影响6例10459断言、Linux11.3.2三例10071断言及严格门禁通过。Windows原全量backend为60通过/3环境失败、integration为32通过/1环境失败：缺少测试helper、未显式GDML能力、未指定已有数据根目录；同候选补齐既有helper和显式环境后，恢复3例490断言及数据定位1例12断言全部通过。原失败报告不改成绿色，不虚构一份全绿的本机全量报告。最终全绿矩阵来自上述真实云原件。全目标构建曾因正在运行的exe被锁而失败，保留原日志；随后仅构建所缺helper成功，产品exe摘要保持不变。

## 真实窗口与退出

- **Windows150%**：实际Qt DPR1.5，普通导航完成同进程A100/B200/A100 MeV各5事件；正常结束后点击重放，新进程三轮各5/5、界面closed，无旧误报。三张event_edep表逐行一致；保存项目，GUI正常exit0。[观察](native/windows150-native/review-observation.json)。
- **Windows125%**：实际Qt DPR1.25，提交20000000事件后真实取消，完成29675，状态cancelled；输入恢复，结束会话后重放禁用、manifest不可重放。会话进程exit0不冒充该轮completed。保存并正常exit0，系统缩放已恢复125%。[观察](native/windows125-native/review-observation.json)。
- **Linux独立X11/xcb**：DISPLAY94，真实生产入口，普通ProjectPage选择后端与运行根目录，Run Console完成A100/B200/A100各5；源会话`57d82a7f5b9c5dbecac81535b9c44cfd`，新进程重放`536e4190c6faf87566cb208b0a327594`，closing/replay_finished/exit0、steps_executed3/steps_total9。三张event_edep表逐行一致，实际看到closed。File→退出→Save保存独立项目，生产GUI与宿主exit0、remaining_owned为空。辅助进程退出码0/1/0（twm为1，原事实保留），不称全部子进程exit0。[观察](native/linux/review-observation.json)、[ABA画面](native/linux/aba-three-runs.jpg)、[重放画面](native/linux/replay-closed.jpg)、[原退出收据](native/linux/runs/20261104-193530-103379166/receipt.json)、[宿主结果](native/linux/host-exit.json)。

Linux脚本自动字段native_window_evidence仍是not_observed，不追改；本轮独立视觉证据来自浏览器返回的实际noVNC画布及正常键鼠操作，不来自该自动字段。原第一次旧启动器socket检查失败保留；第二次复用已就绪的最终X11启动器成功，未扩建视觉工具。WSLg RAIL历史限制仍保留，未称WSLg通过。

## 独审修复与限制

已闭合的显著缺陷：拒绝的源编辑仍继续重放并假成功；重放语义预检调用setter污染首轮；正常重放closing被GUI误判为异常退出。最小修复与反例分别在[重放独审](../../collab/reviews/20261104-f2-replay-review-r2.md)、[GUI反例](../../collab/reviews/20261104-f2-native-replay-review.md)、[预检副作用](../../collab/reviews/20261104-f2-replay-precheck-sideeffects.md)。最终首轮/后续轮非法编辑均在任何BeamOn前拒绝；真实首轮不编辑源的原/重放表一致；正常closing依赖原因、实际退出码和完成轮数核对，不把全部操作数当轮数。

作者早期bc8c是其临时构建，不是独立冻结；独立旧3b为fd47，最终作者自测d378为dirty3b，最终独立/云为864/e7。保留原报告，不能混同。结构预检在hello/初始化前，粒子及数值只读语义预检在初始化后、任何BeamOn前，不声称所有语义校验发生在hello前。

非阻断限制由主审签收：run0摘要局部显示横线、重放参数栏显示unknown，逐轮表/原收据/事件事实完整，列后续文案优化；取消已证明本轮Windows/Linux测试范围，不外推任意物理列表。重放仅对固定构建、数据、随机初态、线程与顺序成立，不承诺跨平台/跨线程数逐位一致。工程一致性检查不等于科学物理基准验证。J3约一秒主题切换等历史限制不作为F2新增前置。
