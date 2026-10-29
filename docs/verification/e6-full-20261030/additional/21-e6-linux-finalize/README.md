# E6 none_dealloc 最终定位与窄修复证据

本目录保留5bf冻结源的复制件、失败/对照日志及最终targeted，不覆盖三份真实CI失败报告。

## 实证根因范围

- CI三例均393断言后finalizing none_dealloc、exit-6，无Python frame。M0安装日志直接核验PySide6/shiboken6 6.12.0；两Geant4 leg未直接打印绑定版本，不把推断当直接核验。
- 现有WSL `/home/u123/g4ci/bin/python`为Python3.11.18、PySide/shiboken/Qt6.12.0；未安装任何依赖。本机Windows为Python3.11.9、PySide/shiboken6.11.1。不同版本不用于断言“Linux特有”。
- 微实验无MainWindow/Matplotlib/Geant4，缺失QComboBox currentData/itemData各500次使None引用数各减500；字符串role/currentText等不减。显式正常控件释放并处理DeferredDelete后仍none_dealloc（WSL桥接exit134）。`wsl-getter_refcounts.log`。
- 等价model role-map读缺失/无选择/有值各500次变化0，自然exit0。`wsl-getter_refcounts_safe.log`。不是增加None引用、强制exit、吞异常或丢字段。
- sampled完整复制件：original打印393后exit134；仅主动清理顺序未修复且得到不同139退出；safe getter复制件自然0/393。额外清理139没有native backtrace，不能断言其具体C++根因，也不将它混成原none_dealloc；未合入清理补丁。
- 无采样safe getter复制件额外两次自然0/393，见natural-confirmations.json。全部原assert AST逐项相同，见assert-preservation.json。

## 产品范围与限制

不同写者已确认PlotPanel.current_dataset、ScanPage.current_metric在正常默认空数据状态各1000次None引用数减999，故不能只改harness。产品未观察单次点击崩溃，不能把线性损耗夸写成单击必崩。

公共`widgets/qt_data.py::combo_data`按rootModelIndex/modelColumn定位当前或指定行，invalid index直接返回Python None，读取标准Qt model.itemData角色映射。保留0、False、空字符串、普通容器、Unicode和实际UserRole；不宣称任意自定义model动态role或全部QVariant问题都等价。

已接明确会空的路径：plot当前dataset、scan当前metric及refresh_results/首次refresh_base、EffectiveConfig快照/基准选择与module初始化、setup几何token初始化。稳定有显式值的wizard/scenario/migration/default-view等未机械替换。

诊断还显示嵌套容器`{'x':None}`的底层QVariant转换仍可损耗引用；该事实保留在候选实验日志，不把role-map宣传成完整绑定修复。当前已证实缺失角色路径已闭合；未新增业务数据/实体能力或pin依赖。

## 最终正式targeted（全部自然退出0）

- 新`smoke_qt_combo_data`：Windows/WSL均29断言；缺失role2000次、真实Plot/Scan方法各1000次None变化均0（正式断言允许小于10的跨GC噪声，仍严格识别原线性丢失）。覆盖0/False/空串/容器、自定义root与column、其他role、invalid/current=-1及一次真实refresh_results。
- 原`smoke_project_import_projection`：Windows/WSL均393，全部旧assert AST一致；未改退出机制。
- WSL相关：plots34、scans58、effective_config22、effective_config_collection42、config_editors33，均自然0。tracked-targeted-results.json、related-results.json及对应raw logs记录。
- compileall gui和相关diff空白检查通过。root登记gui_qt_combo_data，最终134清单；新SHA/CI/full由root冻结后重跑，不冒充已验证新CI。

前端当前tracked编辑已停止，无运行会话、无桌面操作，可供root preflight/freeze。
