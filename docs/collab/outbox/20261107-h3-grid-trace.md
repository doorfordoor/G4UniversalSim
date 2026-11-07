# H3-4 网格计分差异最小前置诊断回执（round125）

- 日期：2026-11-07
- 授权：`docs/collab/decisions/20261107-h3-grid-scoring-prerequisite.md`
- 证据：`out/collab/20261107-h3-grid-trace/`（README、trace.csv、analysis.json、production-run/、trace-run/、logs/、original/、input-sha256-verified.txt）
- 性质：诊断，不是产品修复，不是正式基准；H3-4 运行门禁继续关闭。

## 做了什么

在允许的两个生产文件内加入临时 trace（仅 `G4USIM_H3_GRID_TRACE` 设置时生效）：生产 cell SD 写 `C` 行；ghost 世界根加一个只写证据、不计分的 trace SD 写 `W` 行。用冻结的 A2 输入（4×4×1、10 MeV 质子、seed 20261465、threads 1）各跑一次 20 事件：trace 构建一次，恢复源码后的生产构建对照一次。未改 ScoringManager/Dose/Fluence、未改冻结输入、未改其它生产文件。

## 结果

- 生产对照与冻结论证逐位一致：质量 200 MeV 对 4 个命中单元 143.08371916006 MeV；长度 24.7737095206 对 14.60995595524 mm。
- trace 一次运行：`C` 250 步（114 步有沉积）143.083725 MeV；`W` 79 步（33 步有沉积）56.916280 MeV；**`C + W` = 200.000005 MeV**（差值为 6 位小数打印舍入）。逐事件 `cell + world` 均为 10.000000 ± 2e-6 MeV；事件 8 的 cell 为 0、world 为 9.999999 MeV。
- slab 内 world 步长度 10.163753 mm；`C` 的 14.609955 + 10.163753 = 24.773708 mm，与质量世界 24.7737095206 mm 一致（打印舍入）。
- 33 个有沉积的 world 步：20 步 pre z 恰为 -1.000000 mm（slab 入射面），其余位于内部界面；所有 `W` 步的 ghost pre 体积都是 `/ScoringWorld#0`（无生产 SD 的世界根），因此被 Geant4 静默不向任何生产 SD 分发。
- 结论边界：证据只证明“能量/径迹没有丢失，缺失部分是 pre 点落在 ghost 世界根的步未被分发”，用于证实假设链；不证明修复方案，也不给 world 全量计分或复制质量结果。

## 保留与偏差

- 两个源文件的原字节与 SHA 保留在 `original/`，运行后已逐字节恢复。
- 候选 exe 原 SHA（`9daf3d22…`）已记录；临时 trace 构建覆盖了 `build_vs2026/Release/G4UniversalSim.exe`，候选二进制字节未保留副本。恢复源码后的重建 exe 为 `06626dfa…`，`source_fingerprint = 9523b987…`（与候选一致）。候选二进制需主审重新冻结，这一点如实报告。
- 冻结 inputs 中诊断期间产生的 36 个变体文件已移到证据目录 `diagnostic-inputs/`；18 个冻结输入经 SHA 复核无差异。

## 请求

请主审基于本步级证据给出最小产品修复范围（例如对 world 根 pre 步的归属规则）并重新冻结候选二进制；在此之前不恢复 H3-4 正式批次，不自行改产品。完成后停写等待评审。

## 复核与现状（2026-11-07 05:05，不重跑）

- 本节记录对 round125 授权的重复派工（2026-11-07 05:03 消息）的核对结果。该诊断已按
  `docs/collab/decisions/20261107-h3-grid-prerequisite.md` 执行一次，并于同日晚些时候经
  主审独立复算与复核（`out/collab/h3-4-grid-diagnosis-r1/independent-trace-check.json`、
  `docs/collab/reviews/20261107-h3-grid-trace-review.md`）。按“最多一次、不重复诊断”
  的停止条件，本次未再临时修改源码、未重复 trace、未新增变种。
- 派工消息中引用的失败数字是**修复前 f656 候选**的结果：mass 200 MeV 对 ghost
  143.08371916006 MeV，长度 24.7737095206 对 14.60995595524 mm；这些原始输入/输出
  仍保留在 `out/collab/h3-4-grid-diagnosis-r1`，本回执与证据原样保留。
- 当前工作区候选（r3 导航包络）已不再复现该差异。用同一 A2/A2f 冻结输入（20 事件、
  seed 20261465、threads 1）自测：
  - A2：质量 raw/weighted edep 200 / 200 MeV，4 个命中网格单元合计
    **200.0000000000 / 200.0000000000 MeV**；质量径迹长度 24.7737095206 mm，
    网格合计 **24.77370952061 mm**；
  - A2f：同上网格合计 200.0000000000 MeV；质量 proton hits 的 Σ(edep·weight)
    独立复算 **199.999999999993161764 MeV**（与主审先前给出的数值一致）。
  证据：`out/collab/20261107-h3-grid-fix-r3/{analysis.json,runs/}`，复现命令见其
  README §7。
- 若主审确认仍需要“当前 r3 候选”的步级 trace（而不是修复前 f656 的 trace），请明确
  授权；届时按同一 decision 的最小范围、同样“一次、独立输出、debug 身份”执行，
  不与本次证据混用。
