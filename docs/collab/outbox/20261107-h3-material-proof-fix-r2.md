# H3-2 材料证明最小修复 r2 回执（DeepSeek）

日期：2026-11-07（本机 Asia/Shanghai）
任务：H3-2 修复 r1 独立复验仍失败，仅剩材料一致性证明缺陷。依据
`docs/collab/reviews/20261107-h3-backend-fix-r1-independent-web.md` 与主审核验
`out/collab/h3-independent-r2/supervisor-material-verified.json`，最小修复 B 并保留其它
r1 已通过结果，不扩大阶段范围。

## 1. 结论

两个合法复验输入现在都在 `effective_config_finalization.json` 中写字符串 `unknown`
（此前为布尔 `true`）；原有正例仍为 `true`；既有 parallel_world 专项、组件检查与
CTest 通过。未提交 Git，未改 GUI / ROADMAP / CURRENT-SUPERVISION / 固定清单，未新增
测试框架，未运行 H3-4 统计批次，不声明物理正确性，停写等待独立复审。

## 2. 根因与最小修复

评审定位（fp 对照 `e442d894…`）：

1. `CollectWorldBoxes()` 为当前节点设置 `valid` 时只检查祖先 `transformProven`、box 形状
   与 Normal placement，漏掉自身 `IsIdentityRotation`，于是旋转盒仍用未旋转 `offset±half`
   投影被当成同材料候选。
2. `ResolveMaterials()` 在排除异材质覆盖时 `if (!other.valid || other.material == material)
   continue`，把无法投影的异材质后代（例如球体）直接当作不存在，仍签发 `true`。

修复（仅 `src/ParallelWorld/ParallelWorldConfig.cc`，3 个片段、产品 diff 58 行）：

- `CollectWorldBoxes()`：`valid` 条件加入 `IsIdentityRotation(node.rotation)`；旋转盒不再
  是可投影证据（不实现一般旋转盒包围算法，保持保守）。
- `ResolveMaterials()`：新增 `IsDescendantOf()`；无法投影的后代若属于候选盒子树且材料解析
  身份与候选不同，则证明失败并写 `unknown`；可证明与评分域无内部交集的合法后代仍放行。
- 祖先证明不完整时候选本身不会是 `valid`，因此不跳过、不签 `true`。

`include/ParallelWorld/ParallelWorldConfig.hh` 与其它产品文件本轮无需改动。

## 3. 验证（真实后端）

复验输入直接复用评审目录 `out/collab/h3-independent-r2/material-negative-repro/<case>/`
的原始字节（复制到 `out/collab/20261107-h3-material-proof-r2/work/`，逐文件 SHA-256 复核，
与 `supervisor-material-verified.json` 完全一致）：

| case | main.ini | geometry.ini | parallel.ini | materials.ini | exit | stderr | resolved | 冻结要求 |
| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |
| self_rotated_water_box | c70337a2… | 4ec7e137… | 2d5e63f2… | 89968dd7… | 0 | 0 B | `unknown` | unknown |
| copper_sphere_descendant | c70337a2… | b20f33a6… | 27283525… | 89968dd7… | 0 | 0 B | `unknown` | unknown |

两例 stdout 均含 `G4UniversalSim dry-run completed`，`status=dry_run`；字段路径
`/parallel_world/objects/volume:WaterBox/material_matches_mass_world`。完整记录见
`out/collab/20261107-h3-material-proof-r2/r2-results.json` 与每例 `output/effective_config_finalization.json`。

回归脚本：`scripts/test_parallel_world.py` 内嵌两例原始字节并校验 SHA-256 后才写盘
（输入漂移会先失败，不会把产品回归掩盖成输入变化），随后 `--dry-run` 断言字段精确等于
字符串 `unknown`。`python -B scripts/test_parallel_world.py` → `test_parallel_world: OK`
（含全部既有正例：无旋转叶盒/材料别名/已验证平移层级仍 `true`）。证据目录由
`G4USIM_TEST_EVIDENCE_DIR=out/collab/20261107-h3-material-proof-r2/evidence` 采集（171 个文件，735 KB）。

组件：`python -B scripts/test_parallel_scoring_component.py` → OK（21 checks）；
`ctest -C Release -R parallel_scoring_component` → Passed。

未重跑/不冒充：r1 的默认 run_summary（37271 asserts）、dose_scoring、unconsumed_config、
runner 等结果保持原程序与原证据，本回执不以新程序重算它们；本轮只声明受影响的
parallel_world 专项与组件检查。

## 4. 身份与 diff

- HEAD `83c0b1399584031f82d7d1fe38443ed2d1713e4f`，`git_dirty=true`（含任务前既有
  `M docs/ROADMAP.md`、`M docs/collab/CURRENT-SUPERVISION.md` 等，本任务未触碰）。
- 重建 exe SHA-256 `712fe41ddf9bd1c66bfdf3a8b1c51945f70a8d35041d66b9bdd52362a503fd81`；
  组件 exe SHA-256 `8a65e8c6b23fcb6fadfcb05fe9f4258312105742b29133764b4b7623f1724b85`；
  `--capabilities` source_fingerprint `caa650c55c58ee9044fd42b2cf986262dd4b2437f3de814826578db2eb188d52`。
- 产品小 diff：`out/collab/20261107-h3-material-proof-r2/product.diff`（SHA-256 `03d047f14387dc438495c3ee58971e6c862392f93d60cdc661c435910502db1b`，58 行）。
- 测试小 diff：`out/collab/20261107-h3-material-proof-r2/test.diff`（SHA-256 `18c5b62ea2659739b32dbbff48bac0bf78ac20394e9773fac483227eb5afffae`，75 行）。
- 身份汇总：`out/collab/20261107-h3-material-proof-r2/identities.json`。
- 构建命令：`env -u no_proxy -u http_proxy -u https_proxy -u ALL_PROXY cmake --build build_vs2026 --config Release --target G4UniversalSim parallelScoringCheck`。

## 5. 证据目录

`out/collab/20261107-h3-material-proof-r2/`：

- `work/<case>/`：评审原始输入副本、`stdout.log`、`stderr.log`、`output/effective_config_finalization.json`。
- `r2-results.json`：两例字段值与输入哈希复核。
- `evidence/`：回归脚本采集的运行证据。
- `parallel-world.log`、`component.log`、`product.diff`、`test.diff`、`identities.json`。

## 6. 未验证与边界

- 只在本机 Windows/MSVC/Geant4 11.3.2 验证；未跑 Linux/CI，未重跑 r1 其余专项与 H3-4 批次。
- 未实现一般旋转 solid 的精确证明：旋转盒一律保守 `unknown`，这是有意的最小策略。
- 评审已裁定四项沿用冻结决定：零命中 hits 文件允许不存在；不增加 Stage B 注入 hook；
  Case M 完整事件/矩合并留 H3-4；无法证明的材料匹配必须 `unknown`。
