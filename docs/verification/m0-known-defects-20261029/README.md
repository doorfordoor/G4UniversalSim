# 当前分支已复现的两项遗留缺陷（未修复）

代码提交 70a1aba；复用本轮已构建的 Windows / Geant4 11.3.2 后端。根据独立审查在隔离目录重新运行两个 1 事件病例，结果见 [results.json](results.json)，原始日志在 logs，文本摘要随附。它们是缺陷复现证据，**不是通过的回归报告，也不是修复结果**。

1. csh 中拒绝 setMainConfig 后继续执行，退出 0、status=completed、interactive_command_failure_kind=none，仍使用 1 MeV；请求的另一个配置为 7 MeV。
2. run_metadata.json 预先被目录占用；运行退出 1，但文本摘要仍为 completed / program_exit_code=0 / summary_write_status=completed / output_failure_status=none。复核时目标确为目录。

两病例不在现有统一平台 89 项中。因此本轮 89 项通过不能证明没有这些缺陷。修复时应新增正式反例测试并验证首因、退出码、摘要、生成文件清单一致。完整热切换是另外的功能设计；此处确认的是拒绝/写出失败传播缺陷，不授权将重复 Configure 当成安全热切换。


摘要归档副本仅作 CRLF→LF 换行归一，字段与内容未改；原始字节与归档字节 SHA-256 对照见 [summary-hashes.json](summary-hashes.json)。原始文件仍保留在本机 out/verification/m0-confirm-20261029/。这两份缺陷摘要不属于 89 项通过报告中的日志。
