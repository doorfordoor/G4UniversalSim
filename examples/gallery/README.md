# 开始页示例库

GUI 开始页的五个示例，每个目录包含 Geant4 已算好的小规模结果，打开示例即可在“结果 / 图表”或“参数扫描”中直接查看：

| 目录 | 示例 | 场景（向导） | 事件数 | 首先显示 |
| --- | --- | --- | --- | --- |
| `bragg_peak/` | 质子布拉格峰：150 MeV 质子，200 mm 水体模分 40 片，QGSP_BIC | `depth_dose` | 2000 | `scorer/dose/raw_dose/r0`（各片剂量） |
| `shielding_slab/` | 屏蔽板：70 MeV 质子穿过 10 mm 铝，后方 300 um 硅探测器 | `shielding` | 5000 | `event_edep/r0`（逐事件沉积） |
| `silicon_landau/` | 硅中朗道分布：100 MeV 质子穿过 300 um 硅片 | `silicon_detector` | 20000 | `event_edep/r0` |
| `nai_gamma/` | NaI γ 能谱：662 keV 各向同性点源，3 in x 3 in NaI 晶体 | `gamma_spectrometer` | 20000 | `event_edep/r0` |
| `energy_scan/` | 质子能量扫描：20/35/50/100/200 MeV，300 um 硅片 | `silicon_detector` + 扫描 `source.energy` | 每点 2000 | `edep / raw_edep` |

内容与约定：

- `output/`：该次运行的输出目录，省略 hits 与 ROOT 文件以控制体积；`run_summary.txt` 中列出的生成文件和路径是生成时的实际记录。
- `scan/scan.json`：扫描清单，点的路径相对 `scan/` 书写，各点只保留 `run_summary.txt`、`run_metadata.json`、`scorer_statistics.csv`。运行包不随附，因此 GUI 以只读方式打开（不能“运行”，需新建扫描重算）。
- `thumbnail.png`：用与“结果 / 图表”相同的读取函数绘制的缩略图。
- 打开示例时，示例的向导设置写入当前项目（与新建仿真向导相同），附带结果只读显示；按“生成并运行”会在运行目录中重新计算，从不写入本目录。
- 结果为单一种子、有限事件数的统计样本，不是物理基准；γ 能谱不含探测器分辨率。示例与卡片描述的一致性由 `gui/smoke_tests/smoke_start_page.py` 核对（布拉格峰位置、光电峰与康普顿边、朗道长尾、沉积随能量下降）。

重新生成（需要已构建的 Release 后端，约数分钟）：

```bash
gui/.venv/Scripts/python.exe examples/gallery/build_gallery.py
```

可在命令后加示例 id 只重算其中几个；运行目录位于 `out/gallery_build/`（不提交）。
