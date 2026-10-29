"""R25: actual execution-thread operators, calls, weights and lifecycle.

Small transport checks prove execution, not unbiasedness/variance reduction.
"""
from __future__ import annotations

import contextlib
import csv
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))


def run_case(work: Path, name: str, threads: int, factor: float | None, *, runs: int = 1,
             min_weight: float = 0, max_interactions: int = -1, fault: bool = False,
             sensitive: bool = True, neutron: bool = False, aliases: bool = False,
             numeric_failure: bool = False, target_material: str = "G4_WATER", receipt_fault: str = "", cut: str = "0.01 mm"):
    folder = work / name
    folder.mkdir()
    geometry = folder / "geometry.ini"
    thickness = "0.0001 mm" if neutron else "20 mm"
    geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n"
                        f"[volume.Target]\nparent=world\nshape=box\nsize={thickness},20 mm,20 mm\n"
                        f"material={target_material}\nsensitive={str(sensitive).lower()}\n"
                        "[volume.Probe]\nparent=world\nshape=box\nsize=0.01 mm,30 mm,30 mm\n"
                        "position=11 mm,0,0 mm\nmaterial=G4_Galactic\n", encoding="utf-8")
    particle, process = ("neutron", "hadElastic") if neutron else ("e-", "eIoni")
    bias = (f"[biasing]\nenabled=true\n[biasing.xs.{particle}.{process}]\nfactor={factor}\n"
            f"volumes={'Target,target' if aliases else 'Target'}\nonly_primary=false\napply_to_secondaries=true\nmin_weight={min_weight}\n"
            f"max_interactions={max_interactions}\n") if factor is not None else ""
    if aliases:
        # Registry lookup is case-insensitive: both spellings resolve to the
        # same LV. Repeated eIoni must deduplicate; eBrem must also survive.
        bias += (f"[biasing.xs.e-.eBrem]\nfactor={factor}\nvolumes=target\n"
                 "only_primary=false\napply_to_secondaries=true\n")
    config = folder / "main.ini"
    config.write_text(f"[run]\nthreads={threads}\nseed=93\n[output]\nformat=csv\n"
                      f"[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n"
                      f"[physics]\nreference=FTFP_BERT_EMZ\ndefault_cut={cut}\n"
                      "[scoring]\nenabled=true\nhits=true\nevent_edep=true\nedep=true\n"
                      f"[source]\nparticle={particle}\nenergy=1 MeV\nposition=0,0,0 mm\ndirection=+x\n"
                      f"[phase_space]\nvolume=Probe_PV\nparticles={particle}\nkill=true\n" + bias,
                      encoding="utf-8")
    macro = folder / "run.mac"
    macro.write_text(("/AIHL/detector/enableSD false\n" if not sensitive else "") +
                     "/run/initialize\n" + "/run/beamOn 4\n" * runs, encoding="utf-8")
    env = os.environ.copy()
    env.pop("G4USIM_TEST_OUTPUT_FAULT", None)
    if fault: env["G4USIM_TEST_OUTPUT_FAULT"] = "biasing_thread_construct_t0"
    if receipt_fault: env["G4USIM_TEST_OUTPUT_FAULT"] = receipt_fault
    output = folder / "out"
    completed = subprocess.run([str(EXE), "--config", str(config), "--macro", str(macro),
                                "--output", str(output)], cwd=folder, env=env, capture_output=True,
                               text=True, errors="replace", timeout=120)
    log = completed.stdout + completed.stderr
    (folder / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (folder / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    summary_path = output / "run_summary.txt"
    assert summary_path.is_file(), (name, completed.returncode, log[-3000:])
    facts = {k.strip(): v.strip() for line in summary_path.read_text(encoding="utf-8").splitlines()
             if "=" in line for k, v in [line.split("=", 1)]}
    if receipt_fault:
        assert completed.returncode != 0 and facts["status"] == "failed", (name, facts, log[-3000:])
        assert facts["output_failure_stage"] == "biasing_worker_evidence", facts
        assert facts["biasing_worker_coverage_complete"] == "false", facts
        assert int(facts["biasing_expected_worker_evidence_count"]) == threads * runs, facts
        if receipt_fault == "biasing_missing_worker_receipt":
            assert int(facts["biasing_worker_evidence_count"]) == threads * runs - 1, facts
        else:
            assert int(facts["biasing_worker_evidence_count"]) == threads * runs, facts
            assert any(value == "false" for key, value in facts.items() if key.endswith("_end_run_completed")), facts
        return [], [], facts
    if numeric_failure:
        assert completed.returncode != 0 and facts["status"] == "failed", (name, facts, log[-3000:])
        assert facts["output_failure_stage"] == "biasing_cross_section", facts
        assert "factor * analogXS" in facts["output_failure_message"], facts
        assert not list(output.glob("scorer_statistics*.csv")), name
        return [], [], facts
    if fault:
        assert completed.returncode != 0 and facts["status"] == "failed", (name, facts, log[-3000:])
        assert facts["output_failure_stage"] == "biasing_thread_begin", facts
        assert "test-injected worker bias construction failure" in facts["output_failure_message"], facts
        assert not list(output.glob("scorer_statistics*.csv")), name
        return [], [], facts
    assert completed.returncode == 0 and facts["status"] == "completed", (name, facts, log[-3000:])
    assert int(facts["actual_completed_event_count"]) == 4 * runs, facts
    evidence = [json.loads(line.split("[G4USimBiasing] ", 1)[1]) for line in log.splitlines()
                if "[G4USimBiasing] " in line]
    if factor is not None:
        assert facts["biasing_worker_coverage_complete"] == "true", facts
        assert int(facts["biasing_worker_evidence_count"]) == threads * runs, facts
        assert int(facts["biasing_expected_worker_evidence_count"]) == threads * runs, facts
        assert all(facts[f"biasing_worker_{i}_end_run_completed"] == "true" for i in range(threads * runs)), facts
        assert len(evidence) == threads * runs, (name, evidence, log[-3000:])
        assert {(e["run_id"], e["thread_id"]) for e in evidence} == {
            (run, worker) for run in range(runs) for worker in range(threads)}, evidence
        assert all(e["operators"] == 1 and e["matched_rules"] == (2 if aliases else 1) and e["tls_verified"] and
                   not e["failed"] and e["end_run_completed"] for e in evidence), evidence
    else:
        assert not evidence, evidence
    rows = []
    for path in output.glob("hits_t*.csv"):
        with path.open(newline="", encoding="utf-8") as stream: rows.extend(csv.DictReader(stream))
    crossings = []
    for path in output.glob("phase_space_t*.csv"):
        with path.open(newline="", encoding="utf-8") as stream: crossings.extend(csv.DictReader(stream))
    for row in rows + crossings:
        assert math.isfinite(float(row["weight"])) and float(row["weight"]) > 0, row
    (folder / "worker_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"{name}: execution receipts and {len(rows)} hits checked")
    return rows, evidence, crossings


def main() -> None:
    assert EXE.is_file(), EXE
    with contextlib.ExitStack() as stack:
        work = Path(os.environ["G4USIM_TEST_WORK"]).resolve() if os.environ.get("G4USIM_TEST_WORK") else Path(
            stack.enter_context(tempfile.TemporaryDirectory(prefix="g4usim-biasing-worker-")))
        work.mkdir(parents=True, exist_ok=True)
        for threads in (1, 2):
            analog, _, _ = run_case(work, f"analog{threads}", threads, None)
            assert analog and all(float(row["weight"]) == 1 for row in analog)
            neutral, evidence, _ = run_case(work, f"factor1_{threads}", threads, 1)
            assert neutral and all(float(row["weight"]) == 1 for row in neutral)
            assert sum(e["proposals"] for e in evidence) > 0, evidence
            for factor in (0.1, 10):
                rows, evidence, _ = run_case(work, f"factor{factor}_{threads}", threads, factor, runs=2)
                assert rows and any(abs(float(row["weight"]) - 1) > 1e-8 for row in rows), rows[:3]
                for run in (0, 1):
                    assert sum(e["proposals"] for e in evidence if e["run_id"] == run) > 0, evidence
                    assert sum(e["applied_callbacks"] for e in evidence if e["run_id"] == run) > 0, evidence
            for label, options in (("min_weight", {"min_weight": 2}),
                                    ("max_zero", {"max_interactions": 0})):
                rows, evidence, _ = run_case(work, f"{label}_{threads}", threads, 10, **options)
                assert rows and all(float(row["weight"]) == 1 for row in rows)
                assert all(e["proposals"] == e["applied_callbacks"] == 0 for e in evidence), evidence
            # Even when SD is disabled, thread attachment must execute. Thin
            # neutron survival is a deterministic positive-length weight signal.
            _, evidence, crossings = run_case(work, f"thin_neutron{threads}", threads, 100,
                                               sensitive=False, neutron=True)
            assert len(crossings) == 4, crossings
            assert all(float(row["weight"]) > 1 for row in crossings), crossings
            assert sum(e["proposals"] for e in evidence) > 0, evidence
            run_case(work, f"construct_fault{threads}", threads, 10, fault=True)
            for missing in ("biasing_missing_worker_receipt", "biasing_missing_end_receipt"):
                run_case(work, f"{missing}_{threads}", threads, 10, runs=2, receipt_fault=missing)
            _, alias_evidence, _ = run_case(work, f"alias_volume{threads}", threads, 10, aliases=True)
            assert all(e["operators"] == 1 for e in alias_evidence), alias_evidence
            run_case(work, f"xs_overflow{threads}", threads, 1e308, numeric_failure=True, cut="0.000001 mm")
            run_case(work, f"xs_underflow{threads}", threads, 1e-300, numeric_failure=True,
                     neutron=True, target_material="G4_Galactic")
    print("biasing worker runtime: PASS (execution only; no unbiasedness/FOM claim)")


if __name__ == "__main__":
    main()
