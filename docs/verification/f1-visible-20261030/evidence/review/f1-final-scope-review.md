# F1 阶段关闭完整性审查

结论：**按本次开工契约对照，未发现 F1 实现范围遗漏；可以进入最终可见归档、文档关闭及普通集成手续。下一完整阶段应为 F4。** 本报告没有执行阶段关闭或集成。

核对基线：产品 `f176d0ed4cea60b7ca5a80ed81017c9404ec1257`，GUI 文档检出 `ede037f26db63f606e3ca086d5d586f222f428df`；两者相关源码/测试路径差异为空。依据包括开工契约、当前输出契约、自动归档原报告、最终观察/进程收据及 `out/collab/f1-visible-final-audit-review.md` 的独立 APPROVE。未重跑全量、未改产品/受跟踪文档。

| 原范围 | 当前证据与判断 |
| --- | --- |
| 来源与身份：开工契约 `:30` | 构建身份、实际输入读账、产物 scope/SHA、兼容及错误传播已有实现链与正反例。最终 Windows 报告中 build_identity、f1_input_provenance/resources、f1_artifact_model/output_identity、GDML、RNG、run_summary、ROOT 等均 pass；平台全量与两轮失败修复原件已归档。无新发现的范围遗漏。 |
| 消费者与界面：契约 `:31` | 统一验证、异步过期结果隔离、搬移及新旧协议测试通过；实际窗口补充了状态独立、构建/输入/产物、JSON 展开、缺失/篡改/legacy、历史详情与真实 auto 输出。DeepSeek 设计收据与窗口观察分别留证。 |
| 性能与 auto：契约 `:32` | 54 次格式测量与 18 次缓冲比较已保留。撤回没有稳定收益的 256KiB 候选，符合“先测量、不虚构收益”的契约，不是遗漏缓冲任务；现有标准流缓冲继续使用。显式 auto、默认 CSV、requested/resolved/原因及依赖变化已有测试，真实夹具确认 auto→ROOT。Python 复核时间不是 C++ 哈希 CPU 时间，旧候选测量也不冒充最终冻结重测。 |
| 冻结与验收：契约 `:33` | Windows 143/143、48,511 个 v3 入口及 E6 基线，Linux 两版本各 143 项、M0 两 OS 各 64 项，12 CI 报告/414 次执行记录与原字节门禁已归档。最终实窗 14 次观察、旧/新 host exit 0、关闭后无 F1 窗口，独立证据审计已 APPROVE。余下是正式可见归档、文档关闭和集成记录，不是尚缺一项实现。 |

## 视觉证据的归属与边界

视觉结论来自 root 在 `out/verification/f1-visible-20261030/observations.json` 保存的 14 次原生工具直接图像观察；**本审查者未查看截图，不能声称进行了独立视觉复验**。独立前端审计核对了图像/文本字节、身份关联与关闭链，也明确没有看图。

07 legacy 的同次 UIA 文本滞后，不能作为该页证据；该观察依 root 实际图像记录，原文本仍保留。合成历史没有真实进程退出证据，因此显示“结果未证实”；不能据此声称历史 success/failed 真运行已由这些合成图验证。真实夹具为 2 workers、2 run 各 2/2 事件、3 条读入记录及 20 项登记输出，与合成状态分开。

host 的原 `observation_acceptance=pending`、fixture 的原 pending 以及 `process-receipt.phase_complete=false` 都是采集时事实，最终审查在新文档中另行判定，不追改这些原件。GUI HEAD 与后端构建 commit 不同有明确文档提交原因及双指纹对应，不应把 `build_commit_matches_expected_head=false` 改成 true。

## 关闭前文档收尾

正式归档实窗原件与独立审查，给出新最终报告链接；同步 STATUS、ROADMAP F1 行、CHANGELOG、支持矩阵、Agent 历史/索引和输出契约的候选/待验措辞。特别检查 `docs/ROADMAP.md:27` 旧总表仍写 F1–F5 pending，避免只更新 `:263` 的细行。自动归档 README 的“当时实窗待验”属于不可改的历史，最终报告说明后续已补验即可。

正常集成仍按 `out/collab/f1-integration-precheck.md` 在最终关闭提交后重新核对远端与工作区，再在 q1-final/codex 快进；本审查没有提前执行。Q2 物理基准、K1 可移植配置/资源包、内部 Geant4/任意原生 IO 捕获、全部绘图后台化及 J1 布局均不属于 F1，本次不扩大完成范围。

## 下一阶段

**F4 顺序正确**：`docs/ROADMAP.md:239` 的当前排期明确为 F1→F4→F5→K1；`:266,274` 指定 F4 先交付可复用、语言无关的诊断身份与 editor/row/field/code 定位及点击跳转，供后续 K1/L1 共用。应保留真实 file/line/来源与不可定位状态，不能为跳转伪造位置；也不扩大 GUI 当前编辑白名单。I1 的只读环境设计可以按既定分工并行，F2/F3 不应因旧顺序描述自动插到 F4 前面。
