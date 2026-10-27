# G4UniversalSim

中文完整使用手册：[docs/中文使用手册.md](docs/中文使用手册.md)

G4UniversalSim is a C++17 + Geant4 simulation framework for configuration-driven detector studies. It provides template geometry, material loading, GPS-based sources, reference/manual physics setup, sensitive-detector hits, raw and weighted scoring, cross-section biasing hooks, and lightweight post-processing tools.

## MVP Status

The current project is intended to build into a runnable Geant4 executable with this workflow:

1. Load `config/main.ini`.
2. Register detector, physics list, source/actions, scoring, and optional biasing hooks.
3. Execute a macro such as `macros/run_simple.mac`.
4. Run `/run/initialize` and `/run/beamOn`.
5. Write CSV outputs and `run_summary.txt`.

Advanced MicroElec/ElectronCapture support is optional and experimental. `EdepScorer` is the most validated scorer; LET, dose, fluence and displacement-damage scoring are experimental and only partially validated - check [docs/功能支持矩阵.md](docs/功能支持矩阵.md) for the exact limits of each.

## Current Safety Notes

- `mode = volume_fraction` is supported for material components. Volume fractions are converted to mass fractions using component densities; `density = auto` uses ideal additive-volume density, while explicit density overrides the final mixture density.
- `template = gdml` imports a GDML file through `G4GDMLParser` (`[gdml]/file`, `validate`, `sensitive_volumes`, `bias_volumes`; export with `/AIHL/geometry/exportGDML`) when Geant4 is built with GDML support; without it the configuration is rejected before any geometry object is built. The import does not preserve world/replica/parameterised physical-volume names or per-copy materials, and the GUI cannot generate a GDML run package (external runs can use one).
- STL import is available as the experimental `shape = tessellated`; the reader requires a closed, consistently oriented manifold (see [docs/中文几何配置说明.md](docs/中文几何配置说明.md)).
- Hierarchical geometry supports `trd` / `trapezoid` through `G4Trd`, and full `trap` through `G4Trap`; all `trd` / `trap` length parameters are half-lengths.
- `layered_device` propagates `copyNo`, `metadata.*`, and unknown layer keys to `VolumeNode::userProperties`; metadata is not written to hit CSV files yet.
- `/AIHL/output/...`, `/AIHL/app/...`, and `/AIHL/detector/...` are registered by the default executable. Output commands do not include hits/scoring switches; use `/AIHL/scoring/...` for those.
- Importance biasing, weight-window, splitting, and Russian roulette are future work. The currently usable biasing path is process-level XS biasing.
- Multi-thread CSV output uses per-worker `OutputManager` / `ScoringManager` instances and writes `_tN` files; per-thread CSV files still need an explicit merge (`scripts/merge_outputs.py` or `mergeHistograms`). With `[output]/format = root` (or `both`) G4AnalysisManager merges histograms and ntuples into one ROOT file per run, so ROOT output needs no manual merge.

## Features

- `/AIHL/...` command namespace for project commands.
- `SimulationManager` owns managers and messengers.
- `GeometryManager` builds template-driven `VolumeNode` trees through `VolumeBuilder`.
- `DetectorConstruction` only calls `GeometryManager::BuildWorld()` and binds SDs through a factory.
- GPS-backed source presets plus native `/gps/...` commands.
- Reference physics lists such as `FTFP_BERT_EMZ` and manual physics mode.
- `SensitiveDetector -> ParticleHit -> HitRecord -> ScoringManager`.
- Raw and weighted event energy deposition output.
- Optional cross-section biasing using `G4GenericBiasingPhysics` plus geometry post-build operator attachment.
- Standalone histogram merge tool and Python helper scripts.

Phase status and the support baseline: `docs/ROADMAP.md` and `docs/功能支持矩阵.md`. The single status page is `STATUS.md`.

## Requirements

- CMake 3.10 or newer.
- C++17 compiler.
- Geant4 with matching compiler ABI.
- On Windows, if Geant4/Qt/CLHEP were built with MSVC, build this project with MSVC too.

## Windows Build

Recommended when using an MSVC Geant4 install:

```powershell
cmake -S . -B build_vs -G "Visual Studio 17 2022" -A x64
cmake --build build_vs --config Release
```

Equivalent preset form:

```powershell
cmake --preset vs2022-x64
cmake --build --preset vs2022-release
```

