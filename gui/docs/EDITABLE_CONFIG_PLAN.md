# Editable Configuration Plan

## 1. Principles

- The GUI edits internal models first.
- Validation runs before package generation.
- Generated ini and macro files remain the command-line reproducible source of truth for a run.
- The GUI does not embed or control a Geant4 `G4RunManager`.
- The GUI does not overwrite original user config files by default.
- A generated package must be runnable outside the GUI through `G4UniversalSim.exe --config ... --macro ...`.

## 2. Editable Items

| Module | Item | Add / Remove / Edit | Generated file | Priority |
|---|---|---|---|---|
| Materials | NIST material reference | add/remove | materials.ini | P0 |
| Materials | mass_fraction custom material | add/edit/delete | materials.ini | P0 |
| Materials | volume_fraction material | add/edit/delete | materials.ini | P0 |
| Materials | atom_count custom material | add/edit/delete | materials.ini | P1 |
| Geometry | simple_box | edit | geometry.ini | P0 |
| Geometry | layered_device | add/edit/delete layers | geometry.ini | P0 |
| Geometry | hierarchical volume | add/edit/delete volume | geometry.ini | P1 |
| Geometry | boolean operation | add/edit/delete operation | geometry.ini | P1 |
| Source | particle/energy/position/direction | edit | main.ini or macro | P0 |
| Physics | reference list/default cut/biasing hook | edit | main.ini | P0 |
| Scoring | hits/event_edep/edep histogram | edit | main.ini | P0 |
| Biasing | XS process-level rule | add/edit/delete | biasing.ini or main.ini | P2 |
| Output | threads/seed/output/run name | edit | CLI/main.ini | done |
| GDML/STL | file selection only | select | geometry.ini | P3 |

## 3. Not Open In The First Editor Pass

1. GDML/STL deep editing.
2. General LET/Dose/Fluence editor pages.
3. General MicroElec/ElectronCapture editor pages.
4. Embedded Geant4 RunManager.
5. Arbitrary CSG expression trees.
6. Boolean tool material/sensitive/bias settings.

## 4. Model Foundation Added In Round 7H

The current foundation lives in `gui/g4usim_gui/editors/`.

- `editable_models.py`: shared editable document state and validation messages.
- `material_editor_model.py`: read-only material rows converted from parser summaries.
- `geometry_editor_model.py`: read-only volume and boolean-operation rows converted from parser summaries.
- `source_physics_scoring_model.py`: lightweight editable model shells for later Source/Physics/Scoring forms.

These models do not write back to ini files in Round 7H.

## 5. Materials Editor MVP Added In Round 7I

The Config Builder Materials tab now supports an MVP editor for:

- NIST alias rows.
- `mass_fraction` custom materials.
- `volume_fraction` custom materials, including `density = auto`.
- `atom_count` custom materials.
- Add, duplicate, delete, validate, and revert.
- Generated `materials.ini` preview.
- Package generation using edited materials when the document is dirty.

The source `materials.ini` is never overwritten. Edited materials are written only to the generated run package.

Validation currently covers duplicate names, required density, fraction sums, atom-count integer values, component presence, and geometry material references against the edited document.

## 6. Source / Physics / Scoring Editor MVP Added In Round 7J

The Config Builder Run Config tab now uses editable model classes for:

- Source: preset, particle, energy, point position, direction, and angular mode hint.
- Physics: reference mode, reference list, default cut, and biasing physics hook.
- Scoring: hits, event_edep, EdepScorer, raw/weighted histograms, histogram range, summaries, and auto-create default scorers.

Generated `main.ini` is previewed in the Raw Files tab and written only into generated run packages. Original `config/main.ini` files are not overwritten.

Manual physics editing, advanced source modes, LET/Dose/Fluence editing, and Biasing rules are intentionally outside this MVP.

## 7. Proposed Later Rounds

- Round 7K: Simple Box / Layered Geometry Editor. **Done.**
- Round 7L: Hierarchical / Boolean Geometry Editor.
- Round 7M: Biasing Editor.
- Round 7N: UI polish/theme pass.

## 8. Geometry Editor MVP Added In Round 7K

The Config Builder Geometry tab now supports editable generation for:

- `simple_box`: `[world]` size/material and `[target]` name/shape/size/material/position/rotation/sensitive/bias/region.
- `layered_device`: `[world]` size/material, `[layers]` axis/gap/z_start, and per-layer enabled/name/material/thickness/xy/sensitive/bias/region/copyNo rows.

