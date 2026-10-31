# K1 当前验收证据与 I1 独立验收

**K1 阶段验收已完成，I1 已独立完成。** 第七产品冻结为 `2914b3962167325628ede699b1c14a9d224dec41`；资源路径 P1 修复现已通过独立代码审查和真实反例补验，永久防回归 P2 也已补齐并复核关闭。测试补充提交为 `5644e1e52b9c2dd5b463217e9e601c8116f8a913`。已正常快进集成并推送至 `codex`；下方原未关闭节点与拒绝记录保留为历史。

## P1 恢复审查与最终关闭

[独立最终裁决](../k1-p1-close-20261031/independent-review/addendum-02-final-closure.md.txt)确认：旧 r2 反例真实重现，当前 r3 在收据捕获后路径变为链接时拒绝发布并清理暂存，正常 8.3 路径和配置包离线搬移保持成功。新正式回归在旧 r2 上准确失败，Windows 1/1、36 个 v3 入口及 Linux 1/1、33 个入口通过严格证据门禁。原 17 个断言语法节点全部保留，新增测试已纳入原有常规用例。[补充证据入口](../k1-p1-close-20261031/README.md)保留探索失败、正常/负向对照、日志、报告和逐字节复制清单。

[当前身份映射](../k1-p1-close-20261031/final-identity.json)证明 350 个产品文件与原冻结相同，唯一代码/测试变化是该正式回归增加 73 行。原 Windows 全量、官方 CI、原生适用性映射及 I1 验收按各自原身份沿用；新单例的 69 个入口单列，不把原 730 次执行改称新测试指纹下重跑。无产品代码变化，不新增性能基准或科研物理验证结论。WSL 本地文件系统通过不覆盖 `/mnt/c` 的 `renameat2` 限制；任意并发目录替换不在本专项保证范围。

## 第七正式自动验收

| 项目 | 实际结果 | 证据 |
| --- | --- | --- |
| Windows全量 | 182 PASS / 0 FAIL / 0 SKIP，57181个v3断言入口；原运行自然退出0 | [原报告](../k1-delivery-20261031/verification-2914b39/windows/report.json) |
| Windows原始证据严格门禁 | 报告、日志原SHA、非零计数与求和、冻结身份均通过 | [独立审计](../k1-delivery-20261031/verification-2914b39/review/k1-seventh-windows-review-audit.json) |
| Windows相对第六严格基线 | 同代182例逐例不下降、无缺项；总57181→57181、差0；第六原日志SHA/marker重核通过 | 同上独立审计及[五道门禁](../k1-delivery-20261031/verification-2914b39/windows/gates/original-gate-receipt.json) |
| Windows相对F5严格基线 | 原160例无缺失/逐例下降；50898→57181、增加6283 | 同上；不只比较总数 |
| 官方CI | Linux run41189260366、M0 run41189260331，4 jobs success，4原ZIP/5277members/12reports；548 PASS / 0 FAIL / 0 SKIP、133720个v3入口 | [CI最终审计](../k1-delivery-20261031/verification-2914b39/ci/control/review-result.json) |
| CI证据与基线门禁 | 12严格证据门禁、12同平台F5逐例/总量门禁通过，无regression/raw-log/identity错误；40个external完成诊断、8个受控terminal观察 | 同上；组件观察不改称原生UI实测 |

原生 GUI/CLI 证据保持第四/第五/第六的原身份。第六至第七只改一行测试输出编码，350项产品Git对象及138项冻结GUI原字节一致；[原生适用性映射](../k1-delivery-20261031/verification-2914b39/review/k1-seventh-native-identity-mapping.json)说明历史证据适用范围，不冒称第七重跑。第六原生误把两次 generated 记录称 external 的勘误、另补实际external无package完成，以及CLI首次后处理误计历史行的失败均保留，不改原收据。默认Windows系统文件选择器未验；Qt widget选择器与助手操作不称用户本人验收。

第五取消原因修复后的正式自动与定向原生证据保留；第六实际M0 Windows workflow的cp1252编码失败作为失败历史保留，第七编码修复后重新冻结验收。第四/第五/第六分代原件位于同级[分代证据入口](../k1-delivery-20261031/README.md)，不以局部成功覆盖旧失败。

## I1 独立验收

I1 已满足环境发现、诊断及显式选择范围。第五 `f9a9ddb` 的13份规范报告、16次I1执行覆盖Windows、Linux11.3.2/11.4.3和M0双平台；独立源码审查两项P2已复核关闭。接续审查重新核验37项原SHA/断言标记，全部通过；第四保存实窗图已直接查看，单候选显示x86_64、Geant4 11.3.2、MSVC和必需数据目录已发现，界面明确选择不会模拟。

接续审查起始快照是 `4167c44`，五项I1源码/测试/共用启动模块到 `2914b39` 的SHA完全一致；[追加映射](../k1-delivery-20261031/verification-2914b39/review/k1-resume-i1-seventh-mapping.json)保留原收据、不重跑或重审I1。自动多候选/缺库反例、真实后端查询和单候选实窗分别计证，不称多套真实安装或现场卸库均有实窗验收。

