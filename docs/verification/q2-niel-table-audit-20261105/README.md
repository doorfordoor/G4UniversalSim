# Q2 硅 NIEL 表审计最终限定证据

2026-11-05。结论：**结构/算术通过；物理评价限制，主审签收此适用域**。本次没有运行 Geant4，也未改产品、两张表或冻结合同。

独立 C 盘复演得到 27 pass / 0 fail / 3 limited；另用 60 位 Decimal 独立复算完成 17 项检查，5 个篡改副本均命中真实 fail，原件不变。audit.py 的退出码 1 是显式 overall limited，不是后端失败；组件复算和反例脚本均退出 0。详见[独审](../../collab/reviews/20261105-q2-niel-table-audit-review-v1.md)和[机器回执](review-receipt.json)。

- [执行交付原件](author-v1.zip)：原脚本、结果、表原件、冻结合同、交付说明。
- [独立复核原件](independent-v1.zip)：独立运行日志、Decimal 程序与结果、原表/合同及执行脚本。
- [归档清单](archives-manifest.json)：压缩包与逐文件 SHA-256、字节数和 CRC 验证；旧记录不改写。

95 MeV·mb 是未核实的假设输入；两表注释是来源声明，没有取得 ASTM/SR-NIEL 原始发布物全文及模型版本对齐证据。插值相对差或与假设输入的差异只作算术记录，不据此判断物理缺陷或推断成因。本结论不补足 DDD 的完整逐步折积观测。
