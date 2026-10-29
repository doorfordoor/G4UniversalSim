# 完整 2C 真实 CI 失败证据归档

冻结提交：fee88d2840b8300aa315d0feaf21316768f90206。本轮 **未通过完整阶段验收**，原始失败保留，不重跑、不改代码。机器清单见 `ci-evidence.json`。

## 官方结果

- M0 run 40884097335：Windows/Ubuntu job 均 success，static 15 + GUI 32 全绿；4 份报告本地严格门禁通过。
- Linux run 40884097773：11.3.2 job 123483057740 与 11.4.3 job 123483058028 均 failure，失败 step 都是 Run backend tests on Linux。static/GUI 已通过；backend 分别 47 PASS/5 FAIL、48 PASS/4 FAIL，零 skip。后续 integration 与其门禁未执行，不能声称四 profile 共 118 项全覆盖。

## 精确失败入口与日志尾摘要

| 用例 | 版本 | 原始失败定位 |
| --- | --- | --- |
| live_progress | 仅 11.3.2 | test_live_progress.py:211，event_row_t0 注入后未满足非零退出且 failed 摘要，AssertionError ('event_row_t0', '')。 |
| run_summary | 两版本 | test_run_summary.py:626，dry-run 生成文件 schema 集合仍只接受旧输出。 |
| sd_context_failure | 两版本 | test_sd_context_failure.py:60，预期退出 1 实际 0；11.3.2 为 2-sd_context_unknown_t0，11.4.3 为 2-sd_context_t0。日志记录后续 runs 实际完成，不能当注入失败被正确捕获。 |
| displacement_damage | 两版本 | test_displacement_damage.py:203，期待 cannot open NIEL table，实际为 Input file does not exist or is not regular: missing.csv。 |
| interactive_commands | 两版本 | test_interactive_commands.py:171，期待 effective_threads_origin_kind=runtime_unattributed，实际为 macro。 |

完整逐例日志在两份 Linux artifact 解包树中；`failure-excerpts-11.3.2.md` 与 `failure-excerpts-11.4.3.md` 给出限定长度的日志尾，原始长行未改。四份完整 job 日志为 job-<id>.log。上述是失败事实，不提前把任何一项归因为环境、产品或测试缺陷；由 root 修复裁决。

## 归档与门禁

4 份原始 ZIP 均已下载，SHA-256 全部与 GitHub 官方 digest 一致；官方 run/jobs/artifact JSON 同目录保存。路径穿越与 ZIP symlink 检查后安全解包。共获得 10 份 report.json，逐份使用当前严格 check_report_evidence，无 allow-incomplete/legacy；8 份 static/gui 通过，两份 backend 被拒绝，原始报告未修改。

全部 10 份报告的 source/tests fingerprint、profile 用例名单与预先冻结 manifest 一致：source c5005fd9140d883188cb6850b7e75cf59ca23753932d969f1e30f75f12e4b21b，tests 5e7e0fa2308f17703946e2714b45cb9998f4e9a5df2a723d3a80ed4a458b65d1。各 backend 52 项完整执行，但 integration 19 项未执行，不能用已有 99 项代替 118。

## 前项 P2 修复接续

已复核冻结 PhysicsManager acceptedEM：空/空白 em 只追加 shadowed，不替换 reference requested；manual 空 em 不采信被解析器短路的 list。两版本本轮 effective_source_physics 均 PASS，包含空/空白 em 与非空 option4 的真实导出反例；前述 P2 在这些具体回归范围得到真实运行证明，不把它扩为完整 2C 通过。新增七项 backend EffectiveConfig 专项在两版本均 PASS，生命周期/GDML integration 未运行。

GitHub 连接器间歇性 jobs 读取传输错误时使用公开只读 API；artifact/log 下载成功，未输出或落盘临时签名 URL。验收结论为 failed/incomplete，后续修复应使用新提交新 run，并保留本目录为原始失败证据。
