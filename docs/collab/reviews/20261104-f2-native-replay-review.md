# F2 原生三轮与正常重放反馈

候选3b713ba9259b18d57e8068f3e8ee7a29c8f72443，独立C盘clean构建指纹fd47ea71a204ee31c8b679bd54f2991f3b5db6b12599449b45e3ef11c00b3805。Windows真实125% / Qt windows DPR1.25。

## 通过
正常控件完成100/200/100 MeV、每轮5事件；同一session361f1aaf9448、run0/1/2，均5/5且回执已校验。手动结束再点重放，新session193ce837454a三轮亦5/5。C盘证据out/collab/f2-native-review-3b/aba-ui.txt、aba-0.png、replay-ui.txt及runs原始session.jsonl。

## 确定为缺陷
正常replay发closing、reason=replay_finished、进程exit0，GUI却记录Session ended unexpectedly (exit code 0): no stderr output，并显示会话失败。core/session_client.py:_on_runner_finished仅依赖_closing_expected；重放closing未设置合法预期终态。不能仅因为exit0就成功；应依据实际replay终态与完成计数。最小修复session_client及已有smoke_session_client/backend相关测试，正常三轮、拒绝/不完整/异常退出分别覆盖。重放行参数unknown及run0破折号列后续普通展现待办，不扩本轮。

## 正式静态失败
C盘out/collab/f2-frozen-3b/static/20261104-182923-41ca7eb9/report.json：48pass/1fail/0skip、5681断言。platform_paths指向gui/smoke_tests/smoke_session_panel.py硬编码C:/tmp/replay-manifest.json；改为测试自有临时路径或平台无关路径，保留原失败。

停止条件：现有非法参数重放拒绝修复及上述合法重放GUI终态/路径门禁恢复。不扩工具、不重开J3。
