2026-11-08最新授权：AR0–AR6由新主审及本地非web子代理全权接续，先重审优化AR0，AR2不再暂停；整体架构完成后恢复DS/web协作，F3不追加测量。决定：docs/collab/decisions/20261108-ar0-ar6-primary-ownership.md（路径相对仓库根）。

## 2026-11-08 当前进度与架构后接续排期（当前入口）

K2固定快照25487eb1保持。AR0 r3、AR-V、AR1–AR3及当前主审MR1已按各自合同签收；现进入AR4模型所有权与关联GUI修复，之后连续AR5→MR2→AR6/MR3。AR3 r4原生/兼容/独审及B4 run后命令失败风险补证已完成，原失败和有限证据边界保留。监督30分钟ACTIVE；DeepSeek/web暂停至完整架构验收，F3不追加测量。详见[AR3签收](collab/reviews/20261109-ar3-acceptance.md)、[MR1主审复查](collab/reviews/20261109-mr1-primary-review.md)及[后续总规划](后续开发总规划.md)。

本节是当前阶段快照；下方带旧日期的“当前”“下一项”及旧波次按历史读取。阶段结果保留原验收证据；J4是本次新增的后续交互阶段，不重开J1/J2/J3/F8或K2。W编号仅为排期段，不重复作为开发阶段计数。

本次新增[泛用性与易用性评审](collab/reviews/20261108-generality-usability-gap-review.md)：四维长期目标、七类任务/14张卡、任务级L0–L4和初始15/5分钟、80%门限已纳入；GU0–GU4分阶段完成。当前交付差距评审与达到目标的方法，实际用户耗时/完成率、真实SiP和完整SEU能力均未验证，不提高支持等级。

