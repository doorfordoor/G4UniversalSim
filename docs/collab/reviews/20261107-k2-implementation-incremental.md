# K2-2 增量独立审查（实现未冻结）

2026-11-07。固定清单及合同不变。本记录是交付前发现与指导，不是 K2-2 验收通过，也不是双平台构建或物理验证。

## 原任务核实

原 task `g4-j3-desktop-20261103`、session `session-9d7a035a-8a42-4f18-885b-beb4a0ec12f4`。桥接实际地址从 context 的 `base_url` 读取；不是 `bridgeUrl`，误用空属性时默认端口连接拒绝，随后正确地址 health ready。未变更服务配置。

原 turn125 并非再次 SERVER 终态：真实事件70959为 `turn-aborted`。之后桌面来源 user/request `4cf0e80d-04ec-4185-89dc-eef98ebb7d59` 以同一接续原文启动 turn126（70962），模型仍 `deepseek-account-vision/deepseek-flash/max`。主审未重复派整项、切模型或重启应用。turn126 专项自测输出 `k2 export checks: files=319 ... symlinks=yes`（70983），但完整交付回执仍缺；不得视为整个功能通过。之前三次 AssertionError 和压缩边界失败保留原桥接记录。

## 已证实问题及最小处理

| 阻断项 | 具体反例或源码证据 | 最小范围与停止条件 | 指导回执 |
| --- | --- | --- | --- |
| K2-2 双平台安装版模板链 | Linux 原资源循环仅 copy_tree，没有像 Windows 显式调用模板 builder，源仓库不存在 export-template | Linux 对应资源循环复用现有 builder，开发/安装模板身份相同，回到原交付 | round163，out/collab/20261107-k2-contract/linux-template-guidance-receipt.json |
| K2-2 身份显示 | GUI 成功消息读取旧 identity.value，冻结字段已为 digest，显示 None | GUI 读取 payload_identity.digest，原 GUI smoke 核真实摘要 | 同 round163；已观察源码改正，尚待正式复验 |
| K2-2 数据边界/R3 | `_posix` 用 PurePosixPath 接受 Windows 绝对盘符；自洽模板 manifest 经 `_validate_manifest` 后，`_copy_template` 抛弃 staging 前缀并在外部创建文件 | core/export_project.py 安全相对成员验证及必要 builder 同链，复用 K1 既有校验、不改 K1；有限回归要求 R3 拒绝且 staging 外无新文件，原正反例通过即停止 | round164，out/collab/20261107-k2-contract/path-confinement-review-receipt.json |

路径反例仅写本次新建专属测试目录，无已有用户文件被改写。真实复现程序、结果及7文件不可变快照在 `out/collab/k2-implementation-independent/revised-r2/`：`probe-template-path.py`、`path-probe-result.json`、`identity.json`。被审 exporter SHA 为 `6521a3bc9a5cc0c32c70811d7c1e52cf6106394c7167f2fc99ad3e10a2b7ed09`。这是实际受控文件写出反例，非仅静态猜测。

同一 R3 最小修复另由 round165 指明词法路径反例：`link/../new-export` 在 `abspath` 后丢掉 junction 分量，K1 原始 guard 拒绝而 exporter 接受。真实结果 `revised-r2/lexical-link-probe-result.json`；初次创建 symlink 遇 WinError1314，改用本次自有目录 junction 复现，无提权和全局设置更改，未执行实际导出。该失败和换方法事实保留。

主审随后对两份修复文件保存稳定快照并运行四个限定反例，`path-fix-r1/result.json` 记录全部 R3 拒绝，目标及 builder 包目录都不存在：绝对 manifest 成员、词法 junction 目标、词法 junction 输入、词法 junction builder。exporter SHA `0f548a5fdeedc7fb853d71084f5727490445b7bd85de78a05e86d078e959e5b2`；builder SHA `087013513ae040c431f7db653eaff0e341fd46930fbaf3ee6a4ccb307a9f2b22`。这是本阻断反例的局部独验通过，完整 K2-2 仍待作者交付和正式回归，不能外推整项通过。

## 辅助与后续

原网页线程先核实 failed/stream disconnected；旧报告保留原失败身份。本次仅针对上述新不可变快照发送有限只读复核，thread `01a1b16c-1865-7812-b4e2-43210d7ffc00`，turn `01a1b505-6ca5-7ec1-b79d-9cfe8ed55e9f`。本 turn 同样终态 failed/stream disconnected（cursor:30），有完整最终摘要和已落盘报告 `revised-r2/web-review.md`，不能登记 completed。

主审读取报告并独核其冻结原句与源码，再在原不可变快照运行私有函数/文件反例：`revised-r2/probe-contract-semantics.py` 与 `semantic-probe-result.json`。未运行后端或改产品，确认以下六类需纠正：

