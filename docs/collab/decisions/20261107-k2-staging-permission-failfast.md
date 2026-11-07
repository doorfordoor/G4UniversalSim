# K2-2 staging权限拒绝：有限修复

2026-11-07。阻断项仍为原K2-2的写出失败/R12语义，不新增清单。Windows探针在明确独立目标 `D:/k2-work/20261107-k2-41991fc6-windows` 下无输出，300秒预算后仅结束本轮自有CLI。另一次45秒有界诊断在15秒取得真实栈：`export_project.py:1790` 的 `tempfile.mkdtemp` 停在Python3.11 `tempfile.py:392`。

本机stdlib源码确认：Windows mkdir收到PermissionError且父目录isdir/os.access声称可写时，mkdtemp会继续尝试TMP_MAX个随机名称。原探针299秒已有286秒CPU，而无staging或目标生成。这是已证的权限拒绝重试路径；不能推测其底层ACL/执行限制原因，也不称导出成功。所有自有原CLI/launcher已核退出，原目标和诊断目标均不存在；未关闭其他程序，未改系统、权限或凭据。

证据在 `out/collab/20261107-k2-implementation/independent/`：`windows-cli-timeout.json`、`windows-cli-diagnostic-stderr.log`、`diagnose_windows_cli.py`。此前两份Windows测试失败和LinuxGUI成功分别保留。

最小范围：`core/export_project.py` 该staging分配与原静态专项的R12注入，必要独立回执。新K2入口不得使用会将权限拒绝视为名称碰撞而长时间重试的分配方式；可用本次独有UUID名称和exclusive mkdir，仅真实FileExists碰撞作预定小次数尝试，其余OSError立即按R12拒绝。保持原父链/源目录隔离、不覆盖和owned cleanup语义，不改K1/发布器/物理代码、外部目录权限或其他未经观察的分配点，不引入通用框架。

停止条件：权限拒绝注入时次数有界、及时产生R12、目标及本轮staging均不存在，原正例/P3与R1-R12保持；LinuxGUI/导出专项复验后即回K2-3。此修复只保证诚实拒绝，不能据此声称获得对被拒路径的访问权限。Windows实际独立构建运行仍由K2-3另核，不降标放行。
