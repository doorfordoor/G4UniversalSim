# L1 配置 Agent：实施契约

日期：2026-11-02。共享分支 `roadmap/L1-config-agent`；开工基线 `4840e62e6c2efe935e74e5b934f6194c6aa7731c`。用户已授权推进 ROADMAP 的完整 L1，F2 后续实施。本文件是开工约束，**不是实施完成或验收通过记录**。

本次文档写者最初独占本文件与[中文初稿](../../L1配置Agent.md)；本轮按用户新增授权，再同步 docs/agent-history.md 末尾、AGENTS.md §0、gui/AGENTS.md、gui/docs/中文快速使用说明.md、docs/功能支持矩阵.md 人类节及 docs/开发路线图.md 的 L1 候选条目。六份既有文档只插入新内容，保留旧历史、原换行和生成表；过程及冻结收据写 `out/collab/l1-docs/`。不修改 STATUS、ROADMAP、产品或测试，不运行 Qt、后端、构建，不提交。产品所有权与正式冻结由主负责人负责，共享区其他作者文件不属于本次写入范围。

## 1. 事实依据与阶段边界

先读[ROADMAP](../../ROADMAP.md) L1/F2/L2、[五项目标提案](20261029-1140-astra-product-roadmap.md)、[K1 实施契约](20261031-k1-execution.md)、[可信实验工作流](../../可信实验工作流.md)、[F4 结构化诊断](../../结构化诊断与定位.md)、[F5 实施契约](20261030-2155-astra-f5-execution.md)、[配置撤销与恢复](../../配置撤销与恢复.md)，及 [agent-history](../../agent-history.md) 中匹配的 F4/F5/K1/J2 条目。带日期的旧项目 v7、旧编辑限制与候选状态不覆盖当前代码事实；当前 Project 为 v8，外层快照为 `g4usim_edit_snapshot_v1` / version 1。

L1 交付云模型 API-key / 本地模型接入，以及基于现有配置能力的完整任务闭环。可写范围由**显式动作白名单、编辑绑定、后端能力与用户授权共同限定**，不能从 EffectiveConfig 读回字段推导，也不能因 J2 可手工编辑就自动全部授权给模型。手工编辑覆盖、Agent 动作覆盖和运行/科研证据分别列明；小白名单先跑通首链不等于完整 L1 验收。

- **L1**：在本轮 common 白名单内修改既有目标与 mono/point/fixed 源的受支持字段，校验、生成、启动独立进程、读取完成证据、确认/导出。默认 evaluate 只检查绑定 K1 run 的完成性，不调用 K1 物理比较；后者必须由用户提供明确参考，经现有 K1 比较入口另行执行。保持 K1 配置与资源闭包规则，不宣称自动覆盖所有 J2 字段。
- **F2（L1 之后）**：GUI 控制活跃 Geant4 会话，在实际 Idle 状态按专门白名单调整，逐 run 保存输入/来源并限定环境重放。L1 不借用未来 F2 开放热修改，不把已有 `csh` 或某个 setter 当成 F2 已交付；完整换配置仍用新进程。
- **L2（另阶段）**：依赖 L1/K2 的隔离 C++/CMake 工程修改、构建、有限修复与持久编排。L1 不执行模型输出的脚本、shell、源码、动态插件或任意文件操作；不因此引入代码 Agent 或承诺任意长任务自主科研。

## 2. 可实际使用的首条链

固定链路为：自然语言 → 绑定目标/源/单位/预算 → 严格 JSON 差异 → 本地白名单候选 → F5/K1 原子 apply → fields → initialization → generate → run → 完成性 evaluate → 证据摘要 → 确认/export。物理 compare 不在默认链内；有显式参考时另走现有 K1 流程。

