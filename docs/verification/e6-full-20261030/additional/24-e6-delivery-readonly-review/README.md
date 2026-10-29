# E6 最终交付只读审查素材（尚未阶段验收）

本次只读核对 ROADMAP、开工契约、配置兼容文档、支持矩阵、实际入口和已有证据；不重跑边界试验，不改 tracked 文件。观察 HEAD 为 `5bf479d85ba7c12e0f71984d31b8335c47c5a8c3`，tracked clean。迁移底层由本 agent 实现，本报告只作交付链路/证据映射；迁移实现的独立关闭依据引用其他写者报告，不能将本报告冒称不同写者自证。

**结论：E6 的实施链路和专项反例已有覆盖，5bf Windows自动全量通过，当前仍不得标阶段完成。** ROADMAP:254“进行中”与实际相符；Linux 第二轮失败、新候选冻结/全量/CI、可见窗口和最终归档仍待闭合。最终候选 SHA 尚未提供。5bf Windows 55580 已终态 exit0；本次已读取终态报告：133/133、42786 条 v3 断言、git_dirty=false，严格及 2C 同口径基线40628门禁通过。它只证明5bf该轮 Windows，下一Linux窄修候选必须重新绑定验收身份。

## 完整验收条件映射

|契约/条件|实际实现及现有证据|当前判定与剩余验收|
|---|---|---|
|五类 field/biasing 登记到生成 schema；不改上下文/模块语义|`schema/config_schema.json`；`scripts/generate_config_schema.py`；ConfigManager 注册表及 `FieldConfig.cc:250` 动态键；C++/Python/覆盖/矩阵生成产物。`test_field_biasing_schema`；61 项保留2C差分；独立4例见下。|实现与专项证据具备；须新冻结平台回归，不是新的场/偏置物理基准。|
|主 INI 版本缺失兼容、精确1、候选拒绝/来源、重复lastwins告警|`include/Config/MainConfigVersion.hh:12`；`src/Config/ConfigManager.cc:109,117`；EffectiveSimulation 格式来源；`test_main_config_version`、`test_main_ini_migration`。几何独立加载 `ConfigManager.cc:121`/`Templates/GeometryTemplate.cc:17` 避免主版本误入。|合法/非法/未来/Unicode/几何general独立反例已有；新普通 main writer 明确写1，仍等新冻结最终回归。|
|几何v2；缺省/1兼容；源顺序/注释/数值/单位/引用等价|`core/geometry_migration.py:78`；独立parser，已知metadata明确映射，未知/重复/忽略/未来/歧义拒绝，资源指向转原绝对目标。实际backend源/副本10类、网格/2事件及现有editor4链见 `e6-backend-second`、`e6-specialized`。|结构迁移具备；迁移预览不是全部后端语义验证。STL/GDML/副本表不变成可移植bundle；后端Inspect/build/run仍独立要求。|
|项目缺省/1–6/已知preview/别名；未来/unknown/重复/nonfinite拒绝|`core/project.py:170`、`project_migration.py:132`；构造前JSON实际类型校验；深度比较区分false/0；显式editor仅对象缺失才from_settings；双position别名冲突拒绝，单别名历史派生。`test_config_migration`、原5反例+14合法旧例、18投影独立原反例/修后结果保留。|“不丢数据”通过精确已知转换或明确拒绝达成，不承诺未知任意数据可加载；不全局过滤unknown、不猜语义。|
|副本不覆盖、源不变、源变动/链接/写失败/取消后状态不变|`config_migration.py:65`：同目录临时写+flush/fsync、发布前源SHA复核、os.link独占提交、临时清理失败返回warning；不删除target回滚。main副本限定同目录；正常project save仍原子替换。UI先验证后发布/另存成功后改path。|正式故障/硬链接/清理反例及GUI状态审查已有；不承诺任意Qt/系统异常通用事务回滚。不支持独占硬链接的文件系统明确失败。|
|已有编辑子集读取→迁移→保存/重载→writer→后端|simple/layered/hierarchical四类当前链、`test_config_migration_backend`；新main writer schema1；实际snapshot writer→专用load→普通save/reload→再生成→两次真实2事件（材料/几何/source及输出摘要对照）。`e6-snapshot-current-writer`。|链路专项证据具备；J2新实体/高级源/assembly/材料温压未开放。|
|诊断身份稳定、刷新/重载不累加|`GeometryConfigDiagnostic.hh:29–37` sort/equality同完整身份；`geometry_parser.py:112`来源/位置/code/severity，文案不作唯一身份；同文件重复与重载正式反例。`test_geometry_diagnostic_identity`、`test_config_migration`。|后端与GUI均有证据，不能只引用C++排序代表GUI去重闭合。|
|前端投影错误拒绝不污染，severity及保存/副本链兼容|`window/project.py:55,77,165,237,263`；向导候选先预检再原路径应用；独立88事实 `e6-frontend-guard-independent`，后续snapshot/duplicate回归。|按真实控件上/下界约束，不扩大到未投影整数。`runSettings.threads=0`旧隐式回退现明确拒绝已在兼容文档声明；不把GUI范围等同后端范围。|
|真实writer快照与复制包可重用但不继承成功证据|专用 `core/project_snapshot.py`、`project.py:177`；`history/run_package_actions.py`复用严格metadata；`read_generated_run_settings:68`。真实duplicate/2事件、31底层负例；独立6组及8CLI原payload修前/后。|仅已知标准包/闭合输入集合；具体限制见下。尾NBSP修后8例issues=0；CLI不继承current7/999/旧name；缺seed不追加、0保留。|
|DeepSeek实际咨询/采纳纠偏|outbox `20261029-deepseek-e6-design.md:7–10`；一次真实返回，响应ID `1b764c5f-861b-4f28-a176-48c807fca2ac`、deepseek-flash、1688tokens；`out/collab/e6-deepseek-design.json`。|实际参与已证明；采纳分版本/副本/路径时序/诊断身份，拒绝一律旧项目只读等建议。只归档响应+outbox；API返回不作功能/视觉验收。|
|干净Release、Windows全量及同v3逐项/总数、真实双版本Linux/M0|干净C++身份收据 `out/collab/e6-repair-build-identity.json`。当前133=21/36/56/20。预检16pass/2248assert但git_dirty=true，记录旧HEAD，属于修复专项而非冻结全量。|**待新冻结全量及同v3基线门禁**。5bf CI三路Linux GUI exit-6，8/12 reports，不可发布；5bf Windows133/133及2C门禁已通过，保留为历史控制；下一候选未绑定。|
|offscreen + Windows真实窗口|offscreen smoke/独立程序化检查存在；`e6-visible-acceptance-5bf479d/checkpoint.json` 明确prepared_not_launched、未获解锁、四项pending。|**实际窗口未验**。锁屏是外部验收缺口，不能记为产品缺陷；参考布局图、程序化UI、offscreen均不能补成实窗通过。|
|冻结身份、原失败保留、日志门禁/字节归档、文档终态|已有archive-e6.py和新候选参数绑定器，目标存在拒覆盖、源目标SHA核对、完成标记最后写；原失败不改写。|**尚未execute归档**；等最终SHA/Windows终态/12份CI通过/同口径基线，再绑定和执行；之后更新ROADMAP等，当前不应先标完成。|

