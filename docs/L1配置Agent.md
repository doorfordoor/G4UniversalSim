# L1 配置 Agent（初稿）

本文描述正在实施的 L1 目标、接口和验收方法，不代表功能已交付。开工基线为 `4840e62e6c2efe935e74e5b934f6194c6aa7731c`，分支 `roadmap/L1-config-agent`；范围与写权见[开工契约](collab/inbox/20261102-l1-execution.md)。[ROADMAP](ROADMAP.md) 仍是阶段状态入口，本次不修改其状态。

L1 要让用户用自然语言完成一项可复查的配置实验：明确改谁、怎么改、最多花多少事件与调用；在授权范围内完成修改、校验、试跑、读证据和导出。它建立在已有手工编辑和 [K1](可信实验工作流.md) 上，不由模型直接操纵 Geant4、文件系统或运行进程。能解析、初始化通过、事件完成和某个参考下的比较通过分别报告。

## 从一句话到可审阅结果

例如起始夹具中有体积 `Detector_A`、源 `Beam_A`，用户明确要求：

> 把 Detector_A 的材料改为 G4_Si；只改 Beam_A 为沿 +Z 的 1 GeV 电子单能点源，保持位置和其他源不变。用原物理设置、原种子和一个线程，最多运行一次、100 个事件，完成字段检查和初始化后试跑。检查这次运行是否按指定输入完成，给我看修改和证据，确认后导出到新目录。

这是一项**待冻结夹具的验收任务示例**，不是下文开发任务集 02 的原任务或已跑结果。默认 evaluate 检查运行完成性，不做物理 compare。若用户另要求比较逐事件敏感体总沉积能均值/标准误，须真实提供参考与适用条件，经已有 K1 显式比较入口执行；本文不创造参考数值，也不声称 Agent 面板已实现参考选择/自动物理比较。

服务先列出匹配的既有体积、源及当前值，保留粒子/方向/能量与分布事实。名称重复、所选源并非 mono/point/fixed、预算冲突，或用户要求科学比较却缺参考时，先指出具体问题，不把高级源改成另一种简单实验。当前本轮只写 common 白名单，不创建/删除对象、重写外部文件或自动覆盖全部 J2 高级字段。

无歧义且授权明确时，Agent 展示差异并继续执行授权链路，不逐动作问“继续吗”。若用户只要建议，停在差异；若已授权 apply/校验/试跑，则执行这些动作；若只授权试跑未授权导出，结果形成后才提供具体导出确认。确认不能隐含公开上传或改代码许可。

## 当前基础与新增接口

以下是开工时只读核对的接口，不是 L1 全部实现清单。历史 K1/F5 文档中的 v7 描述不覆盖当前 Project **v8**；编辑快照外层仍是 `g4usim_edit_snapshot_v1` / version **1**。升级只能沿已知迁移，不泛化默认缺失字段。

| 已有入口 | 用途与消费规则 |
| --- | --- |
| [edit_snapshot.py](../gui/g4usim_gui/core/edit_snapshot.py) 的 `WorkspaceSnapshot`、`snapshot_to_dict/from_dict`、`snapshot_fingerprint` | 完整模型与原始编辑状态；克隆/严格 codec，不产生可执行指令。单快照编码上限和事务历史总预算是不同限制 |
| [transactions.py](../gui/g4usim_gui/window/transactions.py) 的 `capture_workspace()`、`apply_workspace(snapshot, reason=...)`、`apply_editor_operation(..., expected_revision=...)` | 捕获主窗口当前草稿、投影/回滚和编辑绑定；不能从 detached typed 模型写回而留下旧 raw 镜像 |
| [edit_transactions.py](../gui/g4usim_gui/core/edit_transactions.py) 的 `EditSession.replace/transact/undo/redo` | 唯一配置事务与 revision；当前默认历史 100 命令、32 MiB 总编码载荷；完整快照 codec 当前另限 24 MiB，不能跨限制接受半个事务 |
| [experiment_workflow.py](../gui/g4usim_gui/core/experiment_workflow.py) 的 `inspect`、`validate(level='fields')`、`generate`、`run` | 共用服务，支持 `expected_revision` 和内部准备包；初始化 level 是 `initialization`；动作异步完成后才能使用结果 |
| 同服务 `apply(candidate, label=..., expected_revision=..., apply_snapshot=...)` | 候选为完整 `WorkspaceSnapshot`；字段校验成功后 F5 replace/projection；模型 JSON diff 本身不是 K1 apply 输入 |
| 同服务 `evaluate(run_id=None, comparisons=None, expected_revision=...)`、`export(destination, resource_policy=None, expected_revision=...)` | 比较与资源导出沿既有真实合同；不用模型自报结果替代 evidence |
| 同服务 `state()`、`records()`、`cancel(force=False)`、`close()` | 消费当前服务投影与历史、取消和排空。读取记录不等于已有可按客户端 operation ID 重入的跨进程执行 API |
| [experiment_identity.py](../gui/g4usim_gui/core/experiment_identity.py) 的 `capture_identity` | 绑定 snapshot、配置/资源 fingerprint、后端与环境执行身份。revision 单独核对，不能与内容哈希互换 |
| [diagnostics.py](../gui/g4usim_gui/core/diagnostics.py) 与 [F4 契约](结构化诊断与定位.md) | 原始 code、severity、真实 editor/entity/field/source、身份与陈旧资格；不从翻译文本正则猜对象或行号 |

L1 的任务/授权/预算与恢复 journal 是上层协调，不接管 `EditSession` 或 runner。异步 provider 在线程中工作；Qt 控件、事务和 K1 公共动作仍在所有者线程。用户编辑、换项目、Undo、外部源变化后，旧响应即使合法也不能应用。

