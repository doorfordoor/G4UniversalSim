"""Static regression for the shielding / coating analysis library (GUI stage 2B).

No Geant4 backend and no Qt are needed: every case is a synthetic output directory
written under ``tempfile.mkdtemp()`` with the exact formats analyze.py parses
(scenario.json, run_summary.txt, run_metadata.json, scorer_statistics.csv, the merged
dose summary CSV and the phase-space files). The test checks that

  1. analyze() returns the dict the CLI serialises (same top-level keys, same nested
     structure) and that its values are the ones the synthetic numbers imply: TID/DDD
     per primary, per unit fluence, rate and per year, primary transmission and the
     per-particle spectra;
  2. the evidence section carries the run facts, the statistics label and the
     scenario/run event-count warning;
  3. a run that genuinely wrote no statistics is accepted and labelled
     ``no_statistics_file_zero_deposition`` (zero is a result, not missing evidence);
  4. five incomplete-evidence cases raise EvidenceError and leave neither a report nor
     spectra behind: statistics file listed in generated_files but missing, failed run,
     zero events, stale phase space and statistics of another run (mixed runs);
  5. main([output_dir]) keeps the CLI behaviour in-process: exit 0 plus
     shielding_report.json/spectra.csv and the historical stdout on success, exit 3
     plus the two historical stderr lines and no report on an evidence error, exit 2
     for wrong usage.

Run with ``python -B scripts/test_shielding_analysis.py``; the exit code is the result.
"""

from __future__ import annotations

import csv
import io
import json
import math
import shutil
import sys
import tempfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "scenarios" / "shielding_coating"
if str(PACK) not in sys.path:
    sys.path.insert(0, str(PACK))

import analyze as shielding_analysis  # noqa: E402

EvidenceError = shielding_analysis.EvidenceError

EVENTS = 100
PLANNED_EVENTS = 200
SOURCE_AREA_CM2 = 0.25
FLUX_PER_S = 2.0
SECONDS_PER_YEAR = 365.25 * 86400.0
TID_TOTAL, TID_REL_ERROR = 1.6e-9, 0.02
DDD_TOTAL, DDD_REL_ERROR = 3.2e-8, 0.05
ZERO_STATISTICS_LABEL = "no_statistics_file_zero_deposition"
STATISTICS_NAME = "scorer_statistics.csv"
WARNING = f"scenario.json planned {PLANNED_EVENTS} events, the run completed {EVENTS}"

STATISTICS_HEADER = (
    "runID,scorer,quantity,key,name,unit,estimator,n_events,entries,value,mean_per_event,"
    "std_error,rel_error,fom_per_s,run_wall_time_s,sum,sum_sq"
)
PHASE_SPACE_HEADER = (
    "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,"
    "time_ns,weight"
)
DOSE_SUMMARY_HEADER = (
    "runID,volume_path,volume_name,mass_kg,raw_edep_MeV,weighted_edep_MeV,raw_dose_Gy,"
    "weighted_dose_Gy,raw_edep_sum_sq_MeV2,weighted_edep_sum_sq_MeV2,n_events"
)

PHASE_SPACE_T0 = [
    ["0", "0", "1", "0", "proton", "2212", "0", "0", "1", "0", "0", "1", "100", "0", "1"],
    ["0", "1", "1", "0", "proton", "2212", "0", "0", "1", "0", "0", "1", "100", "0", "1"],
    ["0", "2", "1", "0", "proton", "2212", "0", "0", "1", "0", "0", "1", "100", "0", "1"],
    ["0", "3", "1", "0", "proton", "2212", "0", "0", "1", "0", "0", "1", "100", "0", "1"],
    ["0", "0", "2", "1", "e-", "11", "0", "0", "1", "0", "0", "1", "1", "0", "2"],
    ["0", "1", "3", "1", "proton", "2212", "0", "0", "1", "0", "0", "1", "0.5", "0", "1"],
    ["0", "0", "4", "1", "gamma", "22", "0", "0", "1", "0", "0", "-1", "2", "0", "1"],
]
PHASE_SPACE_T1 = [
    ["0", "4", "2", "1", "e-", "11", "0", "0", "1", "0", "0", "1", "2", "0", "1"],
]


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def close(got: float, expected: float, label: str) -> None:
    assert math.isclose(got, expected, rel_tol=1e-12, abs_tol=0.0), (label, got, expected)