- 导出说明缺冻结的显式 macro/output 参数；改写还为原无 macro 的 S-A 插入字段。
- S-A README 清单 after SHA `31f14e2f…`，实际准备输出为 `4edca373…`，确实覆盖成 generated 文本，审计不实。
- 两次 beamOn200 静态接受但仅登记200，实际宏请求合计400；冻结单 run 代表子集可最小拒绝。
- 路径值重写同时改变 CRLF、键空白和末尾换行；合法 UTF-8 BOM 被拒绝，违反冻结字节保留约定。
- verify_export 加入清单外文件仍判身份有效；现有源码还追随链接，需保守核实际闭包。
- 模板算法名/行约定与冻结定义不同；在一次受控 private manifest 晚变化后，builder 实际返回 built 并发布仅 `late_changed:true` 的未校验 manifest。

round166 已将六类证据及停止条件合并发给原实现任务，回执 `out/collab/20261107-k2-contract/semantic-contract-review-receipt.json`。主审不盲采辅助模型 P1 标签；本次均按原固定合同或实际数据/身份矛盾核实，不新增清单或扩验收框架。网页报告仍不能替代作者交付后的独立正式复验。

## 08:25Z 接续与六类纠正局部独验

本轮先核 CURRENT，再查原 task/增量 transcript：turn126 仍在执行；真实 observedConfig 保持 Flash/max。初次 limit200 返回最新200条而非缺口起点，主审未直接推进游标，随后 limit1000 补取71440–71806共367条连续原事件（`hb0825-transcript-full.json`），不存在本段漏读。旧压缩/测试语法与断言失败保留，未改写成一次通过。作者 static 和 GUI smoke 已出现成功输出，但最终回执尚缺，不能替代最终候选测试。

主审只读复制最新两文件，保存 `out/collab/k2-implementation-independent/semantic-fix-r1/`：exporter SHA `005e90e6b508925937e2b3535910204f763af2816efe8347898723f81e756793`，builder SHA `8770cb8c557bc186e63773c6ff00874de10683a37658b304a9e2960587c18e51`。独立脚本 `verify-semantic-fix.py` 验证14项全部通过：README字节及审计一致、未插入原无macro键、多BeamOn/倒序拒绝和单次正例、值跨度改写保留BOM/CRLF/空白/注释/无末换行、BOM解析、显式运行参数、干净闭包正例/额外成员拒绝/junction根拒绝、模板双空格行算法及digest、真实受控manifest晚变化R10拒绝且无发布。原反例及旧快照仍保留。此结果仅关闭这些增量反例，非完整K2-2、构建或科学验证。

round167已沿原任务告知局部独验结果，要求继续原GUI/正式注册/文档及最终模板与报告身份，停止扩大覆盖，保留旧75ac模板身份及失败。完成约定交付停写后才冻结并执行整项独验，随后进入K2-3。

## 08:55Z 原交付、冻结与实际检出失败

原 turn126 已 completed/停写（72174及task终态已核）。最终 receipt SHA `1b76fad320ca82406d6251195a03972af50e33a5674702333b82a76cfadd8c10`；outbox SHA `38630d3c90154b496fd64b2b84b06965762781b043debd4413a7843b4738e27f`。24声明文件与310模板成员均与作者原SHA相符，模板digest `2c4f39c3…`。主审按白名单提交 `d999e2366460ba75503c67a2dd6a0c35e7eb5a55`（未推送）；本地ROADMAP/H8、F3讨论与未跟踪协作文件均未混入。作者static 50/50、9213断言但tracked gate exit1；GUI 80/81、10823断言但PyVista skip/exit1，原报告均保留失败。已核既有 `gui/.venv` 含PySide6 6.11.1/PyVista0.48.4/VTK9.6.2，正式补缺可复用，不安装全局依赖。

C独立区干净快进d999后执行原模板check，**实际失败**：清单夹带两份本地未跟踪tools/collab脚本；另9个成员跨检出仅CRLF/LF差异即身份不符。全量反例 `out/collab/20261107-k2-implementation/independent/clean-checkout-template-failure.json`。故K2-2不通过，未运行重复全矩阵或启动K2-3。

最小处理决定 `docs/collab/decisions/20261107-k2-clean-checkout-template-fix.md`：仅收回原tools直接成员规则，并在模板来源读取/复制中统一受控文本CRLF→LF实际复制字节；不写原src/include/main，不扩大到项目输入或最终export身份验证。round169请求已接受并启动原session turn127（72176），正在实际读源码和修复，回执 `clean-checkout-template-fix-receipt.json`。新作者回执使用author-r2与implementation-r2，旧失败身份不改写。修好立即回原清单整项独验。

