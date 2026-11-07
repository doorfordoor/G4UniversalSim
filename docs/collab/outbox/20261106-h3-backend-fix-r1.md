# H3-2 首审修复 r1 回执（DeepSeek）

日期：2026-11-06/07（本机 Asia/Shanghai）
任务：H3-2 首版独立评审未通过；按 `docs/collab/reviews/20261106-h3-backend-independent-r1.md`
与辅助网页审查 `docs/collab/reviews/20261106-h3-web-independent.md`、主审确认的 F–I，
在冻结范围内修复 A–E、F–I 并保留首版回执与失败记录。

## 1. 结论

A–I 八组缺口均已按冻结合同最小修复；产品侧重新构建通过，新增/更新的真实后端回归
通过，并针对主审定位的 run_summary 默认关闭回归完成修复与定向复验。未提交 Git，
未改 GUI / ROADMAP / CURRENT-SUPERVISION / 固定清单 / 前端反馈，未运行 H3-4 统计批次，
不声明物理正确性。

## 2. 改动（A–I）

| 组 | 修复 | 关键位置 |
| --- | --- | --- |
| A | 声明名/派生名统一校验、全局展开 ≤ 4096、内部正体积交叠拒绝（面/边/点接触合法）、与质量体积重名检查 | `src/ParallelWorld/ParallelWorldConfig.cc` 的 `ParseGeometryFile`、`ValidateExpandedVolumes`、`ValidateMainName` |
| B | 材料一致性改为可证明三态：世界坐标投影（仅 identity rotation + Normal placement）、同解析材料身份整盒包含、排除内部异材质后代；否则 `unknown` | `ParallelWorldConfig.cc` 的 `CollectWorldBoxes`、`ContainsWholeBox`、`IntersectsInterior`、`ResolveMaterials` |
| C | 中心/边界/半宽/体积/密度/参考质量/总质量有限性与正性，构造前拒绝；派生盒越界报具体轴 | `ParallelWorldConfig.cc` 的 `ValidateDeclaredContainment`、`ResolveMaterials` |
| D | 有效配置 Accept/Fields/Evidence 与 coverage；逐 run 收据绑定该 run 完成事件数与已关闭输出真实 SHA-256；失败/未完成 run 不写成功收据；finalization 快照与 artifact 证据同一完成边界 | `src/Core/EffectiveSimulation.cc`、`src/Core/SimulationManager.cc` 的 `FinalizeRunSummary` |
| E | 配置后 macro/csh/session 重新校验 ROOT/biasing/native mesh/field/LET/DDD 组合，在内核构造前拒绝 | `SimulationManager::ValidateParallelWorldDependencies`/`ValidateParallelWorldForRun`、`main.cc`、`SessionServer.cc` |
| F | 所有物理体 copyNo 统一 0（含派生网格单元） | `src/ParallelWorld/ScoringParallelWorld.cc` |
| G | `SetParallelWorldConfig` 内完成注册；未注册即初始化报错；`SetParallelWorldOutputManager` 注入输出管理器 | `src/Detector/DetectorConstruction.cc`、`include/Core/SimulationManager.hh` |
| H | ghost 步直接构造路径/参考量，不再 `PopulateDoseContext`；保留 pre 权重；线程本地 manager 缺失锁存并非零收尾 | `src/ParallelWorld/ParallelScoringDetector.cc` |
| I | `ConstructSD` 复核每 ghost LV 的本线程 SD 绑定；TLS 检查只在事件处理中 | `src/ParallelWorld/ScoringParallelWorld.cc`、`ParallelScoringDetector.cc` |

主审定位的 run_summary 回归：原代码把 `WriteEffectiveFinalization()` 移到 artifact 证据
采集之后，导致 `run_metadata.json` 的 generated 快照早于 finalization 文件登记。修复后
逐 run 收据与 finalization 写在 `final_close` 之后、`CollectArtifactEvidence(true,true)`
之前，summary 与 metadata 共享同一登记边界；失败先锁存与 metadata 自排除规则未变。
两处临时调试插桩已移除（RunSummary 与 test_run_summary 的 DEBUG 块）。

同时把 `[parallel_world]` 的 4 条合同规则写入 `schema/config_schema.json` 并重跑
`scripts/generate_config_schema.py`（`ConfigSchemaTable.hh`、`config_schema_data.py`、
`config_schema_coverage.json`、功能支持矩阵 GENERATED 段）。

## 3. 验证（真实后端）

- `python -B scripts/test_run_summary.py`：M0-2 run summary regression tests passed。
- `python -B scripts/test_parallel_world.py`：OK（含 A–I 反例与正例；本机证据目录
  `out/collab/20261106-h3-2-fix-r1/evidence-final/`）。
