# E6 冻结启动页模态回归复现

结论：确认为前端统一载入入口时改变了近期项目错误的弹窗严重级别，导致已有offscreen专项等待未替换的critical模态框。与Windows锁屏无关，也不是载入错误被忽略。

已按要求不改冻结产品/测试、不操作现有PID49116/70480、不操作桌面。复制`gui/smoke_tests/smoke_start_page.py`的原始字节至本目录`smoke_start_page.unmodified.py`，哈希相同；保留原`__file__`路径解析，仅用monkeypatch把`QMessageBox.critical`改为记录并返回Ok，原smoke自身仍只替换warning/information。

实际运行`record_critical.py`：退出0，`smoke_start_page: ok`，只捕获一次critical；标题`Open project failed`，内容为不存在`gui/demo_project.json`的FileNotFoundError。调用栈为启动页近期按钮→`_open_recent_project`→`_load_project_path`→critical。完整记录`critical-record.json`与原始字节日志`replay.log`。

这说明将真实错误保留为可断言的非模态记录后，原smoke所有gallery、项目、语言、文件未改断言均完成；没有通过忽略真实载入失败或改fixture来制造通过。原冻结源码哈希和复制哈希及`frozen_source_unchanged=true`已留存。

封存原冻结报告后建议修复：统一helper允许明确的错误展示策略；普通Open保留critical，近期项目恢复warning及原标题，历史快照恢复warning及原标题。新smoke同时记录warning/critical并分别断言调用入口与错误内容、原项目/路径/陈旧状态未改变。不要只给旧smoke补critical替换而保留无意的用户严重级别变化。

本轮仅复现与建议，尚未修改上述行为；等主任务封存后授权修复。
