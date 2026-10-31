"""K1 component counterexamples and optional real-backend evidence, separately.

Use --executable / G4USIM_EXE for real initialization and small-event runs.
The component runner deliberately never fabricates a successful simulation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from PySide6.QtCore import QCoreApplication, QLocale, QObject, Signal, QThread
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_fingerprint
from g4usim_gui.core.edit_transactions import EditSession
from g4usim_gui.core.experiment_identity import capture_identity, safe_environment
from g4usim_gui.core.experiment_workflow import ExperimentWorkflow as WorkflowService, WorkflowBusyError, WorkflowStaleError
from g4usim_gui.core.experiment_workflow import _compare_csv, _draft_equivalent, _field_report, _verify_request_binding
from g4usim_gui.core.runner import G4USimRunner

# This existing fixture only prepares ordinary F5 snapshots; no test outcomes or
# historical backend receipts are imported or reused.
from test_f5_transactions_backend import initial_state

_SERVICES = []


def ExperimentWorkflow(*args, **kwargs):
    service = WorkflowService(*args, **kwargs)
    _SERVICES.append(service)
    return service


def source_copy_state(folder, executable):
    from g4usim_gui.parsers.geometry_parser import parse_geometry
    from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
    folder.mkdir()
    snapshot, (_, geometry) = initial_state(folder, executable)
    text = geometry.read_text(encoding="utf-8").replace("version = 2", "version = 1") + "vis.palette = legacy\n"
    geometry.write_text(text, encoding="utf-8", newline="\n")
    summary = parse_geometry(geometry, "hierarchical")
    snapshot.project.geometryEditor = geometry_document_from_summary(summary, "hierarchical")
    snapshot.project.geometryEditor.source_copy_mode = True
    snapshot.state["sources"]["geometry"]["text"] = summary.raw_text
    return WorkspaceSnapshot(snapshot.project, snapshot.state)


def wait_for(predicate, timeout=90):
    deadline = time.monotonic() + timeout
    app = QCoreApplication.instance()
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.002)
    assert predicate(), "Asynchronous workflow did not complete within deadline"


def action(service, call, timeout=90):
    received = []
    service.completed.connect(received.append)
    try:
        pending = call()
        assert pending["status"] == "pending", pending
        wait_for(lambda: bool(received), timeout)
        assert len(received) == 1, received
        assert received[0]["record_id"] == pending["record_id"]
        assert not service.busy
        record = received[0]
        path = Path(record["record_dir"]) / "record.json"
        assert path.is_file(), record
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["record_id"] == record["record_id"]
        assert "report" not in saved
        return record
    finally:
        service.completed.disconnect(received.append)


def expect(error, call):
    caught = False
    try:
        call()
    except error:
        caught = True
    assert caught, error


class ComponentRunner(QObject):
    finished = Signal(int)
    errorOccurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.active = False
        self.last_result = None
        self.starts = []
        self.stops = []

    def is_running(self):
        return self.active

    validate_project = staticmethod(G4USimRunner.validate_project)

    def start(self, project, command):
        assert QThread.currentThread() == self.thread()
        self.active = True
        self.starts.append((project, command))

    def terminate(self):
        self.stops.append("terminate")
        self.active = False
        self.finished.emit(1)

    def kill(self):
        self.stops.append("kill")
        self.active = False
        self.finished.emit(1)


def synthetic(folder):
    folder.mkdir()
    component_executable = folder / "G4UniversalSim-component.exe"
    shutil.copyfile(sys.executable, component_executable)
    snapshot, _ = initial_state(folder, component_executable)
    session = EditSession(snapshot)
    runner = ComponentRunner()
    service = ExperimentWorkflow(session, runner, records_root=folder / "records",
                                 environment_probe=lambda executable: {"status": "ready"})
    published_threads = []
    service.completed.connect(lambda record: published_threads.append(QThread.currentThread()))
    fields = action(service, lambda: service.validate())
    assert fields["status"] == "passed", fields.get("reason")
    assert fields["level"] == "fields"
    assert not runner.starts
    identity = fields["identity"]
    candidate = session.current()
    candidate.project.runSettings.beam_on += 1
    changed = capture_identity(candidate, 0, environment=identity["environment"])
    assert identity["fingerprint"] != changed["fingerprint"], "Event count absent from content identity"
    candidate.project.runSettings.seed += 1
    assert capture_identity(candidate, 0, environment=identity["environment"])["fingerprint"] != changed["fingerprint"]
    bad = session.current()
    bad.state["drafts"]["config.seed"] = "invalid"
    before = snapshot_fingerprint(session.current())
    rejected = action(service, lambda: service.apply(bad, expected_revision=0))
    assert rejected["status"] == "failed"
    assert session.revision == 0 and not session.can_undo
    assert snapshot_fingerprint(session.current()) == before
    for binding, raw in (("config.source_editor_energy", "invalid energy"),
                         ("config.physics_editor_default_cut", "invalid cut")):
        candidate = session.current()
        candidate.state["drafts"][binding] = raw
        assert not _field_report(candidate).can_run
        rejected = action(service, lambda: service.apply(candidate))
        assert rejected["status"] == "failed"
        assert session.revision == 0 and not session.can_undo
    formatted = session.current()
    formatted.state["drafts"]["config.source_editor_energy"] = "1000 keV"
    assert _field_report(formatted).can_run
    previous_locale = QLocale()
    try:
        for locale_name in ("zh_HK", "ar_EG", "en_US"):
            locale = QLocale(locale_name)
            QLocale.setDefault(locale)
            assert _draft_equivalent(locale.toString(2), 2, "project.threads.raw")
            assert not _draft_equivalent("invalid 2", 2, "project.threads.raw")
            localized = session.current()
            localized.state["drafts"].update({"project.threads": localized.project.threads,
                "project.threads.raw": locale.toString(localized.project.threads)})
            assert _field_report(localized).can_run
        assert _draft_equivalent("off", 0, "config.scoring_editor_trajectories.raw")
        assert _draft_equivalent("关闭", 0, "config.scoring_editor_trajectories.raw")
        assert not _draft_equivalent("off", 1, "config.scoring_editor_trajectories.raw")
        assert not _draft_equivalent("off", 0, "project.threads.raw")
    finally:
        QLocale.setDefault(previous_locale)
    candidate = session.current()
    rows = [[v.enabled, v.name, v.parent, v.shape, v.material, v.position,
             v.parameters if v.shape.lower() != "box" and v.parameters else v.size,
             v.rotation, v.sensitive, v.bias, v.region,
             *(v.shape_properties.get(key, "") for key in ("dx1", "dx2", "dy1", "dy2", "dz"))]
            for v in candidate.project.geometryEditor.volumes]
    candidate.state["tables"]["geometry_table"] = [[str(value).lower() if type(value) is bool else str(value) for value in row] for row in rows]
    assert _field_report(candidate).can_run
    candidate.state["tables"]["geometry_table"][-1][6] = "invalid size"
    assert not _field_report(candidate).can_run
    invalid_version = session.current()
    invalid_version.state["version"] = 999
    for invalid in (None, invalid_version):
        expect(ValueError, lambda: service.apply(invalid))
        assert not service.busy and session.revision == 0
    bad_source = session.current()
    bad_source.state["sources"]["geometry"]["text"] += "\n# mismatched capture"
    expect(ValueError, lambda: service.apply(bad_source))
    assert not service.busy
    expect(WorkflowStaleError, lambda: service.generate(expected_revision=33))
    good = session.current()
    good.project.sourceEditor.energy = "2 MeV"
    good.project.sourceSettings = good.project.sourceEditor.to_settings()
    good.state["drafts"]["config.source_editor_energy"] = "2 MeV"
    projections = []
    applied = action(service, lambda: service.apply(good, expected_revision=0,
                     apply_snapshot=lambda value: projections.append(snapshot_fingerprint(value))))
    assert applied["status"] == "passed", applied["reason"]
    assert session.revision == 1 and len(projections) == 1
    assert service.records()[0]["stale"]
    session.undo()
    session.redo()
    assert session.revision == 3
    assert next(r for r in service.records() if r["record_id"] == applied["record_id"])["stale"]
    generated = action(service, service.generate)
    assert generated["status"] == "passed", generated["reason"]
    generated2 = action(service, service.generate)
    assert generated2["status"] == "passed", generated2["reason"]
    assert generated["run_id"] != generated2["run_id"]
    assert generated["package"]["output_dir"] != generated2["package"]["output_dir"]
    assert Path(generated["package"]["main_ini_path"]).is_file()
    assert not Path(generated["package"]["output_dir"], "run_summary.txt").exists()
    # Busy rejection and cancellation use only the injected runner. A missing
    # result/provenance must never be upgraded to successful simulation.
    received = []
    service.completed.connect(received.append)
    service.run()
    wait_for(lambda: runner.active or bool(received))
    assert runner.active, received
    expect(WorkflowBusyError, service.generate)
    expect(WorkflowBusyError, service.run)
    service.cancel(force=True)
    wait_for(lambda: bool(received))
    assert received[-1]["status"] == "cancelled", received
    assert runner.stops == ["kill"] and len(runner.starts) == 1
    assert "--run-name" in runner.starts[0][1]
    index = runner.starts[0][1].index("--run-name")
    assert runner.starts[0][1][index + 1] == session.current().project.runSettings.run_name
    assert received[-1]["run_id"] in runner.starts[0][0].outputDir
    service.completed.disconnect(received.append)
    assert all(thread == service.thread() for thread in published_threads)
    # A late worker must fail the monotonic revision guard even after undo.
    entered, release = threading.Event(), threading.Event()
    def held_probe(executable):
        entered.set()
        assert release.wait(10)
        return {"status": "ready"}
    service._probe = held_probe
    received = []
    service.completed.connect(received.append)
    service.run()
    wait_for(entered.is_set)
    session.undo()
    session.redo()
    release.set()
    wait_for(lambda: bool(received))
    assert received[0]["status"] == "stale", received[0]
    assert len(runner.starts) == 1
    service.completed.disconnect(received.append)
    # Caller dictionaries cannot rewrite retained or persisted records.
    records = service.records()
    records[-1]["status"] = "passed"
    assert service.records()[-1]["status"] == "stale"
    imported = action(service, lambda: service.import_history([{"record": fields, "stale": True}]))
    assert imported["status"] == "passed"
    imported_record = next(r for r in service.records() if r.get("session_id") == "historical")
    assert imported_record["stale"] and imported_record["status"] == "stale"
    loaded = ExperimentWorkflow(session, ComponentRunner(), records_root=folder / "records")
    wait_for(lambda: bool(loaded.records()))
    assert all(r["stale"] for r in loaded.records())
    # Environment selection is scientific evidence even if no raw environment
    # dictionary or machine-private selected path is persisted.
    env = {"status": "ready", "capabilities": {"status": "available", "data": {"source_fingerprint": "a" * 64}},
           "data": {"status": "available", "required_complete": True,
                    "report": {"datasets": [{"env": "G4LEDATA", "folder": "data-v1", "required": True,
                                                "found": True, "path": str(folder / "private-A")}]}}}
    other = copy.deepcopy(env)
    other["data"]["report"]["datasets"][0]["path"] = str(folder / "private-B")
    assert safe_environment(env) != safe_environment(other)
    assert "private-A" not in json.dumps(safe_environment(env))
    assert safe_environment(env)["dataset_content_identity"] == "unknown"
    capabilities = {"status": "ready", "capabilities": {"status": "available", "data": {
        "build_git_commit": "a" * 40, "build_git_source_state": "clean", "multithreaded": True}}}
    preserved_capabilities = safe_environment(capabilities)["capabilities"]["data"]
    assert preserved_capabilities["git_commit"] == "a" * 40
    assert preserved_capabilities["git_source_state"] == "clean"
    assert preserved_capabilities["multithreaded"] is True
    # Real query process cwd and relative dataset selection share one anchor.
    from g4usim_gui.core.environment_discovery import _command
    cwd = folder / "probe-cwd"
    cwd.mkdir()
    receipt, stdout = _command([sys.executable, "-c", "import os; print(os.getcwd())"],
                              timeout=5, env=dict(os.environ), cwd=cwd)
    assert receipt["status"] == "completed" and Path(stdout.strip()) == cwd
    relative = copy.deepcopy(env)
    relative["data"]["report"]["datasets"][0]["path"] = "relative-dataset"
    relative["data"]["probe"] = {"working_directory": str(cwd)}
    absolute = copy.deepcopy(relative)
    absolute["data"]["report"]["datasets"][0]["path"] = str(cwd / "relative-dataset")
    assert safe_environment(relative) == safe_environment(absolute)
    # Publication races preserve the same cancelled/stale state on disk and in
    # completed(), rather than leaving a passed receipt from the first write.
    import g4usim_gui.core.experiment_workflow as workflow_module
    real_persist = workflow_module._persist
    for outcome in ("cancelled", "stale"):
        began, release = threading.Event(), threading.Event()
        intercepted = []
        def delayed_persist(record):
            if record.get("status") == "passed" and not intercepted:
                intercepted.append(True)
                began.set()
                assert release.wait(10)
            return real_persist(record)
        race_session = EditSession(snapshot)
        race = ExperimentWorkflow(race_session, ComponentRunner(), records_root=folder / ("race-" + outcome))
        received = []
        race.completed.connect(received.append)
        workflow_module._persist = delayed_persist
        try:
            race.validate()
            wait_for(began.is_set)
            if outcome == "cancelled":
                race.cancel()
            else:
                changed = race_session.current()
                changed.project.runSettings.beam_on += 1
                race_session.replace("edit during terminal persistence", changed)
            release.set()
            wait_for(lambda: bool(received))
            assert received[0]["status"] == outcome, received
            saved = json.loads((Path(received[0]["record_dir"]) / "record.json").read_bytes())
            assert saved["status"] == outcome
            assert not race.busy
        finally:
            release.set()
            workflow_module._persist = real_persist
    # No GUI edit is needed to retire an input whose actual bytes change.
    refreshed = action(service, service.validate)
    assert refreshed["status"] == "passed"
    original_geometry = Path(snapshot.project.pathSettings.geometry_config)
    old_bytes = original_geometry.read_bytes()
    original_geometry.write_bytes(old_bytes + b"\n# changed externally\n")
    service.state()
    wait_for(lambda: not service._refresh_job.pending)
    assert next(r for r in service.records() if r["record_id"] == refreshed["record_id"])["stale"]
    original_geometry.write_bytes(old_bytes)
    validated_backend = action(service, service.validate)
    assert validated_backend["status"] == "passed"
    executable_bytes = component_executable.read_bytes()
    component_executable.write_bytes(executable_bytes + b"\x00")
    service.state()
    wait_for(lambda: not service._refresh_job.pending)
    assert next(r for r in service.records() if r["record_id"] == validated_backend["record_id"])["stale"]
    component_executable.write_bytes(executable_bytes)
    original_geometry.write_bytes(old_bytes)
    service.state()
    wait_for(lambda: not service._refresh_job.pending)
    assert next(r for r in service.records() if r["record_id"] == refreshed["record_id"])["stale"]
    _synthetic_csv_identity(folder)
    local = source_copy_state(folder / "local-source-copy", component_executable)
    local_service = ExperimentWorkflow(EditSession(local), ComponentRunner(), records_root=folder / "local-records")
    local_fields = action(local_service, local_service.validate)
    assert local_fields["status"] == "passed", local_fields["reason"]
    assert local_fields["coverage"] == "local_source_copy_compatibility"
    local_package = action(local_service, local_service.generate)
    assert local_package["status"] == "passed", local_package["reason"]
    assert local_package["execution_bundle"]["manifest_sha256"] is None
    assert "vis.palette = legacy" in Path(local_package["package"]["geometry_ini_path"]).read_text(encoding="utf-8")
    local_export = action(local_service, lambda: local_service.export(folder / "unsupported-export"))
    assert local_export["status"] == "failed" and "Unknown resource grammar" in local_export["reason"]
    missing = local_service.session.current()
    Path(missing.project.pathSettings.geometry_config).unlink()
    refused = action(local_service, local_service.generate)
    assert refused["status"] == "failed" and "package" not in refused
    return {"kind": "synthetic_component", "status": "passed", "records_root": str(service.records_root),
            "physical_validation": "unobserved", "simulation": "not_fabricated"}


def _synthetic_csv_identity(folder):
    reference_path = folder / "component-reference.json"
    reference = {"schema": "g4usim_physical_reference_v1", "quantity": "energy_deposition", "unit": "MeV", "value": 1,
        "source": "synthetic CSV consumer counterexample", "source_kind": "user_supplied", "weighted": False,
        "normalization": "per_event", "object": "sensitive_total", "run": 0, "conditions": "synthetic, no backend"}
    reference_path.write_text(json.dumps(reference), encoding="utf-8")
    spec = dict(artifact="event_edep_t0.csv", column="raw_edep_MeV", quantity="energy_deposition", unit="MeV", reference=1,
        reference_unit="MeV", absolute_tolerance=0, relative_tolerance=0, source=reference["source"],
        statistical_method="mean_standard_error", sigma_multiplier=3, weighted=False, normalization="per_event", run=0,
        object="sensitive_total", reference_file=str(reference_path))
    path = folder / "event_edep_t0.csv"
    evidence = SimpleNamespace(document={"runs": [{"run_id": 0, "completed_events": 2}]}, require=lambda name: folder / name)
    for rows in ("0,0,1,100\n0,00,1,100\n", "0,0,1,100\n0,0,1,100\n", "0,0,1,100\n0,2,1,100\n"):
        path.write_text("runID,eventID,raw_edep_MeV,weighted_edep_MeV\n" + rows, encoding="utf-8")
        expect(ValueError, lambda: _compare_csv(evidence, {}, spec))
    path.write_text("runID,eventID,raw_edep_MeV,weighted_edep_MeV\n0,0,1,100\n0,1,1,100\n", encoding="utf-8")
    compared = _compare_csv(evidence, {"result": {"completed_events": 4}}, spec)
    assert compared["passed"] and compared["sample_count"] == 2
    assert compared["reference_source_verification"] == "user_supplied_unverified_source"
    # A sparse worker is only a lower bound. Merge all selected worker samples
    # and use the chosen run's master N, not process-wide or per-worker N.
    path.write_text("runID,eventID,raw_edep_MeV,weighted_edep_MeV\n0,0,1,100\n", encoding="utf-8")
    worker = folder / "event_edep_t1.csv"
    worker.write_text("runID,eventID,raw_edep_MeV,weighted_edep_MeV\n0,1,1,100\n", encoding="utf-8")
    merged = _compare_csv(evidence, {}, dict(spec, artifact=[path.name, worker.name]))
    assert merged["passed"] and merged["sample_count"] == 2
    expect(ValueError, lambda: _compare_csv(evidence, {}, spec))
    evidence.document["runs"][0]["completed_events"] = 1
    expect(ValueError, lambda: _compare_csv(evidence, {}, spec))
    fixed = _compare_csv(evidence, {}, dict(spec, sigma_multiplier=0))
    assert fixed["passed"] and fixed["standard_error"] is None
    assert fixed["uncertainty_status"] == "insufficient_events"


def real_backend(folder, executable):
    folder.mkdir()
    snapshot, _ = initial_state(folder, executable)
    snapshot.project.runSettings.run_name = "\u3000同名 实验\u00a0"
    session = EditSession(snapshot)
    runner = G4USimRunner()
    service = ExperimentWorkflow(session, runner, records_root=folder / "records")
    fields = action(service, service.validate)
    assert fields["status"] == "passed", fields["reason"]
    inspected = action(service, service.inspect, 180)
    assert inspected["status"] == "passed", inspected["reason"]
    assert inspected["initialization"] == inspected["simulation"] == "unobserved"
    initialized = action(service, lambda: service.validate("initialization"), 180)
    assert initialized["status"] == "passed", initialized["reason"]
    assert initialized["result"]["state"] == "no_run"
    assert initialized["result"]["completed_events"] == 0
    assert initialized["initialization_mesh_identity"]["size_bytes"] > 0
    completed = action(service, service.run, 180)
    assert completed["status"] == "passed", completed["reason"]
    assert completed["result"]["completed_events"] == 3
    assert completed["execution_id"]
    assert len(completed["actual_inputs"]) >= 4
    assert completed["run_id"] in completed["output_dir"]
    assert completed["requested_run_name"] == snapshot.project.runSettings.run_name
    assert completed["observed_run_name"] == snapshot.project.runSettings.run_name
    old_id = completed["record_id"]
    changed = session.current()
    changed.project.sourceEditor.energy = "3 MeV"
    changed.project.sourceSettings = changed.project.sourceEditor.to_settings()
    changed.state["drafts"]["config.source_editor_energy"] = "3 MeV"
    applied = action(service, lambda: service.apply(changed, expected_revision=session.revision))
    assert applied["status"] == "passed", applied["reason"]
    assert next(r for r in service.records() if r["record_id"] == old_id)["stale"]
    session.undo()
    assert next(r for r in service.records() if r["record_id"] == old_id)["stale"]
    second = action(service, service.run, 180)
    assert second["status"] == "passed", second["reason"]
    assert second["run_id"] != completed["run_id"]
    assert second["execution_id"] != completed["execution_id"]
    assert second["requested_run_name"] == completed["requested_run_name"]
    assert second["output_dir"] != completed["output_dir"]
    # Same-label/same-N foreign output is not the current UUID path request.
    from g4usim_gui.output.provenance import output_evidence
    foreign_facts = output_evidence(completed["output_dir"], fresh=True).document["values"]
    expect(ValueError, lambda: _verify_request_binding(second, foreign_facts))
    refused = action(service, lambda: service.evaluate(comparisons=[{"pass": True}]), 180)
    assert refused["status"] == "failed", refused
    # External nested macros are backend-expanded, then the first beamOn and
    # everything after it are excluded from the initialization-only prefix.
    external = session.current()
    external.project.runInputMode = "external"
    external.project.configPath = second["package"]["main_ini_path"]
    external.project.workspaceRoot = second["execution_bundle"]["path"]
    top, nested = folder / "external.mac", folder / "nested.mac"
    top.write_text("/AIHL/source/energy 2 MeV\n/control/execute nested.mac\n", encoding="utf-8", newline="\n")
    nested.write_text("/run/initialize\n/run/beamOn 3\n/AIHL/source/print\n", encoding="utf-8", newline="\n")
    external.project.macroPath = str(top)
    external_runner = G4USimRunner()
    external_service = ExperimentWorkflow(EditSession(external), external_runner, records_root=folder / "external-records")
    external_init = action(external_service, lambda: external_service.validate("initialization"), 180)
    assert external_init["status"] == "passed", external_init["reason"]
    assert external_init["result"]["completed_events"] == 0
    prefix = Path(external_init["command"][external_init["command"].index("--macro") + 1]).read_text(encoding="utf-8")
    assert "/AIHL/source/energy 2 MeV" in prefix
    assert "/run/beamOn" not in prefix and "/AIHL/source/print" not in prefix
    assert external_init["prefix_identity"] != external_init["original_macro_identity"]
    assert external_init["original_macro_identity"]
    external_completed = action(external_service, external_service.run, 180)
    assert external_completed["status"] == "passed", external_completed["reason"]
    assert external_completed["result"]["completed_events"] == 3
    config_only = external_service.session.current()
    config_only.project.macroPath = ""
    external_service.session.reset(config_only)
    config_init = action(external_service, lambda: external_service.validate("initialization"), 180)
    assert config_init["status"] == "passed", config_init["reason"]
    assert config_init["result"]["completed_events"] == 0
    # Real zero-deposition special case: geantino has no physical interactions.
    # This is a narrowly stated analytic/scoring check, not radiation validation.
    zero = session.current()
    zero.project.sourceEditor.particle = "geantino"
    zero.project.sourceSettings = zero.project.sourceEditor.to_settings()
    zero.state["drafts"]["config.source_editor_particle"] = "geantino"
    zero_applied = action(service, lambda: service.apply(zero, expected_revision=session.revision))
    assert zero_applied["status"] == "passed", zero_applied["reason"]
    zero_run = action(service, service.run, 180)
    assert zero_run["status"] == "passed", zero_run["reason"]
    reference_path = folder / "zero-reference.json"
    reference = {"schema": "g4usim_physical_reference_v1", "quantity": "energy_deposition", "unit": "MeV",
        "value": 0, "source": "Geantino noninteracting test particle: analytic zero deposition special case; https://geant4.web.cern.ch/documentation/pipelines/master/bfad_html/ForApplicationDevelopers/TrackingAndPhysics/particle.html",
        "source_kind": "analytic", "weighted": False, "normalization": "per_event", "object": "sensitive_total", "run": 0,
        "conditions": {"particle": "geantino", "energy": "1 MeV", "direction": "+Z", "source_mm": [0,0,-20],
            "world": "100 mm G4_Galactic box", "target": "8 mm FirstTarget silicon box, sensitive", "biasing": False,
            "scope": "noninteracting test particle scoring special case, not general radiation transport validation"}}
    reference_path.write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
    criteria = {"artifact": "event_edep_t0.csv", "column": "raw_edep_MeV", "quantity": "energy_deposition", "unit": "MeV",
        "reference": 0, "reference_unit": "MeV", "absolute_tolerance": 1e-12, "relative_tolerance": 0,
        "source": reference["source"], "statistical_method": "mean_standard_error", "sigma_multiplier": 3,
        "weighted": False, "normalization": "per_event", "run": 0, "object": "sensitive_total", "reference_file": str(reference_path)}
    compared = action(service, lambda: service.evaluate(zero_run["run_id"], [criteria]), 180)
    assert compared["status"] == "passed", compared["reason"]
    assert compared["comparisons"][0]["observed"] == 0
    assert compared["comparisons"][0]["sample_count"] == 3
    assert compared["comparisons"][0]["standard_error"] == 0
    assert compared["comparisons"][0]["reference_source_verification"] == "user_supplied_unverified_source"
    # A different explicit reference gets a new record and fails the same rule.
    reference["value"] = 1
    wrong_path = folder / "wrong-reference.json"
    wrong_path.write_text(json.dumps(reference), encoding="utf-8")
    wrong = dict(criteria, reference=1, reference_file=str(wrong_path))
    mismatch = action(service, lambda: service.evaluate(zero_run["run_id"], [wrong]), 180)
    assert mismatch["status"] == "failed" and not mismatch["comparisons"][0]["passed"], mismatch
    bad_unit = dict(criteria, unit="Gy")
    incompatible = action(service, lambda: service.evaluate(zero_run["run_id"], [bad_unit]), 180)
    assert incompatible["status"] == "failed", incompatible
    bad_weight = dict(criteria, weighted=True)
    incompatible = action(service, lambda: service.evaluate(zero_run["run_id"], [bad_weight]), 180)
    assert incompatible["status"] == "failed", incompatible
    unbound = dict(criteria, reference=2)
    incompatible = action(service, lambda: service.evaluate(zero_run["run_id"], [unbound]), 180)
    assert incompatible["status"] == "failed", incompatible
    # Explicit evaluation in another service rereads evidence and creates a new
    # evaluation. It does not revive its imported old run qualification.
    reopened = ExperimentWorkflow(EditSession(session.current()), G4USimRunner(), records_root=service.records_root)
    reevaluated = action(reopened, lambda: reopened.evaluate(zero_run["run_id"], [criteria]), 180)
    assert reevaluated["status"] == "passed", reevaluated["reason"]
    assert next(r for r in reopened.records() if r["record_id"] == zero_run["record_id"])["stale"]
    exported = action(service, lambda: service.export(folder / "export-with-history"), 180)
    assert exported["status"] == "passed", exported["reason"]
    assert Path(folder / "export-with-history" / "manifest.json").is_file()
    exported_text = (folder / "export-with-history" / "validation_records.json").read_text(encoding="utf-8")
    assert str(folder) not in exported_text and executable.as_posix() not in exported_text
    assert "user_supplied_unverified_source" in exported_text
    overlap = session.current()
    target = next(volume for volume in overlap.project.geometryEditor.volumes if volume.name == "Target")
    duplicate = copy.deepcopy(target)
    duplicate.name = "OverlappingTarget"
    duplicate.sensitive = False
    overlap.project.geometryEditor.volumes.append(duplicate)
    overlap.project.geometryEditor.is_dirty = True
    overlap_service = ExperimentWorkflow(EditSession(overlap), G4USimRunner(), records_root=folder / "overlap-records")
    overlap_result = action(overlap_service, lambda: overlap_service.validate("initialization"), 180)
    assert overlap_result["status"] == "failed", overlap_result
    assert overlap_result["reason"] == "experiment.geometry_overlap_reported", overlap_result["reason"]
    local = source_copy_state(folder / "local-source-copy", executable)
    local.project.runSettings.run_name = snapshot.project.runSettings.run_name
    local_service = ExperimentWorkflow(EditSession(local), G4USimRunner(), records_root=folder / "local-records")
    local_run = action(local_service, local_service.run, 180)
    assert local_run["status"] == "passed", local_run["reason"]
    assert local_run["coverage"] == "local_source_copy_compatibility"
    assert local_run["result"]["completed_events"] == 3
    assert local_run["observed_run_name"] == local.project.runSettings.run_name
    return {"kind": "real_backend", "status": "passed", "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "initialization_record": initialized["record_id"], "run_records": [completed["record_id"], second["record_id"]],
            "external_initialization_records": [external_init["record_id"], config_init["record_id"]],
            "overlap_rejection_record": overlap_result["record_id"],
            "local_source_copy_run": local_run["record_id"],
            "physical_comparison": {"scope": "geantino_zero_deposition_special_case", "positive": compared["record_id"], "negative": mismatch["record_id"],
                                    "reference_authenticity": "user_supplied_unverified"}, "records_root": str(service.records_root)}


def original_inspection_backend(folder, executable):
    """Read-only backend Inspect preserves original paths, not bundle members."""
    from g4usim_gui.core.project import G4USimProject
    import g4usim_gui.core.experiment_workflow as workflow_module
    folder.mkdir()
    initial, (materials, geometry) = initial_state(folder, executable)
    main, top = folder / "原始配置.ini", folder / "入口.mac"
    child = folder / "子目录" / "嵌套 中文.mac"
    child.parent.mkdir()
    main.write_text(f"[materials]\nfile = {materials}\n[geometry]\ntemplate = hierarchical\nconfig = {geometry}\n",
                    encoding="utf-8", newline="\n")
    top.write_text('# original include-only macro\n/control/execute "子目录/嵌套 中文.mac"\n', encoding="utf-8", newline="\n")
    child.write_text("# preserve line\n/control/echo INSPECT_MUST_NOT_EXECUTE\n", encoding="utf-8", newline="\n")
    project = G4USimProject(runInputMode="external", executable=str(executable), workspaceRoot=str(folder),
        configPath=main.name, macroPath=top.name, outputDir=str(folder / "not-created-output"),
        runsRoot=str(folder / "runs"), threads=1)
    runner = G4USimRunner()
    service = ExperimentWorkflow(EditSession(WorkspaceSnapshot(project)), runner, records_root=folder / "records")
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (main, top, child)}
    observed = action(service, service.inspect, 90)
    assert observed["status"] == "passed", observed["reason"]
    assert observed["coverage"] == "original_declared_inputs_observed"
    assert observed["recursive_closure"] == "unobserved"
    assert observed["qualifies"] == "configure_preflight_only"
    assert observed["initialization"] == observed["simulation"] == "unobserved"
    transport = observed["inspection_launch"]
    assert Path(transport["working_directory"]) == folder
    assert service._inspect.workingDirectory() == transport["launch_working_directory"]
    if transport["launch_route"] == "direct":
        assert Path(service._inspect.workingDirectory()) == folder
    else:
        assert transport["arguments"][transport["arguments"].index("--working-directory") + 1] == str(folder)
    assert observed["command"][observed["command"].index("--config") + 1] == main.name
    assert observed["command"][observed["command"].index("--macro") + 1] == top.name
    command = observed["plan"]["macro_plan"]["commands"][0]
    assert Path(command["file"]) == child and command["line"] == 2
    assert command["text"] == "/control/echo INSPECT_MUST_NOT_EXECUTE"
    raw_plan = json.loads((Path(observed["record_dir"]) / "inspect.stdout.log").read_bytes())
    assert raw_plan == observed["plan"]
    assert Path(raw_plan["working_directory"]) == folder
    assert "package" not in observed and not (Path(observed["record_dir"]) / "execution-inputs").exists()
    assert {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (main, top, child)} == hashes
    assert not runner.is_running() and runner.last_result is None
    assert not Path(project.outputDir).exists() and not list(folder.rglob("run_summary.txt"))
    # /control/echo and /AIHL/output/setDir are not export-closure syntax.
    # Inspection must reach the backend and preserve its actual refusal bytes.
    child.write_text("# preserve line\n/AIHL/output/setDir old-output\n", encoding="utf-8", newline="\n")
    refused = action(service, service.inspect, 90)
    assert refused["status"] == "failed", refused["reason"]
    raw_error = (Path(refused["record_dir"]) / "inspect.stderr.log").read_bytes().decode("utf-8", "replace")
    assert "conflicts with an explicit CLI lock" in raw_error
    assert child.name in raw_error and ":2" in raw_error
    assert refused["reason"] == "experiment.inspect_failed: " + raw_error
    assert not Path(project.outputDir).exists() and not list(folder.rglob("run_summary.txt"))
    child.write_text("# preserve line\n/control/echo INSPECT_MUST_NOT_EXECUTE\n", encoding="utf-8", newline="\n")
    original_identity = workflow_module._original_inspection_identity
    calls = []
    def changed_during_query(snapshot, revision):
        calls.append(True)
        if len(calls) == 2:
            top.write_bytes(top.read_bytes() + b"# changed during inspect\n")
        return original_identity(snapshot, revision)
    workflow_module._original_inspection_identity = changed_during_query
    try:
        stale = action(service, service.inspect, 90)
        assert stale["status"] == "stale", stale["reason"]
        assert stale["reason"] == "experiment.inputs_changed_during_inspection"
        assert "plan" not in stale
    finally:
        workflow_module._original_inspection_identity = original_identity
    assert not runner.is_running() and runner.last_result is None
    return {"kind": "real_original_input_inspection", "status": "passed", "records_root": str(service.records_root),
            "record_ids": [observed["record_id"], refused["record_id"], stale["record_id"]],
            "simulation": "not_executed", "recursive_closure": "unobserved"}


def run_fact_export(folder, record_path, bundle_path, executable):
    """Roundtrip previously captured real facts; no simulation is reexecuted."""
    from g4usim_gui.core.config_migration import load_json_strict
    from g4usim_gui.core.experiment_workflow import _portable_record
    from g4usim_gui.core.experiment_bundle import export_bundle, load_bundle
    from g4usim_gui.core.experiment_identity import canonical_digest
    folder.mkdir()
    recorded = load_json_strict(Path(record_path).read_bytes())
    assert recorded["action"] == "run" and recorded["status"] == "passed"
    for key in ("random_settings", "build", "input_coverage", "input_exclusions", "requested_run_name", "observed_run_name"):
        assert key in recorded, key
    portable = _portable_record(recorded)
    assert portable["random_settings"] == recorded["random_settings"]
    assert portable["random_settings"]["initial_engine_seed"] == "unknown"
    assert portable["build"] == recorded["build"]
    assert portable["input_coverage"] == recorded["input_coverage"]
    assert portable["input_exclusions"] == recorded["input_exclusions"]
    assert portable["requested_run_name"] == recorded["requested_run_name"]
    assert portable["observed_run_name"] == recorded["observed_run_name"]
    # A separate synthetic projection counterexample does not change the actual
    # historical run record being roundtripped below.
    synthetic = copy.deepcopy(recorded)
    private = r"C:\private-source\seed.ini"
    synthetic["random_settings"]["effective_seed_origin_file"] = private
    projected = _portable_record(synthetic)
    assert projected["random_settings"]["effective_seed_origin_file"] == "omitted_local_path"
    assert projected["random_settings"]["effective_seed_origin_file_path_text_sha256"] == canonical_digest(private)
    assert private not in json.dumps(projected)
    assert projected["random_settings"]["initial_engine_seed"] == "unknown"
    assert _portable_record(projected)["random_settings"] == projected["random_settings"]
    snapshot = load_bundle(bundle_path, executable=str(executable))
    destination = folder / "facts-bundle"
    export_bundle(snapshot, destination, validation_records=[portable])
    loaded = load_bundle(destination, executable=str(executable))
    wrappers = loaded.transient["bundle"]["validation_records"]
    assert len(wrappers) == 1 and wrappers[0]["stale"]
    history = wrappers[0]["record"]
    for key in ("random_settings", "build", "input_coverage", "input_exclusions", "requested_run_name", "observed_run_name"):
        assert history[key] == portable[key], key
    assert history["random_settings"]["initial_engine_seed"] == "unknown"
    assert "source_fingerprint" in history["build"]
    return {"kind": "real_historical_fact_export_load", "status": "passed",
        "record_id": recorded["record_id"], "run_reexecuted": False, "bundle": str(destination),
        "source_record_sha256": hashlib.sha256(Path(record_path).read_bytes()).hexdigest(),
        "initial_engine_seed": history["random_settings"]["initial_engine_seed"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", default=os.environ.get("G4USIM_EXE", ""))
    parser.add_argument("--component", action="store_true")
    parser.add_argument("--inspect-only", action="store_true", help="Real original-input Inspect compatibility only")
    parser.add_argument("--export-facts-record", default="", help="Existing real run record for focused export/load check")
    parser.add_argument("--export-facts-bundle", default="", help="Existing verified input bundle for focused export/load check")
    parser.add_argument("--report-root", default="")
    args = parser.parse_args()
    if not args.report_root and os.environ.get("G4USIM_TEST_EVIDENCE_DIR"):
        from uuid import uuid4
        args.report_root = str(Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"]) / ("k1-workflow-" + uuid4().hex))
    app = QCoreApplication.instance() or QCoreApplication([])
    with tempfile.TemporaryDirectory(prefix="k1-workflow-") if not args.report_root else _directory(args.report_root) as directory:
        root = Path(directory).resolve()
        try:
            if args.export_facts_record or args.export_facts_bundle:
                assert args.export_facts_record and args.export_facts_bundle and args.executable and not args.component
                result = [run_fact_export(root / "run-facts", args.export_facts_record, args.export_facts_bundle,
                                          Path(args.executable).resolve())]
            elif args.inspect_only:
                assert args.executable and not args.component, "--inspect-only requires a real --executable"
                result = [original_inspection_backend(root / "原始 中文输入", Path(args.executable).resolve())]
            else:
                result = [synthetic(root / "synthetic")]
            if args.executable and not args.component and not args.inspect_only and not args.export_facts_record:
                result.append(real_backend(root / "真实 后端", Path(args.executable).resolve()))
            report = {"schema": "k1_workflow_specialized_v1", "results": result,
                      "formal_acceptance": "not_claimed_requires_rebuilt_frozen_matrix"}
            (root / "specialized-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        finally:
            for service in _SERVICES:
                service.close()
            wait_for(lambda: all(service._closed for service in _SERVICES), 30)
            assert all(not service._watcher.files() and not service._watcher.directories() for service in _SERVICES)
            assert all(not job.pending for service in _SERVICES for job in
                       (service._job, service._history_job, service._refresh_job))
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))


class _directory:
    def __init__(self, path):
        self.path = Path(path)
    def __enter__(self):
        self.path.mkdir(parents=True, exist_ok=False)
        return str(self.path)
    def __exit__(self, *args):
        return False


if __name__ == "__main__":
    main()