Do not mix MinGW/UCRT object files with MSVC-built Geant4, Qt, or CLHEP libraries. That produces unresolved symbols at link time and should be fixed by using a matching toolchain, not by code workarounds.

## Minimal Run

```powershell
.\build_vs\Release\G4UniversalSim.exe --config config/main.ini --macro macros/run_simple.mac
```

The same macro can also self-load the minimal material, geometry, physics, source, and scoring settings:

```powershell
.\build_vs\Release\G4UniversalSim.exe --macro macros/run_simple.mac
```

## Validation Smoke Tests

Use `macros/run_hit_smoke.mac` when you specifically need to verify the sensitive-detector hit chain. It places a 1 MeV electron source inside a sensitive silicon target so `hits_tN.csv`, event edep, and edep histograms are expected to be produced:

```powershell
.\build_vs2026\Release\G4UniversalSim.exe --macro macros/run_hit_smoke.mac --threads 1 --output test/output/hit_smoke_st
.\build_vs2026\Release\G4UniversalSim.exe --macro macros/run_hit_smoke.mac --threads 2 --output test/output/hit_smoke_mt
```

`macros/test_simple_min.mac` remains a minimal initialization/run smoke test. It may produce no hit rows if the sample source does not deposit energy in a sensitive volume; that does not by itself indicate an SD failure.

Process-level XS biasing has a runtime smoke test:

```powershell
.\build_vs2026\Release\G4UniversalSim.exe --macro macros/run_biasing_process_level_smoke.mac --threads 1 --output test/output/biasing_process_level_smoke
```

This checks initialization, operator attachment, and raw/weighted edep output only. It is not a physics validation of biased vs analog results.

Volume-fraction material construction has a smoke test:

```powershell
.\build_vs2026\Release\G4UniversalSim.exe --macro macros/run_volume_fraction_test.mac --threads 1 --output test/output/volume_fraction_test
```

Only material components are supported for `mode = volume_fraction`; direct element components are rejected with a clear error.

## Outputs

Select the data format with `[output] format = csv | root | both` (default `csv`) or `/AIHL/output/setFormat` before `/run/initialize`.

**ROOT** (`format = root`): one `g4usim.root` per run (`g4usim_rR.root` for later runs) written through Geant4's `G4AnalysisManager`. Worker threads are merged automatically. It contains the `edep_raw`/`edep_weighted` histograms and the `hits`, `events`, `edep_volume`, `edep_particle`, `dose`, `fluence`, `mesh` and `let` ntuples. No ROOT installation is needed to run; read it with `uproot` (`pip install uproot`) or ROOT. Every run also writes `run_metadata.json`. See `docs/输出数据契约.md`.

**CSV** (default):

For the default single-thread configuration, output is written under `output/simple_test/`:

- `hits_t0.csv`
- `event_edep_t0.csv`
- `hist_edep_raw_t0.csv`
- `hist_edep_weighted_t0.csv`
- `edep_volume_summary_t0.csv`
- `edep_particle_summary_t0.csv`
- `run_summary.txt`

If no step deposits energy in a sensitive volume, the hit file may be absent or contain fewer rows than expected, while `event_edep_t0.csv` is still written when event edep output is enabled.

For multi-thread CSV output, merge per-thread files explicitly:

```powershell
python scripts\merge_outputs.py --input test\output\hit_smoke_mt --pattern "hits_t*.csv" --output test\output\hit_smoke_mt\hits_merged.csv
python scripts\merge_outputs.py --input test\output\hit_smoke_mt --pattern "event_edep_t*.csv" --output test\output\hit_smoke_mt\event_edep_merged.csv
.\build_vs2026\Release\mergeHistograms.exe --input test\output\hit_smoke_mt --pattern hist_edep_raw_t*.csv --output test\output\hit_smoke_mt\hist_edep_raw_merged.csv
.\build_vs2026\Release\mergeHistograms.exe --input test\output\hit_smoke_mt --pattern hist_edep_weighted_t*.csv --output test\output\hit_smoke_mt\hist_edep_weighted_merged.csv
```

## Documentation

- [中文使用手册](docs/中文使用手册.md)
- [中文几何配置说明](docs/中文几何配置说明.md)
- [GUI 中文快速使用说明](gui/docs/中文快速使用说明.md)
- [Agent 维护说明](docs/Agent维护说明.md)
