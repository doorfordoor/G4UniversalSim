# G4UniversalSim 状态（唯一入口页）

**接手后先读**　[各阶段详细执行指南](docs/collab/decisions/20261102-stage-execution-guide.md)。近期按 F2 受控运行会话与 DeepSeek 的 [J3 现有界面视觉改造与新增皮肤](docs/collab/decisions/20261102-j3-desktop-skins.md) 分线推进。

**D 盘接手入口**　[后续执行计划与 DeepSeek 开工指令](docs/collab/inbox/20261102-2045-astra-d-workspace-execution.md)。下一完整阶段为 F2，字体与主题的实窗补验可并行。

2026-11-02 D 盘桌面修订已同步。字体、数字显示与主题切换修复见[测量与进度](docs/verification/gui-theme-response-20261102/README.md)。

## 2026-11-02 J3 第三阶段：工作区面板与外壳细节（作者交付，未验收）

在[第二阶段](docs/verification/j3-shell-20261102/README.md)基础上只改布局与外壳细节，未动后端与调色板：
3D 视图面板视点/投影控件拆两行网格、材料/粒子图例 190→168、剖切滑块最小宽 110→80，右侧 dock 变窄时
“World / Show Labels / Load Tracks…” 不再被窗口右缘裁掉；3D 预览选项分行；配置 setup 面板最小宽 260→300、
分栏 330/650（“Browse” 可见）；配置标签 padding 7/11 让六个标签不压滚动按钮；状态栏恢复提示单行化（max 320）；
`QToolButton:focus` 用 `focus_ring`、侧栏导航 focus 用 `sidebar_hover`；撤消/重做改用主题色 SVG 图标，
工具栏创建后由 shell 补刷一次。

验证：`--profile gui` **72 pass / 0 fail / 0 skip、10227 断言**，报告
`out/verification/j3-panels-gui2/20261102-225535-090e83e1/report.json`（副本与 72 个日志见
`docs/verification/j3-panels-20261102/`），门禁通过；源码指纹 `9e40e889d49a4425…`、测试内容指纹 `e8c6272783613a79…`。
证据另含 B/纸墨/午夜蓝实窗截图与阶段 2 对照图。**未做**：对比度数值复测、125%/150%、Linux 真实桌面、
独立审查——J3 仍未关闭。

## 2026-11-02 J3 第一阶段：设计系统与皮肤注册表（作者交付，未验收）

J3 已由 DeepSeek 在 D 盘 `roadmap/gui-theme-response` 分支开工，本段只记录**第一步已落地的事实**，不签收 J3。
外观基础设施：`gui/g4usim_gui/core/theme.py` 重写为 28 个颜色角色 + **15 套皮肤**（历史 B/K/C + 纸墨、砂岩、苔原、石墨、霜蓝、
高对比、午夜蓝、电路夜班、板岩、余烬、极光、夜视对比），皮肤带浅/深分组、图表序列与可翻译名称；注册表构建时把
`text_muted`/`border_strong`/`accent_soft`/`selection`/`sidebar_selected`/`focus_ring` 归一化到正文 4.5:1、边界与焦点 3:1 的下限；
样式表拆成“历史基座 + 新视觉层”（旧选择器逐字保留）；`View → Appearance` 按明暗分组列出全部皮肤并分别记住两组选择，
`appearance/light_skin`、`appearance/dark_skin` 为新增键，旧 `appearance/light_palette` 继续作为 B/K 镜像写入；`app.py` 启动恢复记忆。
新增 static 用例 `theme_registry`（113 断言点，含 15/15 皮肤 × 23 项对比度、迁移与 `apply_theme` 契约），用例总数 215。
实测：static profile **49/49、5,615 断言**；主题相关 GUI 用例 **4/4、284 断言**；完整 GUI profile **71/71、10,187 断言**（`gui-profile/` 一并归档）。本阶段未改后端，backend/integration 未重跑。
证据（含 B/K/C 改动前后同工程截图与归档报告）见[第一阶段证据](docs/verification/j3-theme-v1-20261102/README.md)。
**未完成**：区域层级实窗改造、对比度实测表、125%/150% 与 Linux 桌面检查、切换性能基线、独立复验；J3 关闭前不能引用本段作为验收。

## 2026-11-02 J3 第二阶段：外壳层级、命令面板与外观状态（作者交付，未验收）

在[第一阶段](docs/verification/j3-theme-v1-20261102/README.md)基础上，本段记录第二阶段的落地事实，仍不签收 J3：
侧栏改为 `WORKFLOW`/`RUN & ANALYZE` 两组并给选中项加强调轨道；页头改为“面包屑 + 页标题 + 说明 + 项目/运行 chip + 外观/语言按钮”；
新增 **Ctrl+K 命令面板**（`gui/g4usim_gui/widgets/command_palette.py`，按 Pages/Actions/Appearances 分组，标签严格匹配优先、
Up/Down 跳过组标题、Enter 运行、Esc 关闭，选择外观激活所属明暗组）；状态栏常驻 `Appearance: <皮肤名>`（tooltip 带描述）；
菜单栏、编辑历史工具条与状态栏统一为皮肤浅表面与细分隔线。
新增 Qt 用例 `gui_command_palette`（40 断言），完整 GUI profile **72/72、10227 断言**通过，
证据（含 B/C/纸墨/午夜蓝 三页截图与命令面板截图）见[第二阶段证据](docs/verification/j3-shell-20261102/README.md)。
**未完成**：区域层级实窗改造、对比度实测表、125%/150% 与 Linux 桌面检查、切换性能基线、独立复验；J3 关闭前不能引用本段作为验收。

Linux原生通道补充（主审已签收）：main已实际操作独立真实X11/xcb桌面，一次固定HTTP计划passed，操作观察时曾停在awaiting_approval、0事件；随后在观察期间触及300秒预算，整任务保留failed／agent.task_timeout，不称整任务成功。原host exit0、slot_released=true、host与显示服务两组remaining_owned均空、HTTP已关闭；显示辅助子进程退出码[0,1,0]（twm非零保留），不能写全部子进程exit0；代表性原生签收结果为 **独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。WSLg RAIL任务栏无法展开，第三次host退出且0请求，原失败保留，绝不称该通道成功。Ubuntu实际系统安装x11-xkb-utils，其它本次依赖保持隔离OUT前缀；具体包版本／SHA及安装收据见最终证据，不把早期准备收据system_installs=0外推到之后。

## 2026-11-02 L1 本轮验收与最终证据

本轮阶段签收：**本轮约定范围验收完成**。产品／测试冻结 `246e4f6f1b97cc5e0651ff01262c85cf2e9c28d3`；后续仅 docs/evidence，不伪改原 EXE／report 的 BuildInfo 或提交。Windows 六 profile **308 次用例／183347 个实际入口**；CI 十二原报告 **662 次用例／228978 个实际入口**，各原报告／日志身份、非零断言及匹配 J2 基线均经严格重放。 CI 保留一次显式重试：M0 `41415360785`、Linux 双版 `41415360846`、desktop `41415360995` 均 attempt1；installation `41415360795` 的原 Windows job `125177769617` 在数据集上游 MD5 校验时拒绝，授权仅重试 Windows 后 attempt2 job `125215598259` 成功。原 Linux 安装成功结果沿用，原失败 collection／strict 总状态不改绿；最终以 `passed_with_explicit_retry` 聚合，不称首次全过。

新 246 Windows 125%／150% 仅按受限原生范围计证：AI dock 的自然显示、F6／Tab 当前焦点与可容纳标签＋控件联合范围、只读恢复代表及正常关闭。两档 host 实际 exit0；不承诺所有非焦点 footer 同时同屏，不声称物理多屏热插拔或全面可访问性。旧 EE native150 的 52px 不可读布局失败按原身份保留。 Linux独立X11/xcb代表性原生：**独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。最终范围与原件身份以[最终证据](docs/verification/l1-final-20261102/README.md)为准。

EE→246 的全树精确映射仅 panel、其 smoke 与八文档变化；157 GUI 源中其余156及 Agent 五核心／adapter 未变。真实云五域 Task03、NL 诊断修复02、人工对照及受控恢复／production closed-load 均保留 EE 原 HEAD／EXE／脚本与各自范围，不改签新 246 模型请求、窗口或运行。 人工操作臂与 Agent 臂仅一对 Codex 操作者案例：原 actions 记录 64／48 行，其中 measured 57／38 行；measured 首尾跨度 1003.298／1015.809 秒，全日志跨度 1088.615／1234.068 秒。包含工具周转、观察等待、修正与不对称 setup，记录行不等于工具或物理输入总数；不推导提速、受试者成功率或统计优势。两臂各完成4事件、资源输入一致，模型 wire 总请求／token 未独立采样，不能借 Task03 的用量补填。

