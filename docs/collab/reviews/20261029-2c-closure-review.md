# 完整 2C 最终闭合交叉审查

审查对象：产品候选 `f4770b0cb73c8b1f9852fbac0d485e17b25bc0e3`。本审查按 [1959 完整开工信](../inbox/20261029-1959-astra-full-2c-execution.md)、[1010 决策](../inbox/20261029-1010-astra-2c-execution.md) 与 EffectiveConfig 契约核对实现和最终证据，不改变阶段状态。结论作为 root 最终裁决输入：**在下述支持范围与未知边界内，未发现尚未关闭的确定阻断；六项验收具备对应实现和本轮证据。**

审查者此前参与基础模型、消费者和测试修复，故不是所有代码均由独立作者重新实现或逐行复证。本次独立性在于对最终集成候选、原始报告、控制实验及 CI 进行交叉核对。没有重新运行大测试、修改产品/门禁/历史报告；仅新增本文。最终阶段主报告由 root 维护于 `docs/verification/2c-full-20261029/README.md`。

## 1–6 验收映射

| 开工信验收 | 实现与核验路径 | 本轮测试/证据与判定 |
| --- | --- | --- |
| 1 基础契约 | `src/Config/EffectiveConfig.cc:159` Commit、`:220` ReplaceModule；`IniReader.cc:18–22` 读取同 bytes 后原子 LoadBytes；`InputProvenance.cc:42`；`EffectiveConfigSupport.hh:50` Confirm。删除/替换使用候选事务，拒绝不发布；无变化不增 registry revision，快照保留值副本；来源与配置代次独立。 | `effective_config_model`、`input_provenance`、`effective_consumer_state` 均通过；覆盖重复声明、别名、同字节 SHA、失败保留、连续不同命令与不可变快照。不是以 schema 条数代替消费者覆盖。 |
| 2 完整消费者 | Core 启动/命令；Source 实际 SourceSpec/PhaseSpace；Geometry/模板/STL/GDML；Materials；Physics；Scoring/mesh/NIEL；Field；Biasing；Output/trajectories。对应 Manager Export/Confirm 和实际构造观察入口。稳定 JSON Pointer、适用模式投影与明确单位；不输出非 mono 的 mono 缓存或 GDML 假 Box。 | `effective_geometry_materials`、`effective_source_physics`、`effective_output_mesh`、`effective_biasing`、`effective_scoring`、`effective_gdml`；既有 Q1 全域回归。均在本轮 Windows 与双版本 Linux 报告中通过。外部输入由实际 parser 同字节捕获；GDML 包括专门捕获 helper 的 integration 验证。 |
| 3 运行接线 | `src/Core/EffectiveSimulation.cc:265` 快照写出、`:316` 逐 run/thread begin、`:335` 线程 final；实际回调接线、公共 receipt reducer 的 scope/generation/resolved hash/value 匹配。成功关闭才登记，本轮 manifest 与失败锁存共用原输出边界。 | `effective_lifecycle`、`effective_receipt_view`、`effective_config_export`、`run_summary`、`interactive_commands`、SD/输出故障与多 run 回归通过。dry-run 为 configure/finalization、run_id=null、execution_performed=false；不伪造 run_begin。异常收尾实际线程数不可取时允许 unknown，用真实 begin 收据独立核验 worker 集合。 |
| 4 模块模式 | `EffectiveSimulation.cc:360` ApplyModuleModes、`:433` 命令门控。缺失 mode 保留 legacy；显式 auto 只看明确请求/依赖；off 冲突拒绝；on 要求有效配置。biasing 候选解析与最终开关判定分开；mesh-only 不启 SD，phase_space/trajectories 不被 SD gate 清除。 | `effective_modules` 136入口及 source/physics/biasing 等交叉反例通过；不再把默认 scoring=true 当显式请求，不创造空 biasing 规则或新物理。schema 缺失默认为 null，GUI 是只读审查界面。 |
| 5 GUI | GUI effective_config 读取/集合/差异/对象摘要页面；阶段/run/thread、类型/单位/来源、损坏加载原子拒绝与 stale、切语言/主题保持审查状态。结果成功独立依据 run_result。 | `effective_config_viewer`、`effective_config_collection` 及 GUI profile 32例通过。另见 `out/verification/2c-visible-accepted/{gui-report.json,backend.json,visual-review.md}`：真实 Windows Qt 可见且 exposed，10类检查、6图、2run/2worker/8事件、14快照；本次重新校验14快照原始 SHA 全匹配。视觉所见引用前端审查者已经逐图查看的记录，本次没有冒充亲自再次看图或真人点击。 |
| 6 冻结与跨平台 | 干净 canonical Release 日志 `out/collab/2c-clean-build-canonical.log`；冻结报告与真实 GitHub CI；独立 Q1 production 同口径控制实验。 | Windows 118/118、0fail/0skip、40628 v3入口、git_dirty=false；Linux 两版本各118例，M0两平台各47例；12报告严格门禁全通过。Q1控制105/105、36269入口，当前报告原 --baseline 逐例/总数门禁通过。详见下节。 |

## 最终证据身份与测量闭合

