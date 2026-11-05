# Q2-4 执行验收：冻结范围通过

产品 `864bc036d6d7752475e52db4efd2b950cabfcc3d`，Windows / Geant4 11.3.2；exe SHA `f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f`。沿用[冻结统计合同](../../collab/decisions/20261105-q2-uncertainty-freeze-v1.json)。round85 / turn70 首次交付；round86 / turn71 完成三处证据修订，2026-11-05 经[独立复验](../../collab/reviews/20261105-q2-uncertainty-execution-review-r1.md)签收 Q2-4。

- [原始交付 ZIP](original-v1.zip)：1,109 个成员，含 982 个原始运行文件和原回执；7,021,306 字节，SHA-256 `3dfd72a31ed65a7b2eba22347bb904db12e696ce98978071257d2f6c31eec7a2`。在 C 盘独立复制，核 CRC 和逐成员 [SHA](original-v1-manifest.json)；D 盘归档副本再按原字节比对。
- [独立原始数据核对](independent-raw-report.json)：3,656 项核对、0 个问题。69 次有效运行、130,123 个完成事件；独立从原始 CSV 复算两个 Dose 量、LET 比值与协方差、全部 64 批的 raw/weighted 路径/注量矩、N 和 entries。20 事件病例包含 5 个零贡献行；N=1 和全零输出按合同处理。未再做 Geant4 输运。
- 64 批的 K=1351–1436；63/64 覆盖，合计 K=88,809。种子 220004 的 K=1436 正常未覆盖，保留在分母中。整体满足冻结的 C≥57、总 K∈[88,464,89,313]，适用范围仅为该几何、模型、种子表与估计量。
- [真实 C++ 合并探针](merge_probe.cc) 链接同 SHA 的 `src/Scoring/HistoryStatistics.cc`，先在每个事件合并两个贡献，再以两个 worker Submit/Take，合成 N=4、S=6、S2=18、entries=3；[收据](merge-probe.json) 显示 R=0.5，错误平均 0.35355339059327379 被拒绝。这是预注册要求的可区分组件观察，实际 N=2 的 Geant4 稀疏分配只有一个非空 worker。
- [独立审查反例](../../collab/reviews/20261105-q2-uncertainty-execution-review-v1.md) 明确初版比较器三个证据缺口。[两条副本复现](witness-v1.json) 核实初版未拒绝 LET master value 13.9334540572→100、覆盖 entries 1413→1。保留原自测的 526 与 8 项报告。原始物理输出核对和作者交付修订属于两个证据层。

独立脚本 [audit_raw.py](audit_raw.py) 在 C 盘仓库 `out/collab/q2-uncertainty-execution-independent/` 读取同目录冻结 ZIP 和 C 盘已验证后端，核 D 盘冻结合同及原输入清单。各项文件和组件编译身份见[独立证据清单](independent-manifest.json)。尚无新增 Linux 或云 CI，Q2-6 单独核验。

[R1 修订增量](revision-r1.zip) 与原 ZIP 联合保留比较器、报告、探针、运行收据和副本；只更新证据解释和判定，原运行字节不替换。[封存收据](r1-seal.json) 对照核过 982 个原始运行文件、17 个输入以及两个身份文件，共 1001 个。只读复演得到 527/527，8 个原定负对照及 2 个定向副本均检出；[C 盘复演](author-r1-probe-replay.json) 再次通过 7 个状态、事件矩和真实组件合并，[定向复验](witness-r1.json) 证实初版两条漏检均已修复。无额外输运、种子或样本。Q2-5 预注册独立进行，整阶段 Q2 尚未关闭。
