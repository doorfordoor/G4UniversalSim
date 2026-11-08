# AR4首片：run/path所有权与关联消费者修复签收

2026-11-09，当前主审对话完成本片源码、正式报告、原始产物与独立复验核对。**本片限定签收；AR4整体未完成，继续SPS、material/geometry迁移。** MR2仍在AR4和AR5独验后由当前对话执行，不以本片替代。

run/path迁移单独提交 `bf3fd37f129fedd62d10b17f9ac4c8ccc6b98fd7`；关联行为修复、注册和本报告另片提交。两个提交的最终合成须与本次冻结35文件逐字节相同，见 `out/collab/20261108-ar0-ar6/ar4-interim-closeout/final-owned-sha256.json`。中间仅分离runner注册，不将全候选报告冒作中间提交单独执行；原用户两暂存blob及其它历史变更排除，不push。

## 冻结身份与正式证据

实际C++ source为 `66a027a0acb883a67fed50dbbace6a383353dc7e0e3f4516eb1d2043395adcfe`，新鲜MSVC/Release/Geant4 11.3.2 backend SHA `53602a799caa843ad45412ca175849212fa2873123f3c7f53c9e008574686670`。configure/build均0，编译收据仍记录原HEAD 3ecf3a7及dirty事实，不改成事后提交身份。主审直接比较src/include/main/CMake，实质改动仅SessionServer.cc；AR1几何、AR2计分/物理未变，`cpp-scope-review.json`保存比较。

报告均在 `out/collab/20261108-ar0-ar6/ar4-session-r1/`：

|报告|实际结果及身份边界|
|---|---|
|formal-native/20261109-042128-a19eb679|四个真实进程组成一个case，548断言、strict稳定；tests9c97c7a4…；独审440文件。close本轮32结束含2aborted、CSV30行，不称98有效计分行|
|formal-gui/20261109-042303-bab40d0f|15case、87726断言、0skip，strict稳定；同tests9c97…；包括plot290、scan59/66、publication55/326、run/path195/95、session-panel275及既有链|
|formal-compatibility-r2/20261109-042903-32aef046|**原报告2pass/4fail/0skip**，tests6b466f04…稳定；receipt650与gui_session_backend71通过。三协议D:/Temp创建输出拒绝、未握手；GUI输入exit1，不猜同一唯一原因。原失败不改写|
|formal-compatibility-r3/20261109-044834-e9490ea2|项目内TEMP补验四失败项＋面板，5pass/10750断言/0skip，strict稳定；protocol879、cancel162、replay9313、GUI输入108、面板288。包含真实生成包3/3事件|
|formal-rollback-r4/20261109-051504-48a7831e|最终两文件回滚修复后8pass/1960断言/0skip、strict稳定；K1历史78/搬移138/窗口178、F5事务345/历史241、导入393、run/path479、GUI输入108|

最终tests `2103a8557ffd53c91e89d640bad12a1c9c98e83f161133b1678712b6f86181ab`，freeze `formal-r4-freeze.json`。主审逐份 `check_report_evidence --require-candidate-identity`复核；r2仅以明确allow-incomplete核原件，不据此改判通过。后继显示投影和留证helper的差异单列：独立AST核回执准入未改、原42运行断言和四例流程保持；不把旧650挂给新tests，不因无关补丁重跑四故障输运。

模板动态--write/--check通过，338是实际成员结果而非硬编码；identity `71d1a623637a2c0ca1c52b7b2baf49ec463547b8cfeeb54e4ba73a5d3aa87d9c`。本片没有新K2 export/build/安装签收，AR5仍须当前候选双平台实证。

## 所有权与拒绝原子性

19个有效binding及3个raw由现WorkspaceSnapshot/EditSession持有；纯run_path_model不创建QWidget、不读文件。控件提交动作，读取/保存/preview取得同一快照。未编辑flat/settings差异保留，seed半输入、路径空白、数值raw按原边界保存；generated包路径是显示投影，不写回编辑模型，不新增持久owner或Undo栈。

主审实读reducer、capture/getters、project/apply、事务发布与回滚；原独审 `independent/ar4-run-path-review/REVIEW.md`覆盖76 headless/25 Qt/6consumer、getter毒化及既有测试。主审又发现generated绑定在拒绝前清除的交叉缺口，未把分别通过的overlay与容量检查外推为组合通过。

最终transactions SHA `b1ed4fb6d7d81c1e3913931c6e080171d25756fc3172852d6e27e17c3fdf8ecd`，smoke SHA `34cfd4754d4c634c17dbe2a01545adfa5b44979938afed0cb63c469cb7d113b9`。候选准备、capture与replace共用拒绝恢复边界；outer仅在实际提交变化后失效，空事务保持；局部显示副本不进入模型/历史，双失败冻结，普通Undo/Redo/repair仍使旧资格失效。

`independent/ar4-generated-rollback-review/REVIEW.md`：50/50场景899核对；实际fields服务失败记录4/4、28核对，epoch不回退、不恢复can_run。没有构造成功运行资格，该限定与源码不回写服务状态共同判断；不称全部真实成功资格/异步资源竞争已覆盖。原反例、作者主动停止attempt2、独审模态通知attempt1停止均保留。

