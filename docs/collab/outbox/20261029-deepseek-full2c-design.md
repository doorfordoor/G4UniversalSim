# DeepSeek 完整2C前端设计与裁决

基线f25da40；实际API https://api.deepseek.com/chat/completions，requested/returned model deepseek-flash，response ID aa61b350-810e-4eb2-87d3-654a86f3a8e2。输入仅现有读取器/页面及2C契约，无密钥或无关代码。设计已真实返回；协作代理后续因模型capacity停止，不是DeepSeek请求失败，禁止重复调用来制造进展。

## Astra采纳与纠偏

采纳对象摘要、多快照选择、字段新增/删除/类型与来源差异、独立unknown/陈旧/覆盖提示、来源链表与中英主题、显式大小限制诊断。保留既有4MiB单文件限额并测试多文件累计限额；测得真实快照规模后再决定是否需受控扩展。

明确不采纳：无需求的schema v2改名；requested必填（与显式null/未知既有契约冲突）；把不同输入文件的SHA不等判陈旧（多文件本应不同）；凭input_sha或generated_at推断跨运行归属/时序；configure/master缺thread一律缺陷；用假定典型文件大小代替真实测量。继续v1增量扩展，以后端真实session/stage/run/thread证据判归属，JSON差异可跨独立文件对比但不宣称新旧时序。revision是成功配置事务计数，不能比较两个进程新旧。

以下为原建议，作为设计输入而非实现事实：

# EffectiveConfig v2 只读页增量设计

结论：**4 MiB 暂不改，但需增加"显式超限诊断 + 建议分片"契约**。当前限额是原子替换与防抖上限，v2 引入 11 消费者 × origins/thread 证据后，典型快照仍在数百 KB；改限额会掩盖一快照一 run 的边界。真正风险是"超限后静默陈旧"，而非容量。

## 一、后端最小附加契约（schema v2，全增量）

在现有 `parse_snapshot` 校验基础上追加，不新建文件、不改架构：

1. **顶层新增**（可选、只读）：`producers`（11 消费者签名的 `{id, origin_sha, alive: "yes"|"no"|"unknown"}`）、`input_sha256`、`generated_at`（原样字符串，**禁止**用于跨进程时序比较，仅用于展示）、`coverage: {"complete": bool, "missing_consumers": [...], "reason": str?}`、`limits: {"max_bytes": 4194304}`。
2. **字段新增**：`requested` 必填；`resolved`、`resolved_source`（`"default"|"file"|"cli"|"env"|"consumer_override"`）；`resolved_reason`（enum：`"not_set"|"absent_all_sources"|"stale"|"overridden"|"unknown"`）；`thread: {id, ordinal, evidence}`（仅 `stage=="run_begin"` 可非空）；`origin_chain` 复用现有 `origins`，但要求每个 origin 增加 `order`（整数）与 `input_sha256`（必填），**旧 origin 若缺 input_sha256** 视为 v1 兼容原样呈现，UI 标 `来源 SHA 未提供`。
3. **校验约束**（保序、拒非法）：
   - `application_status=="applied"` 时，`evidence_level` **仍不得**为 `manager_accepted`（已由现有校验强制，无需改）。
   - `evidence_level=="manager_accepted"` 时 UI 必须显示"manager 已接受，内核未证实"，不得渲染为 applied。
   - `revision` 严格单调，但**禁止**用其推断跨进程顺序；仅用于"同一快照内相对新旧"。`applied_revision` 若存在需满足 `<= revision`（现有）。跨快照比较只允许 `input_sha256` 与 `generated_at`，且 UI 逐项声明"不可用作时序"。
   - `coverage.complete==false` 或 `missing_consumers` 非空 → UI 顶部"覆盖不完整"，且不因 incomplete 而判失败。
   - 超限：`load_snapshot` 保持现状，仅把错误码细化到 `SnapshotError("Snapshot exceeds 4 MiB limit (N bytes)")`；前端按钮旁呈现"建议后端按 consumer 分片"提示，**不自动改限额**。
   - 兼容 v1：顶层仍校验 `schema in {"...v1", "...v2"}`，v1 字段用 `MISSING` 上游即可，现有 `_unknown()` 已能覆盖"v1 缺 requested/resolved"。