def csv_text(header: str, rows: list[list[str]]) -> str:
    return "\n".join([header] + [",".join(row) for row in rows]) + "\n"


def summarize(*, status: str = "completed", completed: int = EVENTS) -> str:
    return "\n".join([
        "Run Summary",
        "===========",
        "",
        "[Values]",
        f"status = {status}",
        "summary_write_status = completed",
        "output_failure_status = none",
        "output_failure_message = not_applicable",
        "run_count = 1",
        f"planned_event_count = {completed}",
        f"actual_completed_event_count = {completed}",
        "[Runs]",
        "run_0_id = 0",
        f"run_0_planned_events = {completed}",
        f"run_0_completed_events = {completed}",
        "[GeneratedFiles]",
        "- run_metadata.json",
        f"- {STATISTICS_NAME}",
        "",
    ])


def base_metadata(output: Path) -> dict:
    return {
        "schema": "run_metadata_json_v1",
        "values": {
            "status": "completed",
            "summary_write_status": "completed",
            "output_failure_status": "none",
            "run_count": 1,
            "planned_event_count": EVENTS,
            "actual_completed_event_count": EVENTS,
        },
        "runs": [{"run_id": 0, "planned_events": EVENTS, "completed_events": EVENTS}],
        "generated_files": [
            {"path": str(output / STATISTICS_NAME), "schema": "scorer_statistics_csv_v1"},
            {"path": str(output / "dose_volume_summary_t0.csv"), "schema": "dose_volume_csv_v2"},
            {"path": str(output / "phase_space_t0.csv"), "schema": "phase_space_csv_v1"},
            {"path": str(output / "phase_space_t1.csv"), "schema": "phase_space_csv_v1"},
        ],
        "messages": [],
        "warnings": [],
    }


def statistics_text() -> str:
    return csv_text(STATISTICS_HEADER, [
        ["0", "dose", "weighted_dose", "/world_PV#0/Device_PV#0", "Device_PV", "Gy", "total",
         "100", "100", "1.6e-09", "1.6e-11", "3.2e-13", "0.02", "0", "100", "1.6e-07", "2.56e-16"],
        ["0", "displacement", "ddd_total", "/world_PV#0/Device_PV#0", "Device_PV", "MeV_g",
         "total", "100", "100", "3.2e-08", "3.2e-10", "1.6e-11", "0.05", "0", "100", "3.2e-06",
         "1.024e-15"],
        ["0", "dose", "weighted_dose", "/world_PV#0", "world_PV", "Gy", "total", "100", "100",
         "0.99", "0.0099", "1e-04", "0.01", "0", "100", "0.99", "0.01"],
    ])


def dose_summary_text() -> str:
    return csv_text(DOSE_SUMMARY_HEADER, [
        ["0", "/world_PV#0/Device_PV#0", "Device_PV", "0.05", "1.6e-09", "1.6e-09", "3.2e-09",
         "3.2e-09", "1.6e-17", "1.6e-17", "100"],
    ])


def build_base(work: Path) -> Path:
    case = work / "base"
    output = case / "output"
    output.mkdir(parents=True)
    scenario = {
        "mode": "transmission",
        "particle": "proton",
        "events": PLANNED_EVENTS,
        "source_area_cm2": SOURCE_AREA_CM2,
        "sampled_integral_flux_cm2_s": {"proton": FLUX_PER_S},
        "unsampled_flux_above_last_energy_cm2_s": {"proton": 0.5},
        "layers": [{"material": "B4C", "thickness_mm": 0.3}],
        "displacement": True,
    }
    write_lf(case / "scenario.json", json.dumps(scenario, indent=2) + "\n")
    write_lf(output / "run_summary.txt", summarize())
    write_lf(output / "run_metadata.json", json.dumps(base_metadata(output), indent=2) + "\n")
    write_lf(output / STATISTICS_NAME, statistics_text())
    write_lf(output / "dose_volume_summary_t0.csv", dose_summary_text())
    write_lf(output / "phase_space_t0.csv", csv_text(PHASE_SPACE_HEADER, PHASE_SPACE_T0))
    write_lf(output / "phase_space_t1.csv", csv_text(PHASE_SPACE_HEADER, PHASE_SPACE_T1))
    return output


