# G4UniversalSim PySide6 Runner

This directory contains the MVP external runner GUI for G4UniversalSim.

The GUI does not embed Geant4, `G4RunManager`, OpenGL, or Geant4 Qt visualization. It starts the existing `G4UniversalSim.exe` through `QProcess`, captures stdout/stderr, saves logs, and previews lightweight output files.

Round 7C adds a minimal config/macro generation path. The GUI can copy existing material and geometry ini files into a run package, generate `main.ini`, generate `run.mac`, validate the package, and run the generated package through the same CLI path.

Round 7D adds lightweight material and geometry selectors/previews. These previews are static helpers only: they do not edit the original `materials.ini` or `geometry.ini`, and they do not replace Geant4 initialization checks.

Round 7E expands the Output page with file classification, structured run summary preview, safer CSV preview, per-thread output detection, and merge-tool entry points for CSV and histogram outputs.

Round 7F adds run history and package management. The GUI can scan a runs root, classify run packages, load a historical `project_snapshot.json`, duplicate a package without copying old output/log files, and rerun the duplicated package.

Round 7G is a checkpoint and polish pass. It adds manual QA notes, packaging-prep notes, lightweight smoke scripts, clearer run-state/status feedback, merge-button state handling, and more actionable log hints for common Geant4/configuration errors.

Round 7H refactors the GUI shell layout for wider desktop use, gives Config Builder a splitter-based setup/workspace layout, and adds read-only editable model foundations for later material/geometry/source/physics/scoring editors.

Round 7I upgrades the Config Builder Materials tab from preview-only to a Materials Editor MVP. It supports adding, duplicating, deleting, validating, and editing NIST aliases plus `mass_fraction`, `volume_fraction`, and `atom_count` material rows. Edited materials are written only into generated run packages; the original `materials.ini` is not overwritten.

Round 7J upgrades Source, Physics, and Scoring from simple form fields to editable models. The Config Builder Run Config tab can edit source particle/energy/position/direction, reference physics list/default cut/biasing hook, and scoring hits/event_edep/edep histogram settings. Generated `main.ini` reflects the editor models and is previewed before package generation.

Round 7K upgrades Geometry from static preview to a Simple Box / Layered Device editor MVP. The Config Builder Geometry tab can edit `simple_box` `[world]/[target]` fields and `layered_device` layer rows, validate material/sensitive/biasing consistency, preview generated `geometry.ini`, and write edited geometry only into generated run packages. Hierarchical, boolean, array, shielding, GDML, and STL remain preview-only.

Round 7K-check adds backend verification for GUI-generated geometry packages. `gui/smoke_tests/smoke_geometry_backend_package.py` creates Simple Box and Layered Device packages, checks generated `main.ini`/`geometry.ini`/`validation_report.txt`, and optionally runs `G4UniversalSim.exe` when `G4USIM_EXE` is set.

Round 7K-P adds an optional 3D Preview MVP for validated GUI geometry models. The preview builds a lightweight `PreviewScene` from the current Simple Box / Layered Device geometry plus Source editor direction, shows source arrows and sensitive/bias labels, and falls back to a text summary when PyVista dependencies are not installed. This is an approximate configuration preview; it is not Geant4 visualization, navigator tracking, overlap checking, or a replacement for `/run/initialize`.

## Install

