# E6 frontend导入guard不同写者只读复核

## 受检补丁结论

**当前frontend guard改动可提交。** 本轮只读产品/正式测试，独立脚本在新目录保存结果；原始修前证据未覆盖。`review.json`记录6个受检产品文件SHA，审查前后相同。独立88项通过，`smoke_project_import_projection.py`与`smoke_config_migration_ui.py`分别退出0；三份日志均保留。这是offscreen程序化检查，不是可见窗口或物理验收。

- `window/project.py:53-76`：实际SpinBox受检字段完整覆盖Project flat threads、Config run threads/events、scoring settings bins、editor bins/trajectory、source rays/preview seed。editor bins同时送入0下界editor和1下界summary，因此交集1..1e7是实际GUI表示边界。读取实际min/max，不试setValue、不限幅。
- `widgets/project_page.py:128`、`config_builder_page.py:198/200/222`、`widgets/config/run_config.py:355/356/369/372/488`实际赋值逐项与guard相符；setup_panel的flat run defaults只从已受控Project页来，向导调用前路径也有覆盖。
- 两个输入模式下八字段的下界-1/上界+1/正负巨整数，共64例，均在发布前拒绝；旧对象、路径、源字节、SpinBox/LineEdit/Combo/Button状态、两个_building、editor对象身份、运行包stale/dir均保持。直接调用_set_project的异常候选也不能绕过首行guard。
- 八字段的实际上下端点16例通过。runSettings.seed、scoringEditor.verbose、BooleanOperationRow.index等字符串/未投影整数未被错误施加Qtint32限制；显式editor存在时闲置scoringSettings.trajectory_events也没有多余限制。
- `window/project.py:163-175/265`：普通Open critical、Recent warning及原原标题、Snapshot warning及原原标题已分别实测；不存在文件和非法数值均保持旧状态。迁移副本写完不切对象，显式open成功才切路径；失败open和Save As路径由正式migration smoke实测覆盖。
- `window/content.py:44-54`：向导先深拷贝候选，将Project页值和同一个WizardResult应用至候选后预检，再走既有in-place路径。threads=1025、events=2e9+1被拒绝且原状态不变；有效3threads/17events实测捕获两次guard，受检值完全一致且project identity保留。没有因为新增guard引入先改活对象再失败的回归。
- 缺省/旧类型兼容先由core完成，guard只看实际候选；未知枚举不新增白名单，空combo现在显式无选择。不能宣称所有IO/Qt异常都有一般事务回滚；当前结论是已知可预测投影和入口严重级别闭合。

## 额外确定兼容缺口（不是guard新引入）

**P2：真实运行包snapshot尚不能被当前Load Snapshot into Project消费。**

定位链：`writers/package_writer.py:214/241-253`的真实`_write_snapshot`在规范项目JSON上增加`runPackage`、`materialsSourceMode`、`geometrySourceMode`及后续摘要/文档；`window/project.py:217-219`的快照入口仍调用普通`_load_project_path`→`load_project`→`core/project.py:90`类型/未知字段门禁，所以先遇`runPackage`就拒绝。

独立脚本`out/collab/review-e6-writer-snapshot.py`实际调用原writer（未手写删减fixture）生成`real-writer-project_snapshot.json`，随后loader返回`Unsupported project field: project.runPackage`；原件SHA前后不变。结构化结果`writer-snapshot-review.json`。现有`smoke_history.py`用只有schema/version的手写snapshot，仅测试扫描/复制，不覆盖真实writer→loader；本次projection smoke的snapshot检查也只证明拒绝的severity和状态保持，不能外推真实运行包快照能重载。

此问题与guard补丁独立，不能把安全拒绝当作兼容功能成功，也不能用全局过滤未知字段修。建议主负责人裁决一个明确的known package-snapshot envelope适配入口：只消费/验证已知元数据，保留future/unknown拒绝；或者明确当前入口不支持真实运行包snapshot并校准产品。是否同轮修复由主任务裁决，本审查未修改core或前端以避免越权。

## 证据

- `review.json`：88项独立检查与受检产品SHA。
- `out/collab/review-e6-frontend-guard.log`：独立脚本退出0日志。
- `formal-projection-smoke.log`、`formal-migration-smoke.log`：当前正式smoke退出0。
- `writer-snapshot-review.json`、`real-writer-project_snapshot.json`：真实writer额外反例。

不改变首轮126pass/1fail事实，不把本审查或当前专项算作新冻结全量/CI/实窗通过。
