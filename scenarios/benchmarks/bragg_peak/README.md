# 布拉格峰（水）

**物理量**：150 MeV 质子笔形束（点源，沿 +z）射入 40 cm 水体，原生 Geant4 打分网格 `energyDeposit`（1 mm 深度格元、横向 10 × 10 cm 积分）给出深度剂量曲线，取峰后剂量降到峰值 80 % 处（线性插值）的深度 R80。参考值为 PSTAR CSDA 射程 × 迂回因子 0.998（R80 与平均投影射程相差约 0.1 %）。物理列表 `QGSP_BIC_EMZ`（含核反应）。

**2026-10-22 完整模式结果**：R80 = 158.7 mm，参考 157.4 mm，偏差 +0.84 %（容差 1 %），峰位 156.5 mm，峰/入射剂量比 4.9。与 `csda_range` 相同，偏长主要来自 `G4_WATER` 的 I = 78 eV（PSTAR 75 eV）。

**单独运行示例**（结果在 `output/benchmark_bragg_peak/scoring_mesh.csv`，列 `i2` 为深度格元）：

```bash
build_vs2026/Release/G4UniversalSim.exe --config scenarios/benchmarks/bragg_peak/example.ini
```
