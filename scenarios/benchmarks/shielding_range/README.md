# 屏蔽材料中的射程与剩余能量（Al、Si）

屏蔽 / 涂层场景包（`scenarios/shielding_coating`）的参考数据基准。`nist/` 中是 NIST PSTAR / ESTAR 程序为铝和硅输出的默认文本表（https://physics.nist.gov/PhysRefData/Star/Text/），原样保存；`make_reference.py` 由它们生成 `reference.csv`。

- **CSDA 射程**：质子 10/100 MeV、电子 1/5 MeV 在 `G4_Al`、`G4_Si` 大块中，逐事件累加 track 1 的步长（乘 Geant4 密度 2.699 / 2.33 g/cm³ 得 g/cm²），容差同 B1：质子 1.5%，电子 3%。
- **剩余能量**：质子穿过平板后在其后方真空薄片（相空间记录）处的平均动能，参考值为 PSTAR CSDA 射程反演 E_out = R⁻¹(R(E_in) − ρt)（对数插值，路径长度取板厚），容差 1%。`reference.csv` 的 `projected_range_energy_MeV` 列给出用投影射程反演的值，仅供参考：它包含整条剩余径迹的迂回因子，对远薄于射程的平板偏低。

物理列表为仅电磁 `G4EmStandardPhysics_option4`（射程表不含核反应）。Geant4 的 `G4_Al`（I = 166 eV）与 `G4_Si`（173 eV）与 PSTAR 使用相同的平均激发能，因此这里不出现 B1 水中约 +0.6% 的偏差。

**2026-10-22 完整模式结果**（4 线程，Geant4 11.3.2）：

| 病例 | 模拟 | NIST | 偏差 |
| --- | --- | --- | --- |
| 质子 10 MeV，Al | 0.17069 g/cm² | 0.1705 | +0.11 % |
| 质子 100 MeV，Al | 10.021 g/cm² | 10.01 | +0.11 % |
| 质子 10 MeV，Si | 0.16649 g/cm² | 0.1665 | −0.01 % |
| 质子 100 MeV，Si | 9.757 g/cm² | 9.737 | +0.20 % |
| 电子 1 MeV，Al | 0.5568 g/cm² | 0.5546 | +0.40 % |
| 电子 5 MeV，Al | 3.087 g/cm² | 3.092 | −0.18 % |
| 电子 1 MeV，Si | 0.5441 g/cm² | 0.5386 | +1.02 % |
| 质子 20 MeV 穿过 1 mm Al | 14.031 MeV | 13.951 | +0.57 % |
| 质子 50 MeV 穿过 5 mm Al | 35.361 MeV | 35.335 | +0.07 % |
| 质子 100 MeV 穿过 20 mm Al | 64.456 MeV | 64.552 | −0.15 % |
| 质子 30 MeV 穿过 2 mm Si | 22.429 MeV | 22.376 | +0.24 % |

全部在容差内。20 MeV / 1 mm Al 的 +0.57%（能损少 1.3%）是最大偏差，说明 Geant4 在约 14–20 MeV 的 Al 中阻止本领略低于 ICRU 49；射程积分到 0 时相互抵消（10 MeV 射程 +0.11%）。

只覆盖所列粒子、能量和两种材料；涂层材料（B4C、W、HEB）没有 NIST 表，未作比较。

```bash
python scripts/run_benchmarks.py --only shielding_range --output benchmark_report
python scenarios/benchmarks/shielding_range/make_reference.py   # 由 nist/ 重新生成 reference.csv
```
