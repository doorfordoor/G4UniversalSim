# Geant4 11.4 支持与版本矩阵（2026-10-28）

本目录是 `python -B scripts/run_m0_tests.py --profile all` 的归档证据：87 个用例与 87 个逐用例日志，`report.json` 位于本目录根，日志在 `logs/` 子目录（`scripts/check_report_evidence.py` 支持这种归档布局）。

## 报告事实

| 项 | 值 |
| --- | --- |
| 报告 | `version: 2`、`profile: all`、`skip_policy: failure` |
| 用例 | 87 pass / 0 fail / 0 skip（static 10 / gui 27 / backend 35 / integration 15） |
| 断言 | `assertions_executed_total = 116677`，`assert_sites_total = 2702`，`cases_with_zero_assertions = []` |
| 断言探针 | `settrace_assert_lines_v2` |
| 源码指纹 | `3ad03f2d62c354323f86edeb57c4479219ad75ca568ce3f8b3037c3c5d49aca9` |
| 测试/夹具内容指纹 | `4eca0c97e22d4e45310b13e8ae3d556d2ceb8e1bfeb63906a43b4dd9cb857d02` |
| 日志摘要 | `log_digest_algorithm = sha256_raw_bytes_lf_v2`（按落盘字节计算） |
| 后端 | `G4UniversalSim.exe` 1734656 B，SHA-256 `f78fa2fb06c08dbebd590bf7457f306ec85d9d6a7a8c0f0b30f5b7daeb6b45e1`，MSVC 19.51.36246.0 + Geant4 11.3.2（Windows）+ MT |
| 运行环境 | Windows 本机；`git_head = 6a8b237`、`git_dirty = true`（本批改动在运行前未提交） |
| 门禁 | `python -B scripts/check_report_evidence.py --report-root docs/verification/stage-11d4-20261028` → OK |

## 本轮改了什么

1. `src/Core/Geant4DataLocator.cc` 的数据集表新增 Geant4 11.4 分支（12 个数据集，前 5 个 required）。本机 WSL 实测 11.4.3 可构建、四个 profile 87/87 全过（backend 109,942 断言；static 391、GUI 1,877、integration 4,364）。
2. 三个版本相关测试缺陷改为版本无关：数据文件夹从 `--check-geant4-data` 的 discovery 取、激发态核名按能级数值容差匹配（11.3 `Ni60[2505.753]` 与 11.4 `Ni60[2505.75300]` 只是格式化差异）。
3. `.github/workflows/linux-geant4.yml` 加 Geant4 版本矩阵（`11.3.2` / `11.4.3`），每个版本独立前缀、独立报告根、独立 artifact；GDML 期望值改为从构建出的可执行文件 `--capabilities` 读取。

## CI（本次推送真实结果）

- `6a8b237` 上两条 workflow 全部 `completed success`：`Linux build and backend regression` 有 **`ubuntu-24.04 / Geant4 11.3.2` 与 `ubuntu-24.04 / Geant4 11.4.3` 两个 job 各 26 步全绿**（run [40690078563](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690078563) codex、[40690070991](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690070991) roadmap）；`M0 static and GUI regression`（ubuntu + windows 的 static 与 offscreen GUI）run [40690078519](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690078519)、[40690071129](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690071129) 亦全绿。

## 复现命令

```
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --report-root out/verification/stage-11d4-20261028
python -B scripts/check_report_evidence.py --report-root out/verification/stage-11d4-20261028
```

## 不证明什么

- 只覆盖本机 Windows + Geant4 11.3.2 的完整 profile；Linux 侧结论来自 CI（11.3.2 与 11.4.3 两个 job）与本机 WSL，不在本目录。
- Geant4 11.2 未测；Windows + 11.4 未验证；11.4 下的真实桌面 GUI、ROOT/uproot 与打包流程未验证。
- 断言数是已执行 `assert` 的下界，不是覆盖率；证据门禁只证明报告与日志自洽且未被篡改。
- 11.4 的物理结论没有独立基准支持，不能把 11.3 的物理结论直接搬到 11.4。