1. 入口由 F5 所有者刷新尚未结束的编辑事务并捕获完整主项目快照，包括非法原文和来源阻断；不得以过时 `session.current()` 绕过可见草稿。检查忙状态、编辑故障和源变化。
2. 把用户意图固化为本地任务约束：现有目标体积与源、量纲/单位、保持项、输出指标、事件/调用/重试/时限预算，以及授权动作、数据外发范围和导出目的地。任务约束不由模型自行签发。
3. 对“探测器”“那束粒子”等非唯一指代、未说明单位、相互矛盾要求、缺失关键事件预算、参考/物理假设变化，先澄清。无歧义且已授权的步骤继续执行，不在每个服务动作前重复征求许可。
4. 模型只返回数据差异和澄清项。严格解码后按同一基线快照解析对象，拒绝未知字段/动作、重复修改、越权目标和越预算值；本地计算 before/after 展示，不信任模型声称的旧值、验证通过或执行结果。
5. 在私有完整快照上构造候选，通过现有编辑绑定同步 typed 模型、raw drafts 和表格镜像；保留无关非法草稿和来源事实。最终通过 `ExperimentWorkflow.apply()` 与既有 F5 projection 发布一个语义事务。任何预检/投影失败均须原子回退，不能出现模型变了而控件/草稿未变。
6. fields 与初始化使用真实 K1 服务。Inspect 只表示 Configure/preflight；初始化不表示事件完成。初始化不得越过首个 beamOn 偷跑事件；不因模型建议降低已有几何、资源、F1 或物理限制。
7. 生成与运行绑定同一获接受快照、实际资源、后端/环境与预算。每次启动复用唯一 runner；工作目录和长路径复用 `backend_launch`，不另建 subprocess/QProcess 所有者，不更改宿主 cwd。
8. 当前 `AgentController._evaluate_completion` 查询已绑定 K1 record/run，要求 passed、非 stale、当前 revision 与 run_id 一致，写入 level=execution、reason=`agent.execution_completion_only` 的 journal 结果；不调用 `ExperimentWorkflow.evaluate`。用户明确要求科学比较时，先选定真实参考和判据，再经现有 K1 比较入口执行。K1 当前比较限完整逐事件敏感体总沉积能均值/标准误，含 run、raw/weighted、MeV、per_event、参考来源/条件/文件 SHA；不能临时创造参考或把完成性写成物理通过。
9. 汇总逐阶段真实状态、差异、预算消耗、未观测项和输出位置。导出遵循用户已授予的目的地/范围；未授予则在具体可审阅结果上确认。配置确认、保存项目、导出离线包和公开上传是不同动作；L1 导出不隐含上传许可。

本轮自动写入固定为 generated 模式的既有对象 common 白名单，源只接受 mono/point/fixed；不新增对象、不自动编辑谱/体源/高级分布或其它未列字段。原几何复制模式（geometry.source_copy_mode）由 writer 复制原文件，不消费 volume editor 差异，所以 Agent 拒绝该模式的全部 volume 修改（`agent.original_geometry_copy_is_read_only`），run/source 等其它已允许字段仍可修改；不改变 K1 原复制兼容语义。模型读取上下文来自 UI 刷新/捕获的快照，经 `planning_context` 选择字段；受信写入参数实际名为 `write_scope`，由本机 UI 构造对象/字段范围，不能让模型自批。须完整列明可写、只读、需澄清或需人工编辑的边界及测试；完整 L1 验收还包括 provider、授权、预算、恢复、价值对照与正式矩阵，不等于把全部 J2 字段开放给 Agent。unsupported 分支保留人工接续，不扩张实体、assembly 或科学支持。

## 3. 共用接口与当前缺口

