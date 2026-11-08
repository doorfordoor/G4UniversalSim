# AR2 本轮约定范围主审签收（2026-11-09）

当前主审结论：AR2本轮约定范围通过并关闭，R1-AUD-08按三类入口分层证据关闭。已复核独立C原生、源码审查、H2与H3固定科学原始数据结果及审计关闭判据。继续AR3；MR1须在AR3独立验收后由当前主审对话执行，不能用本次阶段签收代替。

## 候选与责任边界

源码 `98379d0dce666d3b3e5411755b9f17b205a4f6993da7906752595d3a6fdb8b8a`，测试 `c88ec7d19b42e7978ce17e6608e9afec2b5a89f8d3b00a25ab28664ed4618041`。26 个明确拥有文件、逐文件 SHA、构建与程序身份在 `out/collab/20261108-ar0-ar6/ar2-integrated-r2/`。本地回退基点为 AR1 提交 `776ac64c63fc08840737f0ddb00c5c1b5ca36138`，不是当前候选提交。

描述不持有 writer/累计器；登记工厂由实际 Action 构造消费，每线程重新创建实例。内置 scorer 保持原算法及输出命名，禁止别名冲撞其输出命名空间。扩展配置描述为唯一配置来源；不允许将实例 enabled 漂移静默覆盖。旧对象注册仍可直接调用，缺重建描述的 Action 克隆在任何工厂调用前拒绝，包括 Sequential。

启动工厂失败锁存 run=-1 首因，保留动作与内核屏障，在实际事件循环前拒绝。仅对 Build 屏障前的故障证明零事件，不扩为任意迟发 BeginRun 异常的全局保证。进入过的 scorer 按实例/run 一次性清理，逐项尝试并保留首异常。Sequential 借用应用唯一输出所有者，MT 仍独立拥有输出实例；真实非 MT 与单 worker MT 分开取证。

## 已核证据

- D 新鲜六目标构建 exit0；focused `20261108-233710-578b7403` 三项通过、零失败/跳过、5978 断言。原生生命周期40项、选择器16项，工厂组件126检查。严格候选身份门通过。
- C 独立新构建三项同样5978断言通过；真实 C HEAD 单列，完整237源码成员与D一致。另17条首因锁存API检查通过。报告 `independent/ar2-native/r2/REPORT.md`。
- 只读原生结果复核431项、931产物集合/SHA一致，包含Sequential两run12+8与metadata归属；`independent/ar2-lifecycle-wrapper-review/native-r2-review.md`。五类旧验证器假通过反例经真实正对照变异11项验证拒绝，`REPLAY-R2.md`。作者复核不替代独立产品签收。
- 17项兼容原报告 `20261108-233845-8fb6f93c` 为16通过、1遗漏构建组件导致前置失败、0跳过；补建既有 scoringNumericCheck 后，`20261108-234608-ef2b20ac` 单项457断言通过。两份原报告保留，见 `compatibility-composition.json`，不伪造一份17全绿原报告。
- H2 `20261108-234126-aa6b346b` 正式50531断言通过，V1a/V4/V6a/V7保持原合同；独核11份摘要、关键加权量及151文件SHA。有限结论不外推未验证物理域。
- H3工程新manifest `983e7f8a3fc22d7495af321ffa9a330711efc3d3f2f94e7f455c0c4266bd797f`，四项各2000，工程分析通过，science=false。科学另起新目录，不把工程结果折抵科学72项。
- H3科学新manifest `ab1affbce80a2ea10538d0300f6b50e3f221ff0bc66948a8e60b2554e817855c`，18原输入、72固定顺序（71后端+1组件），全部exit0，835输出集合/SHA完整。一次原分析所有九项pass；B CI99为[-5.611930e-13,7.045210e-13]、允许±2.002023e-11；C为[-7.627170e-13,9.481746e-15]、允许±1.001079e-11。最终以原JSON精度为准，完整区间在允许域内；未换种、追加批次或改阈值。独立原始数值复核4756项通过，九case均pass；见 `independent/ar2-h3-science-review/RESULT-REVIEW.md`。M真实两线程但每次样本事件分别集中于一个worker，不冒称非零事件均匀分布；初始引擎内部状态unknown边界保留。

## 原失败、审计与后续

AR2 r1保留：selector12/16的惰性CSV假设失败，lifecycle39/40的Sequential摘要归属反例，以及加强判据后额外发现的两个Sequential缺metadata记录。修后r2重新完整执行。C锁存组件外层收集器错误地整体解析JSONL，失败保留，原始三行及native exit0直接独核，未重跑或改写。科学批准检查曾误读UTF-16日志等收集问题也保留，不能冒作产品失败或已执行科学运行。

AUD-08新修旧LET/phase_space两个入口的16项证据与既有H2过滤入口分开。主审另外以相同冻结程序补显式all及gamma,muon两例，均通过，输出 `ar2-integrated-r2/aud08-h2-supplement/`；第三类是已有H2 filter的一致性对照，原审计未显式列出第三名的歧义保留，不将两个新修旧入口说成三个。H2合法mu-零贡献及仅muon非法采用持久化 `h2-native/v7/` 原输入/摘要/CSV，已在独立 `h2-readonly-r2/REVIEW.md` 核验；不依赖已删除的临时h2_volume_scoring子case文件。与本次两个补验及legacy16共同覆盖三类四态；H2第三类限定原单线程fixture，另有未知名threads2负控。补验后完整源码/测试及26文件未变，见 `post-science-identity.json`。

C模板唯一规范内容差异为用户现有 `docs/功能支持矩阵.md`，未覆盖、未绕过manifest；留AR5真实模板/导出门处置。AR3的ROOT Write抛出漏Close及早bias/timer路径仍开放；AR2事件门禁不能证明它们已修。F3 inconclusive、强子LET/DDD完整观测等既有限制保持。

AR2本身不提供动态插件、完整M5生态或新科研能力。AR5还须以真实target/include依赖证明边界，AR6以三项扩展示例证明改动范围，不能用本轮注册表或测试通过替代。

## 验证后文档身份映射
签收说明仅改变模板成员docs/功能支持矩阵.md，动态闭包仍321成员且--check通过；模板identity由80e5844402e26d77718ed2f4940cce846e91f0cfc78d7b70619d5c087c104948变为4303a97d217d5946d8bfc7bcbe36143d7fb61ebf68d00171ae026747423793d3，source仍98379d；当前tests指纹0f3bc162aebfac48846ecfa8164cf10a67bab8fbd1b0ce323ce6d147bc195934只因manifest文件变化，原报告保持c88ec7d。完整映射及原测试manifest见ar2-integrated-r2/docs-only-mapping.json、tested-template-manifest.json；不声称新模板已跑K2或二进制已重编译。
