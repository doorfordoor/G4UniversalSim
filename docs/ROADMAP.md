# G4UniversalSim Development Roadmap

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
| E Fixes and foundations | In progress: E1, E2, E3 (Linux incl. Geant4 11.3.2/11.4.3 matrix, done 2026-10-28), E5 done; E4 pending | see log |
| F System optimisation (backend + GUI) | In progress: F6 done (2026-10-27); F1–F5, F7, F8 pending | see log |
| G 3D view redesign | Done (G1-G6) | see log |
| H Geant4 capability increments | In progress: H1 done | see log |
| Q1 完整可靠性审查、修复与验收 | 进行中：本对话主导；R-01/R-02 已修，R-03/R-04 已在当前代码复现；全模块审查及剩余修复未完成 | `f9930aa` 为修复增量，不是 Q1 总验收 |
| 2C 完整 EffectiveConfig / off-auto-on | 进行中：configured 子集已验收，完整来源与运行应用证据仍缺 | `70a1aba` |
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
- **F2 Run session (adjust between runs).** An interactive session driven by the GUI
  (the audited `csh` session over a pipe): a whitelist of settings that are safe while
  Geant4 is Idle (source particle/energy/position/direction/shape, beamOn, run name,
  output toggles that are per-run), every change logged per run in `run_summary.txt`
  with its origin, and a replay macro written at the end; anything else (geometry,
  physics, threads) is refused with the reason. Done when: three real runs with
  changes preserve per-run inputs and reproduce under a defined backend/version,
  random-engine and thread protocol. Bitwise comparison, where justified, applies
  to defined event data; it is not a promise across platforms, thread counts, or
  timestamp-bearing output files. A full configuration switch uses a new process.
- **F3 Performance.** Profile a hits-heavy and a mesh-heavy run; optional
  `G4TaskRunManager` (`[run] run_manager = mt|tasking`) remains a separate experiment,
  with a defined seed protocol and predeclared event/statistical comparison criteria.

GUI:
- **F4 Validation that leads to the field.** Every message carries its location
  (editor, row, field); clicking it selects the tab/row and highlights the control.
- **F5 Undo/redo and autosave.** Command-based undo in the editors; autosave of the
  project to a recovery file and an offer to restore after a crash.
- **F6 Live run progress.** The backend prints a progress line (events done, rate)
  at a fixed interval; the Run Console shows a progress bar, rate and time left.
- **F7 Better scans.** Two-parameter grids with a 2D map plot; several points at once
  within a thread budget; scans of scenario-pack generators.
- **F8 Smaller GUI follow-ups.** A page for the Geant4 data folder (D follow-up),
  re-opening the wizard on an existing project, a human high-DPI/accessibility pass.

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
- **H8 Voxel phantoms.** `G4PhantomParameterisation` (later DICOM). Benchmark: a voxel
  water phantom gives the same depth dose as the homogeneous phantom.
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
| 4 | 双平台桌面交付 | **I2、J1** 独立文件并行，随后 **F8** 收尾 | 支持矩阵内的运行时/SDK安装、当前版本包、真实桌面布局与向导操作验收 |
| 5 | 自动配置与运行 | **L1 → F2** | 配置 Agent 真正闭环；F2 单独证明 Idle 白名单与重放。L1 先用新进程，不被热会话阻塞 |
| 6 | 科研效率与架构补齐 | **Q2 → H2 → H3**；**F3 → F7**；**E7 → J2** 按文件归属串并行 | 独立物理/权重基准、过滤/平行世界、性能/二维扫描、实体注册与编辑覆盖各自整项验收 |
| 7 | 独立工程与代码执行 | **K2 → L2** | 干净 Windows/Linux 环境能独立构建、运行、继续开发；代码 Agent 有隔离、恢复与有限修复证据 |
| 8 | 高级物理与生态 | **H4 → H5 → H6 → H8 → H7 → H9**，**M5** 独立排期 | 每项单独确定适用域、输入/输出契约和参考数据，不以 AI 能调用为物理验收 |

上表是默认资源顺序，不把前面波次的无关项目做成硬依赖。例如 K2 可以在 K1/I2 就绪后与科研波次并行，不要求所有 H/J 项先完成；L2 必须等 K2 和 L1 的执行契约就绪。Q2 的方法资料准备可从 Q1 开始，正式科研结论不能早于其验证。若用户提出明确科研急需，可调整 H4–H8 的先后并在这里记录，不丢弃原计划。

#### 当前质量与配置工作项

