# H3-4 fixed-benchmark preparation: round124 gaps closed (ready for run review)

Date: 2026-11-07. Task: close the four open preparation gaps from the round124
review (`out/collab/h3-4-independent-r1/analysis-review-pending.json`) for the
frozen H3-4 benchmark, without touching the frozen product, schema, GUI,
contract, closeout manifest, ROADMAP/CURRENT, and without running any formal
batch.

`ready_for_run_review: true`

The 72-run manifest and the three preparation scripts below are the review
artifacts. No formal A/A2/A2f/B/C/M batch, and no new smoke run, was executed in
this round; `runs/` is empty. The earlier preflight, 20-event smoke, r1/r2/r3
grid-fix evidence and all previous failures are preserved unchanged.

## Frozen candidate (unchanged)

| item | value |
|---|---|
| backend exe | `3700e27240a06b865949b0a8a48ba2d47f2af689acc515a428c14f05096c90c3` |
| component exe | `34066c138f518e8533f10543759f860cd8f47a01c833bc359217a1fe2ca5c4cd` |
| source fingerprint | `c7de5a3c819079cd14765d89e22c4570aba54523b17ce6fa51d513f1207e4be7` |

These are the r3-verified candidate identities locked by
`docs/collab/reviews/20261107-h3-grid-fix-r3-acceptance.md`; `prepare.py`
verifies all three before writing the manifest and the manifest records them.

## Files changed in this round (only these)

| file | SHA-256 | size |
|---|---|---|
| `manifest.json` (regenerated) | `da0f7f8c36d53c8a3aabd2225831cfd2cf777a5e29cf3405146874f0bb8fa40a` | 163347 |
| `scripts/prepare.py` | `f8b77f7d6b30d852f99526d215977416f70401908c7ca2a3dec40166be33ef61` | 25962 |
| `scripts/run_benchmarks.py` | `b6f111e612d0e7b4fa51af2e605593e76b24e883e1e6a9f46cd67b9480c8d0b6` | 14178 |
| `scripts/analyze.py` | `6939f5df50f51e732154e13fc8949c8af5795880c32a3e75c15ad296000d2e14` | 63395 |

Nothing outside `out/collab/20261107-h3-4-benchmarks/` and this receipt changed.

## Gap 1 — prepared inputs bound to the new frozen identity

`prepare.py` now:

- asserts the candidate triple above before writing anything;
- generates the same 18 input files and re-runs `verify_frozen_inputs()`, which
  requires the exact 18 names and byte-for-byte equality with the
  `preflight-v1` snapshot SHAs (`h3-4-independent-r1/preflight-v1/snapshot-sha256.json`,
  manifest SHA `8ad79ffc…`); the extra ghost envelope level added by the accepted
  r3 fix is a real path level, not a change to any physics input;
- keeps the original 72 runs, original order, original seeds and event counts;
- writes `preflight_snapshot` (18 input SHAs + snapshot manifest SHA) into
  `manifest.json`;
- R_COMP now declares the component tool's real nested outputs
  (`parallel_entry/`, `mass_entry/`, `latched_failure/` — the tool never writes
  CSVs at its output root);
- A_hits and A2f declare `hits_t0.csv` in `expected_outputs`;
- `path_contract` records the real paths for mass slab
  `/world_PV#0/Slab_PV#0`, parallel box `/ScoringWorld#0/GhostSlab#0`,
  grid cell `/ScoringWorld#0/GhostSlabGrid#0/GhostSlabGrid_<ix>_<iy>_0#0`, and
  states that the r3 navigation envelope is not a scoring volume.

Re-running `prepare.py` reproduces `manifest.json` byte-identically (no
timestamps in the manifest).

## Gap 2 — staged wiring gate in the runner

`run_benchmarks.py` now judges the existing numerical analysis as soon as each
wiring case has its inputs:

- stage A after both `A_nohits` and `A_hits`; stage A2 after `A2`; stage A2f
  after `A2f`;
- each stage calls `analyze.case_a` / `case_a2` / `case_a2f` on the records
  produced so far, writes `analysis/wiring-<case>.json`, and halts the ordered
  manifest before any later science batch when the verdict is not `pass`
  (recorded in `execution.json` as `halted` with the failing check names);
- still stops on a non-zero exit or missing expected output, keeps the
  time/UUID run directory and the anti-overwrite behaviour, and adds no new
  launcher or framework (about 70 lines).
- `--self-test` replays stage A over the existing 20-event smoke outputs,
  proving the gate invokes the real analysis and halts (`WIRING A:
  verdict=fail`), while writing no run record.

## Gap 3 — Case C reads the mass slab in both arms; Probe is diagnostic only

