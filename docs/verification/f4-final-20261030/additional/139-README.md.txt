# F4 Qt dependency evidence collection

This is an out-only byte-copy evidence collection, not new-freeze acceptance or phase closure.

- `final/6.11.1` and `final/6.11.3`: four original cases each, 8 + 45 + 103 + 257 = 413 assertions, all natural exit 0. Both original test sources are unchanged and their SHA matches each result receipt. The run-input case records a real 3/3-event backend run.
- `negative/ci`: original 5d6f008 CI report/logs with 45/103 assertions followed by none_dealloc and -6. Selected bytes were compared with official artifact 12974006530. Its original ZIP remains at the absolute path recorded in manifest, with the official digest verified. Exact PySide version was not directly logged by that old quiet-pip CI step.
- `negative/refcount` and `receipts/linux-6120-binding-negative.log`: independent local CPython 3.11.18 / PySide6-shiboken6 6.12.0 defect controls, including ordinary void calls and actual product functions. This evidence is scoped to that verified combination.
- `negative/loader`: a separate libQt6DBus symbol mismatch caused by globally injecting the Geant4 conda lib directory. These are import failures, not the None defect.
- `negative/missing-data`: the subsequent run-input failures at 75 assertions. Captured stderr identifies missing G4ENSDFSTATEDATA; final data-discovery receipts show required data complete. The `.jsonl.txt` file keeps its original JSONL bytes.
- `official-metadata`: fresh raw official PyPI responses for both matching Qt quartets and new receipt cross-checking the 8 retained wheel SHA values. These requests occurred during evidence collection, not at original installation time. No wheel payload is copied.
- `receipts`: original download/installation/pip-check/build/identity logs and earlier proposal. Early canceled downloads and inherited-package conflict attempts remain historical, not final install proof.
- `scripts`: current key probes/install/build/test launchers and the collector. Final scripts are preserved; superseded early launcher revisions were not separately frozen. `validated-test-snapshots` contains original target scripts with SHA proven equal to final receipts.

`manifest.json` maps every copied payload to its original absolute path, raw SHA, bytes and category. `copy-verification.json` records a second source/destination hash pass. Original files, environments, wheelhouse and backend builds are retained; no cleanup occurred. The backend accurately reports Git identity unknown for the WSL-mounted Windows worktree; GUI Git 096f4b3 is a separate native receipt.

Parent archive input: append the flat JSON argv array in the sibling `f4-qt-dependency-include-file-argv.json` to `prepare-f4-archive.py` arguments. The helper accepts repeated `--include-file <path>` and assigns `additional/<index>-<basename>`; its own generated plan maps paths. No invented colon syntax or `--include-root` is used. The included `archive-inputs.json` maps collection-relative paths to stable argv order. The helper preserves Markdown bytes as `.md.txt` by design. This input does not request publication, a new matrix, or stage closure.
