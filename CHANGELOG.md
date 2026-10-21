# Changelog

Short, user-facing record of notable changes. Detailed support status lives in
`docs/功能支持矩阵.md`; the roadmap lives in the claude.ai project
"G4UniversalSim Development Roadmap".

## Unreleased

### Added
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
- Repository hygiene: corrected `.gitignore`, removed tracked build artifacts and
  Geant4 example B1 leftovers, `.gitattributes` line-ending normalization.
- `gui/requirements.txt` now includes `uproot`.
