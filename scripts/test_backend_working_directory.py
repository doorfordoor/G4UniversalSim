"""Real deep-directory CLI and K1 process launches; not a physics benchmark."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtCore import QCoreApplication
from g4usim_gui.core.edit_transactions import EditSession
from g4usim_gui.core.environment_discovery import probe_environment
from g4usim_gui.core.experiment_bundle import export_bundle, load_bundle
from g4usim_gui.core.experiment_workflow import ExperimentWorkflow
from g4usim_gui.core.runner import G4USimRunner
from test_f5_transactions_backend import initial_state, summary_values
from test_k1_workflow import action, wait_for


def invoke(executable, root, label, arguments, *, cwd=None):
    result = subprocess.run([str(executable), *map(str, arguments)], cwd=cwd or root,
                            capture_output=True, timeout=90)
    (root / (label + ".stdout.log")).write_bytes(result.stdout)
    (root / (label + ".stderr.log")).write_bytes(result.stderr)
    return result


def exercise(root, executable):
    source = root / "source"
    source.mkdir()
    snapshot, _ = initial_state(source, executable)
    deep = root
    while len(str(deep).encode("utf-16-le")) // 2 < 280:
        deep /= "深层 空格 𠮷-" + "segment-" * 5
    deep.mkdir(parents=True)
    bundle_root = deep / "inputs"
    bundle = export_bundle(snapshot, bundle_root)
    replay = bundle["replay_inputs"]
    output = deep / "cli-output"

    # A wrong launch-directory implementation must not silently consume these.
    for key in ("config", "macro"):
        shadow = root / replay[key]
        shadow.parent.mkdir(parents=True, exist_ok=True)
        shadow.write_text("WRONG ANCESTOR INPUT\n", encoding="utf-8")
    shadows = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in (root / replay["config"], root / replay["macro"])}
    inspect_args = ["--working-directory", bundle_root, "--config", replay["config"],
                    "--macro", replay["macro"], "--output", output, "--inspect-run"]
    inspected = invoke(executable, root, "cli-inspect", inspect_args)
    assert inspected.returncode == 0, inspected.stderr.decode("utf-8", errors="replace")
    plan = json.loads(inspected.stdout)
    assert Path(plan["working_directory"]).resolve() == bundle_root.resolve()
    assert not output.exists(), "Read-only inspection created simulation output"
    ran = invoke(executable, root, "cli-run", inspect_args[:-1])
    assert ran.returncode == 0, ran.stderr.decode("utf-8", errors="replace")
    summary = summary_values(output / "run_summary.txt")
    assert summary["status"] == summary["macro_execution_status"] == "completed"
    assert summary["summary_write_status"] == "completed"
    assert summary["output_failure_status"] == "none"
    assert summary["planned_event_count"] == summary["actual_completed_event_count"] == "3"
    assert (output / "effective_config_configure.json").is_file()
    assert (output / "run_metadata.json").is_file()
    assert not list(output.glob("*.tmp-*")), "Snapshot temporary files survived publication"
    for path, expected in shadows.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
    assert not (root / "run_summary.txt").exists()

    file_target = root / "ordinary-file"
    file_target.write_text("not a directory", encoding="utf-8")
    invalid = [
        ["--working-directory"], ["--working-directory", ""],
        ["--working-directory", "relative"],
        ["--working-directory", root / "missing"],
        ["--working-directory", file_target],
        ["--working-directory", bundle_root, "--working-directory", root],
    ]
    before = {p.relative_to(root).as_posix() for p in root.rglob("run_summary.txt")}
    for index, arguments in enumerate(invalid):
        result = invoke(executable, root, "invalid-cwd-" + str(index), arguments)
        assert result.returncode != 0
        assert b"working-directory" in result.stderr
        assert not result.stdout, "Invalid cwd reached a backend operation"
    assert {p.relative_to(root).as_posix() for p in root.rglob("run_summary.txt")} == before

    # Real environment subprocess and both existing QProcess owners must agree.
    environment = probe_environment(executable, cwd=bundle_root)
    assert environment["status"] == "ready", environment.get("diagnostics")
    assert environment["capabilities"]["data"]["launch"]["working_directory"] is True
    assert Path(environment["capabilities"]["probe"]["working_directory"]).resolve() == bundle_root.resolve()
    assert Path(environment["data"]["probe"]["working_directory"]).resolve() == bundle_root.resolve()

    # Exercise data-file discovery itself before Manager construction, rather
    # than only asserting the Python probe's requested-directory echo. Empty
    # dataset folders are sufficient for this directory-discovery contract;
    # they are never used for transport, which retains the real environment.
    locator = root / "locator-copy"
    locator.mkdir()
    copied = locator / executable.name
    shutil.copy2(executable, copied)
    assert hashlib.sha256(copied.read_bytes()).digest() == hashlib.sha256(executable.read_bytes()).digest()
    (locator / "geant4-data.txt").write_text("relative-data\n", encoding="utf-8")
    # probe_environment accepts overlays: None explicitly removes a variable.
    data_env = {"GEANT4_DATA_DIR": None}
    for dataset in environment["data"]["report"]["datasets"]:
        data_env[dataset["env"]] = None
        (bundle_root / "relative-data" / dataset["folder"]).mkdir(parents=True)
    relative = probe_environment(copied, cwd=bundle_root, env=data_env)
    relative_report = relative["data"]["report"]
    assert relative_report["geant4_data_dir"] == "relative-data", relative_report
    assert relative_report["required_complete"] is True
    assert all(row["found"] for row in relative_report["datasets"])
    for row in relative_report["datasets"]:
        observed = Path(row["path"])
        if not observed.is_absolute():
            observed = bundle_root / observed
        assert observed.resolve() == (bundle_root / "relative-data" / row["folder"]).resolve()
    wrong = probe_environment(copied, cwd=root, env=data_env)
    # The kernel may find its compiled default datasets; that does not authorize
    # treating the wrong cwd as the requested relative-data environment.
    assert wrong["data"]["report"]["geant4_data_dir"] is None
    assert wrong["data"]["report"]["note"] != relative_report["note"]
    assert not (root / "relative-data").exists()
    (root / "relative-discovery.json").write_text(json.dumps(
        {"positive": relative, "negative": wrong}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    loaded = load_bundle(bundle_root, executable=str(executable))
    loaded.project.runInputMode = "external"
    loaded.project.configPath = str(bundle_root / replay["config"])
    loaded.project.macroPath = str(bundle_root / replay["macro"])
    loaded.project.workspaceRoot = str(bundle_root)
    loaded.project.outputDir = str(deep / "requested-output")
    service = ExperimentWorkflow(EditSession(loaded), G4USimRunner(), records_root=deep / "records")
    try:
        inspected_record = action(service, service.inspect, 90)
        assert inspected_record["status"] == "passed", inspected_record.get("reason")
        initialized = action(service, lambda: service.validate("initialization"), 120)
        assert initialized["status"] == "passed", initialized.get("reason")
        assert initialized["result"]["state"] == "no_run"
        completed = action(service, service.run, 120)
        assert completed["status"] == "passed", completed.get("reason")
        assert completed["result"]["completed_events"] == 3
        assert completed["actual_inputs"]
        execution_root = Path(completed["execution_bundle"]["path"])
        for row in completed["actual_inputs"]:
            consumed = Path(row["path"])
            if not consumed.is_absolute():
                consumed = execution_root / consumed
            consumed = consumed.resolve()
            assert consumed.is_relative_to(Path(completed["record_dir"]).resolve())
            assert row["status"] == "recorded"
            assert row["sha256"] == hashlib.sha256(consumed.read_bytes()).hexdigest()
        output_path = Path(completed["output_dir"])
        assert output_path.resolve().is_relative_to(deep.resolve())
        actual = summary_values(output_path / "run_summary.txt")
        assert actual["status"] == "completed" and actual["actual_completed_event_count"] == "3"
        return {"kind": "real_cli_and_existing_qprocess_workflow_not_physical_validation",
                "backend_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                "cwd_utf16_units": len(str(bundle_root).encode("utf-16-le")) // 2,
                "output_utf16_units": len(str(output_path).encode("utf-16-le")) // 2,
                "run_id": completed["run_id"], "events": 3}
    finally:
        if service.busy:
            service.cancel(force=True)
        closed = []
        service.closed.connect(lambda: closed.append(True))
        if not service.close():
            wait_for(lambda: bool(closed), 30)


def main():
    executable = Path(os.environ.get("G4USIM_EXE", "")).resolve()
    assert executable.is_file(), "A real G4USIM_EXE is required"
    app = QCoreApplication.instance() or QCoreApplication([])
    evidence = os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
    temporary = None if evidence else tempfile.TemporaryDirectory(prefix="k1-deep-")
    root = Path(evidence) / ("deep-" + uuid4().hex) if evidence else Path(temporary.name)
    root.mkdir(parents=True, exist_ok=temporary is not None)
    try:
        result = exercise(root, executable)
        (root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        app.processEvents()
        if temporary:
            temporary.cleanup()


if __name__ == "__main__":
    main()
