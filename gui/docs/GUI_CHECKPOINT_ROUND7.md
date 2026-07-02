# G4UniversalSim GUI Checkpoint Round 7

This checkpoint summarizes the PySide6 GUI after Rounds 7B-7G.

## Completed Rounds

| Round | Scope | Status |
|---|---|---|
| 7B | External QProcess runner | Done |
| 7C | Config / macro / run package writer | Done |
| 7D | Materials / geometry static preview and validation | Done |
| 7E | Output viewer and merge tools | Done |
| 7F | Run history and package manager | Done |
| 7G | Polish, QA docs, smoke scripts | Done |
| 7H | Global layout shell and editable model foundation | Done |
| 7I | Materials Editor MVP | Done |
| 7J | Source / Physics / Scoring Editor MVP | Done |
| 7K | Simple Box / Layered Device Geometry Editor MVP | Done |
| 7K-check | Backend smoke for GUI-generated Simple Box / Layered Device packages | Done |
| 7K-P | Optional 3D Preview MVP for Simple Box / Layered Device + source arrow | Done |
| 7L | Hierarchical / Boolean Geometry Editor MVP | Done |

## Capability Matrix

| Module | Implemented | Verification | Known limits | Blocks packaging |
|---|---|---|---|---|
| Project Page | executable/config/macro/output/project JSON | compileall, offscreen smoke | no advanced project templates | No |
| Config Builder | package generation with editable materials, geometry, and run config | package writer smoke | array/shielding/GDML/STL remain preview-only | No |
| Materials Editor | NIST alias and simple custom material editing | materials editor smoke | no chemistry parser or material database | No |
| Geometry Editor | `simple_box`, `layered_device`, hierarchical volumes, and sequential boolean op editing/generation | geometry editor smoke, hierarchical/boolean smoke | no array/shielding/GDML/STL editing; boolean 3D preview is approximate | No |
| Geometry Backend Smoke | generated geometry package initialization/beamOn | backend package smoke with optional `G4USIM_EXE` | current tested backend emitted only `t0` files for `--threads 2` | No |
| 3D Preview | optional approximate Simple Box / Layered Device / hierarchical / boolean-tool preview and source arrow | preview3d smoke, hierarchical/boolean smoke, offscreen widget smoke | no Geant4 Vis, GDML/STL, real CSG, picking, or overlap checking | No |
| Run Config Editors | Source/Physics/Scoring editable models | run config editor smoke | no manual physics, advanced source, LET/Dose/Fluence UI | No |
| Run Page | QProcess run/stop/kill/logs/exit code | runner smoke | no live Geant4 state introspection | No |
| Output Page | package browsing, previews, merge tab | output smoke | no plot, no large CSV full load | No |
| Merge Tools | hits/event/hist merge through existing tools | merge smoke | no overwrite by default | No |
| Run History | scan, filter, load snapshot, duplicate/rerun | history smoke | synchronous scan | No |
| Duplicate and Rerun | copy config/macros only, fresh output/logs | duplicate smoke | no archive/delete | No |
| Validation Report | config, material, geometry, boolean summaries | package smoke | static hints only | No |
| Recent Projects | lightweight JSON state in user home | store smoke | no cloud sync | No |
| run_status.json | GUI-only run metadata | runner smoke | absent for old packages | No |

## Typical Workflow

1. Select `G4UniversalSim.exe`, workspace, runs root.
2. Fill Config Builder with existing material and geometry ini files.
3. Validate.
4. Generate Package.
5. Run.
6. Inspect Output page.
7. Merge per-thread output when needed.
8. Use Run History to load, duplicate, and rerun packages.

## Geometry Backend Smoke

Run package-level geometry verification without the C++ backend:

```powershell
python gui/smoke_tests/smoke_geometry_backend_package.py
```

Run package-level geometry verification with the C++ backend:

```powershell
$env:G4USIM_EXE="D:\Geant4\G4UniversalSim\build_vs2026\Release\G4UniversalSim.exe"
python gui/smoke_tests/smoke_geometry_backend_package.py
```

The smoke creates GUI-generated `simple_box` and `layered_device` packages. It verifies generated `geometry.ini`, generated `main.ini`, validation reports, and backend outputs. In the current local backend check, single-thread Simple Box and Layered Device runs passed. A `--threads 2` regression run completed without fatal errors but emitted only `t0` output files, which likely indicates a sequential backend build or no per-worker output in this environment.

## Optional 3D Preview Smoke

The **3D Preview** tab is optional. Without PyVista dependencies, it displays a text fallback and installation hint:

```powershell
pip install -r requirements-3d.txt
```

Smoke test:

```powershell
python gui/smoke_tests/smoke_preview3d.py
```

The smoke validates unit parsing, Simple Box scene construction, Layered Device scene construction, unsupported-template fallback behavior, and Config Builder offscreen availability of the 3D Preview tab. When `QT_QPA_PLATFORM=offscreen` is set, the preview intentionally uses the text fallback because VTK/OpenGL on Windows can fail while creating a render window. PyVistaQt rendering should be visually checked in a normal desktop Qt session; `G4USIM_ENABLE_OFFSCREEN_PYVISTA=1` can be used only on machines with working offscreen OpenGL.

## Hierarchical / Boolean Geometry Smoke

Round 7L adds:

```powershell
python gui/smoke_tests/smoke_hier_boolean_geometry_editor.py
```

This smoke loads real `config/geometry/hierarchical_volume.ini` and `config/geometry/boolean_mixed_csg.ini`, converts them to editable `GeometryDocument` state, checks add/duplicate/delete/move actions at the model level, validates duplicate names, parent cycles, missing boolean targets, invalid tool shapes, generates hierarchical/boolean `geometry.ini`, reparses it, and confirms boolean indices are contiguous. If `G4USIM_EXE` is set, it also tries a C++ backend package run.

## Run Package Layout

```text
runs/<timestamp>_<run_name>/
  config/main.ini
  config/materials/material.ini
  config/geometry/geometry.ini
  macros/run.mac
  logs/stdout.log
  logs/stderr.log
  logs/run_status.json
  logs/merge_*.log
  output/*.csv
  output/run_summary.txt
  validation_report.txt
  project_snapshot.json
```

## Current Non-Goals

- No embedded Geant4 RunManager.
- No Geant4 Qt/OpenGL visualization embedding.
- 3D Preview is approximate and optional; it is not Geant4 visualization and does not replace `/run/initialize` or overlap checks.
- No full material database or chemistry parser.
- No hierarchical/boolean/array/shielding/GDML/STL geometry editor.
- No biasing editor.
- No plot, ROOT viewer, or parameter scan UI.
- No PyInstaller/Nuitka packaging in Round 7.

## Next Route

Round 7L may add hierarchical/boolean editing if needed. Round 8 should focus on packaging strategy and release QA, not new simulation features.
