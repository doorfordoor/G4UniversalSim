# 阶段 1d 验收证据（2026-10-28）

本目录是**阶段 1d（证据门禁自洽性加强 + 日志摘要按落盘字节计算）**的全量回归证据副本。

- 报告：`report.json`（`version: 2`，`profile: all`，79 例全部 pass）
- 逐用例日志：`logs/`（79 个，报告内 `log_sha256` 与这些文件的**原始字节**一致；本目录由 `docs/verification/** -text` 保证不被换行改写）

## 报告事实（可直接复核）

| 字段 | 值 |
| --- | --- |
| 基线提交 | `48d8c68`（上一轮提交；本轮改动工作区未提交，`git_dirty=true`） |
| 用例 | 79 pass / 0 fail / 0 skip（static 6 / gui 26 / backend 33 / integration 14） |
| 断言证据 | `assertions_executed_total=116161`、`assert_sites_total=2393`、`cases_with_zero_assertions=[]`、`assert_probe=settrace_assert_lines_v2` |
| 摘要算法 | `log_digest_algorithm=sha256_raw_bytes_lf_v2`（日志与报告按 UTF-8/LF 字节写出并对落盘字节计算） |
| 源码指纹 | `ba493e735b11ca414fa63bbd9d5c219766a5bb60c838482fa69a884cef558d93` |
| 测试/夹具内容指纹 | `0d5c7cc0398c1261e00c1a3c333cebe23c38ef38455b4fd7aa95c1ebae1069e5` |
| 后端 | `G4UniversalSim.exe` SHA-256 `c446ed5e4be6c0380cf80ebeaf9e6596cd8d0bba07b122080fa0a8c79be8d315`，MSVC 19.51.36246.0 + Geant4 1132 + MT |
| 运行环境 | Windows-10-10.0.26200-SP0，Python 3.11.9 |
| 门禁 | `python -B scripts/check_report_evidence.py --report-root out/verification/stage1d-20261028` → `report evidence: OK` |

## 本轮解决的两个缺陷（Astra 2026-10-28 审查 D-1 / D-2）

1. **证据门禁可被篡改绕过**：此前门禁只检查"总数 > 0、摘要字段非空"。实测把任一通过项的 `assertions_executed` 改成 `0` 并补进 `cases_with_zero_assertions`、或把某个 `log_sha256` 换成 64 个 `0` 并把 `assertions_executed_total` 放大到 `999999`，旧门禁都输出 `OK`。现在逐项校验断言 ≥ 1、`exit_code == 0`、逐项求和与总数一致、计数/零断言列表与实际记录一致、`log_sha256` 与磁盘日志字节一致、发布报告无 fail/skip，并支持 `--baseline` 断言不下降。
2. **日志摘要口径与磁盘字节不符**：此前日志用文本模式落盘（Windows 下 CRLF）却对内存 LF 字符串算摘要，归档的 `docs/verification/stage1b-20261028/` 79 个日志**原始字节 0/79 匹配、CRLF→LF 归一后 79/79 匹配**。现在日志与 `report.json` 都用 `write_bytes` 写 UTF-8/LF 并对落盘字节计算摘要，报告新增 `log_digest_algorithm` 字段；归档旧报告只能加 `--allow-legacy-digest` 复核。

## 复现

```bash
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --report-root out/verification/stage1d-20261028
python -B scripts/check_report_evidence.py --report-root out/verification/stage1d-20261028
```

## 这份证据不证明什么

- 不包含 Linux 或 GitHub Actions 上的后端运行（E3/2A 未建立）；CI 目前只跑 static+gui。
- 断言数是**已执行 `assert` 的下界**（`sys.settrace` 计数），不是覆盖率；门禁只证明"报告与日志自洽且未被篡改"，不证明断言写得好。
- 不证明任何物理结果的正确性；物理基准见 `scenarios/benchmarks/*` 与 `docs/功能支持矩阵.md`。
