# E6 cb837e6 首轮 CI 原始失败证据

冻结完整SHA：cb837e680e08a66dd47e62a9ee7e25fa125026c3，分支roadmap/E6-config-compat，127项清单（static19 / GUI33 / backend55 / integration20）。

真实push工作流，均attempt1，未取消、重跑或重复触发：
- Linux run40911355023，jobs123579858842（11.3.2）/123579859232（11.4.3），均failure。
- M0 run40911355092，jobs123579859374（Ubuntu）/123579859622（Windows），均failure。

四job均static19/19通过，GUI32pass/1fail/0skip；唯一失败gui_start_page（gui/smoke_tests/smoke_start_page.py），timeout after600s。主负责人独立本机定位为统一recent loader改用QMessageBox.critical后原smoke仅mockwarning/information，引起缺失demo_project模态框；实际CI日志与timeout证据保留。该候选不能作为E6验收。

两版Linux后续backend/integration步骤因GUI失败被跳过，没有这四份profile报告。实际得到8份报告，预期完整12份未满足；ci-evidence.json为not_passed、complete=false。严格门禁四份static通过、四份GUI拒绝（timeout记录exit_code=None）；--allow-incomplete诊断也因同一exit_code边界拒绝，不把它写为通过。raw-log-hash-audit.json另对8报告全部208份落盘日志逐个SHA256校验，无不匹配，不改原报告。

四份ZIP均由GitHub连接下载的官方归档，均与artifacts metadata内digest一致；四份job日志、run身份、jobs与官方artifact metadata均已保存。原始ZIP与解包内容不修改，门禁结果写在独立gates目录。

GitHub连接可直接fetch push run集合，本轮无需Git credential或gh。状态查询两次遇连接传输失败，原文connector-status-read-incident.log；只读重取/公开API确认继续运行，没有工作流重跑。后续连接工具成功收取全部归档和job日志。

下一步由主任务修复模态测试边界，以新冻结提交重新验收；本目录保持首轮失败身份，不能用后来绿色结果覆盖。
