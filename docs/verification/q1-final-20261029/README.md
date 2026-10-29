# Q1 最终验收记录（已完成）

验收代码：`8ecad66a5a3d1e9151cec4ed9a9035e70464577f`。Q1 九域审查、确认缺陷修复、独立复核和冻结平台矩阵均已完成；唯一阶段状态见 [ROADMAP](../../ROADMAP.md)，机器可读收据见 [verification.json](verification.json)。后续归档提交仅改变文档与证据，不能冒充另一次源码测试。

## 实现与审查

- 审查范围：配置/生命周期、几何/材料/SD、源/物理/场、计分/统计、偏置/权重、输出/后处理、GUI/进程、测试/交付与跨平台；逐域证据见 [关闭前复核](../../collab/reviews/20261029-q1-closure-review.md)。
- 问题索引 R01–R32：[问题与回归](../../collab/reviews/20261029-q1-findings.md)。其中包含测试平台和测试夹具问题，不能把32项都称为物理模型缺陷。
- 后续实现提交：`4ed7233` 后端线程偏置/随机语义/多run/原生UI守卫，`cb54669` 自动结果来源，`5ffe9b6` 探针v3/测试调度假设，`8ecad66` 绘图测试完整来源夹具。前24项实现及旧候选证据保留在历史记录。
- DeepSeek参与R27前端/结果链审查，merge计划来源竞态由独立复核推动修复；调用与采纳记录见 [来源审查](../../collab/reviews/20261029-q1-output-provenance.md)。

## 平台证据

| 项目 | 当前结论 | 证据 |
| --- | --- | --- |
| Windows / MSVC / Geant4 11.3.2 干净Release | **105 PASS / 0 FAIL / 0 SKIP**，83770个v3入口，零断言用例为空，严格及基线门禁通过 | [原报告](windows-full/report.json)、[门禁](windows-full/evidence-baseline-gate.log)、[构建日志](windows-build/build.log) |
| Windows真实窗口 | 通过：保存/生成/20events成功，取消及关窗killed、自有进程停止 | [report](windows-visible/report.json)，[结果截图](windows-visible/results.png)，[取消截图](windows-visible/cancelled.png) |
| Ubuntu24.04 / Geant4 11.3.2与11.4.3 | 通过：两个版本各105项，四profile发布门禁及篡改负向门禁通过 | [CI收据](ci/ci-evidence.json)；[run40855144863](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40855144863) |
| Windows/Ubuntu static与GUI CI | 通过：两个平台各11 static +31 GUI，报告门禁通过 | [run40855144672](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40855144672) |
| 同v3旧基线对照 | 旧binary 98/98通过、79303个v3入口；候选83770，逐例及总数不下降门禁通过 | [基线报告](baseline-v3/report.json)、[门禁](baseline-v3/evidence-gate.log)、[测量overlay](baseline-diagnostics/measurement-overlay-final.json) |

## 必须保留的限制与兼容变化

- worker偏置实际执行和步前权重修复会改变历史偏置结果，旧结果须重跑；调用收据/原生同run对照不证明无偏性、方差收益或所有能区/材料的物理正确。
- 后端交互执行必须显式 `--ui --ui-session csh`。裸--ui/仅INI interactive未选csh明确拒绝；Python桌面GUI正常运行与预览保留。连续多轮用beamOn，运行后重建内核须新进程。
- V01统计估计量与小样本覆盖率、Q2外部物理基准、完整2C、Windows11.4、安装器/原生Linux桌面不因本次工程验收自动完成。
- manifest约束自动输入归属，不是结果文件内容签名或跨进程原子快照保证；legacy输入明确未验证。

旧失败证据不得改成绿色：f407 CI因绘图fixture漏summary失败，本机对应全量主动停止；产品源码未变，8ec补齐fixture后重新开始完整验收。旧v3测量的目录复用/调度假设失败同样保留。原始报告/日志均保留，复制清单记录逐文件SHA-256；本机旧任务的中止收据见 [interrupted-f407.json](windows-build/interrupted-f407.json)。没有修改旧报告或把被中止的运行写成通过。

已归档CI包含4个GitHub artifact原ZIP及解压文件，GitHub SHA-256匹配、12份报告发布门禁均过；两Linux job的篡改报告负向对照均success。源码指纹统一 `d9c4378a03052a05cc59b55259ba5e99c32a056e0a7d87b92257ca21948bec4b`；测试指纹统一 `5bcb7ac101df9d3cdcb71e9915b4f68e8eeed4d178f556793367a126f4d8bae8`。报告逐profile数量见 [汇总](ci/report-counts.json)。归档包含旧失败CI、旧测量失败，不删除诊断以制造全绿。

## 关闭裁决与后续

- 审查索引 R01–R32 已闭合，包含产品缺陷和测试/证据缺陷；不同写者交叉复核，DeepSeek 参与前端审查。关闭以本基线和约定公开能力范围为限，不承诺不存在未发现问题。
- Windows 使用 MSVC 19.51.36246.0、Release、Geant4 11.3.2 MT/GDML；运行时检出无未提交修改，105组分布为11 static、31 GUI、46 backend、17 integration。可执行 SHA-256：`688f1a454583006d713c6aad93f78b9690acf29bc16dfe79bddc7f1d38804998`。
- 旧基线使用4e6fa7a产品二进制及已登记的五项测量overlay；v3是保守assert入口计数，不是独立科学命题数量。没有与历史v1/v2虚高总数直接比较。
- 下一完整阶段为2C（全消费者来源、三阶段应用证据及off/auto/on）；Q2继续承担独立物理/统计适用范围验证。

## 提交与集成节点

- `8ecad66`：被测试的冻结代码/测试提交。
- `d02f629`：完整验收文档与987个原始证据文件归档；Git暂存内容逐文件与工作副本字节一致，文档链接检查通过。
- 已在独立q1-final工作区将codex从5465dbd正常快进到d02f629，合并后工作区干净；[本地集成收据](local-integration.json)。当前交接提交仅追加状态文档，不改变验收源码/测试。远端普通推送结果另由本轮工具收据确认，不把文档SHA冒称已测试代码SHA。
- D:/Geant4/G4UniversalSim仍保留roadmap/F6-live-progress及邻线未跟踪审查文件，未对其切换分支或覆盖。保留q1-final中的已验收Release供后续使用；旧测量工作区的必要证据已归档。
