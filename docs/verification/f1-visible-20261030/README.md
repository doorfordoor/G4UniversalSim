# F1 最终验收（2026-10-30）

**F1 输出身份与来源阶段已完成。** 产品冻结 `f176d0ed4cea60b7ca5a80ed81017c9404ec1257`；最终 GUI 实窗检出 `ede037f26db63f606e3ca086d5d586f222f428df`，两者仅文档/证据不同，源码及测试指纹一致。本次补验没有修改产品或测试。

## 交付范围

构建身份、实际输入读字节账本、执行标识、显式产物归属及 SHA-256；版本化增量协议、旧格式兼容和损坏拒绝；目录搬移后的当前副本校验；结果/历史页独立展示运行状态与文件身份，异步校验拒绝迟到覆盖；显式 `format=auto` 记录 ROOT/CSV 选择与原因，默认仍为 CSV。完整边界见[输出身份与来源](../../输出身份与来源.md)与[开工契约](../../collab/inbox/20261030-1410-astra-f1-scope.md)。

主负责人负责架构裁决、整合和最终验收，子代理承担实现与交叉审查；[DeepSeek 前端设计真实记录](../../collab/outbox/20261030-deepseek-f1-design.md)与实际窗口观察分别留证。用户允许后续子代理使用 Astra；本报告不把失败的模型路由调用计为审查工作。

## 验收

| 层级 | 结果 | 证据 |
| --- | --- | --- |
| Windows 全量 | 143/143，0 fail/skip，48511 个 v3 断言入口；E6 同口径逐例/总数门禁通过 | [不可变自动归档](../f1-automated-20261030/README.md) |
| 真实 Linux CI | Geant4 11.3.2/11.4.3 各143/143，run 41028779177 | [真实 workflow](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41028779177)，原始证据见自动归档 |
| M0 CI | Windows/Ubuntu 各64/64，run 41028779326 | [真实 workflow](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41028779326) |
| CI 原件核验 | 4 份官方 ZIP 摘要、12 份正式报告、414 次用例执行/103787 个断言入口及原日志 SHA 通过 | [归档独立复核](../f1-automated-review-20261030/README.md) |
| Windows 实际窗口 | 14 次原生图像观察；身份明细、错误/旧格式、历史独立状态、真实输出呈现通过 | [主审报告](evidence/review/f1-root-visible-review.md)、[逐图观察](evidence/visible/observations.json) |
| 真实后端小运行 | 2 workers、2 run 各2/2事件，auto→ROOT、3条读入记录、20项登记产物，退出0、重新SHA验证一致 | [原始夹具收据](evidence/real-backend/fixture-receipt.json)、[metadata](evidence/real-backend/run_metadata.json) |
| 关闭与独立核验 | 旧/最终 host 均退出0；最终closed且关闭后无F1窗口；14图原字节、身份链及范围复核通过 | [退出收据](evidence/visible/process-receipt.json)、[独立审计](evidence/review/f1-visible-final-audit-review.md)、[范围审查](evidence/review/f1-final-scope-review.md) |

源码指纹 `db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc`；测试指纹 `57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35`；Windows exe SHA `f02d3bdc94121dcf35de05e152773fdec8c87f5c8759e53fd1f95d3f51f43ea8`。GUI checkout 与后端 build commit 不相同是已解释的事实，不改写 `build_commit_matches_expected_head=false`。

## 实窗解释与历史保留

窗口由专用 host 加载真实产品组件，主审使用原生 Windows 工具逐项切换、展开 JSON、拖动现有分隔条及关闭，并直接查看工具返回的原生图像。前11次为明确标记的合成状态；后3次展示最终真实 CLI 运行目录。典型原图：[失败与字节一致并存](evidence/visible/05-synthetic-failed-verified.jpg)、[篡改拒绝](evidence/visible/06-synthetic-tampered.jpg)、[真实 auto→ROOT](evidence/visible/12-real-build-auto.jpg)、[两轮输出归属](evidence/visible/14-real-outputs.jpg)。这14次不是14项独立模拟或物理基准。

07旧格式图像已被主审看到，但同次UIA文本滞后上一页；原件保留，不能用滞后文本证明该页。合成历史缺少真实进程退出收据，结果显示未证实，其身份仍可独立为一致/缺失；不把这些截图称为成功/失败历史真运行验收。长哈希有省略和滚动；现有分隔条调整不算J1自由布局。独立代理核对字节和收据，视觉结论来自主审实际观察，不冒称另一人重复看图。

旧host曾被遮挡，用户置前后正常退出；最终host会话85274经原生Alt+F4关闭，退出0。原 `host-state.observation_acceptance=pending`、准备夹具 `visible_observation=pending`、采集收据 `phase_complete=false` 均保留当时事实；最终结论独立登记在本报告与[阶段状态](closure-state.json)，不让host自我认证视觉通过。

两轮失败及修复不删除：首轮异步示例预设选择丢失已修复；Windows数据定位沿用E6既有数据参数；第二轮Linux故障测试暴露GDML缓冲分配异常漏关句柄及Xerces异常族差异，最终冻结全平台重验通过。54次格式测量及18次缓冲对照未支持256KiB候选稳定收益，候选已撤回；不是最终冻结重测，也不把Python校验耗时当C++哈希CPU时间。

## 归档及后续

[复制清单](copy-manifest.json)登记102个原件、4544178字节，含原始图像/文本/收据、真实运行文件、合成夹具和审查记录；[复制核验](copy-verification.json)逐字节通过。原自动归档及其独立复核共2850文件的当时摘要记录在[保留清单](prior-archive-preservation.json)。本README、阶段状态及后续交付/集成收据不是这些运行原件。

原自动归档中的实窗pending、阶段未关闭是当时状态，不追改。本次关闭限定F1约定范围：未增加Q2物理验证、K1任意资源/独立工程导出、J1自由布局、全部绘图后台化或全DPI/原生Linux桌面支持；来源哈希不是数字签名或防恶意共同改写保证。

[发布后独立核验](delivery/f1-visible-published-review.md)已批准：102原件、2850旧文件、14图与关闭链、双HEAD身份及归档根下20产物严格SHA全部通过；[核验收据](delivery/f1-visible-published-evidence-final.json)与[四份审查材料复制清单](delivery/copy-manifest.json)独立保留。审查者未操作桌面或冒称看图。

下一完整阶段为 **F4：诊断定位到 editor/row/field/code 并支持点击跳转**，随后F5、K1；I1可按依赖并行。集成采用独立q1-final工作区正常快进codex，实际推送事实另行登记。
