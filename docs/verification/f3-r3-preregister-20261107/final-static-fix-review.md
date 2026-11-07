# F3 R3 N=2000｜P1 最小替代修正独立复核

2026-11-07。**结论：P1 原阻断就所报告的自动超时反例已解除；允许主审按原计划完成冻结后派发一次限定新批。** 无须为此次修正引入 Job Object 或通用进程树管理。本报告仅审 P1 的替代修正，保留 `final-static-review.md/json` 既有历史结论，不修改其原记录。

原触发反例是 4+20+12 个合法后端进程的合计耗时超过父编排的 3600 秒，`run-one-fixed-batch.py` 只 kill `run-fixed-baseline.py`，留下它所等待的测量 Python/Geant4 后代。现在 `run-one-fixed-batch.py:52–54` 添加两行说明，并把 `command([...run-fixed-baseline.py], 'measurement', 3600)` 改成 `command([...run-fixed-baseline.py], 'measurement')`；`command()` 在第 39、43 行的默认 `timeout=None` 传给 `p.wait()`，不再有这个父级计时截止点。该修改直接消除上述确定性触发条件。

内层所有权仍由原逻辑承担：`run-fixed-baseline.py:12–16` 同步等待各测量阶段；`scripts/measure_output_performance.py:233–235` 的每个计时后端最多 600 秒，`296–315` 的内存阶段 Geant4 最多 600 秒、observer 最多 60 秒，异常时清理所持有的 `process`/`observer`；外层每份科学比较为直接子进程，`run-one-fixed-batch.py:83–86` 保持 600 秒等待和超时回收。**此结论仅覆盖本轮自动超时引起的遗留后代问题**；人为强杀、断电、Python 本身无进展等未知中断场景没有被验证，也没有声称全场景进程树回收。

身份核对：`minimal-timeout-fix.json` 的新 driver SHA-256 `24219117109708416ebcb8ae95a4bfce9f2ab740ee7a2956e4ce8bd559dbd5cd` 与当前源文件一致；更新的 `run-plan.json` 的 `identity.job_driver.sha256` 也一致。计划仍处于 `draft_pending_final_independent_review`，因此尚须按原流程冻结并绑定 approval/active-baseline，不能将此静态通过当作已执行。原已核三阶段预算继续列为 4/20/12，N=2000。

原审查的 P2 外层日志条件由主审派发器承诺将 stdout/stderr 全量重定向至本批 `job.driver.log` 并读回核验存在；当前仅能确认修正收据所声明的路径，**不能提前宣称日志已经产生**。此为派发核验条件，不阻止按既定流程冻结。

本轮仅阅读修正处、收据、草案计划 SHA 及必要内层超时代码；未执行 Geant4、benchmark、driver 或科学比较，未审其他实现。只写本文件与同名 JSON。

已核 SHA-256：`run-one-fixed-batch.py`=`24219117109708416ebcb8ae95a4bfce9f2ab740ee7a2956e4ce8bd559dbd5cd`；`review/minimal-timeout-fix.json`=`18eda70c2f9e35255559d17a86c1df0a4ef53bb37ccf4c5a05b8bc61cbdb8308`；`run-fixed-baseline.py`=`85b082885e126a9b4a4087e082c8dc9b33cc14eb287efdd5baf65bebe853fffb`；`scripts/measure_output_performance.py`=`167ba575bda73fa68e2a01a3b898a38f77bf8465c89cf5110296c7ef35f4c656`；`run-plan.json` 草案=`c60663ad8ff53147aa984d595ac95eda629915ece35e9bdd5a22b2a3b71439e3`。