def copy_case(work: Path, name: str) -> Path:
    target = work / name
    shutil.copytree(work / "base", target)
    return target / "output"


def edit_summary(output: Path, edits: dict[str, str]) -> None:
    path = output / "run_summary.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        for old, new in edits.items():
            if line.startswith(old + " = "):
                lines[index] = f"{old} = {new}"
    write_lf(path, "\n".join(lines) + "\n")


def load_metadata(output: Path) -> dict:
    return json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))


def save_metadata(output: Path, metadata: dict) -> None:
    write_lf(output / "run_metadata.json", json.dumps(metadata, indent=2) + "\n")


def run_main(arguments: list[str] | None) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = shielding_analysis.main(arguments)
    return status, stdout.getvalue(), stderr.getvalue()


def check_report(report: dict) -> None:
    assert set(report) == {
        "scenario", "events", "tid", "ddd", "particles", "primary_transmission", "evidence",
    }, sorted(report)
    assert report["events"] == EVENTS, report["events"]
    assert report["scenario"]["mode"] == "transmission"

    tid = report["tid"]
    assert set(tid) == {"total", "unit", "rel_error", "evidence", "per_primary",
                        "per_fluence_Gy_cm2", "rate_Gy_per_s", "per_year_Gy"}, sorted(tid)
    assert tid["unit"] == "Gy"
    assert tid["rel_error"] == TID_REL_ERROR
    assert tid["evidence"] == STATISTICS_NAME
    close(tid["total"], TID_TOTAL, "tid.total")
    close(tid["per_primary"], TID_TOTAL / EVENTS, "tid.per_primary")
    close(tid["per_fluence_Gy_cm2"], TID_TOTAL / EVENTS * SOURCE_AREA_CM2, "tid.per_fluence")
    close(tid["rate_Gy_per_s"], TID_TOTAL / EVENTS * SOURCE_AREA_CM2 * FLUX_PER_S, "tid.rate")
    close(tid["per_year_Gy"],
          TID_TOTAL / EVENTS * SOURCE_AREA_CM2 * FLUX_PER_S * SECONDS_PER_YEAR, "tid.per_year")

    ddd = report["ddd"]
    assert set(ddd) == {"total", "unit", "rel_error", "evidence", "per_primary",
                        "per_fluence_MeV_g_cm2", "rate_MeV_g_per_s", "per_year_MeV_g"}, sorted(ddd)
    assert ddd["unit"] == "MeV_g"
    assert ddd["rel_error"] == DDD_REL_ERROR
    assert ddd["evidence"] == STATISTICS_NAME
    close(ddd["total"], DDD_TOTAL, "ddd.total")
    close(ddd["per_primary"], DDD_TOTAL / EVENTS, "ddd.per_primary")
    close(ddd["per_fluence_MeV_g_cm2"], DDD_TOTAL / EVENTS * SOURCE_AREA_CM2, "ddd.per_fluence")
    close(ddd["rate_MeV_g_per_s"], DDD_TOTAL / EVENTS * SOURCE_AREA_CM2 * FLUX_PER_S, "ddd.rate")
    close(ddd["per_year_MeV_g"],
          DDD_TOTAL / EVENTS * SOURCE_AREA_CM2 * FLUX_PER_S * SECONDS_PER_YEAR, "ddd.per_year")

    particles = report["particles"]
    assert list(particles) == ["e-", "proton"], list(particles)
    assert set(particles["e-"]) == {"per_primary", "mean_energy_MeV"}
    close(particles["e-"]["per_primary"], 3 / EVENTS, "e-.per_primary")
    close(particles["e-"]["mean_energy_MeV"], 4.0 / 3.0, "e-.mean_energy")
    close(particles["proton"]["per_primary"], 5 / EVENTS, "proton.per_primary")
    close(particles["proton"]["mean_energy_MeV"], 80.1, "proton.mean_energy")
    close(report["primary_transmission"], 4 / EVENTS, "primary_transmission")

    evidence = report["evidence"]
    assert set(evidence) == {"run_summary", "run_status", "run_count", "planned_events",
                             "completed_events", "run_metadata_schema", "scorer_statistics",
                             "phase_space_files", "niel_tables", "warnings"}, sorted(evidence)
    assert evidence["run_summary"] == "run_summary.txt"
    assert evidence["run_status"] == "completed"
    assert evidence["run_count"] == 1
    assert evidence["planned_events"] == PLANNED_EVENTS
    assert evidence["completed_events"] == EVENTS
    assert evidence["run_metadata_schema"] == "run_metadata_json_v1"
    assert evidence["scorer_statistics"] == STATISTICS_NAME
    assert evidence["phase_space_files"] == ["phase_space_t0.csv", "phase_space_t1.csv"]
    assert evidence["niel_tables"] == []   # no NIEL table in this fixture
    assert evidence["warnings"] == [WARNING], evidence["warnings"]


