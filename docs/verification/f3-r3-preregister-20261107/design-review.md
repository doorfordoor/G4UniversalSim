# F3-2 噪声修订方案 R3｜限定独立设计审查

2026-11-07。结论：**有条件支持 N=4000、仅对离线 hits 科学比较做 eventID 有界分区**；不支持 N=4000 继续使用现有全量入内存比较器。若分区接线无法保持冻结科学语义和可核对的流式计数，退而选择 **N=2000 + 原比较算法**，但仍有较大的内存余量风险。两种方案均须由主审在新批前明确修订原 N=1000 冻结，不能自动视为 5% MAD 可达标。

## 事实与风险

1. 两批保留的原始 timing/report.json 各为 5 区组×4 组合=20 条计时样本；资源报告分别在 hits/csv 出现 **MAD 5.15539%**、hits/root 出现 **5.52623%**（其余组合合格），两批整体均为 inconclusive。旧诊断表明全进程计时中内核 wall 外的中位占比约 **28%–52%**，但 run-wall 自身也变化，不能将噪声归因于启动或特定后台进程。旧测量脚本第 182–187 行组合顺序固定，新批按预先固定的伪随机排列做 **5 个完整交错区组**有依据；并不保证 MAD 降至 5% 以下。
2. 原脚本第 196–215 行的 total_elapsed_s 已包含后端进程启动、运行及收尾、排除随后的 Python SHA；第 37–76 行明确 threads=2、seed=4242、同一几何/物理/源与真实单进程 beamOn N。新方案只变 N 与区组执行顺序；保留 4 次独立 warmup、20 次独立计时、12 次独立 RSS（共 **36 次**），每个进程 N 个真实事件。不得拼接旧批、剔除样本或将短跑均值伪作长跑，仍使用全进程 elapsed 和原 5% MAD、资源/收益/科学门限。
3. 1000 事件单次离线科学比较的 Python 进程 OS 峰值 **2,550,013,952 B**，PID/启动身份核实且 295 次观测；内存随 N 线性增长仅作粗略风险估计：N=2000 约 **5.1 GB**，N=4000 约 **10.2 GB**。第二批环境快照报告空闲物理内存 6,828,856 KiB（约 6.99 GB）；N=2000 的预计余量不足 2 GB，N=4000 全量方案明显超过当时空闲量。此为历史快照，不代表执行时容量或实测 OOM。无需也不得关闭用户进程。

## 最小必要修订

**优先方案 N=4000。** science_compare.py 第 33、366、621、632、642、651、743、751、817 行等写死 EVENTS=1000，应统一接收事前冻结的 N，并分别要求两侧 metadata 中 planned/completed_events=N、唯一 runID=0；mesh 的全 run N 只取一次，不能逐 sparse cell 重复加 worker 局部 N。计时新批与后续候选配对必须使用完全相同 N、配置模板和科学定义；旧 N=1000 批仅供噪声诊断。

仅为 hits 负载新增**单次流式扫描 + eventID 分区 + 逐分区精确 Counter 比较**：CSV 按行、ROOT hits 按有界 entry chunk 读取；预先检查全部原有列/branch 及类型。每条原始 hit 验证 runID、0≤eventID<N 和全部科学字段有限性，按确定且互斥的 eventID 范围归入唯一分区，保留原全部业务元组和重复次数，仅忽略 threadID/顺序，浮点维持 12 位有效数字。分别核对读入原行数、分区落盘/读取总行数及 ROOT num_entries，确保不漏、不重、无越界；逐分区比较两侧多重集并释放缓存。event_edep 仍要求独立且恰好 0..N−1 的唯一 eventID；保留全部原 volume/particle summary、scorer/mesh 矩、raw/weighted histogram 各 bin 边界/计数、配置/单位、未知科学文件和每 run 检查，不放宽 1e-9/0 容差。原第 188–201、280–286、611–617 行缓存全部 CSV hits，第 676–688、735–739 行一次性读取全部 ROOT hits；必须使 hits 路径绕开这些内存驻留点，避免只分区已读入的巨型列表。临时分区产物仅用于**计时停止后的离线分析**，其 I/O 不得进入 Geant4 全进程 elapsed；需记录清单、行数、诊断及清理结果。

**保守备选 N=2000。** 仍需把固定的 EVENTS=1000 改为冻结的 N，否则第 366 行直接拒绝合法运行；科学算法可保持原状。它是实现改动最小的选项，但 2.55 GB×2 的估计接近旧环境内存余量，必须由主审依据执行前真实可用资源决定能否承担。若 N=4000 分区实现不能经过限定 diff 核验，优先保留严格科学比较并采用这一备选或暂缓，切勿放宽元组比较、字段完整性或采用哈希摘要代替多重集。

**仍未证明：** 更长单进程能通过原 5% MAD 门、内存随事件数线性增长、执行时的空闲内存，以及 DS 修订实现的正确性。本次是对保留快照的只读设计审查；未读 DS live 测量脚本，未启动 Geant4、未跑性能或科学验证，未审 PID/measurement/run-plan 新 diff。待作者稳定后由主审核实事件 N、顺序重放、分区全覆盖与科学字段无损，再作一次限定新批的冻结决策。

## 已读取文件 SHA-256

| 文件（相对仓库） | SHA-256 |
| --- | --- |
| docs/collab/decisions/20261107-f3-contract-freeze.md | 7d0049ec9b4f727ca3251e5eebc8cca73046680a5a1abc709945f6d1b3f0b97b |
| out/collab/f3-noise-r3/before/measure_output_performance.py | 7210ee1a87ed5450aeea050e15a43c92a4b1318d51323a9fe476302ee30e1bce |
| out/collab/f3-noise-r3/supervisor-old-data-diagnosis.json | 37b7aa2d57c0e2f85282d06360b07ae1330691a05017b6d79468074d8ca70a1e |
| out/collab/f3-noise-r3/analysis-memory-probe/result.json | c37d8622474c4f684d202a0eb6a8cd28ae6ca85cbb41d8afb60682bb7f385583 |
| out/collab/f3-noise-r3/analysis-memory-probe/memory.json | 7953072dbdf67f07336ea854e122ceea495330875d172dd61f5889b03305d42b |
| out/collab/20261107-f3-baseline/preflight/science_compare.py | c8195197b9bd7278f74d689edff83dda247af1b4c686f41b3bcd0e7fc982bd82 |
| out/collab/20261107-f3-baseline/20261107T024015Z-f39d1262/timing/report.json | a870bf31a62e5b0df64fc2f11df970d6ef6e81153648873176b89ae18ed47111 |
| out/collab/20261107-f3-baseline/20261107T024015Z-f39d1262/resource-independent.json | 6e49951011c19d70516881fa6112208476d4413a8a643f3fdda63c138e3bd7e0 |
| out/collab/20261107-f3-baseline/20261107T024015Z-f39d1262/environment.json | b841fcce9855e46512b8c4a05f19b621391519e67848d08ead5ee955b78d9de1 |
| out/collab/20261107-f3-baseline/batch2-20261107T033815Z/timing/report.json | a6796f3ee9a1bdbba23d6c6368c8e99e84f62044da6a217af202eec39aaa345a |
| out/collab/20261107-f3-baseline/batch2-20261107T033815Z/resource-independent.json | 7177149229ee7be1fba24b542c1dc6f8d8831688f6020673ed7a8bd8ffa09249 |
| out/collab/20261107-f3-baseline/batch2-20261107T033815Z/environment.json | c2d2ae61292bb7308328c7c9499708175d8677193af01564441cfb16b333b9c9 |
