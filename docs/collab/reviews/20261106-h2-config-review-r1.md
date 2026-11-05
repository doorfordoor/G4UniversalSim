# H2-3 首交付独审
2026-11-06。未通过，最小修复后复验。

原任务turn87 completed/idle。新增两个GUI用例独立运行2 pass/0 fail/0 skip，50实际断言，报告out/collab/h2-config-entry/independent/20261106-041016-95a69f75/report.json；严格证据门禁通过。此证据不等于全部输入有效或原生窗口验收。

独立反例（Python311，当前gui导入）：创建ScoringEditableModel(fluence=True)，设置volume_spectra.fluence={enabled:True,bins:1000001,min:'0 MeV',max:'1 MeV'}，validate_scoring_model返回errors=[]。将bins改为2.5仍errors=[]。源码model允许10000000并用int截断校验，writer却原样输出bins；UI SpinBox上限也是10000000。后端ScoringManager明确拒绝bins>1000000及非整数。因此正常编辑可生成明知后端拒绝的配置，违反原定入口验收标准。

最小修复：model/UI统一后端1..1000000；验证原始bins为整数（拒绝bool/非整数，不可用int截断放行），writer不改写无效输入。用1000000、1000001、2.5验证模型/UI/写出边界即可，不实际创建百万桶。保留已通过的例程，不扩通用工具。

证据措辞：parse_run_editor_ini此次仅允许新section并检查闭合键，其返回仅source/physics；目前smoke只断言二者存在，不证明从INI恢复scoring。项目JSON保存/加载已测通过，二者须分开写；若既有产品入口没有INI计分导入能力，不为此扩建导入框架，明确项目恢复边界。未修改过的当前main不得宣称已恢复成新计分模型。