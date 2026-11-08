# AR3 运行许可与持久证据：主审限定签收

当前主审接受以下两个有限切片；它们不构成AR3整体、MR1或跨阶段审计项全部关闭。

## 同窗口运行许可

普通运行、扫描队列及session入口共享同一许可。拒绝发生在验证、日志创建和starting信号以前；取消请求本身不释放，实际终止/启动失败收尾才释放，旧回调不能释放新进程许可。扫描点间保留队列所有权。

作者原始38个Python子进程、91次拒绝与有限PID采样经作者外核验；独审另执行8个真实Python子进程、80次断言，覆盖Crashed中嵌套finished、真实MainWindow共享接线、FailedToStart及三个受控负控。报告位于 `out/collab/20261108-ar0-ar6/independent/ar3-run-ownership-review/review.md`。主审随后正式静态/GUI矩阵的run_ownership通过，整报告与严格身份门见 `ar3-integrated-r2-tracked/static/20261109-014246-be8c9a67`。

这证明所测同窗口Qt线程内的准入/释放行为，不称跨窗口、跨线程或全系统锁；子进程夹具不是Geant4科学运行，MainWindow实例化也不等于OS视觉验收。原证据目录适配与作者旧脚本SHA分别记录，不回填历史身份。

## 持久运行证据服务及history接线

服务一次捕获摘要原字节并核读取稳定性，向现有判定器传同一解析结果；没有进程记录时保留summary_only，不从摘要补造exit0。状态JSON字段及重复键严格检查，history消费同一服务。

独审发现的冒号重复生命周期字段绕过、非对象状态JSON使history提前退出两缺陷已修。重复识别移到唯一parser词法分支，在覆盖字典前保留警告；历史元数据投影不再阻断严格服务判定。独立r3复验原44控制及10项parser控制全部通过，三项兼容测试exit0，源SHA首尾稳定。证据：`independent/ar3-persisted-evidence-review/REVIEW-r3.md`及其原始重放目录。主审正式static矩阵与严格身份门也通过。

v1进程记录仍只有mtime/size绑定，不冒充密码学进程身份。output provenance是另一证据层；AR4的scan消费者及状态模型接线尚未完成。因此接受service/parser/history切片及本轮两发现关闭，但AUD02跨阶段项仍开放。

原失败收据与旧独审结论保留。后续源码变化必须另定身份/影响范围，不能把本次结果改名为新候选通过。