固定既有对象／字段白名单、默认只规划、审阅后新授权同 plan 建新 task、旧授权留史及恢复仅旧 ID 只读查询不重发保持。默认 evaluate 仅运行完成性；本地仅 OpenAI-compatible HTTP 协议，未测本地权重质量，不执行模型代码，不扩科学验证、任意新目标或 L2 持久代码工作流。 下方“实施中”、EE快照及失败按各原时点保留，不能覆盖本段的新事实，也不能把历史失败删除。F2 在本轮主审签收后按原依赖推进，L2／K2另阶段。


更新：2026-11-02。本页只做导航与快照；**阶段状态以 [docs/ROADMAP.md](docs/ROADMAP.md) 为准，支持等级以 [docs/功能支持矩阵.md](docs/功能支持矩阵.md) 为准**，两者冲突时先改事实再改文档。

## 2026-11-02 L1 配置 Agent 实施中

按 Roadmap 下一工作项完整启动 L1。当前以 `4840e62e` 为接续基线，工作分支 `roadmap/L1-config-agent`。云端／本地兼容接口、系统凭据与会话凭据、受控配置差异、有界任务及恢复接口正在实现和独审；复用 K1 服务、F5 事务及既有运行器。完整矩阵、真实模型任务集、原生观察和最终交付仍待验收，当前不宣布 L1 完成。见[开工契约](docs/collab/inbox/20261102-l1-execution.md)与[L1 说明](docs/L1配置Agent.md)。F2 热会话和 L2 代码执行保持后续工作项。

首候选 D1 `d1bd57da5a7e61d07fdff6cadc2a1f5f3dadc359` 的实际 Windows 终态为 static 48/5031、GUI 70/9781、11.3 backend 63/82029、11.4 backend 63/72536，合计 **244 次执行／169377 个实际入口**；四份原 launch 的 runner/gate 均为0、identity_errors=[]。两个 integration 未执行，不算完整六 profile；原报告保留 D1 身份，不迁移到后续修复候选。

D1 五域真实云任务 Task01 的 plan/apply/fields/initialization/generate/run/evaluate 七步均 passed，run 完成4事件，但完整捕获只在 `/state/drafts/project.threads.raw` 出现 `2`→`〢`（U+3022）的重格式差异；后续 flush 推进 revision 并使 K1 记录陈旧，任务级收据仍为 **failed**，不把中间运行成功当完整任务通过，原件不改。当前修复 v3 除 `ProjectPage.show_generated_paths` 与实际 K1 display binder 外，还补足路径原文捕获：此前受控显示探针发现旧 transactions 把未改显示值还原为 typed 原路径，丢失原路径草稿空白，出现两处 raw diff、指纹不等；现 K1 binder 将原快照 path raw 保存为内部 view tuple 第三值，capture_workspace 兼容旧二元组，并仅对仍等于生成显示值的路径按原 raw 还原，非路径 raw 继续保留。最终为 ProjectPage／window/experiment／window/transactions 三产品＋两测试五文件；正常载入与 legacy 全量 `set_project`、window/run.py 的 D1 base 均不改，privacy／codec／locale／同指纹和资格门禁不放宽。