- `python -B scripts/test_parallel_scoring_component.py`：OK（21 checks，含
  `MissingThreadManagerLatches`）；`ctest -C Release -R parallel_scoring_component` 通过。
- `python -B scripts/test_dose_scoring.py`、`scripts/test_unconsumed_config.py`、
  `scripts/test_config_schema.py`（102/102）通过。
- runner（backend，3 个受影响用例）：

```
PASS run_summary: asserts=37271/476
PASS parallel_world: asserts=2371/73
PASS parallel_scoring_component: asserts=8/7
3 pass / 0 fail / 0 skip
report: out/verification/h3-2-fix-r1/20261107-001353-e58514a7/report.json
```

- `python -B scripts/check_doc_links.py`：1464 relative links in 453 files, 0 broken。
- 反例复验：双盒交叠、派生重名、两网格超 4096、macro biasing/native mesh/ROOT 均在
  前置阶段拒绝；水盒 + 异材质铜 daughter 正常完成且材料字段写 `unknown`，逐 run 收据
  含 completed_events=20 与真实输出 SHA-256。

## 4. 身份与证据

- HEAD `83c0b1399584031f82d7d1fe38443ed2d1713e4f`，工作区含任务前既有修改
  `docs/ROADMAP.md`、`docs/collab/CURRENT-SUPERVISION.md`、`docs/collab/decisions/20261106-h3-automation-prompt.md`（未触碰）。
- exe `build_vs2026/Release/G4UniversalSim.exe` SHA-256
  `e442d894550940b8c75b6ce98ee6ae089553e4b02ae6361c2f69b06468bc0dc0`；
  组件 `parallelScoringCheck.exe` SHA-256
  `db70c3f50dc23e1cdc96157b3761c8d628939f11302a9f0d2657bac16c92eaa6`；
  `--capabilities` 源指纹 `dda9ff21e4464a57aaa6838609c9a27aaeb66706b162105117da158b4adf3d8f`。
- 构建命令（必须清掉大小写重复的代理变量）：
  `env -u no_proxy -u http_proxy -u https_proxy -u ALL_PROXY cmake --build build_vs2026 --config Release --target G4UniversalSim parallelScoringCheck`；MSVC 19.51.36246.0，Release，Geant4 11.3.2 MT。
- 证据目录 `out/collab/20261106-h3-2-fix-r1/`：
  `tracked.diff`（17 个既有文件，SHA-256 `a2adca415f40ad903608ff22f0625aabbcfa99d1d49223e894a7b72c3b6f4d7d`）、
  `new-files.diff`（11 个新文件，SHA-256 `95fc5450c18fc12384cfb27582910ea8d0270d394aa55cc2bdd8713a5b69cf97`）、
  `identities.json`、`evidence-final/`、`final-parallel-world.log`、`final-component.log`、`final-runner.log`。
- 保留原回执 `docs/collab/outbox/20261106-h3-backend.md` 与首版失败记录 `out/collab/h3-independent-r1/`。

## 5. 需主审裁定（与首版一致）

1. R-RUNTIME 零命中时 hits 文件按现有惰性语义不存在；测试接受「不存在或仅表头」，
   不改变产品惰性。是否要求合同改为「不存在或 0 行」请裁定。
2. Stage B 负例无法由受支持输入构造（声明与内核几何同源）；Stage B 正例在每次启用
   运行执行。是否接受该覆盖方式或另设测试钩子请裁定。
3. Case M 的线程调度不确定：测试只验证两轮事件数合计与逐 worker 文件存在，不把
   调度差异判为失败。
4. 材料一致性采用保守三态：可证明才写 true，旋转祖先/异材质后代写 unknown；是否
   要求 H3-3/H3-4 扩展证明范围请裁定。

## 6. 复现

```bash
cd D:/Geant4/G4UniversalSim
env -u no_proxy -u http_proxy -u https_proxy -u ALL_PROXY   cmake --build build_vs2026 --config Release --target G4UniversalSim parallelScoringCheck
python -B scripts/test_parallel_world.py
python -B scripts/test_parallel_scoring_component.py
python -B scripts/test_run_summary.py
python -B scripts/run_m0_tests.py --profile backend   --case run_summary --case parallel_world --case parallel_scoring_component
python -B scripts/check_doc_links.py
```

## 7. 未做 / 边界

- 未提交 Git（任务要求）；未改 GUI（H3-3）、未运行 H3-4 统计批次、未改 H8/ROADMAP/
  CURRENT/前端反馈。
- Linux、CI、ROOT、biasing、field、native mesh、LET、位移损伤与并行世界组合继续显式
  拒绝；未验证物理正确性、统计收敛与包安装。
