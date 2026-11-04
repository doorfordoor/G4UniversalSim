# Scorer implementation facts — Dose / Fluence / LET / DDD

Raw fact sheet for the Q2 scientific-baseline review. **Read-only inspection**; no product code, test, benchmark or document was modified. Every claim below cites `file:line` in this repository (paths relative to repo root) or in the installed Geant4 tree.

Provenance of the inspected bytes:

| Item | Value |
| --- | --- |
| Repository | `D:\Geant4\G4UniversalSim` (Git for Windows: `/d/Geant4/G4UniversalSim`) |
| Git HEAD | `556524227c04c8b100c9035cbf29cf911c30b20f` |
| Working tree | dirty: `git status --porcelain \| wc -l` = **73** entries (no state-changing git command was run) |
| Geant4 | 11.3.2 — `/d/ProgramFiles/Geant4/include/Geant4/G4Version.hh`: `G4VERSION_NUMBER 1132` |
| Geant4 CMake dir | `build_vs2026/CMakeCache.txt`: `Geant4_DIR:PATH=D:/ProgramFiles/Geant4/lib/cmake/Geant4` |

File identity (sha256 of the bytes inspected; `sha256sum <path>`):

| File | Lines | sha256 |
| --- | --- | --- |
| `src/Scoring/DoseScorer.cc` | 120 | `9bec14defcc3cecd7cf2e175d405750921cbb7490493c11dd1bb8abc2dba0a64` |
| `src/Scoring/FluenceScorer.cc` | 139 | `53ab6bbe407d8e514e27ef2508c161ad7b3f2e3a60c9b99fe4093458195e4fef` |
| `src/Scoring/LETScorer.cc` | 182 | `7d039c70bf76ee4d328d6ed8a56ee7ef9cfff67f39367ff5c22c1bc1fabec757` |
| `src/Scoring/DisplacementScorer.cc` | 130 | `6a95ed51835c8ee17bf44bc3d321db41d2b62ace4ce91be86592344f678ba484` |
| `src/Scoring/HistoryStatistics.cc` | 156 | `91fdcc6421507286ffddc1a021e716acac6d2bb43f4ac4a841ac8001b7b4eaaa` |
| `src/Scoring/NielTable.cc` | 81 | `c49924810f616fdefd9381869c6c2524f4307d39c47081b0fdccbc18df2df1a4` |
| `include/Scoring/DoseContext.hh` | 43 | `6dc39d7211fe9d752b0cf19d96e37e75f0bee16d3478a30cad16372a1118038c` |
| `include/Scoring/HistoryStatistics.hh` | 80 | `abad43750bb5403683a9da638e375a936ebdab76526b4c18790cba4815056643` |
| `src/Output/OutputManager.cc` | — | `7c924d795f5e36318cb67a73a6df43ef1aa31221e14bb8e7dab32ff5614ff88a` |
| `src/Output/RunSummary.cc` | — | `8d838f91f95ffcfbb7e3dd95d6c685f963138b33795ad61a1265e25c5b1676ed` |

---

## 0. Cross-cutting facts (apply to all four quantities)

### 0.1 Units constants actually in force

The scorer code includes `G4SystemOfUnits.hh` (`src/Scoring/DoseScorer.cc:6`), which re-exports CLHEP constants (`/d/ProgramFiles/Geant4/include/Geant4/G4SystemOfUnits.hh:74,102`: `using CLHEP::joule;`, `using CLHEP::MeV;`). Definitions in `/d/ProgramFiles/Geant4/include/Geant4/CLHEP/Units/SystemOfUnits.h`:

| Constant | Definition (exact source text) | Line |
| --- | --- | --- |
| `millimeter` / `mm` | `static constexpr double millimeter  = 1.;` / `static constexpr double mm  = millimeter;` | `:63`, `:96` |
| `centimeter` / `cm` | `static constexpr double centimeter  = 10.*millimeter;` / `static constexpr double cm  = centimeter;` | `:67`, `:100` |
| `megaelectronvolt` / `MeV` | `static constexpr double megaelectronvolt = 1. ;` / `static constexpr double MeV = megaelectronvolt;` | `:170`, `:181` |
| `electronvolt` | `static constexpr double     electronvolt = 1.e-6*megaelectronvolt;` | `:171` |
| `joule` | `static constexpr double joule = electronvolt/e_SI;// joule = 6.24150 e+12 * MeV` | `:178` |

⇒ All stored tallies are in **internal Geant4 units**: energy in MeV, length in mm, mass in GeV/c²-equivalent mass units (so `mass/kg` is the kg conversion), and `sum/joule` is energy in J. `1 joule = 1/(1.602176634e-13) MeV`, i.e. `1 MeV = 1.602176634e-13 J`, which is the constant hard-coded independently in the tests (`scripts/test_dose_scoring.py:19` `MEV_J = 1.602176634e-13`, `scripts/test_statistical_uncertainty.py:44` `MEV_IN_JOULES = 1.602176634e-13`).

### 0.2 Which steps reach which scorer (single dispatch point)

`src/Hits/SensitiveDetector.cc:84-136` `ProcessHits`:

- `:90-91` `const G4double edep = step->GetTotalEnergyDeposit();` / `const G4double ndep = step->GetNonIonizingEnergyDeposit();`
- **Zero-deposit branch** `:92` `if (!zeroEdepHitsEnabled_ && edep <= 0.0 && ndep <= 0.0)`: only when `step->GetStepLength() > 0.0` and Fluence/LET/Displacement is enabled (`:95-97`). Calls `PopulateDoseContext(step, record);` (`:102`), then `ScoreFluenceStep` (`:103`), `ScoreDisplacementStep` (`:104`), and for LET `record.LETstep = ElectronicStoppingPower(step);` (`:106`) + `ScoreLETStep` (`:107`). **Dose is not scored in this branch**, and no hits CSV row is written (`return false;` `:116`).
- **Normal branch** `:119-134`: `PopulateDoseContext` is called whenever any of Dose/Fluence/LET/Displacement is enabled (`:129-132`), `record.LETstep = ElectronicStoppingPower(step);` only when LET is enabled (`:133`), then `scoringManager->ScoreHit(record);` (`:134`).
- Track weight: `HitRecord::weight` (default `1.0`, `include/Output/OutputRecord.hh` `struct HitRecord`) is the per-step statistical weight; hits CSV emits it (`src/Output/OutputManager.cc:823-830`).

`ScoringManager::ScoreHit` (`src/Scoring/ScoringManager.cc:537-574`) accumulates the event totals (`:543-547` `currentEventRawEdep_` / `currentEventWeightedEdep_`), writes the hits row when enabled (`:553-563`), and then fans out to every enabled scorer (`:565-573`):

```cpp
for (ScorerBase* scorer : EnabledScorers()) {
    try { scorer->ScoreHit(hit); }
    catch (const std::exception& error) {
        if (outputManager_) outputManager_->RecordOutputFailure("scoring_" + scorer->GetName(), error.what());
        if (auto* runManager = G4RunManager::GetRunManager()) runManager->AbortRun(true);
        return;
    }
}
```

The zero-deposit entry points are separate: `ScoringManager::ScoreFluenceStep` (`:576-587`), `ScoreLETStep` (`:589-601`), `ScoreDisplacementStep` (`:603-615`). Scorer failures latch an output failure and abort the run (`scoring_<name>` stage), they are never silently dropped.

### 0.3 Mass / volume metadata is produced in exactly one place

`include/Scoring/DoseContext.hh:16` `inline void PopulateDoseContext(const G4Step* step, HitRecord& record)`:

| Field | Source line | Exact expression |
| --- | --- | --- |
| `doseMass` | `:25` | `record.doseMass = logical->GetMass(true, false, step->GetPreStepPoint()->GetMaterial());` |
| `fluenceVolume` | `:29-31` | `if (logical->GetNoDaughters() == 0 && logical->GetSolid()) { record.fluenceVolume = logical->GetSolid()->GetCubicVolume(); }` |
| `meanKineticEnergy` | `:32-35` | `record.meanKineticEnergy = 0.5 * (step->GetPreStepPoint()->GetKineticEnergy() + post->GetKineticEnergy());` |
| `doseVolumePath` | `:36-42` | `record.doseVolumePath += "/" + std::string(volume->GetName()) + "#" + std::to_string(touchable->GetCopyNumber(i));` looping `for (int i = depth; i >= 0; --i)` |

Header comment `:14-15`: "Transport-only metadata. Dose is scored per physical touchable instance; `GetMass(true,false)` removes daughter displacement without adding their mass." Comment `:23-24` for the third argument: "Pass the step material so parameterised copies with their own material get their own mass".

**`GetMass` semantics in the installed Geant4 11.3.2** — `/d/ProgramFiles/Geant4/include/Geant4/G4LogicalVolume.hh:252-253`:

```cpp
G4double GetMass(G4bool forced = false, G4bool propagate = true, G4Material* parMaterial = nullptr);
```

Doc comment (`:254-266`): `forced=true` forces recomputation; `propagate=false` "returns the mass of the present logical volume only (subtracted for the volume occupied by the daughter volumes)". ⇒ The repo call `GetMass(true, false, preStepMaterial)` means **forced recompute + own-body mass with daughter volumes subtracted, using the actual pre-step material of that physical copy**. (Older Geant4 releases named these parameters `useDaughters`/`checkMass`; the behaviour is what `docs/功能支持矩阵.md:161` describes as "扣除 daughter 占据体积，使用实际副本材料".)

