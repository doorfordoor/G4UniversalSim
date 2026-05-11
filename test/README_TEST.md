# G4UniversalSim End-to-End Test Suite

This folder contains self-contained end-to-end test inputs for the current G4UniversalSim implementation. No files under `config/`, `macros/`, `docs/`, or the project root examples are required by these tests.

## Layout

- `main_layered_device.ini`: main configuration for the layered-device run.
- `main_hierarchical.ini`: main configuration for the hierarchical run.
- `materials/test_materials.ini`: material aliases and one simple custom material.
- `geometry/layered_device_test.ini`: `LayeredDeviceTemplate` geometry.
- `geometry/hierarchical_test.ini`: `HierarchicalVolumeTemplate` geometry.
- `biasing/*.ini`: biasing settings mirrored in the main configs for documentation and reuse.
- `macros/*.mac`: full command-driven macro tests.
- `output/*/.gitkeep`: output directories; scripts write `run.log` here.
- `scripts/run_tests.ps1`, `run_tests.bat`, `run_tests.sh`: convenience runners.

## Run

From the repository root:

```powershell
.\test\scripts\run_tests.ps1 -Executable .\build\Release\G4UniversalSim.exe
```

or:

```cmd
test\scripts\run_tests.bat build\Release\G4UniversalSim.exe
```

On Linux/macOS-like shells:

```bash
bash test/scripts/run_tests.sh ./build/G4UniversalSim
```

Each run executes the matching main ini plus macro and writes a console log to:

- `test/output/layered_device/run.log`
- `test/output/hierarchical/run.log`

The main ini files intentionally include the same physics, biasing, source, and scoring state that the macros exercise. In the current application startup flow, Geant4 user initialization objects are created before the macro is executed, so config-driven setup is the reliable path for physics-list and generic-biasing registration. The macros still call the real messenger commands to cover and print those command surfaces before `/run/initialize`.

## Verified Interface Choices

The test files were based on the current source implementation:

- Material ini supports `[Alias] material = G4_*`, `[element.NAME]`, and `[material.NAME]`.
- Geometry commands use `/AIHL/geometry/setTemplate`, `/AIHL/geometry/loadConfig`, `/AIHL/geometry/checkOverlaps`, `/AIHL/geometry/print`, and `/AIHL/geometry/printTree`.
- `layered_device` uses `[world]`, `[layers]`, and `[layer.NAME]` sections. It supports `thickness`, `xy`, `material`, `position` only when `auto_stack=false`, `rotation`, `sensitive`, `bias`, `region`, production cuts, and `vis.*`.
- `hierarchical` uses generic `[world]` and `[volume.NAME]` sections. It supports `parent`, `shape`, `size`, `parameters`, `material`, `position`, `rotation`, `sensitive`, `bias`, `region`, production cuts, `vis.*`, and unknown keys as user properties.
- `copyNo` is supported only through generic geometry user properties read by `VolumeBuilder`; therefore it is used in the hierarchical test, not the layered-device test.
- Physics commands use `/AIHL/physics/setReferenceList`, `/AIHL/physics/setDefaultCut`, `/AIHL/physics/setCut`, `/AIHL/physics/setRegionCut`, `/AIHL/physics/enableBiasing`, `/AIHL/physics/verbose`, and `/AIHL/physics/print`.
- Source commands use `/AIHL/source/preset`, `/AIHL/source/particle`, `/AIHL/source/energy`, `/AIHL/source/planeBeam`, and `/AIHL/source/print`.
- Scoring commands use `/AIHL/scoring/enable`, `hits`, `eventEdep`, `edep`, `let`, `dose`, `fluence`, `autoCreateScorers`, histogram commands, `verbose`, and `print`.
- Biasing macro commands currently cover cross-section biasing through `/AIHL/biasing/xs/...`.

## Current Limitations Reflected Here

- `OutputMessenger` has no implemented `/AIHL/output/...` commands, so output directories are configured through main ini and runner `--output`.
- Biasing has an ini parser through `[biasing]` and `[biasing.xs]`; there is no standalone macro command to load an external biasing ini, so the biasing ini files are mirrored in the two main configs and expanded as real commands in the macros.
- Importance biasing, weight-window biasing, and splitting/Russian roulette do not have usable messenger commands or ini parser support in the current implementation, so they are documented here rather than configured.
- `LayeredDeviceTemplate` does not consume arbitrary metadata keys or copy numbers, so the layered geometry file avoids unsupported metadata/copy-number fields.
- The generic hierarchical parser accepts user properties, so `metadata.role`, `purpose`, and `copyNo` are used there.
