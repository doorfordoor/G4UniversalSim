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

Advanced MicroElec/ElectronCapture support is optional and experimental. LET, dose, and fluence scorers currently expose stubs or light interfaces; `EdepScorer` is the first usable scorer.

## Current Safety Notes

- `mode = volume_fraction` is parsed by the material command parser, but `MaterialFactory` intentionally rejects it because volume fractions have not yet been converted to physically correct mass fractions.
- `gdml` is a placeholder template only. It does not call `G4GDMLParser`; do not run `/run/initialize` with `macros/run_gdml.mac` until real GDML import is implemented.
- STL import is not implemented.
- Hierarchical geometry supports `trd` / `trapezoid` through `G4Trd`, and full `trap` through `G4Trap`; all `trd` / `trap` length parameters are half-lengths.
- `layered_device` propagates `copyNo`, `metadata.*`, and unknown layer keys to `VolumeNode::userProperties`; metadata is not written to hit CSV files yet.
- `/AIHL/output/...`, `/AIHL/app/...`, and `/AIHL/detector/...` are registered by the default executable. Output commands do not include hits/scoring switches; use `/AIHL/scoring/...` for those.
- Importance biasing, weight-window, splitting, and Russian roulette are future work. The currently usable biasing path is process-level XS biasing.
- Multi-thread CSV output is not production-safe yet because per-worker `OutputManager`/`ScoringManager` instances are not fully wired. Use single-thread runs for production CSV output.

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

## Outputs

For the default single-thread configuration, output is written under `output/simple_test/`:

- `hits_t0.csv`
- `event_edep_t0.csv`
- `hist_edep_raw_t0.csv`
- `hist_edep_weighted_t0.csv`
- `edep_volume_summary_t0.csv`
- `edep_particle_summary_t0.csv`
- `run_summary.txt`

If no step deposits energy in a sensitive volume, the hit file may be absent or contain fewer rows than expected, while `event_edep_t0.csv` is still written when event edep output is enabled.

For production CSV output, prefer `--threads 1` until thread-local output and automatic merge are implemented.

## Documentation

- [Usage](docs/USAGE.md)
- [Configuration reference](docs/CONFIG_REFERENCE.md)
- [Module overview](docs/MODULE_OVERVIEW.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
