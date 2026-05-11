# Usage

## Run With `main.ini`

```powershell
.\build_vs\Release\G4UniversalSim.exe --config config/main.ini --macro macros/run_simple.mac
```

`config/main.ini` loads materials, geometry, physics, source, scoring, and biasing state. The macro then executes runtime commands such as `/run/initialize` and `/run/beamOn`.

## Run With Only A Macro

```powershell
.\build_vs\Release\G4UniversalSim.exe --macro macros/run_simple.mac
```

`macros/run_simple.mac` is self-contained for the simple box example: it loads materials, selects the `simple_box` template, configures a proton beam, enables scoring, initializes Geant4, and runs 100 events.

## Interactive UI

```powershell
.\build_vs\Release\G4UniversalSim.exe --config config/main.ini --ui
```

You can then enter Geant4 and `/AIHL/...` commands manually. Native `/gps/...` commands remain available.

## Source Commands

```text
/AIHL/source/preset proton_beam
/AIHL/source/particle proton
/AIHL/source/energy 10 MeV
/AIHL/source/point 0 0 -1 mm
/AIHL/source/direction 0 0 1
/AIHL/source/print
```

## Physics Commands

```text
/AIHL/physics/setReferenceList FTFP_BERT_EMZ
/AIHL/physics/setDefaultCut 1 mm
/AIHL/physics/enableBiasing false
/AIHL/physics/print
```

Manual mode is still available by clearing the reference list and adding modules explicitly.

## Scoring Commands

```text
/AIHL/scoring/enable true
/AIHL/scoring/hits true
/AIHL/scoring/eventEdep true
/AIHL/scoring/edep true
/AIHL/scoring/setEdepHistogram bins=100 min=0 eV max=10 MeV
/AIHL/scoring/setWeightedEdepHistogram bins=100 min=0 eV max=10 MeV
```

Scoring stores both raw energy deposition and weighted energy deposition. Weighted values use `hit.edep * hit.weight`, which is important when biasing is active.

## Biasing Commands

```text
/AIHL/biasing/enable true
/AIHL/biasing/xs/addParticle proton
/AIHL/biasing/xs/addProcessForParticle proton protonInelastic
/AIHL/biasing/xs/setFactor proton 100
/AIHL/biasing/xs/addVolume Target
/AIHL/physics/enableBiasing true
```

Biasing requires two pieces: the physics hook (`G4GenericBiasingPhysics`) and post-build operator attachment through `GeometryRegistry`. Configure biasing before `/run/initialize`.

## Advanced Physics

```text
/AIHL/physics/enableMicroElec true
/AIHL/physics/setMicroElecRegion SV
/AIHL/physics/enableElectronCapture true
/AIHL/physics/setElectronCaptureThreshold 16.7 eV
```

MicroElec/ElectronCapture is optional and experimental. It is registered through PhysicsManager/PhysicsFactory and does not change DetectorConstruction.

## Post-Processing

Merge histogram CSV files:

```powershell
.\build_vs\Release\mergeHistograms.exe --input output/simple_test --pattern hist_edep_raw_t*.csv --output output/simple_test/merged_edep_raw.csv
```

Plot a histogram:

```powershell
python scripts/plot_hist.py --input output/simple_test/hist_edep_raw_t0.csv --output output/simple_test/edep.png --title "Event Edep"
```

Merge CSV output files:

```powershell
python scripts/merge_outputs.py --input output/simple_test --pattern "event_edep_t*.csv" --output output/simple_test/event_edep_merged.csv
```
