"""Real K1 export/load/edit/rerun in a clean relocated directory.

This verifies workflow and consumed configuration, not radiation physics.
All artifacts are retained when the unified runner supplies an evidence root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtCore import QCoreApplication
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.core.edit_transactions import EditSession
from g4usim_gui.core.experiment_bundle import load_bundle, inspect_bundle
from g4usim_gui.core.experiment_workflow import ExperimentWorkflow
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.output.run_summary_parser import parse_run_summary
from test_f5_transactions_backend import initial_state
from test_k1_workflow import action, wait_for

SERVICES = []


def perform(service, call):
    record = action(service, call, 180)
    assert record["status"] == "passed", (record["action"], record["reason"])
    return record


def exercise(root, executable):
    original = root / "original-inputs"
    original.mkdir()
    snapshot, _ = initial_state(original, executable)
    first = ExperimentWorkflow(EditSession(snapshot), G4USimRunner(), records_root=root / "original-records")
    SERVICES.append(first)
    completed = perform(first, first.run)
    assert completed["result"]["completed_events"] == 3
    bundle = root / "exported"
    perform(first, lambda: first.export(bundle))
    manifest_before = hashlib.sha256((bundle / "manifest.json").read_bytes()).hexdigest()
    rejected = action(first, lambda: first.export(bundle), 180)
    assert rejected["status"] == "failed"
    assert hashlib.sha256((bundle / "manifest.json").read_bytes()).hexdigest() == manifest_before

    # Keep the old input evidence, but remove its original usable pathname.
    retained = root / "retained-original-inputs"
    assert original.resolve().parent == retained.resolve().parent == root.resolve()
    original.rename(retained)
    clean = root / "干净 新目录"
    clean.mkdir()
    relocated = clean / "实验配置包"
    bundle.rename(relocated)
    assert not original.exists() and not bundle.exists()
    verified = inspect_bundle(relocated)
    assert verified["manifest_sha256"] == manifest_before
    loaded = load_bundle(relocated, executable=str(executable))
    loaded.project.runsRoot = loaded.project.pathSettings.runs_root = str(clean / "runs")
    session = EditSession(loaded)
    second = ExperimentWorkflow(session, G4USimRunner(), records_root=clean / "records")
    SERVICES.append(second)
    perform(second, lambda: second.import_history(loaded.transient["bundle"]["validation_records"]))
    imported = [r for r in second.records() if r.get("action") == "run"]
    assert imported and all(r["stale"] for r in imported)
    assert next(v for v in second.state()["levels"] if v["level"] == "execution")["status"] == "stale"

    before, revision = snapshot_fingerprint(session.current()), session.revision
    invalid = session.current()
    invalid.state["drafts"]["config.source_editor_energy"] = "not an energy"
    refused = action(second, lambda: second.apply(invalid), 180)
    assert refused["status"] == "failed"
    assert session.revision == revision and snapshot_fingerprint(session.current()) == before

    changed = session.current()
    changed.project.sourceEditor.energy = "3 MeV"
    changed.project.sourceSettings = changed.project.sourceEditor.to_settings()
    changed.state["drafts"]["config.source_editor_energy"] = "3 MeV"
    perform(second, lambda: second.apply(changed, expected_revision=revision))
    perform(second, second.validate)
    initialized = perform(second, lambda: second.validate("initialization"))
    assert initialized["result"]["state"] == "no_run"
    rerun = perform(second, second.run)
    assert rerun["result"]["completed_events"] == 3
    assert rerun["run_id"] != completed["run_id"]
    assert rerun["execution_id"] != completed["execution_id"]
    assert Path(rerun["output_dir"]).resolve().is_relative_to(clean.resolve())
    summary = parse_run_summary(Path(rerun["output_dir"]) / "run_summary.txt").key_values
    assert float(summary["effective_source_energy_MeV"]) == 3.0
    assert all(str(original) not in row["path"] for row in rerun["actual_inputs"])
    assert any(r["stale"] for r in second.records() if r.get("action") == "run" and r["record_id"] != rerun["record_id"])

    revised = session.current()
    revised.project.seed = "4343"
    revised.project.runSettings.seed = 4343
    for binding in ("project.seed", "config.seed"):
        if binding in revised.state["drafts"]:
            revised.state["drafts"][binding] = "4343"
    perform(second, lambda: second.apply(revised))
    assert next(r for r in second.records() if r["record_id"] == rerun["record_id"])["stale"]
    final = perform(second, second.run)
    assert final["result"]["completed_events"] == 3 and final["run_id"] != rerun["run_id"]
    reexport = clean / "再次导出"
    perform(second, lambda: second.export(reexport))
    final_loaded = load_bundle(reexport, executable=str(executable))
    assert final_loaded.project.sourceEditor.energy == "3 MeV"
    assert final_loaded.project.runSettings.seed == 4343
    assert all(r["stale"] for r in final_loaded.transient["bundle"]["validation_records"])
    return {"status": "passed", "kind": "real_backend_workflow_not_physical_validation",
            "backend_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "run_ids": [completed["run_id"], rerun["run_id"], final["run_id"]],
            "record_roots": [str(first.records_root), str(second.records_root)],
            "relocated_bundle": str(relocated), "reexported_bundle": str(reexport)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", default=os.environ.get("G4USIM_EXE", ""))
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()
    executable = Path(args.executable).resolve()
    assert args.executable and executable.is_file(), "A real G4USIM_EXE is required"
    app = QCoreApplication.instance() or QCoreApplication([])
    evidence = args.evidence_root
    if evidence is None and os.environ.get("G4USIM_TEST_EVIDENCE_DIR"):
        evidence = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"]) / ("roundtrip-" + uuid4().hex)
    temporary = tempfile.TemporaryDirectory(prefix="k1-roundtrip-") if evidence is None else None
    root = Path(temporary.name) if temporary else evidence.resolve()
    if not temporary:
        root.mkdir(parents=True, exist_ok=False)
    try:
        result = exercise(root, executable)
        (root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        for service in SERVICES:
            if service.busy:
                service.cancel(force=True)
            drained = []
            service.closed.connect(lambda: drained.append(True))
            if not service.close():
                wait_for(lambda: bool(drained), 30)
        app.processEvents()
        if temporary:
            temporary.cleanup()


if __name__ == "__main__":
    main()
