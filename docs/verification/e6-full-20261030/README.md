# E6 自动验收交付报告：实窗待验

验收候选 `a779634483d1f077357433c532ccb0d9e3dc5517` 已由root正常冻结/push；本次只读确认HEAD一致且tracked clean。本文记录该提交已取得的自动终态；字节归档状态由archive-manifest及archive-complete单独核对。automatic_acceptance_passed，stage_acceptance_pending_visible，stage_complete=false。

实际冻结manifest已读取：**134项=static21/gui37/backend56/integration20**。Windows134个用例全部通过；12份CI各profile实际名单也与该manifest完全一致，详见[实际名单核验](additional/29-e6-release-report-draft/manifest-name-audit.json)。计数来自实际集合，未硬编码133/134；5bf的133仅保留历史。源码指纹ab79c6c2227518bd7f38d5109998ed0998d8fd53ad500cfbe714d544eb19a474；测试指纹e9b4f852e36dca85971d40da2c63ed6fd184055358ca965116babba6b16fafd4。C++未因本次Qt/Python修复改变，exe身份仍由正式报告/build收据核对。

正式证据入口：[Windows终态报告](windows/final-1/report.json)、[Windows strict+2C门禁](additional-files/30-e6-release-windows-gate.log)、[同v3的2C基线](baseline/1/report.json)、[真实CI说明](ci/README.md)、[CI汇总](ci/ci-evidence.json)、[冻结名单](ci/frozen-case-manifest.json)、[Linux dirty边界](ci/git-dirty-audit.json)、[384日志SHA复核](ci/raw-log-hash-audit.json)。

历史保留：[首轮Windows失败](history/e6-full-windows/20261030-002736-c9ff9815/report.json)、[首轮CI失败](history/cb837e6-ci/ci-evidence.json)、[第二轮Windows通过控制](history/windows-round-1-e6-final-windows/20261030-015707-a71633dc/report.json)、[第二轮CI失败](history/ci-round-1-e6-ci-final/ci-evidence.json)。[DeepSeek响应](design/deepseek-response.json)与[采纳纠偏收据](design/deepseek-outbox-receipt.md)仅作设计参与证据。

## 实现

- 统一schema394描述符（supported60/experimental319/deprecated13/unsupported2），相较完整2C357新增37：field8、field.<name>9、biasing1、legacy biasing.xs8、动态process规则10、主INI版本1。五类field/biasing均external_only，legacy8项deprecated、其余28项experimental；不表示394项GUI可编辑或物理已验证。生成器同步C++/Python/覆盖/矩阵，保留dormant、process大小写、别名/默认/精度/模块策略与运行期绑定校验。
- 主INI唯一格式标记[general]schema_version=1；缺失legacy1、显式只接受精确1、非法/未来在候选发布前拒绝；重复仍lastwins+warning。新普通GUI writer显式输出1；主INI与独立geometry加载边界分离。EffectiveConfig格式来源字段不伪作内核应用收据。
- 几何保持v2、项目规范v6；明确旧输入/别名/preview已知迁移规则。未知/歧义、冲突、重复JSON key、非有限值及未来版本明确拒绝。几何诊断和GUI源诊断用稳定完整身份去重，刷新/重载不积累；现有simple/layered/hierarchical writer往返保持。
- 迁移计划展示版本/改动/验证范围；源只读，以同目录临时写+fsync+原子独占发布新副本，发布前复核源SHA，目标已存在或链接别名不覆盖。主INI迁移限定同目录，几何引用重定位原目标。GUI先解析和实际控件范围预检再发布，另存成功后才切换路径。
- 真实运行包快照采用专用严格适配；普通项目入口保持闭合。标准包duplicate只复制完整受支持输入、重定位已确认路径、清空logs/output；Duplicate&Run读取副本当前main线程/seed/name，不继承其他项目CLI。

## 修复与不同写者关闭

