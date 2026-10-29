# Q1 候选 4e6fa7a 验证（不是最终验收）

Windows干净Release：98 pass / 0 fail / 0 skip，175671已执行断言；真实Windows窗口流程通过。Linux CI run 40830609525（11.3.2/11.4.3），四profile与各自严格证据门禁通过；当时artifact仅包含backend/integration，因此这里只有对应两个profile的落盘报告。static/gui job成功可查ci-evidence.json，本轮修正workflow后将完整归档。

候选仍有R25/R26/R27，不能据测试通过关闭Q1。二进制SHA256 97590cf8eafb2f42c36bcd526b84ff6b0e29569432ef477240d7d025038fb75a。

补充检查：Windows报告自身严格门禁通过；与旧89例报告额外逐例计数比较未通过：trajectories 24446 < 24448。新增总断言超过旧总数，但逐例次数有2次差异，保留该失败，不改写报告。后续查明具体原因并在最终证据解释；不把断言次数当物理结果正确性证明。