当前已落下列实现接口并取得部分专项/开发证据；它们不在本次文档写权内，以下只读更新不替代各作者独审或新候选正式验收：

- `agent/provider.py`：`ProviderConfig`、`ProviderClient.complete(messages, cancel_event=None)` → `ProviderReply`；当前走非流式 `chat/completions` 文本 JSON，提供 timeout、连接/字节/token 限制；不自动重试/重定向、不继承代理，不接受任意工具执行。
- `agent/credentials.py`：`CredentialStore.put/get/delete(credential_id, storage='system')`、`clear_session()`。Windows Credential Manager / Linux Secret Service；Linux 直接依赖可选 SecretStorage，缺失时明确拒绝 system 存储。显式 session 模式只驻内存，不是持久存储失败的静默 fallback。
- `agent/actions.py`：`planning_context`、`planner_messages`、`parse_plan`、`build_candidate`、`requires_review`；候选协议为 `g4usim_config_agent_plan_v1`。当前仅 generated，按同快照唯一名称解析现有对象；没有任意 JSON Pointer、路径写入或新增对象动作。

本轮 common 白名单为：既有体积 material/size/position/rotation/sensitive，既有源 particle/energy/position/direction，run beam_on/threads/seed，physics reference_list/default_cut，scoring hits/event_edep/edep/dose/fluence；world、实体尺寸和源分布另有限制。源只写单能 mono、point、fixed；不新增对象，不自动编辑谱/相空间/其它分布或全部高级 J2 字段。原几何复制模式（geometry.source_copy_mode）不消费 volume editor 差异，Agent 因而拒绝全部 volume 修改，原因码为 `agent.original_geometry_copy_is_read_only`；run/source 等其它原已允许字段仍可修改，不修改 K1 copy compatibility。physics 变更需明确审阅，不能偷偷改变科学假设。函数 `max_events=100` 不是用户预算，也不能替代实际累计运行约束。

读取范围（此处 `read_scope` 是范围概念，不是现有 plan JSON 新字段）来自 UI 刷新/捕获的 WorkspaceSnapshot，经 `planning_context` 提供 common 字段与源类型/可编辑性摘要，不默认读取整个工作树、路径文件或日志。实际受信写范围参数叫 `write_scope`，自动 apply 路径由 [window/config_agent.py](../gui/g4usim_gui/window/config_agent.py) 的 `_agent_write_scope` 从本机上下文构造，`enforce_scope` 检查候选；人工审阅 Apply 则按下节新授权 API 接受精确已展示 plan，可另传 write_scope 限制。两条路径均受 common 白名单约束，模型不能自批；计划展示由 `describe_changes` 计算 before/after。

[agent/controller.py](../gui/g4usim_gui/agent/controller.py) 的 `AgentController.start(..., auto_apply=False, auto_run=False, write_scope=None)`、`approve_plan()`、新 `approve_with_authorization(authorization, *, auto_run=False, write_scope=None)`、`continue_run()`、`confirm(destination=None)`、`recover(path)`、`cancel()`、`close()` 已落接口，复用同一 K1/F5/runner。UI 授权与任务恢复/比较的真实语义见后文；有开发链路不等于整阶段已完成。

## 默认 plan-only：审阅差异后重新授权

默认任务先规划并显示 diff，不因生成了合法计划就获得写权限。用户查看后，在 UI 改选本次执行动作/预算，再点击 Apply，调用：

```python
controller.approve_with_authorization(authorization, auto_run=False, write_scope=None)
```

这是对当前可见计划的**新用户授权**，不再发 LLM 请求。当前实现要求：

- 计划仍是同一 base_fingerprint/当前 revision 对应的原 plan，无未回答澄清，且不是忙、关闭、故障或已调度执行状态；原输入已变则拒绝，不能重定向到当前同名对象。
- 新授权必须允许 apply，候选须满足新事件预算；传入 write_scope 时进一步核对精确对象/字段。省略该参数也不开放白名单外能力。
- 新建 TaskJournal 和新 task_id，复制这一份已审 plan，保存**当前 UI 的新 authorization**；记录 `agent.reviewed_from:<旧task_id>` 的 reason 事件以关联来源。旧 task 追加取消记录，其原授权、原用量和历史保留；不在旧文件中改 grant 或把旧任务冒充新任务。
- 后续只执行新 grant 允许的步骤，权限不足停在对应步骤，不自动扩大。即使允许 run，auto_run=false 时仍须显式继续；没有 run grant 不因点击运行就获得它。
- 恢复文件读出的计划不能经此路径获得写权限：`_recovered` 阻断，仍是只读旧 ID 查询；须提交新 prompt 请求并创建新 task，不能仅勾选权限“恢复执行”。

主线程已确认该 UX 与核心专项独审通过，最后的其他所有者忙状态 P2 也已定点关闭：controller `409d6a4a40c446c58e65ef619bbcdcb3814a151a3a30fcb39c3e924540e71af1`、窗口适配 `9689acb7374e98d7996aa13be8225fbc50ce18f281534099842db39eead6d5c7`。面板 125%／150% 独立组件各 108 入口、永久边界测试 146 入口按各专项收据计证，不相加为正式矩阵，也不冒称原生窗口已验收。取消、超时与关闭只处理本任务绑定的工作，不能因别人的 K1 操作忙而取消它。本文冻结为实施候选说明，不写阶段完成。

## 已冻结的纯文件 journal 接口