| 边界 | 已有基线接口/事实 | L1 必须补全；未完成不得冒称 |
| --- | --- | --- |
| 配置所有权 | `WorkspaceSnapshot`、`EditSession`、窗口 `capture_workspace` / `apply_workspace`；单调 revision | 捕获与 apply 的所有者线程适配；不覆盖尚未提交 raw draft；所有用户/模型入口共用事务 |
| K1 动作 | `ExperimentWorkflow.inspect/validate/apply/generate/run/evaluate/export`、`cancel/close`，动作支持 `expected_revision` | 有界任务协调器、授权检查、预算累计、进度和终态投影；不另造领域执行器 |
| 身份 | K1 `record_id/run_id/session_id`、实际启动/结果中的 `execution_id`，配置/资源/执行 fingerprint | `TaskJournal` 持久 intent/有限绑定；`AgentController.recover(path)` 已按旧 operation/run/record/action 查询公共 K1 records，只读显示，不重发。集成仍待新候选正式验收；不是跨进程原子受理 |
| 诊断 | F4 code/location/source/identity 与原文，按快照失效 | 复用结构化位置；模型解释不能改 severity/blocker 或伪造来源行；同 identity 不等于当前资格 |
| 撤销/恢复 | F5 全编辑快照、Undo/Redo、OS lease 和未命名 dirty 恢复副本 | 任务恢复与编辑恢复分开；恢复不执行；Undo 不删除/撤回外部运行或导出事实 |
| 模型与凭据 | `agent/provider.py`、`credentials.py`、`actions.py` 接口已落，并有真实云/实际 HTTP fixture 开发证据 | 各专项收据与正式候选/矩阵/实窗分别计证，不以文件存在或开发链通过宣称整阶段完成 |
| 有界 journal | `agent/session.py` / `TaskJournal` 已冻结并通过纯文件独立窄审 | 只证明文件/lease/预算和保守 query-only，不替代 K1/controller 集成、provider 调用记账或正式验收 |

源码路径和精确现有签名见[中文初稿](../../L1配置Agent.md)。新增 journal 冻结 SHA 为 `7d3672793066112259ac3a780433bb13e7bac22494044904a47021ceb19cadc3`：作者七组/161 入口只读核证，独立新增四组合/58 入口通过，证据根 `out/collab/l1-session-independent/`；两者不相加、不升级整阶段结论。新增接口先报主负责人，由其协调 K1/F5 所有者；不能用私改 K1 历史格式掩盖恢复缺口。

## 4. 授权、歧义与不可信内容

当前 authorization 严格只有 `allowed_actions`、`max_calls`、`max_events`、`timeout_seconds` 四字段；用户请求、快照/对象绑定、计划、单位/科学保持项和提供方/导出选择分别属于其它本地上下文，不是悄悄新增的授权字段。白名单和预算由本地代码实施；模型返回 `approved=true`、日志文字或旧会话聊天都不能扩大权限。

本轮 Agent 以同一快照内唯一名称作 target selector，并核对 base_fingerprint/revision；手工多源已有 `GPSDefinition.editor_id`，不等于当前 Agent wire 协议已使用该 ID，也不能信任模型生成的新 ID。对象以快照身份加唯一选择限定，重名拒绝，不能靠行号或当前 selection 猜测。改名、重排、源字节变化或项目切换后重新解析，不重定向到“看起来相似”的对象。

澄清条件包括：多个候选/没有候选、无单位或量纲不符、跨分布/多源强度语义、物理列表/模型或 cuts 改变、剂量/注量归一化与权重定义、参考和判据变化、资源使用权/数据外发范围不明，以及预算不足。已明确授权某项科学设置时可以按原范围执行；不得强制重复询问，也不得为了任务通过擅自改参考、容差、几何、粒子或统计定义。

项目说明、外部文件、模型响应、后端 stdout/stderr 和历史日志均为数据，不能授予工具权限、索取密钥、添加网络端点或指示忽略白名单。诊断修复必须仍产生同样受约束的候选差异。不得把“不再显示错误”当修复。

