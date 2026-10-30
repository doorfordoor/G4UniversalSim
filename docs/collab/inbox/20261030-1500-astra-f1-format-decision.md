# F1 格式与缓冲决策

来源候选已独立提交 `5373d57`；完整阶段尚未验收。保留默认 CSV，用户无需逐项续行。

## 已测量的事实

实际 54 次运行：E6 与 F1 来源候选，hits（1000事件）、events（5000）、mesh（1000），csv/root/both 各3轮交替，双worker、固定seed4242。报告 `out/verification/f1-performance-before-auto/report.json` 保存每次退出/完成数、exe/input/log/产物SHA。以下为本机中位数，不是所有场景的性能保证：

| 负载 | F1 CSV 秒 / MB | F1 ROOT 秒 / MB | F1 both 秒 / MB |
| --- | --- | --- | --- |
| hits | 5.724 / 95.43 | 3.512 / 50.61 | 7.464 / 144.92 |
| events | 1.326 / 1.23 | 1.316 / 1.21 | 1.345 / 1.31 |
| mesh | 2.652 / 1.71 | 2.626 / 1.43 | 2.675 / 1.90 |

保留文件身份增加了读取成本；例如原E6 hits CSV约5.196秒，F1约5.724秒。本测量包含启动/运行/收尾，独立Python验证时间不等于C++哈希耗时。存在操作系统缓存与后台活动影响，第一轮附近还有轻量组件审查；不能据此宣称严格隔离的因果效应。

另对 F1 的标准流缓冲与显式256KiB堆缓冲做18次交替CSV运行：hits中位5.691→5.589秒（单次范围重叠），events1.333→1.341秒，mesh2.513→2.777秒。没有稳定整体收益，**撤回256KiB候选**，保留现有ofstream缓冲。候选patch/exe/日志保留out/collab/f1-buffer256k-candidate.patch、out/benchmark/f1-buffer256k、out/verification/f1-buffer-performance。候选只验证工程运行与测量，未通过全部数据等价/平台回归，不进入产品。

## 显式 auto 的实施决策

实施既定F1规则：只有用户显式 `[output] format=auto` 或 PreInit 的 `/AIHL/output/setFormat auto` 才启用。实际 scoring 已启用且 hits 或 event_edep 输出启用时解析为 ROOT，否则 CSV。不把物理计分/统计开关打开，不因选择格式改变实验参数。default仍csv，显式csv/root/both与别名不变。

输出 `output_format_requested` 与 `output_format_selection_reason`，原 `output_format` 继续表示实际格式。2C `/output/format` 保存原requested（例如auto）及实际resolved（例如root），macro setFormat成功的来源必须记录；被拒绝不改变配置/来源。受支持PreInit scoring命令改变依赖时，auto应读取最终标志；初始化后格式/计分修改继续拒绝，所有worker选择一致，重复run保持命名和真实格式。

输出代理独占 OutputManager/EffectiveOutput/OutputMessenger 及 `scripts/test_output_auto.py`；增加 `Format::Auto`、`GetRequestedFormat()`、`SetAutoFormatSelector(std::function<bool()>)`、`FormatSelectionReason()`。GetFormat/Writes*返回/使用实际格式；auto没有selector时明确拒绝而不是猜测。Clone共享只读selector，由主负责人绑定SimulationManager的最终scoring enabled/hits/event标志；应用运行期间这些配置不可变，不使用Geant4 RNG。schema/GUI字段描述代理只改schema源并运行生成器，默认值保持csv，勿手改生成产物。

主负责人负责SimulationManager绑定selector、摘要/capabilities、测试登记、文档。既有GUI编辑器若无format控件，不借此扩大J2范围；外部INI/宏与schema检查必须接受auto，实际来源面板展示requested/resolved和选择原因。

验收必须覆盖：省略字段仍csv；四种显式模式；scoring禁用但残留hits/event默认真时仍csv；hits-only/event-only/聚合-only；macro改变scoring/format顺序；初始化后拒绝且来源保持；1/2/4worker、多run、ROOT/CSV真实文件与元数据及有效配置对应；新/旧schema与GUI writer支持范围。首个来源提交和本格式决策分开，完整冻结验收仍一起执行。
