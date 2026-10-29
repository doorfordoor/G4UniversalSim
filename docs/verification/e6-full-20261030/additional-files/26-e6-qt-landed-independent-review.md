# Qt缺失UserRole修复：不同写者正式复核

结论：本次窄补丁可提交，无需为已明确赋真实userdata的全部combo机械改写；最终阶段验收仍等新冻结及真实CI。未修改tracked文件，无os._exit、未绕过退出码、未删除业务断言。原5bf失败证据保持原样。

## 实际代码与语义

qt_data.combo_data保留currentIndex/显式row、rootModelIndex与modelColumn，再对有效模型索引的role map取int(role)；无效索引直接Python None。产品接入plot.current_dataset、scan.current_metric/refresh_results/parameter初始化、effective_config选择/初始化、setup geometry token；下游原有None/字符串处理保持。原导入smoke仅替换两处状态读取。

独立脚本out/collab/e6-qt-landed-independent.py检查0、False、空字符串、NBSP字符串、float、list、dict、tuple及自定义Python对象（保持类型、值、自定义对象身份），显式None、缺失role、-1/越界行；另自定义QStandardItemModel树根/第1列及DisplayRole、UserRole+1=False，均通过，未改变选择/root/column。本次不外推为任意自定义QAbstractItemModel或任意嵌套QVariant转换的修复；现有产品未发现自定义combo模型接入。

## 实际运行

WSL Ubuntu现成Python3.11.18、PySide6 6.12.0，offscreen，未安装依赖。证据out/verification/e6-qt-landed-independent：

- semantics_product：自然退出0。helper缺失role/无选择、真实PlotPanel.current_dataset/ScanPage.current_metric各预热后分3批、每批2000次读取，所有批次None引用增量均0。使用相对增量、有界噪声容差，不断言任何绝对计数。
- formal_helper_final：当前正式smoke_qt_combo_data运行前后source SHA相同；自然退出0、29条v3断言，包含实际product两方法与refresh_results空态，三个记录增量均0。正式测试采用前后差值<10容差，不锁死绝对计数。
- 原smoke_project_import_projection全部assert AST逐项与5bf冻结版相同；实际tracked文件通过原v3探针连续3次自然退出0，每次393条断言，无none_dealloc。仅既有缺CJK字体warning，不是退出失败。

results.json保存各进程退出码、原字节stdout/stderr SHA与断言marker；formal-helper-final.json保存最新版正式专项的前后源码SHA和输出；source-identity.json登记审查源码身份。旧的out候选5次通过记录与本轮tracked验证分别保留。此前Windows55580整轮133通过是5bf历史身份，不冒充当前补丁完整验收。

## 下一步

等root最终SHA与push后，以实际runner动态manifest冻结并采集到out/verification/e6-ci-release。当前新增gui_qt_combo_data使预期总数134，但collector不硬编码该数字；要求双workflow实际完成、4官方ZIP digest、12正确profile分布、双指纹/名单一致及全部严格门禁。未触发或重跑任何workflow。
