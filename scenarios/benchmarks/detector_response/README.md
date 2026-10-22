# 探测器响应（脉冲幅度谱特征）

探测器响应场景包（`scenarios/detector_response`）的基准，参考值都是解析结果（`make_reference.py` 调用 `scenarios/detector_response/response_physics.py`）：

- **康普顿边**：1"×1" 塑料闪烁体（`G4_PLASTIC_SC_VINYLTOLUENE`）中 662 / 1332 keV 光子的沉积谱，边位置取以 2% E 为窗的最大台阶，参考为 Klein–Nishina 运动学 E_c = E·2a/(1+2a)，容差 1%。只用小的低 Z 探测器：大块高 Z 晶体中多次康普顿事件会填到边的上方。
- **逃逸峰**：HPGe（半径 30 mm、长 50 mm）中 4.44 MeV 光子的单、双逃逸峰，位置取 ±10 keV 内计数最高的 1 keV 箱，参考为 E − m_ec² 与 E − 2m_ec²，允许 1 箱。
- **最概然沉积**：300 µm 硅中的 4 GeV μ⁻、300 MeV 与 1 GeV 质子，半样本众数（20 批误差），参考为 PDG 的 Landau–Vavilov–Bichsel 公式（Review of Particle Physics，“Passage of particles through matter”，式 34.12），含 Sternheimer 密度效应（硅参数取自 Geant4 `G4DensityEffectData`），容差 3% + 3σ。

物理列表 `FTFP_BERT` + `option4`，探测器区域 cut 10 µm。

**2026-10-22 完整模式结果**（γ 每例 100000、硅每例 200000 个初级粒子）：

| 病例 | 模拟 | 参考 | 偏差 |
| --- | --- | --- | --- |
| 662 keV 康普顿边，塑料 | 0.478 MeV | 0.47765 | +0.07 % |
| 1332 keV 康普顿边，塑料 | 1.118 MeV | 1.11762 | +0.03 % |
| 4.44 MeV 单逃逸峰，HPGe | 3.9295 MeV | 3.929 | 箱内 |
| 4.44 MeV 双逃逸峰，HPGe | 3.4185 MeV | 3.418 | 箱内 |
| μ⁻ 4 GeV，300 µm Si 最概然沉积 | 84.74 ± 0.32 keV | 82.53 | +2.68 % |
| 质子 300 MeV | 155.94 ± 0.50 keV | 155.82 | +0.08 % |
| 质子 1 GeV | 90.14 ± 0.32 keV | 89.76 | +0.43 % |

全部在容差内。Geant4 `option4` 的最概然沉积系统性略高于 LVB 值，近最小电离时约 +2.7%；`scripts/test_detector_response.py` 中 100 µm 硅约 +5%，层越薄偏高越多。逃逸峰与康普顿边检验的是运动学与能量守恒，不是探测效率。

```bash
python scripts/run_benchmarks.py --only detector_response --output benchmark_report
python scenarios/benchmarks/detector_response/make_reference.py
```
