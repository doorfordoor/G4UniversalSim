# K1 面板中文布局续修交付

## 本轮结果与更正

主代理已加入全部 27 项中文词条。此前 766 次 v3 断言入口的通过结果是在大量词条回退英文时取得，只验证了当时的混合语言布局和翻译调用；不能作为完整中文布局证据。此前报告的语言覆盖表述过宽，现予更正，初次记录及身份保留在下方并标注历史边界。

本轮只修改 `experiment_panel.py` 与 `smoke_k1_panel.py`，更新指定两份交付说明，新增独立后缀测试日志；没有修改 i18n、RunPage 或其他写者的文件，没有提交。

## 失败证据和根因

`out/collab/k1-panel-integrated.log` 原字节保留，G4USIM_ASSERTS=195 后在 `top.x() + label.width() <= viewport.width()` 断言失败；当前原日志标注测试第 138 行（用户提及另一行号不改变失败判据）。最初通过日志 `out/collab/k1-panel-smoke.log` 也未覆盖。

只读诊断复现：zh_CN、面板宽 360，viewport 宽 360；滚动区 content 仍宽 426；fields 名称标签 x=13、宽=358，因此右边界 371 超出 360。此时动作已计算为 3 列，内容最小宽已降到 260，但旧内容几何仍保留。中文令五列按钮最小宽度和缩列时机改变，暴露了动态重排与 QScrollArea 尺寸通知不同步的问题。

## 修复和回归

内容布局使用 Qt `SetMinAndMaxSize`，使变化的约束传播到滚动区；动作重新排布后同步激活动作布局与内容布局，避免等待另一轮排队布局请求才能清除旧宽度。保留 300 高限制、四层常显、原生 palette、折叠和信号接口，没有扩大视口或改变几何判据。

原测试 60 个 assert 表达式全部保留；新增 7 个表达式，共 67 个。中文阶段明确要求动作、四层标题、全部状态、标题/表头及导出说明的集中词条存在、翻译不等于英文源消息并确实包含中文字符；还检查实际四层名称/状态含中文。缩放从原 640→480→360 扩为 640→480→360→480→640→360，保留原边界断言，并新增内容宽度等于 viewport、动作最小宽度不超 viewport 的检查。

- 专项 `python -B tools/test_assert_probe.py gui/smoke_tests/smoke_k1_panel.py`：退出 0，`G4USIM_ASSERTS=1598`。PySide6 6.11.1，Qt offscreen，真实集中中文词典，zh_CN/en 往返和收缩/扩张路径均通过。日志：`out/collab/k1-panel-zh-layout-fixed.log`。
- `python -m compileall -q gui`：退出 0。日志：`out/collab/k1-panel-zh-layout-compileall.log`。
- 原失败日志和首次通过日志 SHA256 均在修复结束时复核，保持原字节。

这里是纯 Qt 自动几何及状态验证；未观察实际 Windows 窗口、未完成整页控制器端到端验证或 Geant4/物理比较。独立复审仍由另派审查者负责。

## 本轮文件身份

集中词典仅作为测试依赖记录其当前身份，本轮未写入。

- `gui/g4usim_gui/widgets/experiment_panel.py`：`741adb59951cbf8adc9428eca4703612efafa737396dc5025d350c8ad53bbfd1`
- `gui/smoke_tests/smoke_k1_panel.py`：`4e90b351f3d934cc07abf2f519d9dd1476117b0e3c28714c1b93426632673c7a`
- `gui/g4usim_gui/core/i18n.py`：`37f5f888f7ad9a70731a7a32b49608b34b51a0f57b85123cb948fff88a2f20cb`
- `out/collab/k1-panel-integrated.log`：`cf14f7a059361d89c1eccd2d094fd5977dcb7b3c9e0517d024a81a300819cc92`
- `out/collab/k1-panel-zh-layout-fixed.log`：`6df1cb302f156a7d5933078c6581cc9c2dee8a1df0fa564f93b9c8756fe1d20b`
- `out/collab/k1-panel-zh-layout-compileall.log`：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

---

# 首次交付记录（历史：27 项中文词条曾回退英文）

## 范围与身份