[agent/session.py](../gui/g4usim_gui/agent/session.py) 的 `TaskJournal` 已由另一作者实现并冻结，SHA `7d3672793066112259ac3a780433bb13e7bac22494044904a47021ceb19cadc3`。本次文档作者独立窄审无新 P1/P2：作者七组/161 仅核原收据与 log SHA，独立新增四个组合/58 个已执行断言入口，未重跑作者全套；证据根 `out/collab/l1-session-independent/`。这是 Windows 纯 Python 文件/子进程证据，不是 Qt/K1/controller、Linux、真实 provider 或完整 L1 验收。

| 实际 API | 合同与调用者边界 |
| --- | --- |
| `TaskJournal.create(root, prompt, authorization, project_identity, limits=None)` | 新 task 目录与原子 journal，持有 OS lease；授权固定 allowed_actions/max_calls/max_events/timeout_seconds；project identity 为 snapshot_fingerprint/revision/session_id |
| `path/state/task_id` 属性、`to_dict()` | 读取/深拷贝事实，返回记录不授予权限；不会将 journal 数据当可执行恢复脚本 |
| `set_plan(plan)`、`transition(state, reason=None)` | 计划是有界 JSON，业务字段/权限仍由 actions/controller 校验；状态日志不是领域执行所有者，不自行证明动作通过 |
| `record_intent(action, binding) → operation_id` | 同目录写/flush/fsync/replace 成功后才返回；单个 in-flight，run 必须预留正整数事件。磁盘失败时不得 dispatch |
| `record_binding(operation_id, binding)` / `bind_operation` | 仅允许 run_id/record_id/events/revision/snapshot_fingerprint/action；原绑定不可换，不能补未预留事件；并不接收 execution_id 或任意 K1 全记录 |
| `record_result(operation_id, evidence)` | 有限 status/reason/run_id/record_id/revision/stale/events/level 投影；一次结果，完全相同重发不写盘，冲突拒绝。result revision 是观测后值，不与 intent pre-revision 混淆 |
| `load(path)`、`resume_policy()` | load 不重写原件；恢复实例永久 query-only，pending 返回原 operation/run/record，can_replay=false 并要求新用户请求/live identity；无 pending 为 new_task_required，不是自动重跑许可 |
| `cancel()`、`close()` | cancel 只记取消；close 幂等释放 lease，不停 provider/runner，调用者须先 drain。恢复实例仅可记中断/取消或查询结果，不可进入执行态 |

journal schema 为 `g4usim_agent_task_journal` / version 1。硬上限为 32 个 intent、100000 预留事件、3600 秒、512 条 record、1 MiB；下调限制不授予任何运行预算。`usage.calls` 计所有 record_intent 动作次数，规划请求也登记为 plan，不仅是实际 provider 请求数。当前固定流水线每 task 最多一次事件 run 和一次初始化，不提供任意宏/动作循环或自动传输重试；K1 内部查询沿既有受控流程。预留事件不因失败/取消/部分完成返还；实际结果少于计划可以保存，未知不填计划数。

同态恢复 `running` 仍拒绝；同态 `cancelled` 是允许的不写盘幂等取消。journal 没有单独 timed_out/stale 任务枚举：超时用 failed/reason=`agent.limit.time`，陈旧还须调用者/结果投影表达，不能把下文拟定协调状态直接写成非法 journal 状态。取消后的迟到 passed 结果可保存，任务仍 cancelled，首因保留；这不证明后端一定中途停住。

系统锁拒绝 live owner 期间的恢复写；正常 close 和真实异常退出后才释放。checksum 用于损坏检查，可被重算，不是授权签名；字段名过滤也不是任意自由文本的 secret 检测器。调用者仍负责最小化/去敏、live identity、结果真实性和实际 K1 查询。未绑定 intent 只能 query-only/unknown；journal 不承诺跨进程 K1 exactly-once 或已实现进程接管。

## JSON 差异与本地事务

模型只能提出数据。以下示例沿当前草案字段形状，`base_fingerprint` 应由真实上下文提供；示例占位文本不能用于执行。`summary` 不能替代逐字段变化预览或授权。

```json
{
  "schema": "g4usim_config_agent_plan_v1",
  "base_fingerprint": "<由本地快照提供的真实指纹>",
  "summary": "修改指定探测器材料和指定源；保留其他配置",
  "clarifications": [],
  "changes": [
    {"domain": "volume", "target": "Detector_A", "field": "material", "value": "G4_Si"},
    {"domain": "source", "target": "Beam_A", "field": "particle", "value": "e-"},
    {"domain": "source", "target": "Beam_A", "field": "energy", "value": "1 GeV"},
    {"domain": "source", "target": "Beam_A", "field": "direction", "value": "0,0,1"},
    {"domain": "run", "target": "", "field": "beam_on", "value": 100},
    {"domain": "run", "target": "", "field": "threads", "value": 1}
  ]
}
```

该对象没有任务授权、参考与预算提升权。预算、对象绑定、原值、预期 revision、provider 和操作身份由本地受信状态保存，不能简单增加模型 `approved` 字段。协议变更须严格版本化、同步消费者和负例，不悄悄让旧 JSON 多出默认权限。

本地接受过程为：严格 JSON → schema/字节/条数/类型 → 白名单 → 授权交集 → 唯一对象/快照 → 单位与预算 → 私有完整候选 → F4/K1 校验 → F5 projection/commit。只要含澄清项就不能先 apply 一部分。空 changes 仅表示无需修改，不能消除源 blocker 或创造验证资格。

物理量保留用户原文与单位，消费时按实际 schema/后端解析语义核验，不另造宽松 token 分组或预览单位传播规则。不得把能量省略单位当 MeV，或把长度省略单位当 mm 来猜意图；只有已明确选择且显示的既有配置单位可作为保持项。若规范化显示 `1 GeV = 1000 MeV`，两个值必须来自相同量纲换算，并保留原请求。