`analyze._batch_values(..., parallel_mass_side=True)` is used for both
`C_disabled` and `C_parallel`: both arms read `/world_PV#0/Slab_PV#0`, and the
off-axis `Probe` rows are counted only in a diagnostic field (no threshold).
Case B keeps using the single ghost box row. The self-test builds both C arms
and asserts the mass endpoint is identical.

## Gap 4 — Welch guards

`_welch_statistics()` now fails (never silently passes) unless: exactly 16
batches per arm, exactly 2000 events per batch, all endpoint values finite, the
mean denominator finite and positive, SE/df/CI finite, and the t critical value
is valid (`_t_quantile` raises on `df <= 0` or invalid t instead of returning
0). The frozen degenerate rule is kept for two constant arms (`SE = 0` →
`[Δ, Δ]`). The all-zero synthetic arm is rejected with a mean-denominator
error, and the ±1 % / ±0.5 % whole-CI verdict classification is unchanged.
Covered by the self-tests.

## Gap 5 — Case M aligned with the freeze decision (round132 follow-up)

Case M keeps the raw event-ID rows per worker (no set de-duplication) and
checks, per run (Run1 200 events, Run2 50 events): the total row count equals
the expected count, the merged ID set is exactly `0..N-1`, there are no
same-worker duplicate IDs and no cross-worker duplicates, every worker's
reported `n_events` equals its event-file row count, and the total equals the
expected count; each run writes its own suffix (`_tN` vs `_tN_rR`; header-only
worker files and a worker without an event file are allowed), the four
quantities plus the event sum-of-squares are merged across workers, and the
cross-worker mass agrees within 1e-12. Duplicates are reported, never hidden by
de-duplication.

On the non-identical-bytes branch the comparison now iterates only the frozen
numeric intervals — dose `raw_edep_MeV`/`weighted_edep_MeV` plus the two dose
sum-of-squares, fluence `raw_track_length_mm`/`weighted_track_length_mm` plus
the two fluence sum-of-squares — and nothing else; metadata such as
`volume_path` is never passed to `Decimal`. There is no cross-process
worker-key/scheduling equality requirement (freeze §1 allows worker scheduling
to differ): a pure `_t0`/`_t1` schedule permutation of the same data passes
when the merged frozen intervals agree, which was verified directly on the
reviewer's `out/collab/h3-4-independent-r3/M-schedule/{first,swapped}` data
(verdict pass, `identical_bytes=false`, `merged_results_agree=true`). Worker
file SHA differences remain diagnostic only: byte-identical files pass;
otherwise agreement of those frozen intervals decides pass/fail, and a SHA
difference alone never raises nor produces `inconclusive`. No new distribution
tests.

## Gap 6 — envelope-aware grid paths in the analysis

`_all_grid_cells`/grid checks now expect the real envelope hierarchy
`/ScoringWorld#0/GhostSlabGrid#0/GhostSlabGrid_<ix>_<iy>_0#0` for the 16
declared cells, treat missing cells as zero without fabricating rows, never
count the navigation envelope as a row, and leave the box path unchanged.
Physics values, the 12-digit addend intervals, mass normalization and the
statistical criteria are the frozen ones.

## Self-checks (existing outputs only; 20-event data is never a formal pass)

Both scripts support a self-test mode that only reads existing outputs or
synthetic values and never runs Geant4:

- `python -B scripts/analyze.py --self-test` → `OK (20/20)`
  (`analysis/self-test.json`, SHA `4d4a6b75…`): Welch guards, C both arms,
  four Case M parser negatives (baseline pass, duplicated event row fails,
  worker-file SHA difference alone passes without raising, worker
  `_t0`/`_t1` schedule permutation passes),
  Case M merge replay on the diagnostic 250-event M smoke (`case_m: pass`), and
  an existing-output replay of `case_a/r_same/case_a2/case_a2f/r_runtime/case_m`
  on the 20-event smoke / r3 20-event runs. The 20-event cases report `fail`
  with the 2000-event guard, and the A2 replay shows the envelope grid paths
  `/ScoringWorld#0/GhostSlabGrid#0/...`. This replay caught a real
  accumulator-initialization bug in the Case M merge (now fixed). Running the
  reviewer's `check_m_negatives.py` harness against this `analyze.py` in a
  throw-away sandbox reproduces: baseline `pass`, duplicated row `fail`,
  SHA-only difference `pass` with no exception.
- `python -B scripts/run_benchmarks.py --self-test` → `OK (14/14)`
  (`self-test/runner-gate.json`, SHA `f8b8bb60…`): stage composition/order,
  four halt-decision cases, A2f hits expectation, nested R_COMP outputs, the
  18-input preflight snapshot, and a replay of stage A through the real
  analysis over the existing 20-event smoke outputs
  (`self-test/analysis/wiring-A.json`, SHA `57b5ed4f…`, verdict `fail` as
  expected before any formal batch).

