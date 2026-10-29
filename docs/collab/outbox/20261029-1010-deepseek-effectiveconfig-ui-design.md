# DeepSeek API 前端设计建议

实际模型：deepseek-flash；用户授权调用。设计建议待 Astra 审查，不是实现证据。

# 2C 有效配置只读审查界面设计

## 1. 目标与边界

新增“有效配置”只读审查页，展示后端导出的 EffectiveConfig 快照，供用户按对象/字段查看 requested、resolved、application_status、applied_revision、evidence_level、reason、来源链、manager/kernel 证据及独立 run_result。

边界：GUI 不解析 INI/macro，不重算 resolved，不判断 auto/off/on，不推导依赖，不比较 revision 判成功，不把 manager_accepted 当 kernel_applied，不根据 applied 或进度推断运行成功，不生成伪快照、不编辑、不应用、不新增物理字段。off/on/auto 仅作为后端 token 展示；三态校验不在前端重做。

## 2. 信息架构与布局

导航名“有效配置”，页标题“有效配置审查”，标题旁固定“只读”徽标。页面置于“配置”之后、“运行”之前。

顶部工具栏：
- 快照加载/刷新按钮、快照来源说明；
- 时点下拉：Configure（macro 前）、Run begin、Finalization；
- 搜索框：对象名、stable ID、canonical path、字段名；
- 筛选：仅差异、仅 unknown、仅实验性、仅未应用；
- 快照元信息条：snapshot_id、revision、created_at、time_point、run_result 独立徽章。

主体为 QSplitter：
- 左：对象树。层级“模块 > 对象 > 字段”，列显示名称、状态摘要、unknown 数。对象节点默认折叠字段，选中对象后在右侧显示对象级摘要。
- 右：对象摘要卡片 + 字段证据表。摘要含 stable ID、canonical path、模块、名称、字段统计、来源链折叠。字段表列：字段、Requested、Resolved、Application status、Applied revision、Evidence level、Reason、来源。字段行展开显示来源链、manager_accepted、kernel_applied 两个独立证据块。默认对象级摘要，展开后看字段级差异。
- 底部可折叠“原始 JSON”，只读、可复制当前对象或整份快照。不提供保存配置、应用、编辑、运行按钮。

字段表允许横向滚动和本地排序；默认按后端稳定顺序，排序/筛选不改数据语义。

## 3. 状态转换

| 状态 | 触发 | 表现与操作 |
|---|---|---|
| Uninitialized | 首次进入 | 空态说明，允许加载快照 |
| Loading | 加载/刷新 | 保留旧快照并显示“刷新中”，禁用重复加载；不阻塞主线程 |
| Ready | 快照有效且有对象 | 树/表可用；选择、展开、搜索、筛选 |
| Empty | 无快照、无对象或该时点未生成 | 分原因显示；不生成伪快照 |
| Partial | 快照有效但部分字段证据缺失 | 页面仍 Ready，字段显示 unknown，不阻断整体 |
| Unsupported | schema_version 不支持或必需字段缺失 | 显示原因和原始 JSON，禁用解释性展示 |
| Error | JSON 损坏、读取失败、进程失败 | 保留上次有效快照，横幅显示错误；可重试 |

选择对象、展开字段、切换筛选只改变选择态，不重新请求后端。刷新采用整份替换，禁止新旧快照字段混合。关闭页面时终止正在读取的 QProcess 并等待结束。

## 4. 来源、unknown、实验性表达