| 代号 | 范围与已有基础 | 依赖/完成条件 | 当前状态 |
| --- | --- | --- | --- |
| **Q1** | 完整可靠性审查、反例复现、修复、回归与交付复核；覆盖已公开能力和拒绝边界 | 见下方专用范围/退出门槛；结果错误、漏计分、假成功优先 | 进行中；R-01/R-02 在 `f9930aa` 修复，89 项全过不等于完整 Q1 |
| **2C** | 完整 EffectiveConfig：11 类真实消费者、稳定对象身份、完整来源链、实际读取字节哈希、事务替换/删除、configure/run_begin/finalization、内核/worker 证据、off/auto/on、GUI 审查 | Q1 基线；每类消费者有正反例，拒绝不污染 revision/来源；unknown 不伪装 applied；现有协议兼容 | `70a1aba` 只有配置阶段子集，完整项进行中 |
| **E6** | E2 范围补齐与配置兼容：field/biasing schema；主 INI 版本策略；几何 v2/项目格式迁移与诊断去重 | 2C；生成表不手改；旧输入/别名、未来未知版本、迁移副本、**现有编辑子集** writer 兼容/往返。扩大编辑范围归 J2，不让 E6 等待 J2，不顺带开放 assembly/材料温压等 | 待开始，E2 原状态保持完成 |
| **E7** | SolidRegistry 与统一实体能力元数据；后端构造、校验、能力查询、GUI 可消费定义逐步归一 | E6/现有 A5；实体逐项差分、缓存/线程生命周期守卫与旧配置不变；不借重构增加未验实体 | 待开始；原 M0 架构积压，不属于 2B 屏蔽场景欠账 |
| **Q2** | 科研基准与适用范围：Dose/Fluence/LET/DDD、统计不确定度、现有 XS biasing 与 analog 对照、独立数据/解析参考与可复现实验 | Q1、F1；V-01 的口径先在 Q1 明确，Q2 再验证有限样本/覆盖与适用边界；不以同源自洽或 process 挂接代替独立证据 | 待完整验收，复用 A/B 已有限定基准 |

#### 原 E/F 余项（保留原编号）

| 代号 | 整项交付内容 | 验收/归属与提交重点 | 当前状态 |
| --- | --- | --- | --- |
| **E4** | 当前规范瘦身、历史状态校准、中文快速入门、文档单一事实入口 | 历史条目迁移已有成果；补规则逐项映射，清除 stale 状态，链接与必要 smoke 通过。阶段关闭交 `docs(E4)` | 部分完成，继续收尾 |
| **F1** | 输出身份、commit/config/全部引用资源 hash，版本化输出；测量后决定缓存/format=auto | 来源/默认行为分开提交；没有批准的默认值变更继续保持现状。依赖 2C/E6，支持 K1/Q2 | 待完成 |
| **F2** | GUI 受控 run session、Idle 白名单、逐 run 输入/来源/重放协议 | 完整换配置用新进程；三轮调整的真实状态与限定环境重放；不承诺跨平台/线程数逐位一致。可在 L1 后交付 | 待开始 |
| **F3** | hits-heavy/mesh-heavy 的耗时、内存、输出基线及瓶颈优化；tasking 单列实验 | 测量→单一瓶颈变更→前后对照；统计/种子/输出契约不改变。性能优化不能成为接受结果差异的理由 | 待开始 |
| **F4** | 定位到 editor/row/field/code 的诊断及点击跳转 | 诊断身份不随语言改变，不抹除来源错误；K1/L1 复用同一结构 | 待开始 |
| **F5** | 配置事务 undo/redo、自动保存、异常恢复 | 撤销后生成语义一致；恢复文件不覆盖原件；自动操作走相同事务接口 | 待开始 |
| **F6** | 实时进度与 sequence | 已完成，Q1 复核解析、取消和失败边界；进度不替代成功证据 | 保持完成 |
| **F7** | 二维扫描、线程预算内并发、场景生成器扫描 | 依赖 K1/F3；每点独立 seed/目录/证据，失败/重试不重复发布，缺点可见 | 待开始；已有单参数串行扫描保留 |
| **F8** | 环境设置页、向导重入、真实桌面 DPI/可访问性收尾 | 数据目录页由 I1 实现；布局/DPI 由 J1 实现；F8 承担向导重入和跨项桌面验收，避免重复建设。三部分齐全才关闭 F8 | 待完成 |

