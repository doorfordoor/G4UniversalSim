# F3-2 噪声修订 R3｜实施回执（保守备选 N=2000）

2026-11-07。本轮按主审 m26429 修正两处覆盖/门限偏差后收尾：不启动 Geant4、不创建测量输出目录、
不改产品/合同/冻结文件/旧批证据/CURRENT/ROADMAP，不提交 Git。

## 1. 冻结口径（逐条落实）

- **N=2000、2 线程、seed 4242、36 次启动**：4 warmup + 20 timing（4 组合 × 5 轮）+ 12 memory
  （4 组合 × 3 次）；事件数只改 `/run/beamOn` 一行，配置与其余渲染不变。
- **顺序**：`--order blocked` 第 r 轮把组合列表左旋 r 位；默认仍为 `legacy`，旧行为不变。
  报告字段为 `execution_position`（本轮实际位置）与 `base_combo_index`（固定列表编号），
  脚本内不存在 `order_index`。
- **科学复验 = 32 个正式样本**，每个样本都与**同组合的 timing 第 0 次**比较：
  - 4 个 timing r0 自身资格核（元数据、角色、注册文件、回执 SHA）；
  - 16 个 timing r1..r4 对同组合 r0；
  - 12 个 memory 样本（r0..r2）对同组合 timing r0。
  每个样本独立 Python 子进程、独立退出释放缓存，逐样本核对 SHA/输入渲染/注册文件。
  旧比较器文件不改（SHA-256 `c8195197…`），只在任务级把 `EVENTS` 绑定为 2000；
  全新子进程加载时默认值仍为 1000（负控验证）。
- **噪声门**：四个组合各自 relative MAD ≤ 5%，等号通过。这是冻结测量唯一的噪声判据；
  任一组合超门 → 本轮结论 `inconclusive`（噪声/资源），保留全部样本，不称产品失败、
  不称阶段通过。F3-3 的候选优化规则（5 对中至少 4 对 ≥5% 收益、其余组合 ≤5%）只保留给
  未来候选比较，不用于本轮基线。
- **资源就绪**：离线比较开始前读取执行时真实可用物理内存，低于 **6 GiB** 则
  `status=resource_not_ready`、不启动任何比较、计划保持未完成、不关闭用户进程；
  该边界是执行准备条件，不放宽科学断言。
- **内存证据**：1000 事件旧 hits/CSV 单次离线比较实测 Python 峰值 `2,550,013,952` B、
  observer 295 样本、身份绑定、exit 0；2000 事件线性投影约 5.1 GB 只是假设场景，
  不构成因果、上下界或“必然通过”保证。新测量方案不实施 N=4000 分区比较器。

## 2. 本轮修改