## 字段数量与实际支持边界

当前直接读取schema计数394：supported60 / experimental319 / deprecated13 / unsupported2。完整2C冻结为357；本次新增37=五类field/biasing36+主版本1。五类分别8/9/1/8/10项，均migrated=true，section GUI元数据均external_only；其中legacy biasing.xs8为deprecated，另外28为experimental。supported总数只因主版本增加1，不意味着场/偏置晋升稳定支持。动态section模板计数是描述符数，不是任意用户实例总数；不能写“394字段均可GUI编辑/均已物理验证”。E2原353历史验收与2C357历史记录保留，不追改旧报告。

独立schema4例覆盖：dormant畸形grammar仍接受；显式auto激活则拒绝；规则disabled仍解析非法number并拒绝；mixed-case/process原大小写与derived-precedence保持接受。`e6-independent-schema-candidate/review.json`与baseline/candidate raw日志保留。该4例仅Configure对照，不能称输运/物理验证；新冻结二进制身份另见build收据。

## 副本、快照、复制的精确限制

- 普通主INI writer是当前支持参数子集生成器，不是任意原文件保真编辑器；迁移主INI才保留源注释/未知键/重复声明。主INI跨目录副本明确拒绝，geometry/main路径基准不能混为统一重写。
- 几何迁移保留源级表达，writer只覆盖原可编辑子集；未知/歧义/不可证明等价内容明确拒绝。路径绝对化保留目标，不复制外部资源；无法因此宣称K1任意搬迁。
- 普通项目loader仍闭合拒绝package envelope；迁移副本入口也不会自动吞snapshot。专用入口若完全无envelope键，走严格legacyplain并提示原资源未验证；出现任何envelope键则必须完整验证，不partial退回。
- 专用snapshot恢复**当前包内**材料/几何+生成时记录的编辑参数。materialDocument只有组分数量，不能恢复完整配方/禁用行草稿；包文件为活跃材料/几何输入。不会反向导入手改main/macro，不声称runtime EffectiveConfig或历史同字节还原。结果/运行路径清除，必须重新校验和生成。
- 仅识别同一旧标准包后缀的成对材料/几何遗留metadata路径，并给notes，绝不读旧包。单个矛盾、任意逃逸/符号链接出包、缺资源/新metadata拒绝。
- duplicate只支持标准完整输入，重定位三个确认INI键及snapshot对应指针；额外/外部资源、非标准宏拒绝。新logs/output为空，不复制旧结果。当前main的threads/seed/name由helper读取，前端候选可表示后发布；不是任意资源闭包或任意主INI反向导入。