**Deliberate asymmetry:** `fluenceVolume` is only populated for a logical volume with **zero daughters** (`DoseContext.hh:29`), with the rationale at `:26-28`: "A mother volume's cubic volume includes its daughters and would give a wrong track-length normalization if silently used here." Dose therefore has a value for a sensitive mother-with-daughters, while Fluence/DDD would throw (§2.2, §4.2).

### 0.4 Fixed-mass / fixed-volume assumption is stated in code

`src/Scoring/DoseScorer.cc:71`: `// Dose per event = edep / mass with a fixed mass, so sums scale exactly.` Both Dose (`:72,77-78`) and Fluence (`:98,103-104`) convert totals by multiplying the **already summed** tallies by a constant factor, and DDD divides each step by the (constant) volume (`DisplacementScorer.cc:78`). This is only valid because each scorer refuses a changing mass/volume per touchable (Dose `:56-58`, Fluence `:57-59`, DDD `:67-69`).

---

## 1. Dose (`[scoring] dose = true`)

### 1.1 Quantity definition in code

| Item | Facts |
| --- | --- |
| Accumulated per step | `touched_.Add(volume.rawEdep, hit.edep);` (`src/Scoring/DoseScorer.cc:59`) and `touched_.Add(volume.weightedEdep, hit.edep * hit.weight);` (`:60`) |
| Energy used | `hit.edep` = `step->GetTotalEnergyDeposit()` (`src/Hits/SensitiveDetector.cc:90`), **not** non-ionizing deposit, **not** kinetic energy |
| Steps skipped | `if (hit.edep == 0.0) return;` (`DoseScorer.cc:45`) |
| Weight | linear: weighted tally multiplies each hit by `hit.weight`; raw tally uses weight 1 |
| Factors multiplied | output conversion `const double gyPerEdep = 1.0 / joule / (v.mass / kg);` (`:72`), applied as `entry.sum = tally->sum * gyPerEdep;` (`:77`) and `entry.sumSq = tally->sumSq * gyPerEdep * gyPerEdep;` (`:78`) |
| Factors divided | mass (`v.mass / kg`) only |
| Output unit | `entry.unit = "Gy";` (`:76`); CSV columns `raw_dose_Gy` / `weighted_dose_Gy` (`:97`) |
| Dimensional check | `sum/joule` → J; `/ (mass/kg)` → kg ⇒ J/kg = Gy |

### 1.2 Mass/volume selection rule

- Single call site: `include/Scoring/DoseContext.hh:25` `logical->GetMass(true, false, step->GetPreStepPoint()->GetMaterial())` (semantics in §0.3).
- Keying: one accumulator per **physical touchable path** — `auto& volume = volumes_[hit.doseVolumePath];` (`DoseScorer.cc:52`), with the path built as `/LVName#copyNo/.../LVName#copyNo` from world depth down (`DoseContext.hh:36-42`). Copies are therefore separate rows, never summed.
- First-hit freeze + change guard: `:53-55` `if (volume.mass == 0.0) { volume.mass = hit.doseMass; volume.name = hit.volumeName; }` then `:56-58` `else if (std::abs(volume.mass - hit.doseMass) > 1e-9 * volume.mass) throw std::runtime_error("DoseScorer detected changing mass for touchable " + hit.doseVolumePath);`
- Fallback behaviour: **none**. `:46-48` `if (hit.doseVolumePath.empty() || !std::isfinite(hit.doseMass) || hit.doseMass <= 0.0) throw std::runtime_error("DoseScorer requires a positive Geant4 physical-volume mass and touchable path for " + hit.volumeName);` The run fails (latched as `scoring_dose`) rather than substituting a density or a nominal mass.
- Subvolumes/daughters: no aggregation. Each sensitive physical touchable is its own row; a mother's mass excludes daughter mass (Geant4 `propagate=false`), and Dose never uses `fluenceVolume`.
- Unverified: that `GetMass(true,false,...)` is correct for *every* complex daughter/replica/parameterised layout. The repo itself says so (`docs/输出数据契约.md:80`: "`GetMass(true,false,preStepMaterial)` 在复杂 daughter/replica 等几何下的语义尚未专项验证"). Follow-up: `grep -rn "GetMass" src include` (only `DoseContext.hh:25`) and per-shape regressions `scripts/test_geometry_a5.py` (replica slices, 5σ), `scripts/test_dose_scoring.py:190-335` (mother-with-daughter, nested parameterised copies).

### 1.3 Normalization object — exactly what is computed

| Normalization | Computed? | Evidence |
| --- | --- | --- |
| Per mass | **yes**, the only one | `DoseScorer.cc:72` `1.0 / joule / (v.mass / kg)`; CSV `:104-105` `Number((v.rawEdep.sum / joule) / massKg)` |
| Per event | **no** — an absolute run total per touchable; per-event value exists only downstream as `mean_per_event = e.sum / events` in the statistics CSV (`src/Output/OutputManager.cc:313`) |
| Per primary / per history | **no** (docs `docs/输出数据契约.md:80`: "尚未按源强、注量、时间或事件数归一化") |
| Per area / per fluence | **no** |
| Per volume | **no** |

### 1.4 LET numerator / denominator

N/A for Dose. (For cross-reference: Dose CSV v1/v2 never carried `LETcalc`/`LETstep`; see §3.4.)

### 1.5 DDD particle spectrum / NIEL

N/A for Dose.

### 1.6 Statistics

| Aspect | Facts |
| --- | --- |
| Per-event sum / sum_sq | Per-event value is the summed edep of that event in that touchable (`DoseScorer.cc:59`); `EndEvent` folds it: `:37-41` `++events_; touched_.EndEvent();` → `HistoryTallySet::EndEvent` → `HistoryTally::Close()` (`src/Scoring/HistoryStatistics.cc:8-22`) adds `event` to `sum`, `event*event` to `sumSq`, `++entries` |
| Zero-event contributions | Events with no hit in that touchable are **not** visited (`touched_` only holds tallies added to). They contribute `x_i = 0`, which adds 0 to sum/sumSq and does not increment `entries` — consistent with the documented estimator ("events that scored nothing count as x_i = 0", `include/Scoring/HistoryStatistics.hh:7-8`) |
| Denominator N | the **run event count**, not `entries`: `src/Actions/RunAction.cc:237-238` `outputManager->WriteScorerStatisticsCsv(runID, run->GetNumberOfEvent(), runTimer_.GetRealElapsed())` |
| N < 2 | `UncertaintyStatus` returns `"insufficient_events"` (`HistoryStatistics.cc:49`); the numeric `rel_error` is 0.0 because `sumSq/sum² − 1/N = 0` at N=1 (`:55-64`), i.e. it is *not* a usable error |
| Zero denominator / zero total | `RelativeError` returns 0.0 when `events <= 0 \|\| sum == 0.0` (`:59`); status becomes `zero_total` (`:51`) or `insufficient_events` |
| Ratio quantity | not used by Dose (`e.ratio == false`) |
| Estimator / formula location | `src/Scoring/HistoryStatistics.cc:55-64` `RelativeError`: `R = sqrt(sumSq/sum² − 1/N)` computed overflow-safely as `(sumSq/sum)/sum - 1/events`; `std_error = rel_error * \|value\|` at `src/Output/OutputManager.cc:318`; FOM at `HistoryStatistics.cc:77-84` |
| Per-worker merging | `HistoryStatistics::Submit` (`:111-136`) under a mutex, keyed by `(runId, scorer, quantity, key)`, adding `sum/sumSq/entries` with `ScoringNumeric::Add`; master takes and erases the map after writing (`src/Actions/RunAction.cc:233-241`, `HistoryStatistics::Take` `:138-148`) |
| Which thread writes what | per-worker CSV via `ScoringManager::WriteAll` (`src/Scoring/ScoringManager.cc:645-649`), called only for `role_ != Role::Master` (`src/Actions/RunAction.cc:191-196`); merged statistics CSV only for `role_ != Role::Worker` (`:233-242`) |
| Statistical vs physical/systematic | Only the event-moment **statistical** error is computed. `grep -rn "systematic" src include` returns **no match**; the header itself labels the estimator "uncorrected event-moment approximation" (`include/Scoring/HistoryStatistics.hh:12-13`), and the export path marks physical validation as not established: `scripts/extensions/dose_json_extension.py:23` `"physical_validation": "not_established"` |

### 1.7 Output files / columns (exact emitted header)

CSV: `dose_volume_summary_t<N>[_r<R>].csv` — `DoseScorer.cc:95` `CsvWriter writer(output.MakeOutputPath(output.MakeThreadFilename("dose_volume_summary.csv")));`, header `:96-98`:

```
runID,volume_path,volume_name,mass_kg,raw_edep_MeV,weighted_edep_MeV,raw_dose_Gy,weighted_dose_Gy,raw_edep_sum_sq_MeV2,weighted_edep_sum_sq_MeV2,n_events
```

Row order `:102-107`: `runID, volume_path, volume_name, mass_kg, raw_edep_MeV, weighted_edep_MeV, (raw_edep/joule)/mass_kg, (weighted_edep/joule)/mass_kg, raw_edep_sum_sq/MeV², weighted_edep_sum_sq/MeV², events_`. Registration: `:110-111` `RegisterGeneratedFile(..., OutputManager::ArtifactScope::Thread, ...)`.

Numbers are formatted with `std::setprecision(12)` (`DoseScorer.cc:14-19`).

ROOT (format `root`/`both`): ntuple `dose` booked at `src/Output/AnalysisOutput.cc:81-86` with columns `runID, threadID, volume_path, volume_name, mass_kg, raw_edep_MeV, weighted_edep_MeV, raw_dose_Gy, weighted_dose_Gy, raw_edep_sum_sq_MeV2, weighted_edep_sum_sq_MeV2, n_events`; filled by `AnalysisOutput::FillDose` (`:204-215`), called from `DoseScorer.cc:88-91`.