@contextmanager
def capture_out_err():
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        yield stdout, stderr


def check_zero_deposition(output: Path) -> None:
    with capture_out_err() as (stdout, stderr):
        report = shielding_analysis.analyze(output)
    assert stdout.getvalue() == "", stdout.getvalue()
    assert stderr.getvalue() == "", stderr.getvalue()
    assert report["tid"]["evidence"] == ZERO_STATISTICS_LABEL, report["tid"]
    assert report["tid"]["total"] == 0.0
    assert report["tid"]["per_primary"] == 0.0
    assert report["tid"]["per_fluence_Gy_cm2"] == 0.0
    assert report["tid"]["rate_Gy_per_s"] == 0.0
    assert report["tid"]["per_year_Gy"] == 0.0
    assert report["tid"]["rel_error"] is None
    assert report["ddd"]["evidence"] == ZERO_STATISTICS_LABEL
    assert report["ddd"]["total"] == 0.0
    assert report["evidence"]["scorer_statistics"] == ZERO_STATISTICS_LABEL
    assert report["evidence"]["warnings"] == [WARNING], report["evidence"]["warnings"]
    close(report["particles"]["proton"]["per_primary"], 5 / EVENTS, "zero.proton.per_primary")
    close(report["primary_transmission"], 4 / EVENTS, "zero.primary_transmission")


def expect_evidence_error(output: Path, fragment: str) -> None:
    raised = False
    message = ""
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            shielding_analysis.analyze(output)
        except EvidenceError as error:
            raised = True
            message = str(error)
    assert raised, f"analyze() accepted incomplete evidence in {output}"
    assert stdout.getvalue() == "", stdout.getvalue()
    assert stderr.getvalue() == "", stderr.getvalue()
    assert fragment in message, (fragment, message)
    assert not (output / "shielding_report.json").exists(), output
    assert not (output / "spectra.csv").exists(), output


