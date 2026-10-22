# 物理基准测试包（路线图 Phase B）

每个子目录是一个基准包：`reference.csv`（参考数据及出处）、可直接运行的 `example.ini` + `geometry.ini` + `run.mac`（在仓库根目录执行），以及说明 `README.md`。完整的对比由 `scripts/run_benchmarks.py` 运行：

```bash
python scripts/run_benchmarks.py --output benchmark_report
```

`--quick` 使用较少的病例与事件（统一测试平台的 `benchmarks` 用例即用此模式），`--only csda_range,gamma_attenuation` 只运行部分基准。报告写入 `benchmark_report.json` 与 `benchmark_report.md`；某病例通过的条件是 |模拟值 − 参考值| ≤ 系统容差 × 参考值 + 3σ（σ 为模拟值的统计标准误差），有任何失败时返回 1。

| 基准包 | 物理量 | 参考数据 | 系统容差 |
| --- | --- | --- | --- |
| `csda_range` | 质子 10–200 MeV、电子 1/10 MeV 在水中的 CSDA 射程 | NIST PSTAR / ESTAR | 质子 1.5 %，电子 3 % |
| `bragg_peak` | 150 MeV 质子笔形束在水中的远端 80 % 剂量深度 R80 | PSTAR CSDA 射程 × 迂回因子 | 1 % |
| `gamma_attenuation` | 0.1/1/10 MeV 光子在水、Al、Pb 中的窄束质量衰减系数 | NIST XCOM | 2 % |

2026-10-22 完整模式（4 线程，Geant4 11.3.2）全部通过，详见各包 README。这些基准验证所选物理列表在这些条件下与参考数据一致，不代表任意材料、能量或几何下的结果都已验证。