E3 的已完成 Linux CI 基础不重建；Windows 11.4、原生 Linux 桌面、包内 ROOT/Python 辅助工具与干净安装验收归 I2。现有后端 ROOT 输出和新版本源码 CI 仍按 Q1 及各阶段冻结矩阵验证。Geant4 11.2 先在 I1/I2 决定是否进入支持矩阵：不支持则清晰拒绝/说明，不默认承担无限旧版本兼容。

接口所有权：F4 先实现可复用诊断结构，F5 先实现配置事务/撤销基础；K1 负责组合这些能力、已有 runner/result/package writer 与 CLI/GUI，形成统一动作服务。前置 F 项不等待 K1 完成，K1 也不再另造第二套事务和进程控制器。I1 只提供环境事实，I2 执行环境安装，均不拥有模拟任务状态。

#### 新五项目标的正式代号

| 代号 | 对应用户目标与整项内容 | 硬依赖 | 主要提交节点/最终验收 |
| --- | --- | --- | --- |
| **I1 环境发现与诊断** | 目标 1；GUI/启动器检测后端、运行时、SDK、编译器、CMake、版本、架构、可选组件和数据；区分候选发现与真实可用 | Q1；只读探测可与配置底座并行 | 环境模型/探测 → GUI 选择与诊断 → 缺库/多环境/路径/真实 smoke。缺 Geant4 时诊断入口仍能启动 |
| **I2 辅助安装与双平台交付** | 目标 1；受控安装前缀、下载校验、失败恢复、运行时/SDK 两种方案、当前版本 Windows/Linux 包、诊断包和版本矩阵 | I1 | 平台方案 → 安装/恢复实现 → 干净系统包验收/实际 CI。普通运行不强迫装编译器；项目许可/签名发布另按具体产物决定 |
| **J1 可调整工作区** | 目标 2；配置、3D/结果、日志、AI 区可移动/缩放/隐藏/浮动；三种布局和 B/K/C 起始主题；本机保存/复位 | Q1；K1 的服务/状态所有权稳定 | Qt dock 骨架 → 布局持久化/主题 → 多屏/DPI/键盘/中英/运行中切换。布局不改配置、不重复启 run |
| **J2 编辑覆盖与几何往返** | 原 M3 余项；按科研需求扩展已支持的高级源/实体/场/偏置编辑，连接能力清单；布尔工具只开放已实现子集 | E6、E7；按阶段冻结编辑范围 | 能力/编辑映射 → editor/writer → 旧输入保留、未知字段无损复制或明确拒绝、真实生成/重载/运行。不是给全部 Geant4 接口做表单 |
| **K1 可信实验工作流与配置导出** | 目标 3 的配置部分；统一 inspect/validate/apply/generate/run/evaluate/export，验证分级、输入身份、可移植配置/资源/证据包 | 2C、E6、F1、F4、F5、I1 | 服务契约 → GUI/CLI 接通 → bundle/验证失效 → 干净目录加载/重跑/分享。修改输入后旧验证不能继续挂在新配置上 |
| **K2 独立 Geant4 工程导出** | 目标 3 的源码部分；可审阅 C++/CMake、配置/资源/许可、扩展点和构建说明；脱离工具可继续开发 | K1、I2；当前支持子集即可，不依赖所有 H 项 | 导出模板/manifest → 生成与构建 → 两平台干净环境构建/运行/二次修改；不能只附 INI 或依赖工具安装目录 |
| **L1 配置 Agent 与模型接入** | 目标 4 首版及目标 5 基础；云 API-key/本地模型适配、结构化差异、授权范围内修改、校验、试跑、读证据、确认/导出 | K1、I1；J1 提供桌面承载，API 可先验证 | provider/凭据与动作接口 → 有界任务状态 → 自然语言端到端/取消/恢复/歧义/失败反例。可写边界来自接口白名单，不来自 EffectiveConfig 读回子集 |
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
| **H8** | 规则体素体模与材料映射 | 均匀体对照、内存/几何校验；DICOM 是另行决定的扩展，不偷偷包含 | H6 后 |
| **H7** | 局域 Geant4-DNA/径迹结构 | 粒子、能区、材料、region 模型边界；官方样例作回归，独立参考另列 | H8 后 |
| **H9** | INI 定义通用直方图/ntuple | F1 输出版本契约，现有 writer 兼容和原始记录独立重算 | 保留原候选顺序最后，不因“统一”批量重写 |

每项仍是完整阶段，按配置→校验→运行→GUI边界→真实测试→文档交付。Q2 与 H4 职责不同：前者验证已有计分/XS 偏置，后者引入新的方差降低算法。

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