原生正常路径见 `independent/ar4-run-path-native/review.md`：Windows两个正式host正常exit0、无所属残留；真实键鼠/UIA、保存/文件对话框重载、半输入、长路径、overlay保存不污染模型。应用缩放1.0/1.5，实际DPR1.25/1.875，不称系统100/150或跨屏验收。图像实际查看、host显示夹具与真实生成分开。此证据绑定修P2前正常路径源码；不冒新候选已重开原生窗口，后继P2由真实Qt及正式受影响链补验。首observer错误exit1保留。

## 原审计逐项关闭

主审回读首轮JSON validation和第二轮MD原条款，完整导航见 `ar4-interim-closeout/audit-closure-map.md`；原标准不缩减。

|原ID|关闭证据与保留边界|
|---|---|
|R1-AUD-01|scan独审发现r1递归aux仍指A的P1，r2按可达宏/配置闭包修复，52+27控制与真实Qt替身通过。原A/B共存、两个inspect＋两个2事件transport及A全SHA不变保留原r1身份；r2重备原输入同有效消费、外部资源只读规则明确，不冒新输运|
|R1-AUD-02|collect直接消费共享read_persisted_run_evidence；独立12态逐字段比较历史同一服务、CSV空exit/trust，覆盖crash/stop/stale/错指纹/坏与缺记录等。summary-only仍独立等级，v1 mtime/size不冒密码学绑定|
|R1-AUD-12|类别同集合乱序/部分重叠/无交集，按(series,volume)同一映射生成屏幕与CSV，缺项不补零；独立原数值/图形/CSV对照|
|R1-AUD-13|两run异值、选后run及overlay开关，核选中ID/实际image/CSV；不只检查能绘图|
|R1-AUD-15|支持参数沿活动模式、稳定editor_id实际改生成字段；phase/manual/inactive不支持组合在产物前拒绝。命名源10/20MeV的有限真实输入/运行回执和独立读回，与gauss17/23文本控制分开计证|
|R2-01|真实CSV与uproot写入ROOT，经生产reader/Qt/PNG/CSV核单X/单Y/双单、非零中心/非1宽/换轴及多格。六图实际打开；原值/低N不可用误差保持，无跨格协方差不画合并误差。非Geant4科学验证|
|R2-10|两publisher link成功unlink失败保提交事实、警告及残留；真实12个Python child/11场景/9解析控制核GUI/队列、非零/取消/坏payload/错target、无覆盖。正式55控制另覆盖临时写失败/闭合stderr等；不删已发布目标，不把清理失败吞成无警告|

独审原报告分别为 `independent/ar4-scan-review/review.md`、`independent/ar4-plot-review/review.md`、`independent/ar4-consumer-review/R2-10-PUBLICATION-REVIEW.md`。plot独立163检查、24图/实际ROOT；旧正式case290但tracked门失败保留，后续主审15case已补严格跟踪。scan原native仅4事件，不外推科学/动态宏全部支持；publication 12 child不是全exit0，含预期非零和取消。

据此27正式问题累计关闭19项，余8项归AR5；不将SPS/文档迁移的未完成架构合同算作审计问题已全部关闭。

## R2-R01有限防御验证

内联与引用共用run/request/status语义门，引用先核实际size/SHA/JSON；缺身份/类型/未知状态拒绝，合法failed回执可接收。成对状态矩阵和90负控保留。原真实55243字节/131产物大ref由独立审查者经实际SessionClient→MainWindow→SessionPanel复用，引用显示已纠正；坏SHA/仅路径不得升级为核验成功。

实际受控artifact_hash_master暴露旧producer在CollectRunArtifacts前决定终态，最终进程1但回执completed/replayable=true。主审修为收集后读取失败锁存，再决定receipt/lastRun/replay step；cancelled→aborted→failed优先级不变。四进程r2原件456/456集合/SHA、1435独立核对通过：normal0/completed，close/hash/inline_hash均1/failed（该轮close aborted0）；259 hashed及142 unavailable不混。对应 `independent/ar4-consumer-review/native-r2-review.md` 和生命周期 `independent/ar4-session-finalization-review/REVIEW.md`。

此为真实后端控制故障路径，不冒设备损坏实测；原r1 close为aborted，旧脚本只许failed的误断言保留。新producer源manifest资格已正确，原manifest.exit_code/closing时点0与最后进程1分层事实仍明确，不宣称所有exit字段一致。新正常replay9313通过不等于故障replay输运已全部验证。

留证finally缺口另修，独立11个fake session/文件异常控制通过，原首因不被cleanup覆盖；不可写存储只尽力保存、不保证文件存在。tests与执行边界保持。R2-R01记有限防御验证完成，不扩大成完整闭合schema或所有并发IO保证。

## 后继

AR4继续SPS→material/geometry，按已独审合同/最小写集串行，不改J4交互流程。AR5完成8个剩余正式问题和SDK后代收尾风险、真实target/闭包/双平台交付；随后当前对话MR2→AR6→MR3。F3不追加测量，H2/H3科学仅按原身份复用，DeepSeek/web暂停至完整架构验收。监督任务保持30分钟ACTIVE，提示改为从仓库读取当前阶段和规则，无固定AR1旧指令。
