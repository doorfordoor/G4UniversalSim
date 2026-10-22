# Changelog

Short, user-facing record of notable changes. Detailed support status lives in
`docs/功能支持矩阵.md`; the roadmap lives in the claude.ai project
"G4UniversalSim Development Roadmap".

## Unreleased

### Added
- **Windows installer** (roadmap Phase D): `packaging/build_package.py` builds a portable
  folder, a ZIP and an Inno Setup installer with the backend and its DLLs, a frozen GUI
  (no Python needed), examples, scenarios, scripts, docs and third-party licenses. The
  Geant4 data is not bundled; the backend finds an existing data folder through the usual
  variables, `GEANT4_DATA_DIR` or `bin/geant4-data.txt`, and the new
  `--check-geant4-data` option reports what it found. The GUI gains `--self-test`.
- **Parameter scans and batch runs** (roadmap Phase C3): a Parameter Scans page varies
  one Configuration-page setting (source energy or particle, physics list, seed, events,
  a volume's material or box thickness) over a list or lin/log range, writes one run
  package per point plus `scan.json`, runs the points one after another and shows a
  results table and a plot of any scorer quantity with statistical errors.
- **New simulation wizard** (roadmap Phase C2): File -> New Simulation... guides through
  scenario (single target, depth-dose phantom, shielding slab, silicon detector, gamma
  spectrometer), NIST materials and sizes, source, and physics/outputs/run, then fills
  the Configuration page's editors and can generate the package and run right away.
- **Built-in plots** (roadmap Phase C1): a Results / Plots tab in the GUI for scorer
  totals with statistical error bars, scoring-mesh depth profiles and 2D maps (CSV or
  ROOT), Edep histograms, per-event deposit and phase-space spectra, with log axes,
  per-primary normalisation, run overlay, comparison across output directories and
  image/CSV export. `gui/requirements.txt` now lists numpy and matplotlib.
- **Detector response pack** (roadmap Phase B4): `scenarios/detector_response/` with
  `make_detector.py` (housed gamma spectrometer crystals, silicon pads) and
  `analyze_detector.py` (pulse-height spectra, Gaussian resolution, efficiencies,
  peak-to-total, Compton edge, escape peaks, most probable deposit). New benchmark
  `detector_response` (Klein-Nishina Compton edges, pair escape lines, PDG
  Landau-Vavilov-Bichsel most probable energy loss in silicon).
- **Semiconductor device pack** (roadmap Phase B3): `scenarios/semiconductor/` with
  `make_device.py` (lid, BEOL, gate oxide, active silicon, substrate depth slices) and
  `analyze_device.py` (per-layer TID, displacement damage dose, 1 MeV neutron-equivalent
  fluence, depth profile); SR-NIEL silicon NIEL tables for protons, electrons and
  neutrons (ASTM E722-19) with a converter. New benchmark `device_dose` (thin-slab proton
  dose vs NIST PSTAR silicon stopping power; DDD vs the SR-NIEL tables).
- **Shielding / coating scenario pack** (roadmap Phase B2): `scenarios/shielding_coating/`
  ports CoatingSimulation as `make_scenario.py` (layer stack, mission spectra, mixed
  sources, junction layers, vacuum pores, transmission/albedo spectra) and `analyze.py`
  (TID, DDD, spectra). New experimental **displacement damage dose** scorer:
  `[scoring] displacement = true` with `[scoring.displacement] <particle> = <NIEL table>`
  writes `displacement_volume_summary_tN[_rR].csv` and `ddd_*` statistics. New benchmark
  `shielding_range` (Al/Si CSDA ranges and proton residual energies vs NIST PSTAR/ESTAR).
- **Physics benchmarks** (roadmap Phase B1): `scenarios/benchmarks/` packs (reference
  data, runnable example configs, Chinese READMEs) for water CSDA ranges (NIST
  PSTAR/ESTAR), the 150 MeV proton Bragg peak R80, and narrow-beam photon attenuation
  (NIST XCOM); `scripts/run_benchmarks.py` runs them and writes a JSON/Markdown report
  (`--quick` runs in the test suite).
- **Electromagnetic fields** (roadmap A7, experimental): `[field]` (global) and
  `[field.<name>]` with `volumes` (local) take uniform `magnetic` / `electric` values
  (combined fields allowed) or `magnetic_map` / `electric_map` CSV grids with trilinear
  interpolation, plus `min_step` / `delta_chord` / `delta_one_step` /
  `delta_intersection`. `scripts/test_fields_a7.py` checks trajectories against exact
  analytic results (circle in B, work done by E, Wien filter, canonical momentum in a
  gradient map, local field box).
- **Physics options** (roadmap A6, experimental): `[physics.region.<name>]` production
  cuts, `max_step`, `max_track_length`, `max_time`, `min_kinetic_energy` and `volumes`
  (regions can be created from logical volumes, also for GDML); `/AIHL/physics/setRegionCut`
  now works; `[physics.radioactive_decay] enabled / time_threshold` (Geant4's default
  1-year threshold skips long-lived nuclides such as Co-60); `/AIHL/physics/dumpProcesses`
  writes processes, models, region cuts/limits and energy thresholds as JSON. Time values
  accept `min`, `h`, `d`, `y`. `scripts/test_physics_a6.py` checks the EM presets against
  NIST XCOM and the decay settings against NNDC.
- **Geometry** (roadmap A5, experimental): new solids `ellipsoid`, `eltube`, `torus`,
  `para`, `hype`, `polycone`, `polyhedra`; STL import as `shape = tessellated` (ASCII or
  binary, closed-manifold check, automatic reorientation); `placement = replica` (box
  x/y/z, tubs phi) and `placement = parameterised` (per-copy position, rotation and
  material from `copies_file`, or `copies` + `copy_step`); `/AIHL/geometry/exportMesh`
  writes the geometry Geant4 actually built (`g4usim_geometry_mesh_v1`) and the GUI 3D
  Preview gains "Show Backend Geometry". `scripts/test_geometry_a5.py` checks volumes
  against analytic formulas, exact STL navigation, replica dose against explicit slabs
  and per-copy materials.
- **GDML** (roadmap A5): `[geometry] template = gdml` imports a GDML file through
  `G4GDMLParser` (`[gdml] file`, `validate`, `sensitive_volumes`, `bias_volumes`, and
  `<auxiliary auxtype="SensDet">`); `/AIHL/geometry/exportGDML` writes the built world.
  Needs Geant4 with GDML; the backend reports it in `--capabilities`.
- `--capabilities` now lists the A4 source modes, A5 solids and placements, and the
  ROOT schema version 4 (it still reported the pre-A3/A4 state).
- **Full GPS sources** (roadmap A4, experimental): energy spectra (`energy_type` gauss,
  uniform, power, exp, histogram or point-wise `spectrum_file`), volume sources (sphere,
  cylinder, box, ellipsoid) with `confine`, Gaussian beam spots, rotated planes
  (`rot1`/`rot2`), annulus/ellipse/square planes, angular distributions (cosine law, cone,
  beam1d, beam2d, focused), multiple weighted sources in `[source.<name>]` sections, ion
  and radioactive-decay sources (`particle = ion`, `ion = Z A [Q [E*]]`), and phase-space
  files: `[phase_space]` writes particles entering a volume to `phase_space_tN[_rR].csv`
  and `[source] phase_space_file` replays them (event k = history k).
  `scripts/test_gps_sources.py` checks every distribution against analytic expectations
  from real primary vertices, Na-24 decay against NNDC, and exact phase-space replay.
- **Statistical uncertainty for every built-in scorer** (roadmap A3): Edep (event total,
  per volume, per particle), Dose, Fluence and LET now accumulate per-event sums of
  squares. The master writes the merged `scorer_statistics[_rR].csv` (any output format)
  with value, mean per event, standard error, relative error and figure of merit; LET_t /
  LET_d use delta-method errors for ratios. Per-thread CSVs and ROOT ntuples gain additive
  `*_sum_sq*` and `n_events` columns (ROOT schema `g4usim_root_v4`; dose/fluence/LET CSV v2,
  edep summary CSV v4); `scripts/g4usim_io.py` adds `load_scorer_statistics()`.
  `scripts/test_statistical_uncertainty.py` checks against raw hits and against the
  observed spread of 20 independent runs.
- **Geant4 scoring meshes** (roadmap A2): native `/score/` box and cylinder meshes with
  all primitive scorers and particle/energy filters, from macros or INI
  (`[scoring.mesh.<mesh>]`, `[scoring.mesh.<mesh>.<quantity>]`). Results per run in the
  ROOT `mesh` ntuple and `scoring_mesh[_rR].csv` with sum, sum of squares, entries and
  relative error; `scripts/g4usim_io.py` loads them as dense arrays.
- **LET** (roadmap A2): `[scoring] let = true` gives track- and dose-averaged LET per
  sensitive volume (`let` ntuple, `let_volume_summary` CSV), checked against the Bethe
  formula for protons in water.
- Dose and fluence prototypes validated against native `doseDeposit` / `cellFlux`
  (agreement < 1e-9).
- ROOT schema is now `g4usim_root_v3` (adds `mesh` and `let`).
- **ROOT output** via Geant4 `G4AnalysisManager` (roadmap Phase A1).
  `[output] format = csv | root | both` and `/AIHL/output/setFormat`.
  One `g4usim.root` per run with worker threads merged automatically; histograms
  `edep_raw`, `edep_weighted`; ntuples `hits`, `events`, `edep_volume`,
  `edep_particle`, `dose`, `fluence` (schema `g4usim_root_v1`).
- `run_metadata.json`: machine-readable run summary (format, Geant4 version,
  source fingerprint, runs, generated files with schemas).
- `scripts/compare_root_csv.py` and the `root_output` regression case.

### Changed
- `scripts/run_m0_tests.py` no longer crashes when a failing case's log tail contains
  characters the console code page cannot encode (they are replaced).
- Repository hygiene: corrected `.gitignore`, removed tracked build artifacts and
  Geant4 example B1 leftovers, `.gitattributes` line-ending normalization.
- `gui/requirements.txt` now includes `uproot`.