先复用已收到的提交/输入/日志，核对代码是否变化；相同已验证事实不重复整段调查，缺失的模块与反例补上。采用“模块审查→反例→修复→针对性回归→独立复核”的滚动推进，全部模块结束后再做整体验收。当前已完成 R-03–R-24 的反例/候选修复主线（含本轮新发现的材料、源、GUI、SD 和 GDML 路径缺陷），正在专项复验与最终冻结；尚未关闭 Q1。V-01 明确估计量和小样本语义，V-02 明确 max_step 的粒子适用范围，均不得偷偷调整默认物理或误差公式。R-08/V-02 的邻线证据基于 `5465dbd`；相关 Field/Physics 实现未变化，但本对话尚未在当前构建重跑，见 [新来信登记](collab/inbox/20261029-1312-astra-new-audit-receipt.md)。

| 审查域 | 必须检查的边界 | 当前覆盖说明 |
| --- | --- | --- |
| 启动/配置/命令 | CLI/INI/macro 优先级、空值/单位/非有限、重复/未知字段、失败传播和来源 | M0 独立审查 + 本轮 CLI/INI/macro/csh 失败传播复核；R01/R02 已验，R09/R13 输入与动态命令反例专项通过，完整回归待冻结验收 |
| 材料/几何/SD | 真实材料与尺寸、母子/布尔/STL/GDML/复制/参数化、名称身份、region、SD 绑定 | geometry/field 交叉审查，R03/R04/R09/R15 候选专项通过；新 R24 路径身份拒绝等待第三轮专项，GDML/复制/参数化旧能力仍跑完整回归 |
| 粒子源 | GPS 高级分布、多源/离子/相空间、事件与初级粒子数、权重、真实顶点 | SourceManager/PrimaryGenerator/GPS 入口与对象生命周期已审；R12/R13 直接命令、多源、离子、confine、alias 的真实顶点反例通过第二轮专项 |
| 物理/场/偏置 | 物理过程/region cuts/限制、场的线程对象、operator 挂接及拒绝边界 | R08 最近显式祖先与共享LV冲突已通过完整A7专项；V02 只修说明不改默认物理，R14 process大小写通过；独立物理范围扩大仍归 Q2/H |
| 计分/统计 | Edep/Dose/Fluence/LET/DDD、NIEL来源、零贡献、权重/溢出、事件分组、误差/协方差 | R03/R05/R06/R07/R10/R11 候选通过真实/合成反例；V01 已冻结方法与小样本语义，不声称统计覆盖率已验证。四worker补充及完整回归待最终验收 |
| 运行与 MT 生命周期 | Build/Begin/End/finalize、共享登记、失败回调、跨 run 清零、随机/线程协议、资源释放 | 动作生命周期/共享失败/跨run清零审查，R06/R23 真实MT失败收尾专项通过；GUI取消/关窗已真实验证，完整回归待最终验收 |
| 输出与后处理 | CSV/ROOT/JSON、计数/单位/版本、worker 合并、缺失/陈旧/写失败、部分产物 | R02 已修，R06/R07 CSV/ROOT/both、稀疏worker、master合并错误路径专项通过；旧格式兼容与门禁待全量复核 |
| GUI 全链路 | 项目保存/加载、writer 保留、inspect/QProcess、异步竞态、取消/关窗、进度/结果/绘图、i18n | GUI公开入口已逐项审查并使用DeepSeek独立复核；R16–R22专项与真实Windows保存/生成/运行/取消/关窗/结果流程通过，完整冻结回归待验 |
| 构建/平台/测试可信度 | 干净检出、源码/测试/可执行指纹、依赖/路径、真实 CI、断言质量、测试盲区与负向门禁 | 测试断言/日志摘要/源与测试指纹门禁复核，新增反例已注册；当前源码干净检出、全量Windows与真实Linux双版本CI仍待取得 |

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

Q1 的已存节点：修前证据 d286577、R01/R02 9930aa；本轮实现 5c6da6d（几何/材料）、529b5de（场/源）、6e1302（数值/SD）、d3f37af（GUI/后处理）。R03–R24 与 V01/V02 候选专项已通过，正式清单98组；**尚缺最终干净检出/全平台/集成验收**，不能据实现提交关闭Q1。详见 [问题索引](collab/reviews/20261029-q1-findings.md) 与 [审查检查点](collab/reviews/20261029-q1-core.md)。2C 的 70a1aba 仍仅为 configured 子集节点，其他后续阶段保持原状态。

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
