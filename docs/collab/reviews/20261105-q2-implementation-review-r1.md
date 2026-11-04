# Q2-2独立反例与限定修复

Q2-2独审发现比较器会在缺少完成运行证据时给pass。独立C盘反例只删除IMP-FLU-01输出副本的run_summary.txt、run_metadata.json，比较器仍exit0/status=pass。证据out/collab/q2-independent-review-v1/counterexample.json，原比较器SHA64b3670fb406aaf6974c34e4950e46ccd6187dba53e60f3560d35fd708ce5f5c。限定修复仅当前比较器/篡改测试/回执。
为每例在算术结论旁加入实际运行证据校验。优先复用现有gui/g4usim_gui/core/run_result.py与产物清单逻辑，至少要求摘要/metadata存在且当前协议完整，status=completed、summary_write_status=completed、output_failure_status=none、唯一run计划=完成=冻结N，且scorer N匹配。核验实际被比较文件确属metadata声明且原字节SHA匹配，缺表/缺事件不能给总体pass。错误要输出明确失败项，不能异常退出后缺少结果。
增加删摘要/删metadata、失败摘要、零或少完成事件、陈旧或损坏产物反例。原数值反例仍要证明独立算术可发现错误：可在副本中刷新对应manifest摘要来隔离“哈希一致但数值错误”的检验，不改原产物，也不降低正常门禁。
修复可复用现有已完成模拟输出自测，无需重跑未变物理。完成后写原outbox/20261105-q2-implementation-v1.md，停止写入交独审。仍不改产品源/正式测试或CI，不扩建工具。