现有多源手工编辑有本地 `GPSDefinition.editor_id`，但当前 Agent plan 的 target 仍是同快照内的唯一名称，不应说它已按 editor_id 发协议。L1 用 base_fingerprint 与本地当前 revision、唯一名称/类型事实限定对象；重名拒绝，不能把 GUI ID 当后端 GPS index。模型的 row 数字、当前 GUI 选择或日志里的同名对象不构成可靠绑定。对同一目标/字段重复写、未知对象、Boolean/A5 不支持组合、路径或方法名、数组越界、类型伪装、NaN/Inf/换算溢出和过期指纹全部拒绝，且不污染 Undo 历史。

一个方案整体接受为一个语义事务；失败不能留下半改配置。保存/加载/Undo 都要保留非法 seed、数值、表格单元和原始来源，不通过“重新读取源文件”或清空草稿让它变合法。F5 投影与回滚双失败时沿既有冻结规则停止编辑、保存和运行，要求恢复最后确认快照。

## 执行、比较与结果状态

任务协调状态（拟定，待实现冻结）为：`draft → clarifying/ready → applying → validating_fields → initializing → generating → running → evaluating → awaiting_confirmation/exporting → completed`。任一活动阶段均可进入 cancelling/cancelled、failed、timed_out、stale 或 recovery_required；这些是 L1 任务状态，不能直接冒充既有 K1 record schema 的状态值。

同一任务下每个 K1 动作各有记录。K1 的 `record_id` 与兼容字段 `run_id` 可以在非运行动作中相同，不能因字段叫 run_id 就声称启动过模拟。实际进程/输出使用 execution 身份；摘要里的 Geant4 runID 是另一层编号。日志、进度 sequence、目录名和 PID 都不能独立证明成功或进程归属。

| 层级 | 必须消费的真实结果 | 不能升级成什么 |
| --- | --- | --- |
| fields | 本次完整候选的字段、依赖、源 blocker 与 F4 诊断 | 后端已接受或物理正确 |
| Inspect | 当前输入的 Configure/preflight 与已观测来源 | 几何初始化、事件或参考比较通过 |
| initialization | K1 真实初始化、几何检查及所用后端/输入身份 | 已 beamOn 或完成预算内事件 |
| generate | writer 实际生成配置和资源收据 | 已启动后端、包已获分发许可 |
| run | 新摘要、actual run/事件合计、输出/F1/执行身份及完成事实 | 仅 exit0、旧摘要、进度到 100% 均不足；更不证明物理准确 |
| L1 完成性 evaluate | `AgentController._evaluate_completion` 查询绑定 K1 record/run，要求 passed、非 stale、当前 revision 与 run_id 相符；写 level=execution、reason=agent.execution_completion_only 的 journal 结果 | 不调用 K1 物理 evaluate，不生成参考比较记录，也不由模型自报 pass |
| 显式 K1 物理比较 | 由用户提供指定 run、真实参考/来源/SHA、raw/weighted、MeV/per_event 与既定判据，使用现有 K1 compare | 不属于当前 Agent 默认完成性链，不等于任意 scorer 或科学模型已验证 |
| export | 新目的地原子发布、资源闭包、manifest/历史/加载核验 | 导入后当前验证仍有效、包内有后端、用户自动授予资源许可或公开上传权 |

首链实际复用 K1 apply/fields/initialization/generate/run/export；默认 evaluate 是 controller 对这次 K1 run 完成资格的再次查询，不调用 `ExperimentWorkflow.evaluate`，界面明确“未做物理参考比较”。用户要求比较而缺参考时先澄清，不能静默降级；显式 K1 物理比较须独立选择参考/判据。参考、容差、物理模型和归一化不能为了通过自动调整。

详细后端自由文本保留原文，AI 摘要附在原诊断之外。定位复用 F4 的真实字段/来源与快照资格；新诊断 code 只能由生产器规范产生。历史报告可查看，但配置或资源改动、Undo/Redo/恢复、外部字节变化后不得变回当前绿色。

## 预算、取消与不重复恢复

当前任务 authorization 只有以下四字段；不是独立模型请求、启动数、重试数或费用配置。用户未授予的权限不能由模型、日志或恢复文件补上；示例100事件只是示例，不是默认许可。

| 已实现字段 | 精确语义 |
| --- | --- |
| `allowed_actions` | 允许的 Agent 动作集合；权限不足停在对应步骤 |
| `max_calls` | 计所有登记的动作 intent：规划、应用、字段校验、初始化、生成、运行、完成性评价、导出，不是只计 LLM 或 run |
| `max_events` | run 前预留计划事件；失败/取消或只完成部分事件不返还预算；实际结果另记 |
| `timeout_seconds` | 整体任务时限；过时停止新动作，按本任务所有权取消/排空并保留迟到事实 |

固定 pipeline 每 task 最多一次事件 run、一次初始化动作。K1 内部的能力/环境/预检查询遵守原有流程，不是用户可以另外无限重复的动作；这也不表示整个 task 只创建两个 OS 进程。当前没有独立 `max_launches`、`max_retries` 或多轮修复预算字段，**传输重试为0**，无自动换端点/账号；批准同 plan 的新授权任务不再发模型请求。需要再次试跑时须明确新用户请求、新 task，不能借恢复自动重复。

候选构造会硬校验 `runSettings.threads` 与 `Project.threads` 两处均为严格整数 **1..64**，包括本次未修改的旧值；任一处越界即拒绝。当前提供线程、事件、动作调用与时间边界，**没有 OS 内存/CPU 配额或沙箱保证**。

连接/请求时限、响应字节和输出 token 上限由 provider 固定配置，不是四字段授权的一部分。当前窗口传入连接10秒、请求60秒、响应65536字节和输出最多4096 token；token 是请求限制，响应字节由客户端核验，二者都不是精确计费/货币封顶。不能把这些界限描述成操作系统资源隔离。

