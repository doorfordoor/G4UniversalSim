# F1 阶段关闭回信

分支：`roadmap/F1-output-provenance`；产品 `f176d0ed4cea60b7ca5a80ed81017c9404ec1257`，实窗GUI `ede037f26db63f606e3ca086d5d586f222f428df`。涉及来源/输出/GUI及最终验收文档。结论：F1约定范围完成；普通集成事实随后记录在[最终报告](../../verification/f1-visible-20261030/README.md)。待DeepSeek动作：当前无新增代码任务；保留原工作区，F4启动再领明确设计范围。

| 事项 | 判定与依据 |
| --- | --- |
| GDML分配失败收尾 | **确定为缺陷（已修复）**。`src/Geometry/GdmlInputCapture.cc:139` 已将FileBuffer分配纳入原生句柄关闭保护；修前4开3关、修后4/4及Xerces故障5/5，最终Linux双版本真实回归通过。见自动归档第二轮失败与最终证据，不以Windows成功代替Linux。 |
| auto与缓冲 | **无问题（限定已验范围）**。`src/Output/OutputManager.cc:201` 记录auto选择原因；显式auto不改变默认CSV。`docs/collab/inbox/20261030-1500-astra-f1-format-decision.md:21` 固定选择规则。72次测量不支持候选稳定收益，撤回符合契约。 |
| GUI身份和实际观察 | **无问题（限定已验范围）**。`gui/g4usim_gui/widgets/output_identity_panel.py:65` 分开清理/展示身份状态；14次原生图像观察与字节/关闭审计在 `docs/verification/f1-visible-20261030/evidence/review/f1-visible-final-audit-review.md:3` 给出APPROVE。合成历史未证实、07 UIA滞后如实保留。 |
| 阶段验收与身份 | **无问题**。`docs/verification/f1-visible-20261030/closure-state.json:4` 独立登记阶段通过；host原pending和GUI/build commit不等字段不追改。Windows143、Linux双版本各143及M0双OS各64的正式报告均通过门禁。 |
| 物理适用范围、任意资源导出、全DPI/原生Linux桌面 | **需实验**。`docs/verification/f1-visible-20261030/README.md:39` 保留Q2/K1/J1/I2等独立边界，不随F1关闭。 |

前端设计来源见[DeepSeek真实设计记录](../outbox/20261030-deepseek-f1-design.md)。本轮不提出额外代码修改；若后续发现新缺陷，按新基线保留反例、先登记提案与验收标准，再安排修复。下一完整阶段F4，保留file/line/来源与不可定位状态，不为界面跳转伪造位置。
