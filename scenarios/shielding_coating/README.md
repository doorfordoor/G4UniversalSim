# 屏蔽 / 复合涂层场景包（路线图 Phase B2）

由 `D:\Geant4\CoatingSimulation` 移植：多层涂层（面向辐射的一层在前）后放置硅器件，用方形平面源以法向入射照射，可用单能或任务平均能谱。原工程的 `/cfg/` 宏命令（层数/材料/厚度、粒子类型、界面薄层、气泡孔隙、步长限制、源尺寸）改为生成器 `make_scenario.py` 的参数，输出全部来自 G4UniversalSim 已有功能：敏感体 Dose（TID）、Track-Length Fluence、相空间记录（透射/反照能谱）、A3 统计误差，以及本阶段新增的实验性位移损伤剂量计分（DDD，见下文）。

## 快速使用

在仓库根目录执行（`example/` 为默认参数生成、2000 个质子的现成配置）：

```bash
build_vs2026/Release/G4UniversalSim.exe --config scenarios/shielding_coating/example/main.ini
python scenarios/shielding_coating/analyze.py scenarios/shielding_coating/example/output
```

生成其他场景：

```bash
python scenarios/shielding_coating/make_scenario.py --out work/shield --layers B4C:300um,G4_W:100um,G4_Al:300um --particle e- --events 20000
```

`--out` 目录中会写入 `main.ini`、`geometry.ini`、`materials.ini`、`run.mac`、能谱 CSV、`scenario.json`（以及孔隙时的 `pores.csv`）；默认从该目录启动后端，`--run-from <目录>` 可改为从其他目录启动（路径相应改写）。

| 参数 | 含义（默认） |
| --- | --- |
| `--layers` | `材料:厚度` 列表，面向源的一层在前（`B4C:300um,G4_W:100um,G4_Al:300um`，即原工程默认的 Al 基底 + W + B4C）。材料可用 `G4_Al`、`G4_W`、`G4_Ti`、`G4_Ta`、`G4_Cu`、`G4_Pb`、`G4_Fe`、`G4_Si`、`G4_KAPTON`、`G4_POLYETHYLENE`、`G4_ALUMINUM_OXIDE`、`G4_SILICON_DIOXIDE`、`G4_Galactic`，或原工程 `materials.ini` 中的 `B4C`、`HEB`（ZrTaTiHfWB10）、`ZnO`、`Si3N4`。 |
| `--particle` | `proton`、`e-` 或 `mixed`（质子与电子两个 `[source.<名称>]` 源，强度等于两份能谱的积分通量，对应原 `/cfg/ptype 2`）。 |
| `--energy` | 单能（MeV）；省略时使用能谱（对应原 `/cfg/ForceMonoEnergetic`）。 |
| `--proton-spectrum`、`--electron-spectrum` | 积分通量表（首行表头，之后每行 `能量MeV 积分通量`），默认 `environment/` 中原工程的 `proton.txt`、`electron.txt`。 |
| `--mode` | `transmission`：记录进入 BackPlane（叠层与器件之间）的全部粒子，不终止；`albedo`：源位于 FrontPlane 与第一层之间，记录向后离开叠层进入 FrontPlane 的粒子并终止。 |
| `--junction-density` | 界面薄层密度比（0 = 关闭）：每个后续层在与上一层相接的一侧切出 W 10 µm、其他 30 µm 的薄层，材料为该层材料的降密度副本 `<材料>_J`（原 `/cfg/openJunction`、`densityCent`、`thinZ1/2`）。 |
| `--pores-layer`、`--pore-radius`、`--pore-fraction` | 在第 i 层放置真空球形孔隙（`placement = parameterised`，`copies_file`）：按 2.2 r 的网格随机选格放置，互不重叠且都在层内，个数 = 体积分数 × 层体积 / 球体积（原 `/cfg/openBubble`、`poreRadius`、`bubbleFrac`；孔隙同样不在界面薄层内）。默认 r = 20 µm，因为 1 cm² × 300 µm 中 5 µm 孔隙需约 57 万个副本。有孔隙时生成的配置关闭 overlap 检查（数千个副本的检查耗时为平方量级，网格构造本身保证不重叠）。 |
| `--niel 粒子=表.csv` | 开启位移损伤剂量，可重复（见下文）。 |
| `--physics`、`--em` | 参考物理列表与 EM 预设（`QGSP_BERT_HP`、`option4`；原工程报告用 `QGSP_BERT_HP` + Penelope，可用 `--em penelope`）。 |
| `--coating-cut`、`--coating-max-step`、`--device-cut` | 涂层区域 production cut（2 µm，与原工程相同）与最大步长（10 µm），器件区域 cut（10 µm），经 `[physics.region.Coating/Device]` 施加。 |
| `--size`、`--device-thickness`、`--source-half` | 层与器件的横向边长（10 mm，同原工程）、硅器件厚度（300 µm）、方形源半边长（4 mm，即原 0.8 cm 源）。 |