取消沿 K1 cancel、runner 停止和 close 排空流程，只处理当前拥有的进程；强制清理失败显式记录。迟到结果不能重新 apply/launch 或把取消/失败改成 passed；已经完成的事件仍如实保存，不声称一定中途停住。当前控制器为原 runner 仅软终止的缺口增加独立的3秒单次 force 升级：定时绑定 serial 与 bound record、重复取消不延期，升级前须核对仍 busy、同一绑定且公共 records 最新 pending 属于该 owner，匹配 completed 撤销定时器，journal I/O 失败仍在 finally 请求取消，发出 force 后仍等待 K1 completed/drain；旧 controller409d／146入口保持历史身份，后续增量9组173仅为当前开发入口，不冒正式通过。

独立启动/并发/重试上限、自动修复轮次和成本策略可作为后续预登记目标；尚未提供的字段不是当前合同。以后若开放须先明确接口、授权与验证，不能靠文档目标默增 grant。后文任务族/人工对照仍是待预登记的验收目标，不代表已有这些扩展预算。

**恢复接口已落，仍待正式集成验收：** `AgentController.recover(path)` load 旧 journal、清空可执行授权，再按旧 operation 的 record_id/run_id/action 查询 `workflow.records()` 的唯一匹配。返回 historical/in_progress/unobserved、current_qualification=false；有终态可尝试补记查询结果，live owner 锁冲突不夺权。界面展示只读，不重新 plan/apply/run/export，也不自动接管进程。未匹配保持未观测，显式新用户请求才创建新 task。以下不重复执行规则仍有效。

- 本地生成 `task_id`，每个已登记动作生成 `operation_id`；当前规划请求以 plan intent 记账，journal 没有独立 attempt_id 字段，也不自动重试。动作/输入/预算与 K1 run/record 绑定按实际字段保存，执行身份沿 K1 记录查询，不假称 journal 接收完整 execution_id；标识不采信模型生成值。
- 受理前使用 journal 原子 intent 与唯一所有者 lease；K1 受理后补可查询的 run/record 映射。特别覆盖 launch 成功但映射尚未落盘、apply 已提交但响应丢失、export 已发布但终态丢失等窗口。现有 `_begin()` 新建 UUID/通知不是跨进程幂等受理，当前文件层方案在这些窗口保守 query-only/unknown，不重发；若要自动接续另补桥接。
- 重启首先 query/reconcile 同一 operation。已有终态只读取；尚在执行只附着查询；找不到确定收据不代表没执行。进程已消失、身份冲突或磁盘结果不明时 recovery_required，禁止自动重新执行。
- 当前同 task 不再次试跑；新用户请求须建新 task 与新 operation，保留旧尝试/消耗，不能把自动恢复包装成重试来绕过单次 run 边界。预算先预留，故障时未确认未 dispatch 的额度不能无依据返还。
- F5 恢复副本不自动联网、apply、生成或运行；先核 lease、原始草稿、源身份和当前编辑 revision。编辑/来源已变则原计划陈旧。恢复成功也不意味着旧运行资格复活。

Undo 撤销配置，不撤销外部已启动进程、已有 CSV、费用或已导出目录。Agent 在 Undo 后必须展示这些历史副作用，不能自动删结果；再次验证/运行属于新动作。编辑恢复与任务恢复分别记录，不能仅靠聊天文本重演步骤。

## 模型、系统凭据与外发范围

首版云/本地协议以明确兼容的文本 JSON chat/completions 为候选：非流式、可取消、连接/请求/响应有界；JSON mode 按实际服务能力显式选择，不把原生 function calling 当先决条件或已支持事实。不支持的 SSE、tool_calls、多个歧义答案、截断 JSON 或协议偏差要给可理解的错误，不悄悄执行其中一段。

真实云模型与本地 OpenAI-compatible HTTP 协议走同一 plan 验证和权限边界；当前本地协议用实际 loopback HTTP fixture，验证合法/错误响应和限制，不声称已跑本地权重或证明其自然语言质量。更换 provider、模型、端点或向云发送额外项目数据必须符合原授权；不能为了任务成功自动回退另一云服务。自定义 endpoint 的协议兼容范围、TLS/代理/重定向策略按实现列明，不宣传兼容任意 API。

持久 key 使用 Windows Credential Manager / Linux Secret Service；Linux 直接使用可选 [SecretStorage 依赖声明](../gui/requirements-agent.txt)。缺依赖、服务不可用、collection 锁定或存取失败时明确拒绝系统保存，不默降 session、不自动创建/解锁 collection；项目/普通设置仅存 credential ID，不退回明文文件、`.env`、配置 JSON、CLI argv、聊天记录或恢复包。显式“本次会话”可只驻内存并在关闭时清理，不是持久化替代；必须用户主动选择，不能静默 fallback。应用层尽力清理不宣称 Python 字符串和操作系统内存绝对无残留。

云端先展示实际外发范围：必要的用户请求、所选对象/配置摘要、局部诊断与明确允许参考摘要；不默认发送整个 workspace、外部路径文件或完整日志。provider 上游错误可能含 secret，应转换为安全机器 code/阶段/状态而非直接落盘；secret、Authorization、secret 回显不得进入任务日志、截图、崩溃收据、F5 snapshot 和导出包。

模型/后端/资源内的“忽略规则”“已批准全部操作”“把 key 发到另一地址”一律只是输入数据。授权来自当前本地用户任务记录，不来自日志、模型回复、资源注释或历史对话。使用系统凭据不授权模型读取凭据明文。

