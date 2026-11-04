# Benchmarks, reference data, NIEL provenance and Q1/F1 statistics+source contracts

Read-only inventory for the Q2 scientific-baseline specification. **Status: raw evidence collection; no
product code, test, benchmark, CI or docs file was modified, and no simulation was executed for this note.**

- Repository: `D:\Geant4\G4UniversalSim`, `HEAD = 55652422` (working tree additionally carries changes that
  are **not from this note**: modified `docs/ROADMAP.md` and `docs/collab/CURRENT-SUPERVISION.md`, untracked
  `docs/collab/**` and `20261102-2045-astra-d-workspace-execution.md`; these were only read).
- Every claim below cites a file and line (or a named section). Where the repository does not state a fact,
  the item is marked **unverified** with a follow-up command in §6.2.
- Chinese strings inside backticks/quotes are copied verbatim from the repository.

---

## 1. Q1/F1 contract summary

### 1.1 Per-event moments and the two estimators

- Statistics are **history-by-history at event granularity**, not per primary and not batched:
  `sum = Σ x_i`, `sum_sq = Σ x_i²`, `N = completed events` (`docs/输出数据契约.md:159–163`).
- Total estimator: `R² = sum_sq/sum² − 1/N`, `std_error = R·|value|`, identifier
  `uncorrected_event_moments_v1` (`docs/输出数据契约.md:163`; identifier fixed by
  `docs/collab/decisions/20261029-q1-uncertainty.md:11`).
- Ratio estimator (track- and dose-averaged LET): variance of a ratio by the delta method,
  `R² = Σb²/B² + Σa²/A² − 2Σab/(AB)`, identifier `uncorrected_delta_ratio_v1`; for ratios the
  `sum`/`sum_sq`/`mean` columns are deliberately empty (`docs/输出数据契约.md:164`;
  `docs/collab/decisions/20261029-q1-uncertainty.md:11`).
- Figure of merit `fom_per_s = 1/(R²·T)` (`docs/输出数据契约.md:165`).
- `estimator` is `total` or `ratio`; `n_events` = completed events, `entries` = non-zero contributors
  (`docs/输出数据契约.md:162–165`).
- The 1/N form is a **known, accepted approximation**, not an unbiased sample-mean standard error: an iid
  sample-mean `SE²` is larger by `N/(N−1)`, and with N=2 and contributions 1 and 2 the project value is
  0.7071 while the sample variance is 1 (`docs/collab/decisions/20261029-q1-uncertainty.md:5`). The decision
  is to keep it and to make Q2 supply the independent coverage/weighted-applicability evidence rather than
  silently switching estimator (`…q1-uncertainty.md:3`, `:11`).
- A comparison against Geant4 11.3.2 `G4StatDouble` (`https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/global/HEPNumerics/src/G4StatDouble.cc`)
  was examined and the earlier "identical to Geant4/MCNP" claim was **withdrawn**; no claim is made about all
  MCNP versions (`…q1-uncertainty.md:7`).

### 1.2 Worker and run merging

- Per-worker CSVs are additive: sum every `*_sum`/`*_sum_sq` column across workers and runs **first**, then
  apply the estimator formula once. Never average per-worker `rel_error`
  (`docs/输出数据契约.md:171`; per-worker schema names at `:167–170`: `edep_summary_csv_v4`,
  `dose_volume_csv_v2`, `fluence_volume_csv_v2`, `let_volume_csv_v2`).
- `N` must come from run metadata, `run_metadata.json` → `runs[].completed_events`, or be passed explicitly
  as `load_scorer_statistics(..., n_events=N)` (`docs/输出数据契约.md:171`; the same rule for the native
  mesh because sparse workers omit zero cells, `:137–144`).
- `format=root` still writes the merged `scorer_statistics` CSV (`docs/输出数据契约.md:180`); the ROOT
  raw-moment layout is unchanged by Q1 (`docs/collab/decisions/20261029-q1-uncertainty.md:12`).
- New columns `uncertainty_estimator` and `uncertainty_status` are appended to `scorer_statistics` and the
  native mesh CSV, schema→v2; old columns keep order and meaning
  (`…q1-uncertainty.md:12`; emission visible at `src/Output/OutputManager.cc:276,298`).

### 1.3 Zero denominators, N<2, unavailability statuses

- Statuses (`docs/collab/decisions/20261029-q1-uncertainty.md:13`; code:
  `src/Scoring/HistoryStatistics.cc:49–51`):
  - `insufficient_events` — fewer than 2 events;
  - `undefined_ratio` — ratio denominator (LET Σa) is zero;
  - `zero_total` — observed total/numerator is zero;
  - `approximate` — otherwise computable.
- When unavailable, the legacy numeric `0` is **only a compatibility sentinel**, never a zero uncertainty;
  consumers must display "unavailable" and hide error bars, and no NaN/Inf may pose as physics
  (`…q1-uncertainty.md:13`; `docs/输出数据契约.md:174`).
- The Python consumer must derive the same status from the same-run `N` (`…q1-uncertainty.md:12`).
- Cross-cell mesh projection deliberately has **no aggregated error** because covariance is not carried
  (`docs/输出数据契约.md:174`).

### 1.4 LET ratio delta method

- The delta method is valid asymptotically; for small samples or heavy-tailed LET_d it may **underestimate**
  the error (`docs/collab/decisions/20261029-q1-uncertainty.md:14`; `docs/输出数据契约.md:180`;
  `docs/功能支持矩阵.md:160`).
- LET_d ≥ LET_t is asserted as a physics sanity relation, not as an uncertainty statement
  (`docs/功能支持矩阵.md:159`).

### 1.5 Statistical vs systematic — kept separate

- `scorer_statistics` covers **statistical** uncertainty only; systematic effects (cross sections, material
  parameters, geometry, NIEL model) are outside it (`docs/输出数据契约.md:159–165`, limits at `:180`;
  `docs/功能支持矩阵.md:160` statistics row).
- Benchmark pass/fail combines a **systematic tolerance on the reference plus 3σ of the simulation**:
  `allowed = tolerance·|expected| + 3·sigma` (`scripts/run_benchmarks.py:114–119`;
  `scenarios/benchmarks/README.md:9`). This is a benchmark acceptance rule, not a physics uncertainty budget.
- A physics-level (not statistical) comparison exists for LET: 0.55 %/1.4 % against the Bethe formula at
  100/10 MeV in 20 µm water (`docs/功能支持矩阵.md:159`).
