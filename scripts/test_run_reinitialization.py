"""R30: real master/worker run IDs stay aligned; post-run restarts fail fast."""
from __future__ import annotations

import contextlib
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "out/build-effective/Release/G4UniversalSim.exe"))
RESTARTS = ("/run/initialize", "/run/reinitializeGeometry", "/run/physicsModified", "/run/geometryModified")


def read_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def first_run_retained(output: Path, facts: dict[str, str]) -> None:
    assert facts["run_0_id"] == "0" and facts["run_0_completed_events"] == "4", facts
    statistics = output / "scorer_statistics.csv"
    assert statistics.is_file(), output
    values = read_rows(statistics)
    assert values and all(row["runID"] == "0" and row["n_events"] == "4" for row in values), values
    assert any(float(row["value"]) > 0 for row in values), values
    files = [path for path in output.glob("event_edep_t*.csv") if "_r" not in path.stem]
    events = [row for path in files for row in read_rows(path)]
    assert len(events) == 4 and all(row["runID"] == "0" for row in events), events
    assert "scorer_statistics.csv" in "\n".join(facts.values()), facts


def run_case(work: Path, threads: int, *, bias=False, interactive=False, rejected=None, before_first=False):
    label = f"t{threads}-bias{bias}-csh{interactive}-" + (rejected.rsplit("/", 1)[1] if rejected else "early" if before_first else "ordinary")
    folder = work / label
    folder.mkdir()
    geometry = folder / "geometry.ini"
    geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n"
                        "[volume.Target]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\n"
                        "material=G4_WATER\nsensitive=true\nbias=true\n", encoding="utf-8")
    config = folder / "main.ini"
    configuration = (f"[run]\nthreads={threads}\nseed=184\n[output]\nformat=csv\n"
                     f"[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n"
                     "[physics]\nreference=FTFP_BERT\n[scoring]\nenabled=true\nhits=true\n"
                     "event_edep=true\nedep=true\nauto_create_default_scorers=true\n"
                     "[source]\nparticle=e-\nenergy=1 MeV\nposition_type=point\nposition=0,0,0 mm\ndirection=+z\n")
    if bias:
        configuration += "[biasing]\nenabled=true\n[biasing.xs.e-.eIoni]\nfactor=2\nvolumes=Target\n"
    config.write_text(configuration, encoding="utf-8")
    sentinel = folder / "must_not_execute.json"
    commands = "/run/initialize\n/run/beamOn 4\n"
    if rejected:
        commands += rejected + f"\n/AIHL/geometry/exportMesh {sentinel.as_posix()}\n/run/beamOn 9\n"
    else:
        if before_first:
            commands = "/run/physicsModified\n/run/initialize\n/run/physicsModified\n/run/initialize\n/run/beamOn 4\n"
        commands += "/run/beamOn 5\n"
    output = folder / "output"
    arguments = [str(EXE), "--config", str(config), "--output", str(output)]
    macro = folder / "run.mac"
    macro.write_text(commands, encoding="utf-8")
    if interactive:
        arguments += ["--ui", "--ui-session", "csh"]
    else:
        arguments += ["--macro", str(macro)]
    environment = os.environ.copy()
    environment.pop("G4USIM_TEST_OUTPUT_FAULT", None)
    completed = subprocess.run(arguments, cwd=folder, env=environment,
                               input=commands + "exit\n" if interactive else None,
                               text=True, capture_output=True, errors="replace", timeout=120)
    log = completed.stdout + completed.stderr
    (folder / "run.log").write_text(log, encoding="utf-8")
    summary = output / "run_summary.txt"
    assert summary.is_file(), (label, completed.returncode, log[-3000:])
    facts = dict(line.split(" = ", 1) for line in summary.read_text(encoding="utf-8").splitlines() if " = " in line)
    first_run_retained(output, facts)
    progress = [json.loads(line.split("[G4USimProgress] ", 1)[1]) for line in log.splitlines() if "[G4USimProgress] " in line]
    if rejected:
        assert completed.returncode == 1 and facts["status"] == "failed", (label, facts, log[-3000:])
        assert facts["run_count"] == "1" and "run_1_id" not in facts, facts
        assert not sentinel.exists(), (label, "later sentinel was executed")
        assert not (output / "scorer_statistics_r1.csv").exists(), label
        assert "start a new process" in log, log[-3000:]
        if interactive:
            assert facts["interactive_command_failure_kind"] == "run_lifecycle", facts
            assert "start a new process" in facts["interactive_command_failure_message"], facts
        else:
            assert facts["macro_execution_status"] == "failed" and facts["macro_failure_phase"] == "execution", facts
            assert facts["macro_failure_command"] == rejected and facts["macro_failure_line"] == "3", facts
            assert Path(facts["macro_failure_file"].replace("\\\\", "\\")).resolve() == macro.resolve(), facts
    else:
        assert completed.returncode == 0 and facts["status"] == "completed", (label, facts, log[-3000:])
        assert facts["run_count"] == "2" and facts["run_1_id"] == "1", facts
        assert facts["run_1_completed_events"] == "5" and facts["actual_completed_event_count"] == "9", facts
        assert [row["run_id"] for row in progress if row["phase"] == "begin"] == [0, 1], progress
        assert [row["run_id"] for row in progress if row["phase"] == "end"] == [0, 1], progress
        second_statistics = output / "scorer_statistics_r1.csv"
        assert second_statistics.is_file(), label
        stats = read_rows(second_statistics)
        assert stats and all(row["runID"] == "1" and row["n_events"] == "5" for row in stats), stats
        second_events = [row for path in output.glob("event_edep_t*_r1.csv") for row in read_rows(path)]
        assert len(second_events) == 5 and all(row["runID"] == "1" for row in second_events), second_events
        if bias:
            evidence = [json.loads(line.split("[G4USimBiasing] ", 1)[1]) for line in log.splitlines() if "[G4USimBiasing] " in line]
            assert {(row["run_id"], row["thread_id"]) for row in evidence} == {(run, worker) for run in (0, 1) for worker in range(threads)}, evidence
            assert len(evidence) == 2 * threads and all(row["tls_verified"] and row["end_run_completed"] and not row["failed"] for row in evidence), evidence
            assert facts["biasing_worker_coverage_complete"] == "true", facts
    print(f"{label}: run identity/restart contract checked")


def main():
    assert EXE.is_file(), EXE
    with contextlib.ExitStack() as stack:
        work = Path(os.environ["G4USIM_TEST_WORK"]).resolve() if os.environ.get("G4USIM_TEST_WORK") else Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="g4usim-run-reinitialize-")))
        work.mkdir(parents=True, exist_ok=True)
        for threads in (1, 2):
            run_case(work, threads)
            run_case(work, threads, bias=True)
            run_case(work, threads, before_first=True)
            run_case(work, threads, interactive=True)
            run_case(work, threads, interactive=True, before_first=True)
            for command in RESTARTS:
                run_case(work, threads, rejected=command)
                run_case(work, threads, interactive=True, rejected=command)
    print("run reinitialization: PASS")


if __name__ == "__main__":
    main()
