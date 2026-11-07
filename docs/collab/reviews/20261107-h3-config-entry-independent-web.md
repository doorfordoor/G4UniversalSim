# H3-3 配置入口独立复验（2026-11-07）

**结论：发现 1 项 P1 阻断，当前 H3-3 不建议签收。** 本报告只审 H3-3 冻结清单中的 GUI/schema/配置保存及 K1 闭包、示例与既有专项，H3-2 后端物理验收结论保持其独立身份。辅助审查未修改产品、测试、构建或提交。

## 按优先级排序的发现

### P1 — 未启用的 `[scoring.displacement]` 空段被 GUI 误判为禁用组合

- **代码位置：** `gui/g4usim_gui/core/parallel_world_scope.py:154-173`，尤其 `:171-172` 对任何 `scoring.displacement` 节均无条件加入 `parallel_world_let_displacement`。`gui/g4usim_gui/core/parallel_world_scope.py:114-115` 追加该问题，`gui/g4usim_gui/core/project_diagnostics.py:71-74` 将其发出为阻断 `error`。
- **冻结合同/实际后端：** `src/ParallelWorld/ParallelWorldConfig.cc:813-817` 依据 `scoring.IsLETScoringEnabled()`、`scoring.IsDisplacementScoringEnabled()` 判定冲突。`src/Scoring/ScoringManager.cc:380-383` 返回实际 displacement 启用标志。仅存在配置节不等于开启该计分。
- **最小触发反例：** 复制 `examples/07_parallel_world_box` 合法外部 box 配置，在主 INI 末尾追加一个不含任何 key 的 `[scoring.displacement]`，保留 `[scoring]` 的 dose/fluence 启用且 displacement 默认关闭。固定程序 `--dry-run` 退出码 0，真实 `run.mac` 完成 200/200 事件且摘要 `status = completed`、`parallel_world_enabled = true`、`parallel_world_volume_count = 1`。同一输入经 GUI `validate_project_report` 却得到错误 `Parallel world: LET and displacement damage scoring are not supported with a parallel scoring world.`。这会错误剥夺合法 External 配置的 GUI 验证/操作资格。
- **证据：** `out/collab/h3-3-independent-r1/disabled-displacement-probe/results.json`、同目录 `main.ini`、`stdout.log`、`run.stdout.log`、`backend-output/run_summary.txt` 和 `backend-run/run_summary.txt`；使用的程序 SHA-256 为 `9daf3d22a3701ddeb3fd691351f92e2b1c31038a9fe2f16367f66f329e4e4dc0`。
- **最小修复范围：** 将 `parallel_world_scope.py` 的 displacement 组合判断与后端实际启用条件对齐，保留真正开启 displacement/LET 时的阻断。补一条包含空 `[scoring.displacement]`、displacement 关闭的 GUI 诊断回归，同时保留实际开启 displacement 时必须报错的反例。无需修改 C++ 物理代码或放宽后端规则。修复及复验由主审单写者执行。

## 独立复验结果与边界

- **既有八项专项独立复跑：** `gui_project_io` 6、`gui_project_import_projection` 393、`gui_project_snapshot_restore` 62、`gui_parallel_world_entry` 41、`gui_main_window` 51、`parallel_world` 2411、`parallel_scoring_component` 8、`config_schema` 309，合计 **8 pass / 0 fail / 0 skip、3281 次断言**。原始报告 `out/collab/h3-3-independent-r1/verification/20261107-030418-357b2c76/report.json`。专项通过仅说明所列用例通过，不能覆盖上面的新增合法配置反例。
- **源码与程序身份：** `source-sha256.json` 的 45 项清单在独立运行后逐项对照当前仓库与冻结 `source/`，两者均 **45/45 一致**。程序 SHA-256 `9daf3d22a3701ddeb3fd691351f92e2b1c31038a9fe2f16367f66f329e4e4dc0`，组件 `parallelScoringCheck.exe` SHA-256 `8e01532770423a2498231c5a029bce1854ce0329f628d9f3ab41e988b8a99e95`，报告/身份文件源码指纹 `9523b9874ebb813cca321184a10269db4c76f4a7b9cbbdcd96e262a85bab6379`。仓库原有 dirty 状态保留。
- **已审入口：** `parallel_world_scope.py` 外部/Generated 状态及只读提示、`project_diagnostics.py` 诊断级别、`run_editor_import.py` 对外部域导入的拒绝、`experiment_bundle.py` 中主 INI 相对 `geometry_config` 的闭包重写和 `load_bundle` 恢复；结合已有 `gui_parallel_world_entry` 真实 box 20-event、资源角色/路径、保存/加载、sidecar 身份变化断言。`schema/config_schema.json` 的 `geometry_parallel_ini` 与后端 box/grid 入口做针对性文本比对，两个示例纳入既有专项。
- **未审/证据限制：** 未额外执行新的独立 K1 跨目录搬移后真实运行链路、未对 GUI 所有操作消费者做全状态人工遍历；未扩至 H3-4 统计物理矩阵、Linux/H3-5 正式回归、3D 原生视觉全覆盖。既有 8 项用例和 20-event smoke 不等于全面物理验证。发现明确阻断后停止扩展测试。

主审可在修复并用同一合法反例复验通过后重新裁定 H3-3。当前 H3-2/H3-3 的已通过专项与本报告中的新增阻断应分别保留原始证据，不覆盖历史记录。