Merged statistics CSV `scorer_statistics[_r<R>].csv` rows `scorer=dose`, `quantity=raw_dose` / `weighted_dose` (`DoseScorer.cc:80-81`), header at `src/Output/OutputManager.cc:296-298`:

```
runID,scorer,quantity,key,name,unit,estimator,n_events,entries,value,mean_per_event,std_error,rel_error,fom_per_s,run_wall_time_s,sum,sum_sq,uncertainty_estimator,uncertainty_status
```

`run_summary.txt` schema tag: `dose_volume_csv_v2` for the emitted 11-column header, `dose_volume_csv_v1` for the legacy 8-column header (`src/Output/RunSummary.cc:73-79`).

### 1.8 Existing validation

| Test / function | What it asserts |
| --- | --- |
| `scripts/test_dose_scoring.py` — `check_output()` `:41-107` | one CSV per worker per run (`:55`); header equality (`:63`); `volume_path` ends `/Target_PV#0` (`:77`); `mass_kg` within 1.5 % of the analytic `2.329e-4` kg for 10×10×1 mm Si (`:59`, `:80`); `raw_dose_Gy == Σedep_MeV · 1.602176634e-13 / mass_kg` at `rel_tol=2e-9` (`:87`) — **independent recomputation from the row's own columns**; run IDs (`:91`); `run_summary` contains `dose_volume_summary` and `dose_volume_csv_v2` (`:94`) and registers every CSV (`:96-97`) |
| `check_output_extension()` `:110-187` | `scripts/run_output_extension.py --run dose_json` aggregates worker CSVs: `units == {mass:kg, edep:MeV, dose:Gy}`, `physical_validation == not_established`, per-volume `dose == E·MEV_J/mass`, `thread_ids == [0,1]` |
| `check_mother_mass()` `:190-268` | water mother 8 cm³ minus 1 cm³ child = 7 g (`:238-244`); Pb child 0.01135 kg — i.e. daughter-subtracted mass is checked numerically |
| `check_nested_and_invalid_mass()` `:271-335` | nested parameterised copies 0.007 / 0.01631 kg (`:294`); overlapping daughters must fail with `"DoseScorer requires a positive Geant4 physical-volume mass"` and `output_failure_stage = scoring_dose` (`:321-326`) |
| `scripts/test_statistical_uncertainty.py:157-163` | single dose row; `dose.value == total_hits_edep·MEV_IN_JOULES/mass` (`:161`); `dose.rel_error == edep_volume.rel_error` (`:162`); `std_error == value·rel_error` (`:163`) |
| `scripts/test_scoring_mesh.py:229-230` | native Geant4 `doseDeposit` mesh vs DoseScorer: `rel_close(float(merged[("depthMesh","dose")].value.mean()), float(dose["raw_dose_Gy"].sum()), 1e-9, ...)` |
| `scripts/test_geometry_a5.py:271-282` | replica z-slices: per-slice mass 25 g each and per-slice dose matches explicit slabs (`\|pull\| < 5`) |
| `scripts/test_biasing_step_weight.py:86,106` | weighted dose total vs native weighted energyDeposit at biasing factor 0.1 / 1 / 10 |
| `scripts/test_semiconductor_device.py:117-129` | production-cut independence of substrate TID: `cut 1 um` vs `cut 1 mm` within 1 % + 3σ |
| Physical benchmark `scenarios/benchmarks/device_dose` | reference TID from PSTAR Si electronic stopping power (`scenarios/benchmarks/device_dose/make_reference.py:8-9,27,85`), compared in the device scenario; `docs/功能支持矩阵.md:140` reports −0.38…+0.14 % vs PSTAR for 10–200 MeV protons |

Coverage gaps (explicit): no non-EM validation, no source-strength/time/fluence normalization, no dose in the zero-Edep branch (by construction), no systematic uncertainty, no check of `GetMass` semantics for every geometry shape (see §1.2), and the mother-with-daughter case is an intentional *failure* for Fluence but a *supported* case for Dose.

### 1.9 Line check — "if mass were double-applied, would this quantity's current tests fail?"

**yes** — `scripts/test_dose_scoring.py:87` recomputes `dose = energy·MEV_J/mass` from the same row's `mass_kg`/`raw_edep_MeV` at `rel_tol=2e-9` (~4300× mismatch for a 1 mm Si target if `mass` entered twice), `scripts/test_statistical_uncertainty.py:161` repeats it at 1e-9, and `gui/g4usim_gui/output/dose_summary.py:87-90` raises `"Dose/energy/mass mismatch"` at 1e-8; if instead the *stored* `v.mass` itself were doubled, `:80` (mass within 1.5 % of `2.329e-4`) fails. Weight double-application is caught only in the biased run (`scripts/test_biasing_step_weight.py:86`). Volume is never used by Dose, so a volume defect cannot be caught here.

---

## 2. Fluence (`[scoring] fluence = true`)

### 2.1 Quantity definition in code

| Item | Facts |
| --- | --- |
| Accumulated per step | `touched_.Add(volume.rawLength, hit.stepLength);` (`src/Scoring/FluenceScorer.cc:65`) and `touched_.Add(volume.weightedLength, weightedStep);` (`:66`) with `const double weightedStep = hit.stepLength * hit.weight;` (`:60`) |
| Length measure | `hit.stepLength` = Geant4 step length (`G4Step`), i.e. straight-line chord inside the sensitive solid |
| Steps skipped | `if (hit.stepLength == 0.0) return;` (`:49`); non-finite/negative length or non-finite weight throws (`:46-48`) |
| Includes zero-Edep transport | yes — the SD zero-deposit branch calls `ScoreFluenceStep` (`src/Hits/SensitiveDetector.cc:103`) |
| Factors multiplied / divided | `rawLengthMm / volumeMm3` and `weightedLengthMm / volumeMm3` (`:83-84`); `sumSq` divided by `mm²` then by `volumeMm3²` (`:85-86`, `:104`) |
| Output unit | `entry.unit = "mm-2";` (`:102`); CSV columns `raw_fluence_mm-2` / `weighted_fluence_mm-2` (`:119`) |
| Dimensional check | mm / mm³ = mm⁻² |

Definition is **track-length fluence inside the solid**, not surface-crossing fluence (also stated by the extension: `scripts/extensions/fluence_json_extension.py:27` `"definition": "track_length / sensitive_solid_volume; not surface-crossing fluence"`).

### 2.2 Mass/volume selection rule

- Volume source: `DoseContext.hh:29-31` `logical->GetNoDaughters() == 0 && logical->GetSolid()` → `GetSolid()->GetCubicVolume()`; **no fallback** — a sensitive volume with daughters leaves `fluenceVolume` at its default and the scorer throws (`FluenceScorer.cc:50-52`):

  `throw std::runtime_error("FluenceScorer requires a positive daughter-free sensitive solid volume and touchable path for " + hit.volumeName);`

- Keying: per physical touchable `doseVolumePath` (`:53`); copies get separate rows.
- First-hit freeze + change guard: `:54-59` `if (volume.volume == 0.0) {...} else if (std::abs(volume.volume - hit.fluenceVolume) > 1e-9 * volume.volume) throw ... "FluenceScorer detected changing volume for touchable "`.
- Rationale for the daughter exclusion is in `DoseContext.hh:26-28` (mother cube would include daughter volume).
- Unverified: `GetCubicVolume()` accuracy for non-box solids (no doc/test asserts it; follow-up: `grep -rn "GetCubicVolume" src include` and `scripts/test_scoring_mesh.py` cylinder case).

### 2.3 Normalization object

| Normalization | Computed? | Evidence |
| --- | --- | --- |
| Per volume | **yes** — the only one | `FluenceScorer.cc:83-84` `const double rawFluence = rawLengthMm / volumeMm3;` |
| Per mass | no | — |
| Per event / primary / area | no | run total per touchable; per-event value only downstream (`OutputManager.cc:313`) |

### 2.4 LET numerator / denominator

N/A for Fluence. (Note the LET scorer reuses the same per-touchable key and the same `stepLength`, §3.1.)

### 2.5 DDD particle spectrum / NIEL

N/A. (DDD reuses the Fluence volume rule and `stepLength`, §4.)

### 2.6 Statistics

Identical machinery to Dose, with length instead of energy:

- `EndEvent` `:40-41` `++events_; touched_.EndEvent();`
- `entry.sum = (weighted ? r.weightedLengthMm : r.rawLengthMm) * inverseVolume;` (`:103`) and `entry.sumSq = ... * inverseVolume * inverseVolume;` (`:104`), i.e. the constant 1/V is applied to the *already summed* totals — valid only because the volume is frozen (`:57-59`)
- N = run event count (`RunAction.cc:237-238`); zero-event contributions `x_i = 0` via `HistoryTally::Close` (`HistoryStatistics.cc:11-19`); `entries` counts only events with non-zero track length
- N<2 / zero denominator: `insufficient_events` / `zero_total` / `undefined_ratio` (`HistoryStatistics.cc:47-53`); numeric 0.0 from `RelativeError` (`:55-64`)
- Merging: additive per-run registry (`HistoryStatistics.cc:111-136`); per-worker CSVs are **not** merged by the backend
- No systematic term (`grep -rn "systematic" src include` → no match)

### 2.7 Output files / columns (exact emitted header)

CSV `fluence_volume_summary_t<N>[_r<R>].csv`, `FluenceScorer.cc:117-120`:

```
runID,volume_path,volume_name,volume_mm3,raw_track_length_mm,weighted_track_length_mm,raw_fluence_mm-2,weighted_fluence_mm-2,raw_track_length_sum_sq_mm2,weighted_track_length_sum_sq_mm2,n_events
```

ROOT ntuple `fluence` (`src/Output/AnalysisOutput.cc:87-93`), filled by `FillFluence` (`:217`), called from `FluenceScorer.cc:109-115`. Statistics rows `scorer=fluence`, `quantity=raw_fluence|weighted_fluence` (`:106`). Summary schema `fluence_volume_csv_v2` (11 columns) / `fluence_volume_csv_v1` (8 columns) at `src/Output/RunSummary.cc:97-104`.

### 2.8 Existing validation

| Test / function | What it asserts |
| --- | --- |
| `scripts/test_fluence_scoring.py` `check()` `:38-70` | exactly `threads × runs` files (`:40`); header equality (`:49`); one row per file (`:51`); `volume_mm3 == 100.0` at 1e-9 (`:56`); `phi == length/volume` at `rel_tol=2e-9` (`:61`); summary `status = completed`, `fluence_volume_csv_v2`, all files registered (`:66-69`) |
| `main()` `:73-131` | disabled → no CSV (`:82`); geantino (zero-Edep transport) 12 events → `raw_track_length_mm == 12.0` at 1e-6 (`:91`) and weighted == raw (`:92`), and no fabricated hits rows (`:94-96`); 2 threads × 2 runs with Dose coexisting (`:99-102`); M5 `fluence_json` extension: 2 volumes, `thread_ids [0,1]`, `volume_mm3 == 100`, aggregated lengths equal per-thread sums, `fluence == total/100` (`:113-126`); invalid config `auto_create_default_scorers = false` fails and writes no CSV (`:128-130`) |
| `scripts/test_statistical_uncertainty.py:167-175` | per-thread `n_events` sum == run events; merged `rel_error` equals `rel_error(Σ lengths, Σ length², N)` at 1e-7 |
| `scripts/test_scoring_mesh.py:231-233` | native `cellFlux [cm-2 → mm-2]` vs FluenceScorer at 1e-9 |
| `scripts/test_biasing_step_weight.py:87,106` | weighted fluence total vs native weighted cellFlux at factor 0.1/1/10; `:81-83` proves the zero-deposition branch is exercised |
| `scripts/test_shielding_coating.py` | uses integrated flux spectra and interface thinning; does not assert Fluence CSV values directly (see §8 table for what it does assert) |

Gaps: no independent physical benchmark for the track-length estimator; no surface-crossing fluence; no daughter-containing geometry; no general bias unbiasedness claim.

### 2.9 Line check — "if the volume were double-applied, would the current tests fail?"

**yes** — `scripts/test_fluence_scoring.py:61` asserts `phi == length/volume` using the row's own `volume_mm3` at `rel_tol=2e-9`; dividing by V² would be off by 100× (V = 100 mm³). If instead the stored volume were wrong, `:56` (`volume == 100.0`) fails. Weight double-application is caught only by the biased run (`scripts/test_biasing_step_weight.py:87`); in unbudgeted (weight = 1) runs `w² = w`. Mass is not used by Fluence, so no mass defect can be caught here.

---

## 3. LET (`[scoring] let = true`)

### 3.1 Quantity definition in code

Documented contract (`include/Scoring/LETScorer.hh:11-23`):

```
// For every charged step in a sensitive volume the SensitiveDetector supplies
// S = unrestricted electronic stopping power (G4EmCalculator::ComputeElectronicDEDX)
// at the step's mean kinetic energy, in HitRecord::LETstep (Geant4 units, MeV/mm).
// With step length l and track weight w the scorer accumulates
//   sum_wl = sum w*l,  sum_wSl = sum w*S*l,  sum_wS2l = sum w*S^2*l
// and reports LET_t = sum_wSl / sum_wl and LET_d = sum_wS2l / sum_wSl
// (keV/um, numerically equal to MeV/mm). The sums are additive across threads.
```

| Item | Facts |
| --- | --- |
| `S` production | `src/Hits/SensitiveDetector.cc:286-299` `ElectronicStoppingPower`: returns `0.0` if no step / `stepLength <= 0` / missing track, pre/post point or material / `particle->GetPDGCharge() == 0.0` / `meanEnergy <= 0.0`; `:295` `const G4double meanEnergy = 0.5 * (pre->GetKineticEnergy() + post->GetKineticEnergy());`; `:297` `const G4double dedx = emCalculator_.ComputeElectronicDEDX(meanEnergy, particle, pre->GetMaterial());`; `:298` `return std::isfinite(dedx) && dedx > 0.0 ? dedx : 0.0;` |
| `S` supply to scorer | `record.LETstep = ElectronicStoppingPower(step);` at `src/Hits/SensitiveDetector.cc:133` (normal branch) and `:106` (zero-deposit branch, only when LET enabled) |
| Step gate | `src/Scoring/LETScorer.cc:75` `if (!ScoringNumeric::PositiveLETStep(hit.LETstep, hit.stepLength, hit.weight)) return;` — `include/Scoring/NumericChecks.hh:32-38` requires finite positive stopping power, positive length, finite weight |
| Particle filter | `:76` `if (!particles_.empty() && particles_.count(hit.particleName) == 0) return;` — empty set means "all charged" (`LETScorer.hh:35`, CSV shows `all_charged`, `LETScorer.cc:26`) |
| Accumulation | `:80` `const double s = hit.LETstep / (MeV / mm);` `:81` `const double l = hit.stepLength / mm;` `:83` `wl = w*l`, `:84` `wsl = wl*s`, `:85` `ws2l = wsl*s`; per-event sums `:86-88`; `:94` `++volume.steps;` |
| Output unit | `entry.unit = "keV/um";` (`:123`), `entry.ratio = true;` (`:124`), CSV columns `let_t_keV_per_um`, `let_d_keV_per_um` (`:151`) |

### 3.2 Mass/volume selection rule

- LET needs **no mass and no volume**: the only geometry input is the sensitive touchable key. `:77-79` `if (hit.doseVolumePath.empty()) throw std::runtime_error("LETScorer requires a sensitive touchable path for " + hit.volumeName);`
- It never reads `hit.doseMass` or `hit.fluenceVolume`; therefore the daughter/volume rule of §0.3 does **not** constrain LET, and a sensitive mother with daughters is scored (only its touchable path is used).
- Keying: `volumes_[hit.doseVolumePath]` (`:82`), one row per physical touchable path.
- The LET CSV has **no** `volume_mm3` or `mass_kg` column at all (`:150-153`).

### 3.3 Normalization object

| Normalization | Computed? | Evidence |
| --- | --- | --- |
| Ratio `Σ w·S·l / Σ w·l` (track-averaged, `LET_t`) | **yes** | `:112` `const double letT = v.sumWL > 0.0 ? v.sumWSL / v.sumWL : 0.0;` |
| Ratio `Σ w·S²·l / Σ w·S·l` (dose-averaged, `LET_d`) | **yes** | `:113` `const double letD = v.sumWSL > 0.0 ? v.sumWS2L / v.sumWSL : 0.0;` |
| Per mass / per volume / per event / per primary | no | run-aggregate ratios; per-event normalization refused by the GUI for LET (`gui/g4usim_gui/output/plot_data.py:412-418`: per-event normalization for `let` raises `ValueError`) |

### 3.4 LET numerator and denominator, explicitly (incl. units conversion)

| Quantity | Numerator (code symbol → unit) | Denominator (code symbol → unit) | Emitted value / unit |
| --- | --- | --- | --- |
| `LET_t` | `sumWSL` = Σ w·S·l → MeV (`LETScorer.hh:44`) | `sumWL` = Σ w·l → mm (`:43`) | MeV/mm; labelled `keV/um` in CSV (`:151`) and statistics (`:123`) |
| `LET_d` | `sumWS2L` = Σ w·S²·l → MeV²/mm (`:45`) | `sumWSL` = Σ w·S·l → MeV | MeV/mm; same label |

Units conversion in code is a pure **scale extraction**, not a physical conversion:

```cpp
const double s = hit.LETstep / (MeV / mm);   // LETscorer.cc:80
const double l = hit.stepLength / mm;        // :81
```

`MeV/mm == 1` and `mm == 1` in Geant4 internal units, so `s` is the stopping power **in MeV/mm numerically**. The label `keV/um` is numerically identical: `1 MeV/1 mm = 1000 keV / 1000 µm = 1 keV/µm`. Hence no multiplication by 10 or 1000 exists anywhere in `src/Scoring/LETScorer.cc` — confirmed by reading `:100-164` in full.

Ratio uncertainty (delta method), documented at `LETScorer.hh:20-23` and implemented through the generic ratio moments:

- per-event `a = Σ w·l`, `b = Σ w·S·l`, `c = Σ w·S²·l` are folded into `Σa², Σb², Σc², Σab, Σbc` (`LETScorer.cc:56-63`)
- `LET_t = B/A` uses `sum = sumWSL`, `sumSq = sumSqWSL`, `denSum = sumWL`, `denSumSq = sumSqWL`, `crossSum = sumWLxWSL` (`:127-131`); `LET_d = C/B` uses `:132-136`
- formula `R² = sumSq_B/B² + sumSq_A/A² − 2·sum_AB/(A·B)` lives in `src/Scoring/HistoryStatistics.cc:66-75` `RatioRelativeError`, documented at `include/Scoring/HistoryStatistics.hh:16-19`

`LETcalc` / `LETstep` columns — status:

| Item | Facts |
| --- | --- |
| `HitRecord::LETcalc` | defined `include/Output/OutputRecord.hh:35`; assigned only from `ParticleHit::LETcalc_` in `src/Hits/ParticleHit.cc:131`; `ParticleHit::SetLETcalc` (`:96`) has **no call site** in `src/` or `include/` (grep) ⇒ always `0.0` |
| `HitRecord::LETstep` | set only when LET is enabled (`src/Hits/SensitiveDetector.cc:106,133`) |
| In CSV | hits CSV **v3** has no LET column: `src/Output/OutputManager.cc:823-830` `HitHeader()` ends `"process", "volume", "weight"`; the **v2** header with `...,weight,LETcalc,LETstep` survives only as a schema-recognition string in `src/Output/RunSummary.cc:55-57`; `docs/输出数据契约.md:73` states the v2 columns were zero-value placeholders and "**不得用旧列推断 LET**" |
| In ROOT | `FillHit` (`src/Output/AnalysisOutput.cc:165-175`) and the hits ntuple booking (`:61-67`) also omit LET |

### 3.5 DDD particle spectrum / NIEL

N/A for LET.

### 3.6 Statistics

| Aspect | Facts |
| --- | --- |
| Per-event sum / sum_sq | three per-event sums (`eventWL/eventWSL/eventWS2L`) folded in `EndEvent` `:48-70`; `++entries` only for touched volumes (`:64`) |
| Zero-event contributions | a volume not touched in an event is skipped entirely, equivalent to `a=b=c=0`; with the ratio estimator the `1/N` terms cancel (`HistoryStatistics.hh:16-19`) |
| Denominator N | run events, from `run->GetNumberOfEvent()` (`RunAction.cc:237`) — not `entries`, not `steps` |
| N<2 | `UncertaintyStatus` → `"insufficient_events"` (`HistoryStatistics.cc:49`) |
| Zero denominator | `RatioRelativeError` returns 0.0 when either total is 0 (`HistoryStatistics.cc:71`); status `"undefined_ratio"` when `ratio && denominator == 0.0` (`:50`); `LET_t`/`LET_d` themselves are emitted as `0.0` in that case (`LETScorer.cc:112-113`) |
| Estimator strings | `uncorrected_delta_ratio_v1` (`src/Output/OutputManager.cc:324`) |
| Merging | additive per-run registry as for Dose (`HistoryStatistics.cc:111-136`) |

### 3.7 Output files / columns (exact emitted header)

CSV `let_volume_summary_t<N>[_r<R>].csv`, `LETScorer.cc:150-153`:

```
runID,volume_path,volume_name,particles,steps,sum_wl_mm,sum_wSl_MeV,sum_wS2l_MeV2_per_mm,let_t_keV_per_um,let_d_keV_per_um,sum_sq_wl_mm2,sum_sq_wSl_MeV2,sum_sq_wS2l_MeV4_per_mm2,sum_wl_x_wSl_MeV_mm,sum_wSl_x_wS2l_MeV3_per_mm,n_events
```

`particles` is `all_charged` or space-joined names (`:24-30`). ROOT ntuple `let` booked at `src/Output/AnalysisOutput.cc:99-106`, filled by `FillLET` (`:242`), called from `LETScorer.cc:140-147`. Statistics rows `scorer=let`, `quantity=let_t|let_d` (`:137-138`). Summary schema `let_volume_csv_v1` (10 columns) / `let_volume_csv_v2` (16 columns) at `src/Output/RunSummary.cc:84-91`.

### 3.8 Existing validation

| Test / function | What it asserts |
| --- | --- |
| `scripts/test_let_scoring.py` `main()` `:133-172` | 20 µm water slab, 2 threads, `let = true`, `dose = true`, `fluence = true`; for 100 MeV and 10 MeV protons `LET_t` must match an **analytic Bethe** electronic mass stopping power within 2 % (`:85-92` function, `:144-149` assertion with the half-slab energy-loss correction), `LET_d ≥ LET_t` (`:150`) and `LET_d < 1.05·LET_t` (`:151`); all-charged adds steps (`:156`); 1 MeV photon beam gives `steps == 0` (`:161-162`); enabling LET from a macro after `let = false` in the INI is rejected with the "main INI [scoring]" guidance (`:165-167`) |
| `merged()` `:111-131` | CSV columns must be additive and match ROOT: sums of `sum_wl_mm` etc. equal the ROOT totals at 1e-9 |
| `scripts/test_dose_scoring.py:356` | dose + LET coexistence writes `let_volume_summary_t*.csv` |
| `scripts/test_statistical_uncertainty.py:130-131,137-148,188-214` | `("let","let_t")` and `("let","let_d")` must be present with `n_events == events`; independent recomputation from hits (for edep, not LET); 20-run observed spread vs reported `R` ratio in (1/1.5, 1.5) and `1/√N` scaling |
| `scripts/test_scoring_numeric.py:145-151` | `uncertainty_estimator == "uncorrected_delta_ratio_v1"` for `let`; `uncertainty_status == "approximate"` when `events >= 2` |

Gaps: no heavy-ion LET, no thick-target/spectrum benchmark, no validation of `ComputeElectronicDEDX` for arbitrary materials/energy (the test only compares 100/10 MeV protons in water), no nuclear stopping, and `LET_d` heavy-tail behavior is explicitly not validated (`docs/功能支持矩阵.md:160`).

### 3.9 Line check — "if mass/volume/weight were double-applied, would the current tests fail?"

**no for mass and volume** — neither symbol appears in `LETScorer.cc` (the ratio is `ΣwSl/Σwl`, `:112-113`); a mass or volume defect cannot change `LET_t`/`LET_d`, so no LET assertion can detect one. **Partially for weight:** `w` multiplies numerator and denominator, so an erroneous `w²` changes only the weighting (not the scale) and the 2 % Bethe check would almost certainly still pass; the CSV's `sum_wl_mm` column is not compared against an independently weighted reference in `scripts/test_let_scoring.py`.

---

## 4. DDD / Displacement damage dose (`[scoring] displacement = true`)

### 4.1 Quantity definition in code

Contract (`include/Scoring/DisplacementScorer.hh:12-22`):

```
// DDD = sum over steps of w * l * NIEL(E_mean) / V (MeV/g), E_mean = mean of
// pre/post-step kinetic energy ... Particles without a table are not scored;
// steps outside a table's energy range add to out_of_range_track_length and
// contribute no DDD. The result is as good as the supplied NIEL tables and the
// fluence estimate; Geant4's own non-ionizing energy deposit is not used.
```

| Item | Facts |
| --- | --- |
| Particle selection | `src/Scoring/DisplacementScorer.cc:52-53` `const auto table = tables_.find(hit.particleName); if (table == tables_.end()) return;` ⇒ **only particles with an explicitly configured NIEL table are scored**; everything else (including all neutral particles and all particles without a table) is silently skipped |
| Step length measure | `:71` `const double lengthMm = ScoringNumeric::Multiply(hit.weight, hit.stepLength / mm, "DDD weighted length");` — weighted length, mm |
| Energy for the NIEL lookup | `:73` `table->second->Evaluate(hit.meanKineticEnergy, niel)`; `meanKineticEnergy` = mean of pre- and post-step kinetic energy (`include/Scoring/DoseContext.hh:32-35`) |
| Zero / invalid steps | `:58` `if (hit.stepLength == 0.0) return;`; `:54-57` non-finite/negative length, weight or energy throws `"DisplacementScorer rejects nonfinite/negative step length, weight or energy"` |
| Out of domain | `:73-76` adds the weighted length to `outOfRangeLength` and returns **without** any DDD |
| In domain | `:77` `particle.trackLength = ScoringNumeric::Add(particle.trackLength, lengthMm, "DDD track length");` |
| DDD per step | `:78` `const double ddd = lengthMm * niel * kMm2PerCm2 / (volume.volume / (mm * mm * mm));` with `constexpr double kMm2PerCm2 = 100.0;` (`:21`) |
| Accumulation | `:80-83` `if (ddd > 0.0) { touched_.Add(particle.ddd, ddd); touched_.Add(volume.total, ddd); }` |
| Output unit | `total.unit = "MeV/g";` (`:92`); CSV `ddd_MeV_g`, `ddd_sum_sq_MeV2_g2` (`:108`) |

Dimensional derivation of `:78` (arithmetic, no code comment states it):

```
l [mm] · NIEL [MeV·cm²/g] · 100 [mm²/cm²] / V [mm³]
= NIEL · (l/V) [mm/mm³ = 1/mm²] · 100 [mm²/cm²]
= NIEL · Φ  [MeV·cm²/g · 1/cm²] = MeV/g
```

So `kMm2PerCm2` is an **area-unit conversion for the track-length density**, and the resulting DDD is `Σ w·l·NIEL(E)/V` in MeV/g. It therefore inherits the Fluence track-length estimator (no surface crossing) and the daughter-free volume rule (§2.2).

### 4.2 Mass/volume selection rule

- Volume source: identical to Fluence — `DoseContext.hh:29-31` daughter-free `GetCubicVolume()`; enforcement `DisplacementScorer.cc:59-62` `throw std::runtime_error("DisplacementScorer requires a positive daughter-free sensitive solid volume and touchable path for " + hit.volumeName);`
- Keying: per physical touchable `doseVolumePath` combined with particle name (`:63`, `:70`); copies are separate rows.
- First-hit freeze + change guard: `:64-69` (1e-9 relative), `"DisplacementScorer detected changing volume for touchable "`.
- No mass is used anywhere in the DDD computation.
- Unverified: `GetCubicVolume()` for non-box solids as in §2.2.

### 4.3 Normalization object