数据内容hash仍unknown；SDK/tools不等于编译链接，可选Python metadata不等于import；不声明完整DLL/SO闭包或环境激活。环境覆盖仅作用探测，GUI仅接受后端路径，后续运行在实际cwd/environment重验。没有后端/SDK/编译器仍可加载诊断服务，GUI自身需PySide6。I1不初始化、模拟或验证物理；Geant411.2和I2安装分发保持独立。

## 恢复审查前的资源边界 P1（历史节点）

既有[候选原记录](../k1-delivery-20261031/review-evidence/k1-relocation-candidate/README.md.txt)的r3节保留：外部receipt捕获后，目录晚发生alias/reparse变动而指向staging时，base拒绝发布，r2直接resolve比较绕过原拒绝入口并发布；两脚本退出0不等于两种行为均正确。r2因此不可直接接受。r3候选在规范比较前保留已有 `_no_links` 检查，正常功能专项已留证，但晚发生目录别名变动反例的独立最终裁决未取得，不能称P1已关闭。

待裁决的最终字节涉及 `core/experiment_bundle.py`、`smoke_k1_relocation.py`、`test_k1_staging_alias.py`。先前最终独审返回上游安全拒绝，详见[原事件](../k1-delivery-20261031/review-evidence/incidents/relocation-independent-review-incident.json)；未重试、未换代理或改措辞重投，普通功能回归和覆盖映射均不代替这一裁决。所有其余已完成工作继续交付，K1整体保持未完成。

## 原交付与检出边界（历史快照）

当前任务分支 `roadmap/K1-trusted-workflow`；检出起始核对为任务2914b39 clean、codex=e701c7f clean、D盘5465dbd及21个原untracked；这是该次检出收据快照，最终集成前另按实际状态核对。当前未合codex。既有STATUS、ROADMAP与本证据README承载状态，不新增交接/状态入口。配置包不是K2工程，有限geantino零沉积比较不外推Q2科研物理验证。


## 交付材料复核

[最终独立复核](independent-review.md.txt)及[机器可读收据](independent-review.json)确认4673个交付文件的原字节、13份最终报告和文稿边界；主负责人已按[复制收据](publication.json)将其写入本仓库，未改写历史原件。另见[主审结论](../../collab/reviews/20261031-k1-seventh-review.md)。这项复制与文档复核不补足资源边界P1的必要独立裁决。

归档保留原始深目录。此次 Windows Git 默认路径限制曾拒绝入库，随后仅在单次 Git 命令使用 `-c core.longpaths=true` 完成；没有修改系统或全局 Git 设置。交付检查另外核对 Git 索引的实际字节，不能只凭 add 的退出码认定原件完整。此记录不扩大 I2 的默认环境安装验收范围。

正式入库后另核[Git索引字节与干净检出链接](staged-verification.json)、[全仓文档链接日志](doc-links.log)及[源码/测试指纹](source-test-identity.json)：4673项证据索引字节相同，636条相对链接无失效，新增活动文档205个本地目标均在跟踪文件集中。源码与测试保持第七冻结；没有因纯文档落版重复运行物理矩阵。

## 此前验收收尾与拒绝诊断补充（历史节点）

用户随后提出“如果不影响最终软件性能结果的话，结束验收”。本轮停止追加验收，保留已通过的主体功能和平台回归结论；这些回归没有发现其覆盖范围内的模拟结果退化，但不是性能基准，也不能证明资源导出的全部边界对后续复现无影响。因此不将这一条件视为豁免 P1，不改为 K1 全部完成，不合入 codex。I1 已完成的结论保持。

对原始代理会话的定向元数据核验已找到明确错误字段 `error.codex_error_info=cyber_policy`。两份 incident 对应两名代理，原始会话各有两条失败终态；观察时间与失败时间分别保留。具体触发条件和是否误判仍未知，没有额度不足、账户封禁时长或本地工具故障的确证。旧 incident 中“不重试”仅保留为当时记录，不据此抹掉后续错误事件；本轮未重新执行被拒专项。详见[诊断说明](p1-refusal-metadata.md.txt)与[原始事件定位及结构化记录](p1-refusal-metadata.json)。该诊断不构成代码独审或 P1 关闭证据。

若后续继续关闭 P1，应先通过官方误判反馈/适用访问权限路径解决审查通道限制，或取得合格人工独审的实际结果；仍需对应当前候选字节及原定反例验收，普通功能通过不替代它。官方说明合法或无关活动也可能触发保护，并提供 Codex 反馈与 API 申诉路径；申请或身份验证本身不保证批准，批准须适用于实际身份、项目和产品入口。见 [OpenAI 官方说明](https://developers.openai.com/codex/cyber-safety/)。本轮未提交外部反馈、申请权限或修改账户设置。

## 实际集成交付

验收提交 `864bb2f9040e189d459565ef3b3a41317cb4682f` 已从原 F5 基线正常快进到 `codex` 并推送，任务分支同时保留。全部命令退出 0、集成检出 clean、远端提交匹配，见[集成收据](../k1-p1-close-20261031/integration/receipt.json)。[实际检出核验](../k1-p1-close-20261031/integration/checkout-verification.json)确认 350 份产品、326 份补充证据及既有完整归档 4672 个成员的原字节一致；原归档清单本身也相同。此后仅补充交付收据与状态文字，不改变产品或测试身份。D 盘原独立检出未修改。