工作区：`C:/Users/123/.codex/worktrees/effective-config/G4UniversalSim`。
本轮读取根目录及 gui/AGENTS.md、docs/collab/inbox/20261031-k1-execution.md。
DeepSeek 实际请求/返回均为 `deepseek-flash`；请求 ID `ebf75eb6-18d8-4035-a250-1dd0ba8ac8a7`。原回复 `out/collab/k1-deepseek-response.json` 保留。本轮是本地修复写者交付，不是独立审查结论。

只修改两份实现/测试文件及用户指定两份交付文档，另在 out/collab 留测试日志。没有提交、暂存、修改 D 盘原检出或其他实现文件。主代理/其他写者并行新增或修改的 STATUS、ROADMAP、环境发现、环境对话框、CLI 等文件未触碰。

## 修复与接口

- 补上 `_render_state`，构造、set_state 与 retranslate_ui 都走同一渲染入口。
- 保留 DeepSeek 的“快照/四层验证、网格动作、表格历史、稳定信号”总体布局。四层状态默认全部显示；小宽度不隐藏科学状态。详情与历史分别用键盘可操作的折叠按钮，默认折叠。
- 最大高度 300；按钮按实际 sizeHint 自适应列数。超出高度的详情/历史通过 Qt 滚动区访问。原生 palette，无业务样式表或硬编码颜色。详细诊断放在层级标签提示和无障碍描述，简要状态常显。
- 保持 `ExperimentPanel(parent)`、`set_state(data)`、`set_busy(bool)`、`action_requested(str)`、`retranslate_ui()`。set_state 接受原 dict 协议，全量替换且深复制输入，不持有项目/runner，不建进程、不自行验证物理。
- `ACTION_TOKENS` 与全部可发动作同步：`inspect / validate / initialize / generate / run / evaluate / export / import / environment / cancel`。新增 import（加载包）、environment；cancel 纳入常量，沿用原实现“空闲也可点击，忙时只有 cancel 可点击”的行为。动作只发信号；环境窗口、加载和控制器接线由主代理完成。
- `levels` 仍是 `[{level, status, detail}]`，四层 token 为 fields/initialization/execution/physics；status 为 unverified/passed/failed/stale/unobserved/cancelled。各层独立，execution passed 不提升 physics。缺层显示 Unverified；未知状态显示 Unobserved，未知历史层显示 Unknown。
- `revision / fingerprint / run_id / status` 摘要保留，hash 简写但 tooltip 保留完整身份。总状态也只识别上述有限状态集合，其他值降级为 Unobserved，集成如需新增总状态须显式补充映射。
- 历史保持 `[{level, status, record_id}]`；保留所有有效 dict 记录，包括同状态且缺 ID 的记录，避免隐藏证据。空/非法历史清表，失败与陈旧记录保留。外部 detail 作为原始诊断，不翻译、不按 HTML 解释。

## 国际化移交

使用实际 `ui_text(source, language=None)` 与 `ui_format(source, *, language=None, **values)`；不再使用伪消息键/默认文案参数。ACTION_TEXT/LEVEL_TEXT/STATUS_TEXT 仅为稳定机器 token 到英文源消息的映射，不是另一套翻译词典。中文只由 core/i18n.py 的集中词典提供，本轮未修改该文件。

下表记录首次交付的全部源消息及当时词典状态。“主代理待加”是历史状态；本轮复核时主代理已加入全部 27 项，当前没有这 27 项缺词。格式串占位符保持原样。

