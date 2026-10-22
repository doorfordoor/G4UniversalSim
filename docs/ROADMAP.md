# G4UniversalSim Development Roadmap

Agreed 2026-10-21. Order of work: **Phase A core functions → Phase B scenario packs → Phase C wizard and plotting → Phase D installer** (only once the framework is mostly stable).

This file is the single source of truth for progress. Every work session updates the status table and the progress log at the end.

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

## Working agreement for each work session

- Work on one roadmap item at a time, in order, in small verifiable slices. Use a local branch `roadmap/<item>` off `codex`.
- A slice is done only when: Release build succeeds, the new feature has a real Geant4 regression test, and the full suite `scripts/run_m0_tests.py --profile all` (GUI venv Python) has no FAIL.
- When a roadmap item is complete: fast-forward `codex`, push `codex` to GitHub (normal push only, never force), mark it Done here with the commit, and add a `CHANGELOG.md` entry.
- New features default to off or keep existing behaviour; mark them experimental in `docs/功能支持矩阵.md` until benchmarked.
- Never rewrite history, force-push, or touch `总体判断.md`, `_backup_git_*`, or the user's other branches.
- Stop and ask the user instead of guessing when a choice is hard to undo or changes physics results or defaults.

## Progress log

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
