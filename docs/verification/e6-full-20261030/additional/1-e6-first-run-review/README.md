# 首轮Windows原报告独立复核

原报告out/verification/e6-full-windows/20261030-002736-c9ff9815/report.json，head cb837e680e08a66dd47e62a9ee7e25fa125026c3，运行记录git_dirty=false。结果126pass/1fail/0skip，共127项；失败gui_start_page，原记录exit_code=4294967295、assertions_executed=null。不要把本机记录写成CI的600秒timeout（本机原report没有这个reason）。

严格门禁退出1：有失败case，不能发布为release证据；--allow-incomplete仅诊断模式退出0，说明所执行断言计数/日志等报告内部约束通过，不代表用例通过。总v3入口41462，与逐项求和一致。全部127份原日志raw-byte SHA256与原报告相同，缺失/哈希不匹配均0。

原report核验前后SHA256均49af2b68722952308eb42ad0a4d413942d67b5da3c763d2572a23ed22284443e；未改任何原报告/日志。head、source指纹、tests指纹、127例集合均与首轮CI冻结清单一致。

review.json为结构化结论；raw-log-hashes.json逐个列哈希；strict-gate.log与triage-allow-incomplete.log保存实际门禁输出。首轮CI仍完整保留于out/verification/e6-ci。
