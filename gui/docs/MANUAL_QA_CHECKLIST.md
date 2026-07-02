# G4UniversalSim GUI Manual QA Checklist

Use this checklist when a desktop session is available. These tests complement, but do not replace, the smoke scripts.

## A. Existing Macro Runner

- Select an existing `G4UniversalSim.exe`.
- Select `config/main.ini`.
- Select `macros/test_simple_min.mac`.
- Select an output directory.
- Click Run.
- Confirm stdout/stderr update.
- Confirm exit code is shown.
- Confirm Output page can refresh.

## B. Generated Simple Box Package

- Open Config Builder.
- Select `config/materials/material.ini`.
- Select `config/geometry/simple_box.ini`.
- Set template `simple_box`.
- Use source `proton`, `10 MeV`, `0,0,-1 mm`, `0,0,1`.
- Click Validate.
- Confirm no errors.
- Click Generate Package.
- Confirm `config/main.ini`, `macros/run.mac`, `validation_report.txt`, and `project_snapshot.json` exist.
- Run package.
- Confirm `run_summary.txt` is visible in Output page.

## C. Boolean Geometry Preview

- Select `config/geometry/boolean_mixed_csg.ini`.
- Reload geometry.
- Confirm the volume table shows ordinary volumes.
- Confirm the boolean table shows boolean operations.
- Confirm boolean sections are not shown as ordinary volumes.
- Validate and review warnings.

## D. MT Hit Smoke + Merge

- Select `macros/run_boolean_hit_smoke.mac`.
- Set threads to `2`.
- Run.
- Open Output page.
- Refresh merge plan.
- Run available merge tasks.
- Confirm merged files appear.
- Confirm merge logs are visible under `logs/`.

## E. Run History Duplicate and Rerun

- Open Run History.
- Refresh runs root.
- Select a successful run.
- Click Duplicate Package.
- Confirm new package has config/macros and empty output/logs.
- Click Duplicate and Rerun.
- Confirm a new package runs without overwriting the old one.

## F. Error Case

- Select a non-existent macro path.
- Click Run.
- Confirm the GUI shows a validation error.
- Confirm the GUI does not crash.

## Notes

- If Geant4 visualization commands fail with OGL-related messages, switch to a no-vis macro.
- If a material is missing, compare geometry material refs with the Materials preview.
- If a command is unknown, check that the macro uses commands supported by this executable version.
