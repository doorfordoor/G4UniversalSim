# 半导体器件剂量与位移损伤场景包（路线图 Phase B3）

硅芯片在封装盖板 / 屏蔽之后，由覆盖芯片的方形平面源以法向入射照射（单能或积分通量能谱；质子、电子、中子或质子 + 电子）。器件分层并全部为敏感体：

```
源 | 盖板（--lid，可选） | 1 mm 间隙 | BEOL 层（--beol） | GateOxide（SiO2） | Active（Si） | Substrate（Si，--slices 个 replica 深度切片）
```

每个敏感层给出：

- **TID**：该层材料的吸收剂量（GateOxide 为 Gy(SiO2)，其余为 Gy(Si)），来自敏感体 Dose 计分；
- **DDD**：位移损伤剂量（MeV/g），由径迹长度注量与 `niel/` 中 SR-NIEL 的硅 NIEL 表（质子、电子、中子）折积；
- **Φ_eq**：1 MeV 中子等效注量 = DDD / 2.037×10⁻³ MeV cm²/g（ASTM E722 的 95 MeV·mb）；
- 每单位入射注量（1 cm⁻²）的值；能谱源时再乘能谱积分通量得到每年的剂量与 Φ_eq（**法向入射**，与 `shielding_coating` 相同的前提）。

NIEL 表的出处、设置与局限见 `niel/README.md`。DDD 只对硅层有意义（表为硅表），氧化层的 DDD 只作参考。

## 使用

在仓库根目录（`example/`：默认器件、质子任务能谱、5000 个初级粒子）：

```bash
build_vs2026/Release/G4UniversalSim.exe --config scenarios/semiconductor/example/main.ini
python scenarios/semiconductor/analyze_device.py scenarios/semiconductor/example/output
```

`analyze_device.py` 打印各层的 TID、DDD、Φ_eq 及相对统计误差，写出 `device_report.json` 与 `depth_profile.csv`（深度剖面），并在某种有表粒子的径迹有 1% 以上落在 NIEL 表能量范围外时警告。

生成其他器件：

```bash
python scenarios/semiconductor/make_device.py --out work/dev --particle neutron --energy 1 --lid none --events 100000
```

| 参数 | 含义（默认） |
| --- | --- |
| `--lid` | 盖板 `材料:厚度` 或 `none`（`G4_Al:1mm`），横向 `--lid-size`（20 mm）。材料与 `shielding_coating` 相同（NIST 材料及 `B4C`、`HEB` 等）。 |
| `--beol` | 栅氧上方的后道层，面向源的在前，或 `none`（`G4_SILICON_DIOXIDE:3um,G4_Al:1um,G4_SILICON_DIOXIDE:2um`）。 |
| `--oxide`、`--active`、`--substrate`、`--slices` | 栅氧（100 nm）、有源硅（10 µm）、衬底（300 µm）厚度与衬底切片数（10）。 |
| `--die` | 芯片横向尺寸（5 mm）；源与芯片同尺寸，注量 = N / A。 |
| `--particle`、`--energy` | `proton`、`e-`、`neutron`、`mixed`；`--energy` 为单能 MeV，省略时用能谱（中子必须给能量）。 |
| `--proton-spectrum`、`--electron-spectrum` | 积分通量表，默认 `shielding_coating/environment` 中的任务平均谱。 |
| `--niel 粒子=表.csv` | 替换或增加 NIEL 表。 |
| `--physics`、`--em`、`--device-cut` | `QGSP_BIC_HP`、`option4`、器件区域 cut 10 µm。 |

2026-10-22 默认器件示例（各 50000 个初级粒子，8 线程）：质子任务能谱在 1 mm Al 后有源层 TID 4.5×10⁻¹¹ Gy·cm²/注量（±6%），法向入射约 41 Gy(Si)/年，DDD 1.1×10⁻⁴ MeV g⁻¹ cm²，Φ_eq 0.053 / 注量；电子任务能谱 2.6×10⁻¹² Gy·cm²（±13%），约 157 Gy/年。这些数值只说明场景可运行，误差较大时增加事件数。

## 验证

- 参考数据基准 `scenarios/benchmarks/device_dose`（`python scripts/run_benchmarks.py --only device_dose`）：δ 电子平衡的硅薄层中质子剂量/注量与 PSTAR 硅电子阻止本领一致（10–200 MeV，−0.38…+0.14%），DDD/注量与 SR-NIEL 表一致（质子 10/100 MeV +0.67%/−0.22%，14 MeV 中子 +0.01%）。DDD 比较检验的是注量与折积，不是 NIEL 数据本身。
- `scripts/test_semiconductor_device.py`（真实 Geant4）：1 mm Al 后 50 MeV 质子在每一层的 DDD/注量与按 PSTAR 射程反演能量查 SR-NIEL 表一致（2%）并有 Φ_eq = DDD / 2.037×10⁻³；2 mm 衬底中部 100 MeV 质子剂量与 production cut 无关（1 µm 与 1 mm 相差 0.2%，±0.8%）；14 MeV 中子衬底 DDD 与 ASTM 表一致；混合能谱、表转换器与非法参数。

未验证：SiO2 中剂量与参考数据的比较（没有 SiO2 的 PSTAR 表）、栅氧这类远薄于 δ 电子射程的薄层中剂量的界面效应、全向辐射环境、NIEL 表本身、电子 DDD 与位移损伤效应（退化、漏电流等器件响应）。GUI 尚不能生成本包配置。
