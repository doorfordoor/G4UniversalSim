> 2026-11-01 修订：下面原审查的“提前解析无新增语义变化”及“初始化顺序修正有效”结论已撤回。提前Path改变了K1 records_root，原绿例并非相同业务范围；当前有效结论见文末“纠正与最终复审”。保留原文仅为审查历史，不能再引用其原结论关闭阶段。

# J1 默认恢复目录初始化顺序 / 退出生命周期窄独审（2026-11-01）

结论：MainWindow提前解析默认恢复根是范围很小、保持实际路径与恢复功能的初始化顺序修正；独立对照支持它改善当前复现，但不足以证明底层Qt所有权根因已经定位。不能归因于QStandardPaths本身。当前源码注释已在审查期间改为default-root boundary ordering，较先前Qt调用归因准确。另发现self_test关闭拒绝后仍deleteLater的生命周期缺口，建议一并处理或用明确收尾契约覆盖。

## 修复逻辑与后果

main_window.py:33-43仅在recovery_root is None时调用原default_recovery_root并提前传给后续RecoveryController；显式根不变，环境变量G4USIM_RECOVERY_DIR和原Qt/系统回退不变，没有改存储根、关闭恢复、改dock父子关系或跳过F5事件过滤器。RecoveryStore的目录创建、租约、自动保存仍在原位置。新增解析发生于QMainWindow构造前，不读self状态；未发现该小改动新增的路径选择/项目/F5语义后果。

但旧路径inside RecoveryStore默认解析与早解析的时点不同，可能触发Python/Qt包装器、queued回调、eventFilter等的不同状态；仅调整顺序不等于证明这些机制均无缺陷。根任务指出r2/r3均显式G4USIM_RECOVERY_DIR的反例符合源码install_layout.py:80-82：存在override即直接返回Path，根本不进入QStandardPaths。因此不能说Qt writableLocation是必要原因。

## 独立离屏矩阵

只用D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe、offscreen；未操作实窗。产品代码未修改。探针将早解析第一次调用返回None，迫使同一默认函数仍在RecoveryStore边界解析，模拟原晚路径；其他产品行为保持。隔离history/QSettings，offer_recovery=False，恢复仍启用，接受close后才DeferredDelete。

有效v3结果：out/collab/recovery-order-v3-review-evidence.json；脚本review_recovery_order_v3.py及run_review_recovery_order_v3.py。

| 条件 | 退出 | 观察 |
| --- | --- | --- |
| early + 显式环境变量恢复根 | 0 | close接受、DeferredDelete、processEvents完成 |
| late + 显式环境变量恢复根 | 1 | close最终接受、无recovery错误；DeferredDelete后processEvents报MainWindow already deleted |
| early + 默认Qt解析根 | 0 | 同上正常 |
| late + 默认Qt解析根 | 1 | 同上删除后包装器错误 |

晚路径在无任何QStandardPaths调用时也失败，直接否定“仅Qt路径API导致”的过强归因。该独立复现错误为Python RuntimeError，不能冒充root旧日志0xC0000005的同一C++根因；它们只共同表明晚边界可触发生命周期失效。没有符号化native栈、对象销毁trace或最小Qt-only复现，不能判定已经排除所有权问题。

保留的v1/v2探针不能用于归因：v1对首次close()返回false直接assert，随后异常退出混入native AV；v2虽等待close，但在构造中QApplication.topLevelWidgets枚举会额外暴露包装器。v3已去掉该枚举并有界等待关闭，结果按上表独立列出，不覆盖旧失败历史。v1/v2的移除eventFilter/空eventFilter分支也因这些混杂不能作为过滤器因果证据。

## P2：self_test对close拒绝仍执行deleteLater

定位gui/g4usim_gui/app.py:92-97：window.close()返回False仅把report标为失败，随后无条件deleteLater并sendPostedEvents。产品closeEvent可因持有进程、experiment动作/服务或恢复尚未收尾而ignore；此时删除widget树绕过其保护，存在任务尚持有窗口引用时触发同类销毁错误的可能。独立探针首轮也实际观察到close未立即接受；改为有界processEvents并重试后可接受，因此不能将close拒绝简单等同不可恢复的窗口坏状态。

建议self_test遵守产品close接受边界，给现有owner有界收尾机会；若超时保持明确失败并给出未收尾事实，不把未接受close的树当正常退出对象立即销毁。新增负例应模拟close第一次拒绝后异步接受，以及持续拒绝，检查不提前DeferredDelete。这里不要求改变正常产品ownership或禁用恢复，也不建议捕获/忽略RuntimeError或os._exit。

## 完成声明边界

