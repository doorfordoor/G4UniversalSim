# Q2-6 Windows GUI恢复测试时序修复独审

2026-11-06。DeepSeek turn82 completed，deepseek-flash/max，round99。仅现有smoke测试修改，产品实现不变。

原失败：1fa1a6e5 / M0 run42054193736 / Windows job127337983931，固定300ms输入循环后断言异步写入回执已完成。最大定时器触发和I/O完成没有相同时间保证。

独审结果：
- 实际注册用例gui_f5_recovery通过，65/62入口、1pass/0fail/0skip；out/verification/20261106-001813-b4257006/report.json，严格证据门禁通过。
- 独立迟延publish 1.2秒：连续输入期间捕获revision5启动，实际回执随后完成，flush最终revision21通过。
- 独立禁用maximum：debounce5000ms，明确触发maximum未启动的断言，不能靠停止输入后debounce或flush通过。
- 负控/迟延记录out/collab/desktop-bridge/q2-ci-recovery-independent.json。原回归全部其余检查保留；不新增工具或生产功能。

修订可接受，提交后观察实际云M0终态。原1fa1a6e5的Linux双版本、安装双平台与桌面均success；原Windows M0失败保留。测试变化不要求重复冻结科学实验，不能把本机通过代替云终态。