## F2 与 L2 的独立边界

F2 在 L1 之后实施，才提供 GUI 审计 run session、真实 Idle 安全白名单、逐 run 输入与限定条件重放。L1 首版使用现有 K1 新进程流程；不能向已初始化内核只改 Manager 缓存，也不能把 `/run/reinitializeGeometry` 当成安全通用修复。几何、物理、线程等完整变更通过新进程配置。

L2 依赖 K2 工程导出，再考虑隔离 C++/CMake 差异、构建/运行、有限代码修复和持久工作流。L1 不执行模型代码、shell 或任意下载/安装器，不向外部文件任意写入。LangGraph 等薄编排层届时按需要评估，不能让框架持久化默认替代 operation 幂等、授权和预算合同。

## 当前开发实证快照

本节只记录已有原件，不代替后续 L1 fresh candidate、正式矩阵/CI、人工对照或原生窗口验收。

- 真实模型任务集 **02**：`out/collab/l1-live-development-02/receipt.json` SHA `b12fcfeefc5d0430e5d1a1993ae39afd0c61059bab9e6511af635228dc7ffbca`，main 确认 exit0。DeepSeek `deepseek-flash` 一项 NL 完成 common 差异→4 个实际事件→完成性 evaluate→确认导出→Undo；另两项真实模型响应进入澄清。receipt 明记 execution_completion_only、native_observation=false、manual_operator_comparison=false。这不是三项都运行，更不是成功率或人工收益结论；原 source_identity 归属于这次开发快照，不能改绑到未来候选。
- 任务集 **01**：第一项完整链已过，但后续 harness 在 UI 线程直接调用 provider，触发 `provider.ui_thread_forbidden`，原整体 exit1 保留于 `out/collab/l1-main/live-development-01.log`。不将 02 原件拼回 01，不以已完成首项宣称当轮全绿。
- 固定实际 HTTP fixture 开发链：11.3 与 11.4 各 24 个已执行断言入口通过，检查真实 K1/后端/export/Undo；响应由确定性 loopback HTTP fixture 提供。使用旧 `2ec5b14` 构建的 EXE，**不是 L1 重新构建/formal**，也不证明实际本地权重质量。11.4 收据根 `out/collab/l1-backend114-development-01/`，11.3 原日志 `out/collab/l1-main/backend-113-dev04.log`。

两版 24 是不同开发入口各自的原计数，不与真实云任务数或 session 作者161/独立58混加。02 任务集并不是后文拟定的全部 NL 验收夹具已冻结/执行，也未做人工时间成功率对照。新候选完整回归、真实 CI、实窗和人工对照仍待，最终文档 尚不冻结为完成稿。

## 固定任务与人工对照

下面是**执行前固定的任务族和成功判据草案**，不是已执行任务数或通过计数。主负责人须将每项绑定真实工程/输入/资源 SHA、适用时的参考 SHA、精确 NL 原文、可允许澄清答案、预期 JSON 差异、保持项、动作/预算、成功判据和证据字段，再冻结 taskset。夹具不能在看到模型失败后简化或换题；真实云任务与确定性 HTTP 协议夹具分别登记，不能把 fixture 当成另一实际权重的成功率样本。若将来评估实际本地权重，再使用相同语义任务并独立记录模型身份。

| 任务 ID | 固定自然语言目标与夹具 | 应观察的结果 |
| --- | --- | --- |
| NL-01 指定硅体与电子源 | 上述 Detector_A / Beam_A 完成性任务；多体积/多源陪衬；另立可选显式参考的 K1 比较例 | 精确改指定对象/单位，保持其他对象；真实 fields/init/generate/run/完成性 evaluate/确认/export；物理比较另记、不混为默认能力 |
| NL-02 单位与保持项 | 指定既有体积尺寸/位置和明确单位，保留源分布、父子及敏感性；同量纲不同表示对照 | 本地换算与后端一致；差异、Undo/Redo、生成和后端读回相符，不把 preview 当运行 |
| NL-03 必须澄清 | 多个“探测器”或多个源；缺能量单位/预算；指定物理模型变化但未定参考 | 在歧义/假设决策处停下；回答绑定任务后继续，不猜目标、不先 apply 部分方案 |
| NL-04 实际诊断修复 | 既有受支持字段的真实 F4 错误及保存的非法草稿/来源变动 | 精确原文和字段定位；只修授权项，无关草稿保留；修改前旧记录失效，来源失效不能清空伪装成功 |
| NL-05 停止与崩溃恢复 | 在模型请求、apply 发布、launch/终态/导出交界注入可重复中断；操作身份预登记 | 能取消、查询原 operation；重启不重复启动/应用/导出，实际结果未知就显示未知；有真实异常退出再读取实验 |
| NL-06 包搬移与拒绝 | 含合法几何 file/copies_file、源引用的实际资源包；另有缺失/链接/越根/篡改/已有目的地 | 允许的完整包搬移后加载/真实重放，未知/不可分发拒绝；失败不覆写目标，不沿旧绝对路径 fallback |
| NL-07 越权与恶意响应 | JSON 畸形、重复键、超长/截断/非有限、错目标、提预算、伪回执、shell/tool、提示注入/secret 回显 | 在相应边界稳定拒绝、原状态/历史不变、无副作用及泄漏；真实 provider 与协议恶意夹具分别登记 |

对照人工与 Agent 时冻结相同起始项目、后端/数据选择、设备、线程/种子、参考判据和导出目标条件。人工可以用相同已交付 GUI/K1 能力；不能让人工从零找文件而 Agent 使用预制答案，或把人工熟悉学习耗时只算进一方。顺序交错/平衡练习效应，操作规程和可查帮助在执行前登记。