| 英文源消息（集中词典键） | 中文映射 | 首次交付时的词典状态 |
|---|---|---|
| Backend initialization | 后端初始化 | 主代理待加 |
| Cancel | 取消 | 主代理待加 |
| Cancelled | 已取消 | 主代理待加 |
| Check initialization | 检查初始化 | 主代理待加 |
| Compare physics | 物理比较 | 主代理待加 |
| Configuration identity: {fingerprint} | 配置身份：{fingerprint} | 主代理待加 |
| Environment | 环境 | 主代理待加 |
| Event completion | 事件完成 | 主代理待加 |
| Export bundle | 导出配置包 | 主代理待加 |
| Export includes configuration, resources and evidence; excludes C++ projects, secrets and machine settings. | 导出包含配置、资源与证据；不含 C++ 工程、密钥或机器设置。 | 主代理待加 |
| Failed | 失败 | 已存在，沿用 |
| Fields and dependencies | 字段与依赖 | 主代理待加 |
| Generate package | 生成运行包 | 主代理待加 |
| Inspect inputs | 检查运行输入 | 已存在，沿用 |
| Level | 层级 | 主代理待加 |
| Load bundle | 加载配置包 | 主代理待加 |
| Passed | 通过 | 主代理待加 |
| Physics comparison | 物理比较 | 主代理待加 |
| Record | 记录 | 主代理待加 |
| Revision: {revision} \| Hash: {fingerprint} \| Run: {run_id} \| Status: {status} | 修订：{revision} \| 配置哈希：{fingerprint} \| 运行：{run_id} \| 状态：{status} | 主代理待加 |
| Run | 运行 | 已存在，沿用 |
| Snapshot details | 快照详情 | 主代理待加 |
| Stale | 陈旧 | 主代理待加 |
| Status | 状态 | 已存在，沿用 |
| Trusted experiment | 可信实验 | 主代理待加 |
| Unknown | 未知 | 已存在，沿用 |
| Unobserved | 未观测 | 主代理待加 |
| Unverified | 未验证 | 主代理待加 |
| Validate fields | 校验字段 | 主代理待加 |
| Validation history | 验证历史 | 主代理待加 |
| {level}: {status} | {level}：{status} | 主代理待加 |
| {status} — {detail} | {status} — {detail} | 主代理待加 |

## 首次交付的验证范围（已更正）

- `python -B tools/test_assert_probe.py gui/smoke_tests/smoke_k1_panel.py`：退出 0，`G4USIM_ASSERTS=766`（v3 入口计数，不是独立命题数）。Qt 平台 offscreen，PySide6 6.11.1。
- 覆盖纯 Qt 鼠标/键盘信号、全部 action token、busy/cancel、busy 不被 set_state/语言重绘解除、四层逐一独立通过、全部已知状态、未知/非法状态降级、历史失败/陈旧保留与清空、输入复制、原始诊断按纯文本处理、zh_CN/en 往返、表头/按钮/动态层级/历史/提示重绘、折叠展开。此时 27 项中文缺失，比较 ui_text 只验证了回退机制和少数已有中文，未覆盖完整中文布局。
- 首次 640/480/360 宽、最大 300 高的 offscreen 检查使用含英语回退的混合语言文本；只能证明当时的布局，不证明完整中文布局。加入中文后失败，证据见本报告前部。
- `python -m compileall -q gui`：退出 0。最终仅测试增加平台信息后再次执行专项；编译检查也覆盖最终文件，见对应日志。
- 初次专项中，假设 Cancel 已有中文词条的断言失败，核查实际词典后改用已有 Run 验证真实语言切换；未伪造词典。第二次发现按钮撑宽，修为按文字宽度重排。最终通过以上专项。

## 未验证及主代理下一步

未观察实际 Windows 窗口、未做高 DPI/屏幕阅读器实测、未运行 Geant4 或物理比较、未跑全矩阵。没有完成 Run 页集成与端到端控制器验证；300 高是面板约束，不是实际 Run 页观察结论。独立复审由另派审查者进行，本写者未代替审查。

集中词条现已由主代理加入，RunPage 也已接入面板；后续控制器接线、测试登记、Run 页真实窗口观察及整阶段验收由主代理推进。未修改集中词典、runner 登记、支持矩阵或阶段状态，遵守此次独占范围。

## 首次交付文件身份（历史，非本轮修复文件）

写交付时 HEAD：`ccb813a8540b83d5015daabebd5047929a16af2c`；工作区存在并行改动，不能把 HEAD 当作这些未提交文件身份。

- `gui/g4usim_gui/widgets/experiment_panel.py`：`168261f715f335d52101777d9af1ac50267ca31ded91915de44d2cf240cfb99b`
- `gui/smoke_tests/smoke_k1_panel.py`：`b6d81fe54dfe8eb89fcafd3bf0de9642c24d9c8709445f61fbed3688da4b0aa1`
- `out/collab/k1-panel-smoke.log`：`9cfdf281152e30fe3399e205097394e3d601da256b0f10364eb4b9bea05a5587`
- `out/collab/k1-panel-compileall.log`：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
