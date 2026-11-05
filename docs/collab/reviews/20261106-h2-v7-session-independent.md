# H2-4 V7 受控会话入口独立复验

2026-11-06。Windows/MSVC，Geant4 11.3.2，基线 e2117037，含 H2 未提交实现。独立执行的 exe SHA-256 为 0433d87766c93d803a8caf247f45dfea79a866cc2cb8f2e93d8fb91cfb48ad06，源码指纹 c4b2b588a59a7e3483c4cded16e717eb97210240eafcadc8e14236f5514039c6，与执行时工作区直接计算相同。

- 代码审查：SessionServer 的 run 分支先校验请求及内核状态，随后调用已存在的计分校验。失败先返回拒绝，再结束会话；进入 Running、登记重放运行、发送 accepted 和调用 BeamOn 均在校验之后。
- 原 V7 输入：hello、initialize applied、run(10) 返回 rejected/scoring_config_invalid，诊断含 muon。未关闭客户端输入即进程正常返回非零 1。摘要 failed、scoring_filter_particle、run_count=0、actual_completed_event_count=0，无 run_started/run_finished、运行收据、科学 CSV。原帧、日志和摘要见 out/collab/h2-v7-independent-r2/v7-records、v7.log 和 v7-output/run_summary.txt。
- 合法 V5：初始化后接受 100 事件，run_finished 实报 100，shutdown exit 0；摘要 completed，唯一非零谱格 bin 5 为 1 mm^-2，N=100。见 out/collab/h2-v7-independent-r2/independent-v5-session.json。第一次对照夹具用相对几何路径而提前退出，日志 v5.log 保留，改用绝对路径后的独立执行通过。
- 旧候选受控会话 1 事件原件保留，见 20261106-h2-v7-independent-r1.md；旧批处理/csh 与已有分量和、权重、DDD 证据维持原构建及限定范围。
