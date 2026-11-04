# F2 最终独立复核

2026-11-04。产品864bc036，独立构建e7de615d，正式范围签收：**通过**。详情、原失败和非阻断限制见[最终验收](../../verification/f2-final-20261104/README.md)。

| 复核点 | 定位 | 结论与反例复验 |
| --- | --- | --- |
| 拒绝请求误当成功继续重放 | src/Core/SessionServer.cc:2330 | 确定为缺陷，现已修复。原ProcessRequest服务继续布尔不是ACK成功；最终损坏首/后轮源参数exit4、0 run_started，正常MT重放仍通过 |
| 预检实际调用setter污染首轮 | src/Core/SessionServer.cc:1253、2448 | 确定为缺陷，现已修复。ApplySourceEdit(apply=false)同域只读验证；原首轮不编辑源、后轮200MeV对照现逐行一致 |
| 正常重放GUI误报退出失败 | gui/g4usim_gui/core/session_client.py:719 | 确定为缺陷，现已修复。检查replay_finished、exit0及实际完成轮数；steps_total为全部操作，steps_executed为完成run，不要求相等。Win150和Linux正常按钮重放均closed |
| 真实运行与收据 | Windows125/150、Linux X11 | 无问题（本轮范围）。三轮/取消/新进程重放、原始表、正常GUI退出分别核验，不以exit0推断取消轮completed |
| 正式身份与报告 | cloud/strict-gates.json、copy-manifest.json | 无问题。12云报告均864/e7，708/255163，严格门禁及归档摘要核对；Windows VTK35无内部跳过 |
| 物理正确性、跨平台逐位一致 | 固定清单的限定重放范围 | 需实验，归Q2及对应科学基准；本轮工程重放不能代替独立物理验证，也不新增跨平台逐位承诺 |

作者bc8c临时构建不是独立冻结；原3b独立fd47失败、作者dirty3b/d378自测、最终864/e7独审与云分开。最终协议文档已区分结构预检和初始化后、BeamOn前的只读语义预检；不重复改正确段落。

Linux宿主自动收据native_window_evidence未观测保持原值；独立检查实际noVNC返回画面完成自然GUI操作，另有实际运行日志和原生退出清理。辅助twm退出1保留、无残留，不将辅助进程非零改写为全0。原WSLg限制不外推本轮X11。

run0摘要横线与重放参数unknown记后续易用性，不影响逐轮身份、事件或输出。无新增阻断缺陷，不扩展F2前置任务；进入记录集成及E4。
