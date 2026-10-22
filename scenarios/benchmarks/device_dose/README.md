# 器件剂量与位移损伤（硅薄层）

半导体器件场景包（`scenarios/semiconductor`）的基准。每个病例：40×40 mm 硅块中埋一个 10×10 mm 的敏感硅薄层（厚度 t），前后各有厚 b 的硅，方形平面源（12×12 mm）法向入射，薄层处注量 Φ = N / 1.44 cm²。`make_reference.py` 生成 `reference.csv`：

- **TID**：D / Φ = S_el(E_mid) × 1.602176634×10⁻¹⁰ Gy g/MeV，S_el 为 PSTAR 硅电子阻止本领（`../shielding_range/nist/PSTAR_Si.txt`），E_mid 为薄层中点能量（PSTAR CSDA 射程反演）。b 大于最快 δ 电子的射程，薄层处于 δ 电子平衡，剂量等于碰撞比释动能；production cut 10 µm（δ 电子被真实产生和输运）。物理列表为仅电磁 `option4`，容差 2%。
- **DDD**：DDD / Φ = NIEL(E_mid)，NIEL 来自 `scenarios/semiconductor/niel` 的 SR-NIEL 硅表（中子为 ASTM E722-19），容差 1%。它检验径迹长度注量与折积，不检验 NIEL 数据本身。中子用 `QGSP_BIC_HP`。

**2026-10-22 完整模式结果**（每例 20000 个初级粒子，4 线程）：

| 病例 | 模拟 | 参考 | 偏差 |
| --- | --- | --- | --- |
| TID，质子 10 MeV，20 µm（前 50 µm） | 5.7375×10⁻⁹ Gy cm² | 5.7594×10⁻⁹ | −0.38 % |
| TID，质子 50 MeV，100 µm（前 300 µm） | 1.5940×10⁻⁹ | 1.5986×10⁻⁹ | −0.28 % |
| TID，质子 100 MeV，100 µm（前 600 µm） | 9.4248×10⁻¹⁰ | 9.4114×10⁻¹⁰ | +0.14 % |
| TID，质子 200 MeV，200 µm（前 1.5 mm） | 5.8270×10⁻¹⁰ | 5.8365×10⁻¹⁰ | −0.16 % |
| DDD，质子 10 MeV | 9.7307×10⁻³ MeV cm²/g | 9.6663×10⁻³ | +0.67 % |
| DDD，质子 100 MeV | 2.9864×10⁻³ | 2.9929×10⁻³ | −0.22 % |
| DDD，中子 14 MeV | 3.8075×10⁻³ | 3.8072×10⁻³ | +0.01 % |

10 MeV 质子 DDD 的 +0.67% 为 1.5σ（统计误差 0.46%）；全部在容差内。

```bash
python scripts/run_benchmarks.py --only device_dose --output benchmark_report
python scenarios/benchmarks/device_dose/make_reference.py
```