```powershell
cd gui
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Optional 3D preview dependencies:

```powershell
pip install -r requirements-3d.txt
```

The GUI starts without these optional packages and displays a text fallback in the **3D Preview** tab.
When `QT_QPA_PLATFORM=offscreen` is set, the GUI also uses the text fallback by default because VTK/OpenGL on Windows can fail before Python can recover. Use a normal desktop Qt backend for visual PyVista QA, or set `G4USIM_ENABLE_OFFSCREEN_PYVISTA=1` only when you know offscreen OpenGL is available.

## Start

```powershell
python main.py
```

## Checkpoint Docs And Smoke Tests

Round 7 checkpoint material lives under:

- `gui/docs/GUI_CHECKPOINT_ROUND7.md`
- `gui/docs/MANUAL_QA_CHECKLIST.md`
- `gui/docs/PACKAGING_PREP_NOTES.md`
- `gui/docs/中文快速使用说明.md`
- `gui/docs/EDITABLE_CONFIG_PLAN.md`

Lightweight smoke checks can be run from the workspace root:

```powershell
python -m compileall gui
python gui/smoke_tests/smoke_project_io.py
python gui/smoke_tests/smoke_parsers.py
python gui/smoke_tests/smoke_output_tools.py
python gui/smoke_tests/smoke_history.py
python gui/smoke_tests/smoke_geometry_editor.py
python gui/smoke_tests/smoke_geometry_backend_package.py
python gui/smoke_tests/smoke_preview3d.py
```

To run the generated geometry packages through the real C++ backend:

```powershell
$env:G4USIM_EXE="D:\Geant4\G4UniversalSim\build_vs2026\Release\G4UniversalSim.exe"
python gui/smoke_tests/smoke_geometry_backend_package.py
```

## Basic Workflow

1. Select `G4UniversalSim.exe`.
2. Select an existing `config/main.ini` or leave config empty when the macro is self-contained.
3. Select an existing macro such as `macros/test_simple_min.mac`.
4. Select an output directory.
5. Set `threads`, optional `seed`, and optional `run name`.
6. Click **Build command** to preview the command.
7. Click **Run**.
8. Watch stdout/stderr in real time.
9. Use **Stop** to request graceful termination or **Kill** to force-stop.
10. Refresh the Output page to preview `run_summary.txt`, logs, and small CSV files.
11. Use the Output page Merge tab to merge per-thread CSV/histogram files when tools are available.
12. Use the Run History tab to revisit generated packages and duplicate/rerun previous configurations.

## Generate a Run Package

Open the **Config Builder** tab and fill:

- Run name, threads, optional seed, BeamOn count, check-overlaps flag.
- Existing materials config path.
- Existing geometry config path and geometry template.
- Source preset, particle, energy, position, and direction.
- Reference physics list and default cut.
- Scoring switches and edep histogram range.

Click **Validate** first. If there are no errors, click **Generate Package** or **Generate and Run**.

The Input Files area includes:

- Materials Editor table: enabled flag, material name, mode, density, component preview, and validation status.
- Geometry tab: Simple Box editor, Layered Device editor, and preview for unsupported templates.
- Geometry volume table: ordinary volumes only, shown in the Geometry preview sub-tab.
- Boolean operation table: `volume.<name>.boolean.<index>` sections are summarized separately and are not treated as ordinary volumes.
- 3D Preview tab: optional approximate Simple Box / Layered Device preview plus source arrow. Missing PyVista dependencies use a text fallback.
- Raw previews for material and geometry ini files.
- Common NIST quick list for reference/copying.
- Warning/error panes for parser messages.

Validation also checks:

- Geometry material references against edited materials when the Materials Editor is dirty; otherwise against the selected materials file plus a small common NIST quick list.
- Source, Physics, and Scoring editor model validation.
- Sensitive and bias volume summaries.
- Boolean-tool unsupported keys such as `material`, `sensitive`, `bias`, `region`, `cuts`, and `visual`.
- Obvious geometry template/config mismatches.

The generated package layout is:

```text
runs/<timestamp>_<run_name>/
  config/
    main.ini
    materials/material.ini
    geometry/geometry.ini
  macros/run.mac
  logs/
  output/
  project_snapshot.json
  validation_report.txt
