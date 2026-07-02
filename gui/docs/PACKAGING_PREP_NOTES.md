# Packaging Preparation Notes

Round 7 intentionally does not package the GUI into an executable.

## Why Not Package Yet

- Manual GUI QA should be completed first.
- Run package behavior should be verified on real user workspaces.
- PySide6 packaging can be large and needs careful Qt plugin handling.
- The GUI should remain independent from `G4UniversalSim.exe`; users must be able to choose their own executable.

## Candidate Packaging Routes

| Route | Notes |
|---|---|
| Source + venv | Simplest and most transparent |
| PyInstaller | Common Windows route, but must handle Qt platform plugins |
| pyside6-deploy | Qt-oriented deployment, needs separate evaluation |
| Nuitka | Possible optimized route, more setup complexity |

## Pre-Packaging Checklist

- Manual QA checklist passes.
- `python -m compileall gui` passes.
- Smoke scripts pass.
- Path handling works with spaces and Chinese characters.
- `scripts/merge_outputs.py` can be found.
- `mergeHistograms.exe` search logic is stable.
- GUI does not require Geant4 Qt/Vis.
- `G4UniversalSim.exe` is not forcibly bundled.
- Users can select their own `G4UniversalSim.exe`.

## Windows Risks

- PySide6 package size.
- Qt platform plugin discovery.
- Visual C++ runtime.
- Geant4 runtime environment.
- Python venv management.
- Paths containing spaces or non-ASCII characters.