- 来源链按后端顺序展示 `kind`、文件、行号、原始值；缺文件/行号显示“来源位置未知”，不补猜。来源链可复制。
- requested/resolved 原样显示；单位、布尔、枚举 token 不翻译；旁边可给静态中文解释。
- 值为 `null`、字段缺失、evidence_level 缺失或为 unknown 时，统一显示“未知（后端未提供）”，使用中性徽标+文字，不显示为 0/false/default，也不归为成功或失败。对象摘要统计 unknown 数。
- 实验性分开展示“实验性（schema）”和“运行时能力：支持/不支持/未知”。schema 或 runtime 缺元数据时显示“未知”，不默认 supported。实验性徽标不表示已验证，不阻断只读审查。
- manager_accepted 与 kernel_applied 分列，值可为 true/false/unknown，禁止合并成“已应用”。application_status 保留后端原 token；applied_revision 只显示，不据此推断事务成功。
- run_result 使用独立徽章；缺失显示 unknown。进度、application_status、manager_accepted 均不得替代 run_result。

## 5. 错误与空态

- 无快照：图标+“尚未加载有效配置快照”，副文案说明只读页不生成快照，提供“加载快照”。
- 该时点未生成：显示 time_point 与原因，“Configure 时点尚无快照，请先完成宏解析或切换时点”，提供切换时点入口。
- 无对象：显示 snapshot_id/revision，“快照有效但对象列表为空”，保留原始 JSON 入口。
- 快照无效/JSON 损坏：错误横幅+错误码+可复制详情，保留上次有效快照并标注“显示的是上次有效快照”；提供重试。
- schema 不支持/缺必需字段：Unsupported 面板，列缺失字段，展示原始 JSON，禁用解释性表格。
- 进程/读取失败：横幅+重试；不得清空旧数据。
- 字段级缺失：不弹全局错误，行内显示 unknown 徽标与来源位置。

**null 规则（必须贯穿 5–9 节）**：`null` 可能是后端有效值（如显式未设置、继承为空、该时点无结果），**不得统一等于“未知”**。必须结合 `status`/`reason`：若 `status` 为有效值且 `reason` 说明其为显式空值，则显示“空值（后端有效）”并保留 null token；仅当字段缺失、`status` 缺失/unknown、`reason` 缺失或 evidence 缺失时显示“未知（后端未提供）”。UI 用不同徽标区分“空值”与“未知”，原始 JSON 始终原样显示 null。

## 6. 可访问性与中英翻译键

- 键盘：Tab 顺序工具栏→树→摘要→字段表→原始 JSON；树支持方向键展开/折叠，表格支持行列导航；Esc 关闭展开行。
- 屏幕阅读器：树节点播报名称+状态摘要+unknown 数；字段行播报字段名、requested/resolved、status、evidence、reason；状态变化用 aria-live=polite，错误用 assertive。
- 对比度≥4.5:1；unknown/空值/实验性不仅靠颜色，配文字与图标；焦点环可见；只读徽标可朗读。
- 翻译键（zh_CN/en_US 同键）：
  - `effective_config.title`、`.readonly_badge`、`.nav_label`
  - `effective_config.time_point.configure/run_begin/finalization`
  - `effective_config.filter.diff/unknown/experimental/unapplied`
  - `effective_config.state.uninitialized/loading/ready/empty/partial/unsupported/error`
  - `effective_config.empty.no_snapshot/time_point_not_generated/no_objects`
  - `effective_config.value.null_valid`（空值（后端有效））、`.unknown`（未知（后端未提供））
  - `effective_config.evidence.manager_accepted/kernel_applied/run_result`
  - `effective_config.source.location_unknown`、`effective_config.raw_json.copy_object/copy_snapshot`
  - `effective_config.error.retry/showing_last_valid`
  - `effective_config.a11y.tree_node/field_row/status_live/error_live`

## 7. 实现文件清单

- `frontend/effective_config/page.py`：页面装配、状态机、QSplitter。
- `frontend/effective_config/toolbar.py`：时点、搜索、筛选、刷新。
- `frontend/effective_config/object_tree.py`：树模型与状态摘要。
- `frontend/effective_config/field_table.py`：字段表、展开证据块、排序。
- `frontend/effective_config/summary_card.py`：对象摘要、来源链折叠。
- `frontend/effective_config/raw_json_view.py`：只读 JSON、复制。
- `frontend/effective_config/models.py`：快照/对象/字段/来源/证据只读数据类。
- `frontend/effective_config/loader.py`：QProcess 读取、超时、取消、整份替换。
- `frontend/effective_config/status.py`：状态与 null/unknown/空值判定（唯一判定入口）。
- `frontend/effective_config/i18n/zh_CN.json`、`en_US.json`。
- `frontend/effective_config/tests/test_status.py`、`test_loader.py`、`test_page_smoke.py`。

