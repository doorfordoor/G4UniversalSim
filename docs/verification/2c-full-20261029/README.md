# 完整 2C 最终验收记录

验收代码：`f4770b0cb73c8b1f9852fbac0d485e17b25bc0e3`。完整 EffectiveConfig、模块策略和只读审查界面已完成实现、交叉审查及约定平台验收。后续文档与证据提交不代表另一次源码测试。阶段状态见 [ROADMAP](../../ROADMAP.md)，机器收据见 [verification.json](verification.json)。

## 交付范围

- 接入 11 类消费者：启动参数、传统源、具名/相空间源、几何、材料、物理、计分/mesh、场、偏置、输出/径迹、命令。按实际模式投影配置，以 JSON Pointer 保留对象身份；请求原文与类型化解析值、单位、来源及应用证据分开记录。
- 默认值、preset、INI 重复声明/别名、CLI 和成功命令形成来源链。文件 SHA-256 来自实际解析的同一份字节；失败命令不发布值、来源、代次或 revision，旧快照不可变。
- 真正接入 configure、逐 run/thread 的 run_begin、线程及进程 finalization；应用收据校验线程、运行、对象、配置代次及解析值。无 getter 或未知原生命令保留 unknown，不拿 Manager 缓存冒充内核读回。文件原子发布，成功关闭后才登记；失败进入受控收尾。
- 提供 `[modules] scoring/biasing/field/trajectories = off|auto|on`。缺失 mode 保留旧行为；显式 auto 根据明确有效请求及依赖决定；off 与活跃显式请求冲突时拒绝，on 不创造物理参数或规则。核心模块不能关闭。
- GUI 支持只读快照集合、阶段/run/thread 选择、对象、来源链、未知状态与两快照差异。损坏加载保留旧集合并标明陈旧；单文件 4 MiB、集合 64 文件/32 MiB；中英、明暗及小窗口经过真实 Windows 窗口检查。
- DeepSeek 实际参与前端设计与实现建议，由 Sol 实现/复核、主任务整合验收；调用、采纳与纠偏见 [设计记录](../../collab/outbox/20261029-deepseek-full2c-design.md)。不是只给模型分配名义角色。

实施边界见 [开工信](../../collab/inbox/20261029-1959-astra-full-2c-execution.md)，协议见 [EffectiveConfig](../../EffectiveConfig.md)，独立闭合复核见 [审查记录](../../collab/reviews/20261029-2c-closure-review.md)。

## 平台与门禁

| 验收项 | 结果 | 原始证据 |
| --- | --- | --- |
| Windows / MSVC 19.51 / Geant4 11.3.2，干净 Release | **118 PASS / 0 FAIL / 0 SKIP**；40628 个 v3 入口；运行时工作区干净 | [报告](windows-full/report.json)、[干净构建](windows-build/build.log) |
| 与 Q1 同口径控制对照 | 控制组 **105/105、36269**；候选逐例和总数均不下降，原严格门禁通过 | [控制报告](q1-counter-control/20261029-223005-6361397e/report.json)、[候选门禁](windows-full/evidence-baseline-gate.log)、[复制后门禁](windows-full/archive-baseline-gate.log) |
| Ubuntu 24.04 / Geant4 11.3.2、11.4.3 | 两版本各 **118/118**，四个 profile 及报告发布门禁均通过 | [Linux run 40892017436](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40892017436)、[完整 CI 收据](ci/ci-evidence.json) |
| Windows、Ubuntu static/GUI CI | 两平台各 **47/47**（15 static + 32 GUI） | [M0 run 40892017433](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40892017433) |
| Windows 真实可见窗口 | 2 runs、2 workers、8/8 events、14 快照；10 类检查通过；6 张原生截图实际查看 | [视觉复核](windows-visible/visual-review.md)、[机器报告](windows-visible/gui-report.json)、[中文差异](windows-visible/zh-light-real-differences.png)、[英文陈旧状态](windows-visible/en-dark-small-stale.png) |

统一 118 项分布为 static 15、backend 52、GUI 32、integration 19。所有报告均有非零断言；CI 12 份报告严格门禁通过，4 份 GitHub artifact ZIP 的 SHA-256 与官方记录一致。原始日志与报告按字节复制，见 [复制清单](copy-manifest.json)。真实窗口由程序化 Qt 操作，不冒称真人点击。

源码指纹：`c2b575bbb9c594765364aa7c78150e842ffb20ff34b10ad4729720bae2c8c91b`。测试指纹：`3ac890cc996d73289098628bb6cca8888f3120f9dffc3e22f60ab387ab1d6d1a`。Windows 可执行 SHA-256：`fbb7c56e820d3d36e5f87a3ef2995d55c554d4c5cb38dbaa75191422d4bc37f0`。本机验收可执行文件保留于当前工作区 `out/build-2c/Release/G4UniversalSim.exe`。

