# 历史归档验证器修复，独立审查反馈第二版

修复范围仅 ignored `out/collab/archive-f1.py` 与自己的验证脚本；未改 tracked、原 CI 文件、生产 exe，未发布归档。

旧 helper SHA：`e803a3c9f76aa12cae23b11e34dc8044415c38b0cfcd80b8f1fbf4d7711a8f24`。
新 helper SHA：`c164beaa0cfe9026224acda6ca00c4257574f4d9caf85d9dc96fa5d2060aad0c`。
本目录保留 `archive-f1-before.py`、`check-before.py`；`helper.patch` 是本版差异。上一版目录中的 receipt/plan/patch 均未覆盖。

## 已修复

1. compact 首轮必须读取其明确的 `job-log-backfill-20261030.json`。该已保存格式的三份补收日志，按原 job ID 与角色精确核对名单、文件名、正数字节数、SHA 及实际落盘字节；缺收据、重复/遗漏/未知 job、占位内容、摘要或长度矛盾均拒绝。历史 Ubuntu M0 的一份旧日志不在这份补收收据中：返回值明确列为 `legacy_presence_only_job_ids`，不能声称由补收收据验证其原始哈希；plan 的本地字节摘要也不是外部真实性签名。这是对当前已保存 sidecar 格式的兼容，不假装支持任意未来补收格式。
2. 原 run 标记 success 时必须所有 job success；原 job 标记 success 时不得包含 failure/cancelled/timed_out 等失败步骤。各 profile 仍与其原报告失败情况对应。没有反向强迫“所有测试通过就要求 job success”，因为打包等其他步骤可以失败。
3. 每个官方 artifact 解包根的文件集合必须精确等于原 ZIP 的文件成员，重复成员和额外文件拒绝。位于 artifact 根之外的独立采集器日志允许保留，且不能被列为官方 ZIP 成员。

## 验证结果

`receipt.json`：46 项检查，41 个拒绝负例通过。比旧版新增 11 个负例与 1 个正例：补收日志非空占位、错误 SHA/长度、缺行/重复/未知 ID/路径错误、收据缺失；成功 job 与失败 profile 矛盾；成功 run 与失败 job 矛盾；官方目录额外成员；bundle 外采集日志允许。

原真实两轮分别读取为 failed 历史，8/12 份报告；补收完成后两个真实 plan 的 blocker/missing 均为空。plan 仍以实际 E6 成功证据作为控制输入，只验证历史归档兼容，不能冒充 F1 最终自动验收。两个目标均未创建。

两处原 CI 树全部 757 个已落盘文件，验证前后逐项 SHA 相同；其中根任务此前补收的三个日志及 sidecar 只读核对。`validate_ci_topology`、`report_gates`、`verify_existing`、`execute` 四函数 AST 与修复前完全一致；失败历史作为最终发布 CI 的负例继续拒绝。

可重跑入口：`out/collab/f1-archive-history-compat/check.py`。该脚本现输出本 revision2 目录，保留旧版收据及其当时“缺三份日志”的真实历史；已有本版收据是一次实验记录，重验应另选新目录保留旧结果。

正式归档应明确选入本版 README/helper.patch/receipt 及两份 plan；旧版审查/实验也作为历史保留。实窗依旧 pending，本修复与 plan 通过均不构成 F1 阶段关闭。
