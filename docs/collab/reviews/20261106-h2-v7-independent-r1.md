# H2-4 V7 第一次修复独立复验

2026-11-06。H2-4 保持失败。批处理及 csh 已在首事件前拒绝，受控会话接口仍可越过该校验。

复验二进制为 Windows/MSVC、Geant4 11.3.2，SHA-256 `c20f760e41872b2df75535c9f8cf70aebd3b7ffc38466dc7276acd2d6c453ead`，源码指纹 `c2e9c72ee8e3e4ab6f8a442ebac6c9d90dd3f9fc8c538929b2b540666a50751e`。基线提交 e2117037，含 H2 未提交实现。输入、二进制副本、输出及日志位于 `out/collab/h2-v7-independent`。

- 原 V7 与两线程、两条 beamOn 变体均 exit 1、failed、scoring_filter_particle、run_count 0、实际完成 0。无运行进度或 CSV 数据。两条 beamOn 的变体在宏第 2 行 `/run/beamOn 10` 失败。见 `independent-batch.json` 与相应原始摘要。
- csh 依次输入 initialize、beamOn 10、beamOn 17、exit，exit 1，scoring_filter_particle，run_count 0，实际完成 0。见 `v7-csh.log` 与 `v7-csh-output/run_summary.txt`。
- V5 exit 0，实际完成 100。唯一非零谱格 bin 5，1.0 mm^-2，N=100。见 `v5-output/spectrum_fluence_t0.csv`。
- 受控会话使用同一 V7 配置，hello → initialize applied → run(events=10) accepted。观察窗内未收到运行终态。随后关闭输入，进程 exit 1，摘要 failed、scoring_filter_particle、run_count 1、实际完成 1，直接违反首事件前拒绝。原会话帧、日志与摘要分别在 `v7-session-records`、`v7-session.log`、`v7-session-output/run_summary.txt`。等待终态超时是观察事实，1 事件来自实际输出摘要。

最小修复范围为 `src/Core/SessionServer.cc` 的 run 分支。完成常规请求与内核状态校验后，进入 Running、登记 replay step、发送 accepted 及调用 BeamOn 前，调用现有 `SimulationManager::ValidateScoringVolumeConfigsBeforeRun()`。沿用受控会话失败/退出与输出摘要处理，保留稳定的失败分类。V7 应得到明确拒绝或错误及非零退出，实际 0 事件、无成功运行回执及科学数据。验证合法会话仍走原路径，并复验这项 V7 原反例。既有批处理结果按上述二进制身份保留。