## 输出与分析

`analyze.py <输出目录>` 读取 `scenario.json`、`run_summary.txt`（实际完成的事件数）、合并的 `scorer_statistics.csv` 与相空间文件，写出 `shielding_report.json` 和 `spectra.csv`：

- **TID**：器件剂量（Gy）每个初级粒子、每单位入射注量（Gy·cm²，乘源面积），以及能谱源时乘能谱积分通量得到的剂量率和年剂量；附 A3 相对统计误差。
- **DDD**：开启 `--niel` 时同样给出（MeV/g）。

**证据规则（2026-10-28）**：缺失的文件不等于零结果。`analyze.py` 先核对运行本身——`run_summary.txt` 的 `status` 必须是 `completed`、`summary_write_status` 必须是 `completed`、`output_failure_status` 必须是 `none`/`not_applicable`、`run_count` 必须为 1，`run_metadata.json`（`schema = run_metadata_json_v1`）里必须正好一轮且 `completed_events == planned_events > 0`，否则以退出码 3 拒绝分析且不写报告。统计文件缺失时用 `run_metadata.json` 的 `generated_files` 判定：**列出但磁盘上没有 → 证据被删/移位，退出码 3**；**根本没列出 → 这一轮确实没有统计（零沉积），按零报告但每个量都带 `evidence = no_statistics_file_zero_deposition` 标签**。相空间文件缺失、为空、出现非 0 轮次或事件号超出完成事件数（陈旧文件）同样是证据错误。报告新增 `evidence` 段（运行事实、统计证据、相空间文件、警告）。`scripts/test_shielding_coating.py` 的真实反例覆盖这五种情形（删统计文件、失败摘要、零事件、陈旧相空间、真零沉积）。
- **能谱**：进入记录平面的各类粒子每个初级粒子的个数、平均能量和对数分箱能谱（每十倍 5 箱，1 keV–10 GeV）；透射模式另给出穿过叠层的初级粒子比例。

分析逻辑同时作为库提供（GUI 阶段 2B 的导入入口）：`from analyze import EvidenceError, analyze` 后调用 `analyze(output_dir)`，返回的 dict 与 `shielding_report.json` 完全相同，证据不足时抛 `EvidenceError` 而不会打印或退出，函数本身不写任何文件；`main(argv=None)` 接收不含程序名的参数列表，返回进程退出码（0 成功、2 用法错误、3 证据错误），命令行入口只是它的包装。上面的 CLI 输出文件、消息文本和退出码保持不变。

**归一化前提**：剂量率假设环境通量以**法向**入射到叠层，与原工程相同；这不是全向（各向同性）辐射下的屏蔽结果。能谱只在表中第一个与最后一个能量之间抽样（箱内均匀抽样，等价于原工程对积分通量的线性插值），最后一个能量以上的通量不抽样，`scenario.json` 记录了被略去的部分。原工程的厚硅灵敏体（1×1×50 cm）改为 300 µm 硅器件，更接近器件级 TID/DDD。

