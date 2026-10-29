# Qt缺失UserRole读取：产品风险与窄补丁建议

只读/out实验，未改tracked；Windows正式full仍由root接收终态，不用os._exit。证据out/verification/e6-combo-role-map-review。

## 先给结论

不能只改测试。已在冻结产品**默认有效状态**找到两条可重复的None借引用损耗路径：
- widgets/plot_panel.py:202-204 current_dataset()，新项目/未加载结果时dataset_combo为空，正常返回None；1000次真实产品方法调用，None refcount24598->23599（-999）。redraw:293起每次先调用它，log_x/log_y/all_runs/per_event等界面选项均连接redraw；正常空数据刷新也能触发。不是靠手工破坏combo索引制造。
- widgets/scan_page.py:259-261 current_metric()，尚无扫描结果时quantity为空，正常返回None；1000次真实产品方法调用，26545->25546（-999）。refresh_results:233-243在空结果时先读currentData并保持空combo，后续绘图/不确定度/导出路径也读取current_metric，重复空/失败/未完成扫描结果刷新会进入。

上述1000次有限产品调用两个进程仍自然exit0，所以不把它们夸写成“已观察单次用户点击崩溃”；引用计数的线性损耗已实证，累积收尾风险与最小QComboBox独立崩溃同源。product-paths.json记录结果。

## 不是所有30个点都同样危险

- EffectiveConfigPage.module_filter的All modules使用**空字符串userdata**，不是None！默认产品1000次currentData读取得到''，引用计数5596->5596、exit0。不能错误把它当成长期热路径。_refresh_module_filter:275初始化空combo时存在一次None读取；_snapshot_selected/_baseline_selected若接到-1或清空瞬态也有缺失role读取，但rebuild通常blockSignals。可用同一窄helper防护，不声称已证明频繁用户触发。
- setup_panel._geometry_template_token:304在首次populate前可能读空combo；稳定后的几何选项都有显式token userdata，空template走hierarchical规范化，不是一直None。可在此加入同helper/invalid-index纯Python短路。
- plot.view_combo的Default有显式'default'；scan parameter/quantity有数据时均用字符串key；wizard/scenario/migration选项均有显式userdata；pyvista All events的userdata是整数-1，section None使用字符串轴值。没有证据支持为这些正常有效值机械替换或pin依赖。
- E6改为setCurrentIndex(-1)的source/physics/材料/几何普通文本combo，产品编辑回写主要用currentText()，不会直接通过本次缺失currentData路径。新测试widget_state大量读这些无UserRole的控件暴露了问题；不能说所有空选项业务都新增了同一产品崩溃。非法索引仍应由shared helper安全覆盖。

## 等价role-map与自然退出证据

out/collab/e6-combo-role-map-api-review.py用model.index(row,modelColumn,rootModelIndex)再model.itemData(index).get(UserRole)，避免对不存在的role走QVariant->None返回。无数据/显式None/无选择/越界行、0/False/字符串/整数/浮点/列表/字典，以及自定义modelColumn和root均与原API有界对照一致；10000次压力loop None refcount5393->5394（无逐次下降），Python3.11.18自然exit0。

对冻结原smoke仅在out复制件替换widget_state内两处读取；每个原assert AST逐一相同。通过原v3探针连续5次均ok、G4USIM_ASSERTS=393、进程exit0、无none_dealloc。candidate-results.json完整保留。不是删除断言/屏蔽退出码/降低标准。

## 最小范围建议

共享一个UserRole读取helper，保留modelColumn/root/index/当前项语义和返回类型。优先接入已证实空数据热路径plot.current_dataset、scan.current_metric/refresh_results，以及测试的无UserRole状态快照读取；再按明确None/invalid-index可能性接effective_config上述选择/初始化、setup token初始化。对于已知总是显式字符串/整数userdata的稳定点，不需要无证据全面重构。

也可对默认模型明确缺选择时先纯Python返回None，但这不足以处理“索引有效但根本没有UserRole”的通用状态快照。测试必须保留真实值/None/0/False等语义与全部旧业务断言，在现成WSL3.11环境正常解释器退出；不得强制exit或只看393。role-map仅是已测Qt标准模型方案，额外自定义模型/复杂userdata不应未经验证泛化。