- `approximate` must not be read as verified coverage (`…q1-uncertainty.md:14`); weighted/biasing statistics
  were not specifically verified (`docs/输出数据契约.md:180`), and "偏置与analog的响应及方差方法验证属于Q2"
  (`docs/输出数据契约.md:218–220`).

### 1.6 Seed / source / build provenance fields

- `run_metadata.json` → `provenance` object, `schema = g4usim_provenance_v1`
  (`docs/输出身份与来源.md:19–27`):
  - `execution_id`: 128-bit lowercase hex, unique per process;
  - `build`: `git_commit`, `git_source_state`, `source_fingerprint`, compiler, build configuration,
    Geant4 version, with `git_state_scope = cpp_build_inputs`;
  - `inputs`: ordered ledger with a continuous `sequence`;
  - `input_coverage = project_readers_observed`, `input_observation = bytes_read_not_semantic_acceptance`,
    plus `input_exclusions`.
- Two distinct identities must not be conflated (`docs/输出身份与来源.md:27`):
  - `source_fingerprint` = sorted-manifest raw-byte SHA-256 of the actual C++ sources/headers, build
    templates, `CMakeLists.txt` and cmake modules — **not** the executable SHA-256;
  - the executable SHA-256 is recorded separately in acceptance evidence (e.g.
    `docs/verification/independent-scoring-5465dbd-20261029/README.md:3`).
- `run_summary.txt` carries `run_summary_schema_version = 1` (`docs/输出数据契约.md:11`) and is written once,
  at the final lifecycle stage (`docs/输出数据契约.md:46`). F1 adds
  `output_format_requested` / `output_format` / `output_format_selection_reason`
  (`docs/输出数据契约.md:107`).
- Effective-configuration origin fields use `effective_<field>_origin_kind/file/line/section/key` with
  `kind ∈ {default, main_ini, cli, macro, runtime_unattributed}`; the summary must not present Manager
  state as proof that the Geant4 kernel applied it (`effective_config_geant4_applied=unknown` is retained)
  (`AGENTS.md` §10; historical coverage enum values must remain tolerated).
- Seed facts are split: configured seed, engine initial seed (or `unknown`), and whether a macro actually
  modified the seed; only commands that executed successfully may claim a macro seed change
  (`AGENTS.md` §3, M0-2 bullet; `docs/输出数据契约.md:46` for `run_summary` contents).
- Biasing facts are separate and may remain unknown: `biasing_worker_*` fields and
  `biasing_effect_observed` stays `unknown` (`docs/输出数据契约.md:228`); actual bias effect is never
  inferred from process attachment (`AGENTS.md` §3 M0-3E).

### 1.7 Input-file hashing

- Each input record has `path/kind/role/capture_method/status/sha256/size_bytes/reason`; the hash is computed
  from the **exact bytes handed to the reader** (BOM, newlines and NUL included) and is **not re-opened at
  finalize**; a parse failure may leave a read record but that record is not semantic acceptance
  (`docs/输出身份与来源.md:31`).
- Inputs covered (`docs/输出身份与来源.md:33`): main INI, standalone geometry and material files, recursive
  macros, spectrum files, phase-space files, **NIEL tables**, field maps, copies tables, STL, GDML
  dependencies, supported RNG restore files.
- Inputs that were not observed require an explicit `unobserved` reason with null hash/size; Geant4 datasets
  are not faked (`docs/输出身份与来源.md:35`).
- Implementation entry points: `src/Config/IniReader.cc:18–26` (`ReadFile` + `Sha256`),
  `src/Scoring/NielTable.cc:15–19` (`ReadFile(path, "niel_table", "displacement_table_parse")`, stores
  `acceptedInput.sha256`), `src/Core/MacroPreflight.cc:287–288` for macros.
- Generated artifacts record `execution_id`, `scope ∈ {process, run, thread}`, `run_id`/`thread_id`,
  `sha256`/`size_bytes`, and `integrity_status ∈ {hashed, unavailable, self_reference_excluded}`; the metadata
  file itself is only `self_reference_excluded` (`docs/输出身份与来源.md:41–53`). A lost/failed artifact
  latches `artifact_integrity` first cause and fails the exit, without silently dropping the entry
  (`docs/输出身份与来源.md:55`).

### 1.8 Output columns and units

- `output_csv_schema_version = 3`; energy/length columns that are actually verified are marked `_MeV`/`_mm`
  in the header; numeric text keeps ~12 significant digits (`docs/输出数据契约.md:11`, `:67`).
- Thread/run file naming: `*_tN.csv` on the first run, `*_tN_rR.csv` on later runs; `eventID` repeats across
  runs, so events must be keyed `(runID, eventID)` (`docs/输出数据契约.md:46`).
- Dose: `raw_dose = Σ edep_MeV × 1.602176634e-13 / mass_kg`, mass from
  `GetMass(true, false, preStepMaterial)` (`docs/输出数据契约.md:77`); the same mass convention is recorded
  in `docs/功能支持矩阵.md:161`.
- Fluence: `Σ stepLength / solid volume`, mm⁻² (`docs/输出数据契约.md:78`).
- DDD: `displacement_volume_summary_tN[_rR].csv` with `ddd_MeV_g`, `ddd_sum_sq_MeV2_g2`, `n_events`, plus
  `track_length_mm` and `out_of_range_track_length_mm`; DDD meaning depends on the user NIEL table
  (`docs/输出数据契约.md:54`).
- `scorer_statistics` carries one `unit` per scorer/quantity row (`docs/输出数据契约.md:162`).
- Old CSV v3 headers must not be used to infer LET: `LETcalc`/`LETstep` were removed in v3 and must not be
  reconstructed from hits (`docs/输出数据契约.md:73`).

### 1.9 Limitations the documents state explicitly