第一轮回归确认recent/snapshot模态严重级别回归，已恢复原warning行为；普通项目错误仍critical。项目构造前校验真实JSON类型，避免字符串bool、fraction→int截断、字符串拆列表、null路径变字符串；preview冲突比较区分false与0。显式editor不再因单个空/非法字段重建整个实验，单position别名兼容、双别名冲突拒绝。

GUI真实QSpinBox整数上下界在_set_project前统一预检，向导先构造相同候选再应用；未投影字段不加多余范围。原始失败脚本/18payload、修后边界及合法历史正例保留。真实writer snapshot→专用加载→普通保存/重载→再生成→真实2事件链确认材料/几何/source和输出摘要；旧包metadata路径成对识别、缺失/逃逸等负例保留。duplicate31底层负例及独立6组、CLI原8payload修前/后保留，尾NBSP按INI ASCII空白规则完整传入最终命令。

第二轮Linux none_dealloc已由最小Qt缺失UserRole读取及产品Plot/Scan空态路径实证。共享combo_data按Qt模型root/column/index读取role map，保留None、0、False、空串、Unicode及已支持值；仅接有明确缺角色/无选择路径。原projection全部assert AST保留，未强制退出/吞退出码。候选原393assert连续5次、落地版连续3次自然退出0；新正式helper29assert和真实Plot/Scan/refresh空态由不同写者复核。复杂嵌套QVariant或任意自定义模型不外推为已完整修复。证据e6-linux-finalize、e6-combo-role-map-review、e6-qt-landed-independent。

## 三轮证据与当前结果

|轮次|身份与终态事实|用途|
|---|---|---|
|首轮|cb837e680e08a66dd47e62a9ee7e25fa125026c3；Windows126pass/1fail/0skip，模态severity回归；CI失败|原报告/log/反例不改写，作为失败历史|
|第二轮|5bf479d85ba7c12e0f71984d31b8335c47c5a8c3；Windows133/133、42786v3、strict及2C同口径baseline40628门禁通过；CI两Geant4 Linux+M0 Ubuntu GUI393assert后exit-6，M0 Windows通过，实际8/12reports|通过Windows控制与失败CI历史，不冒充新候选|
|第三轮|a779634483d1f077357433c532ccb0d9e3dc5517；actual manifest134；Windows root e6-release-windows、session51778由root管理；实际CI Linux40931653660/M040931654093采集至e6-ci-release|Windows134pass/0fail/0skip、42815v3，strict+2C baseline40628逐例/总数通过；CI12/12strict、4官方ZIP身份、384条矩阵用例记录全pass、91884v3，384份raw用例日志SHA一致|

新freeze前预检9pass/0fail/0skip、657v3，原报告旧HEAD+dirty=true，故仅作为本次修复专项。此前诊断/单项绿色不能代替第三轮正式全量。全链正反例映射另见[契约映射](additional/24-e6-delivery-readonly-review/README.md)；该报告内旧冻结计数依其原时间上下文，不追改历史。

上述最终自动门禁均已取得并核对。Linux11.3.2/11.4.3分别42779/42191条v3断言，M0 Ubuntu/Windows分别3459/3455，合计91884；384是矩阵执行记录，不是384种独立用例。报告/退出码为准，stdout ok或assert marker不能掩盖非零退出。

Linux8份报告git_dirty=true、M0四份false，原事实保留。workflow在checkout内建立未忽略的.micromamba、.g4env及bin/micromamba，有实际job日志支持；build_linux/out已忽略，不能归因给它们。8份报告untracked_source_files=[]、tracked_source_gate=pass且双指纹匹配，只能确认覆盖范围内内容身份；未归档完整porcelain/退出码或tracked diff，完整dirty路径以及指纹范围外/仅行尾差异仍unknown。不得称Linux测试时整个checkout clean，也不得断言仅环境生成物。最终CI README和git-dirty-audit.json明确此边界。

## 兼容限制

