# E6 迁移底层独立交叉复核

结论：原独立审查的 **P1/P2 均已修复并由原始反例关闭**。本轮不改产品代码或正式测试。修复者自测仅作定位输入，以下结论来自前端审查者重新执行。

## 确定缺陷已修

| 项目 | 代码证据 | 独立复核结果 |
| --- | --- | --- |
| P1 错误 JSON 类型静默转换 | `gui/g4usim_gui/core/project.py:81` 在构造前调用类型校验；`core/project_migration.py:34`、`:46` 逐层核对 dataclass、union、数组、字典与真实标量类型；`editors/geometry_editor_model.py:213`、`:220` 同样先归一化再校验 | 原 `source_copy_mode="false"`/`is_dirty="false"`、`threads=2.75`、`source_errors="ERR"`、`source_path=null` 四类 payload 全部拒绝，错误含字段路径。无字符串 truthiness 开启 source-copy，无浮点截断或 null 路径字符串化 |
| P2 冗余 preview 比较忽略 JSON 类型 | `gui/g4usim_gui/core/project_migration.py:23` 的 `same_json_value` 首先比较实际类型，再递归；`:95` 使用该比较拒绝冲突 preview | 原 `volumes.sensitive=false` 与 `preview.volumes.sensitive=0` 冲突拒绝，不能被 Python `False == 0` 掩盖 |

实际运行未经修改的 `out/verification/e6-independent/review_migration.py`，修复前观察先保留为 `review-before-types-fix.json`，修复后观察为 `review.json`；追加复核脚本 `verify_types_fix.py` 对五个 payload 的输入逐项比较相同，并断言修复前接受、修复后拒绝。复现脚本未改变原 fixtures。

## 无问题：限定兼容正例与资源对照

- 旧项目版本缺省及 1–6，各配几何旧字符串版本 `"1"`/`"2"`，共14组：平面 `threads="2"` 归一为整数2、`seed=null` 保持既有空字符串兼容语义、几何别名与旧 preview 行保留、false 不变 true、macro 路径推导 external；迁移副本及普通保存后重载与规范模型一致，原文件字节不变。
- 未提供 nested `runSettings.seed` 时仍为既有默认12345；flat `seed=null` 不应被测试误解为强制 nested seed=null。本次未修改此默认或优先级。
- 无 config/macro 路径时推导 generated；旧 `threads=" +2 "` 继续兼容。
- 实际执行 `gui/smoke_tests/smoke_project_io.py` 与 `scripts/test_config_migration.py`，均退出0；日志在独立证据目录。
- 已核对真实 `IniReader`、`GeometryConfig::LoadBytes/ResolveNextTo`、`GDMLTemplate` 路径语法。使用保留2C exe对含前导NBSP的合法 `copies_file` 源与迁移副本分别初始化，均退出0。当前ASCII空白修订未复现语义变化；本结论不代替候选E6全量矩阵。
- 独占link发布、两次源哈希与清理路径未发现新增确定缺陷。发布后临时link清理失败通过 `cleanup_warning` 保留成功；前端已接收并显示该警告，相关故障注入smoke通过。哈希检查是执行时证据，不保证之后永久不变或设备持久化。

完整结构化结果：`out/verification/e6-independent/types-fix-review.json`；含14组正例、五个原反例、实际专项日志位置及本轮源码/原始复现脚本 sha256。初轮观察身份在 `identities.json`，修复前后证据分开保留，不追改旧观察。

## 需实验：明确剩余边界

解锁后的实际Windows桌面操作仍待验。先前 Computer Use 捕获到锁屏，已停止输入；Qt windows平台渲染图只说明自身窗口排版，不冒充桌面点击成功。本轮未进行任何桌面操作。

本报告关闭的是两项工程可靠性缺陷及限定迁移兼容验证；候选E6冻结构建、全量回归、Linux矩阵与物理结论由主任务各自给出。接下来不再修改产品/正式测试，等待冻结或解锁安排。