| Normalization | Computed? | Evidence |
| --- | --- | --- |
| Per volume (implicit, inside each step) | **yes** | `:78` division by `volume.volume / (mm*mm*mm)` |
| Per mass | no | MeV/g is a *unit*, not a normalization by an object mass |
| Per event / primary / area / fluence | no | run totals per touchable; per-primary and per-fluence values are only produced by scenario analysis scripts: `scenarios/semiconductor/analyze_device.py:66-68` `"tid_Gy_per_primary": dose / events, "tid_Gy_cm2": dose / events * area, "ddd_MeV_g_per_primary": ddd / events, "ddd_MeV_g_cm2": ddd / events * area` |

### 4.4 LET numerator / denominator

N/A for DDD.

### 4.5 DDD-specific facts: particle spectrum, NIEL identity, conversion

**Particle spectrum** — the scored particles are exactly the keys of `[scoring.displacement]`:

- table map built in `src/Scoring/ScoringManager.cc:702-731`; each entry `tables[particle] = NielTable::Load(file.u8string());` (`:725`)
- keys are Geant4 particle names, resolved case-insensitively against `G4ParticleTable` in `ResolvePendingNielNames` (`ScoringManager.cc:264-290`), called at `BeginRun` (`:439`) so a name that cannot be resolved fails **before the first event** (`docs/功能支持矩阵.md:46`); a name that is already provably wrong is rejected earlier at config time (`ScoringManager.cc:711` `ThrowUnknownParticleName(key, location, lookup.candidates)`), and two keys resolving to the same particle are rejected (`:281-284`)
- missing tables when `displacement = true`: hard failure — `ScoringManager.cc:735-738` `throw std::runtime_error("... [scoring]/displacement = true needs [scoring.displacement] with <particle> = <NIEL table CSV> entries (header energy_MeV,niel_MeV_cm2_g)")`
- the spectrum is therefore **not** "all particles": e.g. electrons are scored only if `[scoring.displacement]` contains an `e-` entry

**NIEL table identity** (`src/Scoring/NielTable.cc`, `include/Scoring/NielTable.hh`):

| Aspect | Facts |
| --- | --- |
| File format | CSV; header must be exactly `energy_MeV,niel_MeV_cm2_g` (`NielTable.cc:31-34` `throw ... ": NIEL table header must be 'energy_MeV,niel_MeV_cm2_g'"`); UTF-8 BOM stripped (`:24`); `#` comments and blank lines skipped (`:26`) |
| Columns | 2: `energy_MeV` (energy in MeV, `> 0`) and `niel_MeV_cm2_g` (NIEL in MeV·cm²/g, finite, `>= 0`) — `:51-53`; exactly 2 columns enforced (`:36`) |
| Ordering / size | strictly increasing energies (`:55-56`), at least 2 rows (`:60-61`) |
| Stored units | `table->energies_.push_back(energy * MeV);` (`:58`) → internal energy units; `table->values_.push_back(niel);` (`:59`) → raw MeV·cm²/g (`NielTable.hh:39` `// MeV cm2/g`) |
| Interpolation | log-log between nodes when both values `> 0` (`:72-76`), linear where a node value is `0` (`:77-79`) |
| Out of domain | `Evaluate` returns `false` when `!(energy >= energies_.front()) \|\| !(energy <= energies_.back())` (`:67`) ⇒ the step becomes `out_of_range_track_length`, no DDD, no extrapolation |
| Domain accessors | `NielTable.hh:29-31` `MinEnergy()`, `MaxEnergy()`, `Size()` |
| Identity available in code | `table->file_ = path; table->inputSha256_ = acceptedInput.sha256;` (`NielTable.cc:20-21`), exposed by `GetFile()` / `GetInputSha256()` (`NielTable.hh:27-28`) |
| Identity emitted | **only the path**: DDD CSV `niel_table` column = `tables_.at(p.first)->GetFile()` (`DisplacementScorer.cc:113`). `GetInputSha256()` has **no call site** in `src/` or `include/` (grep) ⇒ the table hash never reaches any output for DDD. A hash does reach `scenario.json` for the shielding scenario, computed independently in Python: `scenarios/shielding_coating/scenario_model.py:369-377` `digest = hashlib.sha256(table_path.read_bytes()).hexdigest()` … `niel_meta.append({"particle": particle, "path": str(table), "sha256": digest})`, emitted at `:385` |

**Shipped NIEL tables** (`scenarios/semiconductor/niel/`), verified by parsing each CSV (`python` one-off, read-only):

| File | sha256 | Data rows | E range (MeV) | NIEL range (MeV·cm²/g) | Notes (first comment line) |
| --- | --- | --- | --- | --- | --- |
| `si_electron.csv` | `e26af764ceaf9b388434f440c337a8a1b297f1f86862b045499a52b5cc7d8b87` | 92 | 1e-06 … 10000 | 0 … 1.344e-4 | "Electrons in Si, NIEL (screened relativistic Coulomb, Robinson partition). Source: SR-NIEL web calculator (https://www.sr-niel.org), SR-NIEL-7 ver. 11.1, retrieved 2026-10-22." |
| `si_neutron.csv` | `a2ad28a9fcce3500fca363946e09e19125d084f1b596eff76662b272c242034f` | 640 | 1.025e-10 … 19.95 | 1.2437e-07 … 4.2869e-3 | "Neutrons in Si, NIEL from the ASTM E722-19 damage function (Table A1.1) as served by the SR-NIEL ASTM calculator." |
| `si_proton.csv` | `6c21e35aab18495d4bb2597a76be60c7c35ef0df963224e0108c77c2e4c208d5` | 146 | 1e-06 … 10000 | 0 … 5.6222 | "Protons in Si, NIEL (Coulomb + hadronic, Robinson partition)." |

All three have header `energy_MeV,niel_MeV_cm2_g`, strictly increasing energies, no non-positive energies; `si_electron.csv` and `si_proton.csv` contain exact `0` NIEL nodes (hence the linear-interpolation branch is reachable). Table generation/reference tooling: `scenarios/semiconductor/niel/convert_srniel.py`, README in the same directory.

### 4.6 Statistics

| Aspect | Facts |
| --- | --- |
| Per-event sum / sum_sq | per-event DDD is the sum over in-domain steps of that event (`:80-83`); `EndEvent` `:44-48` `++events_; touched_.EndEvent();` |
| Zero-event contributions | volumes/particles not touched contribute `x_i = 0`; `entries` counts only non-zero events (`HistoryStatistics.cc:11-19`) |
| Denominator N | run events (`RunAction.cc:237`) |
| N<2 / zero total | `insufficient_events` / `zero_total` (`HistoryStatistics.cc:47-53`); numeric `rel_error` 0.0 |
| Merging | additive registry; `ddd_total` per touchable (`DisplacementScorer.cc:90-96`) and `ddd_<particle>` per touchable (`:97-103`); `total.sum` is the all-particle sum because both tallies receive the same value (`:81-82`) |
| Estimator | `uncorrected_event_moments_v1` (`OutputManager.cc:324`) |
| No systematic term | `grep -rn "systematic" src include` → no match |

### 4.7 Output files / columns (exact emitted header)

CSV `displacement_volume_summary_t<N>[_r<R>].csv`, `DisplacementScorer.cc:106-109`:

```
runID,volume_path,volume_name,particle,niel_table,volume_mm3,track_length_mm,out_of_range_track_length_mm,ddd_MeV_g,ddd_sum_sq_MeV2_g2,n_events
```

Per-document note: `docs/输出数据契约.md:54` documents the same header and states the lengths are weighted and all columns except `volume_mm3`/`niel_table` are additive across workers. **No ROOT ntuple exists for DDD** — `AnalysisOutput` books `hits`, `events`, `edep_volume`, `edep_particle`, `dose`, `fluence`, `mesh`, `let` only (`src/Output/AnalysisOutput.cc:61-106`); the ROOT-only path still produces the statistics CSV (`scripts/test_displacement_damage.py:330-333` asserts no displacement CSV but `ddd_total > 0`). Summary schema `displacement_volume_csv_v1` at `src/Output/RunSummary.cc:92-95`.

### 4.8 Existing validation

`scripts/test_displacement_damage.py` (392 lines) is the only DDD-specific test:

| Function | What it asserts |
| --- | --- |
| `muon_summary_checks()` `:174-211` | volume 10000 mm³, particles exactly the configured table keys, `niel_table` path identity, finite non-negative numbers, per-worker `n_events`, master `n_events == events` |
| `check_summary_counterexamples()` `:214-258` | 5 accepted summary layouts / 16 rejected corruptions |
| `main()` muon case `:285-321` | log-log table `[(500,1e-3),(2000,4e-3)]` ≈ `NIEL = 2e-6·E` (`:280`); independent recomputation from hits `expected_ddd += l * 2e-6 * float(hit["kineticEnergy_MeV"]) * 100.0 / volume_mm3` (`:293`) compared at `rel=1e-3` (`:309`, comment `:308` notes hits carry pre-step energy while the scorer uses the step mean); `track_length_mm` equals the hits length sum at 1e-9 (`:307`); electrons with an out-of-domain table give `ddd_MeV_g == 0.0`, `track_length_mm == 0.0`, all length in `out_of_range_track_length_mm` (`:310-314`); statistics `ddd_mu-`/`ddd_total` equal the CSV sums (`:315-317`); `unit == "MeV/g"`, `n_events == 200` (`:318`); `0 < rel_error < 0.05` (`:321`) |
| neutron case `:323-328` | 0.1 mm Si, zero-deposit transport, constant table `[(0.01,2e-3),(20,2e-3)]`; `ddd == 2e-3 · 100.0 · events / (100·100)` within 0.5 % — i.e. NIEL × Φ with the analytic area/volume |
| ROOT-only case `:330-333` | no displacement CSV, `ddd_total > 0` in statistics |
| failure table `:336-365` | missing `[scoring.displacement]`, missing file, bad header, decreasing energies, negative NIEL, single row, `auto_create_default_scorers = false` — all must fail |
| particle-name tests `:367-384` | `he3` resolves to `He3` (length `0.01·200` within 2 %), unknown `protom` fails with "is not a Geant4 particle name" + "did you mean 'proton'" |
| Physical baseline | `scenarios/semiconductor/niel` tables are used by `scenarios/benchmarks/device_dose`; `docs/功能支持矩阵.md:140` reports DDD/fluence vs SR-NIEL +0.67 / −0.22 / +0.01 % for 10 MeV p / 100 MeV p / 14 MeV n; `scripts/test_semiconductor_device.py:112-115` compares `ddd_MeV_g_cm2` to the SR-NIEL table within 2 % and `phi_eq_per_unit_fluence` within 1e-3, `:136-137` 14 MeV neutrons within `0.01 + 3σ` |

