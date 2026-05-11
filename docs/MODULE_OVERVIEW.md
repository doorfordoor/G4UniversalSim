# Module Overview

## Core

`SimulationManager` owns the long-lived managers and messengers, reads `main.ini`, and creates Geant4 user initialization objects for the run manager. It does not own `DetectorConstruction`, `PhysicsList`, or `ActionInitialization` after they are released to Geant4.

## Config

`ConfigManager`, `IniReader`, and `ConfigValue` provide ini loading and typed accessors.

## Utils

Utility code covers strings, files, unit parsing, Geant4 naming helpers, and command parsing shared by messengers.

## Output

`OutputManager` writes hits, event energy deposition, histograms, summaries, and run metadata. It is not thread-safe; current output uses per-thread suffixes such as `_t0`.

## Materials

`MaterialManager` loads NIST material aliases and custom material definitions. Geometry requests materials through this manager.

## Geometry

`GeometryManager` stores template/config/root state and owns `GeometryRegistry`. `VolumeBuilder` converts `VolumeNode` trees into solids, logical volumes, placements, regions, and production cuts.

## Templates

Template classes such as `SimpleBoxTemplate`, `LayeredDeviceTemplate`, `ArrayTemplate`, and related templates generate `VolumeNode` trees from ini files.

## Detector

`DetectorConstruction` is the Geant4 geometry entry point. It calls `GeometryManager::BuildWorld()`, binds sensitive detectors from a factory, and invokes a post-build callback for biasing operators.

## Physics

`PhysicsManager` stores reference/manual physics configuration. `PhysicsFactory` maps aliases and creates Geant4 constructors. Reference mode uses `G4PhysListFactory`; manual mode uses the project `PhysicsList` wrapper.

## Source

`SourceManager` lazily owns `G4GeneralParticleSource`, preserving Geant4 initialization order. `PrimaryGeneratorAction` requests the GPS at event generation time.

## Actions

`ActionInitialization` registers `PrimaryGeneratorAction`, `RunAction`, `EventAction`, `SteppingAction`, and `TrackingAction`. Run and event actions call `ScoringManager` lifecycle methods.

## Hits

`SensitiveDetector` converts `G4Step` data into `ParticleHit`, then `HitRecord`, then calls `ScoringManager::ScoreHit()`. It does not write files directly.

## Scoring

`ScoringManager` coordinates hit output, event edep output, and registered scorers. `EdepScorer` writes raw and weighted event edep histograms and simple summaries. LET, dose, and fluence are stubs for later expansion.

## Biasing

`BiasingManager` stores cross-section biasing rules and attaches `BiasingMultiParticleXS` operators after geometry construction. Physics registration of `G4GenericBiasingPhysics` remains in the physics layer.

## Advanced Physics

`MicroElecPhysics` and `ElectronCapture` are optional. Electron capture acts only on electrons in the configured region below the threshold and reports energy through Geant4 particle change, not through direct scoring calls.

## Tools/Scripts

`mergeHistograms` is a standalone C++17 executable that does not link Geant4. Python scripts in `scripts/` plot histograms, merge CSV outputs, and run simple parameter scans.