## 09:25Z r2交付与独立执行

turn127 completed。主审核r2六文件及308规范模板成员与回执一致，提交 `41991fc64d2bd1a15e8998c2d19a50f85d9a745f`（未推送），C区实际快进并执行原template check，**ok / problems=[]**。正式模板为 `b91e34e42b532d605f7ba92178a3ee04d90b30b12c244b496cb7d48cd5a86c81`，manifest SHA `ee9e1c88853a8d82b69717c40c6cad14afab75820ccc08b408e4b521c4222ca7`。两份本地协作脚本已排除，D原件未删除；旧d999/2c4f失败保留。

主审Windows两次有限执行方法的原报告均保留：C临时目录0断言失败；改用D专属临时目录后static执行2797断言到R12原子rename的WinError5，GUI执行8断言后导出返回None。没有改发布器或重跑至通过。随后换既有WSL环境：system python静态用例因既有project/model导入PySide6.QtCore而0断言失败，不宣称静态夹具无QtCore依赖；改用已有完整venv的GUI专项在同一C候选实际执行 **1通过/0失败/0跳过、33断言**，原报告 `independent/r2-wsl-gui/20261107-173403-a1b89ff9/report.json` 已通过原严格证据门。该限定GUI结果绑定4199，不是整个GUI矩阵或新候选CI通过。跨挂载Git元数据收集耗时保留，原两个父报告最终均已收回，不重启旧任务。

为避免挂载元数据耗时并核干净归档，主审由4199 Git对象生成受限源码tar（SHA `3dbe1883b39324b0e6d32ea82bacc6bdd09d658e634901f3355095663f9b3d33`），在Linux自身文件系统只读产品快照执行原assert probe。r2脚本实际失败于强求ROOT/tools/collab存在；r3早期快照越过该点后失败于R9假定未跟踪ROOT/out存在。相邻源码还要求原树已含CRLF header。均为宿主依赖的测试夹具缺陷，不伪造目录或改产品通过。原归档、旧树和两份失败日志保留，快照范围/唯一测试覆盖SHA在 `independent/r3-test-snapshot-source.json`。

round170/171只修原专项夹具；turn128已completed，r3回执SHA `ec82853ea5a76f21410cb7042ca190f66a6ec49738fb4cff459644991e2c88d4`。作者D与私有干净树均exit0，唯一变更为测试脚本；产品4199/b91e不变。主审不重复跑完整profiles，待下一项有限产品修复后合并独验这些夹具。

另一个独立Windows CLI在明确D盘独立父目录未创建staging或目标，299秒已消耗286秒CPU。300秒预算仅结束本轮自有CLI；一次45秒有界诊断在15秒取得真实栈，定位 `tempfile.mkdtemp` 的Windows PermissionError重试（Python3.11 tempfile.py392）。不能推测底层权限拒绝原因。原CLI/launcher与诊断子进程均核清理，两个目标不存在。最小决定 `20261107-k2-staging-permission-failfast.md` 仅修本K2入口的staging分配为有界、诚实R12拒绝，不改K1/权限/其他用户程序。round172已排在r3之后，turn129实际启动；K2-2仍未签收，K2-3等待此最小缺陷与最终静态独验。

DeepSeek 仍是产品单写者。交付后按冻结合同核源码/模板身份、原测试日志、GUI smoke 与范围文档，再固定候选于 C 盘独立复验；K2-2 通过后才实际执行 K2-3 双平台构建运行和一行受控 C++ 修改。F3 不追加性能批次，不进入优化，不改变门限或阶段标签。

## 10:05Z r4独验与K2-2签收

2026-11-07。固定清单不变。K2-2通过，K2-3进入执行，K2整体未关闭；正式矩阵/云CI/安装与交班属于K2-4，尚未通过。

产品冻结 `42be987e92569918499a638ad17902bbc785521a`，D主分支与C独立区同一候选；模板 `b91e34e42b532d605f7ba92178a3ee04d90b30b12c244b496cb7d48cd5a86c81`，308成员。r3/r4原作者回执和此前失败完整保留，turn129已真实completed/停写。主审仅白名单提交，未混入用户ROADMAP/H8与F3讨论修改。

主审独立源码审查及原14项语义反例复验已完成；最终Linux原生固定源码快照的原专项exit0、3538执行断言通过（P3/R1–R12及正例）。归档4199的受控源码覆盖两文件与最终提交Git对象规范字节完全一致，身份和退出码见 `out/collab/20261107-k2-implementation/independent/k2-2-acceptance.json`。此前完整输出终态未保存在可恢复收据内，故仅补一次记录真实退出码的最终有限专项，未循环跑全矩阵。

