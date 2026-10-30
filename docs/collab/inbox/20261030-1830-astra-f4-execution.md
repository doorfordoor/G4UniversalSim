# F4 结构化诊断与定位：完整阶段执行契约

基线 `045625363fc1385df8d0a727ccdab6978bdd71bb`，分支 `roadmap/F4-validation-navigation`，沿用 effective-config 工作区；原 D 盘 DSH 检出保持独立。用户已启动完整F4，授权连续实现、审查和验收。本文先登记提案和验收，不代表实现已完成。

## 范围与边界

1. 新增无Qt的诊断结构，向K1/L1提供可序列化版本化记录：稳定code/identity、severity、消息模板与参数、保留原文、生产来源、真实file/line/section/key，以及editor/entity/field目标和不可定位原因。身份用规范结构计算，不靠翻译、显示行序或分隔符拼接；severity与不同实体/字段/来源不能错误合并。报告修订与诊断身份分开。
2. 在当前配置校验、已支持的材料/几何/源/物理/计分/运行字段生产诊断时附位置；源schema/兼容/round-trip错误保留，不从格式化或翻译后的文字猜字段。已有无法定位的外部backend/raw错误明确保留原文及不可定位原因。源文件位置只在来源证据足够时展示/跳转，不伪造坐标。
3. 配置页提供紧凑问题列表及明确的定位/查看来源动作，支持鼠标和键盘；保留原始报告与现有必要文本属性兼容。定位按编辑器注册映射切页/嵌套标签/选行/滚动并给予主题一致、非仅颜色的短暂提示；不更改配置或自动修复，不扩GUI可编辑白名单。
4. 诊断绑定产生时的项目/编辑快照。变更、重载、新项目、已删/改名/歧义对象、陈旧异步结果不能跳到错误字段；不把显示行号当对象身份。语言/主题切换不改变诊断身份和业务数据。不可编辑/不可达/不确定目标明确说明，不将切到父页冒充成功定位。
5. 来源查看只读，保留原始路径/行号/原文；若当前文件与诊断基础不同，明确过期，不把新内容的同一行冒充原错误。允许显示明确标注的已记录文本快照，不把事后读取声称为历史读入。无来源字段的raw错误只显示原文，不能强行解析成结构化承诺。
6. 保持ValidationReport.errors/warnings/info、can_run及to_text的现有意义和顺序；增加结构化接口与运行包诊断JSON，不破坏旧validation_report.txt。保留用户真实错误与Open/Recent等既有严重度；F4不修改物理参数、后端支持等级或运行结果判据。

## 文件清单与所有权

- 诊断核心写者：新 `gui/g4usim_gui/core/diagnostics.py`、`validators/config_validator.py`、`editors/source_physics_scoring_model.py` 及相应无Qt测试；负责类型/兼容桥接/生产API。
- 导航与控件写者：`widgets/config_builder_page.py`、`widgets/config/details.py`、新问题列表/导航模块与专属GUI smoke；按核心稳定API接线，不修改核心、集中i18n/theme或window文件。
- 材料/几何写者：`editors/material_editor_model.py`、`editors/geometry_editor_model.py`、`parsers/materials_parser.py`、`parsers/geometry_parser.py` 及专属模型/后端对齐回归；保留E6源身份与源错误生命周期。
- 主负责人：`main_window.py`、`window/*`、`core/i18n.py`、`core/theme.py`、`writers/validation_report_writer.py`、必要运行包结构化报告连接、其他入口适配、统一测试登记、文档与集成；跨所有权改动先协调。
- DeepSeek负责前端信息架构/交互设计咨询，主负责人裁决真实接口与科学边界。子代理实现后交叉审查，写者不能单独批准自己的实现。

代理当前只读勘察，具体API/目标字段表在发现报告汇总后补充；任何缩减需明确理由与后续归属，不能通过把本可定位的普通字段全标不可定位来关闭阶段。

## 提交节点与验收

1. 无Qt协议/生产来源/旧接口与结构化导出：测试身份碰撞、语言无关、重复source错误稳定、真实file/line及旧顺序/严重度不变；负例包含未知/损坏/缺目标、非有限参数和不可序列化载荷。
2. GUI定位与入口接通：当前可编辑域有字段级定位；动态行、层、布尔工具和只读源有相符粒度；跨页/滚动/键盘/主题/语言、重排/删除/改名/重载/新项目/陈旧结果均有正反例。定位前后完整配置相等，原error不能被跳转清除。
3. 真实生成/后端/报告：原源文件与已生成输出不因导航修改；运行包文本报告和结构化诊断一致；实际后端可定位与raw不可定位各验证，保持旧拒绝与退出语义。代码改变范围决定是否重建，但冻结矩阵覆盖Windows和真实Linux Geant4双版本、M0双平台；保留143项F1同v3逐例/总数基线，不删断言或容忍skip。
4. 主负责人真实窗口观察与不同写者证据审计；更新STATUS/ROADMAP/CHANGELOG/支持矩阵/GUI中文文档/Agent历史和协作简报；原F1档案不改写。实现提交与关闭提交分开，正常快进集成codex。任何实际未完成验收保持pending，不以控件构造或截图路径代替观察。

本阶段不包含F5撤销/自动保存、J1自由布局、J2高级参数编辑、K1完整实验包或L1自动Agent，亦不新增物理验证结论。

## 辅助入口的生产边界补充

主负责人还负责 `core/runner.py`/新project诊断模块、`core/wizard.py`、`core/scan.py`、`core/scenario_shielding.py` 与对应Project/Run/向导/扫描/场景页。向导和场景在原规则生产处保留field/code，不靠返回字符串识别字段；`scenarios/shielding_coating/scenario_model.py` 可增加独立于GUI的结构化问题记录接口，旧 `problems()` 保持原文/顺序和规则，render/generate/物理参数完全不变。扫描基础配置错误保留原目标及扫描点上下文，不将其误指扫描值输入；没有当前编辑快照证据时明确不可定位。后端Inspect失败当前仅有stderr，作为raw未定位诊断保留，不为F4改写全部C++异常架构。专项包含旧字符串接口等价、当前表单定位和运行/生成拒绝不变。

## F4 验收期间的依赖修复提案（2026-10-30）

确定为缺陷：Linux CPython3.11的PySide6/shiboken6 6.12.0普通void调用与缺失属性读取可耗减None引用，旧CI出现none_dealloc/-6；仅绕过一处读取不足。文件清单：gui/requirements.txt、gui/smoke_tests/smoke_qt_binding_lifetime.py、scripts/run_m0_tests.py、.github/workflows/linux-geant4.yml及对应维护文档。采用已隔离验证的6.11.1至6.11补丁线，移除会与wheel混载Qt的全局conda库路径，保留数据/插件设置。验收：旧103/45/257断言均保留并正常退出，新增绑定回归拒绝已知坏版本；最终152项Windows、Linux双Geant4及双OS M0按新SHA完整验收，辅助程序实际运行与实窗13态另核对。旧失败轮不改写。QA host自身Close遍历销毁对象的异常只修out辅助程序，不据此修改产品。
