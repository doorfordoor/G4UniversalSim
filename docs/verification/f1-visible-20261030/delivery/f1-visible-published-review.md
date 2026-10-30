# F1 最终实窗归档发布后独立核验

结论：**APPROVE，可提交本次 F1 最终归档与关闭文档，并按既定流程正常集成。** 未发现本核验范围的阻断缺陷。实际 Git 集成尚未执行，不因缺少未来集成收据报缺陷，也不将此批准写成已经推送或快进成功。

本次只核对档案实际字节、身份、既有观察/关闭收据与文档一致性；未操作 GUI、未看图或冒称独立视觉复验、未运行模拟/重建产品、未改原档案或产品。视觉结论仍来自 root 的直接原生图像观察，前端写者对原观察证据的独立 approve 保留其原范围。

## 复制与历史保护

- 新归档 `docs/verification/f1-visible-20261030` 的 copy-manifest 恰好 **102 原件、4544178 字节**。每项目标及仍保留的 source 均独立重算 SHA-256/size，全部与清单相符；evidence 目录实际集合与清单精确一致，无漏项/额外项/大小写冲突。
- copy-verification 的 count/bytes 与清单一致，所记 copy-manifest SHA `322ef45f47cced924c6a79c884eb83af42fd11abdda6765ea1b4ad5de16dfecb` 与实际字节一致。
- prior-archive-preservation 的 **2850 文件**全部与当前旧自动归档/旧独立复核逐字节一致；进一步一次性读取 `ede037f` Git tree 的全部对应原始 blob，逐项 SHA/size 也完全一致。旧根目录实际集合等于2850项，无遗漏或新增。
- 原自动 README 的阶段未关闭/实窗 pending，以及旧 manifest/verification 等原件未被回改。本次最终结论独立登记在新 README/closure-state，未让历史收据自我改绿。

## 身份、关闭与搬移

产品 build 为 `f176d0ed4cea60b7ca5a80ed81017c9404ec1257`，GUI checkout 为 `ede037f26db63f606e3ca086d5d586f222f428df`。Git 两 HEAD 的 2857 个差异路径全部是文档/证据；当前实际源码指纹仍为 `db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc`，测试指纹仍为 `57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35`，实际 exe SHA 仍为 `f02d3bdc94121dcf35de05e152773fdec8c87f5c8759e53fd1f95d3f51f43ea8`。

14 张 JPEG 的原字节 SHA、JPEG 格式/尺寸、对应非空 UIA 文件及统一窗口身份均闭合；观察记录时间位于 host load 与 closed 之间。这里检查图像数据，不作视觉判断。07旧格式同次 UIA 滞后的边界仍明确，不能用旧文本证明当前图像；合成历史仍为结果未证实。

host import/load/exit 三份身份均为 GUI HEAD 与上述双指纹；host 源脚本 SHA 相符。`ready=true/closed=true`、PID、host-state SHA 与 process 收据一致；旧 host 和最终 host 均 exit 0；closed 后的进程收据与新 windows=[] 收据形成关闭链。原 `observation_acceptance=pending`、`phase_complete=false` 均未改写。

对归档的新根 `evidence/real-backend` 直接调用统一 `output_evidence(...,fresh=True)`，结果 **verified、20项登记产物**；metadata SHA/manifest 摘要与真实 fixture 收据相符。2 workers、2 runs 各2/2事件、auto→ROOT、3条输入记录均一致。原准备收据 visible_observation=pending 保留；构建 commit 与 GUI 文档 HEAD 不同的 `build_commit_matches_expected_head=false` 也保留，源码匹配为 true。该核验未重跑原输入或扩大为物理验证。

## 文档与可提交边界

新 README 与 closure-state 统一表达 F1 约定范围已完成、next_phase=F4；明确实际集成另记，不提前宣称执行成功。七份 live docs 的当前状态均一致：AGENTS、CHANGELOG、STATUS、ROADMAP、agent-history、功能支持矩阵、输出身份与来源。ROADMAP 总表已更新 F1/F6 done，F4 仍待开始；自动节点的旧 pending 条目有历史解释，未与新关闭条目混为当前阻断。

Q2物理基准、K1独立资源工程/实验包、J1自由布局、全绘图后台化和全部DPI/原生Linux桌面支持仍不随本次关闭。正常集成时继续执行原流程中的工作区/分支/远端核对；本审计不替代实际集成收据。

## 独占审计产物

- `out/collab/f1-visible-published-check.py`：最终独立检查脚本，未修改原件。
- `out/collab/f1-visible-published-evidence-final.json`：最终执行退出0的结构化收据，包含脚本SHA、七份live docs快照SHA及各项批准边界。
- `out/collab/f1-visible-published-check-final.log`：最终执行日志。

初次同结论收据与日志 `f1-visible-published-evidence.json`、`f1-visible-published-check.log` 也独立保留，没有覆盖。root 可将本最终脚本/JSON/报告另行复制到 delivery 目录并登记新收据；不应把这些发布后审查再塞回原102运行原件清单。