## 两轮失败与后续门禁

1. cb837首轮Windows126pass/1fail/0skip（模态severity回归）及同轮CI失败均保留原件；`--allow-incomplete`只能诊断内部计数/哈希，不能发布失败报告。
2. 5bf第二轮CI run40926120374/40926120368：两个Geant4 Linux+M0 Ubuntu GUI在393assert后none_dealloc exit-6；M0 Windows通过。真实8/12份报告，后端/integration未全形成，不可用stdout的ok改成成功。Linux诊断out中的safe-getter对照退出0只属定位实验，必须窄修后新冻结+官方回归，不代替release。
3. 5bf Windows55580已终态133pass/0fail/0skip、42786v3；严格证据与2C逐例/总数门禁通过（baseline40628），日志 `out/collab/e6-final-windows-gate.log`。该轮保留历史/控制，不得换标签冒充下一SHA。
4. 下一最终门禁必须绑定新的40位SHA与不同Windows报告目录：全133、各case非零assert、无fail/skip、raw日志SHA、source/tests/exe身份、同v3的2C逐例及总数不下降；真实Linux11.3.2/11.4.3四profile和M0双平台，共4artifact/12report，所有正式门禁通过。
5. 真实Windows解锁后验迁移预览/独占冲突/取消、实际snapshot内容与提示、Duplicate&Run参数；记录程序化操作和截图可见观察的不同证据。执行环境缺口单列，不能静默跳过。
6. 最终再进行字节复制+SHA复核及归档-local report/log门禁、保留原失败，最后同步文档阶段终态。E6目前不满足该完整闭合条件。

## 归档参数材料

同目录 `archive-include-roots.json`继承已有20根，新增Linux原实验/独立复核、锁屏准备、此交付审查，共24个include-root；另显式保留关键原反例脚本、修前/修后日志和API边界收据。已有默认历史根不重复冒充final。

primary release head/windows仍为null，CI预留e6-ci-release。cb837首轮CI/Windows与5bf第二轮CI/Windows均标history；5bfWindows终态报告及门禁已存在；仍需按history角色校验归档。只准备参数不执行。二进制、ZIP容器、凭据、CI selfcheck旧2C副本和media不进入文本归档；主binary只保留SHA身份JSON。DeepSeek仅响应与outbox收据；实窗media后续独立管理。新Linux诊断.patch未列入文本白名单，原对照脚本/结果足以保留；不借此扩大tracked修复范围。

## 最终状态分层（本次报告收口）

- 代码：5bf已提交/推送冻结且本次tracked clean；Linux none-getter窄修将产生下一候选，不能把out实验当作已集成修复。
- 自动验收：5bf Windows133/133和同v3/2C门禁通过；该SHA三路Linux失败且8/12报告，完整平台验收未通过。下一候选最终自动证据待绑定。
- 实窗：尚未启动，等待明确解锁与root启动协调；这项外部待验独立列出，不是产品缺陷，也不能由自动验收替代。
- 归档：参数和历史角色准备完毕，未执行；最终release SHA/Windows/CI及实窗材料由root裁定后绑定。