No formal batch was executed; `runs/` is empty and `execution.json` was not
created.

## Preserved evidence (not modified)

`preflight/` (10 dry-runs + 20-event smoke), `candidate-capabilities.json`,
`inputs/` regenerated byte-identically, `out/collab/h3-4-independent-r1/`
(the reviewer's analysis-review-pending and preflight-v1 snapshot), and the r1/
r2/r3 grid-fix evidence and trace reports. The degraded `analysis-review-pending`
draft remains as the recorded failure it was.

## Reproduction

```bash
python -B out/collab/20261107-h3-4-benchmarks/scripts/prepare.py
python -B out/collab/20261107-h3-4-benchmarks/scripts/analyze.py --self-test
python -B out/collab/20261107-h3-4-benchmarks/scripts/run_benchmarks.py --self-test
```

Formal batches stay blocked until the reviewer approves this manifest and the
three scripts.

## Known limits

- The self-checks replay only existing 20-event smoke / 20-event r3 outputs
  (plus the 250-event diagnostic M smoke); they do not substitute for the
  frozen 2000-event batches.
- B/C/M formal batches, grid exact-path rows and the Welch verdicts will be
  produced only in the authorized run.
- No physics claim is made here.

## Formal 72-run execution (2026-11-07, gate `approved_original_72_run_execution_only`)

- Launched once with the exact frozen command:
  `C:/Users/123/AppData/Local/Programs/Python/Python311/python.exe -B out/collab/20261107-h3-4-benchmarks/scripts/run_benchmarks.py`
  (cwd `D:\Geant4\G4UniversalSim`); no prepare/self-test/smoke was rerun, no script, input,
  manifest or program was modified, nothing was rebuilt.
- `execution.json`: **status = completed, halted = null, executed_runs = 72/72,
  records ok = 72/72**; run order exactly the frozen manifest order; candidate
  identities rechecked at start (exe `3700e272…`, component `34066c13…`,
  source fingerprint `c7de5a3c…`, manifest `da0f7f8c…`).
  SHA-256 `253ec40fca828e0bf77f3c8afa910abc4eb3f280ccd6fadecb866299a9bceaf1`.
- Runner wiring gate `wiring_checks`: A `pass`, A2 `pass`, A2f `pass` — the
  scientific batches (B, C) and M/R_COMP therefore ran; none was skipped.
- Analysis executed exactly once with the frozen `scripts/analyze.py`
  (`6939f5df…`): **status = `wiring_failed`**, verdicts
  A pass, R-SAME pass, A2 pass, A2f pass, B pass, C pass, M pass,
  R-RUNTIME pass, **R-COMP fail**.
  `analysis/results.json` SHA-256
  `cbbe99d6aff5976d7632ec1234052ad9b7158dc785387361e28a37f00d9c1bb4`.
- R-COMP single failing check: `parallel_mass_kg`
  (`analysis/results.json`, case `R-COMP`). Actual recorded value is exactly
  `0.0008` and every other R-COMP check passes (exit 0, PASS marker, 21 `ok:`
  lines, all nested outputs present, parallel weighted edep 10 / dose
  2.0027207925e-09 / length 0.5 / fluence 0.000625, mass edep 4, mass event and
  hits rows, latched failure empty). The failing predicate compares the
  Decimal-12 interval of `0.0008` with the exact point pair
  `(0.0008, 0.0008)`, which cannot be true by construction — a consumer
  assertion defect in the frozen analysis script, not a physical mismatch.
  Per the authorization this script was **not** edited and the batch was **not**
  rerun; recorded as-is for independent review.
- R-RUNTIME: no `hits_t0.csv` is produced by the lazy hit writer (zero hits), as
  the frozen contract's literal product wording anticipates an empty file;
  recorded as the literal artifact difference to be adjudicated by the reviewer,
  no file fabricated.
- Every run keeps `runs/<label>/` with argv, input SHA, log, record and output
  hashes; `logs/formal-run.log` SHA-256
  `3fd7be7d80f873ce793d8d0a6792a5bbf8fb9e1d557bc5c15e4deb44a77f12ac`,
  `logs/formal-analysis.log` SHA-256
  `54247fd32bc1e57b77c002f0bcfc6d9ca01d79ec7fefe68194bc159cef6bdaea`,
  `analysis/summary.txt` SHA-256
  `cf984b1c63d6f70d8cb34042d478cc5b8fb1c75c2efaf7c960b7d372232af8ad`.
- Phase status: **not passed and not declared passed**; waiting for the
  independent reviewer's decision on the single R-COMP consumer-check failure.
