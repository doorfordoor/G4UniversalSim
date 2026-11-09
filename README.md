# G4UniversalSim

中文入口：[完整使用手册](docs/中文使用手册.md) · [文档导航](docs/README.md)

## Project status

This repository is a research and engineering workbench (C++17 backend + PySide6 GUI), not a 1.0 release.
Stage completion is maintained in [the roadmap](docs/ROADMAP.md#current-roadmap).
For active work and handoff, start at [STATUS.md](STATUS.md). Feature coverage and limits live in the
[support matrix](docs/功能支持矩阵.md).

- Backend: Geant4 11.3.2/11.4.3 compatible builds. Validated scope (F2 controlled session and replay,
  stage evidence) is recorded per stage in the matrix and the final evidence directories.
- GUI: editor/runner for generated configuration packages; some editors remain partial or
  experimental (matrix §3).
- Software acceptance (tests, CI, receipts) is separate from physics validation.
- A stage receipt is not a physics benchmark and does not promise cross-platform bitwise identity.

## Linux Build

Validated recipe (Ubuntu/WSL2 and CI; Geant4 from conda-forge or an equivalent prefix):

```bash
cmake -S . -B build_linux -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="<Geant4 prefix>"
cmake --build build_linux -j"$(nproc)"
./build_linux/G4UniversalSim --check-geant4-data
./build_linux/G4UniversalSim --capabilities
```

Environment variables, data discovery, GUI system libraries, CI differences and Geant4 11.4 toolchain
requirements are documented in [docs/Linux构建与验证.md](docs/Linux构建与验证.md).

## Installed package

Release packages are described in [packaging/README-package.md](packaging/README-package.md):
`bin\G4UniversalSim.exe` (backend with Geant4/Xerces/VC++ DLLs), `gui\G4UniversalSimGUI.exe`
(no Python required), and the prerequisite Geant4 **data** (not bundled). Data can be given through the
installer's “Geant4 数据文件夹” page (`bin\geant4-data.txt`), by editing that file, or with
`GEANT4_DATA_DIR`; verify with `bin\G4UniversalSim.exe --check-geant4-data`.

The source entry and the installed entry use the same command line and configuration files; only the
executable path differs. The GUI selects its backend on the Project page or via
“环境 → 环境发现与诊断”.

## Configuration packages

A run package contains a main INI plus the materials/geometry files it references and a `run.mac`
wrapper:

- `main.ini` — `[run]`, `[output]`, `[materials]`, `[geometry]`, `[physics]`, `[source]`, `[scoring]`
- `materials.ini`, `geometry.ini` (or inline sections)
- `run.mac` — generated `/run/initialize` + `/run/beamOn` wrapper

Run it from the source build or the installed package with the same `--config` arguments (see Minimal
Run). The GUI writes generated packages under its runs root; the installed GUI writes to
`Documents\G4UniversalSim\gui_runs` by default.

Advanced F2 controlled sessions use `--session-server` (see [docs/会话协议.md](docs/会话协议.md)); they
are optional, and the old `--macro`/csh workflows are unchanged.

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

- CMake 3.21+ and a C++17 compiler.
- Geant4 11.3.2 or 11.4.3 with matching compiler ABI, plus its physics data sets.
- Windows: Visual Studio 2026 with the "Desktop development with C++" workload (MSVC ABI);
  do not mix MinGW/UCRT objects with MSVC Geant4/Qt/CLHEP.
- Linux: GCC toolchain; GUI additionally needs the system libraries listed in
  [docs/Linux构建与验证.md](docs/Linux构建与验证.md).
- Python 3.11 for the GUI and helper scripts only (`gui/requirements.txt`); the backend needs no Python.
- Geant4 data: set the data variables (for example `GEANT4_DATA_DIR`) or the installer's
  `bin/geant4-data.txt`; verify with `--check-geant4-data`.

## Windows Build

Presets are the supported path (Visual Studio 2026 with CMake support):

```powershell
cmake --preset vs2026-x64
cmake --build --preset vs2026-release
```

Raw equivalent (same preset, for reference):

```powershell
cmake -S . -B build_vs2026 -G "Visual Studio 18 2026" -A x64
cmake --build build_vs2026 --config Release
```

Products: `build_vs2026\Release\G4UniversalSim.exe` and `build_vs2026\Release\mergeHistograms.exe`.
`CMakePresets.json` defines only `vs2026-x64`, `vs2026-release` and `vs2026-debug`; older preset names
that may appear in old notes are not usable.

## Minimal Run

Check the Geant4 data first; `required_complete` must be `true` before any run:

```powershell
.\build_vs2026\Release\G4UniversalSim.exe --check-geant4-data
```

Then run the example configuration into a fresh output directory:

```powershell
.\build_vs2026\Release\G4UniversalSim.exe --config config/main.ini --macro macros/run_simple.mac --output test\output\minimal_run
```

Success means the process exits 0 and **this run's new** `run_summary.txt` reports the planned events as
completed (see Outputs). A dry-run, an interactive session without a run, or a zero-run exit is not a
simulation success.

## Validation Smoke Tests

交互执行请使用 `--ui --ui-session csh`。裸 `--ui` 和未选择 csh 的 INI `interactive=true` 会在执行前明确拒绝；原生 Qt/其他会话不能实施当前的命令与生命周期守卫。Python 桌面 GUI 的正常运行和预览仍可使用。旧偏置结果需要以 Q1 修复后的版本重新运行，worker 实际偏置与步前权重修复会改变结果；运行通过不等于物理基准通过。

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

- [中文使用手册](docs/中文使用手册.md) — full end-user manual
- [GUI 中文快速使用说明](gui/docs/中文快速使用说明.md) — GUI first run and operations
- [安装包说明](packaging/README-package.md) — installed package and data prerequisites
- [Linux 构建与验证](docs/Linux构建与验证.md)
- [环境辅助安装](docs/环境辅助安装.md)
- [中文几何配置说明](docs/中文几何配置说明.md)
- [功能支持矩阵](docs/功能支持矩阵.md) · [ROADMAP](docs/ROADMAP.md) · [STATUS](STATUS.md)
- [Agent 维护说明](docs/Agent维护说明.md)
