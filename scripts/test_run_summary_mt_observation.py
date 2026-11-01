"""Worker scheduling evidence must never hide primary or cross-run defects."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import test_run_summary as summary

EXPECTED = ((0, "e-", 1.0), (1, "proton", 3.0))


def fixture(directory, *, split=False, bad_energy=False, bad_position=False, missing_event=False):
    directory.mkdir(parents=True, exist_ok=True)
    generated, schemas = [], []
    values = {"status": "completed", "summary_write_status": "completed", "output_failure_status": "none",
              "macro_execution_status": "completed", "actual_threads": "2", "run_count": "2",
              "planned_event_count": "16", "actual_completed_event_count": "16"}
    for run_id, particle, energy in EXPECTED:
        suffix = "" if run_id == 0 else f"_r{run_id}"
        values.update({f"run_{run_id}_id": str(run_id), f"run_{run_id}_planned_events": "8",
                       f"run_{run_id}_completed_events": "8"})
        for worker in ((0, 1) if split else (0,)):
            events = list(range(worker * 4, worker * 4 + 4)) if split else list(range(8))
            if missing_event and worker == 0:
                events.remove(0)
            for kind, schema in (("hits", "hits_csv_v3"), ("event_edep", "event_edep_csv_v3")):
                path = directory / f"{kind}_t{worker}{suffix}.csv"
                generated.append(str(path.resolve()))
                schemas.append((str(path.resolve()), schema))
                with path.open("w", newline="", encoding="utf-8") as stream:
                    fields = (["runID", "eventID", "trackID", "parentID", "particle", "kineticEnergy_MeV",
                               "x0_mm", "y0_mm", "z0_mm"] if kind == "hits" else ["runID", "eventID"])
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    for event in events:
                        row = {"runID": run_id, "eventID": event}
                        if kind == "hits":
                            row.update(trackID=1, parentID=0, particle=particle,
                                       kineticEnergy_MeV=99 if bad_energy else energy,
                                       x0_mm=1 if bad_position else 0, y0_mm=0, z0_mm=-9)
                        writer.writerow(row)
    lines = ["[Values]", *(f"{key} = {value}" for key, value in values.items()), "[GeneratedFiles]",
             *("- " + name for name in generated), "[GeneratedFileSchemas]"]
    for index, (path, schema) in enumerate(schemas):
        lines += [f"file_{index}_path = {path}", f"file_{index}_schema = {schema}"]
    (directory / "run_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def rejected(action):
    try:
        action()
    except AssertionError:
        return
    assert False, "Invalid event evidence was accepted"


def main():
    with tempfile.TemporaryDirectory(prefix="g4-mt-observation-test-") as temporary:
        root = Path(temporary)
        fixture(root / "sparse")
        sparse = summary.observe_mt_primaries(root / "sparse", EXPECTED)
        assert not sparse["both_workers_each_run"]
        assert all(run["worker_events"] == {"0": list(range(8))} for run in sparse["runs"].values())
        fixture(root / "split", split=True)
        assert summary.observe_mt_primaries(root / "split", EXPECTED)["both_workers_each_run"]
        for name, options in (("energy", {"bad_energy": True}), ("position", {"bad_position": True}),
                              ("events", {"missing_event": True})):
            fixture(root / name, **options)
            rejected(lambda path=root / name: summary.observe_mt_primaries(path, EXPECTED))
        duplicate = root / "duplicate"
        fixture(duplicate, split=True)
        path = duplicate / "hits_t1.csv"
        with path.open("a", encoding="utf-8") as stream:
            stream.write("0,0,1,0,e-,1,0,0,-9\n")
        rejected(lambda: summary.observe_mt_primaries(duplicate, EXPECTED))
        missing = root / "missing-hits"
        fixture(missing, split=True)
        (missing / "hits_t1.csv").unlink()
        rejected(lambda: summary.observe_mt_primaries(missing, EXPECTED))

        macro = root / "input.mac"
        macro.write_text("/run/beamOn 8\n", encoding="utf-8")
        calls = []
        def simulated_run(executable, argv, expected=0):
            output = Path(argv[argv.index("--output") + 1])
            calls.append(output)
            fixture(output, split=len(calls) == 2)
            return "fixture process output"
        with patch.object(summary, "run", simulated_run):
            observation = summary.run_mt_primary_observation(Path("fixture.exe"), macro, root / "bounded", EXPECTED)
        assert observation["both_workers_each_run"] and len(calls) == 2
        attempts = json.loads((root / "bounded/attempts.json").read_text())
        assert len(attempts) == 2 and all(a["status"] == "valid_observation" for a in attempts)
        assert not attempts[0]["observation"]["both_workers_each_run"]
        assert all((Path(a["output"]) / "backend.log").is_file() for a in attempts)

        calls.clear()
        def only_sparse(executable, argv, expected=0):
            output = Path(argv[argv.index("--output") + 1])
            calls.append(output)
            fixture(output)
            return "sparse process output"
        with patch.object(summary, "run", only_sparse):
            rejected(lambda: summary.run_mt_primary_observation(Path("fixture.exe"), macro,
                                                                root / "exhausted", EXPECTED, max_attempts=3))
        assert len(calls) == 3
        assert len(json.loads((root / "exhausted/attempts.json").read_text())) == 3

        calls.clear()
        def broken_then_good(executable, argv, expected=0):
            output = Path(argv[argv.index("--output") + 1])
            calls.append(output)
            fixture(output, split=True, bad_energy=len(calls) == 1)
            return "wrong primary energy"
        with patch.object(summary, "run", broken_then_good):
            rejected(lambda: summary.run_mt_primary_observation(Path("fixture.exe"), macro,
                                                                root / "bad-immediate", EXPECTED))
        assert len(calls) == 1, "A semantic failure was retried"
        assert json.loads((root / "bad-immediate/attempts.json").read_text())[0]["status"] == "failed"
    print("MT primary observation: complete events, real worker coverage, bounded exhaustion and immediate semantic failure checked")


if __name__ == "__main__":
    main()
