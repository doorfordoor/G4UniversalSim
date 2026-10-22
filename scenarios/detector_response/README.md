# 探测器响应场景包（路线图 Phase B4）

两类探测器，脉冲幅度都取自每个事件在敏感体中的沉积能量（`[scoring] event_edep = true` 写出的 `event_edep_tN.csv`，探测器是唯一的敏感体），能量分辨率在分析阶段施加：

- **γ 谱仪**（`--kind gamma`）：圆柱晶体（`NaI`、`CsI`、`BGO`、`LaBr3`、`HPGe`、`plastic`、`CZT`），可选 Al 外壳，轴线上距外壳前表面 `--distance` 处的各向同性点源。源只在包住外壳的圆锥内抽样（`angular = isotropic` + `max_theta`），绝对效率乘圆锥占 4π 的份额 (1 − cos α)/2。
- **硅探测器**（`--kind silicon`）：厚 `--thickness`、边长 `--size` 的硅片，带电粒子平行束法向入射，得到沉积能谱与最概然沉积。

## 使用

在仓库根目录（`example/`：3"×3" NaI、0.5 mm Al 外壳、10 cm 处 662 keV 点源、100000 个光子）：

```bash
build_vs2026/Release/G4UniversalSim.exe --config scenarios/detector_response/example/main.ini
python scenarios/detector_response/analyze_detector.py scenarios/detector_response/example/output --fwhm 0,0.04,0
```

生成其他探测器：

```bash
python scenarios/detector_response/make_detector.py --out work/ge --crystal HPGe --radius 30mm --length 50mm --energy 1.332 --events 100000
python scenarios/detector_response/make_detector.py --out work/si --kind silicon --thickness 300um --particle mu- --energy 4000
```

`analyze_detector.py <输出目录> [--fwhm a,b,c] [--bin keV]`：

- `--fwhm`：高斯分辨率，采用 MCNP GEB 形式 FWHM(E) = a + b√(E + cE²)（E、a 单位 MeV，b 为 MeV^½，c 为 MeV⁻¹），参数须来自实际探测器的刻度；默认不展宽。示例 `0,0.04,0` 在 662 keV 处 FWHM ≈ 32.5 keV（4.9%），只是演示值。
- 输出 `pulse_height.csv`（每个初级粒子的沉积谱与展宽谱）和 `detector_report.json`。γ 谱仪：探测效率（沉积 > 1 keV）、全能峰效率（沉积与 E 相差 ≤ 1 keV）及峰总比，均给出本征（每个射入圆锥的光子）与绝对（每个 4π 发射的光子）值；康普顿边（谱在光峰下方、以 2% E 为窗的最大台阶）与 Klein–Nishina 值；1.022 MeV 以上的单/双逃逸峰强度；展宽后全能峰事件的位置与 FWHM。硅：最概然沉积（半样本众数，20 批估计误差）、平均值、FWHM，以及 PDG 的 Landau–Vavilov–Bichsel 值。

2026-10-22 示例（3"×3" NaI，662 keV，`FTFP_BERT` + `option4`）：本征全能峰效率 0.306，绝对全能峰效率 1.12×10⁻²，峰总比 0.56，康普顿边 0.478 MeV（Klein–Nishina 0.4777 MeV）。这些是模拟值，没有与 NaI 实测效率比较。

## 验证

- 基准 `scenarios/benchmarks/detector_response`（`python scripts/run_benchmarks.py --only detector_response`）：小塑料闪烁体中 662/1332 keV 的康普顿边与 Klein–Nishina 运动学相差 +0.07%/+0.03%；HPGe 中 4.44 MeV 的单、双逃逸峰位于 E − m_ec²、E − 2m_ec²（1 keV 分箱内）；300 µm 硅中 4 GeV μ⁻、300 MeV 和 1 GeV 质子的最概然沉积比 PDG Landau–Vavilov–Bichsel 公式（含 Sternheimer 密度效应，参数取自 Geant4 的 `G4DensityEffectData`）高 +2.7%、+0.1%、+0.4%（容差 3% + 3σ）。
- `scripts/test_detector_response.py`（真实 Geant4）：100 keV 光子照射裸 BGO（平均自由程约 0.3 mm，近似全吸收）的绝对探测效率与前表面立体角份额相差 −1.4%（检验圆锥抽样与归一化）；NaI 中沉积不超过光子能量，展宽后光峰位置与 FWHM 符合模型；100 µm 硅中 μ⁻ 的最概然沉积比 PDG 值高约 5%（Geant4 `option4` 的涨落模型在更薄的层中偏高更多）。

**局限**：脉冲幅度就是沉积能量，没有闪烁光产额、Birks 猝灭、光收集、电荷收集或电子学；分辨率模型由用户给出。大块高 Z 晶体中多次康普顿使康普顿边不再锐利，报告的边位置只在小的低 Z 探测器中有意义。没有与实测效率或能谱比较；GUI 尚不能生成本包配置。