| Area | Stated limitation | Source |
| --- | --- | --- |
| Statistics | uncorrected 1/N event-moment estimator; LET_d delta method may underestimate in small samples/heavy tails; no coverage claim | `docs/collab/decisions/20261029-q1-uncertainty.md:5,14`; `docs/输出数据契约.md:180` |
| Statistics | weighted-spectrum/biasing statistics not specifically verified; belongs to Q2 | `docs/输出数据契约.md:180,218–220` |
| Statistics | no covariance across mesh cells, so no aggregated error for projections | `docs/输出数据契约.md:174` |
| Numeric bounds | overflow/non-finite tests use extreme values, not the physical range | `docs/输出数据契约.md:178` |
| Dose | cumulative dose of the simulated history only; not normalized by source strength, fluence, time or events; no independent physics benchmark | `docs/输出数据契约.md:80`; `docs/功能支持矩阵.md:161` |
| Fluence | daughter-free sensitive solids only; track-length/volume definition, not surface crossing; not normalized | `docs/输出数据契约.md:82`; `docs/功能支持矩阵.md:163` |
| DDD | correctness "完全取决于所用的表"; NIEL data itself and displacement-damage effect not benchmarked | `scenarios/shielding_coating/README.md:56`; `scenarios/semiconductor/niel/README.md:17`; `docs/功能支持矩阵.md:162` |
| LET | only 20 µm water, 10/100 MeV; no heavy ions or thick targets; GUI cannot edit LET | `docs/功能支持矩阵.md:159` |
| Benchmarks | results hold only for the listed conditions; 2026-10-22 full mode is not a general claim | `scenarios/benchmarks/README.md:20`; `scenarios/benchmarks/csda_range/README.md:17` |
| Q1 scope | small-sample coverage and the Q2 external physics baseline are **not** completed by Q1 engineering acceptance | `docs/verification/q1-final-20261029/README.md:26` |
| Historical defects | R03 (sensitive mother dose counted daughter mass) and R04 (GDML SD name collision) were reproduced pre-fix; fixed in Q1 | `docs/verification/r03-r04-current-20261029/README.md:3`; `docs/collab/reviews/20261029-q1-findings.md:9–10`; `docs/collab/reviews/20261029-q1-closure-review.md:28` |

The R03 fix is recorded as "`改为步前材料对应本体质量`" with the changed header
`include/Scoring/DoseContext.hh:25` (`docs/collab/reviews/20261029-q1-findings.md:9`); R04 is recorded at
`src/Geometry/GdmlIO.cc:64` plus `GeometryRegistry` (`…q1-findings.md:10`). The closure review nevertheless
keeps "A5 实验等级不变" for geometry (`docs/collab/reviews/20261029-q1-closure-review.md:28`).

---

## 2. Benchmark inventory

Common mechanics (`scenarios/benchmarks/README.md`; `scripts/run_benchmarks.py`):

- Each pack directory contains `reference.csv` + runnable `example.ini`/`geometry.ini`/`run.mac` + `README.md`
  (`scenarios/benchmarks/README.md:3`).
- Run: `python scripts/run_benchmarks.py [--quick] [--only csda_range,gamma_attenuation] --output benchmark_report`
  (`scenarios/benchmarks/README.md:6,9`; flag handling `scripts/run_benchmarks.py:28`).
- Executable resolution: `G4USIM_EXE` environment override, else
  `build_vs2026/Release/G4UniversalSim.exe`; there is no `--exe` flag, and a missing binary prints
  `backend executable missing` (`scripts/run_benchmarks.py:50–51,400–401`).
- Pass rule: `allowed = tolerance·|expected| + 3·sigma`, `passed = |simulated − expected| ≤ allowed`
  (`scripts/run_benchmarks.py:114–119`); any failure makes the script exit 1 (`:435`).
- Outputs `benchmark_report.json` and `benchmark_report.md` (`scripts/run_benchmarks.py:23–26`); `--output`
  defaults to a temporary directory (`:396`).
- `--quick` selects a subset and fewer events (`scripts/run_benchmarks.py:132,134,166,204,231,235,246,253,276,290,317,326,329`);
  the unified test platform runs exactly `scripts/run_benchmarks.py --quick` as its `benchmarks` backend case
  (`scripts/run_m0_tests.py:255`).
- `--threads` defaults to 4 (`scripts/run_benchmarks.py:397`).

| Pack | Particles / energies | Material & geometry | Observable | Reference (as written in `reference.csv`) | Tolerance | Quick mode | Recorded result (2026-10-22 full mode) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `csda_range` | proton 10/50/100/150/200 MeV; e- 1/10 MeV | liquid water 80 cm cube; `[physics] em = option4`; default cut 0.7 mm | CSDA range (g/cm²), per-event track-1 step sum | NIST PSTAR (protons), NIST ESTAR (electrons), `https://physics.nist.gov/PhysRefData/Star/Text/`; "water I = 75 eV" (`reference.csv:1–10`) | 1.5 % proton, 3 % electron, +3σ (`run_benchmarks.py:146`) | proton 10/100/200 + e- 1 MeV; 200/300 events (`:132,134`) | +0.23…+0.95 %; proton systematically +0.6–0.9 % explained by `G4_WATER` I = 78 eV vs 75 eV (`csda_range/README.md:5–17`) |
| `bragg_peak` | proton 150 MeV | water 40 cm; native mesh 1×1×300 bins over 150 mm; 10×10 cm transverse sum | Distal 80 % dose depth R80 | PSTAR CSDA × detour factor 0.998 (projected/CSDA; Bortfeld 1997 cited) (`reference.csv:1–5`) | 1 % + 3×0.1 mm fixed σ (`run_benchmarks.py:182–183`) | single case, 1000 events (`:166`) | R80 158.7 mm vs 157.4 mm (+0.84 %); peak at 156.5 mm; peak/entrance 4.9; physics `QGSP_BIC_EMZ` incl. nuclear reactions (`bragg_peak/README.md:3–5`) |
| `gamma_attenuation` | γ 0.1/1/10 MeV | water 40/100/300 mm; Al 40 mm; Pb 0.1/10 mm; vacuum phase-space plane 50 mm behind slab, `kill=true` | µ/ρ from surviving primaries with unchanged energy and `w > 1−1e−9` | NIST XCOM total mass attenuation with coherent scattering (`reference.csv:1–9`) | 2 % + 3σ (binomial) (`run_benchmarks.py:212–213`) | 4000 events (`:204`) | −1.74 % (water 0.1 MeV) … +0.21 % (Al 1 MeV); all within 1.7σ (`gamma_attenuation/README.md:5–16`) |
| `shielding_range` | proton 10/100 MeV, e- 1/5 MeV; residual-energy proton 20/50/100 MeV in Al, 30 MeV in Si | `G4_Al` 2.699 g/cm³, `G4_Si` 2.33 g/cm³; slabs 1–20 mm | CSDA range; mean exit kinetic energy behind slab | NIST PSTAR/ESTAR tables saved verbatim under `nist/`, converted by `make_reference.py` (`reference.csv:1–5`) | 1.5 % proton / 3 % electron; residual energy 1 % (`run_benchmarks.py:242,258`) | (proton,100), (e-,1); residual 5/2 mm; 300 events (`:231,235,246,253`) | −0.18…+1.02 %; largest residual-energy deviation +0.57 % at 20 MeV/1 mm Al (`shielding_range/README.md:10–26`) |
| `device_dose` | proton 10/50/100/200 MeV; neutron 14 MeV | Si 40×40 mm block; sensitive 10×10 mm slab 20–200 µm; buildup 50 µm–1.5 mm each side; 12×12 mm plane source; cut 10 µm | TID per fluence (Gy·cm²); DDD per fluence (MeV·cm²/g) | TID: PSTAR Si electronic stopping × 1.602176634e-10 at E_mid; DDD: SR-NIEL Si table at E_mid (`reference.csv:1–10`) | 2 % TID / 1 % DDD, +3σ (`run_benchmarks.py:300`) | `tid` proton 10/100, `ddd` proton 100; 4000 events (`:276,290`) | TID −0.38…+0.14 %; DDD +0.67/−0.22/+0.01 %; buildup chosen for delta-electron equilibrium so dose = collision kerma (`device_dose/README.md:5–20`) |
| `detector_response` | γ 0.662/1.332 MeV; γ 4.44 MeV; µ- 4 GeV; proton 300 MeV/1 GeV | 1″×1″ plastic scintillator; HPGe r=30 mm × l=50 mm; Si 300 µm | Compton edge; single/double escape peak position; Landau MPV of deposited energy | All analytic: Klein–Nishina kinematics, `E − m_e c²`, `E − 2m_e c²`, PDG Landau–Vavilov–Bichsel Eq. 34.12 (`reference.csv:1–10`) | 1 % edge; 0 + one 1 keV bin for escape peaks (σ = 0.001/√12); 3 % + 3σ MPV (`run_benchmarks.py:345,351,363`) | 662 keV edge, 4.44 MeV single escape, 4 GeV µ-; 30000/40000 events (`:317,326,329`) | edge +0.07/+0.03 %; escape peaks within one bin; MPV +2.68/+0.08/+0.43 % (`detector_response/README.md:11–21`) |