## 8. Qt smoke 验收

1. 启动应用，导航“有效配置”，标题与“只读”徽标可见，无编辑/应用/运行按钮。
2. 未加载时显示 Uninitialized 空态；点击加载进入 Loading，完成后 Ready。
3. 加载中重复点击被禁用；旧快照保留并显示“刷新中”。
4. 选择对象→摘要卡更新；展开字段→证据块显示 manager_accepted/kernel_applied/run_result 独立。
5. 筛选“仅 unknown”只影响显示；搜索 canonical path 命中正确对象。
6. 构造 `resolved:null,status:"valid",reason:"explicit_empty"`：显示“空值（后端有效）”，原始 JSON 为 null；构造字段缺失：显示“未知（后端未提供）”；两者徽标不同。
7. 损坏 JSON：Error 横幅，保留上次快照并标注；重试可恢复。
8. schema 不支持：Unsupported 面板，表格禁用，原始 JSON 可看。
9. 键盘遍历树/表；aria-live 播报状态；切换 en_US 键完整无缺失。
10. 关闭页面，QProcess 终止且无悬挂进程。

## 9. 后端 JSON 最小契约

```json
{
  "schema_version": "1",
  "snapshot_id": "string",
  "revision": "string",
  "created_at": "ISO8601",
  "time_point": "configure|run_begin|finalization",
  "run_result": {"status": "string|null", "reason": "string|null"},
  "objects": [{
    "stable_id": "string",
    "canonical_path": "string",
    "module": "string",
    "name": "string",
    "source_chain": [{"kind": "string", "file": "string|null", "line": "int|null", "raw_value": "string|null"}],
    "fields": [{
      "field": "string",
      "requested": "any",
      "resolved": "any",
      "application_status": "string|null",
      "applied_revision": "string|null",
      "evidence_level": "string|null",
      "reason": "string|null",
      "status": "string|null",
      "manager_accepted": "bool|null",
      "kernel_applied": "bool|null",
      "experimental": {"schema": "string|null", "runtime": "supported|unsupported|unknown|null"}
    }]
  }]
}
```

契约要点：`null` 为合法传输值；是否“有效空值”由 `status`+`reason` 共同决定，前端不自行把 null 映射为 unknown。缺失键与显式 null 需区分：缺失→unknown；显式 null 且有有效 status/reason→空值。`application_status`、`applied_revision`、`manager_accepted`、`kernel_applied`、`run_result` 均独立，不得互相推导。前端只消费本契约，不补字段、不重算。

## Astra 采纳范围与纠偏（2026-10-29）

这是两次真实 DeepSeek API 响应的设计建议，第二次完成输出；不是已实现契约。采纳对象树/字段详情、只读、失败保留旧快照但标 stale、来源可查、unknown 不冒充成功。以下建议不采纳：

- 虚构 frontend/ 目录、独立翻译 JSON、en_US 和 web aria-live；使用本仓 gui/g4usim_gui 的 core/widgets、集中 i18n 的 en/zh_CN、Qt 可访问性属性。
- 不采用其自创 schema_version/objects/status=valid 示例作为接口；以 EffectiveConfig C++ 输出的 schema/stage/revision/fields 为准，revision 是数字。
- 显式 null 是 JSON 值，照实显示 null；值缺失、application_status=unknown、evidence 缺失是独立维度。不能因 reason 缺失把已知值改成未知，也不能因 manager_accepted 把内核标为 applied。
- 初版只加载后端导出的文件，不虚设多阶段/实时运行连接，不启动额外 QProcess；页面明确 manager_state_subset，不能称 2C 完成。
