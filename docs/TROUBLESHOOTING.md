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
/AIHL/biasing/xs/addParticle proton
/AIHL/biasing/xs/addVolume Target
/AIHL/physics/enableBiasing true
```

Operators attach through the geometry post-build callback after `DetectorConstruction::Construct()` has rebuilt the registry.

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