Per-pack notes and applicability limits:

- **csda_range** — only liquid water; the systematic offset is attributed to the Geant4 water ionisation
  potential (78 eV vs the 75 eV used by PSTAR/ESTAR), "`这是材料参数差异，不是程序错误`"
  (`scenarios/benchmarks/csda_range/README.md:17`). Single-run example command at `:19–23`.
- **bragg_peak** — one energy, one material; R80 defined by linear interpolation of 1 mm depth bins; the
  reference is CSDA × detour, i.e. derived from PSTAR rather than a measured Bragg curve
  (`scenarios/benchmarks/bragg_peak/README.md:3–7`).
- **gamma_attenuation** — narrow-beam total µ/ρ including coherent scattering only; the detector is a
  phase-space plane, so scattering-in is not counted (`scenarios/benchmarks/gamma_attenuation/README.md:3–22`).
- **shielding_range** — Al and Si only; "coating materials (B4C, W, HEB) have no NIST table and were not
  compared" (`scenarios/benchmarks/shielding_range/README.md:28`); `projected_range_energy_MeV` is
  informational only and biased for thin slabs (`:6`).
- **device_dose** — the slab is placed in delta-electron equilibrium by construction and the cut is 10 µm;
  the DDD row "`检验径迹长度注量与折积，不检验 NIEL 数据本身`" (`scenarios/benchmarks/device_dose/README.md:5–6`).
  Because the same SR-NIEL CSV supplies both the scorer and the reference, this row is **circular for NIEL**
  and only validates fluence×folding.
- **detector_response** — "escape peaks and Compton edge test kinematics/energy conservation, not detection
  efficiency" (`scenarios/benchmarks/detector_response/README.md:23`); the MPV is systematically above the
  LVB formula (~+2.7 % near minimum ionising, ~+5 % in 100 µm Si).
- **Evidence identity** — the benchmark READMEs quote the run date and Geant4 11.3.2
  (`scenarios/benchmarks/README.md:20`) but **no commit hash, executable SHA-256 or archived report**; no
  `docs/verification/*/README.md` carries a benchmark report (`grep -rn "benchmark" docs/verification/*/README.md`
  only returns statements that no new physics benchmark was performed). Identity for the recorded numbers is
  therefore **unverified** against `HEAD 55652422` (follow-up in §6.2).

---

## 3. NIEL table facts

### 3.1 Files, bytes and hashes

Computed with `sha256sum` / `wc -lc` in this working tree (read-only):

| File | SHA-256 | Size | Lines | Particle | Energy range in file |
| --- | --- | --- | --- | --- | --- |
| `scenarios/semiconductor/niel/si_electron.csv` | `e26af764ceaf9b388434f440c337a8a1b297f1f86862b045499a52b5cc7d8b87` | 1917 B | 102 | electron | 1e−6 (added zero row) … 1e4 MeV |
| `scenarios/semiconductor/niel/si_neutron.csv` | `a2ad28a9fcce3500fca363946e09e19125d084f1b596eff76662b272c242034f` | 12088 B | 649 | neutron | 1.025e−10 … 19.95 MeV |
| `scenarios/semiconductor/niel/si_proton.csv` | `6c21e35aab18495d4bb2597a76be60c7c35ef0df963224e0108c77c2e4c208d5` | 2617 B | 158 | proton | 1e−6 (added zero row) … 1e4 MeV |

Also in the directory: `README.md` (2267 B) and `convert_srniel.py` (2599 B).

Column contract (identical in all three files, header line e.g. `si_proton.csv:12`):

```
energy_MeV,niel_MeV_cm2_g
```

- Units: energy in MeV, NIEL in MeV·cm²/g (`scenarios/semiconductor/niel/README.md:3`).
- The reader requires the header **exactly** `energy_MeV,niel_MeV_cm2_g`, exactly two columns, `energy > 0`,
  finite `NIEL ≥ 0`, strictly increasing energies and at least two rows; violations fail before the first
  event (`src/Scoring/NielTable.cc:31–33,38,52–61`). Blank lines and `#` comments are skipped and a UTF-8 BOM
  is stripped (`:25–27`).