4. **线程证据**：`thread` 缺失≠未知；若 stage=`run_begin` 且 `thread` 缺 → `coverage.missing_consumers` 应包含对应 consumer，UI 标"线程证据缺失"，不得默认通过。

## 二、UI 布局（保持 split tree|tabs，仅增控件）

1. 顶部状态用四段条：**阶段 badge**（configure/run_begin/finalization）、**run_id + thread**、**revision/input_sha256**（生成时间展示但带"非时序"图标/文案）、**coverage chip**（complete/missing/unknown）。
2. 过滤栏新增三项（与已有 search、unknown_only 并排，不拥挤）：
   - `消费方` 下拉（含"全部/11 消费者/unknown"）
   - `阶段/run/thread` 选择器（仅 v2 出现；已加载多文件时按 `input_sha256` 分组呈现"文档集"）
   - `仅用户覆盖项` 复选框（`resolved_source in {"cli","env","consumer_override"}`）
3. 多文件：定义"文档集"= 按顺序加载的 N 个快照；按 `input_sha256 + stage + run_id(+thread)` 分组，组内按 stage 排序（configure < run_begin < finalization），**仅同一文档集内**可视作阶段推进展示；跨文档集视为独立，UI 不连线。当前 `snapshot_path` 单文件 → 保留 `snapshot` 单文件主展示，新加 `documents: list`，`active_document` 索引。
4. 右面板 Tab 保留。字段详情区改为三段：
   - **值段**：requested / resolved / unit / application_status / evidence_level / revision / applied_revision / reason / resolved_reason
   - **来源链段**：origins 按顺序表（来源类型、file、section、key、line、alias、input_sha256），缺失标灰与"未提供"；源 SHA 与快照 SHA 不一致时红标"陈旧来源"。
   - **运行时证据段**：evidence_source 与 thread 对象；无 thread 显示"线程证据缺失"。
5. **unknown/陈旧/不完整的视觉**：unknown 仅在"字段级真正未给"时使用；陈旧=当前快照为上一次有效（已有 stale）；覆盖不完整=coverage chip + 顶部 banner；三者分别用不同色/图标，并配文本，颜色非唯一通道。
6. 中英：`refresh_language` 已用 `ui_text`，新增文案全部走 `ui_text`，`_populate` 与 `_selected` 内不再硬编码英文，改为 `ui_text` + `ui_format`。

中文关键文案（供 `ui_text` 词表补充）：
- "覆盖不完整：缺少 {n} 个消费方"
- "未知（未提供）"（已有）
- "陈旧：正在展示上一次有效快照"
- "来源链（按记录顺序）"
- "来源 SHA：未提供 / 与当前快照不一致"
- "阶段 = run_begin，但未提供线程证据"
- "revision 仅限本快照内相对比较，不作跨进程时序依据"
- "manager 已接受 ≠ 内核已生效 ≠ 仿真成功"

## 三、验收（可自动化的最小集）

1. **Schema 兼容**：v1、v2 样例各一，`load_snapshot` 均成功；v1 缺 `requested` 时 `_unknown` 为真。
2. **安全边界**：`applied + manager_accepted`、`applied` 缺 `evidence_source`、`applied_revision > revision`、非有限数、重复 path、超 4 MiB 均 `SnapshotError` 且错误码明确。
3. **不可推断**：构造两快照 `revision` 逆序但 `input_sha256` 一致，UI 不出现"较新/较旧"判定。
4. **多文件分组**：加载 A、B、C 三快照，切 stage/run/thread 后 tree 仅显示当前组字段；跨组不通。
5. **覆盖不完整**：`coverage.complete=false` 时 banner 出现、"仅未知"过滤不加权成败、run `thread` 缺 → 提示且不通过。
6. **来源链**：origin 的 `input_sha256` 与顶层不一致时展示"陈旧来源"且不判 applied。
7. **i18n/主题**：中英切换后所有新控件文本切换，`refresh_language` 重跑 `_populate` 保持选择与筛选；无硬编码英文。
8. **限额**：构造 4 MiB+1 字节 → 原有限额错误、按钮旁分片建议可见、`stale` 仅在已有有效快照时为真。

不回填 `applied/success`，不让 manager_accepted 触发 applied 状态，不用 revision 做跨进程排序——三条边界在上述契约与验收中均为强约束。
