# 光子窄束衰减

**物理量**：单能光子垂直穿过平板，平板后 50 mm 的真空薄片用相空间记录器（`[phase_space] kill = true`）统计未发生任何相互作用的初级光子（能量不变、方向不变），透射率 T 给出质量衰减系数 μ/ρ = −ln T /(ρx)，与 NIST XCOM（含相干散射）比较。物理列表 `FTFP_BERT_EMZ`。

**2026-10-22 完整模式结果**（每例 20000 个光子）：

| 材料 | 能量 | 厚度 | 模拟 μ/ρ（cm²/g） | XCOM | 偏差 |
| --- | --- | --- | --- | --- | --- |
| 水 | 0.1 MeV | 40 mm | 0.1677 ± 0.0017 | 0.1707 | −1.74 % |
| 水 | 1 MeV | 100 mm | 0.0704 ± 0.0007 | 0.07072 | −0.41 % |
| 水 | 10 MeV | 300 mm | 0.02214 ± 0.00023 | 0.02219 | −0.24 % |
| Al | 1 MeV | 40 mm | 0.0616 ± 0.0006 | 0.06146 | +0.21 % |
| Pb | 0.1 MeV | 0.1 mm | 5.51 ± 0.06 | 5.549 | −0.75 % |
| Pb | 1 MeV | 10 mm | 0.0700 ± 0.0007 | 0.07102 | −1.46 % |

全部在统计误差的 1.7σ 内。其他 EM 预设在 1 MeV 水中的比较见 `scripts/test_physics_a6.py`。

**单独运行示例**（1 MeV 光子穿过 10 cm 水；`output/benchmark_gamma_attenuation/phase_space_t*.csv` 中 `trackID = 1`、能量 1 MeV、`w = 1` 的行即未散射光子）：

```bash
build_vs2026/Release/G4UniversalSim.exe --config scenarios/benchmarks/gamma_attenuation/example.ini
```
