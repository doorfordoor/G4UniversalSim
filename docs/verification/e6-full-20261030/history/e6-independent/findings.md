# E6 前端代理对迁移底层的独立审查（进行中）

## 已复现，应修复

1. **P1 项目迁移接受错误 JSON 类型并静默改变运行/复制语义。** `core/project.py:106-109` 把 `threads=2.75` 降为 `2`；`project.py:140-162` 的 `_check_supported_fields` 只核对 dict/list，标量没有类型和等值门禁。经 `geometry_document_from_dict` 后，`geometryEditor.source_copy_mode="false"` 和 `is_dirty="false"` 均成为布尔 true，`source_errors="ERR"` 变 `['E','R','R']`，`source_path=null` 变字符串`"None"`。其中 source-copy 可以在没有显式布尔勾选的情况下被打开，违反E6的类型不降级/复制必须显式选择约束。`plan_project_migration`沿此路径写出规范文件，并称已检查支持的结构。应在兼容归一化后、构造前按项目/模型字段类型拒绝这类值；若历史某类型需兼容，必须逐项明确且不能用`bool("false")`。不能只在新副本writer修，因为正常load也会进入。

2. **P2 冗余 preview 冲突检测把不同 JSON 类型当相同。** `core/project_migration.py:40` 用Python`!=`；`volumes=[{"name":"V","sensitive":false}]`，`preview.volumes=[{"name":"V","sensitive":0}]` 被当作相同并静默丢弃preview差异。要求相同表示才允许冗余时，应类型敏感地比较（JSON bool与number不得等价）。与第1项类型校验联动可关闭。

可复现脚本 `out/verification/e6-independent/review_migration.py`；实际输出 `review.json`。脚本只记录观察，不修改产品文件。

## 真实资源语法对照

已核对 `IniReader::ParseBytes`、`GeometryConfig::LoadBytes/ResolveNextTo`、`GDMLTemplate::ResolveGdmlPath` 与模板路径规则。最初看到Python宽Unicode strip风险；执行前迁移写者已改为ASCII空白。真实保留2C后端对含前导NBSP的合法`copies_file`源文件及迁移文件均初始化退出0，说明该风险当前测试未复现；不列缺陷。`source.log`、`migrated.log`与对应INI/CSV已留存。本实验是相同既有2C executable的迁移资源解析对照，不是候选E6全量或物理验证。

发布算法采用独占link而不是replace，发布前再次源哈希、link失败清临时文件、清理失败不掩盖原异常的路径在源码中成立；发布后cleanup_warning由前端接入显示并新增故障注入smoke，已退出0。未发现另一个确定的发布缺陷；不把两次源哈希外推为文件系统永久不变或设备持久化证明。

审查输入及保留2C exe的sha256见同目录`identities.json`。审查中的其他模块会并发修订，报告指向上述观察时点，不阻塞整阶段；修复后应用独立反例回归。