2026-10-22 默认叠层（B4C 300 µm + W 100 µm + Al 300 µm，`QGSP_BERT_HP` + `option4`，各 20000 个初级粒子）示例结果：质子能谱 TID 2.9×10⁻¹¹ Gy·cm²/注量、26 Gy/年（法向，±7%），1.9% 的初级质子穿过叠层，平均 90 MeV；电子能谱 7.0×10⁻¹³ Gy·cm²、43 Gy/年（±19%），0.2% 的初级电子穿过。统计误差较大时请增加事件数；这些数值只说明场景可运行，不是验证结论。

## 位移损伤剂量（实验性）

原工程按每步动能做粗略 Kinchin–Pease 估计，Geant4 自身的非电离沉积（`GetNonIonizingEnergyDeposit`）只是局部反冲能，不含 Lindhard 分配且依赖 cut，二者都不适合作为位移损伤量。本包使用工程上通用的方法：器件内每种粒子的径迹长度注量与其 NIEL(E) 表折积，DDD = Σ w·l·NIEL(E_平均)/V（MeV/g），由主 INI 的 `[scoring] displacement = true` 和 `[scoring.displacement] <粒子> = <表.csv>` 开启（见《中文使用手册》9 节）。

结果的物理正确性完全取决于所用的表。`scenarios/semiconductor/niel` 附带 SR-NIEL 的硅表（质子、电子、ASTM E722-19 中子），例如 `--niel proton=scenarios/semiconductor/niel/si_proton.csv`；其他表请转换为表头 `energy_MeV,niel_MeV_cm2_g` 的 CSV；以 MeV·mb 给出的位移损伤函数 D(E) 可按 NIEL = D × N_A / A × 10⁻²⁷ 换算（硅 A = 28.0855 g/mol）。表外能量的径迹计入 `out_of_range_track_length_mm` 而不计 DDD，请检查该列以确认表覆盖了器件内的能谱。

## 验证

- `scripts/test_shielding_coating.py`（真实 Geant4）：混合源中电子份额等于 F_e/(F_e+F_p)；质子能谱 >10 MeV 的份额等于积分通量表给出的比例；1 MeV 电子厚 W 的反照率（0.36）远大于厚 B4C（0.01）；Geant4 世界中的孔隙副本数与生成数一致且都在层内、材料为真空，20 MeV 质子在 20% 孔隙率 B4C 层中的平均能损为致密层的 0.793 倍（材料份额 0.800 ± 0.03）；界面薄层的厚度、材料和密度正确；`analyze.py` 的各种归一化相互一致。
- `scripts/test_shielding_analysis.py`（static，不需要后端或 Qt）：在临时目录里用合成输出覆盖 `analyze()` 的数值（TID/DDD 每初级粒子、每单位注量、剂量率与年剂量、透射率、逐粒子能谱）和 `evidence` 段，并检查五种证据错误（统计文件被删、`status = failed`、零事件、陈旧相空间、混入其他轮次统计）抛 `EvidenceError` 且不写报告，同时验证 `main()` 的退出码与成功/失败两条命令行路径。
- `scripts/test_displacement_damage.py`：DDD 计分器与由 hits 独立重算的结果一致（相对差 2×10⁻⁴，来自步内能量变化），中子零沉积步按 NIEL·N/A 计入，表外能量与非法表在事件前拒绝。
- 屏蔽输运的参考数据基准见 `scenarios/benchmarks/shielding_range`：质子/电子在 Al、Si 中的 CSDA 射程与 NIST PSTAR/ESTAR，质子穿过 Al/Si 平板后的平均能量与 PSTAR 射程反演（`python scripts/run_benchmarks.py --only shielding_range`）。

未验证：涂层材料（B4C、W、HEB）中的阻止本领与参考数据的比较（没有对应的 NIST 表）、全向辐射环境、任何 NIEL 表本身、Penelope 与 option4 的差别、以及原工程的其他涂层组合。GUI 尚不能生成本包的配置。