- Interpolation is log–log inside an interval when both endpoints are positive, linear in energy when either
  is zero; evaluation outside `[front, back]` returns false instead of clamping
  (`src/Scoring/NielTable.cc:67,73–79`). Out-of-range track length is reported separately as
  `out_of_range_track_length_mm` (`docs/输出数据契约.md:54`;
  `scenarios/shielding_coating/README.md:56`).

### 3.2 Provenance as stated by the README

- All tables were produced by the SR-NIEL web calculator (`https://www.sr-niel.org`, "SR-NIEL-7 ver. 11.1"),
  retrieved **2026-10-22** with calculator defaults; citation SR-NIEL (Boschini et al.) and ASTM E722-19
  (`scenarios/semiconductor/niel/README.md:3,11`).
- Proton (`README.md:5`; file comments `si_proton.csv:1–11`): Protons & Ions NIEL calculator, Si, 21 eV
  displacement threshold, `IonModel = Hadron+Coulomb`, hadronic part **unscaled**, Jun 2003/2004 + Jun 2017 +
  Huhtinen 2002 interpolation, 0.1 keV–10 GeV.
- Electron (`README.md:7`; `si_electron.csv:1–9`): Electrons NIEL calculator, 21 eV, exponential nuclear form
  factor, 0.1 MeV–10 GeV. First tabulated NIEL at 0.1 MeV is 0; `convert_srniel.py` prepends a 1 eV zero row
  so sub-0.1 MeV secondaries score zero instead of out-of-range — "`这只延续源表的零值，不是新的数据`"
  (`README.md:13`; rule implemented at `convert_srniel.py:41–46`).
- Neutron (`README.md:9`; `si_neutron.csv:1–9`): ASTM E722-19 damage function, Table A1.1, as served by the
  SR-NIEL ASTM calculator; 1.0e−10–19.95 MeV binned values (mid-point convention, log interpolation between
  points, `README.md:13`). The lowest value is non-zero, so **no** 1 eV zero row is added.
- 1 MeV neutron equivalent fluence: `NIEL_ref = 95e-27 × N_A/28.0855 = 2.037e-3 MeV cm²/g`,
  `Φ_eq = DDD/NIEL_ref`, explicitly **not** interpolated from the resonance table (`README.md:15`).
- Limits stated: Si only; oxide/other materials still point at the Si table for reference only; NIEL is a
  model quantity with inter-publication differences; "`本仓库没有独立验证这些表`" (`README.md:17`).

### 3.3 Conversion script

Usage (`scenarios/semiconductor/niel/convert_srniel.py:8`, `README.md:19–22`):

```bash
python scenarios/semiconductor/niel/convert_srniel.py <saved-result-page.html> <out.csv> "<description>"
```

- Input is the saved SR-NIEL result page (`http://www.sr-niel.org/Simulation/<id>niel_<p|e|n>.html`,
  `convert_srniel.py:4–5`); the script scrapes the first table between "Input Parameters" and
  "Energy (MeV)" (`:37–39`).
- Row regex requires exactly the page's `d.dddde±dd` four-decimal scientific format
  (`:24`); rows are de-duplicated and sorted ascending (`:33`), at least two distinct energies are required
  (`:35–36`).
- Output is written with 5 significant digits, `f"{e:.5g},{v:.5g}"` (`:48`), with the header at `:47`.
- Description and input parameters are emitted as `#` comments; the 1 eV zero row is added only when the
  lowest source NIEL is 0 and its energy is above 1e−6 MeV (`:41–46`).
- No checksum or SR-NIEL submission ID is stored, so reproducing the exact page is not possible from the
  repository alone (**unverified**; follow-up in §6.2).

### 3.4 Existing verification of the tables — and what is missing

- Direct statement: the NIEL data themselves are **not independently verified** in this repository
  (`scenarios/semiconductor/niel/README.md:17`); the support matrix records
  "`NIEL 数据本身与位移损伤效应未作基准`" (`docs/功能支持矩阵.md:162`).
- `scenarios/benchmarks/device_dose` uses `si_proton.csv`/`si_neutron.csv` at `E_mid` as the **reference**
  while the same tables are the scorer input; the README concedes it "`不检验 NIEL 数据本身`"
  (`scenarios/benchmarks/device_dose/README.md:6`). Its DDD deviations (+0.67/−0.22/+0.01 %) therefore
  validate fluence × step-length folding, not the table values.
- `scripts/test_semiconductor_device.py:4–12` loads the **shipped** tables and checks that (a) they load and
  `convert_srniel.py` rebuilds a table from a result page, (b) 50 MeV protons behind 1 mm Al give
  DDD-per-fluence equal to the SR-NIEL proton NIEL at the post-lid energy (PSTAR CSDA inversion) and
  `Φ_eq = DDD/2.037e-3`, (c) 14 MeV neutron DDD-per-fluence equals the ASTM NIEL from the table. However its
  `table()` helper re-reads the same CSV and re-implements interpolation in Python (`:56–60`, `:109–112`), so
  this is an implementation-consistency check, not an independent datum.
- `scripts/test_displacement_damage.py` exercises the scorer only with **synthetic** tables
  (`mu.csv` NIEL = 2e-6·E, `far.csv`, `flat.csv`; `:280–282`) and validates invariants (track length vs hits
  1e−9, DDD vs independent hit recomputation 1e−3, out-of-range accounting, statistics merge, rejection
  messages; `:307–317`, `:336–365`). It never reads the shipped SR-NIEL CSVs.
- The only place the shipped bytes are pinned is the K1 delivery identity manifests, e.g.
  `docs/verification/k1-delivery-20261031/verification-4167c44/identity/full-tracked-source-and-test-objects.json:126060,126068,126076`
  (`sha256_raw_git_object` for the three CSVs). That is a Git-object identity record, **not** a physics check.
- `docs/collab/reviews/20261029-q1-closure-review.md:31` states the boundary explicitly:
  "`NIEL 数据来源与物理标定分开`".
- Net: **no independent check of the table values exists**; the data are traceable to a dated calculator
  session (SR-NIEL-7 v11.1, 2026-10-22) but the session identity/page is not archived.

---

## 4. Detector-response analytic references