可将早解析作为已复现有效的顺序修复候选，但正式回归应保留实际defaultStart、显式env override、显式root、正常与恢复窗口、show/close/deferred delete、自然进程退出及当前完整selftest（含language/PyVista）覆盖。当前有限绿不能关闭J1；冻结包、DPI/运行中操作与正式矩阵仍由主任务闭合。

## 纠正与最终复审（2026-11-01，替代上文结论）

### 撤回与原因

明确撤回本报告原“未发现新增语义变化”“可将早解析作为有效顺序修复候选”两项判断。审查遗漏了window/experiment.py:73-74：_recovery_root为None时传records_root=None，ExperimentWorkflow沿项目runsRoot选择experiment-records；提前解析为Path后转到recoveryRoot/experiment-records。恢复文件路径可能相同，但K1历史目录范围已经改变，空历史目录让异步历史加载/关闭路径更容易跳过。前轮early/late矩阵也比较了这两个不同历史范围，不能归因于初始化先后，更不能用于排除ownership问题。

原探针及结论全部保留历史，报告开头已加撤回声明。G4USIM_RECOVERY_DIR不调用QStandardPaths的反例还独立否定了其必要因果归因。这里不是把错误结论仅改成弱措辞，而是撤回该产品方案；当前main_window.py已完全移除pre-resolve，原参数None语义保持。

### 当前实现复核

- main_window.py:33起直接super，75行保存原recovery_root参数；window/experiment.py:73-74原分支不变。默认None再次使用项目runsRoot历史；显式root才使用其experiment-records。
- app.py:41-60的_close_self_test_window先走真实window.close。拒绝后仅pump Qt事件，等待产品ExperimentWorkflow.close在所有EvidenceJob排空后emit closed，再由产品回调完成正常关闭。只有已接受或原先shown窗口已隐藏时才deleteLater/DeferredDelete；超时返回False，不显式删除窗口树。
- 本入口self_test必先show，且无用户交互或另外hide步骤，因此not isVisible作为产品自发接受关闭的判断在此窄用途合理。该helper不是任意未显示窗口的通用销毁API。
- self_test:83-88隔离QSettings/history/recovery文件，98行仍MainWindow(offer_recovery=False)，没有传显式recovery_root而改变K1历史分支；只禁止交互恢复提示，不禁用恢复控制器。
- finally超时报告okFalse、保留state_directory，正常关闭才移除测试状态；127行报告exclusive写入，旧证据不覆盖。helper超时“对象仍活着”指此函数边界，没有把它夸大成任意native bootloader崩溃都可控。
- build_package.py:146/150、167/171已按os.name==nt限定环境清理与Windows二进制审计，Linux复用freeze入口保持原继承环境；windows_freeze模块本身只导入跨平台标准库，不因导入就执行Windows操作。

### 独立复验与证据

原venv D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe，QT_QPA_PLATFORM=offscreen，未操作实窗/未改产品。

1. smoke_workspace_layout.py --default-start-lifecycle：无override和显式G4USIM_RECOVERY_DIR各独立进程退出0，日志j1-review-current-default-none.log / j1-review-current-override.log。审读测试确认真实ProductMainWindow._recovery_root is None、experiment.records_root等于project.runsRoot/experiment-records；真实_history_job用Event阻塞，0.03s关闭超时后窗口有效/可见、destroyed0；释放gate后正常接受关闭，destroyed1且wrapper无效。覆盖隐藏docks、中文和可选PyVista导入，未减少旧覆盖。
2. 源码产品gui/main.py --self-test独立退出0：j1-review-current-selftest.json/.log，9页、plots true、preview3d true、中文参数扫描、ok true；这次使用撤回pre-resolve之后的代码，不靠切到空recovery历史目录通过。
3. scripts/test_frozen_startup.py再次独立退出0，保持启动ImportError报告/非零退出和原证据保留负例。
4. 原j1-default-entry-deferred-close-wait.log中closeFalse/visibleTrue/busyTrue/service_waitingTrue/close_pendingTrue，正常eventpump后visibleFalse再析构exit0；与当前真实history gate测试吻合，直接支持“忽略close拒绝而强制删除未排空owner”这条故障链，而非路径API因果。

### 当前审查结论

前报self_test拒绝关闭仍强制删除P2已由当前helper及真实异步反例闭合，本轮窄范围未发现新阻断缺陷。pre-resolve必须保持撤回，不能重新引入作为稳定化方案。支持按本故障链修复后的正式矩阵与冻结包继续验收，不宣称所有Qt内部所有权问题已证明不存在，也不由本次源代码selftest关闭完整I2/J1阶段。
