# F4 结构化诊断与定位：工程验收与原始证据

**约定功能、Windows全量、真实CI和Windows实窗验收已通过。** 本归档在codex快进前生成，原始事实保留各自提交和时间；发布后的阶段关闭与集成见仓库 `docs/collab/reviews/20261030-astra-f4-close-review.md`，不追改本快照。

## 范围与身份

实现稳定 code/identity、真实 editor/row/field/source 位置、共享问题列表、切页/展开/选行/滚动定位，以及旧快照失效和只读历史来源。覆盖 Configuration、Project/Run、Scenario、Wizard、Scan；保留旧报告与后端原文，无位置时明确拒绝猜测。定位不改配置，不自动修复；不扩大高级 GUI/物理功能。F5、K1、L1、Q2仍各自独立。

产品及 Windows/实窗绑定 **`7d718d038a00d89995ea773b4772764116b620c3`**；真实 CI 绑定 **`a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9`**。CI提交仅增加 Linux GUI 系统运行库安装的六行，是产品提交的直接子提交。已逐项核对 **11,340 个 Git 路径/mode/blob 条目**，除此 workflow 外全部相同。两边实际提交身份保留，不能改写为全平台同一 SHA。见[完整身份映射](identity/identity-map.json)和[独立裁决](review/2-f4-ci-only-acceptance-review.md.txt)。

[干净构建收据](additional/1-receipt.json)：Release/MSVC、Geant4 11.3.2；exe SHA `8055edd08ef07aa6eee7d710c8d360b83e8bec60cb410160f4b89aad61d6f25b`。source fingerprint=`db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc`；tests fingerprint=`92c2c470814b0bea95d918e3393394a9c39ff5897fc3d57e64d33ef7e6174ddb`。指纹相同之外的 workflow/requirements 范围由上述完整 Git 树核对补足。

## 最终矩阵

| 验收项 | 要求 | 实际终态 / 原件 |
| --- | --- | --- |
| Windows all，产品7d | 152项，28 static / 44 GUI / 59 backend / 21 integration | `152` / `152`；`49,913` 个v3断言；[报告](windows/final-1/report.json) |
| Linux Geant4 11.3.2，CI a9 | 全部152项、四profile | `152 PASS / 0 FAIL / 0 SKIP` |
| Linux Geant4 11.4.3，CI a9 | 全部152项、四profile | `152 PASS / 0 FAIL / 0 SKIP` |
| M0 Windows / Ubuntu，CI a9 | 各72项 | `72 PASS` / `72 PASS` |
| CI完整性 | 4官方artifact、12实际报告、448次用例执行 | `4官方ZIP / 12报告 / 448执行；109,307个v3入口`；[CI原始收据](ci/ci-evidence.json) |
| 严格门禁 | 无fail/skip/零断言，原日志SHA；同v3 F1逐例/总量及反例检查 | `Windows及F1逐项/总量门禁通过；CI同平台/版本/profile门禁12/12，helper6/6，篡改负对照2/2`；[F1原基线](baseline/1/report.json) |

Windows原始报告来源：`out/verification/f4-release-windows/20261030-202435-a53c3ee6/report.json`。CI原始收据来源：`out/verification/f4-ci-a9ad09d/ci-evidence.json`。真实 run：[Linux 41056994075](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41056994075)、[M0 41056993987](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41056993987)；最终结论 `两个workflow均completed/success`。不得拿旧7d的M0绿色填补a9缺失报告。

## 已确认的 Windows 原生验收

产品7d、[host v2身份](visible/1-f4-visible-7d718d0/identity.json)，13种合成状态、19张实际查看的JPG、15对输入前后业务hash一致（12次完成定位/查看源、2次选行、1次Esc相关输入）。几何第三行size、材料density、第二层thickness、布尔operation、场景高级字段、向导早期页和扫描Enter定位均准确可见；旧报告禁用定位，当前源/历史源说明分明。已观察浅色/深色、中英产品界面；[逐图独立审查](review/1-f4-native-7d718d0-independent-final-review.md.txt)包含适用边界。