当前 UX 新接口为 `AgentController.approve_with_authorization(authorization, *, auto_run=False, write_scope=None)`。默认 plan-only 先返回可审阅 diff；用户在当前 UI 改选执行权限/预算后点击 Apply，才对**同一个 base_fingerprint 与同一份 plan**明确授予新执行授权。接口先核当前 revision/快照、无澄清/活动步骤和授权/候选预算，必要时核传入 write_scope，再创建**新 TaskJournal / 新 task_id**，写入原 plan、新 UI 授权及 reason 事件 `agent.reviewed_from:<旧task_id>`。旧 task 追加取消历史，其原 authorization/已记账用量不被改写；本动作不再调用 LLM，也不把旧 plan-only grant 原地提升。

该接口不是恢复授权入口：`_recovered` 显式阻断从恢复文件读出的计划，即使用户重新勾选权限也不能经此 API 执行，须从新 prompt 发起新任务。各后续步骤逐项检查新 grant，权限不足就停在对应步骤；run 还受 auto_run/显式继续约束，不自动勾选、扩 grant 或重调模型绕过。主线程已确认此 UX 与核心专项独审通过；最后其他所有者忙状态 P2 已按 controller `409d6a4a`／窗口适配 `9689acb7` 定点关闭，取消/关闭不得误停其它任务的 K1 工作。这是专项结论，不是完整候选或 L1 阶段验收。

## 5. 有界执行与恢复

当前实现的授权封套固定为四字段，缺失/未知字段按严格 schema 拒绝，不能将函数默认值当用户许可：

- `allowed_actions`：允许的 Agent 动作集合；不在集合中的步骤停下，不从日志或模型补授权。
- `max_calls`：累计计所有已登记动作 intent，包含规划、应用、校验、初始化、生成、运行、完成性评价和导出，不是仅计模型请求或事件 run。取消/确认等状态变化及 K1 内部查询不能被当成另一个可无限调用的选项。
- `max_events`：事件运行前预留计划事件；失败/取消或部分完成不返还额度，实际完成数另存，未知不能填计划数。
- `timeout_seconds`：当前任务的整体时限；超时停止调度并按既有所有权取消/排空，迟到实际结果保留，不翻转终态。

固定流水线在每个 task 内最多一次事件 `run`、一次初始化动作；K1 内部能力/环境/预检查询沿已有流程，不是独立可选无限动作。当前没有独立 `max_launches`、`max_retries` 或多轮自主修复字段，也不等于整个任务只创建两个 OS 进程。传输重试为 **0**，不自动换端点或再次调用模型；新授权批准同 plan 无需重调模型。再次试跑须明确新用户请求、新 task，旧消耗与历史保留，不能靠恢复自动刷新预算。

候选对 `runSettings.threads` 和 `Project.threads` 两处都要求严格整数 **1..64**，任何一处越界都拒绝，包括用户本次没改的旧值。线程、事件、动作调用和时间是明确边界，**不提供 OS 内存/CPU 配额或沙箱保证**。

请求/连接时限、响应字节和输出 token 上限来自 provider 的固定配置，不是 authorization 的附加字段。当前窗口配置为连接10秒、请求60秒、响应65536字节、请求输出最多4096 token；这是传输/响应限制，不是准确费用上限，也不能据此声称操作系统资源隔离。停止宽限/强制清理沿 K1 cancel/close 所有权，清理失败须可见。

更多独立启动/并发/重试预算及成本策略仅是可预登记的后续扩展目标，当前不据此增加字段或放开自动重试。若将来实施，须先版本化接口、登记范围并测试，不能将目标描述当已实现。原任务族和人工对照预登记保留其未来验收属性。

恢复必须先查操作身份，再决定展示或继续：

