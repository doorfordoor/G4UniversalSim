# F4 isolated Qt dependency validation — ready for parent review

## Recommendation

Use **`PySide6>=6.11.1,<6.12`** for the supported CPython 3.11 workflow, retaining the latest verified 6.11 patch line rather than fixing the project indefinitely to an old exact wheel. PySide6 package metadata itself pins shiboken6, Essentials and Addons to the identical release; do not independently mix those versions.

`dependency-proposal.patch` changes only `gui/requirements.txt`, adds `gui/smoke_tests/smoke_qt_binding_lifetime.py`, and registers `gui_qt_binding_lifetime` immediately after `gui_qt_combo_data` in `scripts/run_m0_tests.py`. The new smoke retains dependency version output in the normal report log, so no general CI inventory subsystem is needed. The patch passed `git apply --check`; it has **not** been applied to tracked files.

If applied, registry becomes **152 = static28/gui44/backend59/integration21**, M0 each OS72, expected CI448 case executions across12 reports/4 artifacts. Existing tests/old evidence remain unchanged. Parent owns documents, freeze, full matrix and real CI.

## Actual evidence

Windows original venv was read only: Python3.11.9 / PySide6=shiboken6=Qt6.11.1. Candidate binding smoke passes **8 assertions / natural exit0** (`windows-6111-binding-probe.log`). No Windows dependency was installed/changed.

Two task-owned WSL venvs use Python3.11.18 and **no inherited site packages**:

- `/home/u123/venvs/g4-f4-qt-6.11.1-20261030`
- `/home/u123/venvs/g4-f4-qt-6.11.3-20261030`

Both `pip check` commands exit0, no broken requirements. Four Qt distributions are local to their venv with exact paired versions, not borrowed from the original 6.12 installation. Numpy2.4.6, Matplotlib3.11.2 and uproot5.7.7 are locally installed with the same top-level versions as the previous WSL environment. Original WSL6.12 and Windows environments remain intact.

| Test | 6.11.1 | 6.11.3 |
|---|---|---|
| New binding lifetime smoke | 8 assertions, exit0 | 8 assertions, exit0 |
| Original `gui_f4_inspect_backend` | **45**, exit0 | **45**, exit0 |
| Original `gui_run_inputs` | **103**, exit0, actual3/3 events | **103**, exit0, actual3/3 events |
| Current `gui_f4_layout` | **257**, exit0 | **257**, exit0 |

Each pair totals **413 assertions**. Final receipts are **`validation-6.11.1-rpath-data/results.json`** and **`validation-6.11.3-rpath-data/results.json`**. They contain exact original script hashes, raw log SHA, exit statuses, timings and markers; the source tests were never edited. Earlier directories are failed environment attempts, not final acceptance.

The binding smoke checks None ownership for ordinary void `update()`, `setObjectName()`, missing dynamic property and existing false property. Each 100-call loop has delta0 on both verified Linux versions and original Windows6.11.1. The same smoke on unchanged Linux6.12.0 fails with `update` delta-100, exit1/2 executed assertions (`linux-6120-binding-negative.log`), proving the test detects the actual class of defect without forcing an interpreter crash. Natural process exit is still required.

## Backend and environment provenance

Built current backend independently, not an old Linux binary: `/home/u123/g4-f4-qt-validation-build114-20261030/{G4UniversalSim,mergeHistograms}`. Configure/build returned0 with GNU13.3 / Release / Geant41143 / MT. `source_fingerprint=db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc` matches current backend sources. Linux Git cannot resolve the Windows worktree's `D:/...` gitdir, so the binary correctly retains **build_git_commit/source_state=unknown**. Do not rewrite that fact. Native Windows Git receipt separately identifies GUI checkout `096f4b3` (full SHA in `windows-checkout-receipt.json`) and clean status. The two identities are not conflated.

Two unrelated local setup issues were explicitly resolved, with originals retained:

1. Initial inherited site-packages exposed unrelated 6.12 PDF/WebEngine distributions, producing pip conflict warnings. Inheritance was removed before final validation and numeric/plot dependencies installed into each venv; final `pip check` passes. Online WSL downloads were slow, so only these own pip processes were stopped; official wheels were fetched through Windows, SHA-verified against PyPI, then installed by real pip from the owned wheelhouse. All download/install receipts remain.
2. Initial backend run aborted because only `GEANT4_DATA_DIR` was supplied. Conda stores EMLOW/ENSDFSTATE/etc without the G4 prefix; its activation scripts provide the actual named variables. Captured stderr explicitly says **`G4ENSDFSTATEDATA environment variable must be set`** (`runner-debug-state/runner-signal-capture.jsonl`). Final runs use all12 actual `export G4...DATA=${CONDA_PREFIX}/...` paths from the installed package scripts, validated as existing directories; `data-environment.json` and successful backend `data-discovery.json` prove the complete required datasets. This failure was never treated as a Qt6.11 regression or reduced to75 assertions.

## Necessary Linux library-path check

There is also a reproducible shared-library collision when the whole Geant4 conda lib directory is globally added to `LD_LIBRARY_PATH`, as the current Linux workflow does. Both candidate venvs then fail QtWidgets import before assertions: **`libQt6DBus.so.6: undefined symbol ... QVariant ... version Qt_6`**. The loaded DBus comes from `/home/u123/g4env114/lib`, while the binding bundle is6.11; this is not a None-refcount failure.

The final successful runs leave `LD_LIBRARY_PATH` unset. CMake's existing runtime paths resolve Geant4 and its own conda libraries in the backend process; the Python process uses its bundled Qt. Real Inspect plus the real3-event run now pass, so the backend does not need that broad injected prefix for these validated paths. **Before the next real CI**, parent should either remove the single workflow line that globally exports `$G4_PREFIX/lib` (suggested separate `linux-library-path-proposal.patch`) or prove the exact new CI conda package set does not collide. Do not discard this demonstrated failure as an unnecessary inventory change. Keep `QT_PLUGIN_PATH` pointing to the selected PySide6 bundle and retain all existing dataset exports. No general loader/product workaround is proposed.

## Upgrade gate / primary sources

- [Official PyPI6.11.1 metadata](https://pypi.org/pypi/PySide6/6.11.1/json) and [6.11.3 metadata](https://pypi.org/pypi/PySide6/6.11.3/json): exact three companion dependencies, Python>=3.10,<3.15, genuine manylinux wheels. Selected metadata/URLs/SHA are stored as `pypi-*.json`; `f4-pyside-pip-index.log` confirms pip availability including6.12.0/6.11.3/6.11.1.
- [Qt official release notes](https://doc.qt.io/qtforpython-6/release_notes/pyside6_release_notes.html):6.11.3 is a later maintenance release; there is no need to fall back to6.10 after both6.11 endpoints satisfy this task. Release notes are not claimed to acknowledge this exact local defect.
- [Python C API None documentation](https://docs.python.org/3/c-api/none.html): None became immortal in3.12. Therefore a3.12-only pass cannot validate reference ownership on the supported3.11 runtime; switching Python merely to hide the crash is not the proposed fix.

Revisit the upper bound on any candidate6.12.x+ repair: run the ownership probe on CPython3.11, verify matching package versions and loader paths, run the two original failure tests through natural exit, then full Windows/Linux GUI/integration and native acceptance. Patch releases within the allowed6.11 line still go through the registered regression; current evidence explicitly covers6.11.1 and6.11.3, not every future release.

This is targeted dependency validation, **not formal full-matrix/CI or F4 stage closure**. No desktop interaction, tracked edits, commits or CI runs were performed by this agent.
