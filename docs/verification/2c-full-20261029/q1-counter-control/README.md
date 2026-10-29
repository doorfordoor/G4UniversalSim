# Q1 同口径控制实验

本控制组仅在 Q1 生产基线 f25da40 上覆盖五份冻结测试，提交 7929314120e07142b48205f00059625806e9193b，分支 codex-q1-counter-control；未推送，未修改 q1-final 工作区或保留二进制。生产 Git 对象与8ecad66/f25da40完全一致，五测试原始字节 SHA 与候选工作区一致。

全量105项：105 PASS / 0 FAIL / 0 SKIP，36269个v3断言入口，无零断言用例，退出码0；原 check_report_evidence 严格门禁返回0，无 legacy/incomplete 选项。

source fingerprint: d9c4378a03052a05cc59b55259ba5e99c32a056e0a7d87b92257ca21948bec4b

tests fingerprint: 3a72f846ab54c00475fbed357db4ddfef417d89e27b5305399f5cefa18507cec

五项入口数：{'dose_scoring': 79, 'scoring_numeric': 457, 'geometry_a5': 4320, 'gdml_touchable_identity': 65, 'q1_results_backend': 125}。这是一份“Q1生产代码+测试计数修订”的新控制证据，不修改历史Q1报告、不与旧83770动态入口数直接作覆盖优劣比较，也不构成新的独立物理验收。候选组可据同脚本的新控制报告做同v3门禁对照；完整2C结论另由主任务裁决。

原始报告及全部逐例日志：20261029-223005-6361397e/；完整runner日志 full105.log；严格门禁 strict-gate.log；来源及文件/二进制SHA control-evidence.json；复制回主工作区后的字节验证另见 copy-verification.json。