1. “不丢数据”限明确已知转换或明确拒绝，不过滤任意未知字段、不猜物理含义。几何迁移结构检查不替代后端Inspect/build/run；项目保留原错误/blocker，不自动开启source-copy绕过。已有旧文件正常读取，未强制只读。
2. 普通writer仅原编辑子集；J2高级实体/源、assembly、材料温压不开放。主INI迁移保留源注释/未知字段/重复，普通writer不承诺任意文件保真。GUI表示范围限制不改变后端INI/CLI范围；旧runSettings.threads=0不再静默回退，已明确兼容差异。
3. 主INI跨目录副本拒绝；geometry绝对化资源指向不打包外部文件。不支持独占链接的文件系统明确失败；发布完成后临时清理失败只warning，不错误宣称整个发布失败。
4. 专用snapshot恢复当前包内材料/几何与生成时编辑参数；材料摘要只有组分数量，不能恢复禁用行/未输出草稿。不能反导手改main/macro、不能称runtime EffectiveConfig或历史字节一致，也不继承历史成功。无任何envelope的legacyplain按普通兼容规则并提示资源未验证；partial envelope不得退回。单个矛盾/缺资源/逃逸symlink/未知新metadata拒绝。
5. duplicate支持标准闭合输入，额外/外部资源及非标准宏拒绝；不读旧包、无旧结果继承。任意可移植bundle及任意实验反向恢复属于K1，独立物理验证属于Q2。

## DeepSeek实际参与

一次真实deepseek-flash设计咨询：2026-10-29 15:54:17UTC，响应ID1b764c5f-861b-4f28-a176-48c807fca2ac，prompt477/completion1211/total1688。采纳分开版本、显式新副本、保存成功后切路径、诊断稳定身份和验证边界；纠偏旧项目一律只读、缺模式无条件阻断等建议。实际响应out/collab/e6-deepseek-design.json与docs/collab/outbox/20261029-deepseek-e6-design.md可追踪。仅归档响应和outbox，不含密钥/请求脚本；收到AI建议不能算独立物理或视觉验收。

## 下一步和阶段状态

- 自动验收已通过；最终证据绑定到a779634的冻结清单。归档由root按审核后的plan执行；目标docs/verification/e6-full-20261030，复制结果需独立核对。
- 实窗仍pending_user_unlock_and_real_window_check；新候选[准备验证](additional/28-e6-visible-acceptance-a779634/preparation-verification.json)核对13源码身份、58资源hash且0不匹配；[当前检查点](additional/28-e6-visible-acceptance-a779634/checkpoint.json)与[实窗计划](additional/28-e6-visible-acceptance-a779634/plan.md)明确prepared_not_launched、尚未获解锁且未启动UI/backend。旧5bf准备目录仅作历史保留。锁屏是外部验收待办，不是产品缺陷；offscreen/WSL/布局参考图不能替代真实窗口观察。待验迁移预览/取消/冲突、snapshot当前输入及提示、Duplicate&Run最终参数。
- 自动终态已具备，记录automatic_acceptance_passed与stage_acceptance_pending_visible，stage_complete=false。归档执行后应由archive-complete.json和archive-verification.json证明字节复制、SHA核对及归档本地门禁；本稿不预写尚未执行的归档成功，这些文件也不代表实窗通过。
- 最终归档保留三轮身份和原反例/关闭、DeepSeek响应/收据及build身份JSON；排除二进制、凭据、ZIP容器、旧CI selfcheck和媒体。以后实窗单独补录实际操作与观察证据，不改本轮原报告；实窗完成前不称E6 complete、不合主线，ROADMAP保持进行中。

## 原件路径的纯文本保存

[原始报告发布稿](additional-files/31-e6-final-README.md.txt)与[迁移过程报告草案](additional/29-e6-release-report-draft/README.md.txt)按原字节保存为纯文本，manifest保留原source名称、original_archive_path、原因和SHA；其中历史/原发布位置链接只作为文本，不是当前活链接。本页是可携带活索引，其他Markdown未广泛改名。
