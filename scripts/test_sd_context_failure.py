"""R23: caught SD callback faults preserve the previous run and fail safely."""
from __future__ import annotations

import csv
import math
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "out/build-effective/Release/G4UniversalSim.exe"))


def run_case(work: Path, threads: int, fault: str | None) -> None:
    name = f"{threads}-{fault or 'control'}"
    folder = work / name
    folder.mkdir()
    geometry = folder / "geometry.ini"
    geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n"
                        "[volume.Target]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\n"
                        "material=G4_WATER\nsensitive=true\n", encoding="utf-8")
    config = folder / "main.ini"
    config.write_text(f"[run]\nthreads={threads}\nseed=42\n[output]\nformat=csv\n"
                      f"[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n"
                      "[physics]\nreference=FTFP_BERT\n[scoring]\nenabled=true\nhits=true\n"
                      "event_edep=true\nedep=true\ndose=true\nauto_create_default_scorers=true\n"
                      "[source]\nparticle=proton\nenergy=2 MeV\nposition_type=point\nposition=0,0,0 mm\ndirection=+z\n", encoding="utf-8")
    macro = folder / "run.mac"
    macro.write_text("/run/initialize\n/run/beamOn 40\n/run/beamOn 40\n/run/beamOn 10\n", encoding="utf-8")
    environment = os.environ.copy()
    environment.pop("G4USIM_TEST_OUTPUT_FAULT", None)
    if fault:
        environment["G4USIM_TEST_OUTPUT_FAULT"] = fault
    output = folder / "output"
    completed = subprocess.run([str(EXE), "--config", str(config), "--macro", str(macro), "--output", str(output)],
                               cwd=folder, env=environment, capture_output=True, text=True, errors="replace", timeout=180)
    log = completed.stdout + completed.stderr
    (folder / "run.log").write_text(log, encoding="utf-8")
    summary = output / "run_summary.txt"
    assert summary.is_file(), (name, completed.returncode, log[-3000:])
    facts = dict(line.split(" = ", 1) for line in summary.read_text(encoding="utf-8").splitlines() if " = " in line)
    assert facts["run_0_completed_events"] == "40", facts
    first_statistics = output / "scorer_statistics.csv"
    assert first_statistics.is_file(), (name, log[-3000:])
    with first_statistics.open(newline="", encoding="utf-8") as stream:
        statistics = list(csv.DictReader(stream))
    assert statistics and all(int(row["n_events"]) == 40 for row in statistics), statistics
    for row in statistics:
        assert math.isfinite(float(row["value"])), row
    first_dose = []
    for path in output.glob("dose_volume_summary_t*.csv"):
        if "_r" in path.stem:
            continue
        with path.open(newline="", encoding="utf-8") as stream:
            first_dose.extend(csv.DictReader(stream))
    assert first_dose and all(int(row["runID"]) == 0 for row in first_dose), first_dose
    assert sum(float(row["raw_edep_MeV"]) for row in first_dose) > 0, first_dose
    if fault:
        assert completed.returncode == 1, (name, completed.returncode, log[-3000:])
        expected_stage = "scoring_sd_initialize" if "initialize" in fault else "scoring_transport_context"
        assert facts["status"] == "failed" and facts["output_failure_stage"] == expected_stage, facts
        assert facts["output_failure_run_id"] == "1", facts
        failure_thread = int(facts["output_failure_thread_id"])
        assert 0 <= failure_thread < threads, facts
        if threads == 1:
            assert failure_thread == 0, facts
        print(f"{name}: actual failure worker={failure_thread}")
        assert facts["run_count"] == "2" and "run_2_id" not in facts, facts
        expected_message = "unknown exception" if "unknown" in fault else "test-only SD"
        assert expected_message in facts["output_failure_message"], facts
        assert not (output / "scorer_statistics_r1.csv").exists(), name
        assert not (output / "scorer_statistics_r2.csv").exists(), name
    else:
        assert completed.returncode == 0 and facts["status"] == "completed", (facts, log[-3000:])
        assert facts["actual_completed_event_count"] == "90" and facts["run_count"] == "3", facts
    print(f"{name}: previous run retained; callback failure contract checked")


def main() -> None:
    assert EXE.is_file(), EXE
    with tempfile.TemporaryDirectory(prefix="g4usim-sd-context-") as temp:
        work = Path(temp)
        for threads in (1, 2):
            run_case(work, threads, None)
            for fault in ("sd_context_t0", "sd_context_unknown_t0", "sd_initialize_t0", "sd_initialize_unknown_t0"):
                run_case(work, threads, fault if threads == 1 else fault.removesuffix("_t0") + "_any_worker")
    print("SD callback context/initialization failure: PASS")


if __name__ == "__main__":
    main()