两轮联合审计27项正式问题中12项已关闭，余15项按AR4/5继续；三项风险中R1-R-02-B4已完成有界防御验证，另两项保持待处置。原ID/原判据见[修复映射](后续开发总规划.md#joint-audit-plan)。MR1已由当前对话完成，MR2在AR4/5独验后、MR3在AR6签收时执行。

| 阶段/范围 | 状态 | 生命周期与范围 | 新规划位置/下一动作 |
| --- | --- | --- | --- |
| A1–A7、B/C/D、G1–G6 | 通过 | 既有声明范围已交付；不扩大实验性/物理支持等级 | W1保护迁移，W6汇总当前最终版证据 |
| E1–E7、Q1、2C | 通过 | 原范围已关闭；E7为既有15/7能力注册范围 | AR0–AR6复用，不重新建设schema/事务/注册表 |
| F1/F2/F4/F5/F6/F8 | 通过 | 原范围已完成，限制按原报告 | W1保持；F2文案等普通反馈归J4 |
| I1/I2、J1/J2、K1、L1 | 通过 | 原限定范围已关闭，非任意环境或模型质量保证 | W1回归与W3 L2基础 |
| J3 | 限制 | 原约定范围已关闭，原生/主题观察边界保留 | 新体验需求归W2 J4，不重开旧视觉阶段 |
| Q2 | 限制 | 本轮限定范围已关闭，LET/DDD/NIEL/XS限制保留 | W4按量/适用域专项补证，W6公开边界 |
| H1/H2/H3 | 通过 | 原固定范围已交付；H3有限病例和GUI范围不外推 | W1迁移对照；更广科学能力按新任务 |
| K2 | 限制 | 固定范围已关闭；K2-3为限制、K2-4通过 | AR5/AR6保证导出并补新验收所需实装观察；L2复用 |
| AR0–AR6 | 进行中 | AR0 r3、AR1、AR2、AR3已签收；AR3 r4 D四项1773断言、22兼容55954、C独立三项487及风险补证通过；原科学与临时产物边界保持。当前AR4，AR5/6待 | [AR1](collab/reviews/20261108-ar1-acceptance.md)；[AR2](collab/reviews/20261108-ar2-acceptance.md)；[AR3](collab/reviews/20261109-ar3-acceptance.md) |
| AR-V审计验收工具工作包 | 已完成（本轮约定范围） | R2-05/06/07关闭；身份门禁/CI接线、6专项1623断言、独立390次CLI均通过 | [主审签收](collab/reviews/20261108-ar-v-acceptance.md)；后续新候选必须使用严格身份门禁，旧报告原身份保留 |
| 两轮审计关联修复 | 部分关闭 | 12/27正式问题关闭，余15项；R1-R-02-B4有限防御验证完成，其余两项风险待 | [唯一映射](后续开发总规划.md#joint-audit-plan)；AR6前逐项闭环 |
| MR1–MR3主审累计复查 | MR1通过，MR2/3待 | 当前对话已核累计源码/所有权/AR-V/原始正反例，允许进入AR4；科学证据按原身份复用，不声称r4新科学执行 | [MR1](collab/reviews/20261109-mr1-primary-review.md)；MR2在AR4/5后，MR3在AR6 |
| J4 | 未开始 | 工程化模拟流程与可用性；新增J4-5任务模板/结果解释/现有扫描走查 | W2：J4-0～5，承接GU2产品改进 |
| GU0 | 设计评审通过 | 七类有限源码核查、差距/采纳矩阵、14卡候选与测量方法；独审0阻断，3条澄清已纳入；无真实用户成绩 | 只签方法设计；详细输入/参与者仍须执行前冻结 |
| GU1 | 未开始 | 14卡基线登记与8/10常见卡达标分两出口；失败/缺输入不得删卡 | AR6候选后基线即可启动J4修复，之后复验达标 |
| GU2 | 未开始 | 常见任务创建/解释/扫描/错误恢复与主结果可用性 | W2 J4-0～5实施，不重复计同一交付 |
| GU3 | 设计完成、能力待验证 | A真实SiP输入；B剂量/SEE响应；C扩展成本；有限方法已定，数据/模型/组件证据待补 | W4科学/适配与W5 M5分别拥有实现 |
| GU4 | 未开始 | 非开发者独立任务测试与原生流程对照；15/5分钟、80%为初始项目门限 | W6前按预注册方案实测，不能由AR6或自动测试替代 |
| F3 | 限制 | 未关闭；F3-1通过、F3-2限制、F3-3/4未开始 | W3条件接续；新方案/有限批次须明确批准，不混算旧三批 |
| F7 | 未开始 | 依赖K1/F3，原单参数串行能力保留 | W3，F3正式关闭后二维/并发扫描 |
| L2 | 未开始 | 依赖L1/K2及架构迁移后的接口复验 | W3默认主目标；不依赖F3 |
| H4 | 未开始 | importance/weight windows与独立加权/FOM验收 | W4默认首项；旧XS失败域单独核对 |
| H5 | 未开始 | 光学材料/过程/表面/光子计数 | W4，H4后默认排期，非代码硬依赖 |
| H6 | 未开始 | 活化/热中子与数据/时间窗验证 | W4，H5后默认排期 |
| H8 | 未开始 | 规则体素与限定混合建模；原用户参考规划保留 | W4，H6后默认排期；H8-R自适应/DICOM为可选后续 |
| H7 | 未开始 | 局域DNA/径迹结构 | W4，H8后默认排期 |
| H9 | 未开始 | INI直方图/ntuple与输出兼容 | W4，保留H序列最后 |
| M5 | 未开始 | 完整扩展生态阶段；现有后处理原型不等于完成 | W5：API兼容、扩展生命周期与管理 |
| M0–M4与整体发布 | 未开始 | 指未来最终版本的汇总/发布验收，不否定旧基础工作 | W6：源码/真实分平台包/主流程/文档/限制与用户最终确认 |

默认路线：**W1架构 → GU1任务基线/W2 J4与GU2 → W3 L2及条件性F3/F7 → W4高级科研与GU3-A/B → W5 M5与GU3-C → GU4/W6整体发布**。F3受阻时继续无关事项但保留缺口；不得自动取消F7前置。人工意见全部编号映射见[总规划J4](后续开发总规划.md#j4-plan)。本次产品实施主线仍为AR0–AR6，新增GU已落实目标/方法设计；后续任务按有限输入和验收合同启动，不从本文自动派发F3测量或未定科学范围。

## 2026-11-07 K2固定范围带限制验收关闭，后续功能暂停

工程64bacb3e、产品b1a7ffbc及309成员模板b2285d11按原身份验收。四云success、12原报告734用例376754断言严格通过，Windows/Linux1.0.0原生runtime/SDK安装已验；原失败、观察边界与科学限制保留。见[最终验收](verification/k2-final-20261107/README.md)。按[用户停点](collab/decisions/20261107-k2-stop-before-architecture-upgrade.md)，交班后暂停新增功能及后续派工，等待整体架构优化计划与用户后续指示，不自动进入L2。F3未关闭、不追加测量或优化，F7依赖不变。下方旧进展按原时点保留。

## 2026-11-07 F3保留资源限制，K2按原依赖并行推进

H3代码冻结f812465b，四云成功；12原报告726用例361946断言严格通过，Windows/Linux1.0.0分平台安装已验。科学72项与工程补验保持原身份，Q2限制及历史失败保留。见[最终验收](verification/h3-final-20261107/README.md)。F3合同及R3修订已冻结；三批基线各自资源inconclusive，原数据与5%标准保留，停止新增性能批次及优化，F3未关闭。R3唯一36次exit0、32科学比对/536产物SHA/12内存身份独核通过，见[本批结果](verification/f3-r3-baseline-20261107/README.md)。K2依K1/I2已就绪，与科研波次并行，K2-1合同已独审冻结并实际启动K2-2导出链实现，见[固定清单](collab/decisions/20261107-k2-closeout.md)；不改变F7依赖。

## 2026-11-06 H2验收关闭，H3启动

H2固定范围已完成，冻结5f68ede0，12云报告720用例357003断言及双平台安装验收通过。[最终证据](verification/h2-final-20261106/README.md)。H3先审平行世界与质量世界的计分/质量/输运语义，再按冻结对照判据实现。Q2限制继续保留。

# G4UniversalSim Development Roadmap

2026-11-05：E4文档收尾验收完成。Q1已完成部分迁移，本轮补齐后续阶段入口、规范与中文入门。附带安装CI按原身份跟踪，下一阶段Q2。[最终验收](verification/e4-final-20261105/README.md)

2026-11-04：**F2受控多轮运行会话验收完成并关闭**。协议B版本化接口保留csh/批处理；冻结864bc036，云12报告708/255163严格门禁通过，Windows125/150和Linux独立X11真实三轮/取消/重放/退出完成。限定环境重放不代替物理基准。见[最终证据](verification/f2-final-20261104/README.md)。下一完整阶段E4。

2026-11-04：**J3本轮约定范围验收完成，保留证据限制后关闭**。候选92134da0；主审本机正式矩阵与真实Windows125/150、Linux独立X11补验，云12报告696/247580及严格门禁复核通过。约一秒切换及历史图/WSLg限制保留。见[最终证据](verification/j3-final-20261104/README.md)。下一完整阶段F2，先做既定三轮实验与协议提案。

Linux原生通道补充（主审已签收）：main已实际操作独立真实X11/xcb桌面，一次固定HTTP计划passed，操作观察时曾停在awaiting_approval、0事件；随后在观察期间触及300秒预算，整任务保留failed／agent.task_timeout，不称整任务成功。原host exit0、slot_released=true、host与显示服务两组remaining_owned均空、HTTP已关闭；显示辅助子进程退出码[0,1,0]（twm非零保留），不能写全部子进程exit0；代表性原生签收结果为 **独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。WSLg RAIL任务栏无法展开，第三次host退出且0请求，原失败保留，绝不称该通道成功。Ubuntu实际系统安装x11-xkb-utils，其它本次依赖保持隔离OUT前缀；具体包版本／SHA及安装收据见最终证据，不把早期准备收据system_installs=0外推到之后。

2026-11-02 当前 L1 签收状态：**本轮约定范围验收完成**；Linux独立X11/xcb代表性原生：**独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。本轮严格矩阵、安装重试与新 Windows 受限原生证据见[最终证据](verification/l1-final-20261102/README.md)。下方早期计划／带日期候选记录保留历史；不改变 F2→后续科研波次及 K2/L2 依赖，不把本轮配置白名单扩大为任意代码执行。


2026-10-31 F5：**已完成**。冻结验收5c1eec5；Windows160/160、50898个v3入口，Linux11.3.2/11.4.3各160、M0两平台各79，原F4逐例与总量门禁通过。原生22份观察/28截图/真实退出0保持5d身份，经明确映射关联新冻结；不新增物理验证结论。[最终证据](verification/f5-final-20261031/README.md)。下方带日期的旧状态保留其历史范围。

Agreed 2026-10-21. Order of work: **Phase A core functions → Phase B scenario packs → Phase C wizard and plotting → Phase D installer** (only once the framework is mostly stable).

This file is the single source of truth for progress. Every work session updates the status table and the progress log at the end.

2026-10-24 接续计划：见[开发接续计划](开发接续计划.md)。该计划细化 E2 余项、F6/F2 依赖、阶段验收及历史证据边界；本文件继续维护唯一的阶段状态。E2 已于 2026-10-25 启动整阶段实施，验收证据见 [E2接续检查点](E2接续检查点.md)。

2026-10-24 交付节奏：按用户要求，以 E2、F6、F2 等完整工作项持续推进并交付。模块拆分与中间测试属于内部实施步骤，不要求用户逐项发出继续指令；必要决策和真实阻塞仍需明确报告。

## Status

| Item | Status | Commit |
| --- | --- | --- |
| Repo cleanup | Done | `f90e1da` |
| A1 ROOT output layer (G4AnalysisManager) | Done | `889b618` |
| A2 Native Geant4 scoring + LET | Done | see log |
| A3 Statistical uncertainty | Done | see log |
| A4 Full GPS sources | Done | see log |
| A5 Geometry (GDML, replica/parameterised, solids, true preview) | Done | see log |
| A6 Physics (EM options, radioactive decay, region cuts/limits) | Done | see log |
| A7 Fields | Done | see log |
| B Scenario packs + benchmarks | Done (B1 benchmarks, B2 shielding/coating, B3 semiconductor, B4 detector response) | see log |
| C Wizard + built-in plotting | Done (C1 built-in plots, C2 wizard, C3 parameter scans) | see log |
| D Installer | Done (portable ZIP + Inno Setup installer; uses an existing Geant4 data folder) | see log |
| E Fixes and foundations | In progress: E1, E2, E3 (Linux incl. Geant4 11.3.2/11.4.3 matrix, done 2026-10-28), E5 and E4 done | see log |
| F System optimisation (backend + GUI) | In progress: F1/F2/F4/F5/F6/F8 done; F3/F7 pending | see log |
| G 3D view redesign | Done (G1-G6) | see log |
| H Geant4 capability increments | In progress: H1/H2/H3 fixed scope done; H4-H9 pending | see log |
| Q1 完整可靠性审查、修复与验收 | **已完成**：九域审查及R01–R32闭合；Windows105、Linux双版本各105与实窗通过 | 验收代码 `8ecad66`；[最终证据](verification/q1-final-20261029/README.md) |
| 2C 完整 EffectiveConfig / off-auto-on | 已完成：11消费者/三阶段/模块策略/只读GUI，Windows118、双版本Linux118、同口径门禁与实窗验收 | `f4770b0`；[最终证据](verification/2c-full-20261029/README.md) |
| E6/E7、Q2、I1/I2、J1/J2、K1/K2、L1/L2 | 已编号并排期；继承已有基础，不冒充完整实现 | 下文统一计划 |

## Data storage decision

Geant4's analysis category (`G4AnalysisManager`) is the single output layer. ROOT (`.root`) is the primary format, written natively by Geant4 with automatic thread merging; CSV stays as a debug/compatibility option. GUI and Python tools read ROOT with `uproot`.

## Phase A: core functions

1. **Output layer on G4AnalysisManager — done.** `[output] format = csv|root|both`; one merged `g4usim[_rR].root` per run (schema `g4usim_root_v1`); `run_metadata.json`. Follow-ups: switch default to `root` once the GUI reads ROOT; add git commit and config hash to metadata.
2. **Scoring on native Geant4 scorers — done.** `/score/` meshes from macro or INI (`[scoring.mesh.*]`), exported to ROOT `mesh` / `scoring_mesh.csv` with sum, sum_sq, entries, rel_error; dose/fluence prototypes validated against native scorers; LET_t/LET_d (`[scoring] let = true`) validated against Bethe. Follow-ups: real-volume primitive scorers (G4MultiFunctionalDetector on logical volumes), heavy-ion LET benchmark, GUI editors. Original scope: `/score/` box/cylinder meshes written to the ROOT file; `G4MultiFunctionalDetector` primitive scorers (energyDeposit, doseDeposit, cellFlux, passageCellCurrent, nOfSecondary) with particle and energy filters, configurable from INI/macro; validate the existing dose/fluence prototypes against them; add LET (track- and dose-averaged).
3. **Statistical uncertainty everywhere — done.** Edep/dose/fluence/LET accumulate per-event sum and sum of squares; master-merged `scorer_statistics[_rR].csv` (all formats) with mean, std error, rel error and FOM; LET ratio errors by the delta method; additive columns in per-thread CSVs and ROOT (`g4usim_root_v4`). Follow-ups: show error bars in the GUI results pages, validate weighted (biased) runs, batch-statistics option for heavy-tailed LET_d.
4. **Full GPS sources — done.** `energy_type` (gauss/uniform/power/exp/histogram/points file), volume sources with `confine`, Gaussian beam spots, rotated and annulus/ellipse/square planes, cos/cone/beam1d/beam2d/focused angular distributions, weighted `[source.<name>]` multi-sources, ion and radioactive-decay sources, phase-space write (`[phase_space]`) and replay (`[source] phase_space_file`). Follow-ups: GUI source editors for these fields, the radioactive-decay time threshold (A6, long-lived nuclides such as Co-60 are skipped by default), GPS biased sampling, streaming of large phase-space files.
5. **Geometry — done.** New solids (ellipsoid, eltube, torus, para, hype, polycone, polyhedra), STL import (`shape = tessellated`), `placement = replica` / `parameterised`, `/AIHL/geometry/exportMesh` and the GUI "Show Backend Geometry" view of the real Geant4 world. GDML import (`template = gdml`, `SensDet` auxiliaries) and export (`/AIHL/geometry/exportGDML`) with an exact round trip; the machine's Geant4 11.3.2 was rebuilt with GDML for this. Follow-ups: GUI editors for the new solids/placements, assembly volumes, A5 solids as boolean tools, STEP/IGES via external conversion.
6. **Physics — done.** EM presets via `[physics] em` verified by process dump and NIST XCOM transmission; `[physics.radioactive_decay]` (enabled, time_threshold); `[physics.region.<name>]` production cuts, step limits and user special cuts (`volumes =` creates regions, also for GDML); `/AIHL/physics/dumpProcesses` (`g4usim_process_dump_v1`). Follow-ups: GUI physics editors for these fields, per-region EM model options, broader EM benchmarks in Phase B.
7. **Fields — done.** `[field]` / `[field.<name>]` uniform magnetic and electric fields (also combined), Cartesian field maps with trilinear interpolation, volume-local fields, adjustable integration accuracy; built per thread. Follow-ups: cylindrical/symmetric maps, time-dependent fields, GUI field editor.

## Phase B: scenario packs

Each pack = configs + docs + a benchmark against reference data.

- Shielding / composite coating — done (B2): `scenarios/shielding_coating` ports CoatingSimulation as a generator (`make_scenario.py`: layer stack, integral-flux proton/electron/mixed spectra, reduced-density junction layers, parameterised vacuum pores, region cuts/step limits, transmission or albedo phase space) plus `analyze.py` (TID/DDD per primary, per fluence and normal-incidence rate; spectra). New experimental displacement damage scorer (`[scoring] displacement`, track-length fluence folded with user NIEL tables; no NIEL data shipped). Reference benchmark `scenarios/benchmarks/shielding_range`: Al/Si CSDA ranges and proton residual energies vs PSTAR/ESTAR. Follow-ups: cited Si NIEL tables, omnidirectional (cosine-law) irradiation, coating-material stopping benchmarks, GUI support.
- Semiconductor device dose and displacement damage — done (B3): `scenarios/semiconductor` (`make_device.py`: lid, BEOL, gate oxide, active Si, replica substrate slices; mono/spectrum/mixed/neutron sources; `analyze_device.py`: per-layer TID, DDD, 1 MeV neutron-equivalent fluence, depth profile). Ships SR-NIEL silicon NIEL tables (protons, electrons, ASTM E722-19 neutrons) with a converter. Benchmark `scenarios/benchmarks/device_dose`: thin-slab proton dose per fluence vs PSTAR Si electronic stopping power (within 0.4 %) and DDD per fluence vs the SR-NIEL tables (within 0.7 %). Follow-ups: SiO2 dose reference, device response models (e.g. leakage current damage constants), omnidirectional sources, GUI support.
- Detector response — done (B4): `scenarios/detector_response` (`make_detector.py`: housed cylindrical crystals NaI/CsI/BGO/LaBr3/HPGe/plastic/CZT with a cone-sampled point source, or a Si pad with a parallel beam; `analyze_detector.py`: pulse-height spectra from `event_edep`, MCNP-GEB Gaussian resolution, intrinsic/absolute detection and full-energy-peak efficiency, peak-to-total, Compton edge, escape peaks, Si most probable deposit). Benchmark `scenarios/benchmarks/detector_response` against analytic references: Klein-Nishina Compton edges, pair escape lines, PDG Landau-Vavilov-Bichsel MPV (Geant4 option4 +0.1 to +2.7 % in 300 um Si). Follow-ups: scintillation light yield and Birks quenching, measured efficiency comparisons, optical/charge collection, GUI support.
- Benchmarks — done (B1): `scenarios/benchmarks` (csda_range, bragg_peak, gamma_attenuation) with `scripts/run_benchmarks.py` (JSON/Markdown report, `--quick` in the suite): proton/electron CSDA ranges vs PSTAR/ESTAR (+0.2 to +0.95 %, explained by I = 78 eV for G4_WATER), 150 MeV R80 +0.84 %, photon mu/rho vs XCOM within 1.7 sigma.

## Phase C: wizard and built-in plotting

- Guided "new simulation" wizard — done (C2): File → New Simulation... (`gui/g4usim_gui/core/wizard.py`, `widgets/new_simulation_wizard.py`): scenario (single target, depth-dose phantom, shielding slab, silicon detector, gamma spectrometer) → NIST materials and sizes → source → physics/outputs/run with a live summary; the result replaces the project's editor models in place and goes through the editors' validation, package writer and run. Follow-ups: scenario-pack (B2–B4) presets that need backend-only fields, custom materials, wizard re-entry from an existing project.
- Built-in plots — done (C1): Results / Plots tab (`gui/g4usim_gui/output/plot_data.py`, `widgets/plot_panel.py`, matplotlib) for scorer totals with A3 error bars, scoring-mesh profiles and 2D maps (CSV or ROOT), Edep histograms, per-event deposit and phase-space spectra; log axes, per-primary normalisation, run overlay, comparison with other output directories, image and data export. Follow-ups: selection statistics, map comparison (ratio/difference), plots for scenario-pack reports.
- Parameter scans and batch runs — done (C3): Parameter Scans page (`gui/g4usim_gui/core/scan.py`, `core/scan_runner.py`, `widgets/scan_page.py`): one Configuration-page setting (source energy/particle, physics list, seed, events, volume material, box thickness) over a list or lin/log range; every point validated first, then an ordinary run package plus `scan.json`; points run one after another with the normal runner; results table and plot of any scorer_statistics quantity with statistical errors, per-primary option, CSV export, reopen. Follow-ups: two-parameter grids, parallel points, scans of scenario-pack generators.

## Cross-cutting improvements

- One schema as the single source of truth for C++ validation, GUI forms and docs.
- English documentation alongside Chinese.
- CI (GitHub Actions) with Geant4 Docker/conda-forge; compatibility matrix Geant4 11.2–11.4, Windows/Linux.
- Batch/cluster mode (Slurm export) and Linux Docker image.
- Lighter process docs: `CHANGELOG.md` plus the support matrix instead of long agent logs.

## Phase D: distribution

One-click Windows installer (backend + GUI + examples) after Phases A–C are mostly stable.

Done (D): `packaging/build_package.py` builds a portable folder, a ZIP and an Inno Setup installer (`packaging/installer.iss`): backend plus the Geant4/Xerces-C/Qt 5/VC++ DLLs it loads (collected with dumpbin), the PyInstaller-frozen GUI, examples, scenarios, scripts, docs and third-party licenses. Geant4 data is not bundled (user choice): the backend uses the per-dataset variables, `GEANT4_DATA_DIR`, or `bin/geant4-data.txt` (written by the installer), and `--check-geant4-data` reports what it found. The build checks the package with a clean environment (data resolution, a real run, frozen-GUI self-test); `packaging/test_installer.py` installs, checks and uninstalls silently. Follow-ups: code signing, a GUI page for the data folder, testing on a machine without Geant4, an optional data-download helper.

## GUI refresh (after Phase D)

Done: Start page with an examples gallery (five examples with bundled results that open in Results / Plots or Parameter Scans), line icons, refined light/dark theme with a matching Qt palette, status chips, grouped tabs, collapsible Configuration setup sections, theme-coloured plots with an icon toolbar, empty states; fixes for stale validation after the wizard, plot theming, untranslated scan text and CJK text in plots. Follow-ups: a "run session" mode for adjusting whitelisted settings between runs, a GUI page for the Geant4 data folder, high-DPI and accessibility review by a person.

## Next phase plan (agreed 2026-10-23): E fixes, F optimisation, G 3D view, H Geant4 increments

Built from the 2026-10-23 project review. Items are numbered for reference; the
**order of work** below interleaves the phases so the user-visible 3D problems are
fixed first and foundations land before the features that depend on them. Every item
follows the working agreement (branch, Release build, real Geant4 regression, full
suite, CHANGELOG, support matrix). "Done when" lists the evidence, not just the code.

### Phase E: fix the known weaknesses

- **E1 GUI/backend rule mismatch (3D blocker).** The GUI checks material names
  case-sensitively, the backend (`MaterialFactory`) does not, so the default demo
  geometry (`silicon`, `iron`, `water`) is rejected by the GUI, no package is generated
  and "Show Backend Geometry" fails although the backend builds it in ~3 s. Make the GUI
  match the backend, then add a **differential test**: every geometry/material/main INI
  fixture in the repo and every wizard/gallery package goes through both the GUI
  validator and `--inspect-run`; any disagreement fails. Done when: the demo project
  generates a package and shows backend geometry; the differential test is in the suite
  and lists zero mismatches (or each remaining one is documented and blocked on purpose).
- **E2 Single configuration schema — done (`aaa9c1d`, agreed modules).** One machine-readable schema (sections, keys,
  types, units, defaults, allowed values, support level, since-version) as the source
  for the Python validators, GUI form hints and the support-matrix field tables; the
  C++ side gets a generated key/type table that its existing validators consult, and a
  test fails if C++ parsing and the schema disagree. Migrate module by module
  ([run]/[output] → [source] → [physics] → [scoring] → geometry/material files).
  Done when: E1's differential test passes from the schema for the migrated modules and
  the matrix tables are generated.
- **E3 Continuous integration.** GitHub Actions on Linux with Geant4 11.3 (conda-forge
  or the official Docker image): configure, build, static + GUI offscreen + backend
  suites; Windows stays local (no Geant4 on hosted runners). Later: Geant4 11.2/11.4
  matrix. Done when: every push to `codex` runs it green, and a Linux build is
  documented. (Decision needed: hosted runners on the public repo.)
  Status 2026-10-28: **done for Linux.** `.github/workflows/linux-geant4.yml` runs on
  `ubuntu-24.04` with conda-forge Geant4 11.3.2 (micromamba) and is green on both
  branches with all four profiles: `codex` run 40640355033 and
  `roadmap/F6-live-progress` run 40640350911 for commit `3291145` (~12-13 min each; the
  earlier `a5970ff` runs were green for backend and integration only). The job configures and builds the backend, checks the
  Geant4 data lookup, then runs the static, offscreen GUI, backend and integration
  profiles on Linux, validates each report with `scripts/check_report_evidence.py`, and
  proves the evidence gate rejects a tampered report. The Linux build process (two
  GCC-only defects, the PySide6 teardown SIGSEGV and the conda Qt plugin-path trap) is
  documented in `docs/Linux构建与验证.md`. Status 2026-10-28 (later): the Geant4 matrix is in
  place — `linux-geant4.yml` builds and runs all four profiles twice, once with Geant4 11.3.2
  and once with 11.4.3 (the 11.4 leg receives the expat/zlib/freetype `-D*` paths; 11.4 was
  probed locally first, see `docs/Linux构建与验证.md` §8). Both legs are green on commit
  `6a8b237`: run 40690078563 (`codex`) and 40690070991 (roadmap) with 26 steps per job, and
  the `m0-static-gui.yml` workflow was enabled by the repository owner and is green on ubuntu
  and windows (run 40690078519 / 40690071129 for the same commit; 40675415994 / 40675409885
  for the first green at `402a9f2`). Remaining: Geant4 11.2 is untested; Windows + 11.4 and
  the 11.4 desktop GUI/ROOT/packaging paths are not verified.
- **E4 文档与开发规范收尾。** 已有历史条目迁移和链接检查，继续清理当前规范中的历史状态矛盾、补齐中文快速入门和契约索引。
  按现行人类文档中文规则执行，不把早期英文快速入门设想当作必交付项。验收：历史规则逐项可追踪、当前入口无相互矛盾状态、链接检查通过。
- **E5 Split the large GUI files.** `config_builder_page.py` (~2300 lines) into one
  widget per editor (materials, geometry, boolean ops, 3D, source, physics, scoring,
  details) and `main_window.py` into controllers (run, inspection, geometry export,
  examples). No behaviour change: all GUI smokes pass unchanged, plus a smoke that every
  editor widget can be built alone.

### Phase F: system optimisation

Backend:
- **F1 Output and provenance.** `[output] format = auto` (ROOT when hits or per-event
  data are on, CSV otherwise), git commit and config hash in `run_metadata.json`
  (A1 follow-up), buffered CSV writers; measure hits-heavy runs before/after.
  (Decision needed before changing any default.)
- **F2 Run session (adjust between runs).** Done 2026-11-04, frozen864bc036.
  Versioned session protocol B retains csh/batch. Audited Idle source particle,
  energy, position and direction edits carry request/actual receipts; geometry,
  physics, threads and complete configuration switches require a new process.
  Real A/B/A, cancellation and separate-process replay passed within the fixed
  build/data/random-state/thread/order scope. No cross-platform bitwise promise.
  See [final acceptance](verification/f2-final-20261104/README.md).
- **F3 Performance.** Profile a hits-heavy and a mesh-heavy run; optional
  `G4TaskRunManager` (`[run] run_manager = mt|tasking`) remains a separate experiment,
  with a defined seed protocol and predeclared event/statistical comparison criteria.

GUI:
- **F4 Validation that leads to the field.** Every message carries its location
  (editor, row, field); clicking it selects the tab/row and highlights the control.
- **F5 Undo/redo and autosave.** 主项目和成功应用向导共用完整快照事务；v8保存材料/几何及原始草稿，完整v7编辑快照仅补枚举的新字段，独立恢复副本受系统会话锁保护，恢复为未命名、未保存副本。[使用与限制](配置撤销与恢复.md)。
- **F6 Live run progress.** The backend prints a progress line (events done, rate)
  at a fixed interval; the Run Console shows a progress bar, rate and time left.
- **F7 Better scans.** Two-parameter grids with a 2D map plot; several points at once
  within a thread budget; scans of scenario-pack generators.
- **F8 GUI follow-ups and acceptance.** 衔接I1环境设置与J1主题/布局，完成向导重入及跨页DPI、键盘、文案和可访问性实窗验收。

### Phase G: 3D view redesign

- **G1 The real geometry by default.** "Show Backend Geometry" no longer needs a
  generated package: it writes a temporary one (same validation), caches the mesh by a
  hash of the inputs and refreshes it automatically a moment after geometry edits
  (export measured at ~2.5-3 s). While it runs, the editor sketch is shown and labelled
  approximate; failures show the backend's own message with file and line.
- **G2 Visual design.** Theme-coloured background, one colour per material with a
  legend, sensitive volumes highlighted, the world hidden by default, subtle edges,
  labels on hover instead of always on, camera presets (front/side/top/isometric),
  perspective/orthographic toggle, image export.
- **G3 Interaction.** Click a volume to select its table row and back; isolate/hide
  volumes; a section (clipping) plane with a slider; opacity control.
- **G4 Accurate editor sketch.** Exact nested transforms (composed like Geant4),
  segments of spheres/tubs/cones, the A5 solids drawn or listed as "not drawn" instead
  of silently missing. Done when: for every geometry fixture the sketch's volume
  bounding boxes match the backend mesh within tolerance (automated).
- **G5 Source display.** Glyphs that match the GPS settings: point, plane shape,
  direction cone, isotropic marker.
- **G6 Particle tracks.** Overlay trajectories from H1 (colour by particle, filter by
  particle/energy, step through events).

### Phase H: Geant4 capability increments

Each item ships with a benchmark against an independent reference, default off, and
is marked experimental in the support matrix until benchmarked.

- **H1 Trajectory export.** `[output] trajectories = <n events>` writes a small JSON
  (`g4usim_trajectories_v1`: particle, parent, step points, energy). Benchmark: step
  points lie in the volumes the navigator reports; primary range matches CSDA.
- **H2 Filtered scoring and spectra.** Particle and kinetic-energy filters on the
  volume scorers and meshes; energy spectra per volume. Benchmark: filtered parts add
  up to the unfiltered total; a mono beam's spectrum peaks at the expected energy.
- **H3 Parallel-world scoring.** Meshes and scoring volumes in a parallel world
  (`G4ParallelWorldPhysics`), independent of the mass geometry. Benchmark: same dose as
  scoring slabs placed in the mass world.
- **H4 Variance reduction.** Geometry importance sampling and weight windows.
  Benchmark: deep-shielding transmission equals the analog result within errors, with
  the figure of merit gain reported.
- **H5 Optical physics.** Scintillation (light yield, Birks), Cherenkov, optical
  surfaces, photon counting at a sensitive surface. Benchmark: photons per MeV equal the
  configured yield; Cherenkov photon count per mm against the Frank-Tamm formula.
- **H6 Activation and thermal neutrons.** `G4Radioactivation` with time windows and
  thermal scattering data (e.g. `G4_WATER_TS`). Benchmark: activity against the Bateman
  solution; thermalised neutron spectrum against a Maxwellian at room temperature.
- **H7 Track-structure physics.** Geant4-DNA in one region. Benchmark: values from the
  published Geant4-DNA examples for the same configuration.
- **H8 规则体素模板与材料映射。**参考 ICRP110/DICOM 的参数化经验，先交付规则体素和限定混合建模；
  自适应与 DICOM 另行评估。范围、验证及未决事项见 [H8 参考规划](#h8-reference-plan)，不将同源对照等同于独立物理验证。
- **H9 Generic histograms and ntuples.** `G4AnalysisManager` H1/H2/ntuple definitions
  from INI, replacing hand-written writers where they overlap.

### 统一代号与排期（2026-10-29，当前执行依据）

代码基线 `f9930aa`，隔离分支 `roadmap/2c-effective-config`；原 DSH 目录 `5465dbd` 保留并发审查资料。以下覆盖旧顺序中的待办部分，既有完成记录不重编号、不重写。**代号是完整交付单元，提交节点是内部实施步骤，不要求用户逐提交发出“继续”。** 排期波次是分组，不意味着该波次全部项目同时开工或一次巨型提交。

- 保留 `2C` 和原 `E/F/H/M` 编号；`Q` 为质量与科研验证，`I` 为环境交付，`J` 为工作区/编辑覆盖，`K` 为实验包/工程导出，`L` 为 AI 执行。
- `R-01` 等仍是缺陷编号，`V-01` 是方法风险；它们不是开发阶段。`Q1` 不等于 `R-01`，后者只是 Q1 下的一个问题。
- 2A/E3 Linux 与 2B 屏蔽场景、E1/E2/E5、F6、G1–G6、H1 的已交付范围保留。E2 的新增范围记 E6，不把原 353 字段迁移改成未完成。
- 阶段状态只维护在本文件；STATUS 是导航，接续计划解释执行约定，历史 M0–M5 文档用于目标追踪，不再各写一张当前进度表。

#### 排期波次与交付顺序

| 顺序 | 波次 | 完整工作项 | 进入下一波次的关键条件 |
| --- | --- | --- | --- |
| 1 | 可靠性基线 | **Q1**；E4 文档校准可同步 | 本对话完成约定范围的全模块审查、修复、独立复核与验收；不只清空已收到的 R 清单 |
| 2 | 配置底座 | **2C → E6** | 真实消费者/生命周期证据、模块三态、schema 与迁移契约闭合；I1 只读环境设计可并行 |
| 3 | 可信实验闭环 | **F1 → F4 → F5 → K1**，并行 **I1** | 手工操作和未来 Agent 共用检查/修改/运行/判断服务；可验证、可移植配置包成立 |
| 4 | 双平台桌面与手工建模 | **I2、J1**独占文件并行；随后 **J2**，几何相关部分衔接 **E7**；**F8**完成跨项验收 | Windows/Linux交付、区域清楚的主题与可调整布局、3D外观控制、空白创建与无源输入、常用编辑覆盖；跨页DPI/键盘/向导实窗验收 |
| 5 | 自动配置与运行 | **L1 → F2** | 配置 Agent 真正闭环；F2 单独证明 Idle 白名单与重放。L1 先用新进程，不被热会话阻塞 |
| 6 | 科研效率与架构补齐 | **Q2 → H2 → H3**；**F3 → F7**；E7 已前移支撑 J2，剩余架构工作按文件归属串并行 | 独立物理/权重基准、过滤/平行世界、性能/二维扫描各自整项验收，不重复建设已有编辑链路 |
| 7 | 独立工程与代码执行 | **K2 → L2** | 干净 Windows/Linux 环境能独立构建、运行、继续开发；代码 Agent 有隔离、恢复与有限修复证据 |
| 8 | 高级物理与生态 | **H4 → H5 → H6 → H8 → H7 → H9**，**M5** 独立排期 | 每项单独确定适用域、输入/输出契约和参考数据，不以 AI 能调用为物理验收 |

上表是默认资源顺序，不把前面波次的无关项目做成硬依赖。例如 K2 可以在 K1/I2 就绪后与科研波次并行，不要求所有 H/J 项先完成；L2 必须等 K2 和 L1 的执行契约就绪。Q2 的方法资料准备可从 Q1 开始，正式科研结论不能早于其验证。若用户提出明确科研急需，可调整 H4–H8 的先后并在这里记录，不丢弃原计划。

#### 当前质量与配置工作项

| 代号 | 范围与已有基础 | 依赖/完成条件 | 当前状态 |
| --- | --- | --- | --- |
| **Q1** | 完整可靠性审查、反例复现、修复、回归与交付复核；覆盖已公开能力和拒绝边界 | 九域独立复核、确认缺陷及正式回归闭合，冻结矩阵与同v3逐例/总数门禁通过 | **已完成**；验收代码 `8ecad66`，见[最终报告](verification/q1-final-20261029/README.md) |
| **2C** | 完整 EffectiveConfig：11 类真实消费者、稳定对象身份、完整来源链、实际读取字节哈希、事务替换/删除、configure/run_begin/finalization、内核/worker 证据、off/auto/on、GUI 审查 | Q1 基线；每类消费者有正反例，拒绝不污染 revision/来源；unknown 不伪装 applied；现有协议兼容 | 已完成（产品 `f4770b0`）；`70a1aba` 仅为历史配置子集。[完整2C最终证据](verification/2c-full-20261029/README.md)，不扩张E6/F1/Q2等范围 |
| **E6** | E2 范围补齐与配置兼容：field/biasing schema；主 INI 版本策略；几何 v2/项目格式迁移与诊断去重 | 2C；生成表不手改；旧输入/别名、未来未知版本、迁移副本、**现有编辑子集** writer 兼容/往返。扩大编辑范围归 J2，不让 E6 等待 J2，不顺带开放 assembly/材料温压等 | 已完成：代码 `a779634`，Windows134、Linux双版本各134、M0双平台各58；实窗12状态与真实2/2事件、独立复核通过。[最终证据与集成状态](verification/e6-visible-20261030/README.md)。E2 原状态保持完成 |
| **E7** | SolidRegistry 与统一实体能力元数据；后端构造、校验、能力查询、GUI 可消费定义逐步归一 | E6/现有 A5；实体逐项差分、缓存/线程生命周期守卫与旧配置不变；不借重构增加未验实体 | 2026-11-02 **本轮15/7约定范围完成**：既有15原语/7布尔工具统一factory注册、能力元数据及GUI离线定义接线，兼容/缓存生命周期/适用矩阵通过；实体集合、A5实验性与科学等级不变；测试冻结2ec5b14，见[最终证据](verification/j2-f8-final-20261102/README.md) |
| **Q2** | 科研基准与适用范围：Dose/Fluence/LET/DDD、统计不确定度、现有 XS biasing 与 analog 对照、独立数据/解析参考与可复现实验 | Q1、F1；V-01 的口径先在 Q1 明确，Q2 再验证有限样本/覆盖与适用边界；不以同源自洽或 process 挂接代替独立证据 | 已完成本轮限定范围验收（2026-11-06），科学产品864bc036、最终文档/测试ed6aad6a；LET/DDD/NIEL/偏置适用域限制保留。[最终证据](verification/q2-final-20261105/README.md) |

#### 原 E/F 余项（保留原编号）

| 代号 | 整项交付内容 | 验收/归属与提交重点 | 当前状态 |
| --- | --- | --- | --- |
| **E4** | 当前规范瘦身、历史状态校准、中文快速入门、文档单一事实入口 | 历史条目迁移已有成果；补规则逐项映射，清除 stale 状态，链接与必要 smoke 通过。阶段关闭交 `docs(E4)` | 已完成（2026-11-05）：46行映射、两平台Qt操作复演、文档云708/255154与严格门禁通过。[最终验收](verification/e4-final-20261105/README.md) |
| **F1** | 输出身份、commit/config/项目实际读取资源 hash，未观测输入明确标记；版本化输出与测量后决定缓存/format=auto | 来源/格式节点分开提交；默认CSV不变。依赖 2C/E6，支持 K1/Q2 | 已完成：产品f176d0e；Windows143/143及E6基线、Linux双版本各143、M0双OS各64通过，14次实窗观察/正常关闭与独立复核通过。[最终证据及集成](verification/f1-visible-20261030/README.md)。[自动归档](verification/f1-automated-20261030/README.md)保留两轮失败及当时pending；72次测量完成、缓冲候选撤回。[契约](collab/inbox/20261030-1410-astra-f1-scope.md) |
| **F2** | GUI 受控 run session、Idle 白名单、逐 run 输入/来源/重放协议 | 完整换配置用新进程；三轮调整的真实状态与限定环境重放；不承诺跨平台/线程数逐位一致。可在 L1 后交付 | 已完成（2026-11-04）：864bc036，云708/255163、Win125/150与Linux X11真实运行及重放通过。[最终验收](verification/f2-final-20261104/README.md) |
| **F3** | hits-heavy/mesh-heavy 的耗时、内存、输出基线及瓶颈优化；tasking 单列实验 | 测量→单一瓶颈变更→前后对照；统计/种子/输出契约不改变。性能优化不能成为接受结果差异的理由 | 进行中（资源限制）：三批均inconclusive；R3 36执行/32科学/536产物SHA/12内存身份全核通过，三组合MAD超冻结5%，停止追加及优化，阶段未关闭；[R3证据](verification/f3-r3-baseline-20261107/README.md)。增加重复/配对测量、CPU热点采样、隔离原型与性能上限评估的[后续参考方案](collab/decisions/20261107-f3-closeout.md#f3-future-options)已记录，尚未批准执行或修改冻结门限 |
| **F4** | 定位到 editor/row/field/code 的诊断及点击跳转 | 诊断身份不随语言改变，不抹除来源错误；K1/L1 复用同一结构 | 已完成：产品 `7d718d038a00d89995ea773b4772764116b620c3`；Windows 152/152、49913 个 v3 入口与 F1 原始143/48511同代基线门禁；Linux11.3.2 为 152 项、11.4.3 为 152 项（run 41056994075），M0 Windows 为 72 项、Ubuntu 为 72 项（run 41056993987）。CI实际提交 `a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9`，与产品的关系见[提交身份映射](verification/f4-final-20261030/identity/identity-map.json)。Windows原生 13 态、19 次实际观察与进程退出 0；[最终证据](verification/f4-final-20261030/README.md)，[独立审查](collab/reviews/20261030-astra-f4-close-review.md)。 后续F5当前状态见下一行。 |
| **F5** | 配置事务 undo/redo、自动保存、异常恢复 | 主编辑快照完整；恢复不覆盖原件，撤销后重新验证 | 已完成：5c1eec5，Windows160/50898、双Linux各160、M0双平台各79及F4门禁通过；5d实窗22观察/28截图/退出0经身份映射。[最终证据](verification/f5-final-20261031/README.md) |
| **F6** | 实时进度与 sequence | 已完成，Q1 复核解析、取消和失败边界；进度不替代成功证据 | 保持完成 |
| **F7** | 二维扫描、线程预算内并发、场景生成器扫描 | 依赖 K1/F3；每点独立 seed/目录/证据，失败/重试不重复发布，缺点可见 | 待开始；已有单参数串行扫描保留 |
| **F8** | 环境设置衔接、空白/模板/导入与向导重入、跨页DPI/键盘/文案一致性与可访问性 | I1/I2提供环境链路；J1实现布局/主题/主要中文及焦点适配；J2实现无源创建和编辑能力；F8做跨项桌面验收 | 2026-11-02 **本轮约定范围完成**：2ec Windows300/181357、CI12报告636/221186严格通过；旧18c三档限定映射+新2ec125代表补验及文件独审，窄dock/QQ/缓存边界保留；后续docs/evidence提交不改原测试身份 |

E3 的已完成 Linux CI 基础不重建；Windows 11.4、原生 Linux 桌面、包内 ROOT/Python 辅助工具与干净安装验收归 I2。现有后端 ROOT 输出和新版本源码 CI 仍按 Q1 及各阶段冻结矩阵验证。Geant4 11.2 先在 I1/I2 决定是否进入支持矩阵：不支持则清晰拒绝/说明，不默认承担无限旧版本兼容。

接口所有权：F4 先实现可复用诊断结构，F5 先实现配置事务/撤销基础；K1 负责组合这些能力、已有 runner/result/package writer 与 CLI/GUI，形成统一动作服务。前置 F 项不等待 K1 完成，K1 也不再另造第二套事务和进程控制器。I1 只提供环境事实，I2 执行环境安装，均不拥有模拟任务状态。

#### 2026-11-01 实际使用反馈与排期调整

用户两次运行后的六项反馈已获授权纳入计划；本节规定目标，不宣称实现。J2 从原第六波次前移至 L1 之前。I2/J1 本次完整启动，J2/F8/H2/H7 仍按各自完整阶段验收，不在本次偷偷扩成全量物理开发。

| 反馈 | 阶段与交付 | 必须满足的验收条件 |
| --- | --- | --- |
| 3D颜色、透明度可调 | J1补齐原G3透明度控制缺口；后端vis属性编辑归J2 | 按体积/材料调整与复位，选中/径迹/世界显示优先级清楚；换几何不串用同名对象偏好；不改仿真输入/验证资格，真实窗口检查 |
| 五模板之外从零构建 | J2并列空白创建、模板创建和导入；F8整体验收 | 无需先选示例；可从world和空材料文档开始，新建/取消/Undo/恢复不污染旧工程；五模板继续可用 |
| 无已有文件直接输入 | J2贯通内存文档、校验、writer和K1动作 | 无用户准备的INI/macro/材料几何文件仍可输入、校验、生成、真实运行、保存重载及离线导出；程序按需生成必要文件，不取消运行环境依赖；非法草稿、外部源变动和旧包边界保持 |
| 自动使用NIST元素 | J2补全搜索/来源显示和诊断，复用已有后端FindOrBuildElement | 自建元素优先，合法NIST元素免预声明，拼写错误拒绝；自定义同位素组成不被替换；体积分数必须使用有密度材料，不能把元素当材料；生成/重载后来源可解释 |
| 多物理模块注册与替换 | J2开放reference+附加/替换及受支持manual模式，必要后端先补齐 | 一套完整physics list内多个constructor；同类冲突明确诊断，替换后旧模块实际消失、新模块和process实际存在；region步长限制按真实机制生效，不能只凭INI或注册调用判成功；微观径迹结构归H7 |
| 多源、多类型源、多灵敏体积 | J2命名源/intensity/位置方向能谱、Surface Sphere及多体积可达性；H2过滤/能谱 | 区分按强度选源与每事件多源同发，球面与球体内部采样有独立真实顶点检验；多敏感体分别计分不丢事件关联，普通多体积不冒充独立SD响应；单探测器谱分析不能直接套多体积 |

J2内部提交顺序为：无源创建/文档身份 → 材料辅助及多体积操作 → 多源与球面源链路 → 物理组合/替换与高级编辑 → 完整回归/独审；源码、运行证据与物理适用范围分别登记。E7所需几何接口在对应提交前完成，不借依赖关系推迟与实体无关的改进。

#### 新五项目标的正式代号

| 代号 | 对应用户目标与整项内容 | 硬依赖 | 主要提交节点/最终验收 |
| --- | --- | --- | --- |
| **I1 环境发现与诊断** | 后端/运行时真实查询、SDK/工具链及可选组件候选事实、版本/架构/数据诊断，异步 GUI 显式选择 | Q1；只读发现与运行资格分开，不安装或自动模拟 | **已完成**：第五冻结专项与独立审查通过，第四单候选实窗按未变 I1 字节映射；第七 `2914b39` 五项文件 SHA 再核一致。[证据与限制](verification/k1-final-20261031/README.md#i1-独立验收) |
| **I2 辅助安装与双平台交付** | 目标 1；受控安装前缀、下载校验、失败恢复、运行时/SDK 两种方案、当前版本 Windows/Linux 包、诊断包和版本矩阵 | I1 | **2026-11-01 已完成阶段验收**：计划/获取/发布/恢复、runtime/SDK、两平台安装/核验/卸载、SDK consumer 与完整源码构建、冻结工具及实际 CI 均已验证；无匹配清单时明确不可安装，不承诺自动配置任意编译器。最终测试 `6310969` 与产品 `5fe0a10` 的身份及旧失败见[最终证据](verification/i2-j1-final-20261101/README.md)。 |
| **J1 可调整工作区** | 配置、3D/结果、日志、AI区可移动/缩放/隐藏/浮动；三种布局及B/K/C主题、明确区域层级与主要中文；本机布局持久化，按体积/材料调整3D颜色和透明度及会话复位 | Q1/K1状态所有权稳定；与I2按文件独占并行 | **2026-11-01 已完成阶段验收**：DeepSeek实际设计协作、单实例dock、本机保存/重启恢复/回退、主题/3D外观与运行中切换经独审及实窗验证；26图、4次正常退出，中英及代表性DPI，未做物理多屏热插拔。显示动作不改配置、不新增run所有者；完整可访问性归F8。[最终证据](verification/i2-j1-final-20261101/README.md)。 |
| **J2 编辑覆盖与几何往返** | 原M3余项；空白创建与无已有配置文件输入、NIST元素来源辅助、命名多源及球面源、物理模块组合/替换、多敏感体编辑和高级实体/场/偏置；后端vis属性往返 | E6；实体能力归一相关部分依赖E7，其余不被无关实体重构阻塞；在L1前完成本轮明确范围 | 2026-11-02 **本轮约定范围完成**：空白/高级编辑/往返/资源闭包及接口回归，2ec完整矩阵/严格门禁/独审通过；E7仅既有15/7元数据范围。旧失败原件、实验性/物理界限不提高，见[最终证据](verification/j2-f8-final-20261102/README.md) |
| **J3 现有界面视觉改造与皮肤扩展** | 现有 B/K/C 的主要区域区分、排版与状态辨认，以及三套新增 Qt 皮肤、浅深偏好兼容与可读性 | J1/F8 和 D 盘主题响应基线；可与 F2 分线 | **2026-11-04本轮范围验收完成（带证据限制）**：冻结92134da0，主审本机49/77/33矩阵、云12报告696/247580、Windows实际125/150和Linux独立X11/恢复/退出通过；N1、原P2及恢复布局反例关闭。约一秒切换、旧图身份/非逐页八态及WSLg限制按原事实保留。[最终验收](verification/j3-final-20261104/README.md) |
| **K1 可信实验工作流与配置导出** | 统一 inspect/validate/apply/generate/run/evaluate/export，四层验证、输入身份、可移植配置/资源/证据包 | 2C、E6、F1、F4、F5、I1 | **已完成阶段验收**：第七产品 `2914b39` 的 Windows182/182、57181 v3入口与官方CI548/548、133720入口按原身份保留；P1及永久回归P2经独审关闭，`5644e1e` 新单例Windows36/Linux33通过严格门禁。已正常快进集成并推送至 `codex`。[最终证据](verification/k1-final-20261031/README.md) |
| **K2 独立 Geant4 工程导出** | 目标 3 的源码部分；可审阅 C++/CMake、配置/资源/许可、扩展点和构建说明；脱离工具可继续开发 | K1、I2；当前支持子集即可，不依赖所有 H 项 | 导出模板/manifest → 生成与构建 → 两平台干净环境构建/运行/二次修改；不能只附 INI 或依赖工具安装目录  2026-11-07固定范围带限制验收关闭：S-A/S-B独立工程、双平台运行及受控修改已独核；四云与12原报告734用例376754断言严格通过，双平台1.0.0安装通过，K2-3限制保留。见[最终验收](verification/k2-final-20261107/README.md)；K2后按用户决定暂停，等待整体架构优化计划，不自动进入L2。 |
| **L1 配置 Agent 与模型接入** | 目标4首版及目标5基础；既有字段白名单、模型接口、结构化差异、授权动作与历史证据 | K1、I1；J1/J2/F8本轮既有范围 | **2026-11-02 本轮约定范围验收完成**：冻结246e4f6；Windows六profile308/183347、CI十二报告662/228978，安装Windows一次授权重试后成功、原失败保留；新Windows125/150受限观察，WSLg：独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留。真实云／人工单对／恢复按EE原身份沿用，不宣称通用模型质量、提速或科学验证。[最终证据](verification/l1-final-20261102/README.md) |
| **L2 代码 Agent 与持久工作流** | 目标 4 高级部分及目标 5 完整整合；隔离工程代码差异、编译、运行、日志诊断、有限修复、用户确认与导出 | L1、K2 | 隔离执行 → checkpoint/进程身份 → 有限重试与审阅 → 故障恢复和不重复执行验收。届时评估 LangGraph 薄编排层，不绑定领域模型 |

价值判断和详细边界仍见 [五项目标提案](collab/inbox/20261029-1140-astra-product-roadmap.md)，前端依据见 [DeepSeek 建议及 Astra 纠偏](collab/outbox/20261029-1135-deepseek-workspace-design.md)。本次只是正式编号，不新增安装器、GUI 或 Agent 实现。

#### 原 H 余项与科研验收

| 代号 | 范围 | 依赖与关闭条件 | 排期 |
| --- | --- | --- | --- |
| **H2** | 体积/网格粒子与能量过滤、能谱 | Q1/Q2；先复用 A2 已有过滤，验证互斥分量求和、记录位置、单位与真实能谱 | 科研效率波次 |
| **H3** | 平行世界计分 | Q2/H2；计分几何不改变质量世界输运，对无扰动对照 | 科研效率波次 |
| **H4** | importance、weight windows 等方差降低 | Q2 的现有加权统计/analog 基线；独立均值、误差、FOM 对照；不能以挂接成功关闭 | 高级科研默认第一项 |
| **H5** | 光学过程、材料/表面、光子计数 | 光产额、Birks、Cherenkov、表面效率分别验收；有独立公式/参考 | H4 后，独立需求可调整 |
| **H6** | 活化与热中子 | 核数据版本、时间窗、温度条件；Bateman/受控热谱对照 | H5 后 |
| **H8** | 规则体素模板、材料映射与限定混合建模；[参考规划](#h8-reference-plan) | 坐标/材料/质量与空间计分、精确几何对照、分辨率收敛及资源测量；自适应/DICOM 为可选扩展 | H6 后；本次仅细化规划，尚未实现/验收 |
| **H7** | 局域 Geant4-DNA/径迹结构 | 粒子、能区、材料、region 模型边界；官方样例作回归，独立参考另列 | H8 后 |
| **H9** | INI 定义通用直方图/ntuple | F1 输出版本契约，现有 writer 兼容和原始记录独立重算 | 保留原候选顺序最后，不因“统一”批量重写 |

每项仍是完整阶段，按配置→校验→运行→GUI边界→真实测试→文档交付。Q2 与 H4 职责不同：前者验证已有计分/XS 偏置，后者引入新的方差降低算法。

<a id="h8-reference-plan"></a>

#### H8 参考规划：规则体素模板、混合建模与自适应研究

**规划性质（2026-11-04）：**本节将“用大小方块搭建材料模型”的讨论整理为 H8 的设计参考，尚未实现或验收，不是立即开工指令。H8 默认仍排 H6 后，不调整当前 F2 工作；阶段状态只在本文件维护。正式范围以规则体素及材料映射为主，包含与精确几何共存的限定案例；八叉树、多分辨率和 DICOM 分别作为后续可选研究，不作为 H8 基础交付的前置条件。

##### 目标与适用范围

- 提供一种可选的体素建模模板：通过三维材料标签、尺寸及位置生成几何，复用既有材料、运行、计分和实验包链路。优先解决不规则材料分布、已有切片/三维标签数据以及局部复杂封装的建模问题。
- 面向通用几何，同时准备 SiP/半导体局部案例。规则封装、层状芯片和细薄结构仍可直接使用精确几何；体素不是新的默认几何引擎，也不替代 `layered_device`、`hierarchical` 等模板。
- 先回答“能否正确表示、稳定计分、独立复现”，再回答“是否省资源”。方块数减少、文件变小或预览更流畅，都不能单独证明输运更快。
- 首版不包含完整 DICOM/CT 分割、灰度到材料或密度的自动标定、任意 CAD 自动体素化、运行中自动细化、GPU 粒子输运、医学剂量认证或完整 SEU/SEE 预测。二维图像不能自行补出真实厚度和材料；所有人工补充假设须随模型保存。

##### 已有基础与实现边界

本次只读核对基线为 `513117f3b7d37c687e1aabc6797e7b02d8a71436`，主工作区当时分支为 `roadmap/F2-controlled-session`。实施时必须重新核对，以下不是冻结的开工版本。

- [VolumeBuilder](../src/Geometry/VolumeBuilder.cc) 已有参数化复制路径，可用于理解项目对象构建和生命周期；`CopyTableParameterisation` 当前实现位置/旋转和材料，未覆写逐副本尺寸计算，不能当作自适应尺寸后端。[TemplateFactory](../src/Templates/TemplateFactory.cc) 尚无 voxel/phantom 注册；现有能力也不等于大规模体素导入和计分索引已经齐备。
- [DoseContext](../include/Scoring/DoseContext.hh) 从 pre-step touchable 读取完整祖先路径及各层 copy number，通过 `GetMass(true,false,preStepMaterial)` 求质量，并在无 daughter 时取 solid 体积供 Fluence 使用。现有 Dose 路径身份不能简化为“只有一个 copyNo”；体素接入仍须验证参数化副本的实际尺寸、材料、质量与缓存行为。
- [ScoringManager](../src/Scoring/ScoringManager.cc) 使用单步沉积和上述上下文；[OutputRecord](../include/Output/OutputRecord.hh) 的 `doseVolumePath` 是内部计分上下文，当前 hits CSV 不直接导出它。已有整事件 `event_edep` 也不等于逐灵敏区的事件谱。H8 需要显式体素/ROI 身份与输出契约，不能只依赖 `volumeName`。
- 未发现已接入的 H8 体素后端。因此下文“同材料跨格错归属”等是必须防范的集成风险，不能写成已经在现有体素功能中复现的缺陷。

##### 三种路线及选择依据

| 路线 | 可以借鉴的内容 | 限制与 H8 决策 |
| --- | --- | --- |
| ICRP110 嵌套参数化 | 官方示例使用 X/Y 复制与 Z 参数化，按三维编号查材料；规则长方体三边可不同 | 固定网格，不是八叉树。可作为学习原型和基线；嵌套 touchable depth 与展平编号必须显式转换 |
| `G4PhantomParameterisation` 规则导航 | 适合大量等尺寸长方体，DICOM 示例有材料映射与计分经验 | 必须完整填满容器；默认策略、接口和性能以实际 Geant4 版本核实。初版显式关闭同材料跳边界，先建立空间计分基线 |
| 可变尺寸叶块/八叉树 | 均匀区保留大块，边界、细节与重点区域保留细块 | 是独立的数据结构和几何后端研究；不能把叶块数组直接传给规则 phantom。需另外验证导航、质量、线程安全、索引与资源收益 |

在 H8-0 用同一小模型比较前两条路线，再固定一个正式首版后端；无需同时维护两个生产实现。Geant4 自身的 smart voxel 导航优化不等于用户模型已经有多分辨率体素。

##### 建议的数据与坐标契约

下表是待 H8-0 冻结的设计字段，不是目前可运行的配置语法；不得把示意字段直接加入 GUI writer 或宣称已经支持。

| 项目 | 首版建议 |
| --- | --- |
| 容器与格式 | 一个带独立格式版本的描述文件，加一个材料标签文件；主配置只引用它。沿用项目 INI/路径诊断基础，确切 section/key 在原型后确定 |
| 维数与间距 | `nx, ny, nz` 为正整数；`dx, dy, dz` 为有限正数，明确长度单位。间距是完整格长，不能与 Geant4 half-length 混用；允许各向异性的长方体 |
| 原点与方向 | 原点定义为整个网格局部坐标的最小角；首版固定右手 X/Y/Z、正轴增长，使用显式平移放置。旋转/方向矩阵是另行决定的扩展，不静默转置或镜像输入 |
| 索引 | 零起始 `(i,j,k)`，X 最快：`q = i + nx * (j + ny * k)`；格心为 `origin + ((i+0.5)dx,(j+0.5)dy,(k+0.5)dz)`。底层 copy 编号和 touchable depth 由后端适配，不暴露为唯一数据身份 |
| 标签编码 | 学习原型可用小型文本标签；正式候选为 `uint16`、小端二进制，精确长度 `2 * nx * ny * nz` 字节，不带隐藏头部。规模上限、乘积溢出和 Geant4 整数接口上限须预检；扩展位宽要显式版本/类型 |
| 材料映射 | 每个出现的标签都显式映射到已校验材料；0 也必须定义，不能默认代表空气。初版同标签固定材料与密度；不按标签自动混合、不从颜色推材料、不忽略未知标签 |
| ROI 与物理分区 | 材料标签、计分 ROI/灵敏体身份、物理 region/cut 是不同概念。可选 ROI 数据必须与标签网格同形状，或用明确的索引集合描述；ROI 不能暗中改变材料或生产阈值 |
| 稳定身份 | `grid_id + (i,j,k)` 及独立 ROI ID；将数据哈希、格式版本和几何变换随输出保存。更换后端不能使同一格身份改变；自适应 leaf ID 与规则格映射另有契约 |
| 资源与搬迁 | 相对路径按描述文件目录解析；导入既有 K1 包时登记标签、材料与 ROI 的实际读取字节哈希，复用资源路径/搬迁校验。不得只保存原机器绝对路径 |

先提供自制、可重新生成的 `10×10×10` 材料积木样例，以及 `3×4×5`、三轴间距不同且角点标签不同的非对称样例。后者专门检测轴交换、展平次序、偏移半格和镜像。完整 ICRP 人体数据不作为默认构建或测试依赖；第三方数据的取得、使用与再分发条件独立核对。

##### 几何、混合建模与计分

1. **规则几何先完整闭合。**预检尺寸、标签、映射及预计资源，在创建大量 Geant4 对象前报错。体素容器应无缝填满；用解析包围盒、总体积/分材料质量、边界穿越和真实 overlap/navigation 检查共同验证，不能仅凭预览看起来正确。
2. **混合建模先采用不重叠分区。**将精确薄层、互连和灵敏体放在明确的精确区域，体素容器覆盖其余可独立划分的区域；规则容器内不能叠加同位置的精确物质。项目 [GeometryManager](../src/Geometry/GeometryManager.cc) 已要求 parameterised volume 不与其他子体积共用母体，应使用独立容器。Geant4 对不同尺寸/形状的参数化副本不支持子体积，不能默认在任意八叉树叶块中再塞精确芯片。复杂嵌入、挖孔或局部替换留给单独原型；不通过全局增大 overlap 容差隐藏问题。
3. **区分材料分辨率与计分分辨率。**为获得细剂量图，不一定需要把同材料几何细分；H3 平行世界/计分网格是独立路线，不能在 H8 中悄悄实现或当成已可用。预览降采样也不能修改真实输运几何。
4. **同材料边界策略显式记录。**规则导航可能让一步跨多个同材料体素；若仍将整步 `edep` 和质量归到 pre-step 单一路径，会损坏空间分布，即使总能量看似正确。首版若使用 phantom 后端，应显式设置并验证 `SetSkipEqualMaterials(false)`；嵌套后端也要以实际步记录验证边界行为。
5. **分步分配是后续优化。**可研究官方 `G4ScoreSplittingProcess` / `G4EnergySplitter`，但必须检查与本项目 SD、SteppingAction 和自定义 scorer 的调用关系，防漏计/重复计。按步长平均分摊是近似，不能冒充真实沉积位置。加入跨多个同材料格、跨材料界面、斜射、格角、零沉积步和 SD/Step 两条计分路径的反例；所有开放的 track length/Fluence、NIEL/DDD、LET 和权重计分也须分别验证，不能仅凭 Edep 修正通过就开放其余 scorer。
6. **输出定义先于实现。**最低限度明确每格/ROI 的沉积能量、质量、剂量、单位、run/event/worker 身份、零沉积与未采样含义、文件生成条件和合并规则。剂量按该计分域总沉积能量除以实际质量计算，ROI 剂量不是各格剂量的简单平均。线程本地累加、合并顺序、事件数及不确定度算法沿用经核实的统计契约。
7. **保留半导体关心的事件结构。**首版基准优先采用 analog 输运；逐 ROI 保存/汇总事件沉积，零沉积事件也有明确分母。若引入偏置权重，须另验统计估计量，不把加权条目当未加权事件概率。阈值超过事件只是所定义响应模型的统计量，不自动等于真实 SEU 截面；电荷收集、灵敏体尺寸、阈值及器件验证归独立模型。

##### GUI、预览与失败处理

- GUI 提供模板选择、描述文件与标签导入、三轴尺寸/间距/原点、材料映射表、ROI/统计摘要及输入哈希；先只读展示不支持的字段，禁止静默改写为另一个模型。功能只有预览时须明确标为预览并阻止生成可运行包。
- 默认二维正交切片，显示轴向、坐标、材料图例、ROI 与物理长度；按需显示外表面、裁剪区域或选定切片的三维预览。不得为每个体素创建一个 GUI 对象。大数据读取/切片异步、可取消，变更输入后废弃旧任务结果。
- 未知格式、缺失/多余字节、越界标签、非有限数、重复映射、非法轴向、ROI 形状不符、输入在校验后变化，以及无法满足内存/输出预算，均须停止并给出文件/字段/标签位置和修复建议；不自动填空气、不裁掉薄层、不自动降精度。
- 资源预算不仅估算标签数组，还包括 ROI、运行时几何/导航、每 worker 计分和预览/转换临时内存；报告预计值与实测值，具体限额由基准决定。取消/失败只清理任务自身临时产物，保留源数据与失败证据。
- 初始化后更改几何采用新进程；复用当前生命周期守卫，不以 H8 名义开放未经验证的热重建。对不支持的 biasing/region/field 组合明确拒绝并给出替代路径。

##### 分阶段实践与依赖

以下是 H8 内部交付步骤，不是新的独立进度台账；各步结果回填本节及既有验收入口。

| 步骤 | 实践内容与产物 | 进入下一步的依据 |
| --- | --- | --- |
| H8-0：学习与小原型 | 读 ICRP110 与 DICOM 相关源码；使用同一合成标签比较嵌套/规则 phantom；建立索引、质量和单步边界观察，冻结格式与后端选型说明 | 非对称模型坐标/材料正确；边界计分策略明确；没有把小原型称为正式支持 |
| H8-1：规则模板完整链路 | 接入配置/校验、材料构建、几何、稳定身份、计分输出、CLI/宏能力边界、EffectiveConfig、GUI 导入/切片、K1 资源包与文档 | 正反例与真实后端/GUI smoke 通过；未知输入拒绝，单/多线程与多 run 不串数据；旧模板回归保持 |
| H8-2：实际案例与有限范围验收 | 均匀水模、分层硅/铜/封装材料、一个来源清楚的 SiP 局部；精确几何与规则体素对照，至少一个无重叠混合模型；分辨率收敛及资源报告 | 软件一致性、物理参考、性能三类证据分别呈现；公开适用域、局限和未过项目；以此评估 H8 基础范围关闭 |
| H8-R：自适应可行性研究（可选） | 同一细规则标签离线合并为粗块/八叉树，再对照精确与细规则模型；研究转换器、叶块后端和身份映射 | 先满足几何/计分与误差条件，再判断内存、初始化和运行收益；无收益时保留规则后端，不拖住基础交付 |

技术上复用 Q1 的失败与证据规范、2C 的来源/应用收据、E6/E7 的配置与几何能力声明、F1 的输出契约、K1 的资源闭包和现有 GUI 工作区。Q2 为科学比较提供方法和独立参考，F3 为资源测量提供方法；不因排期顺序把无关 H4/H5/H6 功能写成代码硬依赖。H3 仅在以后采用独立计分几何时成为对应方案依赖。开发完成后同步支持矩阵、中文几何说明、相关 Agent 约束与示例，本次参考规划不提前改成“支持”。

##### 自适应算法的具体研究路径

- **先无损合并，再谈近似。**以规则标签为真值，将 8 个兄弟块仅在材料及密度、ROI/敏感标签、物理 region/cut/场等必须保持的属性完全一致时合并；保持材料与语义标签的空间分布。去掉内部边界仍可能改变步分段与随机历史，不要求逐事件结果完全相同。不能跨 ROI 边界合并，也不能把相同颜色当成相同物理属性。是否在既有 Geant4 层级中可表达这些属性仍须后端验证。
- **八叉树是候选，不是硬性目标。**每层将三轴各二分；记录根盒、叶块位置/尺寸、最大深度与最小尺寸、稳定 ID 和原网格映射。非二次幂尺寸须明确补齐与裁切，不得默默新增空气层改变模型。各向异性薄层可比较分块长方体或 k-d 划分，避免为追求正方体过度细分。
- **薄结构与界面受保护。**从表面/CAD 转换时使用保守的表面—体素相交判定，不能仅采样方块中心；禁止把多个材料混为一个未验证的等效材料。已有标签若已漏掉薄层，八叉树不能恢复它。精确几何的保护区、最小层厚和几何误差要求必须来自案例需求。
- **按误差与资源共同停止。**材料同质、保护标签一致且达到几何/计分约束才允许粗化；2:1 邻接平衡、Morton 编码、稀疏分块/RLE 可作为存储或遍历优化候选，不是物理精度保证。首版不按运行中的粒子轨迹改变网格；若以后用独立 pilot 结果确定网格，应冻结网格并用独立 production 统计验证，记录选择偏差风险。
- **区分三层收益。**离线体素化/压缩速度、数据/预览内存、Geant4 初始化与输运速度分别计量。GPU 体素化论文只能支持转换算法研究，不能推导本项目的 Geant4 输运一定加速。

##### 验收矩阵与判断方法

| 验证层 | 必做对照/反例 | 合格判据如何确定 |
| --- | --- | --- |
| 格式与身份 | 小积木、非对称网格、非法/截断/超长文件、溢出尺寸、缺材料、ROI 错形；后端编号与稳定格 ID 双向映射 | 离散标签与索引精确一致；长度/体积误差依据浮点和几何容差事先定义，不能事后放宽 |
| 几何与材料 | 包围盒、各材料体积/质量、边界薄层、容器填充、混合区不重叠、边角穿越 | 与解析模型/原标签独立重算一致；记录有限抽样 overlap 检查的覆盖限制 |
| 空间计分 | 同材料多格、材料界面、ROI 边界、参数化实际质量、SD/Step、单/多线程与多 run | 格/ROI 沉积合计与独立记录一致；能识别“总量正确但空间归属错误”；没有漏计/重复计或身份冲突 |
| 几何离散化 | 精确水模与体素水模同坐标深度剂量；分层模型多个网格间距；SiP 局部精确/规则/混合对照 | 固定物理、源、cuts、计分域及事件预算；报告偏差及 Monte Carlo 不确定度、收敛趋势，不能只比较一条曲线或单 seed |
| 半导体关注量 | 各层与各灵敏 ROI 的逐事件能谱、零沉积占比、预先定义阈值的尾部事件 | 按预先选定分布/区间方法与样本量评估；稀有尾部统计不足就记未确定，不能用平均剂量一致替代 |
| 独立物理验证 | 可公开复现的论文/实验或独立解析参考；记录数据来源、材料/尺寸假设、物理列表及版本适用域 | 精确/体素在同一 Geant4 的相互一致只是软件/离散化验证，不是独立物理正确性；没有适配数据时明确未验证 |
| 工程资源与交付 | 同机同构建/版本/线程，精确与细规则两路；自适应对照仅在 H8-R 加入，不阻塞基础范围；冷启动与重复运行分开 | 记录转换、I/O、初始化、峰值内存、events/s、输出大小和预览耗时；至少多次重复并报告波动。性能目标开测前冻结，不承诺任意百分比 |

数值容差、目标能区/粒子、统计事件数和资源预算在 H8-0/H8-2 开测前按真实案例冻结。阶段关闭需要可复现输入、实际完成事件数、源码/数据哈希、失败记录、适用平台证据及局限说明；不以退出码 0、单张图、方块数减少或与同源结果接近替代验收。

##### 未决事项与建议的首次实验

1. 正式后端选嵌套参数化还是 `G4PhantomParameterisation`；以小样例的计分可解释性与真实内存/速度决定。项目支持的每个 Geant4 版本须查头文件，不能照抄开发版网页中的旧 API 名称。
2. 描述文件的精确 schema、首版数据规模上限、ROI 存储方式、逐体素/逐 ROI 输出是否默认关闭，以及如何避免完整 event×voxel 稠密输出；须在兼容现有 F1/K1 契约的条件下确定。
3. 第一件真实 SiP 局部模型的尺寸、材料来源、薄层/灵敏区及待回答的问题；没有真实数据时只做标明假设的合成模型，不包装成器件预测。
4. 自适应是否值得进入正式路线：需先有“固定细网格资源确实成为瓶颈”的测量，且在同等误差要求下有收益。DICOM、旋转网格、精确嵌入与高级自适应另行定范围。

建议首次实验只做“空气/硅/铜的规则标签积木 → 两种参数化原型 → 非对称索引/质量核对 → 同材料跨格计分反例”，随后复现均匀水模深度剂量和分层芯片。完成这条链再扩充 GUI 和真实大模型；学习所得、失败案例及后端选型理由都保留为工程参考。

##### 主要来源与证据边界

- [Geant4 ICRP110 官方示例说明](https://geant4.web.cern.ch/docs/advanced_examples_doc/example_ICRP110Phantom)与[嵌套构建源码（v11.4.3）](https://github.com/Geant4/geant4/blob/v11.4.3/examples/advanced/ICRP110_HumanPhantoms/src/ICRP110PhantomConstruction.cc)：用于学习规则人体体素组织，不能推导已有自适应网格或半导体有效性。
- [规则导航说明](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/Geometry/geomNav.html#fast-navigation-in-regular-patterned-geometries-and-phantoms)、[`G4PhantomParameterisation` 头文件（v11.4.3）](https://github.com/Geant4/geant4/blob/v11.4.3/source/geometry/navigation/include/G4PhantomParameterisation.hh)及[DICOM1 计分说明（v11.4.3）](https://github.com/Geant4/geant4/blob/v11.4.3/examples/extended/medical/DICOM/DICOM1/README.md)：说明规则填充、同材料跳边界和分步计分问题；实际行为按目标版本源码及运行复核。
- [参数化物理体积限制](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/Geometry/geomPhysical.html#parameterised-volumes)：约束混合几何的层级设计；不能把参数化当作任意几何嵌入机制。
- [Schwarz 与 Seidel，Fast Parallel Surface and Solid Voxelization on GPUs（2010）](https://michael-schwarz.com/research/publ/2010/vox/)：保守体素化与稀疏八叉树的原始算法参考，其图形学/GPU 结果不代表本项目粒子输运性能。
- [ICRP110 示例 README](https://github.com/Geant4/geant4/blob/v11.4.3/examples/advanced/ICRP110_HumanPhantoms/README)与[ICRP Publication 110](https://www.icrp.org/publication.asp?id=ICRP%20Publication%20110)：数据下载和使用条件另行确认，不默认授权随本项目再分发。

#### 其他旧目标的归属，避免漏项或重复计数

| 旧目标/遗漏项 | 当前正式归属 | 保留边界 |
| --- | --- | --- |
| **M0 真实性与契约总验收** | Q1 + 2C + E6/E7 + F1 + K1 + I1/I2 的相关基础验收 | 是汇总里程碑，不再重复实现一套代码；不能因任何单项通过就关闭 M0 |
| **M1 后端已声明能力** | 已有 A4–A7 等实现经 Q1 复核；新增能力走 H 或独立需求 | assembly、材料温压、安全几何热重建等继续明确拒绝/受限。现有明确未支持项不自动变为 Q1 必须新增的功能 |
| **M2 物理计分总验收** | Q1 修正已有错误，Q2 完成独立验证；H 扩展各自验收 | LET/Dose/Fluence/DDD 已有实现，不能照抄旧“未实现”状态；限定验证域与实验性等级保持 |
| **M3 GUI 总验收** | F4/F5/F8、J1/J2、K1 的编辑/运行/结果链路 | GUI 布局自由不等于高级参数已可编辑；296 个无编辑路径字段不是必须一次全开放的承诺 |
| **M4 测试与交付总验收** | Q1、I2 及每阶段干净检出/CI/分发节点 | 旧安装包、历史 Linux CI 不代表新源码版本的验收；Windows 11.4/真实桌面/ROOT/打包仍需证据 |
| **M5 扩展生态** | 保留 **M5** 整阶段代码，排高级生态波次 | 已有可信 Python 后处理 registry；后续范围含 API 兼容、第三方扩展生命周期与管理。C++ 内核插件/隔离另给设计，Agent provider 不等于插件系统 |
| 主 INI schema_version、几何自动迁移与诊断去重 | **E6**；编辑器无损往返由 **J2** 消费 | 不将几何 `version=2` 当作主 INI 已版本化；源文件默认不被迁移覆盖 |
| 非 csh UI、嵌套/动态命令、并发/取消/关窗、原生 GPS 的证据盲区 | **Q1** 审计现有入口并修复或明确阻断不支持路径；**2C/F2/K1** 扩展相应可观察能力 | 不为了审查完成而声称支持任意原生命令或安全热重载 |
| 微电子/可选 3D/ROOT 等依赖、旧版本、签名与诊断包 | **I1/I2** 的支持矩阵与分发 | Geant4 11.2、代码签名证书、DICOM 或真实实验数据属于条件性范围；缺输入如实记录，不伪造完成 |

来源索引：[长期路线图](开发路线图.md) 的 M0–M5 目标和 §3、[接续计划](开发接续计划.md) 的 F/H 与版本兼容要求、[2C 消费者清单](EffectiveConfig.md)、[历史审计对照](collab/outbox/20261028-0120-deepseek-legacy-audit-crosscheck.md)、[M5 原型边界](输出扩展原型说明.md)。历史对照将 SolidRegistry 放在 2B 的旧归属，由本表明确改归 E7；不是重开已验收的 2B。

#### Q1：由本对话负责完整审查与修复

**决定：采用本对话主导的全链路工作方式。** Astra 负责范围、科学口径、问题裁决和最终验收；Sol 等子代理按不重叠模块审查/实现，并由不同审查者复核修复；DeepSeek 参与 GUI 可用性/前端实现，不能独自判定物理正确。隔壁作为可选独立审查来源，不是本对话启动/继续修复的前置条件；本次不会擅自停止或改写隔壁任务。

采用“模块审查→反例→修复→针对性回归→独立复核”的滚动推进，最后完成整体冻结验收。R01–R32 已闭合，九域覆盖及边界见 [关闭复核](collab/reviews/20261029-q1-closure-review.md)。V-01 保留估计量及小样本语义，V-02 明确 max_step 粒子范围，没有调整默认物理贴合结果；A7/物理及新增偏置、随机、多run回归均已在当前Windows与Linux双版本执行。邻线旧反例按真实基线复用，未等待邻线全部审完。

| 审查域 | 必须检查的边界 | 当前覆盖说明 |
| --- | --- | --- |
| 启动/配置/命令 | CLI/INI/macro优先级、空值/单位/非有限、重复/未知字段、失败传播和来源 | R01/R09/R13/R26/R30/R32及对应正式回归通过；未审计的动态派发与非csh执行明确拒绝 |
| 材料/几何/SD | 真实材料与尺寸、母子/布尔/STL/GDML/复制/参数化、名称身份、region、SD绑定 | R03/R04/R09/R15/R23/R24闭合；对象/路径身份、回调失败与往返回归通过，实验等级保持 |
| 粒子源 | GPS高级分布、多源/离子/相空间、事件与初级粒子数、权重、真实顶点 | R12/R13、真实初级顶点及动态入口回归通过；未新增高级GUI源编辑器 |
| 物理/场/偏置 | process/region/limits、场线程对象、operator挂接及拒绝边界 | R08/R14/R25/R29闭合；worker真实算符/收据与原生scorer同run对照通过；独立无偏性及FOM仍归Q2 |
| 计分/统计 | Edep/Dose/Fluence/LET/DDD、零贡献、权重/溢出、事件分组、误差/协方差 | R03/R05–R07/R10/R11/R29及1/2/4worker风险回归通过；V01方法范围保持，不宣称覆盖率已验证 |
| 运行与 MT 生命周期 | Build/Begin/End/finalize、共享失败、跨run、随机/线程协议、资源释放 | R23/R25/R26/R30闭合；多run及随机语义真实回归、Windows取消/关窗与自有进程清理通过 |
| 输出与后处理 | CSV/ROOT/JSON、计数/单位/版本、worker合并、缺失/陈旧/写失败、部分产物 | R02/R06/R07/R27闭合；manifest自动来源/搬移/执行前复核及旧格式路径通过；不宣称内容签名 |
| GUI 全链路 | 保存/加载、writer、inspect/QProcess、竞态、取消/关窗、进度/结果/绘图/i18n | R16–R22及R27闭合，DeepSeek参与复核；冻结Windows真实保存/生成/20events运行/取消/关窗/结果通过 |
| 构建/平台/测试可信度 | 干净检出、源码/测试/exe指纹、依赖/路径、真实CI、断言质量与负向门禁 | R28/R31闭合；Windows105、Linux11.3.2/11.4.3各105、CI12报告和篡改负向门禁通过；同v3旧98基线逐例/总数门禁通过 |

Q1 关闭门槛：上述每域有明确范围、审查者、基线与证据；冻结范围内确认的程序缺陷已修并独立复核，已知结果错误/漏计分/假成功不能延期；V-01 的方法口径和 V-02 的适用范围均与文档一致；新反例进入正式回归，不能只复跑旧测试；当前支持矩阵内 Release、全量测试、无 FAIL/SKIP、非零断言与严格证据门禁通过，并完成 Windows/Linux 当前源码复核。声明未支持的新能力不要求在 Q1 新增，但已有入口必须拒绝或如实标明边界。

Q1 的冻结验证矩阵如下；它复用已有构建路径，不要求先完成 I2 安装器：

| 平台/版本 | Q1 必须取得的新代码证据 | 不从本行推断的能力 |
| --- | --- | --- |
| 本机 Windows / 现有 MSVC / Geant4 11.3.2，MT + GDML | 干净检出 Release、static/GUI-offscreen/backend/integration、CSV/ROOT/JSON、1/2/4 worker 及多 run 风险病例；Windows 实际窗口中的保存/生成/运行/取消/关窗/结果关键流程 | Windows 11.4、未建的纯 sequential Geant4、所有显示器/DPI/无依赖安装包 |
| Ubuntu 24.04 / Geant4 11.3.2，现有 CI 依赖方案 | 相同源码与测试指纹下四 profile、相应输出/GDML能力、严格门禁、真实 CI run/提交及负向证据 | 原生 Linux 桌面交互、桌面安装器、多屏与发行版通配 |
| Ubuntu 24.04 / Geant4 11.4.3，现有 CI 版本矩阵 | 当前代码四 profile、版本相关数据定位/物理过程与现有输出回归、严格门禁、真实 CI run/提交 | Windows 11.4、11.4 桌面/安装体验及所有物理结论自动迁移 |

依赖/可选组件必须记录实际能力与软件版本；若冻结矩阵某格不可运行，保留未验状态，Q1 不冒称全矩阵通过。I2 再扩展 Windows 11.4、原生 Linux 桌面、包内 ROOT/Python 辅助工具、干净安装/卸载和版本支持选择。历史 CI 绿、offscreen GUI 通过均不能代替对应新证据。

若某项因环境/外部数据未能验证，必须逐项登记且不称该范围已验收；不能为关闭 Q1 把已发现缺陷悄悄改名为下一阶段。确需延期或改变冻结范围时单独说明原因及影响。Q1 结束仅表示这一代码基线和约定范围的审查闭合，不保证以后没有新缺陷；后续各阶段仍沿相同修复规则处理新问题。

#### 提交与集成节点（适用于每个完整代号）

| 节点 | 提交内容与命名示例 | 进入条件/作用 |
| --- | --- | --- |
| 范围与契约 | `docs(Q1): define audit coverage` / `docs(K2): define standalone export contract` | 冻结范围、文件责任、兼容边界、反例/判据；复杂物理决策先落文档。已有充分提案可复用 |
| 可运行实现 | `fix(Q1): correct R-03 dose mass` / `feat(I1): detect runtime environments` | 一个缺陷或一个自洽端到端能力一个提交；相关回归与接口文档同交，专项通过。内部可有多个提交，不等待用户逐个批准 |
| 整项验收 | `test(Q1): archive complete verification` / `test(J1): verify workspace recovery` | 冻结代码、完整适用平台回归、GUI真实路径/物理基准按范围执行；报告、日志、指纹归档，清楚说明未验证项 |
| 集成交付 | `docs(Q1): close audited baseline`，记录实现/证据/集成 SHA | 核对隔离与集成分支 HEAD/dirty/并发审查；独立复核后正常合并/快进与授权范围内普通推送。CI须对应实际提交；旧报告不能为变动后的源码背书 |

提交示例是主题模板，不是假造已存在 SHA。可以合并紧密相关的文档/测试提交，避免空提交；源码实现与验收证据须可追溯。默认不提交红色的正式测试；确需保留修前失败，保留诊断夹具/日志，修复与正式反例一起进入可运行提交。纯计划文档只做链接/路径与相应静态检查，不机械重跑整套 Geant4。

Q1 已存节点：修前证据d286577、R01/R02 f9930aa；5c6da6d（几何/材料）、529b5de（场/源）、f6e1302（数值/SD）、d3f37af（GUI/后处理）；后续4ed7233（执行生命周期）、cb54669（结果来源）、5ffe9b6（探针/测试）、8ecad66（绘图来源夹具）。最终验收8ecad66：Windows105/105、83770个v3入口；同v3旧98基线79303，逐例/总数未下降；Linux run40855144863两版本各105，M0 run40855144672两OS各42，Windows实窗通过。原失败记录保留，详见 [最终报告](verification/q1-final-20261029/README.md)。该Q1验收不包含完整2C；2C后续独立验收见最终报告，其他阶段保持各自状态。

当前继续使用已存在的隔离分支，不移动或重写其历史；后续整项按仓库约定使用 `roadmap/<代号>-<主题>`，优先复用合适 worktree。同一文件一个写者，完整回归期间冻结源码/测试。整项完成后才登记关闭；一个补丁或一个平台过关不等于阶段关闭。安装包/对外发布与源码集成另分节点，当前旧 1.0 包不作为新代码交付物。

### 旧 Order of work（2026-10-23 历史）

1. E1 (unblocks the 3D view) → 2. G1 → 3. G2 + G3 → 4. E5 (before more GUI work) →
5. H1 → G6 → 6. G4 + G5 → 7. E2 (schema; modules migrate over several sessions) →
8. F6 → F2 → 9. F4 + F5 → 10. F7 → 11. H2 → H3 → H4 → H5 → H6 → H8 → H7 → H9 →
12. E3, E4, F1, F3, F8 fit in between when a session is short.

Decisions to ask the user when the item comes up: hosted CI runners (E3), any change of
an output default (F1), which session protocol to expose (F2), and the priority among
H4–H8 if the user's applications favour some of them.

## 开发执行约定

- 每次主线交付一个完整代号；无依赖且文件责任分离的工作可并行。按上文提交节点连续推进，不要求用户逐提交发出“继续”。使用 `roadmap/<代号>-<主题>`，保留已存在的隔离分支。
- 实现提交运行相关专项；整项验收冻结源码并执行相应 Release、真实后端、完整适用平台测试和证据门禁。纯文档变更不重跑不相关物理测试。
- 整项完成后先核对集成分支和并发改动，再正常合并/快进与授权范围内普通推送；在本文件记录提交和实际 CI，更新 `CHANGELOG.md`。存在分叉时不得强行快进或重写他人历史。
- 新功能默认关闭或保持原行为；未完成物理基准的能力在 [功能支持矩阵](功能支持矩阵.md) 标明实验性和验证范围。
- 不强推、不重写历史，不改 `总体判断.md`、`_backup_git_*` 或用户的其他分支。
- 已授权的确定缺陷修复直接推进；改变科研定义、兼容默认值或不可逆发布等需单独裁决时，先完成可审阅提案，再按已有授权判断是否需要用户决定。

## Progress log

- **2026-11-03 J3 整体验收 P2**：整体验收退回并发现状态标签文字对比度不足（B/K/苔原成功文字 4.345/4.345/4.310:1）。`c082eccc` 新增 `theme.veil_text()`/`status_combinations()`，成功/失败/运行中标签改用 `$success_text`/`$danger_text`/`$running_text`（≥4.6:1 且保留色相），基础层与设计层同步；`test_theme_registry` 与 `smoke_theme_response_shell` 增补真实控件采样断言。干净 worktree 冻结 static 49/49（5 687）、GUI 76/76（10 535）、integration 33/33（6 830），审查者探针 15/15 通过；J3 仍未关闭。
- **2026-11-03 J3 独立审查响应**：独立复验不同意关闭 J3（`docs/collab/reviews/20261103-j3-closure-review.md`）。响应修正 i18n 重复 key、紧凑布局与 dock 契约、外观菜单“当前使用/下次使用”、命令面板边框对比度，并新增视觉矩阵（8 皮肤×3 场景 + 面板 + 快捷键表 + 150% 采样）与语义色表；候选冻结基线见 `docs/verification/j3-close-20261103/README.md`。仍缺状态图、Windows 125/150 真实操作记录、Linux 真实桌面与自动化重启用例，J3 保持未关闭。

### 2026-11-03 J3 状态不串改用例

新增 `gui_theme_state`：切换纸墨/午夜蓝/B 后运行名输入、输出文件选中行、当前页面与工作区标签保持不变，外观偏好只进入 QSettings；与四个既有主题用例共 5 例 188 断言通过。证据`docs/verification/j3-visual-checks-20261102/state-preservation/`。运行中任务、K1 资格与Undo 栈仍未覆盖，J3 未关闭。


### 2026-11-03 J3 视觉校验（作者侧）

15 皮肤 × 17 项对比度全部达标；125% 与 1180 逻辑宽 @150% 紧凑布局可用（可选 dock 自动收起、材料编辑器两行网格，最小宽度约 760）；主题切换中位 765.1 ms，父版 752.5 ms（约 1.02×，低于 1.20× 调查线）；WSLg X11/xcb 下纸墨/午夜蓝/中文界面渲染正常，3D 无 pyvista 时给出明确回退说明。证据与边界见 `docs/verification/j3-visual-checks-20261102/README.md`。J3 仍未关闭，Linux 真实桌面与独立复验待做。


- 2026-11-02：J3 第七阶段（作者交付，未验收）。Help 菜单新增 F1 快捷键表与关于对话框，侧栏导航补 tooltip；新增 `gui_help_menu` 用例，5 个 GUI 用例、211 断言通过；证据 `docs/verification/j3-help-20261102/README.md`。
- 2026-11-02：J3 第六阶段（作者交付，未验收）。新增 3D 模型树与体积筛选、双击隔离、右键菜单，并让打开「3D Preview」标签自动绘制几何。7 个 GUI 用例、1965 断言通过；证据 `docs/verification/j3-modeltree-20261102/README.md`。
- 2026-11-02：J3 视觉校验（作者侧，未独立验收）。补 `docs/verification/j3-visual-checks-20261102/`：
  15 皮肤 × 17 项 WCAG 对比度实测全部达标（最低 1.16:1 为侧栏选中指示）；125% 缩放配置页完整；
  150% + 1280 逻辑宽屏幕发现工作区最小宽度（约 1600 逻辑像素）超出屏幕、右侧 3D 面板被裁的
  已知缺陷（未修复）。窗口 < 1400 时启用 `WorkspaceLayout.adapt_to_width()` 与
  `PyVistaPreviewWidget.set_compact()` 收窄面板。125%/150% 结论、Linux 实窗与切换性能基线仍待完成。
- 2026-11-02：J3 第五阶段（作者交付，未验收）。`WorkspacePageStack.reveal_current()` 在离开停靠页时
  隐藏该页 dock，修复配置编辑器在 Run Console / Results / Run History / Parameter Scans 继续占据约 620–700 px
  的问题；导航到 Results 时 `WorkspaceLayout.focus_analysis_view()` 收起 3D 预览与 AI 面板并显示日志 dock。
  7 个 GUI 用例、2022 断言通过（报告 20261102-232214-51bfb1b2），证据
  `docs/verification/j3-analysis-docks-20261102/README.md`。Results 页最终布局与跨平台实窗仍待做。
- 2026-11-02：J3 第四阶段（作者交付，未验收）。新增 `WorkspaceLayout.preset_for_page()` 与
  `focus_current_page()`：Start/Project/Configuration/Scenario/Effective Configuration → `configuration`，
  Run Console → `running`，Results/Run History/Parameter Scans → `analysis`；View → Workspace layout 增加
  “Fit workspace to current page”（`Ctrl+Shift+L`，`workspaceFocusPage`），命令面板 Actions 7→8。7 个 GUI 用例
  通过、399 断言，证据 `docs/verification/j3-focus-20261102/README.md`。仍待对比度实测表、125%/150%、Linux 真实桌面、
  独立审查，J3 未关闭。

- 2026-11-02：J3 第三阶段（作者交付，未验收）。3D 视图面板视点/投影控件改两行网格、图例 190→168、剖切滑块最小宽 80，
  右侧 dock 不再溢出裁剪；3D 预览选项分行；配置 setup 面板最小宽 300、分栏 330/650；配置标签 padding 7/11；
  状态栏“恢复副本”单行（max 320）；`QToolButton:focus` 焦点描边与侧栏 focus 背景；撤消/重做主题色 SVG 图标并在工具栏
  创建后补刷一次。gui profile 72/0/0、10227 断言，门禁通过；证据 `docs/verification/j3-panels-20261102/README.md`。
  对比度数值未复测、125%/150% 与 Linux 桌面待做，不宣称 J3 完成。

- 2026-11-02：J3 第二阶段（作者交付，未验收）。导航分为 `WORKFLOW` 与 `RUN & ANALYZE` 两组并加选中轨道；
  页头加区域面包屑，项目 chip 保持单行；新增 Ctrl+K 命令面板（Pages/Actions/Appearances 分组、标签严格匹配优先、
  Up/Down 跳过组标题、选择外观激活对应明暗组）；状态栏常驻 `Appearance: <皮肤名>`；菜单栏、编辑历史工具条与状态栏改用皮肤浅表面。
  新增 `gui_command_palette` 用例（40 断言），完整 GUI profile 72/72、10227 断言通过。
  区域层级实窗改造、对比度实测、性能与独立复验仍待做，不宣称 J3 完成。详见
  [第二阶段证据](verification/j3-shell-20261102/README.md)。

- 2026-11-02：J3 第一阶段（作者交付，未验收）。外观基础设施落地：`theme.py` 重写为 28 颜色角色 + 15 套皮肤注册表 +
  可访问性下限归一化，样式表拆为历史基座与新视觉层；`View → Appearance` 按明暗分组列出全部皮肤并记忆两组选择，
  `appearance/light_skin`/`dark_skin` 新增、旧 `light_palette` 保留为 B/K 镜像；app.py 启动恢复；新增 static 用例
  `theme_registry`（113 断言点）与 `check` 指示器图标。static 49/49（5,615 断言）、主题相关 GUI 4/4（284 断言）、完整 GUI profile 71/71（10,187 断言）通过，
  证据含 B/K/C 改动前后同工程截图。区域层级实窗改造、对比度实测表、125%/150% 与 Linux 桌面检查、性能基线及独立复验待做，
  不宣称 J3 完成。详见[第一阶段证据](verification/j3-theme-v1-20261102/README.md)。

- 2026-10-29：基于 `f9930aa` 整理统一代号、依赖与提交节点，新增 Q1/Q2、E6/E7、I/J/K/L，并保留 2C、原 E/F/H 和 M0–M5 的完成边界。Q1 改为主对话负责全模块审查、复现、修复和独立验收，隔壁证据按基线复用。本次仅规划文档；未新增代码、未重新完成全面审查。编号交接见 [计划通知](collab/inbox/20261029-1310-astra-plan-codes.md)。

- 2026-10-28：Geant4 11.4 支持与 CI 版本矩阵。`src/Core/Geant4DataLocator.cc` 的数据集表新增 11.4 分支（12 个数据集，
  `G4EMLOW8.8`/`PhotonEvaporation6.1.2`/`RadioactiveDecay6.1.2`/`G4PARTICLEXS4.2`/`G4ENSDFSTATE3.0` 等，前 5 个 required）；
  本机 WSL 11.4.3 实测构建成功、四个 profile 87/87 全过（backend 109,942、static 391、GUI 1,877、integration 4,364 断言），
  构建门槛（Ubuntu 24.04 的 expat/zlib/freetype 都低于 11.4 下限，CMake 需六个 `-D*` 参数）写进
  [Linux构建与验证](Linux构建与验证.md) §8。三个版本相关测试缺陷改为版本无关：数据文件夹从 `--check-geant4-data` 的 discovery 取、
  激发态核名按能级数值容差匹配（11.3 `Ni60[2505.753]` 与 11.4 `Ni60[2505.75300]` 只是格式化差异）。
  `linux-geant4.yml` 加入 `matrix.geant4: ['11.3.2', '11.4.3']`（每版本独立前缀/报告根/artifact，GDML 期望值改问可执行文件 `--capabilities`），
  `6a8b237` 上两个 job 各 26 步全绿（run 40690078563 / 40690070991），同一推送的 M0 workflow 也全绿（run 40690078519 / 40690071129）。
  提交链：`97036df`（数据集表 + 版本无关测试）→ `6a8b237`（CI 矩阵）→ 本轮证据与文档。统一测试平台 87 例 / 116,677 断言，
  证据见 [docs/verification/stage-11d4-20261028](verification/stage-11d4-20261028/README.md)。边界：11.2 未测，Windows + 11.4、
  11.4 下的真实桌面 GUI/ROOT/打包未验证。
- 2026-10-28：阶段 2B（屏蔽/涂层场景 GUI 端到端）完成，提交 `402a9f2`（链：`960d683` 场景模型 → `f00bb30` headless 驱动 +
  `analyze(output_dir)` → `a96d957` 场景页 → `719f1df` 端到端 smoke → `7834784` NIEL 溯源 → `402a9f2` CI 回归修复）。
  命令行生成器提炼为可导入 `scenarios/shielding_coating/scenario_model.py`（`ShieldingSpec`、纯函数 `render()`、`generate()`），
  `make_scenario.py` 保持原 CLI 契约并继续导出兄弟场景脚本依赖的 helper；分析侧 `analyze.analyze(output_dir)` 供 GUI 复用；
  新增 Scenario 页（15 字段三层校验、生成、QProcess 运行、结果表五列带证据、DDD 行显示 NIEL 表路径与 sha256、中英切换）与
  headless 驱动 `gui/g4usim_gui/core/scenario_shielding.py`；新增用例 `shielding_scenario_model`、`shielding_analysis`、
  `scenario_shielding_core`、`scenario_page`、`gui_scenario_backend`，并把 `platform_paths` 加入 static（测试不得写死构建路径）。
  统一测试平台 87 例（static 10 / gui 27 / backend 35 / integration 15），证据见 [docs/verification/stage2b-20261028](verification/stage2b-20261028/README.md)；
  契约见 [屏蔽涂层场景端到端](屏蔽涂层场景端到端.md)。CI：M0 workflow 在 ubuntu 与 windows 均绿（`402a9f2`，run 40675415994 / 40675409885），
  Linux workflow 的 static 与 offscreen GUI 已绿，backend 的一个写死路径失败已修复；`45891c3` 上 **M0（ubuntu+windows）与 Linux 四 profile 同时全绿**（M0 run 40680571889/40680563877，Linux run 40680571833/40680563958）。
- 2026-10-27：完成 F6 整阶段（分支 roadmap/F6-live-progress，提交 `2e87f18`）。版本化后端遥测、GUI 解析与进度显示；真实 1/2/4 worker、多 run、失败/强杀与摘要对账通过，性能以成对设计重测（中位比值 1.0047，本机漂移 ±3 %，只能称开销低于噪声）。见 [F6接续检查点](F6接续检查点.md)。

- 2026-10-27：阶段 0 只读审计修复（提交 `2e87f18`，前一个快照为 `67ce037`）。B1 位移损伤粒子名大小写解析、B2 主 INI 重复声明可见化、B3 敏感探测器名字一致性 + detector 命令 PreInit 门禁、B4 seed 生命周期门禁、GUI 源字段保留与进度/日志修正；新增 3 个回归用例，统一测试平台 76 PASS / 0 FAIL / 0 SKIP、`tracked_source_gate=pass`（报告 out/verification/stage0-20261027/20261027-225818-646efeac/report.json，副本见 [docs/verification/stage0-20261027](verification/stage0-20261027/README.md)）。README／手册中“LET/GDML/STL/自动合并未实现”等与后端相反的表述、状态文档多头、证据目录被 gitignore 等问题仍在阶段 1 处理。

- 2026-10-27：完成 E2 多模型只读审计试运行：Astra 审查架构与兼容边界，Sol 审查 GUI 校验/生成，主负责人复核证据及复现；未发现可确认功能缺陷。当前提交上 4 项专项通过，补充 writer 边界检查 7/7；未重跑整套物理回归。建立 [多模型协作约定](多模型协作约定.md)，范围、调用记录及一项非阻断回归保护建议见 [E2多模型审计试运行](E2多模型审计试运行.md)。E2 状态不变，F6 未启动。

- 2026-10-27：E2 约定模块完成，实现提交 `aaa9c1d`。统一登记 source/physics/scoring、六种几何模板及材料独立文件，8 个文件/模板上下文、48 类 section、353 个字段定义；field/biasing 明确留待后续。完整验收 70 PASS / 0 FAIL / 0 SKIP；最终 GUI 提示与单位枚举调整后 4 项专项通过；257 个启动标量、102 个上下文配置、510 组原后端对照通过，tracked_source_gate 和 Release 源码指纹均通过。详见 [E2接续检查点](E2接续检查点.md) 与 [配置schema说明](配置schema说明.md)。未重建安装包；下一项 F6，等待用户启动。

- 2026-10-28：
  - 测试平台报告 v2：每个用例经 `tools/test_assert_probe.py`（`settrace_assert_lines_v2`，含线程）记录已执行 `assert` 数；`report.json` v2 带 `tests_content_fingerprint` 与逐用例 `log_sha256`；`scripts/check_report_evidence.py` 成为 CI 证据门禁（逐项断言数、求和、零断言列表、日志字节摘要、`--baseline`）。
  - 证据门禁自洽性与日志摘要口径按 Astra 审查 D-1/D-2 修复（篡改报告实测可绕过 → 现被拒绝；日志改为按落盘字节计算摘要，`log_digest_algorithm=sha256_raw_bytes_lf_v2`）。
  - 命令失败传播 D-4/D-5/D-6：交互偏置拒绝进入会话失败汇总并非零退出、material 变更命令 PreInit 门禁、`ParseStrictDouble` 拒绝 inf/nan；新增 `scripts/test_config_value_finiteness.py`，用例总数 80。
  - E3 Linux：`.github/workflows/linux-geant4.yml` + `docs/Linux构建与验证.md`；本机 WSL 验证 Ubuntu 24.04 + conda-forge Geant4 11.3.2 的构建、backend 与 integration 套件；修掉两个 GCC-only 三目类型缺陷与 PySide 退出 SIGSEGV。
  - E3 在真实 Actions 上转绿（`a5970ff`，run 40634469313 / 40634465977）：workflow 级失败（job 级 env 用了 `runner` 上下文）、Linux 集成套件的 Qt offscreen 插件缺失（conda Qt5 插件目录遮蔽，`QT_PLUGIN_PATH` 指向 PySide6 插件）、公开仓库日志需登录（新增失败用例 `::error` 注解 + `scripts/ci_annotate_failures.py`）三个问题逐一定位修复；Linux 上 static / offscreen GUI / backend / integration 四个 profile 全绿。`m0-static-gui.yml` 仍被仓库设置手动禁用，是另一件事。
- 2026-10-24：根据 Claude 项目记录、会话及当前提交 `7640721` 整理中文接续计划。下一开发项为 E2 的 `[source]` 迁移，先复核本机基线，再逐模块推进。F2 的可变参数以生命周期实测建立白名单；E3 补充现有静态/GUI CI 未覆盖的 Geant4 后端。仅规划，未新增功能、未重新执行全套验收。

- 2026-10-23: E2 started: `schema/config_schema.json` with `[run]`, `[general]`, `[output]`; generator for the C++ key table (ConfigManager's known keys for migrated sections), the GUI data module and the matrix field tables (`--check` in the test); GUI run-settings/trajectory validation and tooltips from the schema. `scripts/test_config_schema.py` (suite `config_schema`): 255 values agree between the schema check and `--inspect-run`, 22 fields/aliases consumed, unknown keys reported, defaults and alias precedence. Found and fixed: 32-bit int overflow clamped silently (seed), empty `format`/`name`/`dir` mean the default, GUI seed range. Next modules: [source], [physics], [scoring], then geometry/material files.
- 2026-10-23: G4 + G5 done: `preview3d/sketch_geometry.py` (Qt-free) parses values as the backend (unitless = mm/rad), composes `G4PVPlacement` transforms through the parent chain and tessellates every backend solid with segments; replica/parameterised copies and boolean results are listed as not drawn. `scripts/test_sketch_accuracy.py` (suite `gui_sketch_accuracy`): 50 fixtures, 130 volume boxes within 1.5 % of the Geant4 mesh, 20 boolean targets by containment; a wrong rotation convention fails it. Source glyphs from the GPS settings (XY plane, fixed/isotropic, preview-only modes faint), also over the Geant4 geometry; `smoke_source_glyphs.py` (suite `gui_source_glyphs`) checks 4 x 200 real primaries against the glyphs via H1 trajectories.
- 2026-10-23: G6 done: Run Config "Particle tracks of the first events" writes `[output] trajectories`; `preview3d/trajectories.py` (Qt-free) loads one run's worker files (schema, duplicate-event and volume-index checks) and filters by event, particle, primaries and minimum energy; the 3D view draws one line set per particle with a check-box legend, event stepping and glass volumes, and loads a finished run's tracks itself. Also fixed: Configuration tabs overlapped below their minimum size (now scroll areas). New smoke `gui_trajectory_view` (real run of the demo project through Generate and Run).
- 2026-10-23: H1 done: `[output] trajectories` writes `trajectories_tN[_rR].json` (g4usim_trajectories_v1); real-run test: 7657 segments of 3408 tracks inside their volumes, primary length = hits step sum, 100 MeV proton mean path +0.58 % vs PSTAR CSDA (the B1 offset), filter and point cap, two runs; suite case `trajectories`.
- 2026-10-23: E5 done: `config_builder_page.py` 2411 -> 383 lines plus `widgets/config/` (one widget and one logic module per editor), `main_window.py` 997 -> 115 lines plus `window/` (shell, project, run, content). Moved code was copied by line range and method body; a widget/text/placement/signal-receiver fingerprint of the page and window is identical except one fix (Add Volume also added a volume-fraction material). New smoke `gui_config_editors`.
- 2026-10-23: G2/G3 done: material colours and legend, glass containers, camera presets, hover info, click-to-select linked with the volume table, isolate/hide/show all, section plane; Qt-free view model plus a real-window VTK smoke (`gui_3d_view`: click vs drag picking, visibility, clipping planes, table link).
- 2026-10-23: G1 done: the 3D tab builds the Geant4 world without a run package (demo project: 15 volume copies), re-exports after edits with a 1.2 s debounce, serves unchanged inputs from the cache, collapses a burst of edits into one export, and reports editor and backend errors; real-backend smoke `gui_backend_geometry_auto`. Also fixed the geometry writer erasing the editor's material errors.
- 2026-10-23: E1 done: GUI and backend agree on all 61 geometry/material cases (46 same verdict, 15 the editor reports as source-copy only, 48 GUI-writer round trips accepted); the default demo project now generates a package and shows 15 backend volume copies. Fixed seven GUI rule differences (see CHANGELOG).
- 2026-10-22: GUI refresh done: Start page and examples gallery (bundled results checked against the card claims: Bragg peak at 157.5 mm, 662 keV photopeak and Compton edge, Landau tail, deposit falling with energy), new shell and page styling, before/after screenshots; suite with the new `gui_start_page` smoke.
- 2026-10-21: Repo cleanup pushed (`f90e1da`).
- 2026-10-22: A1 ROOT output done (`889b618`): ROOT identical to CSV for 1/2/4 threads and repeated runs; suite 40/40 PASS.
- 2026-10-22: A2 done: scoring meshes (macro + INI) with ROOT/CSV export and uncertainties; native doseDeposit/cellFlux agree with DoseScorer/FluenceScorer to <1e-9; LET_t within 0.6 % (100 MeV) / 1.4 % (10 MeV) of Bethe for protons in water.
- 2026-10-22: A3 done: per-event uncertainties for edep/dose/fluence/LET; agree with raw-hit recomputation (1e-9) and with the observed spread of 20 independent runs (ratio 1.04–1.25).
- 2026-10-22: A4 done: every GPS spectrum/position/angular mode checked against analytic expectations from real primary vertices (5 sigma); 1:3 multi-source fraction 0.746; Na-24 decay 99.9 % to the 4122.9 keV level and mean beta 551 keV (NNDC 554); phase-space replay exact to 5e-12.
- 2026-10-22: A5 (all but GDML): 10 new solids match analytic volumes to 1e-12; STL navigation exact on 2000 tracks; replica per-slice dose equals explicit slabs (5 sigma); per-copy materials 1.00/2.33/11.35 g; mesh export positions exact. GDML blocked on the Geant4 installation.
- 2026-10-22: A5 done: Geant4 11.3.2 rebuilt with GDML (XercesC 3.2.5; local export filter for the MSVC 14.51 LNK1189 limit); GDML round trip of 20 volume copies exact; WSL Geant4 11.2.1 retired in favour of the single Windows install.
- 2026-10-22: A6 done: 5 EM presets match NIST XCOM 1 MeV transmission in water (1 sigma); region cuts/limits behave as Geant4 defines them; Co-60 decays only with time_threshold, matching NNDC (99.8 % to the 2505.7 keV level, mean beta 95.3 vs 95.8 keV).
- 2026-10-22: A7 done: uniform B circle (1e-5 mm), E work, Wien filter, constant and gradient maps (canonical momentum, 1e-6) and a local field box all match analytic trajectories. Phase A complete.
- 2026-10-22: Phase B1 benchmarks done: 7 CSDA ranges, R80 and 6 photon attenuation cases agree with NIST within the stated tolerances; the suite runs the quick set.
- 2026-10-22: Phase D installer done: 627 MB portable folder, 209 MB ZIP, 134 MB installer; clean-environment backend run and frozen-GUI self-test inside the package, silent install/check/uninstall test.
- 2026-10-22: Phase C3 parameter scans done, completing Phase C: GUI smoke (values, packages, collection, page, runner sequencing) and a real energy/seed scan through the page (deposit vs PSTAR S x rho t, seeds reach the backend). Fixed a crash: a widget attribute named `metric` shadowed `QPaintDevice.metric()`.
- 2026-10-22: Phase C2 new-simulation wizard done: five scenarios, GUI and real-backend smokes (Bragg peak slab, detector fluence N/A, 662 keV photopeak, Si median deposit).
- 2026-10-22: Phase C1 built-in plots done: Results / Plots tab, exact-value synthetic smoke and a real-backend smoke (CSV = ROOT mesh, Bragg peak at 157 mm, per-primary run comparison).
- 2026-10-22: Phase B4 detector response pack done, completing Phase B: 7 detector_response cases within tolerance; Geant4 option4 thin-Si MPV found +2.7 % (300 um, MIP) to ~+5 % (100 um) above the PDG LVB formula.
- 2026-10-22: Phase B3 semiconductor pack done: SR-NIEL Si tables obtained from the public calculators (user-approved), device generator/analysis, 7 device_dose cases within tolerance (TID vs PSTAR, DDD vs SR-NIEL).
- 2026-10-22: Phase B2 shielding/coating pack done: generator, analysis, displacement damage scorer (exact against a hits recomputation), and 11 Al/Si range/residual-energy cases within tolerance of the user-supplied NIST PSTAR/ESTAR tables.

- 2026-10-29：2C 在隔离 worktree 启动，Astra 主导、Sol 实现、DeepSeek API 参与前端设计。独立配置模型、configured 导出与只读查看器开发中；全模块来源/运行应用证据/三态开关未完成，保持进行中。契约见 collab/inbox/20261029-1010-astra-2c-execution.md。

- 2026-10-29：2C 配置阶段基础链路在隔离分支完成本机验收：统一平台 89 项全过、117149 条断言，独立模型另 24 条；报告见 [2C 子集证据](verification/2c-configured-20261029/README.md)。类型化模型、配置导出、只读 GUI 已接通；全模块来源/输入哈希、运行开始/最终化、off/auto/on 未完成，2C 保持进行中。未将新代码合入原 DSH 工作区，未声称新代码 Linux/CI 已验证。

- 2026-10-29 收尾补充：独立审查的 M0 两项遗留缺陷在 70a1aba 重新复现（csh setMainConfig 拒绝仍成功 P1、元数据写失败留下成功摘要 P2），尚未修复。安排在完整 2C 扩展前修复并新增正式反例；证据见 [当前分支复现](verification/m0-known-defects-20261029/README.md)。不能把既有 89 项绿当作这两项已解决。

- 2026-10-29 接续：R-01/R-02 修复完成本机 Release 与完整回归，89 PASS / 0 FAIL / 0 SKIP、117833 断言、严格门禁通过，见 [本轮证据](verification/reliability-r01-r02-20261029/README.md)。同时在同一后端复现仍未修复的 R-03/R-04，见 [独立诊断](verification/r03-r04-current-20261029/README.md)；其修复提案和 R-05–R-07 提案已入信箱。V-01 不混算程序缺陷。五项产品目标已作价值评估并排期，DeepSeek API 提供工作区建议后由 Astra 纠偏；当前保持可靠性修复→完整 2C，不宣称新目标已实现。新代码未合入原 DSH 分支，未验证 Linux/11.4/安装包。

- 2026-10-29 Q1后续候选：`4ed7233` worker偏置/随机/多run/原生UI入口守卫，`cb54669`结果来源，`5ffe9b6`探针v3与调度无关测试；105组正式清单。build7专项4/4与严格证据门禁通过，旧4e6测量基线以相同v3和两项测试修正重跑；没有重写旧失败报告。最终全平台验收与集成尚未完成。

- 2026-10-29 Q1关闭：九域审查、R01–R32修复/拒绝边界、交叉复核、干净Release与105组正式回归、同v3基线及实际Windows/Linux矩阵全部完成。验收代码8ecad66，后续仅文档/证据归档；失败CI/测量诊断不改写。集成采用独立q1-final检出正常快进codex，DSH原分支与未跟踪审计资料保留；实际提交/推送收据见最终证据目录。下一完整阶段2C。

- 2026-10-29 完整2C关闭：产品 `f4770b0` 干净Release，Windows118/118、40628个v3入口、运行时git_dirty=false；原Q1生产代码加同五份测试overlay重测控制105/105、36269入口，原baseline门禁通过。该控制是新测量，历史Q1的83770及失败报告不改写、不直接比较。Linux实际run40892017436两个版本各118，M0 run40892017433两平台各47；12gate通过、4ZIP哈希匹配。最终关联实窗2run/2worker/8事件/14快照、6张截图已查看。[最终报告](verification/2c-full-20261029/README.md)。E6、F1、Q2、完整GUI编辑和安装包不随本阶段关闭。

## 2026-10-30 F4 阶段关闭记录（已完成）

产品 `7d718d038a00d89995ea773b4772764116b620c3`；Windows 152/152、49913 个 v3 入口与 F1 原始143/48511同代基线门禁；Linux11.3.2 为 152 项、11.4.3 为 152 项（run 41056994075），M0 Windows 为 72 项、Ubuntu 为 72 项（run 41056993987）。CI实际提交 `a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9`，与产品的关系见[提交身份映射](verification/f4-final-20261030/identity/identity-map.json)。Windows原生 13 态、19 次实际观察与进程退出 0；[最终证据](verification/f4-final-20261030/README.md)，[独立审查](collab/reviews/20261030-astra-f4-close-review.md)。

实窗GUI提交 `7d718d038a00d89995ea773b4772764116b620c3`，与产品身份关系：实窗GUI与Windows后端均为产品7d718d0，121份GUI源文件清单经独立复核。13个合成诊断状态及主题、语言切换共19次原生观察，独立启动器确认自然退出0；合成导航、真实后端Inspect拒绝与图像观察分别计证，未据此新增物理验证结论。。CI身份关系：CI为产品的直接单父提交子节点，仅在Linux工作流增加六行系统运行库安装；完整11340项Git路径、模式与对象核验确认其他项相同，来源及测试指纹一致。Windows与实窗证据保留7d718d0原身份，CI十二份报告保留a9ad09d原身份；映射证明代码与测试对应关系，不证明跨平台二进制字节相同。。依赖结论：GUI依赖统一经gui/requirements.txt限定PySide6>=6.11.1,<6.12；本轮Windows实窗使用6.11.1。Linux CI采用Python3.11并安装libegl1、libgl1、libxkbcommon0、libdbus-1-3、libfontconfig1，保留数据集环境及PySide6自身QT_PLUGIN_PATH，后端使用本轮已验CI构建的CMake RPATH，Python/GUI不全局注入conda LD_LIBRARY_PATH。旧WSL命令保留历史，不作为当前启动方案。。集成事实：此关闭记录形成时，codex分支尚待正常快进；随后同日回信记录真实集成结果。。

既有编辑器及Project/Run、向导、扫描、屏蔽场景共用结构化诊断；按实际对象/字段/快照定位，表格按目标单元格滚动，旧报告失效，来源只读，原文本和阻断规则兼容。无编辑控件或可靠来源时明确拒绝。这不扩张高级GUI字段或科研物理验证；F5为下一完整阶段，仍待启动，K1/L1/Q2按原依赖推进。

5d6f008几何定位空白反例与Windows中断轮（92 PASS/1 FAIL、无完整report）、旧CI失败/未执行profile，以及096f4b3原生host异常退出均保留历史原件，不计最终通过。QA host的Close事件对象树遍历缺陷只在out辅助程序修正；第三轮7d718d0的Linux CI因缺少libEGL.so.1失败，仅有6份实际报告，后续6个Linux profile未执行；其旧报告与失败日志仍属历史，不能用新CI回填或冒充当轮通过。PID40456、2026-10-30 19:51:06的0xc0000409与缺失退出收据不得改写。合成夹具、离屏交互、真实后端Inspect拒绝与原生图像观察分别计证；本阶段不声称新增模拟或物理基准。

## 2026-10-31 F5 验收记录

2026-10-31 F5：**已完成**。冻结验收5c1eec5；Windows160/160、50898个v3入口，Linux11.3.2/11.4.3各160、M0两平台各79，原F4逐例与总量门禁通过。原生22份观察/28截图/真实退出0保持5d身份，经明确映射关联新冻结；不新增物理验证结论。[最终证据](verification/f5-final-20261031/README.md)。下方带日期的旧状态保留其历史范围。

后续按[模型分工](collab/MODEL-POLICY.md)选择实际可用模型与推理档；K1 已完成阶段验收，I1 已独立完成；当前验收与限制见上表。

### 2026-11-03 J3 整体验收退回

产品 d4400b26 新增实际成功状态标签对比度缺陷，J3 保持未关闭。原生性能对照未触发回归线；Windows限定操作及Linux独立X11三套皮肤切换已补证，完整状态/宽表/部分平台缺口保留。详见[本轮整体报告](verification/j3-whole-review-20261103/README.md)；修复后重新走相应门禁，不重写旧报告。
