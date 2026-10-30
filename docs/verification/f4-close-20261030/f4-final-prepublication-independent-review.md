# F4 正式归档计划发布前独立复审

结论：**通过，可由root发布此固定计划，无阻塞项。尚未发布归档，也未据此自动关闭阶段。**

本次检查对象为 `out/collab/f4-final-publication-plan.json`，SHA256 `5b46eddd49ed1a65c40746449bae6e57c2e714f1922a6048bf2597ba50d52871`，2495个源文件，不是早期selftest计划。真实执行 `prepare-f4-archive.py --review-plan`，session6837已poll至实际退出0，结果为 `review_passed_not_published`；目的目录 `docs/verification/f4-final-20261030` 仍不存在。

- 临时副本中13份正式报告门禁全部通过：Windows all保留产品7d、12份CI保留a9。Windows同v3 F1基线48511门禁通过；完整11340项Git树、原始commit与精确六行apt差异校验通过。原生identity仍为7d，launcher真实进程退出0，不把CI提交改标为实窗提交。
- 2495个源文件尺寸和SHA全部与计划匹配，复审后再次核对仍一致。独立枚举11个输入根，无未说明漏项：最终Windows153/153、native48/48；CI519个源文件中515纳入、4个官方ZIP按显式F1规则留在原处。全部历史根逐文件纳入，历史ZIP、原始events.jsonl/stdout/stderr均保留。
- 三轮失败CI原件明确隔离：5d为12报告/444执行/4失败；096为8报告/284执行/3失败、4profile未执行；7d为6报告/200执行/10失败、6profile未执行。均未算入最终12报告。首次Windows中止没有补造report，旧096完整Windows仍保留旧候选身份。最终7d native未被同SHA旧CI失败误归为失败native。
- README的25个本地链接全部按未来归档路径检查通过，无对原out目录存在性的依赖。README将已完成的工程、矩阵、实窗验收与后续复制发布、codex集成、单独阶段关闭回信区分；工具仍明确phase_complete=false和visible_acceptance不由工具裁定。历史pending原字节未改，归档前root裁决不是发布后关闭记录。
- Linux8份报告git_dirty=true、M0四份false均保留；依赖目录说明不冒充完整porcelain清单或干净CI。DeepSeek咨询、离屏回归、真实Inspect与原生观察范围分别计证，未扩为物理验收。

机器证据：`out/collab/f4-final-prepublication-independent-review.json`；临时复制全部门禁：`out/collab/f4-final-prepublication-review.json`；真实运行日志：同名`.log`。这些新复审输出未写入已冻结CI目录、未修改本计划选择的源文件。若计划或任何输入字节发生变化，必须重新验证，不能沿用本次固定SHA结论。