Windows独立区42be候选对原拒绝父目录直接执行分配，立即诚实R12/write_failed，目标不存在；不再长重试、不改权限，底层拒绝原因仍unknown。原300秒/45秒失败与诊断保留。GUI按实际影响复用4199的既有专项：1通过/0失败/0跳过、33执行断言和原严格证据门通过；保留原SHA，不冒充42be新GUI正式报告。R4仅单点staging分配，其正负例由最终专项覆盖。自动专项通过不代表原生构建运行或物理验证。

允许按原冻结合同§7.2/§8在仓库外实施K2-3，Windows/Linux均复用既有11.3.2 SDK；S-A200、S-B1000事件，P7/P8与一行受控C++修改。原5%和科学门、F3未关闭及F7依赖保持。只写导出副本与本项证据，不改产品或扩大平台框架。构建/组件指纹以实际依赖为准；如不符原冻结观察量，保留并报主审核定，禁止伪造变化或改额外源码强制满足。


## 10:28Z K2-3真实运行反例与最小前置修复

原turn130仍running；73027–73387、73388–73419、73420–73451连续增量已收。Windows原build exit0，但原CTest exit8缺si_proton.csv、原S-A exit1解析出project/project/config/parallel.ini。主审直接核ParallelWorldConfig.cc的ResolveRelative与h2VolumeScoringCheck真实读取路径，否定此前统一cwd的含糊合同解释。手工补表/主配置副本成功仅诊断，原失败不追改；摘要/科学比较不能代替原包可运行。旧受控副本复制CMake缓存仍指原sa，首次build0但指纹未变，也不签修改成功；在途新配置构建可完成，不取消。原日志/摘要和原能力/产物SHA快照见out/collab/20261107-k2-build/independent/original-42be-failures/identity.json。

主审最小决定20261107-k2-native-runtime-minimal-fix.md仅更正parallel的INI相对值、唯一Si proton表闭包、对应原专项及必要事实文档；不改后端、K1、writer、CSV数据或CTest要求，不扩整个scenarios，不降科学标准。round174已steer到原turn130，已实际读取；r5交付后独审冻结新候选再回原K2-3。原合同文件/SHA保留，新决定明确消除冲突，不伪造原合同正确。旧原生S-B/依赖与编译证据按真实范围可复用；原两个构建正常等待不计失败尝试。

## 10:58Z r5交付独验与恢复K2-3

2026-11-07。依据原固定清单与20261107-k2-native-runtime-minimal-fix.md，仅签收两项最小修复，恢复K2-3。整项双平台验收/正式云CI均尚未通过。

产品冻结56b1da77704223a8b84e3256c915c8242aad8946，D/C同产品；r5原回执7a8db9cf…，六文件原SHA及全部309规范模板成员独核一致。正式模板1fa4e29430ee813a5736329b9fd2677e178dbac11ceabb289ed828055de8df29，manifest 4f512a9d…；唯一新增scenarios/semiconductor/niel/si_proton.csv，其原内容未改。C实际检出template check exit0/problems=[]；原b91、旧失败身份均保留。

独立固定源码快照专项exit0/3551执行断言；同候选C真实检出的GUI专项exit0/33断言。受限归档GUI首次缺既有shielding_coating依赖失败，转真实检出后通过，原失败保留，不要求修产品。新导出主INI未手改，Linux原生S-A200/200 completed与H2组件均exit0；此有限运行复用先前仓库外本机构建，236个编译输入字节与新导出逐个相等、真实exe SHA已记录；**不是新候选重新构建或K2-3全通过**。主审Windows新目录仍拒绝，Linux首个运行缺SDK逐数据环境变量的失败保留；改为复用现有micromamba激活环境后上述运行通过，未改全局环境或权限。完整证据out/collab/20261107-k2-implementation/independent/r5/acceptance.json。

作者r5覆盖了主审original-42be-failures/identity.json索引，原索引字节未保留；原始日志/能力/产物SHA快照和consumer-counterexamples.json仍在，新r5/failure-evidence-integrity.json据实际原始文件重新列索引。主审签收该记录限制，不伪称旧索引原样；不影响两项真实反例和修复验证。后续严禁作者写主审independent目录。

恢复原K2-3有限矩阵：从新候选原始导出取证，两个component的精确CTest集合、双平台S-A200/S-B1000、确定性、P7/P8、一行C++修改、真实产物/依赖/摘要/比较均须完整。复用SDK和确有不受影响的旧编译/依赖/运行证据，保持旧SHA，逐项说明编译输入/输出数据等价映射；不为换一个导出器提交号盲目重建同一C++。所有新构建先核缓存CMAKE_HOME_DIRECTORY，绝不复用指向另一个树的缓存。修改后科学判据与F3限制保持，不再扩大范围。