- Windows：`out/verification/2c-full-windows-final/20261029-223652-da8b6389/report.json`；`evidence-baseline-gate.log` 明确记录原门禁通过。source=`c2b575bbb9c594765364aa7c78150e842ffb20ff34b10ad4729720bae2c8c91b`，tests=`3ac890cc996d73289098628bb6cca8888f3120f9dffc3e22f60ab387ab1d6d1a`。本次直接读取118条结果，无非pass项。
- CI：[Linux run 40892017436](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40892017436)、[M0 run 40892017433](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40892017433) 均 success，四 job 均 success。`out/verification/2c-ci-final/ci-evidence.json` 保存12报告、4官方 artifact ID/digest及4完整 decoded job log。本人实际下载全部ZIP、核官方SHA并执行原严格checker；HEAD与两个指纹均匹配。没有请求rerun，没有覆盖旧失败CI目录。
- Q1控制：`out/verification/q1-counter-control/control-evidence.json`、`control-provenance.json`、`measurement-overlay.patch`。overlay=`7929314120e07142b48205f00059625806e9193b` 仅5测试；src/include/main/CMake Git对象与8ec/f25完全相同，production diff为空，5脚本SHA与候选一致。测试内容整体指纹不同是新2C专项加入所致，不能冒称两个仓库测试树完全相同。
- `counter-comparison.json` 的五项差精确为 Dose -230、numeric -47253、geometry -16、GDML -12、results +10，总计 -47501，`83770-47501=36269`。控制与候选对应五例入口分别为79/457/4320/65/125，全部相同。历史83770原报告没有修改；新入口数不是覆盖质量排名。
- Dose/numeric 对每条真实记录执行原判据，按独立不变量收集错误后固定 assert，保留具体失败证据；输出真实 rows/cells/arrays 与实际数值故障分支。故障注入 ST 保留t0，MT采用真实worker atomic-once any_worker，保留首因/非零/停止后续/首轮保留契约。没有以等待、增加粒子、生产barrier或放宽门禁制造计数。

## 已确认缺陷闭合

| 确认问题 | 最终关闭依据 |
| --- | --- |
| 空/空白 physics.em 被忽略却记录为有效显式请求 | `PhysicsManager.cc:723–757` 以真实消费结果处理、保留 ignored 原声明与原因；`test_effective_source_physics.py:42` 空值/空白及显式 option4 反例，本轮372入口通过。 |
| 连续 mutation 令非target requested 恢复旧INI值 | `EffectiveConfigSupport.hh:58–59` 保留未改非target旧requested/requested_known；连续不同命令组件反例及真实消费者来源回归通过。 |
| biasing非法参数 Fatal abort 绕过摘要/快照 | `BiasingMessenger.cc:49–69` throw/有限性检查及 catch登记+JustWarning，Manager失败counter与main守卫闭合；负数/nan/inf/错误参数等六反例包含失败状态、非零、revision/来源不变及后续不执行，`effective_biasing`302入口通过。 |
| 新快照未分类/旧mock与manifest契约不符 | 快照schema登记、dry精确清单及真实最小summary fixture已修；run_summary、输出provenance及消费者专项、本轮全部平台原门禁通过。未降低本轮名单/run归属约束。 |
| worker0分配、稀疏贡献worker数及逐行assert计数被当作调度保证 | 实际worker边界注入、贡献集合上界与独立合成反例、按不变量计数及同生产控制实验闭合；原历史失败保留，R31允许的worker/root与master/merge数值捕获分支诚实记录。 |

## 保留的未知与覆盖边界

1. manager_accepted、构造/挂接、过程匹配、proposal/applied计数是不同证据层。缺少通用内核getter、类型/值不一致、scope/generation不匹配、未观察字段仍unknown；没有为覆盖率把Manager缓存升格。Geometry通用solid细项、Physics构造器列表、部分场积分属性等不具备完整逐字段内核反射，保留单独observations/unknown。
2. 未可靠读回的原生GPS/Geant4修改明确unknown并保留成功命令来源；不保证任意动态派发/宏或所有原生命令可审计，Q1 pending alias、状态门禁和不安全重初始化拒绝继续适用。配置快照不是随机引擎状态，也不保证随机逐位重放。
3. 同字节SHA证明被捕获parser输入，不证明来源权威、设备持久化、任意未来网络资源可重获；GDML untracked输入显式保留不完整边界。写出登记不证明外部未改文件，manifest不是密码学签名。
4. 应用证据和工程回归不证明普遍物理正确性、NIEL数据有效性、偏置一般无偏性或方差收益；独立物理科学验证仍不在2C闭合范围。
5. 平台证据限本次Windows Release与Linux Geant4 11.3.2/11.4.3 CI；不扩大为Windows+11.4、11.2、所有UI会话、安装包或任意硬件。可见GUI是程序化Qt操作真实窗口，长列需滚动，不宣称所有内容同时可见。
6. 本次复核重读最终报告/控制provenance/关键修复和开工契约，并亲自完成CI下载、摘要与12门禁；未重新遍历所有C++行、所有几何/物理组合或再跑118例。此前独立collector的1/17行和nan/inf/nan(ind)检查仅有工具执行记录，没有独立落盘日志，不列为已归档正式证据。

上述边界不是未关闭的已确认缺陷。若最终仅提交文档整理，产品候选及测试证据身份仍按f4770b0标明，不能把未重跑的新文档commit冒称已执行同一轮测试。
