# F1 自动归档的独立复核收据

本目录补充[自动验收归档](../f1-automated-20261030/README.md)的发布前、发布后独立审查，不改写该归档的原件、README 或完成清单。**F1 实窗仍待验，阶段未关闭，未合入 codex。**

- [发布前独立审查](prepublication-review.md)批准计划SHA `a5d05c536c31899529cdc4a78d7738693dc1a0e326f3b4eb521e0e349d57ae8a`；2797源文件、23个本地链接及13份正式报告门禁通过，两个Linux GDML原日志均确认故障后的资源关闭。[机器收据](prepublication-gates.json)。
- [发布收据](publication-receipt.json)记录按该计划独占发布后的重新校验；复制过程退出0。
- [发布后独立审查](postpublication-review.md)复核2797原件、38个生成核验文件、完成收据之间的哈希、13份正式与22份历史报告的分类、E6逐项基线及CI拓扑，未发现阻断项。[独立字节检查](postpublication/independent-bytes-check.json)。
- [本目录复制清单](review-copy-manifest.json)登记9份原审查/工具收据的字节摘要；新索引README本身不属于原收据。

产品冻结为 `f176d0ed4cea60b7ca5a80ed81017c9404ec1257`。后续文档提交只存证与更新当前状态，不把文档HEAD改写为已测可执行文件的构建提交。实窗完成时需建立新的可见验收证据，不能追改本次自动归档。