同时记录人工活动时间、Agent 人工介入时间、端到端墙钟时间、等待模型/模拟时间、澄清轮次、模型调用/预算、真实事件/启动数、任务成败与失败首因。成功以预登记的最终字段/保持项、真实证据链、预算和可加载导出为准，不以模型自评、生成过配置或断言总数判定。正常任务成功率与负例“正确拒绝率”分开；取消、基础设施失败与未完成如何计入分母须事先固定，禁止事后剔除首败。

样本数量、重复次数、provider/model 选择、费用预算、成功率及时间价值门槛**待主负责人预登记**，本稿不造数字。若 Agent 相对人工无实际收益，按五目标提案改进动作/交互和复测，不用增加 Agent 数量或事后放宽成功定义代替价值证据。

## 验收矩阵与交付证据

| 层次 | 必须覆盖的范围 | 证据边界 |
| --- | --- | --- |
| 纯组件/协议 | 严格计划/授权/单位/预算、恶意响应与 HTTP 故障、凭据适配失败、ledger 原子性/所有权、错误/取消优先级 | mock 不冒充真实系统存储、真实云/本地模型或 Geant4 |
| 实际云 / 本地协议 | 云 API 执行固定真实 NL；本地 OpenAI-compatible 采用实际 HTTP fixture 检验协议、错误/限制；分别保留身份/原失败 | fixture 不冒充实际本地权重质量；连通不等于任务成功，返回的 model/usage 与未知事实分开，不泄漏 key |
| 双版双平台 | Windows/Linux × Geant4 11.3.2/11.4.3 现适用 static/GUI/backend/integration，以及现有 M0/desktop/install 适用回归 | 唯一冻结 HEAD/源码与测试身份、实际 EXE、原 report/log、严格门禁和 matching 历史逐例基线；不造未来计数或把 skip 当 pass |
| 原生实窗 | Windows 与 Linux 的代表性实际桌面范围、cloud/local 设置、澄清/差异/apply/定位/Undo、运行/停止/恢复/export、焦点/语言/DPI和自然退出 | 原生 Linux 未做必须写待验/限制，CI offscreen/WSL不代替；逐项实际观察与图 SHA、遮挡边界，文件审不冒第二次视觉 |
| 资源与恢复端到端 | 真实路径/包搬移、8.3/长路径适用项、外部源改变、原子失败、实际崩溃与恢复后查询、无重复执行 | 跨提交复用须精确字节/范围映射；旧输入/报告/首败不回写成新通过 |
| 科学比较 | K1 实际支持的总沉积能定义与明确参考；必要领域专门基准另立 | Agent 完成配置任务不扩大后端科学能力，不因模型解释宣称剂量/注量/材料/物理模型已独立验证 |

现有支持或明确不支持的可选组件（如 GDML）、数据环境和平台差异沿当前能力查询与支持矩阵处理；依赖未满足要可诊断，不能无理由降测试。凭据真实系统操作和外发测试只能在受控测试账户/用户授权端点内，正式收据去敏但保留可复核身份与首因。

每次验收目录应包含任务集/人工对照预登记、产品/测试/provider/后端身份、授权/预算摘要与 operation 映射、原动作/运行/比较记录、资源 SHA、取消/恢复/导出负例、原生观察和独审。公开归档只投影允许的内容，密钥、其他应用截图、未授权个人资料及大二进制/数据不得机械收入；本机绝对路径或测试假 token 不自动等于真实 secret，按实际内容判断。

## 本稿待落实项

