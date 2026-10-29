# 2C 配置阶段基础链路：复核与交接

- 分支：`roadmap/2c-effective-config`；基线 `5465dbd`。隔离工作区：`C:\Users\123\.codex\worktrees\effective-config\G4UniversalSim`。
- 结论：数据模型、配置阶段导出与只读 GUI 已验收；**完整 2C 仍在进行中**。Astra 统筹/集成与首席审查，Sol 完成实现和交叉复核，DeepSeek 通过 API 提交前端设计，采纳范围见本目录对应开工回信和 outbox 设计稿。
- 涉及文件：Config/EffectiveConfig、Core/SimulationManager、main、GUI effective_config 读取器/页面/导航/i18n、专项测试、统一 runner 与文档。未修改物理模型、几何、材料、scorer 或原 DSH 代码。

## 本轮结论（行号对应隔离工作区）

| 证据 | 判定 | 处理 |
| --- | --- | --- |
| `main.cc:602` | 确定为缺陷（本轮已修复） | 候选导出曾可能截断输入/既有文件；现独占创建，真实后端测试覆盖 INI、macro、既有导出和硬链接别名，全部拒绝且字节保持。 |
| `src/Core/SimulationManager.cc:1374` | 确定为缺陷（本轮已修复） | 命名/相空间源曾可能输出旧单源缓存；现省略不适用字段，非 mono 不输出 mono energy。真实源模式反例通过。 |
| `src/Config/EffectiveConfig.cc:100` | 确定为缺陷（本轮已修复） | 请求未知曾借 JSON null 占位；现 requested/resolved 各自可缺失，显式 null 保持类型和值。模型与真实导出→GUI parser 回归通过。 |
| `gui/g4usim_gui/widgets/effective_config_page.py:117`、`:128` | 确定为缺陷（本轮已修复） | 搜索同时接受原始 path 与解码对象名，语言切换保留 canonical path 选择与详情；专项回归通过。 |
| `gui/g4usim_gui/widgets/effective_config_page.py:45`、`:68` | 确定为缺陷（本轮已修复） | 截图暴露顶部说明区占高、树过窄；主体 stretch 与 splitter/表头宽度已修正，真实 JSON 的浅色/深色/小窗口 offscreen 图已查看。 |
| `src/Core/SimulationManager.cc:1313`、`gui/g4usim_gui/core/effective_config.py:35` | 无问题（限当前验收范围）；完整覆盖需实验 | 当前只有 configure + Manager 子集，所有应用状态均 not_applied，未把此导出当内核真值；全模块与运行期证据仍须逐消费者实现/验证。 |

以上缺陷来自本轮未交付候选，不归咎于旧提交。旧“F6 没有 sequence”“11.4 矩阵未开始”结论已撤回；不把旧矩阵或旧审计引申为新代码已通过 CI 或全仓库无缺陷。

## 验收与剩余工作

最终 36 backend + 53 static/gui/integration = 89 PASS / 0 FAIL / 0 SKIP，117149 条断言；独立 C++ 模型另 24 条。两个报告指纹一致、用例集合无重叠/无遗漏、日志按落盘字节复核。报告见 [本轮证据](../../verification/2c-configured-20261029/README.md)。初轮 GDML 预期/符号链接权限两项环境失败保留，最终使用已有参数复测，不改权限或放宽判据。

下一步先按 [消费者清单与 source 约束](../../EffectiveConfig.md) 做逐源来源/适用字段/解析字节哈希与事务删除语义，再接运行开始和最终化证据；其后推进其他模块、off/auto/on 和差异视图。所有阶段状态继续只在 ROADMAP；不把本轮完成写成 2C 整阶段完成。

给 DSH/DeepSeek：本轮原 D 盘代码未改、未合并。请先读本隔离分支和证据；同一文件仍执行单写者规则。前端下一批重点是对象摘要、来源链与差异呈现，须等后端真实契约，不根据设计稿自造 schema 或物理语义。Astra 继续负责集成，不需要用户逐片转发批准。
