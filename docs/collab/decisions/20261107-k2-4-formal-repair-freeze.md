# K2-4 两处正式阻断：最小修复独审冻结

以本提交冻结修复工程候选；原正式候选 `4bc77b5b80a2d3309cb8f972f33d4110ce1986ce` 的失败全部保留。仅修改 `scripts/test_k2_project_export.py`、`packaging/ci_delivery.py`、`scripts/test_install_ci_delivery.py`，代码差异 +33/-4。未改变扫描器、夹具策略、产品C++、导出实现或模板manifest。

主审已逐行检查：Windows文档命令从真实导出预设推导；恶意盘符数据复用现有已命名拒绝夹具，原拒绝类型和断言保持。安装源码快照根文件集合补入CMakePresets.json，并在原临时origin测试中验证实际字节、收据成员及SHA。不是扩大路径豁免或重构验收框架。

作者已提交 `out/collab/20261107-k2-final/author/repair-receipt.json`，明确三个文件停写。主审逐一核对作者文件SHA、所有具名验证证据SHA及独立审查副本字节，原回执保存于 `out/collab/20261107-k2-final/independent/hb1310/author-repair-receipt-original.json`。

独立C审查树实际运行四项：平台路径3断言、夹具策略51断言、安装快照49断言、K2导出3550断言，全部exit0。C审查环境文件symlink探针不支持，相关两条断言未执行，junction分支实际执行；作者D环境3552仅按作者身份保留，不能冒充主审3552或全链接路径覆盖。详见同目录 `targeted-results.json` 与原始日志。这些是定向修复签收，不冒称正式profile全通过。

主审从实际审查树调用修复后的snapshot_sources，生成980文件新快照；逐个按manifest原始source_path核验309模板成员规范字节/SHA，再调用真实build_export_template写出包内模板。无缺失/不一致；CMakePresets确在快照收据中。详见 `actual-snapshot-and-package-template.json`。模板仍为 `b2285d117a557614782eb8656593c2a64b9caba4538de91410126d7db35ba878` / 309成员 / 3820084规范字节，未重生成manifest。

原desktop两平台167个GUI源文件与4bc Git字节及8份命令日志SHA已独核，正常exit0与两类预期拒绝exit1分别保存，见 `out/collab/20261107-k2-final/original-ci-independent-check.json`。该证据仅证明冻结GUI/ROOT helper原范围，不能替代安装后K2实际导出入口。

签收结论：两处最小修复允许进入正式云复验。K2-4仍为进行中，须完成原定正式报告/严格证据/真实云CI及必要真实入口观察。旧4bc失败不改写，旧K2-3科学/原生产物保留原SHA按未受影响范围复用，不因本次脚本修改循环编译/科学矩阵。

作者回执的首个原失败workflow标签误写为full-installation；真实job128408194604属于M0 static and GUI regression run42374151337，主审依据实际云回执纠正对应关系，不修改作者原收据。Windows原安装任务继续跟进原终态。F3及网页暂停保持原约束。