此前 K1 display binder 窄修专项通过仍保留原范围；本次 v3 作者 Qt56 开发入口通过，旧54／25保持旧身份，不改记为 v3 后端或正式重跑。早期绝对休眠路径及设置次序的夹具失败保留原日志／源码，r4仅修夹具后56，不记为新产品失败。产品 v3 raw-path delta 独审已 PASS（限定接口／显示／F5 资格，不冒充 backend／formal），新候选身份／重新构建／全部 formal／真实 CI／原生观察及人工对照仍待。详细增量见[L1进度](docs/L1配置Agent.md)及[候选历史](docs/agent-history.md#2026-11-02-l1-路径显示-raw-修复候选)，本页不预写未来 HEAD、通过结论或阶段完成。

### EE证据增量与下一布局候选（阶段未关闭）

正式身份仍为 `ee6f40ded197a59c0b63726b92a09560831867ca`（EE）。本机四份原 Windows 报告终态为 static48/5031、GUI70/9795、11.3 backend63/82029、11.4 backend63/72536，合计 **244次执行／169391个实际入口**；四原 launch 均 runner/gate0、identity_errors=[]，对应 report 的 git_dirty=false。EE 两个 Windows integration 未执行，不以真实专项或 CI integration 补记本机六 profile 通过。EE 真实 CI 四 workflow 均终态成功，12份 profile 原报告 strict/matching baseline 通过，合计662次执行／227634个实际入口；Desktop／安装的独立结果不再算进该数。原证据根为 `out/verification/l1-ee6f40d/`，不迁移到下一候选身份。

Task03 五域真实云链和应用恢复02分别已收 Ptolemy 限定文件独审 PASS：前者是一次真实模型规划、程序化审阅、真实 K1 run4/export/Undo 链，不是原生／人工时间或科学验证；后者仅固定 HTTP 夹具下“K1 terminal 已发布、Agent result 未落盘”的单一受控崩溃点，实际73→0，恢复只查询旧身份且不重发，历史结果陈旧、当前资格不恢复，不扩大为任意中断恢复。两者原失败／脚本及独审身份保留。

native125 的人工操作臂／Agent臂单对描述性比较、原保存与导出文件链，以及另行授权的生产 closed-load 模型 IO 已分别有限通过；closed-load收据1beea485仅允许QtCore import、无QCoreApplication／QApplication实例，不冒第二次实窗或CLI回放；不是受试者成功率／提速结论，文件审不冒像素或第二次原生观察。原EE native150虽正常退出，仍发现52px下L1 AI全控件不可读的布局P2；该次原生失败按原身份保留，不改记原生总体通过。此为L1新缺陷，不套用旧F6按钮82>56的历史窄边界或改写其原结论。真实 NL 诊断修复02已由 main 单次运行，外层原13956／child63728均实际exit0、owned0，作者receipt为1request／8ops／4events／export／Undo passed；其实际链路纯文件独审已限定 PASS：一次真实回复共1295tokens，initial→capture恰5叶差异（4个energy同步表示及派生errors清空），其它raw保持；Undo完整JSON回S_invalid已核。expected/captured只差旧sourceEditor.errors清空，原生产语义指纹相同，不称全JSON相同。该审不代表native／科学／通用NL可靠性或生产load／CLI回放。原01为driver注入夹具失败、0modelcalls，v1/01原件保留，不被02成功替换。

Harvey 的52px布局后续候选已仅在OUT冻结：产品SHA为 `05e4ec9077bbd0d8e08f8381a63b5ada86e3ad8566d436d6b04fae484a3038ae`，仅动态两列可读最小宽度提示及固定footer inset／reflow；测试SHA为 `6f06b0277c10b5ff27a21691a2b7c63f2a2f5d3124602b18a2f1af7cabd748e9`，保留原函数AST（main仅增新调用），新增真实MainWindow自然show的QAction／F6／Tab回归。候选注入后的125%／150%完整组件入口各1216、实际exit0；同一新回归在原产品52px负向实际exit1。workspace layout／core accessibility、Controller／F5／K1和翻译不改。上述作者专项与Ptolemy候选限定独审PASS分别计证；独审按当前focused-target及可容纳标签／控件joint合同关闭原52px P2，无其它确认P1/P2，不冒新candidate正式矩阵或新native通过。retained语言补验仅125%，英→中→英每轮9Tab的当前焦点完整可见、可容纳joint通过，非焦点右列仍可裁剪，不保证全footer同时同屏，新native仍待。main已精确apply已审panel／test两path，实际tracked两档各exit0／1233，另按原收据保留wrapper计数假设失败及更正，不与作者各1216混计；新提交身份、新构建、完整Windows六profile、真实CI和对应原生补验均待，不预填future HEAD或继承EE资格。当前不关闭 L1，F2／L2 顺序及既有白名单、raw／同指纹、授权／预算／只读恢复合同不变。 详见[同名候选历史](docs/agent-history.md#2026-11-02-l1-ee验收快照与原生布局后续候选)。

## 2026-11-02 J2/F8及E7本轮验收

**本轮约定功能验收已完成。** main已接受J2、F8和支撑J2的E7既有15原语／7布尔工具注册与元数据范围。正式构建／测试冻结为 `2ec5b14fc823ad837dce3ea6f5d7c5ae3f66a3c8`；后续包含本页的提交仅为docs/evidence，不改原report／EXE身份，不因文档提交重建或重跑矩阵。交付以实际Git树、三份精确锁及main后置字节映射为准，不自填未来commit SHA。见[最终证据](docs/verification/j2-f8-final-20261102/README.md)、[功能支持矩阵](docs/功能支持矩阵.md)与[J2/F8说明](docs/J2编辑覆盖与F8验收.md)。

| 2ec本机profile | 通过/执行 | v3实际入口 | runner / strict / launch identity_errors |
|---|---:|---:|---|
| windows-static | 46/46 | 4586 | 0 / 0 / [] |
| windows-gui | 66/66 | 8636 | 0 / 0 / [] |
| windows113-backend | 63/63 | 82029 | 0 / 0 / [] |
| windows114-backend | 63/63 | 72536 | 0 / 0 / [] |
| windows113-integration | 31/31 | 6790 | 0 / 0 / [] |
| windows114-integration | 31/31 | 6780 | 0 / 0 / [] |

六份原launch的identity_errors=[]，对应report均git_dirty=false；合计300/300、181357入口，aggregate passed/errors=[]，SHA `a701f34fc2d3e9bd2d0aec9fc833d249179fc76ad5de873f8c42011e665ec73c`。真实CI四workflow／八job均原attempt1 success：M0 `41352200756`、Linux双Geant4 `41352200765`、Desktop `41352200727`、Installation `41352200731`。12份报告strict全部通过、零skip、逐例及总数matching基线不下降，共636次case执行／221186入口；Desktop/Install不另伪加到636。

CI状态不概括为全局clean：四份M0报告clean；Linux双版本八份原报告git_dirty=true，原status仅对应`.g4env-11.3.2/`或`.g4env-11.4.3/`、`.micromamba/`、`bin/`三行环境目录。tracked_source_gate=pass、untracked_source_files=[]，source/tests/merge与2ec精确匹配。原JSON、原checker和旧56b/2901/18c失败均保留，不改绿、不泛放其它dirty。

E7只关闭本轮15/7统一factory注册、能力元数据和GUI离线定义接线；兼容、缓存／生命周期及适用矩阵通过。实体集合和A5实验性等级不变，不新增assembly、每体积GDML、任意worker构造、全GeometryConfig重写或科学支持结论。

18c三档原生按149GUI/C++与精确7文件允许差异的实际byte-map沿用原HEAD/EXE/限定scope，不冒充2ec全三档重跑。2ec代表性125%另已实际补验I1发现/I2首屏打开关闭、Import旧包及保存、模板Finish/另存、重入Next/Back/Esc并正常退出；main24观察/41JPEG，Ptolemy纯文件独审通过，Harvey合同余项清单无新增必跑操作。文件审不是第二次像素审查。Import的4条旧历史均stale，当前仅import_history；无本轮validate/generate/run新record。自动几何预览可以调用后端构造，但不是事件Run；缓存project/Undo不是live F5。

197张标记local-only原图（70继承QQ、86旧18c、41新2ec）仅保本机，公开只path/size/SHA和观察边界。18c100%的初始化no_run、事件run100/100与导出未CLI replay分别保留；F6极窄dock容不下joint的界限、QQ遮挡、未做物理跨屏/热插拔及科学基准均不扩大。H2/H7/Q2不随本次关闭。下方各候选是当时身份的历史快照，原文不追改。

<details>
<summary>第四及更早候选历史快照（原文保留）</summary>

## 2026-11-02 第四修复候选：18c5858证据快照

**第四修复候选，两项test-only专项独审已完成；阶段仍未关闭，完整新候选验收待进行。** 第三冻结为 `18c5858fd6e80a5cb6096beacebfef69c479ad49`。本段只登记该身份的Windows、真实CI和原生范围；第四候选针对两个测试平台断言修订，不预写尚不存在的新HEAD、新CI成功或新增运行事实。

| 18c5858本机profile | 通过/用例 | v3入口 | runner / strict / identity_errors |
| --- | ---: | ---: | --- |
| windows-static | 46/46 | 4586 | 0 / 0 / [] |
| windows-gui | 66/66 | 8574 | 0 / 0 / [] |
| windows113-backend | 63/63 | 82029 | 0 / 0 / [] |
| windows114-backend | 63/63 | 72536 | 0 / 0 / [] |
| windows113-integration | 31/31 | 6790 | 0 / 0 / [] |
| windows114-integration | 31/31 | 6780 | 0 / 0 / [] |

18c六profile均已终态passed，合计300/300、181295入口；local-final-audit的status=passed、errors=[]，六份原report/launch SHA及逐项算术已核对。六份launch的identity_errors=[]，对应report均git_dirty=false；这些是18c冻结的本机结果，不替代第四候选新CI或阶段验收。证据根文字为 `out/verification/j2-f8-18c5858/`，不把未归档OUT作为公共链接。

18c5858四项push/attempt1 CI均终态：Linux Geant4 `41344573528` 与M0 `41344573541`失败，Desktop `41344573534`与Full installation `41344573604`成功；八份profile报告strict4pass/4fail，release_accepted=false。Linux114、113及M0 Ubuntu各仅gui_f8_accessibility在659行QAccessible.Name断言失败；Windows M0另仅gui_j2_geometry在264行成功reload后的source_path字面相等断言失败（195入口），不是上一轮STL162。Linuxbackend/integration因上游GUI失败未执行，不能记为通过。首败、全部原log/ZIP及旧身份保持，专项归因或入口数增加不把原CI改绿。

两项修订只针对真实接口：成功Reload保存resolve后的规范来源锚点，用精确resolve、samefile及内容SHA验证；失败Reload保留此前原字面锚点与非法草稿的判据不删。真实8.3短路径原195fail、候选长/短各214pass提供本机反例，但原CI没打印路径，不能声称已经看见其具体TEMP拼写。Qt6.11.1/6.11.3官方Combo实现的Unix分支解释了本轮Linux Name/currentText行为，Windows Name仍为标签；语义标签由实际Label关系表达，空文本依Qt回退。测试在本次Windows/Linux目标上严格核对角色、真实interface.object、Name/Value、确切Label/buddy及动态语言；丢buddy、同文异label、错误control接口三类负向在两端各9次均须拒绝，不推广为macOS/所有Unix验收。两项test-only专项独审均PASS；Linux作者完整655绿例与独立微Qt检查分开，不为测试改正确产品。

18c三档原生host/application均正常exit0，main实际观察排除QQ像素。150%为760×640下九页快捷键/F6、保留config+preview后Project完整name/Tab EXE、History三名称英/中/英与Search→Status、模板到Run/Back/取消及深色Project；125%为1200×800下F6/retained Project/Tab及History三名称/语言切换，没有扩写成九页或向导全流程。100%为实际新建blank、生产Save/Open、fields、初始化no_run/0事件、generate、run100/100、export及结果身份关联；导出manifest+7成员闭合、outputs_included=false/replay_verified=false，未执行CLI replay，零沉积world不代表物理响应基准。150/125 Harvey与100 Ptolemy均为纯文件审，不替代独立视觉复验或额外运行。

本轮全部86张原生原图仅本地保留，公开仅SHA/大小/观察文字，不把QQ原图带入Git。现有18c149项GUI逐文件映射及三档原identity已核对，C++源码指纹仍按18c冻结报告记录；这只是原身份的相同产品字节证据。两test与本文档提交得到新HEAD后，最终产品/C++身份映射仍为pending，完成后才能按原限定scope映射，不虚构新增操作或重复三档；**新候选完整真实CI仍必须**。第四候选GUI终态后还计划补一轮100%或125%代表性native，覆盖I1/I2打开取消、Import已有offline包、template Finish后再次重入Back/Esc；该项为pending，按届时新HEAD/build独立记录，不提前算作旧三档覆盖，也不作为本文档冻结前置。F6无法容纳完整joint的窄dock边界不在本修复内，不扩大物理/跨屏/热插拔结论。

下方“第三修复候选”实施快照保留原字节，仅作为当时2901f42等历史身份记录，不代表本段的新候选结论。

<details>
<summary>第三修复候选历史快照（原文保留）</summary>

## 2026-11-02 J2/F8 当前实施

**第三修复候选，相关专项独审已完成，完整新候选验收待进行；阶段未关闭。** 工作区 effective-config、分支 roadmap/J2-F8-editing；首轮冻结为 `56b689f`，第二冻结为 `2901f42`。本候选包含下述已审修复，仍须以新提交身份完成完整复验，不能把专项或本机通过改写成整阶段验收。当前约定见[开工契约](docs/collab/inbox/20261101-j2-f8-execution.md)和[J2/F8说明](docs/J2编辑覆盖与F8验收.md)。

`2901f42` 的 C++ 源码指纹仍为 `9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a`。截至本次文档候选快照，以下本机正式报告已通过 runner 和 matching 历史 strict 门禁，identity_errors 为空、report git_dirty=false；未用内部SKIP代替完整PyVista路径。

| 本机 profile | 通过/用例 | v3入口 | runner / strict / identity_errors |
| --- | ---: | ---: | --- |
| windows-static | 46/46 | 4545 | 0 / 0 / [] |
| windows-gui | 66/66 | 8394 | 0 / 0 / [] |
| windows113-backend | 63/63 | 81988 | 0 / 0 / [] |
| windows114-backend | 63/63 | 72495 | 0 / 0 / [] |
| windows113-integration | 31/31 | 6790 | 0 / 0 / [] |
| windows114-integration | 31/31 | 6780 | 0 / 0 / [] |

本快照六份本机profile均已终态passed，合计300/300、180992入口；local-final-audit的errors=[]。这些是2901f42本机结果，不替代第三修复候选完整验收。证据根文字登记为 `out/verification/j2-f8-2901f42/`；最终归档入库后另补稳定链接，当前不以未归档out作为公共证据链接。

第二候选四个真实push CI（均attempt1）已终态：Linux Geant4 `41336912644` 与 M0 `41336912651` **失败**，Desktop `41336912646` 与 Full installation `41336912645` 双平台成功。Linux GUI暴露QSpacerItem被当成layout递归的问题；Windows M0 GUI保留K1 policy别名身份拒绝及geometry文件路径断言首败。整体release_accepted=false；未运行的下游profile不记通过，安装/桌面成功不替代功能CI。

第二候选原生有效DPR 1.0/1.25/1.5的host均exit0，三档149项GUI SHA与2901f42冻结源码相符、使用完整D盘venv。main逐条观图，QQ覆盖像素排除；125%向导经自然拖动后另留完整无遮挡dialog观察。100%实际保存/重载blank-native.json、完成生成/初始化/100事件/导出，初始化no_run与100/100事件分开；7成员offline-native资源SHA匹配，历史仍stale、未执行离线replay。150%Project retained问题在相应视觉范围已消失，但F6窄dock边界与History名称/标签遗漏保持开放，**不升overall native pass**。后续三档对新repair范围仍需补验；物理跨屏/热插拔与物理正确性不由这些观察推出。

第三修复候选包含History三显式buddy及动态语言名称、仅真实QLayout的递归兼容、geometry路径测试精确resolve/samefile比较（不改geometry产品）；History、spacer及STL专项独审均通过，History+spacer组合595专项亦已独审，尚不替代新candidate的CI/原生。F6窄dock界限不修改，不声称不可容纳的整组标签/控件可以同时放入窄视口。K1 final-v1 policy规范身份及原拼写首尾guard专项独审已通过603入口／13组，原短路径30入口及junction 3+5反例保留；**完整新候选验收待进行**，专项关闭不等于CI或阶段关闭。

首轮 `56b689f` 六份本机报告300次执行、286通过/14失败/0跳过、179468入口及严格失败保持原件；GUI自身git_dirty=true/73条长路径表象不追改。原M0 `41330577407`、Linux `41330577426` 失败，安装 `41330577328`、桌面 `41330577359` 成功；本轮新结果不替换原run或旧失败。源码、构建、报告、截图及独审各按原身份保留。完整新候选矩阵/native/CI全部终态并经独审后才考虑阶段关闭；当前归档只是OUT候选，不是最终公开发布。

</details>

</details>

## 一句话定位

2026-10-31：K1 可信实验工作流与配置导出已完成阶段验收，I1 已独立完成。第七产品冻结 `2914b39` 的 Windows 182/182、57181 个 v3 入口及官方 CI 548/548、133720 个入口保持原身份；资源路径 P1 已通过独审，`5644e1e` 永久回归补充在 Windows/Linux 分别 36/33 个入口通过严格门禁。产品字节未变，未新增物理或性能基准；已正常快进集成并推送至 `codex`。详见[验收证据](docs/verification/k1-final-20261031/README.md)及[ROADMAP](docs/ROADMAP.md)。

当前工作：2026-11-01 **I2 辅助安装与双平台交付、J1 可调整工作区已完成阶段验收**。安装计划、受校验获取、发布/取消/恢复/卸载及 runtime/SDK 流程通过 Windows/Linux 实际验证；停靠布局、主题及 3D 颜色/透明度控制通过组件、冻结桌面与 Windows 实窗验收，DeepSeek 已实际参与前端设计。最终测试提交 `6310969` 仅修三个测试，产品文件与 `5fe0a10` 相同；旧失败和未归因的历史偶发失败保留。详见[最终证据与边界](docs/verification/i2-j1-final-20261101/README.md)。下一阶段为 J2/F8，空白创建、多源/物理组合等反馈按既定排期推进，AI 仍未接入。 验收提交`c3276e3`已正常快进并推送至`codex`，见[实际集成收据](docs/verification/i2-j1-close-20261101/README.md)。

配置驱动、可复现、可验证的 Geant4 桌面工作台（C++17 后端 + PySide6 前端 + 场景包/基准/测试平台）。
当前是"有真实物理验证的 Beta"，不是 1.0：核心链路可用，大量高级能力仍是实验性，产品完成度低于工程纪律。

## 当前计划入口（2026-10-29 编号整理）

统一工作项、排期波次、依赖、Q1 审查范围与提交节点均在 [ROADMAP](docs/ROADMAP.md) 的“统一代号与排期”一节。本对话作为 **Q1 完整可靠性审查、修复与验收**的主负责人；隔壁审查作为独立证据来源，不必等它全部结束。已有反例按代码基线复用；Q1 已在冻结范围完成验收，见[最终报告](docs/verification/q1-final-20261029/README.md)。

当前顺序：Q1（已完成）→ 2C（已完成）→ E6（已完成）→ F1（已完成）→ F4（已完成）→ F5（已完成）→ K1（已完成，I1 已完成）→ I2/J1（已完成）→ J2/F8 → L1/F2；J2 中实际依赖实体元数据的部分先满足 E7。其后科研波次 Q2/H2/H3、F3/F7，与 K2/L2 按依赖安排；H4–H9 和 M5 保留后续独立阶段。这是导航摘要，具体状态与默认顺序以 ROADMAP 为准。用户一次启动一个完整代号，阶段内的提交和专项测试由负责人连续推进。

2026-10-29 Q1已完成：九域审查、R01–R32闭合并交叉复核；验收代码 `8ecad66`。干净Windows **105 PASS / 0 FAIL / 0 SKIP**，83770个v3入口；旧同代98项基线79303，逐例/总数与原始日志门禁通过。Linux11.3.2/11.4.3真实CI各105（run40855144863），Windows/Ubuntu static+GUI各42（run40855144672），Windows实窗保存/生成/运行/取消/关窗通过。[完整收据](docs/verification/q1-final-20261029/README.md)；旧失败证据保留，历史偏置结果须重跑，原生交互迁移显式csh。

## 2026-10-31 F5 当前验收

关闭提交71b52e7已正常快进至codex并与阶段分支一同推送，[集成收据](docs/verification/f5-close-20261031/README.md)。

2026-10-31 F5：**已完成**。冻结验收5c1eec5；Windows160/160、50898个v3入口，Linux11.3.2/11.4.3各160、M0两平台各79，原F4逐例与总量门禁通过。原生22份观察/28截图/真实退出0保持5d身份，经明确映射关联新冻结；不新增物理验证结论。[最终证据](docs/verification/f5-final-20261031/README.md)。下方带日期的旧状态保留其历史范围。

后续按[模型分配规则](docs/collab/MODEL-POLICY.md)执行；J1负责视觉/布局/主题，主题后整理易懂文案，F8做跨页验收。

[新对话交接](docs/collab/20261031-f5-handoff.md)。

## 2026-10-30 F5 历史启动记录（当时尚未验收）

用户启动完整 F5。基线 `676ffb2`，实施约定 `75b1a19`，当前隔离分支 `roadmap/F5-transactions-recovery`；范围与验收见[实施约定](docs/collab/inbox/20261030-2155-astra-f5-execution.md)，实际前端设计回信见[DeepSeek 建议](docs/collab/outbox/20261030-2155-deepseek-f5-design.md)。现有 v6 未持久保存材料草稿，需要统一完整编辑快照、事务、普通保存和自动恢复；实现与新证据完成前不视为 F5 已交付。

## 2026-10-30 F4 阶段关闭记录（已完成）

2026-10-30 集成补记：关闭提交`20f8562`已正常快进到codex并推送，原D检出保持独立；[实际收据](docs/verification/f4-close-20261030/integration.json)。下文“记录形成时尚待快进”保留其生成时间点，当前F4已关闭，F5未启动。

产品 `7d718d038a00d89995ea773b4772764116b620c3`；Windows 152/152、49913 个 v3 入口与 F1 原始143/48511同代基线门禁；Linux11.3.2 为 152 项、11.4.3 为 152 项（run 41056994075），M0 Windows 为 72 项、Ubuntu 为 72 项（run 41056993987）。CI实际提交 `a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9`，与产品的关系见[提交身份映射](docs/verification/f4-final-20261030/identity/identity-map.json)。Windows原生 13 态、19 次实际观察与进程退出 0；[最终证据](docs/verification/f4-final-20261030/README.md)，[独立审查](docs/collab/reviews/20261030-astra-f4-close-review.md)。

实窗GUI提交 `7d718d038a00d89995ea773b4772764116b620c3`，与产品身份关系：实窗GUI与Windows后端均为产品7d718d0，121份GUI源文件清单经独立复核。13个合成诊断状态及主题、语言切换共19次原生观察，独立启动器确认自然退出0；合成导航、真实后端Inspect拒绝与图像观察分别计证，未据此新增物理验证结论。。CI身份关系：CI为产品的直接单父提交子节点，仅在Linux工作流增加六行系统运行库安装；完整11340项Git路径、模式与对象核验确认其他项相同，来源及测试指纹一致。Windows与实窗证据保留7d718d0原身份，CI十二份报告保留a9ad09d原身份；映射证明代码与测试对应关系，不证明跨平台二进制字节相同。。依赖结论：GUI依赖统一经gui/requirements.txt限定PySide6>=6.11.1,<6.12；本轮Windows实窗使用6.11.1。Linux CI采用Python3.11并安装libegl1、libgl1、libxkbcommon0、libdbus-1-3、libfontconfig1，保留数据集环境及PySide6自身QT_PLUGIN_PATH，后端使用本轮已验CI构建的CMake RPATH，Python/GUI不全局注入conda LD_LIBRARY_PATH。旧WSL命令保留历史，不作为当前启动方案。。集成事实：此关闭记录形成时，codex分支尚待正常快进；随后同日回信记录真实集成结果。。

既有编辑器及Project/Run、向导、扫描、屏蔽场景共用结构化诊断；按实际对象/字段/快照定位，表格按目标单元格滚动，旧报告失效，来源只读，原文本和阻断规则兼容。无编辑控件或可靠来源时明确拒绝。这不扩张高级GUI字段或科研物理验证；F5为下一完整阶段，仍待启动，K1/L1/Q2按原依赖推进。

5d6f008几何定位空白反例与Windows中断轮（92 PASS/1 FAIL、无完整report）、旧CI失败/未执行profile，以及096f4b3原生host异常退出均保留历史原件，不计最终通过。QA host的Close事件对象树遍历缺陷只在out辅助程序修正；第三轮7d718d0的Linux CI因缺少libEGL.so.1失败，仅有6份实际报告，后续6个Linux profile未执行；其旧报告与失败日志仍属历史，不能用新CI回填或冒充当轮通过。PID40456、2026-10-30 19:51:06的0xc0000409与缺失退出收据不得改写。合成夹具、离屏交互、真实后端Inspect拒绝与原生图像观察分别计证；本阶段不声称新增模拟或物理基准。

## F1 已完成（2026-10-30）

[归档独立复核](docs/verification/f1-automated-review-20261030/README.md)已完成：发布前批准、发布后2797原件与38个生成核验文件一致，正式与历史报告分开验真。

来源首提交5373d57实现构建身份、实际输入读账、显式输出归属及流式SHA，兼容旧记录；GUI独立展示运行结果与文件身份并后台重验。最终产品f176d0e的Windows全量143/143、48511个v3入口及E6逐项基线通过；Linux11.3.2/11.4.3各143项（run41028779177）、M0 Windows/Ubuntu各64项（run41028779326）通过，12报告/4官方ZIP/414次执行的日志证据核验通过。实际Windows窗口14次原生图像观察、真实2线程/2轮各2事件输出与正常退出收据已独立核对，**F1阶段已关闭**；[最终验收报告](docs/verification/f1-visible-20261030/README.md)集中记录证据与集成事实。[自动验收归档](docs/verification/f1-automated-20261030/README.md)保留当时pending原件。见[执行契约](docs/collab/inbox/20261030-1410-astra-f1-scope.md)与[输出身份说明](docs/输出身份与来源.md)。默认CSV保持不变；72次性能测量完成，无稳定收益的缓冲候选已撤回。

首冻结cd0f44a全量发现异步示例图表丢失预设选择，已修复并通过7项定向GUI回归及最终全量，原断言保留；另一个Windows数据定位失败为漏传已有环境参数，同E6环境控制通过。首轮Windows141/143、四CI任务GUI各38/39的失败证据原样保留。归档复核发现旧README误称四份job日志均落盘，实际缺三份，已补收原日志并新增更正收据，未改旧报告。

第二冻结3d1faf1的Windows143/143、48,511个v3断言及E6逐例基线通过，M0 run41024949832双平台通过；Linux run41024949824两个版本均在GDML集成故障测试失败。审查进一步复现缓冲分配失败漏关原生句柄，按[修复提案](docs/collab/inbox/20261030-1643-astra-f1-gdml-repair.md)在f176d0e修复并完成上述全平台重验。窗口遮挡曾使实窗验收暂停；用户置前后旧host正常退出，最终GUI加载ede037f（相对产品仅文档变化），完成实际观察并正常退出。合成状态、真实CLI运行及原生观察分别计证，历史合成行仍为结果未证实，不扩张物理验证。

## E6 已完成（2026-10-30）

验收代码 `a779634`，隔离分支 `roadmap/E6-config-compat`。394 项 schema、主 INI 版本、迁移副本、诊断及标准运行包恢复/复制已实现并交叉审查；DeepSeek 真实参与前端设计，见 [设计记录](docs/collab/outbox/20261029-deepseek-e6-design.md)。导入参数丢失、弹窗回归及 Linux Qt 空数据读取问题均已修复。Windows **134/134、42815 个 v3 入口**与 2C 基线门禁通过；真实 Linux 11.3.2/11.4.3 各134项、M0 两平台各58项通过，12份CI报告严格门禁、4份官方归档摘要、384份用例日志哈希匹配。三轮原证据见 [自动验收报告](docs/verification/e6-full-20261030/README.md)。解锁后补齐12个实窗状态、20张原生截图观察、真实Inspect→Run的2/2事件与独立复核，见 [E6最终报告](docs/verification/e6-visible-20261030/README.md)。Linux报告dirty的完整状态清单未采集，不能称整个检出clean；高级编辑、任意资源打包与科研验证仍分别归J2/K1/Q2。

E6补充导航：[不同写者归档复核](docs/verification/e6-full-20261030/independent/README.md)、[阶段及集成状态](docs/verification/e6-full-20261030/acceptance-state.json)。原自动归档保持当时的pending记录和字节；本次实际完成证据独立追加，不追改历史报告。

## 完整 2C 已完成（2026-10-29）

验收产品 `f4770b0`：11 类消费者、同字节输入来源、事务/稳定对象身份、configure/run_begin/finalization、独立内核/worker 收据、模块 off/auto/on、只读 GUI 集合与差异闭合。干净 Release 与 Windows 全量 **118 PASS / 0 FAIL / 0 SKIP，40628 个 v3 入口**，报告运行时 `git_dirty=false`；Linux 11.3.2/11.4.3 实际 CI `40892017436` 各118项，M0 `40892017433` 两平台各47项，12个证据门禁通过、4个ZIP传输SHA匹配。最终依据见[完整2C验收报告](docs/verification/2c-full-20261029/README.md)，契约见[EffectiveConfig](docs/EffectiveConfig.md)。

同口径 Q1 控制使用原 Q1 生产代码加同五份测试 overlay 新测量：105项、36269个v3入口；候选118项通过原 `check_report_evidence --baseline`。历史Q1的83770入口和原始报告保持原样，不能与新计数直接比较；[控制提案](docs/collab/inbox/20261029-2223-astra-2c-counter-control.md)及最终报告说明逐记录检查、固定断言入口和真实覆盖量的区别。

最终真实Windows可见GUI对应上述二进制：2run、2worker、8/8事件、14快照，10类程序化Qt检查及6张原生窗口截图全部完成并实际查看，证据保留在 `out/verification/2c-visible-accepted`。这不是offscreen或真人点击声明，也不构成物理正确性证明。sourcefp `c2b575bbb9c594765364aa7c78150e842ffb20ff34b10ad4729720bae2c8c91b`；testsfp `3ac890cc996d73289098628bb6cca8888f3120f9dffc3e22f60ab387ab1d6d1a`。

原始首轮失败 `out/verification/2c-full-windows/20261029-214410-a8c2b6e8`、旧CI `out/verification/2c-ci`、修后专项 `out/verification/2c-regression-repair`、build03/fee88d2可见检查 `out/verification/2c-visible` / `out/verification/2c-visible-final` 继续保留，不能冒充最终证据。实施与DeepSeek设计裁决见[开工信](docs/collab/inbox/20261029-1959-astra-full-2c-execution.md)和[设计记录](docs/collab/outbox/20261029-deepseek-full2c-design.md)。

2C 后续 E6、F1 已完成；F4 已完成；下一完整阶段F5仍待启动，验收范围与证据见本页新增关闭记录。Q2、安装包及完整GUI编辑等保持各自未完成状态，按ROADMAP依赖推进。

## 2026-10-29 隔离开发工作区与2C子集历史

用户授权 Astra 主导 2C 实现。当前工作区 `C:\Users\123\.codex\worktrees\effective-config\G4UniversalSim`，基线 `5465dbd`，分支 `roadmap/2c-effective-config`；原 D 盘工作区由 DSH 保留，禁止并发合并。实施契约见 [2C 开工回信](docs/collab/inbox/20261029-1010-astra-2c-execution.md)。DeepSeek 已通过 API 提供前端设计，采纳范围与纠偏见 [前端设计建议](docs/collab/outbox/20261029-1010-deepseek-effectiveconfig-ui-design.md)。

该历史子集接通独立数据模型、配置阶段导出与只读查看器；当时未完成完整消费者覆盖、三阶段应用证据与 off/auto/on，其历史验收范围不扩大。原基线 87 项归档报告已在本轮通过严格证据门禁复核。

2C子集历史验收（旧探针计数，不与Q1 v3直接比较）：MSVC + Geant4 11.3.2 构建成功；最终两组覆盖统一平台全部 **89 PASS / 0 FAIL / 0 SKIP，117149 条断言**，另有独立模型 24 条。两组报告源码/测试指纹一致，逐用例断言非零，归档日志 SHA-256 与严格门禁通过；见 [验收记录](docs/verification/2c-configured-20261029/README.md)。初轮两项环境失败原样保留，已使用已有 GDML/数据根参数复测，未放宽测试。真实导出数据的浅色/深色/小窗口 offscreen 图已查看，不等同桌面与高 DPI 验收。

当时 2C 子集代码范围：`Config/EffectiveConfig` 类型化事务与不可变快照、`--dump-effective-config` 独占新文件/标准输出、GUI新增只读查看器（当时共9页）；完整 2C 后续验收见本页上节。上轮收尾收到独立审查，csh 拒绝主配置切换后仍报成功（R-01，P1）、元数据写失败但文本摘要仍成功（R-02，P2）在 70a1aba 重新复现；旧反例见 [修前证据](docs/verification/m0-known-defects-20261029/README.md)。它们当时未被已有 89 项覆盖，本轮已补正式回归并修复，见下段。

2026-10-29 R-01/R-02阶段历史验收：Release 构建、**89 PASS / 0 FAIL / 0 SKIP，117833 条断言**，严格证据门禁通过，见 [修复报告与日志](docs/verification/reliability-r01-r02-20261029/README.md)。维持拒绝配置热切换；metadata 异常纠正可写文本摘要并排除失败产物，不承诺跨文件原子性。该节点当时未做Linux/11.4/安装包验收；后续当前源码Linux/11.4证据见上方Q1，安装器扩展仍归I2。

R03–R32现已完成修复与回归，旧[反例证据](docs/verification/r03-r04-current-20261029/README.md)和提案保留为历史。V01方法边界已裁决，统计适用范围后续归Q2。该Q1历史节点的下一项是[2C](docs/EffectiveConfig.md)，现已另行完成；五项新增目标与E/F/H依赖继续遵循[ROADMAP](docs/ROADMAP.md)；不因Q1通过宣布这些阶段完成。

## 原 DSH 集成基线（2026-10-28 归档，2C 新工作区见上节）

- 分支 `roadmap/F6-live-progress`，集成分支 `codex`（快进合并后推送）；`main` 为早期历史分支。
- 阶段 0 审计修复已交付：提交 `67ce037`（工作区快照）→ `2e87f18`（静默失败路径）→ `02c0dc6`（验收证据与状态）→ `48f566b`（跨代理协作信箱）→ `8b7721b`（阶段 1 文档与仓库卫生）→ `c80a9cf`（历史审计对照表）→ `5c6ea1d`（阶段 1.4 报告 v2 与证据门禁）→ `f1dad9d`（阶段 1b 零断言清零与 writer 边界用例）→ `48d8c68`（阶段 1b 证据与状态收尾）→ `7f5dc48`（阶段 1d 证据门禁自洽性与日志摘要按落盘字节）→ `32736c9`（阶段 1e 命令失败传播 D-4/D-5/D-6）→ `de1ea93`（Linux 构建与 CI workflow、双平台验证）→ `976ce9e`（CI workflow 的 `runner` 上下文修复）→ `dc03a1b`（D-7 屏蔽场景证据语义）→ `dbd72cf`（失败用例公开注解）→ `a5970ff`（Qt 插件修复，GitHub Actions 转绿）→ `3291145`（GUI 路径比较）→ `b45d325`/`088761d`（四 profile 绿记录与 Astra 信）→ `960d683`（2B 场景模型）→ `f00bb30`（headless 驱动 + `analyze(output_dir)`）→ `a96d957`（Scenario 页）→ `719f1df`（端到端 smoke）→ `7834784`（NIEL 溯源）→ `402a9f2`（2B CI 回归修复）→ `45891c3`（2B 证据与文档、`platform_paths` 守门）→ `2feddfc`（记录双 workflow 全绿）→ `92bb98a`（2C 现状测绘）→ `5d6b94e`（STATUS 指向测绘）→ `97036df`（Geant4 11.4 数据集表与版本无关测试）→ `6a8b237`（Linux CI 版本矩阵）→ 本提交（11.4 结论与证据）。HEAD 以 `git log` 为准。
- 最近一次完整回归（Geant4 11.4 支持 + CI 版本矩阵，严格证据门禁）：**87 PASS / 0 FAIL / 0 SKIP**，`profile=all`，`version=2`，`assertions_executed_total=116677`、`assert_sites_total=2702`、`cases_with_zero_assertions=[]`、`assert_probe=settrace_assert_lines_v2`、`log_digest_algorithm=sha256_raw_bytes_lf_v2`、`skip_policy=failure`、`tracked_source_gate=pass`、`untracked_source_files=[]`、`backend_provenance=source_sha256_manifest_matches_executable`。
  - 报告与 87 个逐用例日志：[docs/verification/stage-11d4-20261028/README.md](docs/verification/stage-11d4-20261028/README.md)（2B 交付基线见 [stage2b](docs/verification/stage2b-20261028/README.md)、F6 `sequence` 基线见 [stage2b-f6](docs/verification/stage2b-f6-20261028/README.md)）；更早证据见 [stage1j](docs/verification/stage1j-20261028/README.md)、 [stage1f](docs/verification/stage1f-20261028/README.md)、[stage1e](docs/verification/stage1e-20261028/README.md)、[stage1d](docs/verification/stage1d-20261028/README.md)、[stage1b](docs/verification/stage1b-20261028/README.md)（旧摘要口径，只能加 `--allow-legacy-digest` 复核）、[stage1](docs/verification/stage1-20261028/README.md)、[stage0-20261027](docs/verification/stage0-20261027/README.md)。
  - 源码指纹 `3ad03f2d62c354323f86edeb57c4479219ad75ca568ce3f8b3037c3c5d49aca9`、测试/夹具内容指纹 `4eca0c97e22d4e45310b13e8ae3d556d2ceb8e1bfeb63906a43b4dd9cb857d02`；后端 `G4UniversalSim.exe` SHA-256 `f78fa2fb06c08dbebd590bf7457f306ec85d9d6a7a8c0f0b30f5b7daeb6b45e1`（1734656 B）；构建身份 MSVC 19.51.36246.0 + Geant4 1132 + MT。
  - 报告运行时 `git_head=6a8b237`、`git_dirty=true`（本轮 `src/Core/Geant4DataLocator.cc` 的 11.4 分支在运行前未提交）。
- Linux 验证：①本机 WSL（Ubuntu 24.04.4 + conda-forge Geant4 11.3.2 + g++ 13.3）backend **35/35**、integration **14/14** 全通过（backend 在 2B 后按 `G4USIM_EXE` 修复重跑，109970 断言），证据 [docs/verification/linux-wsl-20261028/README.md](docs/verification/linux-wsl-20261028/README.md)；③**Geant4 11.4（实验性）**：本机 WSL 11.4.3 构建成功、四个 profile 87/87 全过（backend 109,942、static 391、GUI 1,877、integration 4,364 断言），见 [docs/Linux构建与验证.md](docs/Linux构建与验证.md) §8；`linux-geant4.yml` 已加版本矩阵（11.3.2 / 11.4.3）。②**GitHub Actions 四 profile 全绿**（`3291145` 的 `codex` run [40640355033](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40640355033) 与 roadmap run [40640350911](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40640350911)，`ubuntu-24.04` 上 static / offscreen GUI / backend / integration 各自过证据门禁，另有篡改副本负向对照；更早的 `a5970ff` 只覆盖 backend+integration），构建过程、两个 GCC-only 缺陷、PySide 退出 `SIGSEGV` 与五个 CI-only 缺陷的修法见 [docs/Linux构建与验证.md](docs/Linux构建与验证.md)。
- 测试平台：`python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip`；87 个用例 = static 10 / gui 27 / backend 35 / integration 15，所有用例都报告非零断言数；报告是 `version: 2` 证据（逐用例断言数、双指纹、`log_sha256` 按落盘字节），`scripts/check_report_evidence.py` 为 CI 门禁（逐项断言 ≥1、求和/计数/零断言列表一致、摘要与磁盘字节一致、发布报告无 fail/skip，归档旧报告需 `--allow-legacy-digest`）。
- CI 现状：`.github/workflows/linux-geant4.yml` 现用 Geant4 版本矩阵（`11.3.2` / `11.4.3`，每版本独立前缀、报告根与 artifact；11.4 leg 传 expat/zlib/freetype 的六个 `-D*` 参数），`6a8b237` 上 `ubuntu-24.04 / Geant4 11.3.2` 与 `ubuntu-24.04 / Geant4 11.4.3` 两个 job 各 26 步全绿（run [40690078563](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690078563) / [40690070991](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690070991)）。更早的事实：`ubuntu-24.04` + conda-forge Geant4 11.3.2，构建后依次跑 static / offscreen GUI / backend / integration 四个 profile（各自 `--report-root`、`--fail-on-skip`、证据门禁、`if: failure()` 注解），随后用篡改副本验证门禁必须拒绝，最后 `if: always()` 上传 artifact；跨平台指纹一致。`.github/workflows/m0-static-gui.yml`（Windows/Ubuntu 的 static+gui）已由仓库所有者启用，`402a9f2` 上 **ubuntu 与 windows 双平台全绿**（run [40675415994](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40675415994) / [40675409885](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40675409885)，各 15 步）；此前 2026-10-23 的失败是 Windows-only GUI 断言比较错误，已由 `402a9f2` 修好。**两条 workflow 在 `45891c3` 上同时全绿**：M0 run [40680571889](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40680571889) / [40680563877](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40680563877)（ubuntu + windows 的 static 与 offscreen GUI），Linux run [40680571833](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40680571833) / [40680563958](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40680563958)（static / offscreen GUI / backend / integration 四 profile + 证据门禁 + 篡改负向对照 + artifact）。Linux backend 首次包含 2B 的 `scenario_shielding_core` 并通过。

## 阶段状态（摘要，详表见 ROADMAP）

- A 核心功能、B 场景包与基准、C 向导/绘图/扫描、D 安装包、G 3D 预览：已完成。
- E 修复：E1（GUI 与后端规则一致）、E2（配置 schema）、E3（Linux CI，含 Geant4 11.3.2 / 11.4.3 版本矩阵）、E5（GUI 拆分）已完成（E3 见 ROADMAP 的“done for Linux”；M0 workflow 已由所有者启用并在 `402a9f2` 双平台全绿；11.2 未测）；E4 已做部分规范迁移和链接检查，仍需收尾；新增 E6/E7 的范围见 ROADMAP。
- F 优化：F6（实时运行进度）已完成，2026-10-28 追加可选 `sequence`（进程级单调、跨 run 不重置，GUI 拒绝重复/回退行；旧后端仍可解析），契约见 [docs/实时运行进度.md](docs/实时运行进度.md)；F1 输出与来源已完成（见上方验收边界）；F4 校验定位已完成；F2 运行会话、F3 性能/tasking、F5 undo/autosave、F7 二维扫描、F8 GUI 收尾未做。
- H 增量：H1（径迹输出）已完成；H2–H9（过滤计分、平行世界、方差降低、光学、活化、DNA、体素体模、通用直方图）未做。
- M0 全模块 EffectiveConfig / 模块开关归已完成的2C；SolidRegistry 归 E7，仍未实现。M0–M5 是长期目标汇总，不与新工作项重复计算完成度。

## 阶段 2B（屏蔽/涂层场景 GUI 端到端，已完成 2026-10-28）

- 命令行生成器提炼为 `scenarios/shielding_coating/scenario_model.py`（`ShieldingSpec`、`problems()`、`render()`、`generate()`），`make_scenario.py` 保持 CLI 契约；分析侧 `analyze.analyze(output_dir)` 供 GUI 复用。
- 新增 Scenario 页（15 字段三层校验、生成、QProcess 运行、结果表五列带证据、DDD 行显示 NIEL 表路径与 sha256、中英切换）与 headless 驱动 `gui/g4usim_gui/core/scenario_shielding.py`；12 步端到端 smoke 走 offscreen Qt + 真后端 200 事件。
- NIEL 溯源写入 `scenario.json` 的 `niel: [{particle, path, sha256}]` 并进入分析报告 `evidence.niel_tables`；缺证据仍沿用 D-7 语义（退出码 3，不写零报告）。
- 新增用例 `shielding_scenario_model`、`shielding_analysis`、`scenario_shielding_core`、`scenario_page`、`gui_scenario_backend`，并加 static 守门 `platform_paths`。契约与限制见 [docs/屏蔽涂层场景端到端.md](docs/屏蔽涂层场景端到端.md)。

## 正在做 / 下一步

阶段 1（文档与仓库卫生，进行中）：

1. 已完成：修文档里的反向错误（README 与中文使用手册中“LET/GDML/STL/自动合并未实现”的旧说法）；
2. 已完成：`STATUS.md` 单一入口 + 5 份过期快照归档 `docs/archive/`（含 [归档索引](docs/archive/README.md)）；
3. 已完成：`_backup_git_*` 进 `.gitignore`、25 个本地分支推远端（CI 从零变为逐分支可触发）；
4. 已完成：`AGENTS.md` 48.5 KB → 33.5 KB（29 条日期条目全文迁入 `docs/agent-history.md`，只留索引）、`docs/Agent维护说明.md` 文档地图重写、新增 static 用例 `doc_links`（53 个 Markdown 文件 100 条相对链接全部可解析）；
5. 已完成：历史审计结论对照表 [docs/collab/outbox/20261028-0120-deepseek-legacy-audit-crosscheck.md](docs/collab/outbox/20261028-0120-deepseek-legacy-audit-crosscheck.md)（`总体判断.md`、2026-10-03 现场审计、E2、F6、阶段 0 逐条判定为仍成立/已修复/部分成立/已过时，仍成立的 9 条按阶段归位）；
6. 已完成：报告加断言级计数与工作区/测试内容双哈希、默认报告目录改 `out/verification`、CI 把 skip 当失败（`--fail-on-skip` + `check_report_evidence.py` 门禁）；顺带修复 `.gitattributes` 让 checkout 换行改变源码指纹的真实缺陷；
7. 已完成：支持矩阵第 2–3 节每条功能标注证据类型（外部表 / 解析式 / 同源自洽 / 自测 / 未验证），第 1 节给出判定口径；
8. 已完成：E2-S1 六个 editor→writer 边界升级为 static 用例 `writer_boundary`；9 个零断言用例改写成 `assert` 表达（断言证据从 115305 增至 116133，零断言列表清空）。
9. 已完成：Astra 2026-10-28 审查的 6 条缺陷全部闭合（D-1 证据门禁可篡改绕过、D-2 日志摘要与磁盘字节不符、D-3 文档漂移、D-4 交互偏置拒绝只告警、D-5 材料交互无生命周期门禁、D-6 `ParseStrictDouble` 接受 inf/nan）。
10. 已完成：D-7（`scenarios/shielding_coating/analyze.py` 缺证据当零结果）闭合——运行事实不达标即退出码 3 且不写报告，统计文件用 `run_metadata.json` 的 `generated_files` 区分“被删”与“真零”，相空间跨轮次/越界为证据错误，报告新增 `evidence` 段，回归含五种反例。
11. 已完成：E3 Linux CI 在真实 Actions 上转绿（四 profile + 注解 + 篡改负向对照），并顺带修掉三个 CI-only 缺陷（job 级 `env` 上下文、conda Qt5 插件遮蔽 PySide6 Qt6 插件、公开仓库日志不可读）。

阶段 2（2B 场景已定为**屏蔽 shielding_coating**）：

- 2A：Linux + Geant4 11.3/11.4 CI（E3）——已完成（Actions 双版本矩阵绿，见上）；遗留 11.2 兼容性；
- 2B：屏蔽场景 GUI 端到端 + schema 驱动编辑器——**已完成（2026-10-28，见上节）**；
- 2C：完整 EffectiveConfig + 模块 off/auto/on（Astra 主导设计）——原 DSH 基线的**只读测绘**见 [docs/collab/outbox/20261028-2000-deepseek-effectiveconfig-survey.md](docs/collab/outbox/20261028-2000-deepseek-effectiveconfig-survey.md)：
  现状（13 个 `effective_*` 标量、11 个来源字段、materials 六态、19 个 main_ini section、散落布尔开关、缺 `--dump-effective-config`）、
  六条缺口（无对象 ID、无 requested/resolved/applied 四元组、缺 BeginOfRun 快照、无 off/auto/on 语义、GUI 无结构化入口、验收只能数 353 字段），
  以及当时的切片建议与五个待 Astra 决定的问题。该测绘后的configured子集及最终完整2C已分别验收，见本页开头；不能再将当时“未写代码”的状态应用于当前隔离分支。
- 铁律：阶段 2 冻结新功能，目标是压低 `experimental` 比例，而不是扩大分母。

## 已知缺口（不要把以下当作已完成）

- 后端名字校验类错误可能在"首个事件前"才发现（例如 `[scoring.displacement]` 的粒子名在 `BeginRun` 校验，`--inspect-run` 查不出）。
- E6当前schema 394个字段中 supported 60 / experimental 319 / deprecated 13 / unsupported 2；62项有 `gui` 元数据，332项无GUI元数据。字段登记及 `gui` 元数据不等于可编辑；新增模块策略、场/偏置登记与版本标记均未开放对应编辑器。字段数不等于全配置或物理验证。
- 探测器响应、Dose/Fluence/DDD 等基准多为"同源自洽"或"解析式"，缺少第三方独立数据与实测效率对照。
- 偏置只有 process-level XS 路径；importance、weight-window、splitting、Russian roulette 未实现。
- 交互命令审计只覆盖 `--ui --ui-session csh`；Qt UI 与部分嵌套/动态命令不受审计保证。
- 安装包 `out/` 中 1.0.0 早于 F6/阶段 0 改动，不可作为当前版本引用。
- 屏蔽/涂层场景只覆盖法向入射平板几何与 15 个字段：未做角度分布、非平板几何、光核/活化；TID/DDD 沿用 B2/B3 定义，不是新的物理基准。
- 测试脚本的跨平台约束靠 static 用例 `platform_paths` 守门（提到 `build_vs2026` 必须同时读 `G4USIM_EXE`），不保证其它手工脚本。
- 命令族的“改了缓存、内核没变、退出码 0”三条路径已闭合（Astra 2026-10-28 审查 D-4/D-5/D-6）：交互会话里的 biasing 修改被拒绝时计入 csh 失败（`interactive_command_failure_kind = biasing`）并停止会话、material 的 9 个变更命令只允许 `PreInit`（初始化后由 Geant4 拒绝 → `geant4_illegal_application_state`）、`ParseStrictDouble` 拒绝 `inf`/`nan`/溢出。只覆盖脚本化 `--ui --ui-session csh`；Qt UI 内的同类操作仍未自动化验收。
- Geant4 版本：11.4.3 已进 Linux CI 矩阵并在 Actions 上绿，但本机 Windows 只有 11.3.2——Windows + 11.4 与 11.4 下的真实桌面 GUI（非 offscreen）、ROOT/uproot、打包流程均未验证；Geant4 11.2 未测。
- Actions 日志需登录才能下载：失败用例只能靠公开注解（`scripts/ci_annotate_failures.py`）与 artifact 诊断，注解不是完整日志。
- 断言证据是**已执行 `assert` 的下界**（`sys.settrace` 计数），不是覆盖率；证据门禁只证明“报告与日志自洽且未被篡改”，不证明断言写得好。
- F6 进度协议的可选 `sequence` 已补（2026-10-28）：`[G4USimProgress]` 每条消息带进程级单调序号（跨 run 不重置），GUI 拒绝重复/回退的行，旧后端不带该字段时仍按旧行为解析；它只是顺序证据，不判定成功。

## 文档地图

| 文档 | 职责 |
| --- | --- |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 阶段状态与进度日志（唯一登记处） |
| [docs/功能支持矩阵.md](docs/功能支持矩阵.md) | 支持等级基线：什么能解析、能运行、物理验证到哪一步 |
| [docs/开发路线图.md](docs/开发路线图.md) | M0–M5 长期目标与历史验收记录 |
| [docs/开发接续计划.md](docs/开发接续计划.md) | 后续工作包的范围、依赖、验收标准与待决事项 |
| [docs/测试平台说明.md](docs/测试平台说明.md) | `run_m0_tests.py` 分层、报告字段、证据与限制 |
| [docs/中文使用手册.md](docs/中文使用手册.md) | 面向用户的操作手册（INI、命令、输出、限制） |
| [docs/输出数据契约.md](docs/输出数据契约.md) | CSV/ROOT/摘要字段与版本迁移 |
| [docs/collab/README.md](docs/collab/README.md) | 跨代理协作：信箱、单写者规则、会话互读 |
| [docs/archive/README.md](docs/archive/README.md) | 已归档的历史快照清单 |
| [AGENTS.md](AGENTS.md) / [gui/AGENTS.md](gui/AGENTS.md) | 仓库/前端开发约束（实现口径、测试要求、禁止事项） |

## 协作与工作约定

- **单写者**：同一工作区默认只有本会话写代码；Astra（Codex 侧）作为总设计师/首席审查者只读审查并写提案，双方通过 `docs/collab/` 文件信箱交接，不粘贴整段对话、不导出密钥。
- **提交节奏**：`roadmap/<item>` 分支 → 全量回归 → 更新 ROADMAP/矩阵/CHANGELOG → 提交 → `codex` 快进 → 推送；不改写历史、不强制推送。
- **证据**：结论必须能落到"报告 + 日志 + 指纹/哈希"三件套；"命令成功退出"不等于物理正确。

## 接手阅读顺序（约 30 分钟）

1. 本页；
2. `AGENTS.md`（严格口径）与 `gui/AGENTS.md`；
3. `docs/ROADMAP.md` 状态表；
4. `docs/功能支持矩阵.md` 你关心的模块行；
5. `git log --oneline -15` 与 `git status`；
6. 需要动后端时跑 `python -B scripts/run_m0_tests.py --profile backend --require-tracked-sources`（需要本机 Geant4 与已构建 exe）。