[真实Inspect原文](visible/1-f4-visible-7d718d0/inspect.stderr)对应正常非零拒绝 exit1，`--inspect-run` 不启动模拟、无run_summary，GUI未伪造位置。host requested return0与[launcher实际进程退出0](visible/1-f4-visible-7d718d0/launcher.json)分开确认，session19960；[原始事件](visible/1-f4-visible-7d718d0/events.jsonl)和[独立机器审查](additional/15-f4-native-7d718d0-independent-final-review.json)可对账。原件中的pending/not_claimed是生成时历史状态，未追改。

03图不能排除高亮定时器同时清除，**不作Esc独占因果证明**；源文件两态是独立解析器夹具，不证明当前生成配置被执行。哈希证明限已记录输入；主题/语言菜单没有单独事件配对，其严格身份不变另由自动回归证明。本轮不是Linux原生桌面、所有DPI/主题或物理验证。

## DeepSeek 与依赖修复

实际设计咨询：`deepseek-flash`，response `ed8eb74c-0550-4f78-8b5a-14655a61b685`，2255 tokens（504/1751），UTC 10:27:53。[原始响应与调用收据](design/design-response.json)、[采纳与纠偏记录](design/design-receipt.md.txt)。角色是前端设计咨询，不宣称它实现产品或完成视觉验收。

Linux CPython3.11 + PySide6/shiboken6 6.12.0 的 None 引用负例与原CI异常退出均保留。采用 `PySide6>=6.11.1,<6.12`，两个稳定版本定向各413断言正常退出；移除全局conda库注入，a9补足干净Linux runner系统GUI库。见[依赖证据清单](additional/81-manifest.json)；此局部实验不替代最终矩阵。几何滚动缺陷按实际单元格修复，QA host Close异常仅修out辅助程序。

## 原样保留的历史轮次

| 原轮次 | 已发生事实 | 归档入口 |
| --- | --- | --- |
| Windows5d中止 | 92 PASS + 1 FAIL 后终止，无完整report；不补造后续结果 | [中止收据](history/windows-round-1-20261030-192616-7a34aee1/interruption.json) |
| Windows096旧完整轮 | 151/151，49,905个v3断言；属于旧候选，不能替换新152项 | [原报告](history/windows-round-2-20261030-194526-3f060b82/report.json) |
| CI5d | 12报告、444执行，440 pass/4 fail | [原汇总](history/ci-round-1-f4-ci-5d6f008/round-summary.json) |
| CI096 | 8报告、284执行，281 pass/3 fail；4个后续profile未执行 | [原汇总](history/ci-round-2-f4-ci-096f4b3/round-summary.json) |
| CI7d | 6报告、200执行，190 pass/10 fail；6个Linux profile未执行，缺libEGL | [原汇总](history/ci-round-3-f4-ci-7d718d0/round-summary.json) |
| 原生5d / 096 | 前者目标不可见、host退出0；后者QA host异常退出-1073740791 | [5d收据](history/visible-round-1-f4-visible-5d6f008/launcher.json)、[096收据](history/visible-round-2-f4-visible-096f4b3/launcher.json) |

最终4个官方ZIP按原始摘要验证，原容器保留在来源；历史CI容器作为失败历史保存。所有日志/JSON/图像按原字节归档，历史Markdown采用`.md.txt`呈现，后缀不符的历史图像不转码。事件和stderr的`.txt`副本仅加呈现后缀，原路径与SHA见[副本收据](additional/57-raw-text-copy-receipt.json)。

## 审查与归档范围

双提交归档工具已通过[独立复审](review/5-f4-core-mixed-head-helper-review.md.txt)，严格限定精确六行CI依赖变化。原件/副本SHA、完整成员集合和前后严格门禁由归档收据记录，Git暂存与集成由后续关闭回信记录。[最终总审查](review/4-f4-root-prearchive-review.md.txt)：`产品/矩阵/实窗与归档工具审查通过；具体复制与发布门禁见archive-verification.json和archive-complete.json`；集成结果 `本快照生成时尚未快进，后续实际提交记录于仓库F4关闭回信`；阶段关闭决定 `工程验收通过；发布后的阶段关闭由主负责人单独记录`。


Linux八份报告git_dirty=true，M0四份false；原值保留，依赖目录能解释但未保存全部porcelain条目，不声称CI干净。实际CI Qt/PySide/shiboken为6.11.3；本机Windows为6.11.1。详见ci/README.md.txt与状态范围收据。
