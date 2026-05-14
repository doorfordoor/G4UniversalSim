# Troubleshooting

## MinGW Linking MSVC Geant4 Libraries

Symptom: many unresolved symbols from Geant4, Qt, or CLHEP at link time.

Cause: toolchain ABI mismatch, commonly MinGW/UCRT object files linked against MSVC-built `.lib` files.

Fix: build with a matching compiler. For an MSVC Geant4 install:

```powershell
cmake -S . -B build_vs -G "Visual Studio 17 2022" -A x64
cmake --build build_vs --config Release
```

## `/run/initialize` Fails

Check that materials and geometry were loaded before initialization. `macros/run_simple.mac` is self-contained; if using your own macro, include material and geometry commands or run with `--config config/main.ini`.

Known placeholder features that must not be initialized yet:

- `template = gdml` / `macros/run_gdml.mac`: GDML import is placeholder-only and does not call `G4GDMLParser`.
- STL import: no parser/backend exists.

`shape = trd` / `shape = trapezoid` and `shape = trap` are now wired to `G4Trd` and `G4Trap`. If a `trap` geometry still fails during `/run/initialize`, check that all required parameters are present and that the resulting faces satisfy Geant4 `G4Trap` planarity constraints.

If you need a runnable example, use `macros/run_simple.mac`, `run_layered.mac`, `run_hierarchical.mac`, `run_array.mac`, or `run_shielding.mac`.

## `config/main.ini` Not Found

Run from the project root or pass an absolute path:

```powershell
.\build_vs\Release\G4UniversalSim.exe --config D:\path\to\config\main.ini --macro macros/run_simple.mac
```

## Geometry Root Node Is Empty

Usually the geometry template or config failed to load. Verify:

```text
/AIHL/geometry/setTemplate simple_box
/AIHL/geometry/loadConfig config/geometry/simple_box.ini
/AIHL/geometry/printTree
```

`simple_box.ini` must contain `[world]/size` and a world material.

## Material Not Found

Load materials before geometry build:

```text
/AIHL/material/load config/materials/material.ini
```

For NIST materials, names such as `G4_AIR`, `G4_Si`, and `G4_WATER` should be available through Geant4.

Do not use `mode = volume_fraction` in runnable material files yet. The parser recognizes it, but `MaterialFactory` intentionally reports it as reserved and not implemented.

## Sensitive Volume Has No Hits

Check that the geometry marks the target as `sensitive = true`, the source intersects it, and scoring is enabled. `SensitiveDetector` skips zero-edep hits by default, so a run with no energy deposit may produce no hit rows.

## `event_edep_t0.csv` Is Not Generated

Enable event edep output:

```text
/AIHL/scoring/enable true
/AIHL/scoring/eventEdep true
```

The file is created lazily when events end.

## Biasing Operator Does Not Attach

Biasing needs both the physics hook and operator attachment:

```text
/AIHL/biasing/enable true
/AIHL/biasing/xs/addRule proton protonInelastic
/AIHL/biasing/xs/setRuleFactor proton protonInelastic 3.0
/AIHL/biasing/xs/addRuleVolume proton protonInelastic Target
/AIHL/physics/enableBiasing true
```

Operators attach through the geometry post-build callback after `DetectorConstruction::Construct()` has rebuilt the registry.

If you use the old `[biasing.xs]` section or old macro commands such as `/AIHL/biasing/xs/addParticle`, the manager expands them as legacy shorthand into particle/process rules and prints a warning. Make sure the legacy `processes` list is not empty.

## Biasing Process Name Fails Validation

Process-level XS rules are validated after physics construction, when particle process managers exist. If `/run/initialize` reports that a process was not found, check:

```text
[biasing.xs.proton.protonInelastic]
```

The process part must match an actual Geant4 process name for that particle and the selected physics list. Wrong names are reported as explicit warnings or errors instead of being silently ignored.

For charged particles, the framework emits a warning that XS biasing needs extra validation because cross sections can vary during a step due to energy loss. Compare raw and weighted scoring carefully.

Importance biasing, weight-window, splitting, and Russian roulette are not implemented. If a macro or config appears to use them, treat it as future-work documentation rather than a runnable setup.

## `/AIHL/output`, `/AIHL/app`, Or `/AIHL/detector` Is Unknown

These command groups are registered by the current default executable. If they are unknown, rebuild the executable and make sure you are running the updated binary. `/AIHL/output/...` currently exposes output directory, thread suffix, print, flush, and close commands only; hits/scoring switches remain under `/AIHL/scoring/...`.

## LET, Dose, Or Fluence Output Looks Empty

`LETScorer`, `DoseScorer`, and `FluenceScorer` are currently stub/no-op or minimal command surfaces. Use hits, event edep, and `EdepScorer` outputs for runnable scoring. Do not interpret LET/dose/fluence stub output as validated physical quantities.

## Multi-Thread CSV Output Is Inconsistent

Current `OutputManager` / `ScoringManager` wiring is not production-safe for multi-thread CSV output. Use `--threads 1` for production CSV runs until per-thread managers and merge are implemented. Existing merge tools are post-processing helpers, not proof that runtime writes are race-free.

## Reference Physics List Not Found

Use a Geant4 reference list available in your installation, for example:

```text
/AIHL/physics/listAvailableReferences
/AIHL/physics/setReferenceList FTFP_BERT_EMZ
```

Some lists vary by Geant4 version.

## Qt Or Visualization Problems

If Qt visualization fails, run in batch mode with a macro and avoid `--ui`. Make sure your Geant4 build and this project use the same compiler and Qt runtime.

## PART002: `G4ParticleTable::CheckReadiness`

This indicates a particle lookup occurred before a physics list was assigned to `G4RunManager`. `SourceManager` now creates GPS lazily; keep source particle application after physics list registration or let `PrimaryGeneratorAction` request it at event generation time.

## MicroElec Region Warning

If MicroElec reports that region `SV` is missing, verify the geometry config assigns `region = SV` to the sensitive volume. The warning is non-fatal; ElectronCapture will only act in matching regions during tracking.