The original `geometry.ini` is never overwritten. When the geometry document is dirty and the template is `simple_box` or `layered_device`, package generation writes the generated file to:

```text
<package>/config/geometry/geometry.ini
```

Unsupported templates remain preview-only:

- `hierarchical`
- boolean geometry
- `array`
- `shielding`
- GDML/STL

Boolean operation sections continue to be displayed in the separate Boolean Ops preview tab, but they are not editable in Round 7K.

## 9. Backend Verification Added In Round 7K-check

`gui/smoke_tests/smoke_geometry_backend_package.py` verifies the writer/package boundary for GUI-generated geometry:

1. Builds a dirty `simple_box` `GeometryDocument`.
2. Builds a dirty `layered_device` `GeometryDocument`.
3. Generates independent run packages through `create_run_package`.
4. Checks generated `geometry.ini` key names against the C++ template contract.
5. Checks generated `main.ini` points to the package-local `config/geometry/geometry.ini`.
6. Checks `validation_report.txt` contains `geometry_source_mode = generated by Geometry Editor`.
7. If `G4USIM_EXE` points to a real backend executable, runs both packages through `G4UniversalSim.exe`.

Example:

```powershell
$env:G4USIM_EXE="D:\Geant4\G4UniversalSim\build_vs2026\Release\G4UniversalSim.exe"
python gui/smoke_tests/smoke_geometry_backend_package.py
```

If `G4USIM_EXE` is not set, the smoke test skips backend execution and still verifies package generation.

## 10. Optional 3D Preview Added In Round 7K-P

The Config Builder now includes a **3D Preview** tab. It is an optional configuration-level preview and does not modify generated packages.

Implementation pieces:

- `preview3d/scene_model.py`: PyVista-independent `PreviewScene`, `PreviewVolume`, and `PreviewSource` data classes.
- `preview3d/units.py`: lightweight parsing for `mm`, `cm`, `um`, `m`, `deg`, vec3, and direction strings.
- `preview3d/scene_builder.py`: converts `GeometryDocument + SourceEditableModel` into `PreviewScene`.
- `preview3d/fallback_preview_widget.py`: text summary when optional 3D dependencies are missing.
- `preview3d/pyvista_preview_widget.py`: PyVistaQt rendering when `pyvista`, `pyvistaqt`, and `vtk` are installed.
- `requirements-3d.txt`: optional dependencies only.

Supported preview scope:

- `simple_box`: world wireframe, target box, source arrow, sensitive/bias markers.
- `layered_device`: world wireframe, enabled z-stacked layers, source arrow, sensitive/bias markers.
- unsupported templates: text summary and clear warnings.

Non-goals:

- no Geant4 RunManager embedding,
- no Geant4 native Qt/Vis integration,
- no real boolean CSG,
- no GDML/STL rendering,
- no picking/editing in 3D,
- no overlap checking.

## 11. Hierarchical / Boolean Geometry Editor Added In Round 7L

The Config Builder now exposes editable **Hierarchical Volumes** and **Boolean Operations** tabs. This remains a GUI-level editor for existing C++ geometry syntax; it does not introduce new Geant4 semantics.

Supported generated syntax:

- `[world]` for the root world volume.
- `[volume.<name>]` for ordinary hierarchical volumes.
- `[volume.<target>.boolean.<index>]` for sequential boolean solid operations.
- Boolean operations: `subtraction`, `union`, `intersection`.
- Boolean tool fields: `shape`, `size` for `box`, `parameters` for `tubs`, `position`, `rotation`, optional `name`.

Important semantics:

- A boolean tool is a solid operand, not an ordinary volume.
- A boolean tool does not own `material`, `sensitive`, `bias`, `region`, or cuts.
- The final target volume inherits the target volume material, sensitive/bias flags, region, production cuts, and visual settings.
- Enabled boolean operations are written in target-local contiguous order starting at `0`.
- Disabled volume/op rows remain in the GUI but are not written to generated `geometry.ini`.
- The source `geometry.ini` is never overwritten; generated geometry is written only into the run package.

Validation now checks:

- world/root existence,
- duplicate volume names,
- missing or cyclic parents,
- missing materials,
- supported shape names,
- vector-like position/rotation fields,
- boolean target existence,
- operation name validity,
- boolean tool shape and required size/parameters,
- non-contiguous boolean indices, which the writer will renumber.

3D Preview support is approximate:

- hierarchical boxes and tubs are displayed as bounding boxes,
- boolean tools are displayed as wireframe/transparent cutter boxes,
- real CSG subtraction/union/intersection is not rendered,
- the Geant4 backend remains authoritative.