Gaps: NIEL data itself is not benchmarked against displacement damage measurements (`docs/功能支持矩阵.md:162` "NIEL 数据本身与位移损伤效应未作基准"); no DDD under non-unit (biased) weight in any test; no ROOT ntuple; no DDD mesh/primitive cross-check; `GetCubicVolume()` for non-box solids unverified.

### 4.9 Line check — "if the volume were double-applied, would the current tests fail?"

**yes** — `scripts/test_displacement_damage.py:286` fixes `volume_mm3 = 100 * 100 * 1.0` (analytic, independent of the CSV) and `:293` recomputes the DDD from hits with that analytic volume, compared at `rel=1e-3` (`:309`); the neutron case `:328` hard-codes `100.0 · events / (100·100)`. A `1/V²` implementation would be off by 100×. **Weight:** not covered — every DDD test runs unbiased (weight = 1), so `w` vs `w²` is invisible, and `scripts/test_biasing_step_weight.py:46-47` enables `dose`/`fluence` but not `displacement`. Mass is unused by DDD.

---

## 5. Consumer index

| Quantity | Computed (value) | Written (CSV) | Written (ROOT) | Submitted to merged statistics | Read / merged / analysed |
| --- | --- | --- | --- | --- | --- |
| Dose | `src/Scoring/DoseScorer.cc:72,77-78` (`gyPerEdep`, `entry.sum/sumSq`) | `src/Scoring/DoseScorer.cc:95-109` (per worker/run) | ntuple `dose`: `src/Output/AnalysisOutput.cc:81-86` + `FillDose` `:204-215` | `DoseScorer.cc:80-81` → `HistoryStatistics::Submit` `HistoryStatistics.cc:111-136` → master CSV `OutputManager.cc:288-329` | `RunAction.cc:233-241` (master writes + `Take`); `src/Output/RunSummary.cc:73-79` (schema); `gui/g4usim_gui/output/dose_summary.py:46-105` (worker aggregation, mass only once); `gui/g4usim_gui/output/plot_data.py:104-105,172-183`; `scripts/g4usim_io.py:215-231` (ROOT); `scripts/extensions/dose_json_extension.py:11-31`; `scenarios/semiconductor/analyze_device.py:66`; `scenarios/shielding_coating/analyze.py` (TID, via `scorer_statistics`; line unverified) |
| Fluence | `src/Scoring/FluenceScorer.cc:83-84,103-104` | `:117-127` | ntuple `fluence`: `AnalysisOutput.cc:87-93` + `FillFluence` `:217` | `FluenceScorer.cc:106` → `HistoryStatistics.cc:111-136` → `OutputManager.cc:288-329` | `RunSummary.cc:97-104`; `gui/g4usim_gui/output/fluence_summary.py:44-109` (lengths summed, volume once; raises on mismatch `:81-86`); `scripts/extensions/fluence_json_extension.py:11-31`; `scripts/test_scoring_mesh.py:231-233` (native `cellFlux`) |
| LET | `src/Scoring/LETScorer.cc:80-85,112-113` | `:149-160` | ntuple `let`: `AnalysisOutput.cc:99-106` + `FillLET` `:242` | `LETScorer.cc:137-138` (ratio entries) → `HistoryStatistics.cc:66-75,111-136` → `OutputManager.cc:307-309` | `RunSummary.cc:84-91`; `gui/g4usim_gui/output/plot_data.py:151,412-418` (refuses per-event normalization for let); `scripts/g4usim_io.py:215-231`; `scripts/test_let_scoring.py:111-131` (ROOT vs CSV) |
| DDD | `src/Scoring/DisplacementScorer.cc:71-83` | `:106-118` | **none** (no ntuple; `AnalysisOutput.cc:61-106`) | `DisplacementScorer.cc:90-103` → `HistoryStatistics.cc:111-136` → `OutputManager.cc:288-329` | `RunSummary.cc:92-95`; `scripts/test_displacement_damage.py:124-126` (`statistics()` filters `scorer == "displacement"`); `scenarios/semiconductor/analyze_device.py:67-68` (`ddd_MeV_g_cm2`, `phi_eq_per_unit_fluence`); `scenarios/shielding_coating/analyze.py` (DDD, line unverified) |
| Shared merge path | — | per-worker CSVs are **never** merged by the backend | G4 ntuple merging when MT (`AnalysisOutput.cc:51` `SetNtupleMerging(true)`) | process-wide registry keyed `(runId, scorer, quantity, key)` | GUI re-merges worker CSVs for display (`dose_summary.py`, `fluence_summary.py`); `plot_data.py:104-105` reads `scorer_statistics*.csv` and `:395-429` normalizes **per completed event only** |

Note on "merged": the only backend merge is the **statistics registry** (`scorer_statistics[_rR].csv`); the per-touchable `dose/fluence/let/displacement_*_summary_tN*.csv` files stay per-worker and must be summed (energy/length/DDD) or re-divided (dose/fluence) by the consumer, keeping the mass/volume denominator single (`gui/g4usim_gui/output/dose_summary.py:3-5` "Physical-volume mass is a shared denominator across workers and must never be added"; `fluence_summary.py:3-4`).

---

## 6. Statistical estimator — one page summary

| Item | Location | Exact content |
| --- | --- | --- |
| Event moment accumulation | `src/Scoring/HistoryStatistics.cc:8-22` | `if (event != 0.0) { sum += event; sumSq += event²; ++entries; }`; always resets `event = 0; pending = false;` |
| Estimator | `src/Scoring/HistoryStatistics.cc:55-64` | `R = sqrt((sumSq/sum)/sum - 1/events)`, returns 0.0 when `events <= 0 \|\| sum == 0.0`, and 0.0 if the radicand is not positive |
| Ratio estimator | `src/Scoring/HistoryStatistics.cc:66-75` | `R² = (sumSq_A/A)/A + (sumSq_B/B)/B - 2·(cross/A)/B` |
| FOM | `src/Scoring/HistoryStatistics.cc:77-84` | `FOM = ((1/R)/sqrt(T))²`, 0 unless `R > 0` and `T > 0` |
| Availability flag | `src/Scoring/HistoryStatistics.cc:47-53` | `events < 2` → `insufficient_events`; ratio && denominator 0 → `undefined_ratio`; numerator 0 → `zero_total`; else `approximate` |
| Documented caveat | `include/Scoring/HistoryStatistics.hh:12-15` | "uncorrected event-moment approximation. It omits the N/(N-1) finite-sample variance correction; it is not `G4StatDouble::rms()`" … "N<2 or a zero total cannot establish a relative uncertainty. Numerical zero is retained for legacy consumers; UncertaintyStatus must accompany it." |
| Merge | `src/Scoring/HistoryStatistics.cc:111-136` | mutex-protected additive merge per `(runId, scorer, quantity, key)`; inconsistent `ratio`/`unit` throws |
| CSV emission | `src/Output/OutputManager.cc:288-329` | `value`, `mean_per_event`, `std_error = rel_error·\|value\|` (`:318`), `rel_error`, `fom_per_s`, `sum`, `sum_sq`, `estimator` (`total`/`ratio`), `uncertainty_estimator`, `uncertainty_status` |
| Thread model | `src/Actions/RunAction.cc:191-196,233-242` | worker/sequential: `EndRun` + `WriteAll` (per-worker CSVs, submits partials); master (or sequential): `WriteScorerStatisticsCsv` then `HistoryStatistics::Take(runID)` |
| Statistical vs physical | — | statistically: only the above; physically: nothing. `grep -rn "systematic" src include` → no match; exports carry `"physical_validation": "not_established"` (`scripts/extensions/dose_json_extension.py:23`, `fluence_json_extension.py:25`); `docs/功能支持矩阵.md:160` "仅为统计误差" |

---

## 7. Output-file summary (all four quantities)

