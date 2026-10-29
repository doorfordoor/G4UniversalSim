# E6 主审实际窗口观察（2026-10-30）

实现基线 a779634，执行检出 838e2e3；两者产品和测试指纹相同。用户明确回复已解锁后执行。主审通过 computer-use 26.1023.51421 的 node_repl / @oai/sky 获取真实 Windows 窗口截图并直接查看；截图不是 Qt 自渲染图。程序化 Qt 驱动与原生输入分别说明，不声称真人逐项点击。

## 已观察的八个状态

1. `01-migration-preview`：实际迁移窗口显示项目 v5→v6、三条改动、格式检查不等于模拟/物理验证的提示。写入新副本可用、打开新项目副本禁用。原窗口及对话框两张截图。
2. `02-migration-cancel`：主审用原生按钮打开保存选择，看到建议新文件名，按 Escape 取消。回到同一预览，打开新副本仍禁用；文件检查确认未产生建议目标。保存选择含系统导航侧栏，未归档该中间截图。
3. `03-migration-refused`：程序化真实产品调用先写出新副本并检查不切换当前项目，再拒绝原文件、占用目标、源硬链接；未来/损坏文件清除旧计划。实际截图观察损坏 JSON 报错，空预览且写入按钮禁用。此前三个目标拒绝的具体信息以 receipts 为据，并非三张各自实窗截图。
4. `04-snapshot-restored`：消息页实际显示须重新校验生成；明确未恢复主配置/宏手改、未输出草稿或历史成功。材料 1 项、几何 2 体积，无已生成运行包。树中线程与事件均为 2，种子 246；源能量 7 MeV 可见。
5. `05-snapshot-materials`：主审点击材料标签，实际表格显示 Mix、mass_fraction、2.8 g/cm3、Si:0.25/O:0.75、OK。原包外源已变化的反例与同包当前文件读取由程序化断言证明。
6. `06-snapshot-geometry`：主审点击几何标签，实际表格显示 world 与 Target，Target 属于 world、材料 Mix、位置原点，尺寸列可见开头 3 mm/4 mm；完整 3/4/5 mm 由模型断言及重新生成字节比对证明。表格可横向滚动，不把裁剪部分称为截图完全可读。
7. `07-duplicate-range-refusal`：实际窗口显示副本路径、已创建但未载入/未运行、1025 超出当前 GUI 的 [1,1024]。此消息是截获真实产品警告参数后由测试以非阻塞 QMessageBox 重建，不能冒称原模态调用的原生端到端证据。当前状态完整保持、未 Inspect/Run 由测试断言证实。一次 accessibility click 返回缓存 element unavailable，重新观察后 Escape 关闭；未重复复制或运行。
8. `08-real-run-result`：实际 Inspect→Run 使用已验后端。可见退出码 0、100%、运行 0 的 2/2 事件、模拟成功及后端终态日志。状态“未运行”是当前进程不再运行，与单列成功结果区分。实际 CLI 为副本线程 2、seed 43、writer_run，绝非另一项目 7/999。GUI结果与真实摘要另经独立验证。

## 方法边界与退出

六种合法 Duplicate 样本（普通43、seed缺省、0、旧snapshot/当前main冲突、Unicode尾NBSP、ASCII外空白）使用合成 Inspect 和截获最终 Run 命令，无模拟执行；第七种1025检查拒绝。真实2事件另走未替换的 Inspect 和 runner。程序化生成后的材料/几何与原包逐字节一致。所有58个准备资源保留。

主窗口PID10188写出closed收据后消失，WaitForExit完成；原始Start-Process对象未保留，因此GUI host退出码unknown，不能从进程消失推定0。真实后端正常退出0独立有证据。stderr仅出现合成未运行包缺metadata的legacy/unverified警告；未抹去这些记录。

## 补充的四个真实模态状态与结论

新建独立窗口 `E6 import acceptance a779634`（PID31088），未替换 QMessageBox。程序化调用真实 `_load_project_path`，主审以原生 Escape 关闭各弹窗；Recent 使用与其一行包装入口相同的 `recent=True` 路径。

9. `09-import-open`：普通打开越界项目，红色错误图标，标题“打开项目失败”，具体字段 project.threads、原始大整数及GUI [1,1024] 范围可见。
10. `10-import-recent`：同输入，黄色警告图标，标题“打开最近项目失败”，拒绝原因一致。
11. `11-import-snapshot`：同输入，黄色警告图标，标题“加载快照失败”，拒绝原因一致。
12. `12-import-envelope`：普通项目打开运行包专用快照，红色错误图标，明确 `Unsupported project field: project.runPackage`。

四次返回 False，当前完整项目、页面状态及58原资源哈希不变；没有后端进程。补充程序 `app.exec()` 返回0，执行会话8299最终工具返回 exit_code=0，独立于首个GUI host未知退出码；原始收据保存于import-supplement/process-exit.json。主审确认两自有GUI与真实后端均已消失，未停止其他应用。

共12个实际观察状态、20张原生截图；截图既包含主窗口又可能包含同次对话框，不代表20次独立测试。结合冻结全量与独立身份/收据复核，本阶段实窗门禁通过。本轮未修改产品或测试源码。发布后cleanup warning等专项仍使用已验正式smoke，不宣称本轮逐项实窗重跑。工程检查不扩张为物理基准、全DPI/可访问性或Linux原生桌面验证。