1. 在副作用 dispatch 前原子登记不可复用的 `operation_id`、输入/授权/预算身份、动作及预留额度；禁止两个窗口/恢复进程同时拥有同一活动任务。OS lease 不能被 PID 或超时猜测替代。
2. K1 受理后记录可查询的 run/record 绑定；服务事件通知不是可靠提交日志。当前 `TaskJournal.record_intent` 在返回前原子发布，`record_binding` 可补映射，但不提供 K1 原子受理。对“已 launch、映射未写”窗口必须保守 query-only/unknown，不能重发。若后续需要自动接续，须另补由执行所有者受理 operation 身份的桥接，不能把当前方案称 exactly-once。
3. 当前 `AgentController.recover(path)` 按 journal 中旧 operation/run/record/action 匹配当前 K1 公共 records，返回 historical/in_progress/unobserved 和 `current_qualification=false`；不 apply/run/export，不自动接管进程。终态查询结果可以尝试写回 journal，live owner 锁冲突保持只读，不夺锁。未找到不代表从未执行；新用户请求必须新建 task 并重新核对 live identity，不能让保存的授权恢复执行权。无权控制的进程不能 kill。
4. 进程/收据缺失或冲突时标为结果未知并停止该副作用；不能把“没查到”当“未执行”。需要人工对账时说明具体未知事实，不能恢复后无条件再跑。再次执行须明确新用户请求与新 task，分配新的 operation，旧失败与预算历史仍保留。
5. 当前快照、外部源、环境或授权已变则陈旧，重新校验后才能继续；恢复和 Undo 不使旧验证复活。当前 `TaskJournal.load` 恢复实例永久禁止新 intent/set_plan/执行态 transition，连同态 running 也拒绝；仅允许中断/取消及补查询结果。要继续执行须显式新用户请求、live identity 核对和新 task，保留旧预算与历史，不能自动新建任务重置预算。F5 恢复不自动网络请求或启动后端。

## 6. Provider、凭据与记录

云端与本地都通过统一文本/JSON 协议适配层进入同一本地验证器；不能把“OpenAI-compatible”当作所有供应商、原生 tool calling、JSON mode、流式或重试都已支持。首版协议可非流式，明确不支持的响应与能力；UI 仍须可取消且不阻塞所有者线程。

持久 API key 只存系统凭据服务：Windows Credential Manager、Linux Secret Service。Linux 实现直接使用可选 `SecretStorage`（见 `gui/requirements-agent.txt`）；依赖缺失/服务不可用明确拒绝 system 存储，不默降 session 或明文文件，也不自动创建/解锁 collection。无系统存储时不可持久保存，不回退 `.env`、项目、导出包或 keyring 自动选择的未知后端。若提供显式“仅本次会话”，须仅驻内存、用户主动选择、关闭清理且不可宣称系统持久化；不能在系统存储失败后静默切换。

模型设置只存 credential ID；不在 CLI 参数、调试日志、异常、聊天历史、恢复快照或包 manifest 写 secret/Authorization。云端须明确端点和外发字段；本地 HTTP 仅限实际 loopback，远端按受信 HTTPS 策略。重定向、代理和端点变化的实际策略逐项记录，不默默转发凭据；不自动选择另一个模型/云服务来绕过失败或授权。

任务记录保存必要的授权与状态事件、操作/输入身份、精简差异、诊断引用、预算和原始结果归属；去敏规则不修改原 K1/F1 证据。普通日志既不是权限凭证，也不是可执行恢复指令。导出只含按策略允许的配置/资源/证据，原聊天/密钥/系统本机布局默认不进入。L1 的配置包仍遵循链接、越根、重复/未用资源和原子发布拒绝边界。

## 7. 实施与冻结顺序

