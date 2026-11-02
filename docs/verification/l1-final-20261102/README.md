# L1 配置 Agent：本轮约定范围验收与交付

主审已签收本轮约定范围；产品／测试冻结 **246e4f6f1b97cc5e0651ff01262c85cf2e9c28d3**。本目录与关闭文档是随后docs/evidence交付，不改原EXE／report的BuildInfo，不宣称后续文档提交重新执行了模拟。配置解析、初始化、事件完成与物理验证仍分别报告。

## 实际自动范围与原始失败

Windows六profile共 **308用例／183347个实际入口**：static48/5031、GUI70/10131、11.3backend63/82029、11.4backend63/72536、11.3integration32/6815、11.4integration32/6805。CI十二原报告共 **662用例／228978个实际入口**。18原report、970原case log均保留原字节／SHA／HEAD；新树严格重放、匹配J2原基线及篡改摘要负例通过，见[重放收据](strict-replay.json)。

四workflow分别M0 run41415360785、Linux双版41415360846、desktop41415360995、installation41415360795。最后一项原Windows job125177769617在G4NDL数据包MD5不匹配时拒绝，原failed collection与strict整体失败均保留；一次明确授权仅重试失败Windows job后，attempt2 job125215598259/artifact13133459640成功。原Linux安装结果沿用，不称重跑Linux或首遍全过。最终为`passed_with_explicit_retry`，相关原件在非视觉ZIP内；HTTPS收据与SDK legacy MD5／实际SHA分开，MD5不是来源认证或SHA签名。

CPP源码指纹`9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a`，测试指纹`e4a95aa36b5fc262c01516a28365c6ec00374f36907dfd1b95fc6f8da2eade86`。各双版／平台真实EXE保留原构建收据；同源码不等于跨平台二进制相同。

## 新Windows及Linux代表性原生

[Windows独审](windows-native-review/README.md)：246冻结，DPR1.25／1.5，两档有限自然导航、英→中→英、当前focused-target及可容纳label/control联合矩形、只读interrupted恢复、正常关闭与owned为空。150是125%桌面×Qt1.2，不写成改动物理屏设置。宽编辑器／复选框及非焦点footer的裁剪范围照实保留，不保证全部按钮同时同屏，不代表物理多屏热插拔或全面可访问性。恢复只查询旧身份，隔离journal可追加退役终态，不恢复授权／当前资格，也不是独立网络抓包。

[Linux独审](linux-native-review/README.md)：独立TigerVNC真实X11/xcb桌面，经twm和回环noVNC实际可见与操作；**不是offscreen，不是WSLg RAIL成功**。实际1 request／1 task／0 events、无K1动作，plan operation passed、界面曾awaiting_approval；随后在300秒预算处task最终**failed／agent.task_timeout**，不写整任务成功或停在等待批准。确定性HTTP夹具提出e-/1GeV与proton目标不符，因此仅验通道／权限／预览，不代表自然语言语义、实际本地权重或物理正确。

Linux host及原launcher正常退出，slot_released=true，host与display两组remaining_owned均空；HTTP线程停止、listener关闭。显示辅助退出码**[0,1,0]**，twm exit1保留，不冒全子进程exit0；回环服务清理已核。原fc-list受限探测首败、xcb-cursor缺库、WSLg RAIL显示／焦点与QA草稿变化、旧observer未启动、首次Xvnc启动失败均按原身份保留，不用新通道成功改绿旧失败，不认定唯一网络／图形根因。

[Linux依赖边界](linux-dependencies/README.md)：Ubuntu实际系统安装x11-xkb-utils7.7+8build2、dpkg exit0；其余本次libxcb-cursor0、TigerVNC/twm等依赖OUT隔离。早期preparation的system_installs=0只属于当时，后续真实系统安装收据单列。未发布.deb、安装树或服务器二进制。

## 既有EE任务、人工对照与恢复

EE→246仅panel、其smoke及八docs变化，157GUI其余156与五Agent核心／adapter保持，精确映射原收据在ZIP中。真实五域Task03、NL诊断02、人工单对、受控恢复及production closed-load均保留EE原HEAD／EXE／脚本，不冒新246模型调用、窗口或运行。五域三attempt／两失败一成功、NL01零请求夹具失败、恢复01失败与旧EE150布局失败全部保留。

人工操作臂／Agent臂只有**一对Codex操作者案例**。原actions行64／48，measured行57／38；measured首尾跨度1003.298／1015.809秒，全日志跨度1088.615／1234.068秒。包括工具周转、探查、观察等待、修正与不对称setup；行数不是工具／物理输入总数，不能推导用户提速、受试者成功率或统计优势。两臂各4事件、资源SHA一致；wire请求总数／token未独立取证，不借Task03补填。

恢复02只覆盖固定HTTP夹具下“K1 terminal已发布、Agent result尚未落盘”单受控点73→0，query-only、不重发、不增加events或恢复当前资格；正常close退役与新backend失败分开。production closed-load确实调用原reader/codec，且无Application／事件循环，不是CLI replay或又一原生窗口。NL诊断02真实一次请求1295tokens/8ops/4events，expected/captured仅derived errors不同、生产语义指纹相同，Undo回完整S_invalid；不扩大通用NL可靠性。

## 精选归档、隐私与复验

[非视觉交付索引](release-index.json)：主[ZIP](nonvisual-evidence.zip)1284原件，另[bootstrap成功收据小增量](bootstrap-fetch-increment.zip)1原件，共1285原件／7409082 raw bytes。主[manifest](manifest.json)逐项原路径／SHA／bytes，另64项reference-only。ZIP不是完整运行环境或全部历史raw自含包；SDK/数据/大CSV与重复展开工作树不发布。

J2的18matching baseline引用已提交稳定公开树／对象及原SHA，不复制J2整套；原EE完整绿色轮次不重复归档。`verify.py`从本目录原ZIP解出18份报告和对应日志，以冻结246 checker及稳定公开J2原成员重放，无原OUT绝对路径回退：

```text
python docs/verification/l1-final-20261102/verify.py --repo-root .
python docs/verification/l1-final-20261102/verify_scope.py
```

所有原图、含QQ原图及原UIA永久local-only。Windows122项、Linux16项资产仅scope/path/size_bytes/sha256/mime五字段；公开原图／UIA载荷均0。不会通过crop、上传、AI重绘或派生图替代原证据。云prompt/reply、journal、完整capture、凭据、QSettings、EXE/SDK/数据集/巨大CSV不采入；review是明确白名单投影。内容扫描是辅助，不冒秘密不存在的证明。

精确公共文件清单见`public-files.manifest.json`（自身唯一排除），范围索引／字节与Git属性证明分别单列。根已有`docs/verification/** -text`，不新增属性豁免。文档／证据提交只做受控链接、字节及严格重放和docs-only身份验证，不为纯文档再模拟。不扩后端科学支持、任意对象／字段、本地权重质量、F2热会话、K2完整工程或L2代码工作流；下一阶段按ROADMAP推进。