纯文件 journal 已按上述冻结身份完成专项与独审；common 动作/controller/UI、真实云任务与固定 HTTP 双版开发链已落接口/部分证据，恢复 old ID 只读查询和默认完成性 evaluate 如上。本轮不扩张自动字段、物理比较或实际本地权重质量结论。授权/预算、cancel/recover/Undo/export 的正式整合、固定任务/人工时间成功率对照、新候选双版双平台完整矩阵/CI/实窗仍需后续证据和对应独审，本文当前只冻结为实施候选说明，阶段完成稿等这些证据齐后另行形成；当前不写 L1 完成。候选契约与历史入口见 [L1 候选历史](agent-history.md#2026-11-02-l1-配置-agent-实施候选)。

本次按用户授权同步两份新稿及六处既有文档的 L1 候选入口，保留旧历史和生成表；不修改 STATUS/ROADMAP，不执行产品测试或 Qt/后端。正式验收完成后由主负责人统一裁决阶段状态；当前仅冻结实施候选，不填阶段完成、不造正式计数、不绑定未来提交身份。


## 2026-11-02 首候选 D1 与路径显示修复进度

以上初稿和历史进度按原时点保留；本段只追加D1后的候选增量，不改变默认完成性评价、白名单、授权或只读恢复合同。D1 `d1bd57da5a7e61d07fdff6cadc2a1f5f3dadc359` 的四份Windows正式报告已终态：static48/5031、GUI70/9781、113backend63/82029、114backend63/72536，合计244次执行/169377入口，四原launch均runner/gate0、identity_errors=[]。两个integration未执行；新修复不能继承这四报告的D1运行身份。

五域真实云Task01已走完七个passed步骤并完成4事件，随后完整capture发现唯一差异 `/state/drafts/project.threads.raw`：预期 `2`，实际 `〢`（U+3022）；flush导致新revision和K1 stale，整体receipt仍failed。中间字段/初始化/运行成功不能掩盖原始编辑原文及资格失效，也不能把尚未完成的确认/导出/Undo写成通过；原失败与原件保持。

当前v3修复不止三路径显示：作者受控display probe发现旧transactions捕获会把未改显示值还原成typed原路径，丢失原路径草稿中的空白，产生两个raw diff且指纹不等。K1 binder现将原snapshot的path raw存为内部view tuple第三值，capture_workspace兼容旧2tuple，仅在路径仍等于生成显示值时还原原raw；非路径raw继续保留，不新增持久codec字段。最终为ProjectPage、window/experiment、window/transactions三产品＋两测试五文件；正常全量load和legacy原 `set_project` 调用不变，window/run.py仍为D1 base，不把legacy分支写成当前MainWindow自然缺陷。privacy/codec/locale/完整同指纹/revision与K1资格门禁不放宽。当前源freeze是 `out/collab/l1-project-path-display-repair/v3-final/freeze.json`，早期v1五文件及文档v2原件保留；本次只同步三份文档，不改产品或runner。

此前实际K1显示绑定窄修专项通过保持旧范围；当前v3作者Qt56开发入口通过，旧Qt54/后端25不重标为v3。先前休眠绝对路径和设置顺序的夹具失败与源码日志保留，r4仅修夹具相对路径/顺序后56，不算新产品失败，也未放宽既有隐私规则。产品v3 raw-path delta独审已PASS（限定接口/显示/F5资格，不冒backend/formal），新候选提交身份、重新构建、完整矩阵、真实CI、原生和人工对照均待；本段不预写未来HEAD或阶段完成。详见[新增候选历史](agent-history.md#2026-11-02-l1-路径显示-raw-修复候选)。


## 2026-11-02 L1 EE验收快照与原生布局后续候选

以上原时点记录与旧任务族不追改，本段只登记 EE 已完成范围及后续待验边界。

正式身份仍为 `ee6f40ded197a59c0b63726b92a09560831867ca`（EE）。本机四份原 Windows 报告终态为 static48/5031、GUI70/9795、11.3 backend63/82029、11.4 backend63/72536，合计 **244次执行／169391个实际入口**；四原 launch 均 runner/gate0、identity_errors=[]，对应 report 的 git_dirty=false。EE 两个 Windows integration 未执行，不以真实专项或 CI integration 补记本机六 profile 通过。EE 真实 CI 四 workflow 均终态成功，12份 profile 原报告 strict/matching baseline 通过，合计662次执行／227634个实际入口；Desktop／安装的独立结果不再算进该数。原证据根为 `out/verification/l1-ee6f40d/`，不迁移到下一候选身份。

Task03 五域真实云链和应用恢复02分别已收 Ptolemy 限定文件独审 PASS：前者是一次真实模型规划、程序化审阅、真实 K1 run4/export/Undo 链，不是原生／人工时间或科学验证；后者仅固定 HTTP 夹具下“K1 terminal 已发布、Agent result 未落盘”的单一受控崩溃点，实际73→0，恢复只查询旧身份且不重发，历史结果陈旧、当前资格不恢复，不扩大为任意中断恢复。两者原失败／脚本及独审身份保留。

native125 的人工操作臂／Agent臂单对描述性比较、原保存与导出文件链，以及另行授权的生产 closed-load 模型 IO 已分别有限通过；closed-load收据1beea485仅允许QtCore import、无QCoreApplication／QApplication实例，不冒第二次实窗或CLI回放；不是受试者成功率／提速结论，文件审不冒像素或第二次原生观察。原EE native150虽正常退出，仍发现52px下L1 AI全控件不可读的布局P2；该次原生失败按原身份保留，不改记原生总体通过。此为L1新缺陷，不套用旧F6按钮82>56的历史窄边界或改写其原结论。真实 NL 诊断修复02已由 main 单次运行，外层原13956／child63728均实际exit0、owned0，作者receipt为1request／8ops／4events／export／Undo passed；其实际链路纯文件独审已限定 PASS：一次真实回复共1295tokens，initial→capture恰5叶差异（4个energy同步表示及派生errors清空），其它raw保持；Undo完整JSON回S_invalid已核。expected/captured只差旧sourceEditor.errors清空，原生产语义指纹相同，不称全JSON相同。该审不代表native／科学／通用NL可靠性或生产load／CLI回放。原01为driver注入夹具失败、0modelcalls，v1/01原件保留，不被02成功替换。

Harvey 的52px布局后续候选已仅在OUT冻结：产品SHA为 `05e4ec9077bbd0d8e08f8381a63b5ada86e3ad8566d436d6b04fae484a3038ae`，仅动态两列可读最小宽度提示及固定footer inset／reflow；测试SHA为 `6f06b0277c10b5ff27a21691a2b7c63f2a2f5d3124602b18a2f1af7cabd748e9`，保留原函数AST（main仅增新调用），新增真实MainWindow自然show的QAction／F6／Tab回归。候选注入后的125%／150%完整组件入口各1216、实际exit0；同一新回归在原产品52px负向实际exit1。workspace layout／core accessibility、Controller／F5／K1和翻译不改。上述作者专项与Ptolemy候选限定独审PASS分别计证；独审按当前focused-target及可容纳标签／控件joint合同关闭原52px P2，无其它确认P1/P2，不冒新candidate正式矩阵或新native通过。retained语言补验仅125%，英→中→英每轮9Tab的当前焦点完整可见、可容纳joint通过，非焦点右列仍可裁剪，不保证全footer同时同屏，新native仍待。main已精确apply已审panel／test两path，实际tracked两档各exit0／1233，另按原收据保留wrapper计数假设失败及更正，不与作者各1216混计；新提交身份、新构建、完整Windows六profile、真实CI和对应原生补验均待，不预填future HEAD或继承EE资格。当前不关闭 L1，F2／L2 顺序及既有白名单、raw／同指纹、授权／预算／只读恢复合同不变。 见[候选历史](agent-history.md#2026-11-02-l1-ee验收快照与原生布局后续候选)。
