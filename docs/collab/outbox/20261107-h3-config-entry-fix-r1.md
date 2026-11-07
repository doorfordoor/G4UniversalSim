# H3-3 修复 r1 回执：空 `[scoring.displacement]` 误报

日期：2026-11-07
任务：H3-3 独审 P1（`docs/collab/reviews/20261107-h3-config-entry-independent-web.md`）：
合法外部主 INI 追加空 `[scoring.displacement]` 时 GUI 误报 LET/DDD 组合错误、阻断运行。
范围仅两文件，未改 C++/schema/导航/前端架构，未重建后端。完成即停，等待独审。

## 根因与改动

后端只看 `[scoring]` 的 `let`/`displacement` 启用标志；`parallel_world_scope.py` 的
`_unsupported_combinations()` 误把 `[scoring.displacement]` 节存在当成已启用。

- `gui/g4usim_gui/core/parallel_world_scope.py`
  pre-fix SHA-256 `dabdbd0820ab0b09fc08d14201c6a77961ad43bc2fb8869964d2f55f368549fb`
  → post-fix `52a533b048e8b76e39c2f950a8fd1dc04f056ca72726aa95fcd49acbdd1d10a5`：
  删除 `elif name == "scoring.displacement": …` 分支；组合判断仍依据 `[scoring]`
  `let`/`displacement` 真值（真正启用 LET/DDD 继续拒绝）。
- `gui/smoke_tests/smoke_parallel_world_entry.py`
  pre-fix `0ddd7fc016ef301bac7145f8eb43e34645d2f93bf66b6e87f1f528011f9e9e89` → post-fix
  `74468fb6b5adab7a9449a5280d599e0b78b9ab742a263d9808610859f7e0a3e2`：
  新增空节合法回归（scope 无 issue、GUI errors 为空、保存后 main.ini 字节不变）；
  保留 `let = true` / `displacement = true` 两个负例。
- 具体 diff：`out/collab/20261107-h3-3-config-entry-fix-r1/fix.diff`
  （SHA-256 `3bf073bd50efc4d8fc6b2fd2de9ee9b80e126c429626f4a05ea41a4c89380cc0`，
   2674 字节；基线由 H3-3 交付证据的两个 diff 重建并与其 identities 交叉核对）。

## 真实命令、退出与报告

1. 审阅者反例 GUI 校验：scope=enabled、issues=[]、errors=[]、can_run=true
   （`logs/reviewer-fixture-gui.log`）。
2. 同反例后端 dry-run（**复用原 exe** `9daf3d22a3701ddeb3fd691351f92e2b1c31038a9fe2f16367f66f329e4e4dc0`，
   未重建）：**exit 0**，stderr 0 B（`logs/reviewer-fixture-dry-run.*.log`）；dry-run
   默认生成的 `output/` 已移入证据 `backend-dry-run-output/`，审阅者 fixture 目录恢复原文件集合。
3. `python -m compileall -q gui/g4usim_gui`：exit 0。
4. `python -B scripts/run_m0_tests.py --profile all --case gui_parallel_world_entry
   --case gui_project_io --case gui_project_import_projection
   --case gui_project_snapshot_restore --fail-on-skip --report-root
   out/collab/20261107-h3-3-config-entry-fix-r1/verification`：
   **4 pass / 0 fail / 0 skip，509 assertions**，报告
   `verification/20261107-032327-145b6db5/report.json`
   （SHA-256 `a2965a3c004fca002d1f4e99eabfe06d6a7d91df9961a9efe5c54ea4c313b436`）。
5. 范围外核查（未修）：空 `[field.demo]` 后端配置期即拒绝（exit 1，
   `[field.demo]: needs magnetic, electric, magnetic_map or electric_map`），
   GUI 对应告警与后端一致，无需同类修复。

## 身份与边界

- HEAD `83c0b1399584031f82d7d1fe38443ed2d1713e4f`，`git_dirty=true`；未提交 Git。
- 后端 exe 未变（`9daf3d22…`），源指纹 `9523b987…`；未跑 H3-4/全量矩阵/Linux/云 CI。
- 原 H3-3 证据与 `verification/20261107-024554-34286906/` 原样保留；本轮报告独立目录，
  未清理、未补造任何报告。
- 证据：`out/collab/20261107-h3-3-config-entry-fix-r1/`
  （README、fix.diff、identities.json、logs/、backend-dry-run-output/、verification/）。
