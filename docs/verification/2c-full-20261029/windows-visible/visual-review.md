# f4770b0 最终 Windows 可见 GUI 复核

后端 source_fingerprint：c2b575bbb9c594765364aa7c78150e842ffb20ff34b10ad4729720bae2c8c91b。exe SHA-256：fbb7c56e820d3d36e5f87a3ef2995d55c554d4c5cb38dbaa75191422d4bc37f0。backend、capabilities、generate+review 整体进程均实际退出 0；本轮无重试、无夹具修复。

真实运行 2 runs × 4 events，2 workers，总 8/8 事件；14 个 configure/run/thread/finalization 快照全部保留并逐文件复核 SHA-256。输入、日志、摘要位于 backend/，完整机器证据为 backend.json、backend-capabilities.json、gui-report.json。

真实 Qt windows 平台、可见且 exposed 的主窗口完成 10 类程序化检查：集合选择、configure 基准差异、转义名搜索、未知/差异过滤、切语言保持路径、无效集合原子拒绝、切语言保留陈旧、整体 reload 恢复、浅/深主题、1500×950 与主窗口最小 1200×760。6 张原生 window handle 截图均已使用 view_image 实际打开查看，哈希记于 gui-report.json。

所见：中文浅色完整集合与差异文本清晰，英文深色过滤与失败诊断可辨；英文和中文陈旧提示没有被正常加载状态覆盖，中文浅色恢复图正确显示“已加载快照，仅供审查”。未见乱码或控件重叠；小窗长 selector 文本省略，证据列和长 JSON 需水平/垂直滚动，不能据此声称所有列同时可见。源 Manager 缓存 2 MeV 与原生 GPS 4 MeV 差异明确为 unknown，未显示为已应用或模拟成功。

这是程序化 Qt 操作真实 Windows 可见窗口，不是 offscreen，不宣称真人点击。偏好与历史隔离于本次测试组织名和本目录状态文件；自有窗口已关闭，所持 QProcess 全部 NotRunning。仅写 out/，旧 2c-visible 与 2c-visible-final 均未覆盖，未改 tracked 文件或产品。它是本构建/本输入的工程界面验证，不是一般物理有效性证明。