All references in `scenarios/benchmarks/detector_response/reference.csv:1–2` are declared as coming from
`scenarios/detector_response/response_physics.py`; they are **formulas computed in-repo**, not external
measured or evaluated data.

| Case | Quantity checked | Formula / source | Tolerance | Type |
| --- | --- | --- | --- | --- |
| Compton edge, 662 keV and 1332 keV, 1″ plastic | Step position below the photopeak (max step in a 2 % E window) | Klein–Nishina `E_c = E·2a/(1+2a)`, `a = E/m_e c²` (`scenarios/detector_response/response_physics.py:30–32`) | 1 % (`scripts/run_benchmarks.py:351`) | Analytic kinematics |
| Backscatter edge (helper, not a benchmark row) | `E/(1+2a)` | `response_physics.py:35–36` | — | Analytic kinematics |
| Single/double escape, 4.44 MeV HPGe | Highest 1 keV bin within ±10 keV of `E − m_e c²` / `E − 2m_e c²` | `response_physics.py`; `reference.csv:6–7` | exact position, one-bin allowance; σ = 0.001/√12 (`run_benchmarks.py:363`) | Kinematic identity, not efficiency |
| Landau MPV, 300 µm Si, µ- 4 GeV / p 300 MeV / p 1 GeV | Half-sample mode of deposited energy | PDG Landau–Vavilov–Bichsel Eq. 34.12 with Sternheimer density effect, `Δ_p = ξ[ln(2mc²β²γ²/I) + ln(ξ/I) + j − β² − δ(βγ)]`, `K = 0.307075 MeV cm²/mol`, `j = 0.200` (`response_physics.py:48–58`); Si `I = 173 eV`, `C = 4.4351`, `x0 = 0.2014`, `x1 = 2.8715`, `a = 0.14921`, `k = 3.2546`, `d0 = 0.14` from Geant4 `G4DensityEffectData` (`:26–27`) | 3 % + 3σ (`run_benchmarks.py:345`) | Analytic PDG formula, not measured |
| Absolute efficiency, bare BGO cylinder at 100 keV | Detected fraction equals the solid-angle fraction although the source samples only a cone | `solid = (1 − 50/√(50²+20²))/2` (`scripts/test_detector_response.py:62–67`) | `4·f·√(solid/f·(1−solid/f)/events) + 0.015·solid` (binomial + 1.5 %) | Geometric analytic |
| Energy resolution / FWHM model | Gaussian GEB form `FWHM(E) = a + b√(E + cE²)` supplied by the user | `scenarios/detector_response/README.md:27` | FWHM within 5 % of the model; photopeak position within 0.002 MeV; no deposit > E (`test_detector_response.py:70–80`) | Model self-consistency |
| Photopeak / intrinsic efficiency fields | Full-energy efficiency, peak-to-total, escape-peak fields only above pair threshold | `test_detector_response.py:70–80`, `:94–99` | `fep_efficiency_intrinsic > 0.1`; invalid option sets rejected | Implementation checks |

Notes:

- The analytic reference implementation is duplicated logic: `make_reference.py` (per pack README) calls the
  same `response_physics.py`, and the test asserts the report echoes `rp.landau_mpv` exactly (1e−12)
  (`scripts/test_detector_response.py:85–91`) — that assertion guards serialisation, not physics.
- **No external data comparison exists** for detector response: "`没有与实测效率或能谱比较`"
  (`scenarios/detector_response/README.md:34`). Limits also include: pulse height = deposited energy only, no
  light yield, Birks quenching, light collection, charge collection or electronics; the resolution model is
  user-supplied; the Compton-edge position is meaningful only in small low-Z detectors because multiple
  Compton scatters smear the edge in large high-Z crystals (`scenarios/detector_response/README.md:34`;
  `scenarios/benchmarks/detector_response/README.md:5,23`).

---

## 5. Evidence inventory

Only directories under `docs/verification/` are listed; each is an archived, self-contained evidence package
(see `AGENTS.md` §6 for the archive rule). "Identity" quotes the README's own commit/count lines.