| File | Produced when | Units in header | Schema tag (`src/Output/RunSummary.cc`) |
| --- | --- | --- | --- |
| `dose_volume_summary_tN[_rR].csv` | `dose=true`, CSV format, worker reaches write stage | `mass_kg`, `*_MeV`, `*_Gy`, `*_MeV2` | `dose_volume_csv_v2` (`:76-78`); legacy 8-col = `dose_volume_csv_v1` (`:74-75`) |
| `fluence_volume_summary_tN[_rR].csv` | `fluence=true`, CSV, worker write | `volume_mm3`, `*_mm`, `*_mm-2`, `*_mm2` | `fluence_volume_csv_v2` (`:100-103`); legacy = `fluence_volume_csv_v1` (`:98-99`) |
| `let_volume_summary_tN[_rR].csv` | `let=true`, CSV, worker write | `*_mm`, `*_MeV`, `*_MeV2_per_mm`, `*_keV_per_um`, `*_MeV_mm`, `*_MeV3_per_mm` | `let_volume_csv_v2` (`:87-90`); legacy 10-col = `let_volume_csv_v1` (`:85-86`) |
| `displacement_volume_summary_tN[_rR].csv` | `displacement=true` + ≥1 NIEL table, CSV, worker write | `volume_mm3`, `*_mm`, `ddd_MeV_g`, `ddd_sum_sq_MeV2_g2` | `displacement_volume_csv_v1` (`:93-95`) |
| `scorer_statistics[_rR].csv` | any run with submissions, `role_ != Worker`, any output format | `unit` column per row (`Gy`, `mm-2`, `keV/um`, `MeV/g`, `MeV`) | `scorer_statistics_csv_v2` (`:42-44`) |
| `g4usim[_rR].root` | format `root`/`both` | ntuple names carry units | `g4usim_root_v<N>` (`:45-46`) |

---

## 8. Test coverage matrix (assert vs gap)

| Script | Quantities exercised | Assertion style | Known gap |
| --- | --- | --- | --- |
| `scripts/test_dose_scoring.py` | Dose (masses, copies, failures) | analytic mass + independent `E·1.602e-13/m` recomputation from the same row (`:87`), analytic mother-minus-child mass | no physical benchmark; mass correctness relies on Geant4 `GetMass` |
| `scripts/test_fluence_scoring.py` | Fluence | geantino 12 mm/100 mm³; `phi == length/volume`; extension aggregation | implementation/self-consistency; no physical reference |
| `scripts/test_let_scoring.py` | LET | **analytic Bethe** stopping power of water, 2 % tolerance; `LET_d ≥ LET_t`; ROOT vs CSV | only 10/100 MeV protons in water; no nuclear stopping/heavy ions |
| `scripts/test_displacement_damage.py` | DDD | independent recomputation from hits (0.1 %), analytic NIEL·Φ for neutrons, out-of-domain, failure table | no biased-weight case; NIEL data itself unbenchmarked |
| `scripts/test_statistical_uncertainty.py` | Dose, Fluence, LET, Edep | independent hits recomputation of `sum/sum_sq/rel_error` (`:145-148`), 20-run spread vs reported R (`:187-214`), ROOT/CSV/statistics agreement (`:176-184`) | only event-moment statistics; no systematic term |
| `scripts/test_scoring_numeric.py` | all | non-finite input must latch failure (`status=failed`, `output_failure_status != none`, no statistics CSV `:135`); estimator/status strings (`:145-147`); C++ numeric-check model `checks=38` (`:159-162`) | numeric robustness only |
| `scripts/test_scoring_mesh.py` | Dose, Fluence (via native primitives) | native `doseDeposit` vs Dose (`:229-230`), native `cellFlux` vs Fluence (`:231-233`), mesh schema/rel_error | single box target; mesh is a different estimator |
| `scripts/test_biasing_step_weight.py` | Dose, Fluence (weights) | weighted totals vs native primitives at factor 0.1/1/10 (`:86-87`) | no DDD/LET; single material/process |
| `scripts/test_semiconductor_device.py` + `scenarios/benchmarks/device_dose` | Dose (TID), DDD | PSTAR/SR-NIEL external tables (2 %, 1 %), cut-independence | only EM option4, specific stack; SiO₂ dose unbenchmarked |
| `scripts/test_shielding_coating.py` | TID/DDD via `scorer_statistics` | source spectra/backscatter/pore geometry, and five evidence counterexamples (`:265-269` zero-deposition labelled `no_statistics_file_zero_deposition`) | no absolute physical reference for TID/DDD |

---

## 9. Answer table — "would current tests fail if a factor were double-applied?"

| Quantity | mass ×2 | volume ×2 | weight ×2 |
| --- | --- | --- | --- |
| Dose | **yes** — `test_dose_scoring.py:87` (2e-9), `test_statistical_uncertainty.py:161` (1e-9), `gui/.../dose_summary.py:87-90` (1e-8), plus analytic mass `:80` if the stored value changes | n/a (mass only) | **only in the biased run** — `test_biasing_step_weight.py:86,106`; unseen in every unbiased test |
| Fluence | n/a | **yes** — `test_fluence_scoring.py:61` (`phi == length/volume`, 2e-9) and `:56` (`volume == 100`); GUI `fluence_summary.py:81-86` (1e-8) | **only in the biased run** — `test_biasing_step_weight.py:87,106` |
| LET | **no** — mass does not appear in `LETScorer.cc` | **no** — volume does not appear; ratio is volume-free (`:112-113`) | **effectively no** — `w` is in both numerator and denominator, so `w²` changes only the weighting and the 2 % Bethe check would pass |
| DDD | n/a (mass unused) | **yes** — `test_displacement_damage.py:286,293` (analytic 100 mm³, 1e-3) and `:328` (analytic 100×100) | **no** — all DDD tests are unbiased (`weight = 1`), and `test_biasing_step_weight.py` does not enable `displacement` |

---

## 10. Discrepancies, doc drift and unverified items

| # | Item | Evidence | Status |
| --- | --- | --- | --- |
| 1 | `docs/输出数据契约.md:77` labels the Dose table `dose_volume_csv_v1` with 8 columns, but the code emits 11 columns and `RunSummary` tags it `dose_volume_csv_v2` | `src/Scoring/DoseScorer.cc:96-98` vs `docs/输出数据契约.md:77`; `src/Output/RunSummary.cc:74-78` | doc drift (documentation, not code) |
| 2 | `docs/输出数据契约.md:78` likewise documents the 8-column Fluence header as `fluence_volume_csv_v1`, while the code emits 11 columns (`fluence_volume_csv_v2`) | `src/Scoring/FluenceScorer.cc:118-120`; `RunSummary.cc:100-103` | doc drift |
| 3 | NIEL table sha256 is captured (`NielTable.cc:21`) but never emitted; the DDD CSV carries only the path | `DisplacementScorer.cc:113`; `grep -rn "GetInputSha256" src include` → only `IniReader` call sites | gap in reproducibility of the exact table bytes |
| 4 | LET has no `volume`/`mass` column and no geometry term, so LET rows cannot be audited against a volume defect | `LETScorer.cc:150-153` | by design; reviewer note |
| 5 | DDD has no ROOT ntuple, unlike Dose/Fluence/LET | `src/Output/AnalysisOutput.cc:61-106` | by design (`docs/功能支持矩阵.md:162` "ROOT 输出只有统计文件") |
| 6 | `HitRecord::LETcalc` is dead (setter never called) and both LET columns were dropped from hits v3 | `src/Hits/ParticleHit.cc:96,131`; `src/Output/OutputManager.cc:823-830`; `docs/输出数据契约.md:73` | historical remnant; harmless but should not be read as LET |
| 7 | `GetMass(true,false,...)` semantics for complex/parameterised geometries | `docs/输出数据契约.md:80`; only supported by targeted tests (`test_dose_scoring.py:190-335`, `test_geometry_a5.py:271-282`) | **unverified in general** — follow-up: run `python scripts/test_dose_scoring.py` and `python scripts/test_geometry_a5.py`, and read Geant4 source for `G4LogicalVolume::GetMass` (not shipped: `/d/ProgramFiles/Geant4` has only `include/`, `bin/`, `lib/`, `share/`) |
| 8 | `GetCubicVolume()` accuracy for non-box sensitive solids used by Fluence/DDD | `DoseContext.hh:30` | **unverified** — follow-up: `grep -rn "GetCubicVolume" src include` and a cylinder/tube scoring test (`scripts/test_scoring_mesh.py` exercises a cylinder mesh, not `GetCubicVolume`) |
| 9 | `LETstep` unit assumption (`ComputeElectronicDEDX` returns MeV/mm) rests on the repo comment and Geant4 internal units | `include/Scoring/LETScorer.hh:15`; `src/Hits/SensitiveDetector.cc:297` | **code-comment + unit-system inference**, not an explicit unit assertion in code; empirically supported by `test_let_scoring.py:149` matching Bethe in keV/µm within 2 % |
| 10 | GUI `plot_data.py` refuses per-event normalization for LET and never divides by primary count | `gui/g4usim_gui/output/plot_data.py:395-429` | consistent with §3.3; no defect |
| 11 | `scenarios/shielding_coating/analyze.py` and `gui/g4usim_gui/core/scenario_shielding.py:488` consume `scorer_statistics.csv` for TID/DDD | `docs/功能支持矩阵.md:143,204` | consumer exists; exact assertion lines **unverified** (not read in this pass) — follow-up: `grep -n "scorer_statistics\|ddd\|tid" scenarios/shielding_coating/analyze.py` |

### Re-verification commands (all read-only)

```bash
# mass / volume call sites
grep -rn "GetMass\|GetCubicVolume" src include
# LET columns and dead field
grep -rn "LETcalc\|LETstep" src include
# estimator and availability
grep -n "RelativeError\|RatioRelativeError\|UncertaintyStatus\|FigureOfMerit" src/Scoring/HistoryStatistics.cc
# no systematic-uncertainty code path
grep -rn "systematic" src include
# NIEL identity plumbing
grep -rn "GetInputSha256\|GetFile()" src include
# schema tags
grep -n "dose_volume_csv\|fluence_volume_csv\|let_volume_csv\|displacement_volume_csv\|scorer_statistics_csv" src/Output/RunSummary.cc
# table hashes
sha256sum scenarios/semiconductor/niel/*.csv
```
