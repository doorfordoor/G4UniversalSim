# DeepSeek E6 前端设计咨询与 Astra 集成取舍

基线：`c6bf8ad2c4d58b5e66392b1a029859c26b6dc17a`，当前隔离工作区。涉及文件：拟修改 `gui/g4usim_gui/window/project.py`、`widgets/config/geometry.py`，拟新增迁移预览对话框及 smoke；core 迁移接口由另一写者负责。结论：设计咨询真实完成，产品代码尚未修改，等待主任务实施契约。

## 实际调用与信息边界

- 2026-10-29 15:54:17 UTC，`https://api.deepseek.com/chat/completions`，请求/返回模型 `deepseek-flash`。
- 响应 ID：`1b764c5f-861b-4f28-a176-48c807fca2ac`；状态 `received`；prompt 477、completion 1211、total 1688 tokens。
- 本次只有一次咨询。请求只含当前 Qt/版本/保存/几何边界事实，无密钥、无项目私有输入；密钥只用于 HTTPS Authorization，不写入日志/结果。未运行旧的一次性实现脚本。
- 完整实际响应在 `out/collab/e6-deepseek-design.json`；安全审查后的本轮脚本为 `out/collab/e6-design-request.py`。API 成功只说明收到建议，不是功能或视觉验收。

## 采纳

1. 项目 JSON、主 INI、几何文档版本分别展示；缺版本显示 legacy，不把几何 v2 混为主 INI 版本，不把项目 version=6 混为几何文档版本。
2. 迁移前提供摘要、精确改动表、warning/blocker、输出文本预览；展示由 core 提供的结果，页面不重写迁移规则。未来未知版本、无法无损解释的字段拒绝或明确 blocker，不自动搬进 metadata。
3. “写入新副本…”为显式动作；取消/失败保留当前对象、编辑状态、路径、陈旧标记。成功只报告副本落盘，提供显式“打开新副本”；再次加载成功后才能切换。
4. 修正现有 Save As 的时序：成功保存后再切换 `project_file`，失败保持旧路径。普通项目打开也统一“先解析成功再发布”。
5. 诊断身份基于来源类型、规范路径、行/字段位置、类型码与严重级别，展示层翻译不能成为唯一去重键。同文案不同位置不得合并。
6. 回归覆盖旧版推导、未来版本/未知字段、取消/失败/冲突保留、原件字节不变、当前 editable 子集往返及中文/英文切换；J2 白名单保持。

## 明确纠偏

- 不采纳“所有旧版项目一律只读、标未迁移且限制编辑”。已有 v1–v6 是兼容读取承诺；可安全迁移的旧项目仍应正常打开，迁移信息必须解释，不能凭旧版本号制造 blocker。
- 不采纳“缺 runInputMode 且无路径则无法推导并阻断”：现行契约明确推导为 generated；有 config/macro 路径推导 external。
- 不采纳“几何 round-trip blocker 必须阻止项目加载”：项目可保留源错误和不可编辑状态，阻断的是相关生成/写回路径，不应取消整个项目的诊断查看能力。source-copy 必须由用户显式选择，不能为迁移自动开启。
- 不采纳默认二次确认流程。用户点击“写入新副本…”并选择新路径已是明确动作；冲突应拒绝，不能增加无必要确认。对话框采用简单审阅式流程，是否模态由现有 Qt 生命周期确定，无需非模态额外状态机。
- `os.replace` 会覆盖既有目标，不能独自满足“副本拒覆盖”。core 必须保证 exclusive/no-clobber 发布并拒绝原件/既有文件（含硬链接）；页面不靠 QFileDialog 存在性检查宣称原子拒覆盖。
- 迁移预览不能称作 backend accepted、模拟执行成功或物理验证；原始诊断 token 保持原样。

## 拟议界面与最低接口

窗口统一 helper 接管普通/最近/历史项目加载，用 core 的兼容读取报告解释旧字段推导；不能在 helper 中重复解析 JSON。工具/项目菜单提供“配置迁移副本…”入口，支持项目 JSON、主 INI、几何 INI 明确类别，选择后使用同一审阅对话框。core 最低返回：kind/source_path/source_version/target_version、changes(path,before,after,reason)、warnings/blockers、output_text、source_identity；写入新副本接受 plan 与目标并验证源未变化。

前端独占：`window/project.py`、新 `widgets/migration_dialog.py`、本轮 smoke；`core/i18n.py` 需主任务确认单写者。几何迁移入口若复用同一对话框，可在 Geometry 配置旁增加按钮；不改变现有 editor/writer 支持集合。若实施契约只采用全局入口，几何页仅显示可读诊断，不另增平行规则。

下一步：主任务确定 core API 与文件归属后实施；此记录不代表 E6 已完成。