def run() -> None:
    work = Path(tempfile.mkdtemp(prefix="g4usim_shield_analysis_"))
    try:
        base_output = build_base(work)

        with capture_out_err() as (analyze_stdout, analyze_stderr):
            report = shielding_analysis.analyze(str(base_output))
        assert analyze_stdout.getvalue() == "", analyze_stdout.getvalue()
        assert analyze_stderr.getvalue() == "", analyze_stderr.getvalue()
        check_report(report)
        assert issubclass(EvidenceError, Exception)
        assert not (base_output / "shielding_report.json").exists(), "analyze() wrote a report"
        assert not (base_output / "spectra.csv").exists(), "analyze() wrote spectra"

        cli_output = copy_case(work, "cli_success")
        expected_output = Path(cli_output).resolve()
        status, stdout, stderr = run_main([str(cli_output)])
        assert status == 0, (status, stderr)
        assert stderr == "", stderr
        assert (cli_output / "shielding_report.json").is_file()
        assert (cli_output / "spectra.csv").is_file()
        written = json.loads((cli_output / "shielding_report.json").read_text(encoding="utf-8"))
        assert written == report, "the CLI report differs from analyze()"

        expected_stdout = "\n".join([
            "transmission run, 100 primaries (proton), layers B4C 300 um",
            "  TID: 1.6e-11 Gy per primary, 4e-12 Gy cm2 per unit fluence "
            "(rel. error 0.02, evidence scorer_statistics.csv), 0.0002525 Gy/year at normal incidence",
            "  DDD: 3.2e-10 MeV/g per primary, 8e-11 MeV/g cm2 per unit fluence "
            "(rel. error 0.05, evidence scorer_statistics.csv), 0.005049 MeV/g/year at normal incidence",
            "  primaries crossing the stack: 0.04",
            "  e-: 0.03 per primary, mean 1.333 MeV",
            "  proton: 0.05 per primary, mean 80.1 MeV",
            f"  warning: {WARNING}",
            f"report: {expected_output / 'shielding_report.json'}, "
            f"spectra: {expected_output / 'spectra.csv'}",
            "",
        ])
        assert stdout == expected_stdout, stdout

        with (cli_output / "spectra.csv").open(newline="", encoding="utf-8") as handle:
            spectra = list(csv.reader(handle))
        assert spectra[0] == ["particle", "e_low_MeV", "e_high_MeV", "count_per_primary"]
        assert spectra[1:] == [
            ["e-", "1", "1.58489", "0.02"],
            ["e-", "1.58489", "2.51189", "0.01"],
            ["proton", "0.398107", "0.630957", "0.01"],
            ["proton", "100", "158.489", "0.04"],
        ], spectra[1:]

        zero_output = copy_case(work, "zero_deposition")
        (zero_output / STATISTICS_NAME).unlink()
        metadata = load_metadata(zero_output)
        metadata["generated_files"] = [entry for entry in metadata["generated_files"]
                                       if Path(entry["path"]).name != STATISTICS_NAME]
        save_metadata(zero_output, metadata)
        check_zero_deposition(zero_output)
        status, stdout, stderr = run_main([str(zero_output)])
        assert status == 0, (status, stderr)
        assert f"  note: {ZERO_STATISTICS_LABEL}; a zero here means the run wrote no statistics" in stdout, stdout

        missing = copy_case(work, "missing_statistics")
        (missing / STATISTICS_NAME).unlink()
        expect_evidence_error(missing, "was listed in run_metadata.json generated_files but is missing")

        failed = copy_case(work, "failed_run")
        edit_summary(failed, {"status": "failed"})
        expect_evidence_error(failed, "only a completed run can be analysed")

        empty = copy_case(work, "zero_events")
        edit_summary(empty, {"run_0_completed_events": "0"})
        metadata = load_metadata(empty)
        metadata["runs"][0]["planned_events"] = 0
        metadata["runs"][0]["completed_events"] = 0
        save_metadata(empty, metadata)
        expect_evidence_error(empty, "no rate can be derived from an empty run")

        stale = copy_case(work, "stale_phase_space")
        edit_summary(stale, {"run_0_completed_events": "4"})
        metadata = load_metadata(stale)
        metadata["runs"][0]["planned_events"] = 4
        metadata["runs"][0]["completed_events"] = 4
        save_metadata(stale, metadata)
        expect_evidence_error(stale, "the files look stale")

        mixed = copy_case(work, "mixed_runs")
        (mixed / STATISTICS_NAME).unlink()
        metadata = load_metadata(mixed)
        metadata["generated_files"] = [entry for entry in metadata["generated_files"]
                                       if Path(entry["path"]).name != STATISTICS_NAME]
        save_metadata(mixed, metadata)
        write_lf(mixed / "scorer_statistics_r1.csv", STATISTICS_HEADER + "\n")
        expect_evidence_error(mixed, "the output directory mixes runs")

        status, stdout, stderr = run_main([str(missing)])
        assert status == 3, (status, stderr)
        assert stdout == "", stdout
        lines = stderr.splitlines()
        assert len(lines) == 2, stderr
        assert lines[0].startswith("analyze.py: evidence error: "), lines[0]
        assert "was listed in run_metadata.json generated_files but is missing" in lines[0], lines[0]
        assert lines[1] == ("analyze.py: no report was written; fix the run or its files instead of "
                            "reading a zero from missing evidence"), lines[1]
        assert not (missing / "shielding_report.json").exists()
        assert not (missing / "spectra.csv").exists()

        status, stdout, stderr = run_main([])
        assert status == 2, status
        assert stdout == shielding_analysis.__doc__ + "\n", stdout
        assert stderr == "", stderr
        status, _stdout, _stderr = run_main(None)
        assert status == 2, status
        status, _stdout, _stderr = run_main(["too", "many"])
        assert status == 2, status
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    run()
