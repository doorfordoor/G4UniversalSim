"""End-to-end regression for the headless shielding scenario driver (roadmap 2B-2).

``gui/g4usim_gui/core/scenario_shielding.py`` is what the scenario page calls: it
validates the form values with the configuration schema, writes the scenario through
the shared model, runs the real backend and turns the analysis report into table rows.
This test drives that module without Qt and checks the evidence labels survive.

Backend layer: needs the real executable (200 events, two worker threads).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from g4usim_gui.core import scenario_shielding  # noqa: E402

EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def main() -> int:
    assert EXE.is_file(), f"backend executable not found: {EXE}"

    # 1. The form definition: defaults are complete, advanced fields are separated.
    values = scenario_shielding.default_values()
    assert set(values) == {field.key for field in scenario_shielding.FIELDS}
    assert len(scenario_shielding.visible_fields()) == 7
    assert len(scenario_shielding.visible_fields(advanced=True)) == 8
    assert scenario_shielding.field_spec("events").kind == "int"
    try:
        scenario_shielding.field_spec("no_such_field")
        raise AssertionError("an unknown field must be rejected")
    except scenario_shielding.ScenarioRunError as exc:
        assert "Unknown scenario field 'no_such_field'" in str(exc)

    # 2. Validation: the defaults pass, and every failure is reported with its reason.
    assert scenario_shielding.validate_values(values) == []
    assert scenario_shielding.validate_values({"events": "0"}) == ["Events must be at least 1"]
    assert scenario_shielding.validate_values({"threads": "0"}) == ["Threads must be at least 1"]
    assert scenario_shielding.validate_values({"seed": "twelve"}) == [
        "Random seed must be an integer, got 'twelve'"]
    assert scenario_shielding.validate_values({"pore_fraction": "1.5"}) == [
        "Pore fraction must be less than 1"]
    assert scenario_shielding.validate_values({"energy": "1e308 GeV"}) == [
        "[source]/energy must be a finite energy (units eV, keV, MeV, GeV), got '1e308 GeV'"]
    assert scenario_shielding.validate_values({"layers": "B4C:0um"}) == [
        "length must be > 0: '0um'"]
    schema_problems = scenario_shielding.validate_values({"seed": "99999999999"})
    assert schema_problems == ["[run]/seed = 99999999999 is out of range for a 32-bit integer"]
    assert scenario_shielding.validate_values({"mode": "sideways"}) == [
        "--mode must be one of ['transmission', 'albedo'], got 'sideways'"]

    # 3. Generation writes the same files the CLI writes.
    work = ROOT / "out" / "scenario_driver"
    scenario_shielding.cleanup_directory(work)
    generated = scenario_shielding.generate(values, work / "default")
    assert generated.directory.is_dir()
    assert set(generated.files) == {"materials.ini", "geometry.ini", "main.ini", "run.mac",
                                    "scenario.json", "spectrum_proton.csv"}
    assert generated.main_ini_path.is_file() and generated.main_ini.startswith("#")
    assert "[run]\nthreads = 4" in generated.main_ini
    assert generated.meta["mode"] == "transmission" and generated.meta["pores"] == 0
    assert generated.output_directory == generated.directory / "output"

    # 4. One real run: 200 events, two worker threads, mono-energetic source.
    values = dict(values)
    values.update({"events": "200", "threads": "2", "energy": "100 MeV"})
    outcome = scenario_shielding.run_scenario(values, work / "run", executable=EXE, timeout=900)
    assert outcome.ok, outcome.error or "the run did not produce a report"
    assert outcome.exit_code == 0
    assert outcome.summary.get("status") == "completed", outcome.summary.get("status")
    assert outcome.summary.get("run_0_completed_events") == "200"
    assert outcome.duration_seconds > 0
    log = outcome.log_path.read_text(encoding="utf-8")
    assert "--config main.ini" in log.splitlines()[0]
    assert "G4UniversalSim" in log
    report = outcome.report or {}
    assert report["evidence"]["run_status"] == "completed"
    assert report["evidence"]["completed_events"] == 200
    assert report["tid"]["total"] > 0.0
    assert report["tid"]["evidence"] == "scorer_statistics.csv"
    # No NIEL table was given, so the analysis must not invent a DDD value.
    assert report["ddd"] is None
    assert outcome.warnings == []

    # 5. The result table exposes TID/DDD with the evidence label, no Qt needed.
    rows = scenario_shielding.result_rows(report)
    assert [row["group"] for row in rows].count("TID") == 2
    assert [row["group"] for row in rows].count("DDD") == 0
    assert all(row["evidence"] == "scorer_statistics.csv"
               for row in rows if row["group"] == "TID")
    assert [row["evidence"] for row in rows if row["group"] == "Transmission"] == ["phase_space"]
    assert any(row["label"] == "Per primary" for row in rows)
    assert all(row["value"] != "" for row in rows)
    lines = scenario_shielding.evidence_summary(report)
    assert "Run status: completed" in lines[0]
    assert any(line.startswith("Statistics evidence: scorer_statistics.csv") for line in lines)

    # 6. Missing evidence must surface as an error, not as a zero result.
    statistics = outcome.output_directory / "scorer_statistics.csv"
    assert statistics.is_file()
    statistics.unlink()
    try:
        scenario_shielding.analyse(outcome.generated)
        raise AssertionError("removing the statistics file must not yield a report")
    except scenario_shielding.ScenarioRunError as exc:
        assert "was listed in run_metadata.json generated_files but is missing" in str(exc)

    # 7. Bad inputs on the run path fail with explicit messages, not a silent pack.
    try:
        scenario_shielding.run_scenario(values, work / "missing", executable=work / "no-backend.exe")
        raise AssertionError("a missing executable must be rejected")
    except scenario_shielding.ScenarioRunError as exc:
        assert "does not exist" in str(exc)
    try:
        scenario_shielding.run_scenario(dict(values, events="0"), work / "invalid", executable=EXE)
        raise AssertionError("an invalid form must be rejected before running")
    except scenario_shielding.ScenarioRunError as exc:
        assert str(exc) == "Events must be at least 1"

    scenario_shielding.cleanup_directory(work)
    print("test_scenario_shielding_core: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
