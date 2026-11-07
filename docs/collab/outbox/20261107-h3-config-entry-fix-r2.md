# H3-3 修复 r2 回执：disabled 平行世界误用启用组合规则

日期：2026-11-07
任务：H3-3 独审新增同函数 P1（`out/collab/h3-3-independent-r2/disabled-world-probe`）：
`[parallel_world] enabled=false` 且 `[scoring] let=true` 时，后端 dry-run exit 0，
GUI 却把 LET/DDD 当成平行世界冲突并阻断运行。范围仅两文件，未改 C++/schema、
未重建后端、未扩验证框架。完成即停，等待独审。

## 根因与改动

后端 `ParallelWorldConfig::CompatibilityProblems` 在 `!enabled_` 时提前返回；
GUI `read_inputs_scope()` 无条件调用 `_unsupported_combinations()`，把禁用世界的
LET/DDD、ROOT 输出、native mesh 当成平行世界冲突。

- `gui/g4usim_gui/core/parallel_world_scope.py`
  pre-fix SHA-256 `52a533b048e8b76e39c2f950a8fd1dc04f056ca72726aa95fcd49acbdd1d10a5`
  → post-fix `fe3c9935aa5d9248e2f6e3a92f6c071ebde663b6fda538dd4b887e09a0407a4e`：
  `_unsupported_combinations()` 只在实际 `enabled` 分支调用；disabled 世界自身的
  `name`/`geometry_config` 非法项与布尔诊断继续保留。
- `gui/smoke_tests/smoke_parallel_world_entry.py`
  pre-fix `74468fb6b5adab7a9449a5280d599e0b78b9ab742a263d9808610859f7e0a3e2`
  → post-fix `49734b39e832e73385696a00ecb179678e772cbd32781c2a588cef1400b058ef`：
  新增 disabled + `let` / disabled + `displacement` 合法回归（无 issue、GUI errors
  为空、保存不重写主 INI）、disabled + name/geometry_config 只报
  `parallel_world_disabled_with_keys`、disabled + 非法布尔仍报
  `parallel_world_boolean` 且不叠加 LET 冲突、disabled + ROOT/native mesh 不报
  平行世界冲突；保留 r1 空 `[scoring.displacement]` 合法回归与 enabled + LET/DDD
  拒绝负例。
- 最小 diff：`out/collab/20261107-h3-3-config-entry-fix-r2/fix.diff`
  （SHA-256 `52dfcd0573cfafd61fec2ab50bcf54b397596a17b5a2cdf58b5ceb1839158568`，
  90 行；相对主审 r1 冻结基线 `out/collab/h3-3-independent-r2/source` 生成，
  pre-fix 与冻结记录逐字节一致）。

## 真实命令、退出与报告

1. `python -m compileall -q gui/g4usim_gui`：exit 0（空输出）。
2. 审阅者反例（拷贝到 `out/collab/20261107-h3-3-config-entry-fix-r2/reviewer-fixture/`，
  9 个输入文件 SHA 与来源一致、运行前后未变）：scope `disabled`、issues=[]、
   状态行 `Parallel world: disabled (external [parallel_world])`；
   `validate_project_report(..., ready_to_run=True)` errors=[]、warnings=[]、
   `can_run=true`（`logs/reviewer-fixture-gui.log`、
   `logs/reviewer-fixture-gui-results.json`）。
3. 同一拷贝的固定后端 dry-run（**复用原 exe**
   `9daf3d22a3701ddeb3fd691351f92e2b1c31038a9fe2f16367f66f329e4e4dc0`，
   未重建）：`--config main.ini --dry-run --output <证据>/backend-dry-run-output`
   → **exit 0**，stderr 0 字节，stdout 末尾 `dry-run completed`
   （`logs/reviewer-fixture-dry-run.*.log`）；dry-run 产物写入证据目录，
   未在审阅者 fixture 或项目原 output 中写出/清理。
4. `python -B scripts/run_m0_tests.py --profile all --case gui_parallel_world_entry
   --case gui_project_io --case gui_project_import_projection
   --case gui_project_snapshot_restore --fail-on-skip --report-root
   out/collab/20261107-h3-3-config-entry-fix-r2/verification`：
   **4 pass / 0 fail / 0 skip，523 assertions**，报告
   `verification/20261107-033200-4f9ff430/report.json`
   （SHA-256 `2a4a278573ef78dc3c46c2d0007ed5bb156e529eb2770a9abfdd122b22ac7182`；
   `gui_parallel_world_entry` 62 assertions / 56 sites）。

## 身份与边界

- 后端 exe 未变：`9daf3d22…`（完整值见 `identities.json`），源指纹 `9523b987…`。
- HEAD `83c0b1399584031f82d7d1fe38443ed2d1713e4f`，`git_dirty=true`；未提交 Git。
- 未跑 H3-4/全量物理矩阵/Linux/云 CI；不声称阶段通过。
- 证据：`out/collab/20261107-h3-3-config-entry-fix-r2/`
  （README、fix.diff、identities.json、reviewer-fixture/、logs/、
  backend-dry-run-output/、verification/；r1 报告与历史目录未覆盖/未清理/未补造）。

## 范围外建议（未实施）

- `parallel_world_scope` 目前对 `[scoring.mesh.*]` 的识别只按节名；后端将来若
  允许禁用平行世界与 native mesh 共存（当前仅并行冲突规则不适用），可增加端到端
  对照用例，避免两端口径再次分叉。
