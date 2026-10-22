# 硅 NIEL 表（SR-NIEL）

`[scoring.displacement]` 使用的硅非电离能损表，表头 `energy_MeV,niel_MeV_cm2_g`。全部来自 SR-NIEL 网页计算器（https://www.sr-niel.org，SR-NIEL-7 ver. 11.1），2026-10-22 以计算器默认设置取得，文件头注释保留了计算器的输入参数：

| 文件 | 粒子 | 计算器与设置 | 能量范围 |
| --- | --- | --- | --- |
| `si_proton.csv` | proton | Protons & Ions NIEL Calculator：Si，位移阈能 21 eV，Hadron + Coulomb，强子部分不缩放（强子贡献取自 Jun 等 2003/2004、Jun 2017 与 Huhtinen 2002 的插值） | 0.1 keV – 10 GeV |
| `si_electron.csv` | e- | Electrons NIEL Calculator：Si，位移阈能 21 eV，指数核形状因子 | 0.1 MeV – 10 GeV |
| `si_neutron.csv` | neutron | Neutrons NIEL Calculator Using ASTM Standards：Si，ASTM E722-19 损伤函数（Table A1.1） | 1.0×10⁻¹⁰ – 19.95 MeV（分群值） |

使用时请引用 SR-NIEL（M.J. Boschini 等的相关论文，见 https://www.sr-niel.org/index.php/biblio）与 ASTM E722-19。

**改动说明**：源表在最低能量处已为 0（低于位移阈值），`convert_srniel.py` 在 1 eV 处补一行 0，使更低能量的次级粒子（例如 δ 电子）计为零损伤而不是“表外”；这只延续源表的零值，不是新的数据。中子表是 ASTM 的分群（群中点）值，共振结构按表中点间对数插值。

**1 MeV 中子等效注量**：`analyze_device.py` 用 ASTM E722 的参考值 95 MeV·mb，即 NIEL_ref = 95×10⁻²⁷ × N_A / 28.0855 = 2.037×10⁻³ MeV cm²/g（硅），Φ_eq = DDD / NIEL_ref；不从共振中子表插值 1 MeV 处的值。

**局限**：表只适用于硅；氧化层等其他材料中的 DDD 仍按硅表计算，仅供参考。NIEL 是模型量，不同文献的表（尤其是质子的强子部分）彼此存在差异，本仓库没有独立验证这些表。要换用其他表，生成器 `--niel 粒子=表.csv` 即可。

重新生成：在 SR-NIEL 计算器提交后保存结果页（`http://www.sr-niel.org/Simulation/<编号>niel_<p|e|n>.html`），然后

```bash
python scenarios/semiconductor/niel/convert_srniel.py 结果页.html scenarios/semiconductor/niel/si_proton.csv "说明"
```