```

After generation, the Project page is automatically switched to:

- config = `<package>/config/main.ini`
- macro = `<package>/macros/run.mac`
- output = `<package>/output`

The package can be reproduced outside the GUI:

```powershell
G4UniversalSim.exe --config <package>/config/main.ini --macro <package>/macros/run.mac --output <package>/output --threads 1
```

## Output Viewer

The Output page supports both standalone output directories and generated run packages.

Tabs:

- **Overview**: package root, output directory, file counts, thread CSV counts, merged file counts.
- **Preview**: selected text/config/macro/json/csv file preview.
- **Run Summary**: lightweight structured parsing of `run_summary.txt` plus raw text.
- **CSV Preview**: safe preview using Python's standard `csv` module. The row limit can be 50, 200, or 1000 rows. Files larger than 50 MB are not fully loaded.
- **Merge**: detects available merge tasks and runs them through `QProcess`.
- **Logs**: quick view of `stdout.log`, `stderr.log`, and `validation_report.txt`.

Recognized output types include:

- `hits_t*.csv`
- `event_edep_t*.csv`
- `hist_edep_raw_t*.csv`
- `hist_edep_weighted_t*.csv`
- `hits_merged.csv`
- `event_edep_merged.csv`
- `hist_edep_raw_merged.csv`
- `hist_edep_weighted_merged.csv`
- `run_summary.txt`
- `stdout.log` / `stderr.log`
- `validation_report.txt`
- `project_snapshot.json`

## Merge Tools

The GUI calls existing tools rather than reimplementing merge logic:

```powershell
python scripts/merge_outputs.py --input <outputDir> --pattern "hits_t*.csv" --output <outputDir>/hits_merged.csv
python scripts/merge_outputs.py --input <outputDir> --pattern "event_edep_t*.csv" --output <outputDir>/event_edep_merged.csv
mergeHistograms.exe --input <outputDir> --pattern hist_edep_raw_t*.csv --output <outputDir>/hist_edep_raw_merged.csv
mergeHistograms.exe --input <outputDir> --pattern hist_edep_weighted_t*.csv --output <outputDir>/hist_edep_weighted_merged.csv
```

`merge_outputs.py` is located under the workspace `scripts/` directory and is run with the same Python executable that launched the GUI.

`mergeHistograms.exe` is searched in:

1. `build_vs2026/Release`
2. `build/Release`
3. `build_vs/Release`
4. Debug variants of those folders

Merge logs are written under the package `logs/` directory when a package root is known; otherwise they go under `<outputDir>/logs/`.

Merged files are not overwritten automatically. If a target merged CSV already exists, the corresponding merge task is marked unavailable.

## Run History

The **Run History** tab scans a runs root and displays generated packages. A directory is treated as a package when it contains one of:

- `project_snapshot.json`
- `config/main.ini` plus `macros/run.mac`
- `output/` plus `logs/`

Displayed fields include:

- timestamp and run name
- status
- exit code
- geometry template
- thread count and BeamOn count
- output file counts
- merge status
- package path

The scanner reads only metadata, small text files, summaries, and filenames. It does not load large CSV files.

## run_status.json

When a run starts, the GUI writes:

```text
<package>/logs/run_status.json
```

or, for standalone output directories:

```text
<outputDir>/logs/run_status.json
```

The file records:

- state
- startedAt / finishedAt
- exitCode
- command
- program and arguments
- workingDirectory

This metadata is GUI-only and is never required by the C++ executable.

## Load Snapshot / Duplicate / Rerun

**Load Snapshot into Project** restores GUI state from a historical `project_snapshot.json`. It does not automatically run the simulation.

**Duplicate Package** copies:

- `config/`
- `macros/`
- `project_snapshot.json`
- `validation_report.txt`

It creates fresh empty:

- `logs/`
- `output/`

It does not copy old CSV/log/merge output files.

**Duplicate and Rerun** duplicates the package, points the Project page at the new package, and starts the run through the normal QProcess path.

The default behavior avoids overwriting old run packages or mixing old and new output files.

## Recent Projects

Recent project paths and last workspace/runs root are saved in a lightweight JSON state file under the user home directory. The project contents themselves remain in the project JSON file chosen by the user.

The generated command follows the current CLI contract:

```text
G4UniversalSim.exe --config <configPath> --macro <macroPath> --output <outputDir> --threads <N> --seed <N>
```

If `seed` is empty, `--seed` is not passed. If `config` is empty, the GUI can run with macro only. A macro is required.

## Project JSON

The **Save project** and **Load project** buttons store GUI state only:

```json
{
  "schema": "G4UniversalSimProject",
  "version": 1,
  "projectName": "demo",
  "executable": "D:/Geant4/G4UniversalSim/build_vs2026/Release/G4UniversalSim.exe",
  "workspaceRoot": "D:/Geant4/G4UniversalSim",
  "configPath": "D:/Geant4/G4UniversalSim/config/main.ini",
  "macroPath": "D:/Geant4/G4UniversalSim/macros/test_simple_min.mac",
  "outputDir": "D:/Geant4/G4UniversalSim/gui_runs/demo/output",
  "threads": 1,
  "seed": "12345",
  "runName": "demo_run"
}
```

The JSON file is not an input to `G4UniversalSim.exe`; config and macro files remain the simulation inputs.

## Current Limits

- Materials Editor is MVP-level: it supports row-level editing and validation, but not a full material database or chemistry parser.
- Source/Physics/Scoring editors are MVP-level. Manual physics editing, advanced source modes, and LET/Dose/Fluence controls are intentionally not exposed.
- Geometry Editor is MVP-level: `simple_box`, `layered_device`, hierarchical volumes, and sequential boolean operations are editable/generated. `array`, `shielding`, GDML, and STL remain preview-only.
- Boolean tools are solid operands, not ordinary volumes. They do not have material/sensitive/bias state; the target volume keeps those properties.
- 3D Preview is approximate and optional. It shows boolean tools as cutter/wireframe volumes and does not render real CSG, GDML/STL, embed Geant4 visualization, or validate overlaps.
- No biasing rule editor.
- Source, physics, and scoring forms are intentionally minimal.
- No Geant4 OpenGL/Qt view embedding.
- No large CSV loading.
- No histogram plotting.
- No parameter scan UI.
- Merge is limited to existing `merge_outputs.py` and `mergeHistograms.exe`; no physics analysis is performed by the GUI.
- Delete/archive is not implemented; packages are never hard-deleted by the GUI MVP.
- No packaging into a standalone executable.
