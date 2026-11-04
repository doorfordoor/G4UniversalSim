# Dose四能点：Windows独立参考证据

产品864bc036，Geant4 11.3.2，仅电磁option4。10/50/100/200MeV各20000事件，原四种子及2%参考容差加3σ，未经结果调参。

author.zip和independent.zip保存两套输入/原始输出/参考与比较脚本/反例；archives-manifest.json列ZIP及逐文件原始SHA、大小。两ZIP全部CRC和逐文件SHA已复核。独立归档还包含independent_math.py及54项复算、六步host收据和反例前后完整SHA快照；494项比较及7个反例均通过。

review-receipt.json汇总限定结果。initial-input-rejection.json保存执行器最初无效方源输入的桥工具预览；原始拒绝日志已被后续运行覆盖，这份预览不是完整原日志。执行器driver-notes保留复用误报等开发历史，不将其改写为物理失败或冻结变更。

[独立验收结论及适用范围](../../collab/reviews/20261105-q2-dose-reference-review-v1.md)。本包不代表Linux/11.4、云CI、完整强子物理或统计置信覆盖已验证，Q2整阶段尚未关闭。
