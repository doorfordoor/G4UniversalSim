# 已实现的snapshot适配API（frontend接线）

`from g4usim_gui.core.project import load_project_snapshot`

返回`ProjectSnapshotLoad`：

- `.project`：待发布的G4USimProject；frontend仍先`_check_project_projection`，再`_set_project`。专用snapshot入口才调用本API，普通Open/Recent/迁移副本Open不变。
- `.notes: tuple[str, ...]`：legacy普通项目/标准包恢复范围、未输出草稿/无旧hash/main-macro及runtime边界、已识别旧duplicate路径对等说明；可在成功后日志/状态/消息区显示，不要误报为完整运行恢复。
- `.package_root: str`：标准包根；legacy普通项目分支为空串。
- `.inputs: tuple[SnapshotInput, ...]`：本次读取role/path/sha256，普通项目分支为空；哈希只证明本次读取，不证明历史run原字节。
- `.snapshot_sha256: str`：原snapshot实际读取字节sha。

无任一envelope key的legacy普通项目按原strict project规则读取，保留原normal-project行为并notes“仅编辑参数、原资源/历史未验证”。只要出现任一已知envelope key就必须完整package适配，partial不回退。unknown/future/type/duplicate/nonfinite一律拒绝。

标准包模式：实际材料/几何/main/macro在同包标准layout必须存在，escape/symlink出包拒绝；旧duplicate材料和几何路径仅允许同一旧包标准后缀的**成对**遗留值且不读旧路径。返回generated模式，flat run镜像由记录的runSettings对齐，当前runsRoot映射到本包父目录，configPath/macroPath/outputDir清空，几何从包内文件读取，材料路径指包内配方。只从实际geometrySourceMode和严格geometryDocument保留已明确的source_copy_mode，不自动绕过blocker。

`materialDocument`原producer是摘要，没有配方文本；只验证闭合结构和计数，不伪造disabled行/草稿。恢复的是包内**当前**材料几何+快照记录S/P/S，不是已手改main/macro、最终EffectiveConfig或历史结果。需要重新生成/运行。

静态专项`scripts/test_project_snapshot_compat.py`已执行通过（真实writer→专用load→普通save/load→再generate，metadata拒绝与旧duplicate pair不读旧源）；backend链正在追加既有integration脚本。没有修改前端窗口文件。
