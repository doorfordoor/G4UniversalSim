# F4 完整阶段关闭审查（2026-10-30）

F4结构化诊断与定位已完成实现、交叉审查及约定验收，未发现未关闭的阻塞缺陷。原始证据已发布并经机器复核；本记录形成时codex尚待正常快进，实际集成追加在文末。F5未启动。

## 交付与身份

共享诊断模型与列表、字段和表格单元格定位、跨页/高级区域展开、只读当前/历史来源、旧报告和陈旧异步结果保护已接入配置、项目/运行、场景、向导及扫描。运行包新增validation_diagnostics.json，旧文本报告与拒绝规则保留。定位不自动改配置；没有可靠位置时保留原文并明确不可定位。

产品与本机Windows/实窗：`7d718d038a00d89995ea773b4772764116b620c3`。真实CI：`a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9`，仅增加Linux CI六行系统库安装。完整11,340项Git树证明其余条目一致，[身份映射](../../verification/f4-final-20261030/identity/identity-map.json)保留两个SHA，不以相同指纹冒称提交相同。

## 验收

| 项目 | 结果 |
| --- | --- |
| Windows完整矩阵 | 152 PASS / 0 FAIL / 0 SKIP，49,913个v3入口；原会话实际退出0 |
| F1同口径基线 | 原143项/48,511入口，旧项逐例及总量无下降；日志原始SHA门禁通过 |
| Linux Geant4 11.3.2 / 11.4.3 | 各152项通过；[run41056994075](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41056994075) |
| M0 Windows / Ubuntu | 各72项通过；[run41056993987](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41056993987) |
| CI证据 | 4官方ZIP、12报告、448次执行、109,307个v3入口；12/12基线门禁、6/6辅助程序、2/2篡改负对照通过 |
| Windows原生窗口 | 13态、19张逐张复审截图、15对操作前后业务hash相等，实际退出0 |

Linux八份报告git_dirty=true、M0四份false，原值保留。已安装依赖目录能解释Linux标志，但没有完整porcelain清单，不称CI全部干净。Qt实际CI为6.11.3，本机为6.11.1，依赖约束及旧6.12.0失败实验均保留。

原生覆盖Windows当前尺寸与选定中英/明暗状态；源预览是独立解析器夹具，Esc手动观察不能排除计时器清除。真实Inspect拒绝不代表执行模拟，统计计数不代表新增物理验证，optional PyVista不提升为已验。详细边界见[最终报告](../../verification/f4-final-20261030/README.md)与[原生独审](../../verification/f4-final-20261030/review/1-f4-native-7d718d0-independent-final-review.md.txt)。

## 修复、协作与归档

几何单元格选中却不可见的缺陷已修复并由实窗补验；Linux绑定生命周期及库混载/缺系统库分别修复。旧native辅助宿主Close遍历导致的崩溃只在out宿主修正，旧失败未改写。DeepSeek实际提供前端设计咨询，其他写者实施并交叉审查；不把咨询说成代码或视觉验收。

固定归档包含2,495份源证据，连同生成门禁文件共2542个文件。发布前独立临时复制、13份正式报告/F1基线、25个便携链接及原始字节检查通过；发布后工具再次验证完整成员集合与SHA。[归档清单](../../verification/f4-final-20261030/archive-manifest.json)、[发布后门禁](../../verification/f4-final-20261030/archive-verification.json)、[完成标记](../../verification/f4-final-20261030/archive-complete.json)和[独立发布前审查](../../verification/f4-close-20261030/f4-final-prepublication-independent-review.md)可复核。

三轮失败CI、Windows中断轮与旧151项通过轮、两轮失败native均原样保留，均不计本轮正式通过。历史F1/E6归档和原D盘DSH工作区未改。主审[归档前裁决](../../verification/f4-final-20261030/review/4-f4-root-prearchive-review.md.txt)与本记录分开，旧pending文本仍表示其生成时状态。

## 集成记录

关闭提交`20f8562d9787234fece40f2a82bc08f3c1284e3f`已从`0456253`正常快进至codex并推送；记录时本地两工作树与两远端分支均为该提交，工作树干净。原D分支仍为roadmap/F6-live-progress、HEAD5465dbd，未修改。见[实际集成收据](../../verification/f4-close-20261030/integration.json)。本回信随后仅追加事实记录，不改变已验产品及测试指纹。

发布后[独立索引审查](../../verification/f4-close-20261030/f4-final-postpublication-index-review.md)确认固定2561路径中的2548份证据raw blob全部一致。随后新增测试平台状态说明和两份独审原件；原2561 blob保持不变，最终2564路径增量已核对。文档链接514条/198文件无断链；原证据CRLF/尾空格按原字节保存。完整阶段关闭，下一完整代号F5，未启动。
