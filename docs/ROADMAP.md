# G4UniversalSim Development Roadmap

Agreed 2026-10-21. Order of work: **Phase A core functions → Phase B scenario packs → Phase C wizard and plotting → Phase D installer** (only once the framework is mostly stable).

This file is the single source of truth for progress. Every work session updates the status table and the progress log at the end.

## Status

| Item | Status | Commit |
| --- | --- | --- |
| Repo cleanup | Done | `f90e1da` |
| A1 ROOT output layer (G4AnalysisManager) | Done | `889b618` |
| A2 Native Geant4 scoring + LET | Done | see log |
| A3 Statistical uncertainty | Next (meshes already carry sum_sq / rel_error) | |
| A4 Full GPS sources | Not started | |
| A5 Geometry (GDML, replica/parameterised, solids, true preview) | Not started | |
| A6 Physics (EM options, radioactive decay, region cuts/limits) | Not started | |
| A7 Fields | Not started | |
| B Scenario packs + benchmarks | Not started | |
| C Wizard + built-in plotting | Not started | |
| D Installer | Not started (only after A–C are mostly stable) | |

## Data storage decision

Geant4's analysis category (`G4AnalysisManager`) is the single output layer. ROOT (`.root`) is the primary format, written natively by Geant4 with automatic thread merging; CSV stays as a debug/compatibility option. GUI and Python tools read ROOT with `uproot`.

## Phase A: core functions

1. **Output layer on G4AnalysisManager — done.** `[output] format = csv|root|both`; one merged `g4usim[_rR].root` per run (schema `g4usim_root_v1`); `run_metadata.json`. Follow-ups: switch default to `root` once the GUI reads ROOT; add git commit and config hash to metadata.
2. **Scoring on native Geant4 scorers — done.** `/score/` meshes from macro or INI (`[scoring.mesh.*]`), exported to ROOT `mesh` / `scoring_mesh.csv` with sum, sum_sq, entries, rel_error; dose/fluence prototypes validated against native scorers; LET_t/LET_d (`[scoring] let = true`) validated against Bethe. Follow-ups: real-volume primitive scorers (G4MultiFunctionalDetector on logical volumes), heavy-ion LET benchmark, GUI editors. Original scope: `/score/` box/cylinder meshes written to the ROOT file; `G4MultiFunctionalDetector` primitive scorers (energyDeposit, doseDeposit, cellFlux, passageCellCurrent, nOfSecondary) with particle and energy filters, configurable from INI/macro; validate the existing dose/fluence prototypes against them; add LET (track- and dose-averaged).
3. **Statistical uncertainty everywhere.** Per-scorer mean, variance (sum of squares per event), relative error and figure of merit in outputs.
4. **Full GPS sources.** Energy spectra from file, multiple weighted sources, beam profiles, cosine-law/focused angular distributions, confined volume sources, radioactive-decay sources, phase-space file read/write.
5. **Geometry.** Real GDML import/export (`G4GDMLParser`, detect XercesC); replica and parameterised placement; unified SolidRegistry with additional solids; CAD via tessellated solids; backend geometry export so the GUI 3D preview shows the true geometry.
6. **Physics.** EM option presets (opt4, Livermore, Penelope); radioactive decay; per-region production cuts and step limits (finish the region-cut implementation); active-process dump.
7. **Fields.** Uniform magnetic/electric fields, field maps, volume-local fields.

## Phase B: scenario packs

Each pack = configs + docs + a benchmark against reference data.

- Shielding / composite coating (port from `D:\Geant4\CoatingSimulation`: TID, displacement damage, escape spectra, porosity).
- Semiconductor device dose and displacement damage.
- Detector response.
- Benchmarks: NIST stopping power / CSDA range, proton Bragg peak in water, gamma attenuation.

## Phase C: wizard and built-in plotting

- Guided "new simulation" wizard (scenario → materials → geometry → source → run); full editors stay as advanced mode.
- Built-in plots from ROOT output: spectra, depth-dose, 2D maps, error bars, run comparison.
- Parameter scans and batch runs with a results table.

## Cross-cutting improvements

- One schema as the single source of truth for C++ validation, GUI forms and docs.
- English documentation alongside Chinese.
- CI (GitHub Actions) with Geant4 Docker/conda-forge; compatibility matrix Geant4 11.2–11.4, Windows/Linux.
- Batch/cluster mode (Slurm export) and Linux Docker image.
- Lighter process docs: `CHANGELOG.md` plus the support matrix instead of long agent logs.

## Phase D: distribution

One-click Windows installer (backend + GUI + examples) after Phases A–C are mostly stable.

## Working agreement for each work session

- Work on one roadmap item at a time, in order, in small verifiable slices. Use a local branch `roadmap/<item>` off `codex`.
- A slice is done only when: Release build succeeds, the new feature has a real Geant4 regression test, and the full suite `scripts/run_m0_tests.py --profile all` (GUI venv Python) has no FAIL.
- When a roadmap item is complete: fast-forward `codex`, push `codex` to GitHub (normal push only, never force), mark it Done here with the commit, and add a `CHANGELOG.md` entry.
- New features default to off or keep existing behaviour; mark them experimental in `docs/功能支持矩阵.md` until benchmarked.
- Never rewrite history, force-push, or touch `总体判断.md`, `_backup_git_*`, or the user's other branches.
- Stop and ask the user instead of guessing when a choice is hard to undo or changes physics results or defaults.

## Progress log

- 2026-10-21: Repo cleanup pushed (`f90e1da`).
- 2026-10-22: A1 ROOT output done (`889b618`): ROOT identical to CSV for 1/2/4 threads and repeated runs; suite 40/40 PASS.
- 2026-10-22: A2 done: scoring meshes (macro + INI) with ROOT/CSV export and uncertainties; native doseDeposit/cellFlux agree with DoseScorer/FluenceScorer to <1e-9; LET_t within 0.6 % (100 MeV) / 1.4 % (10 MeV) of Bethe for protons in water.