## 同口径控制为何重测

原 Q1 的 83770 个 v3 入口报告保持原样。四个测试曾对实际 worker 行/数组反复进入同一 assert；分工或先发现错误的位置改变，会使重复次数变化，不能直接当作验证遗漏。修订保留每条记录的全部数值与身份检查，按固定独立不变量收集错误并断言，另输出实际记录覆盖。第五项修订移除“贡献 worker 必须少于总事件数”的不成立假设，增加原 ROOT 无 metadata 时必须拒绝推断 N 的反例。

控制组生产源码与 `8ecad66`/`f25da40` 完全一致，使用原 Q1 已验二进制；仅覆盖与候选 SHA 相同的五份测试，形成干净 overlay `7929314120e07142b48205f00059625806e9193b`，重跑全 105 项。其余 100 项入口数与历史完全相同；总差可由这五项精确解释。见 [控制来源](q1-counter-control/control-evidence.json)、[计数对照](q1-counter-control/counter-comparison.json)、[可复现测试补丁](q1-counter-control/measurement-overlay.patch)。控制工作区必要证据已复制核验后归档，原 Q1 主工作区与二进制保留。

没有修改历史报告、降低门禁或用空断言凑数；新旧动态入口总数不用于比较科学覆盖优劣。同口径控制与候选均使用 `settrace_assert_lines_v3`，原门禁仍检查逐例/总数、零断言、退出状态、日志原始字节摘要和报告自洽性。

## 失败证据与修复

- 保留 [fee88d2 Windows 首轮](history/windows-fee88d2/report.json) 的 113 PASS/5 FAIL，以及 [同提交失败 CI](history/ci-fee88d2/ci-evidence.json)。失败不改成绿色，CI 没有靠 rerun 掩盖。
- 已修空 EM 声明的来源误归属、连续命令导致未修改字段 requested 回退；成功与失败命令均有真实专项。
- 新负例发现非法 biasing macro 可触发 Fatal abort、绕过失败摘要；现改为受控失败计数，停止后续命令、保留命令位置、不发布失败配置。保留 [修前日志](history/bias-negative/run.log) 与修后专项。
- 新快照已登记正确格式；dry-run/未执行的失败路径明确无 run、无执行证据。MT 回调故障改由实际执行 worker 原子竞争一次，ST 保留 `_t0` 入口；失败线程由真实快照核对，收尾无法取得线程数时允许诚实 unknown。
- NIEL 缺文件诊断仍验证字段、INI 行号和绝对路径；受审计交互成功命令明确记 interactive 来源。测试测量不稳定性、旧文件白名单和旧来源预期与产品缺陷分开记录。

开发中间构建/专项保留于 history；只有本页冻结代码和对应完整报告用于最终验收。完整协议历史见 [Agent 条目](../../agent-history.md)。

## 保留的边界与下一节点

- 快照/调用收据不证明物理正确、无偏性、统计适用范围或随机逐位重放；Q2 继续负责独立科研验证。
- 原生动态命令、无独立 getter 的参数、部分无法完整捕获的 GDML 网络流继续 unknown；失败的其他对象绑定不能被某个成功绑定抵消。不提供安全内核热重建。
- Windows 本轮为 Geant4 11.3.2 MT/GDML；`threads=1` 是一个 MT worker，不冒充独立串行构建。Windows 11.4、原生 Linux 桌面/安装器属于后续平台阶段。
- 当前 schema 357 项不等于全 GUI 可编辑，也不等于 E6 已完成；field/biasing 统一 schema、完整编辑能力、独立工程导出及 AI 执行工作流保持后续阶段边界。
- 下一完整节点为 **E6**，按 ROADMAP 推进。集成记录见 [local-integration.json](local-integration.json)；D 盘 DSH/邻线工作区不切换、不覆盖。

## 提交与集成节点

- `f4770b0`：本轮被完整测试的冻结代码/测试提交。
- `790ad2c`：最终关闭文档及原始证据归档；暂存的1168份归档文件与工作副本逐字节一致，全部文档链接检查通过。
- `codex` 已从 f25da40 正常快进到该证据提交，两个开发/集成工作区均干净；`codex` 与 `roadmap/2c-effective-config` 已普通推送至790ad2c。详见本目录集成收据。
- 本补记提交仅记录已发生的集成/推送事实，不改变验收源码或测试，也不冒称为另一轮运行。保留D盘邻线分支、21项未跟踪审查资料及Q1原二进制。