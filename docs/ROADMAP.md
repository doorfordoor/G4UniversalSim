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
| 审计修复批次（2026-10-29） | 进行中：R-01/R-02 已修并通过完整 89 项回归；R-03/R-04 本分支确认仍有缺陷，R-05–R-07 待修；V-01 单列方法决策 | 下文接续安排 |
| 2C 完整 EffectiveConfig / off-auto-on | 进行中：configured 子集已验收，完整来源与运行应用证据仍缺 | `70a1aba` |
| 可信配置/环境诊断、工作区、AI 执行与独立工程导出 | 已评估并排期，尚未实现；按下文整阶段交付 | [价值与验收提案](collab/inbox/20261029-1140-astra-product-roadmap.md) |

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
- **E4 Lighter process docs.** Move the dated entries of `AGENTS.md` / `gui/AGENTS.md`
  into `docs/agent-history.md`; keep the rules short and current. Add an English
  quick start next to the Chinese one (human docs stay Chinese-first). Done when:
  each AGENTS.md is mostly rules and links, and no rule is lost (checked line by line).
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
  physics, threads) is refused with the reason. Done when: a real session with three
  runs and changes between them reproduces bit-for-bit from the replay macro.
- **F3 Performance.** Profile a hits-heavy and a mesh-heavy run; optional
  `G4TaskRunManager` (`[run] run_manager = mt|tasking`) with identical results to MT
  for fixed seeds per event.

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

### 2026-10-29 接续顺序（覆盖下方旧顺序中的待办部分）

用户希望继续开发，同时由另一会话逐项审查已完成阶段。修复采用连续接收、按影响插入的方式：结果错误、漏计分和假成功先于依赖它们的新功能；体验问题随对应阶段处理。历史 Done 只表示原约定范围和当时测试通过，不免除新反例修复，也不把所有历史阶段统一改成未完成。

1. **可靠性修复批次 → 完整 2C**。R-03（敏感母体 Dose 质量）与 R-04（GDML 漏绑 SD）优先；R-01（csh 拒绝仍继续）、R-02（metadata 失败而文本成功）可以独立并行。R-05（粒子/事件归一化）、R-06（Edep 溢出）、R-07（ROOT 回退事件数）在同批结果可靠性门禁内闭合。V-01 是统计口径决策，不混算程序缺陷。然后继续完整消费者、输入哈希、对象身份、运行证据和三态开关。
2. **可信配置与环境诊断**。整合 F1/F4/F5 与 E3/D/F8 的相关目标：统一检查/修改/生成/运行/判断服务、撤销恢复、分级验证、可移植配置包；自动辨别运行时与 SDK，给出路径/版本/能力/真实 smoke 诊断。
3. **可调整工作区 + 环境安装助手**。两条可并行：DeepSeek 负责 Qt dock 与主题设计，Sol 实现；应用管理的安装前缀、支持矩阵及 Windows/Linux 分别验收。三个起始主题，配置/3D结果/日志/AI 面板可调整、保存、复位。
4. **配置 Agent**。云 API 或本地模型通过同一动作接口执行自然语言实验配置、检查、小运行和证据汇报。支持取消、限额、记录、恢复与可审阅差异；受支持参数调整通常不需要生成 C++ 或重新编译。
5. **独立 Geant4 工程导出**。携带必需 C++/CMake/资源与许可说明，脱离工具安装目录后可构建、运行、继续修改；先明确支持子集及可信源码模板，跨平台干净目录验收。
6. **代码 Agent 与可恢复工作流**。在隔离工程中进行源码修改、构建、有限修复与用户确认。需要持久编排时优先评估 LangGraph，领域动作保持独立；不为多 Agent 而重复建设控制层。

第 3 项用户目标中的“验证配置导出”优先级最高，“独立源码导出”单独排后；第 5 项是第 4 项成熟后的整合目标。详见 [五项目标价值、范围与验收](collab/inbox/20261029-1140-astra-product-roadmap.md)、[DeepSeek 工作区建议与纠偏](collab/outbox/20261029-1135-deepseek-workspace-design.md)。阶段 2 仍冻结新增产品功能，先修复和闭合基础。

F2 继续保留，但完整主配置切换优先新进程，不以热重载作为 AI 自动化前置要求；Idle 可变字段另按生命周期验收。F3 性能、F7 扫描和 H2–H9 按明确科研需求插入，不抢在可信结果基础之前。以上为范围与次序，不是完成声明或固定工期。

### 旧 Order of work（2026-10-23 历史）

1. E1 (unblocks the 3D view) → 2. G1 → 3. G2 + G3 → 4. E5 (before more GUI work) →
5. H1 → G6 → 6. G4 + G5 → 7. E2 (schema; modules migrate over several sessions) →
8. F6 → F2 → 9. F4 + F5 → 10. F7 → 11. H2 → H3 → H4 → H5 → H6 → H8 → H7 → H9 →
12. E3, E4, F1, F3, F8 fit in between when a session is short.

Decisions to ask the user when the item comes up: hosted CI runners (E3), any change of
an output default (F1), which session protocol to expose (F2), and the priority among
H4–H8 if the user's applications favour some of them.

## Working agreement for each work session

- Work on one roadmap item at a time, in order, in small verifiable slices. Use a local branch `roadmap/<item>` off `codex`.
- A slice is done only when: Release build succeeds, the new feature has a real Geant4 regression test, and the full suite `scripts/run_m0_tests.py --profile all` (GUI venv Python) has no FAIL.
- When a roadmap item is complete: fast-forward `codex`, push `codex` to GitHub (normal push only, never force), mark it Done here with the commit, and add a `CHANGELOG.md` entry.
- New features default to off or keep existing behaviour; mark them experimental in `docs/功能支持矩阵.md` until benchmarked.
- Never rewrite history, force-push, or touch `总体判断.md`, `_backup_git_*`, or the user's other branches.
- Stop and ask the user instead of guessing when a choice is hard to undo or changes physics results or defaults.

## Progress log

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
