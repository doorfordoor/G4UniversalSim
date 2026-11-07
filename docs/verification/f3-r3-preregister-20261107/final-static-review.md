# F3 R3 N=2000 最终限定静态复核

2026-11-07｜结论：**发现 1 项冻结前应修正的超时清理阻断；修正后可按现有 N=2000 限定方案放行单批。** 无须扩展科学比较算法、提高门限或增加验收项目。本结论不构成性能、科学或原生运行验收。

## 按优先级的发现

**P1｜测量整阶段超时会遗留自有后代进程（阻断）**。`out/collab/f3-noise-r3/run-one-fixed-batch.py:39-45,52` 对 `run-fixed-baseline.py` 设置 3600 s 超时，却只执行 `p.kill()`；后者在 `out/collab/f3-preflight-independent/r2/run-fixed-baseline.py:12-14` 同步启动测量 Python，而测量 Python 再启动 Geant4，内存阶段还启动 PID observer（`scripts/measure_output_performance.py:231-235,279-303`）。**可发生反例**：20 次计时各未超过其单进程 600 s 超时，但整测量阶段耗时超过 3600 s；外层终止 `run-fixed-baseline.py` 后，测量 Python/Geant4 仍可能继续写文件，而外层记录 `stopped_incomplete`，失去对唯一 36 次预算的控制。**最小修正**：只对本次启动的测量进程树建立可确认的所有权，超时终止并等待该自有树全部结束（Windows Job Object 或同等明确的父子进程树回收机制）；不得按进程名扫杀、不得关闭用户进程。保留现有每个科学比较子进程的独立 600 s 超时和日志。修正此执行边界后重算该 driver SHA 并写入待冻结计划，再生成最终计划 SHA/approval，不能在 freeze 后偷改。

**P2｜最外层 driver 自身日志是否落盘需由启动者兑现（运行前核对项）**。`run-one-fixed-batch.py:35-47,90,97-99` 的自身 `print`/traceback 写向继承的 stdout/stderr；代码已将其调用的 `measurement`、`resource-independent`、`memory-independent` 及每份科学比较 stdout/stderr 写入 `*.driver.log`、`independent-analysis/*.log`，但无法单凭该源码证明最外层 stdout/stderr 被持久化。**最小范围**：主审实际派发唯一 job 时将外层两路完整输出重定向至本批独立日志并核对文件存在；无需修改产品或科学脚本。如启动器已提供持久化，该项可直接关闭。

## 已核实的执行/科学边界

- `run-plan.json` 现为 `draft_pending_final_independent_review`，三个 argv 均显式 `--events 2000`、`--order blocked`、同一 `baseline=` exe：1 round×4 = **4 warmup**，5×4 = **20 timing**，0 round + 3×4 = **12 memory**，共 **36** 个独立 Geant4 调用。`scripts/measure_output_performance.py:162-174,217-235,255-265` 按重复轮左旋四组合，计时依旧为进程完整 elapsed，Python SHA 在其后；无旧批合并。
- `science_batch.comparison_plan()` (`author/science_batch.py:44-85`) 定义 4 个同组合 r0 自资格、16 个 timing 对 r0、12 个 memory 对 r0 = **32**；`run-one-fixed-batch.py:73-90` 只复用该计划，显式传入 `base/memory/memory`，逐份启新的 `compare_n.py` 子进程并保存完整日志与 JSON，未执行 `science_batch.run_batch`。已给定的独立审查 `review/independent/review.json` 报告 32 个真实旧路径及 64 项核查通过；本轮静态核对其关键控制流，未重新跑科学比较。
- `author/compare_n.py:19-45,89-110` 对原始科学比较器 SHA `c8195197...` fail-closed，仅在任务级绑定 `EVENTS=2000`，不改原算法；每份科学比较子进程退出释放 CSV/ROOT 缓存。`run-one-fixed-batch.py:61-72` 的逐样本配置/宏/产物 SHA 再核验由主审 driver 承担，不能声称 `science_batch.py` 自带完整 hash 审计。
- `run-one-fixed-batch.py:5-11,20-23,29-38,49-58,91-97` 提供计划冻结态、approval 的计划 SHA、所有 `identity` 源 SHA、active baseline 绑定、独占 `job-started.json`、启动前 30 s 静置及每份离线比较前 ≥6 GiB 内存观察，最多等待 12 h；旧合同全四组合 MAD≤5% 由 `resource-independent.py:4-8` 检验，不合格记 `inconclusive` 而不选择目标。既有 F3-3 ≥5% 中位改善、5 对≥4 对更快、其余三点≤5% 回归及 RSS/字节/文件/科学门限不变。

## 审查限制与身份

旧 1000 事件分析 Python 峰值 **2,550,013,952 B**；2000 事件约 5.1 GB 仅为风险估算，≥6 GiB 可用门槛不能保证运行成功。当前计划仍为 draft，且独立检查曾观察约 3.0 GB 可用，不应宣称已就绪或新批已启动。无 Geant4/benchmark/driver/科学批执行；无源码、旧数据、产品文件修改。

本轮实读 SHA-256：`scripts/measure_output_performance.py`=`167ba575bda73fa68e2a01a3b898a38f77bf8465c89cf5110296c7ef35f4c656`；`author/compare_n.py`=`5fbda942e62f8a8cc51a8f23c4932c073f278a2abf0efee1d573fe0ef1548294`；`author/science_batch.py`=`bf0d0d199665395792ab397879238c39e4c793e509b429c5948734158bf55bf1`；`run-one-fixed-batch.py`=`4453faa2ef3099e5a737f3499ce8cc1de336e0d7f0101a1ae55cc49a2a94eb91`；`run-plan.json`=`72df74cf9cbf2939bac7e474ab45c51fb6f39bfe72c1e804482fee147ad311aa`；`review/independent/review.json`=`7d70b1cc748e741b0e4ba12b3816b5db3bbb223c3ec823c1fb440038a73574c3`；原科学比较器=`c8195197b9bd7278f74d689edff83dda247af1b4c686f41b3bcd0e7fc982bd82`；原合同=`7d0049ec9b4f727ca3251e5eebc8cca73046680a5a1abc709945f6d1b3f0b97b`。