| Path | Identity (as stated) | Relevance | Does **not** establish |
| --- | --- | --- | --- |
| `docs/verification/q1-final-20261029/README.md` | acceptance code `8ecad66a5a3d1e9151cec4ed9a9035e70464577f`; Windows MSVC Geant4 11.3.2 Release **105 PASS / 0 FAIL / 0 SKIP**, 83770 v3 assertions; Ubuntu 11.3.2 and 11.4.3 105 each, CI run 40855144863 (`:3,9–11`) | Q1 closure: statistics statuses, numeric failure latch, Dose/Fluence/LET/DDD regressions, R01–R32 index (`:5–6`) | Explicitly defers "V01统计估计量与小样本覆盖率、Q2外部物理基准" (`:26`) |
| `docs/verification/independent-uncertainty-5465dbd-20261029/README.md` | review commit `5465dbdddf36dae921a885d2a18a1d049c383a1e`; 3 backend processes / 4 runs / 12 events plus a GCC 15.1.0 helper linking the statistic source; 89-file manifest (`:3,5`) | Independent sample-SE and ratio-delta recomputation, ROOT/CSV reconciliation, zero-contribution and sparse-worker cases | "不宣称完整回归、统计覆盖率或物理基准验收通过" (`:23`); same simulated data |
| `docs/verification/independent-scoring-5465dbd-20261029/README.md` | commit `5465dbdd…`; 5 processes / 12 events; backend Windows Release Geant4 11.3.2 SHA-256 `f78fa2fb06c08dbebd590bf7457f306ec85d9d6a7a8c0f0b30f5b7daeb6b45e1`; 103-file manifest (`:3`) | Two-primaries-one-history (R05), weighted single/multi-thread, geantino zero-EDep, weight overflow (R06) | "没有执行完整回归；正常退出的复现实例不能等同于物理判据通过"; not a physics benchmark (`:18`) |
| `docs/verification/independent-biasing-weight-5465dbd-20261029/README.md` | commit `5465dbdd…`; 16 processes (15 completed, 1 invalid target rejected), 16 runs, 70 events (`:3`) | Analog vs eIoni bias 0.1/1/10 with identical 128 hits, MT bias, thick/thin neutron cases, input weights into primaries/secondaries | Implementation/consistency only; no variance-reduction physics validation |
| `docs/verification/independent-output-contract-5465dbd-20261029/README.md` | commit `5465dbdd…`; 3 successful backend processes / 9 events; 4 JSON CLI exports (`:3–4`) | LET numerator/denominator, old-file pollution after directory reuse, ROOT sparse event counts, covariance absence (`conclusions.json`) | No implementation change, no regression claim |
| `docs/verification/independent-rng-repro-5465dbd-20261029/README.md` | commit `5465dbdd…`; 13 processes / 12 completed, 14 runs, 46 events; one seed-after-init rejection (`:3`) | Reproducibility, seed origin, native seed commands, RNG state store generation | "没有运行完整测试套件"; no restore test (`:3,17`) |
| `docs/verification/r03-r04-current-20261029/README.md` | backend SHA-256 `4658f847bb29cd91d42eda9f52931207f7762ea0374947fa27ac364007ab2acd`; 69 files / 321180 B ZIP, ZIP SHA `ea7998a9…` (`:3–10`) | Pre-fix counterexamples: R03 mother-volume mass included daughters (0.0062992 kg vs 0.000488 kg; dose 2.54e−12 vs 3.28e−11 Gy), R04 GDML `Sensor`/`sensor` SD binding loss | "这是反例复现，不是四项通过验收"; no independent physics benchmark (`:14`) |
| `docs/verification/stage2b-20261028/README.md` | report v2, 87 pass / 0 fail / 0 skip, 116636 assertions, source fingerprint `5bd97ec5…`, `git_head = 402a9f2`, exe SHA `dd62fd87…` (`:11–20`) | Unified-platform evidence example (static/gui/backend/integration) | Engineering regression only; no physics baseline |
| `docs/verification/2c-full-20261029/README.md` | acceptance code `f4770b0cb73c8b1f9852fbac0d485e17b25bc0e3`; 11 consumer classes, per-run/thread receipts (`README.md:3–16`) | Effective-config provenance machinery (sources, hashes, unknown states) reused by F1 | "本轮没有新增独立物理基准" in the configured subset (see `2c-configured-20261029/README.md:46`) |
| `docs/verification/f1-visible-20261030/README.md` | product `f176d0ed4cea60b7ca5a80ed81017c9404ec1257`; Windows 143/143 with 48511 v3 assertions; Linux 11.3.2/11.4.3 143 each; M0 64/64; 14 real-window observations (`:3,15–19`) | F1 output identity/provenance acceptance | "这14次不是14项独立模拟或物理基准" (`:27`) |
| `docs/verification/f2-final-20261104/README.md` | product/cloud `864bc036d6d7752475e52db4efd2b950cabfcc3d`; C++ fingerprint `e7de615d…`; cloud 708 cases / 255163 assertions (`:3–8`) | Identity/evidence packaging example (strict gates, per-profile counts) | "工程一致性检查不等于科学物理基准验证" (`:53`) |
| `docs/verification/j3-final-20261104/README.md` | candidate `92134da062e8e3a203a39ff59fcd2b87bd0ffef1`; Windows 125/150 % + Linux X11/xcb native receipts (`:3–20`) | Identity example for GUI/native evidence split | "没有做物理基准验证" (`:47`) |
| `docs/verification/k1-final-20261031/README.md` | 350 product files identical to the frozen identity; 73-line test-only addition (`:9`) | Path/resource identity and singletons | "不新增性能基准或科研物理验证结论" (`:9`) |
| `docs/verification/e4-final-20261105/README.md` | E4 closing (WSL/installation limits retained) | Platform evidence only | "工程完成与科学基准各使用对应证据" (`:33`) |

Not listed here but relevant as pre-fix or non-final material: `2c-configured-20261029` (configured subset),
`f2-baseline-20261104`, `i2-j1-final-20261101`, `k1-p1-close-20261031`, `r03-r04-current-20261029`.

---

## 6. Gap list

### 6.1 Per-quantity independent-reference gap

| Quantity | Strongest existing reference | Type of that reference | Missing independent external reference | Artifact reusable as "independent"? | Only implementation cross-check |
| --- | --- | --- | --- | --- | --- |
| Dose / TID | PSTAR Si electronic stopping × 1.602176634e-10 at `E_mid` in `device_dose` (Gy·cm²) | External stopping-power data, but transformed by CSDA inversion and restricted to delta-electron-equilibrium slabs | No absorbed-dose measurement or independent transport calculation for the scoring geometry; no source-strength/time normalisation; `shielding_coating` TID has no reference at all ("`这些数值只说明场景可运行，不是验证结论`", `scenarios/shielding_coating/README.md:50`) | `device_dose` TID rows (4 energies, 10–200 MeV, Si) as a *limited* external anchor; PSTAR tables in `scenarios/benchmarks/shielding_range/nist/` | Native `doseDeposit` vs project dose scorer < 1e−9 (`docs/功能支持矩阵.md:158,161`); R03 counterexample (`docs/verification/r03-r04-current-20261029/README.md:3`) |
| Fluence | None external. Only `Φ = N/1.44 cm²` from the plane-source area in `device_dose` (`scenarios/benchmarks/device_dose/README.md:3`) and a geantino geometry check (~12 mm/0.12 mm⁻²) | Geometric/definitional | No measured or independently calculated fluence behind a slab; track-length vs surface-crossing difference unquantified; daughter-free solids only | None in-repo | Native `cellFlux` vs project fluence < 1e−9 (`docs/功能支持矩阵.md:158,163`); geantino path-length test |
| LET | Bethe formula at 100/10 MeV in 20 µm water (0.55 %/1.4 %) | Analytic (Bethe) | No external LET table/measurement; no heavy ions, no thick targets, no mixed field; LET_d ratio statistics heavy-tail limit | Bethe comparison for the two listed points only (`docs/功能支持矩阵.md:159`) | `let_scoring` Q1 regression and the ratio-delta recomputation in `independent-uncertainty-5465dbd-20261029` |
| DDD | SR-NIEL Si tables at `E_mid` in `device_dose` | External **model** data, but circular: the same CSV is the scorer input | Independent NIEL values (different calculator/publication) and any measured displacement-damage datum; DDD model itself (step-length folding, `NIEL(E_mean)`) unvalidated against experiment | `si_neutron.csv` ASTM E722-19 table is a distinct provenance from the proton table and could cross-check the 1 MeV-neutron equivalent normalisation (`scenarios/semiconductor/niel/README.md:15`) | `test_displacement_damage` synthetic tables (`scripts/test_displacement_damage.py:280–317`); `test_semiconductor_device` re-implements the same CSV in Python (`:56–60,109–112`) |
| Statistics | 20 independent runs of the same model (ratio 1.04–1.25) and the independent sample-SE/ratio-delta recomputation | Self-consistency across runs; independent *implementation* but same simulation model | A coverage study (frequentist coverage vs N, heavy-tailed LET_d, zero-denominator frequency) and a comparison against a reference statistics tool on the same histories; Q1 acceptance explicitly defers it (`docs/verification/q1-final-20261029/README.md:26`) | `independent-uncertainty-5465dbd-20261029` conclusions.json (independent sample SE and ratio delta) — reusable as an implementation oracle, not as coverage | `scripts/test_statistical_uncertainty.py` ratio checks; `docs/功能支持矩阵.md:160` |
| Biasing / weighted | Analog vs eIoni-bias runs with identical 128 hits and weights (16 processes / 70 events) | Implementation consistency | Any physics-level variance-reduction validation (mean and variance vs analog, across materials/energies, with weight distributions); explicitly assigned to Q2 (`docs/输出数据契约.md:218–220`; `docs/ROADMAP.md:264`) | `independent-biasing-weight-5465dbd-20261029` hits/weights cases as a regression oracle | `test_biasing_*`, `biasing_step_weight` Q1 regressions |
| Provenance (F1) | `source_fingerprint` + per-input SHA-256 ledger + `execution_id` | Deterministic identity of bytes actually read | No external attestation that hashed bytes were semantically accepted; Geant4 datasets deliberately not hashed (`docs/输出身份与来源.md:35`); no signature/transparency log | `run_metadata.json` from any archived run (e.g. `f2-final-20261104`, `f1-visible-20261030`) can be re-verified against the tree | F1 regression suite (`docs/verification/f1-visible-20261030/README.md:15`) |