| 文件 | 变更 | SHA-256 |
| --- | --- | --- |
| `scripts/measure_output_performance.py` | 仅新增 `ordered_combos`/`order_fields`、`--order`（默认 legacy）、blocked 报告字段；两处循环改 `enumerate(ordered_combos(...))`；diff 7 hunks、+44/−4 | `167ba575bda73fa68e2a01a3b898a38f77bf8465c89cf5110296c7ef35f4c656` |
| `out/collab/f3-noise-r3/before/measure_output_performance.py` | 修改前备份 | `7210ee1a87ed5450aeea050e15a43c92a4b1318d51323a9fe476302ee30e1bce` |
| `out/collab/f3-noise-r3/author/proposal.md` | N=2000 方案；32 样本覆盖、四组合噪声门、inconclusive 语义；修正 `PIID`→`PID` | `76155322034b4d697cd737467f467d42d99a4864a63caf4c83a657386a65acc6` |
| `out/collab/f3-noise-r3/author/parameters.json` | 36 次预算、32 样本覆盖（4/16/12）、逐样本对同组合 r0、四组合 5% 门与 inconclusive、6 GiB 门、三条命令 | `db0d50ba7fa82e871f96375371a146e6cd5e4da7c37c2a29af0c80533f0a1a64` |
| `out/collab/f3-noise-r3/author/compare_n.py` | 任务级 EVENTS=2000 绑定 + 旧模块 SHA 守卫（不改旧文件） | `5fbda942e62f8a8cc51a8f23c4932c073f278a2abf0efee1d573fe0ef1548294` |
| `out/collab/f3-noise-r3/author/science_batch.py` | 32 样本比较计划 + 资源门 + 每比较独立子进程；无 Geant4、无测量目录 | `bf0d0d199665395792ab397879238c39e4c793e509b429c5948734158bf55bf1` |
| `out/collab/f3-noise-r3/author/selfcheck_plan.py` | 无 Geant4 自测与负控 | `38a43be92a7366f82ce6c991c515f94947314cd027be554f36d723833b48d36c` |
| `out/collab/f3-noise-r3/author/selfcheck-report.json` | 自测报告 | `bfb034613be1c80442f8d4c68b8717e3c0a2ad8b27b7cc34329f01556231dc62` |
| `out/collab/f3-noise-r3/author/science-plan.json` | `--plan-only` 输出（32 样本、readiness） | `153bfb31467e628391007ed570e59924b4738a51d6a5780584ccefb5f72cb097` |
| `out/collab/f3-noise-r3/author/diagnose.py` | 只读诊断（含实测内存证据、N=2000 取舍） | `510fbd0592f37c523ab6a01ae0d94741d7f1ec7743270174fbc2ded25601e210` |
| `out/collab/f3-noise-r3/author/diagnosis.json` | 由 diagnose.py 重生成 | `ec71c70001045b70fc35c37a731d90573e24115e4f789716a8d89818e9f292f5` |

冻结输入（只读，SHA 已复核）：合同 `5e2cdd47…`、合同冻结 `7d0049ec…`、设计审查 `7b38f888…`、
旧比较器 `c8195197…`、PID observer `dd44e9c8…`、baseline exe `2ff536c5…`、两批 timing 报告
`a870bf31…` / `a6796f3e…`、内存探针 `result.json` `c37d8622…` / `memory.json` `7953072d…`。

## 3. 无 Geant4 自测结果

命令：`python -B out/collab/f3-noise-r3/author/selfcheck_plan.py --out out/collab/f3-noise-r3/author/selfcheck-report.json`

- **257 checks / 0 failures**；`geant4_launched=false`；运行前后 `out/collab/f3-noise-r3/measurement/`
  均不存在（自测不创建测量目录）。
- 覆盖：参数/命令一致性（36 次、三条命令逐 flag、memory observer）、32 样本计划
  （4+16+12、每样本 baseline 为同组合 r0、memory 路径命名）、blocked 五轮位置覆盖 0–3、
  legacy 等价、渲染只改 beamOn N、比较器 SHA 不变与任务级 EVENTS=2000（全新子进程默认仍 1000）、
  1000/1999 事件负控被拒、6 GiB 就绪门边界（等于通过、少 1 字节拒绝、未知不算 ready）、
  diff 仅 7 hunks/+44/−4、冻结输入 SHA、诊断“assumption/not a bound”标签、proposal 32 样本与
  四组合噪声门语义。
- `science_batch.py --plan-only`：32 样本、`timing_r0_selfcheck=4`、`timing_pair=16`、
  `memory_sample=12`；当前实测可用内存 `2,103,373,824` B < 6 GiB → `ready=false`，
  若真正执行会在比较前被资源门拦截，不启动任何样本。

## 4. 未做 / 待主审冻结后执行

- 未启动任何 Geant4 进程；未产生新的计时/RSS/科学样本；未创建 `measurement/`。
- 未提交 Git；未修改产品源码、合同、冻结文件、CURRENT/ROADMAP、旧批报告。
- 通过最终静态复验与主审冻结后，按 `parameters.json` 的三条命令执行 36 次唯一新批，
  再以 `science_batch.py` 执行 32 次离线科学比较（资源门通过才启动），最后按四组合
  relative MAD ≤ 5% / inconclusive 口径汇总结论。
