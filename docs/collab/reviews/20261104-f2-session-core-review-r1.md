# F2 后端首候选独立复验：不通过，限定修复

候选9f4d73de6026c3c1b7735229a276df9168301ada；C盘独立重新编译Windows及WSL/Linux 11.3.2均退出0，源码指纹6ec4965905148761661b92ceb89cbb0e7c343487b188dabcacc9ef77e83c07da与作者相同，C构建身份为9f4/clean。此结论不是完整F2验收。用户已选B，无需再次确认方向。

## 已确认和原件

主审Windows七项专项原报告6通过/1环境缺口：随机命令用例缺独立构建的randomCommandGuardCheck.exe，不算产品缺陷。已在同一独立源码身份补构建该目标，并仅补跑该项：out/collab/f2-core-independent-windows-random-helper/20261104-134202-676d95ad/report.json，1通过/0失败/0跳过、302断言。原失败报告保留，不能改写成原七项全绿。其余新协议/取消及旧入口、摘要和GPS相关用例通过，原报告out/collab/f2-core-independent-windows/20261104-132406-07cec254/report.json在C盘独立区。完整断言计数38233含原环境失败。四份原报告、各自日志和双平台构建身份已复制到D盘out/collab/f2-core-independent-r1/reports，24文件逐SHA与日志摘要核对通过；不覆盖原件。

额外反例原件已从C盘复制并逐文件SHA核对至D盘out/collab/f2-core-independent-r1/。r1三个CLI探针最初因geometry.ini相对错误目录而提前拒绝，其“通过”不签收；fixture-review.json明确保留该工具/fixture错误。改为绝对几何和宏路径后只重跑这三例，r2全部形成真实反例。r1运行中的非法取消例有效；其取消后最终摘要status=aborted、计数2/200000符合部分运行语义，保留为通过回归，不要改坏。额外8worker正例有唯一正常终态；16worker例记录了实际终态丢失。

## 必须修复（均为原清单的正确性/数据保护，不加阶段）

| 组 | file:line（首候选） | 独立证据/判定 | 最小修复与验收 |
| --- | --- | --- | --- |
| A 配置宏静默忽略 | main.cc:403附近只检查options.macroFile；792后server分支早于普通宏路径 | 确定为缺陷：r2/ini-macro的有效INI [run]/macro=绝对selected.mac（改源200MeV）仍welcome并exit0，宏未执行也未拒绝 | 以Configure后的实际context选择判断；本协议不支持预置宏时明确拒绝，不能只管CLI --macro。保留旧入口行为；增实际INI宏负例并核对不启动事件、不静默忽略 |
| B 记录目录实际边界 | main.cc:792–814字面lexically_normal/逐组件大小写比较 | 确定为缺陷：r2/relative-output-record及case-alias-record均welcome/exit0，将session.jsonl放在实际输出根内部 | 用实际绝对/规范路径及平台等价规则判断输出根和记录根；处理相对输出、Windows大小写别名和既有前缀链接，不能引入权限修复。仅修这项新路径判断，旧K1/P1已关闭不重开。正例外部目录继续可用 |
| C 非法控制请求生效 | src/Core/SessionServer.cc:472、555附近快速路径 | 确定为缺陷：r1/invalid-cancel在真实运行中发state_revision=-991且params.run_request_id=123，得到accepted，实际2/200000事件后cancelled | 快速ping/busy/cancel与主路径共用请求身份/类型/revision/去重规则；分别测错误目标类型、过期revision、错误run目标，拒绝不得停止合法run。有效当前目标取消仍及时生效；进行中原run重复请求及时返回原缓存，不延到run结束，不再执行 |
| D 记录覆盖/并发及关闭 | SessionServer.cc:274–309、1310–1314及逐轮ofstream写路径 | 确定为缺陷：extra/reuse-report两次正常会话复用同一记录目录，第一次session.jsonl SHA被第二次改变。源码另见reader和main都调用未加锁RecordFrame/RecordLine操作同一ofstream；记录/逐轮流close后未核对失败 | 新会话使用专属唯一子目录或明确拒绝已有记录，不能截断历史；把所有记录写入/关闭及失败锁存串行化，避免锁序死锁。关闭成功后才能报written；失败明确保留。增两会话递归保留旧文件哈希、运行中多ping日志可逐行解析、写入/关闭失败资格回归；不重构整个存储层 |
| E 正常多worker终态丢失 | SessionServer.cc:301–309、711后run_finished同时内嵌artifacts与完整receipt | 确定为缺陷：extra/mt16-report，16worker实际16/16完成，磁盘receipt 43752字节/117产物，但run_finished为0条，stdout只剩无归属frame_too_large，进程仍exit0。8worker同条件正例通过 | 避免重复内嵌大载荷，必要时发有身份/大小/SHA的已关闭收据文件引用，由现有证据读取服务读取；保持有界帧。正常受支持多worker必须有唯一且归属正确终态，不能裸error替换后继续宣称成功。增此真实16worker反例及小载荷正例，不扩通用通信框架 |

## 修复任务

任务ID：F2-SESSION-CORE-REPAIR-R1-20261104。只修改main.cc、src/Core/SessionServer.cc、必要的include/Core/SessionServer.hh或既有路径工具最小辅助；新测试scripts/test_session_protocol.py、scripts/test_session_cancel_mt.py（或一个仅这些反例的新后端测试并在run_m0_tests.py注册）、docs/会话协议.md、outbox/20261104-f2-session-core-repair-r1.md。必要增补先在回执解释原目标关系。不要改物理/计分/几何、旧csh/batch语义、旧测试阈值、GUI、CI或原反例。边界及记录变化后协议文档须如实对齐；取消实际在worker事件边界，不再写成主线程事件回调。

本轮不新增功能或提案；按上述真实反例最小修复，跑相关新/兼容专项和严格证据门禁，交源码/构建身份、原失败/修后成功与文件清单。不能把主审最初fixture错误当产品缺陷或删掉原记录。主审的C盘源仍冻结9f4，D盘由你单写，主审不改你的源文件。不提交Git、不推送、不切分支，完成后冻结等独审；修好返回原F2清单，后端通过即接GUI及完整重放。

你是本轮执行负责人，请有信心把这个高级科研项目做完整、清晰、美观、快速、易用。unlimited Token，不限子智能体数量，充分发挥设计和工程能力，充分实现与验证。实际平台限制以系统为准，不为消耗而重复工作。完成约定范围，范围外想法记入建议。