Structural gaps that apply to all quantities:

1. **Benchmark identity is not pinned.** The recorded 2026-10-22 numbers carry no commit hash or executable
   SHA-256 (`scenarios/benchmarks/README.md:20`; each pack README quotes only the date and Geant4 version).
2. **No benchmark report is archived** under `docs/verification/`; `grep -rn "benchmark" docs/verification/*/README.md`
   returns only statements that no new physics benchmark was claimed.
3. **Water benchmark systematic +0.6–0.9 % is a material-parameter difference**, not a code error
   (`scenarios/benchmarks/csda_range/README.md:17`); it must not be "fixed" by loosening tolerance.
4. **DDD is circular** wherever the reference and the scorer share one NIEL file.
5. **Detector response is analytic-only**; no measured spectra/efficiency anywhere
   (`scenarios/detector_response/README.md:34`).
6. **Weighted/biasing statistics** are outside Q1 and are a Q2 obligation
   (`docs/collab/decisions/20261029-q1-uncertainty.md:3`; `docs/输出数据契约.md:218–220`).

### 6.2 Explicitly unverified items and follow-up commands

| Item | Why unverified | Follow-up command |
| --- | --- | --- |
| Benchmark pass/fail at `HEAD 55652422` | No simulation was executed for this note; the recorded results are dated 2026-10-22 | `python scripts/run_benchmarks.py --quick --output out/collab/q2-reference-proposal/raw/benchmark-quick` (needs `build_vs2026/Release/G4UniversalSim.exe` or `G4USIM_EXE`) |
| NIEL table bytes in this tree | Hashes were computed here, but no archived receipt binds them to the SR-NIEL session | `sha256sum scenarios/semiconductor/niel/si_*.csv` |
| SR-NIEL session/page identity | The converter stores no submission ID or page hash | none available in-repo; would require re-running the calculator and diffing (`scenarios/semiconductor/niel/convert_srniel.py:8`) |
| Exact wording of the Q1 decision lines | Only cited by line; quotes here are short excerpts | `sed -n '3,18p' docs/collab/decisions/20261029-q1-uncertainty.md` |
| R03/R04 fix on the current binary | Q1 findings/closure claim the fix; no test was run here | `python scripts/test_dose_scoring.py` and `python scripts/test_geometry_a5.py` (backend required) |
| Current matrix text for the four quantities | Rows were read from this tree; line numbers drift if the file is edited | `sed -n '138,175p' docs/功能支持矩阵.md` |
| Detector-response external validity | No measured data exists in the repo | requires external measured spectra/efficiency; no command |
| Full Q2 bias-vs-analog baseline | Only implementation-level evidence exists today | design a Q2 case set from `independent-biasing-weight-5465dbd-20261029` (analog vs factors, several materials/energies, weight moments) |

---

## 7. Sources read for this note

| Path | Read |
| --- | --- |
| `docs/collab/decisions/20261029-q1-uncertainty.md` | full (18 lines) |
| `docs/ROADMAP.md` | Q2/F1/F2 rows and §wave-6 context (`:250,254,260–272,321,328,456`) |
| `docs/功能支持矩阵.md` | rows for Dose/Fluence/LET/DDD/statistics/provenance (`:140,158–163,172,495,538`) |
| `docs/输出数据契约.md` | full (228 lines) |
| `docs/输出身份与来源.md` | full (77 lines) |
| `scenarios/benchmarks/README.md` + 6 pack `README.md`/`reference.csv` | full |
| `scripts/run_benchmarks.py` | relevant functions (`:23–26,50–51,77–119,125–370,397,435`) |
| `scenarios/semiconductor/niel/README.md`, `convert_srniel.py`, `si_*.csv` | full / headers + hashes |
| `src/Scoring/NielTable.cc` | full (81 lines) |
| `scripts/test_displacement_damage.py` | full (392 lines) |
| `scripts/test_semiconductor_device.py` | docstring + table helper (`:1–60`) |
| `scripts/test_detector_response.py`, `scenarios/detector_response/response_physics.py`, `scenarios/detector_response/README.md` | full |
| `scripts/test_shielding_coating.py`, `scenarios/shielding_coating/README.md` | full |
| `docs/verification/{q1-final,independent-*,2c-full,f1-visible,f2-final,j3-final,stage2b,r03-r04-current,k1-final,e4-final}/README.md` | heads / identity sections |
| `docs/collab/reviews/20261029-q1-findings.md`, `20261029-q1-closure-review.md` | R03/R04 rows and scoring row |