1. 主负责人确认动作/任务/恢复接口和文件独占；模型传输、凭据、计划 codec 与授权、任务 ledger、UI 接线分工明确。轻量显式状态机先行，不为“多 Agent”另引入领域状态所有者。
2. 首链真实联通，固定本轮 common 白名单和受拒绝分支、人工接续；完成 provider/授权/预算/恢复/确认导出等整项接口，不把一例首链通过当完整 L1 验收，也不借“完整”之名扩大 Agent 可写字段。
3. 覆盖非法响应、越权、单位/多源、外部源变动、忙时/迟到回调、保存与恢复失败、cancel/force/Undo/export；不同作者独立复核。
4. 固定新候选产品/测试和任务夹具身份，预登记人工对照方案和门槛，再执行完整 Windows、真实 Linux、两 Geant4 版本现适用矩阵、真实 cloud NL 与 local OpenAI-compatible HTTP 协议反例及原生 GUI 验收。本地 HTTP fixture 不证明实际本地权重的质量。旧失败保持原字节；测试/门禁/统计不能为凑计数改绿。
5. 全部必需证据及独审齐后，主负责人再同步阶段文档、冻结/提交/映射/集成；本开工稿不预填完成、报告数、成功率或未来 SHA。

## 8. 验收记录要求

[中文初稿的固定任务与验收表](../../L1配置Agent.md#固定任务与人工对照)是预登记骨架，执行前须填真实起始工程/资源 SHA、预期差异、提供方/模型标识、预算、人工操作规程、样本与阈值。验收至少证明：

- 真实自然语言驱动上述完整首链，指定对象/源/单位和科学保持项正确；读取真实结果，按授权导出并离线加载核验，不只测 parser 或 mock 响应。
- 同一固定任务对照人工活动时间、端到端时间与成功率；拒绝/失败/取消按预登记规则计入或单列，不能事后挑题、删首败或用断言数代表使用价值。
- 云 API 有实际模型 NL/澄清和端到端记录；本地 OpenAI-compatible 协议使用实际 loopback HTTP fixture 校验合法/恶意响应与限制，不冒称已测本地权重理解质量。真实云、确定性 HTTP fixture、组件注入分别计证。
- cancel、恢复和异常退出后没有重复 operation/launch；Undo/Redo 恢复完整草稿并使验证陈旧；导出缺资源/越根/篡改/已有目标失败保持原子性。
- Windows/Linux、Geant4 11.3.2/11.4.3 与现有严格基线逐项核验；不默认加入 11.2。真实窗口观察与 offscreen、组件、后端、科学比较分别计证；Linux 实窗若未执行明确待验，不能冒称 CI offscreen 已覆盖。
- 视觉验收记录实际看到的范围、DPI/语言、键盘/焦点/滚动、凭据设置、澄清/差异/运行/停止/恢复/导出和正常退出；截图路径或矩形 containment 不等于已观图或无遮挡。

## 9. 当前开发证据快照（不是候选验收）

- `out/collab/l1-live-development-02/receipt.json` 原 SHA `b12fcfeefc5d0430e5d1a1993ae39afd0c61059bab9e6511af635228dc7ffbca`：main 确认 exit0，真实 DeepSeek `deepseek-flash` 一项 NL 任务完成 4 事件、导出、Undo，另两项真实响应为澄清。evaluation_scope=execution_completion_only，native_observation=false、manual_operator_comparison=false；不能据此给成功率/人工收益结论。
- 旧 `l1-live-development-01` 虽首项完整链已过，harness 后续在 UI 线程直接调用 provider，被 `provider.ui_thread_forbidden` 拒绝，原整体 exit1 保留；不能用 02 的通过回填 01 或拼成全绿。
- 11.3/11.4 固定 HTTP fixture 开发真链各 24 入口通过，使用旧 `2ec5b14` 构建的 EXE；不是 L1 重新构建，也不是正式双版矩阵。模型响应为确定性 HTTP fixture，不等于实际本地权重质量。

本稿现冻结为准备正式验收的实施候选契约，新增长期入口见 [L1 候选历史](../../agent-history.md#2026-11-02-l1-配置-agent-实施候选)。核心专项独审已收齐；新候选构建、完整矩阵、真实 CI、人工对照及原生窗口验收尚待，不预填阶段完成、正式通过计数或未来提交身份。
