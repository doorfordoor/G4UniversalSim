"""Required-backend J2: memory editors -> real Qt/K1 -> movable CLI replay.

The unified runner supplies G4USIM_EXE and G4USIM_TEST_EVIDENCE_DIR. No backend
fallback or synthetic success is permitted. --allow-stale-backend is an explicit
local diagnostic mode; its receipt is never labelled a fresh-source acceptance.
Vacuum proton transport tests event/volume identity and step limits, not physics
accuracy or independent sensitive-detector response calibration.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gui"), str(ROOT / "scripts")]

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from run_m0_tests import workspace_source_fingerprint
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_fingerprint
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.run_editor_model import GPSDefinition, RegionDefinition
from g4usim_gui.editors.geometry_editor_model import HierarchicalVolumeRow
from g4usim_gui.models.package_model import PathSettings

EVENTS = 4


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def wait_for(app, predicate, *, timeout=180):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert predicate(), "J2 asynchronous action/visible output did not finish"
    app.processEvents()


def action(app, window, start, evidence, label, receipt):
    """Observe the existing owner's real terminal signal and persisted record."""
    received = []
    window.experiment.completed.connect(received.append)
    try:
        start()
        assert received or window.experiment.busy, (label, window.run_page.macro_plan_view.toPlainText())
        wait_for(app, lambda: bool(received) and not window.experiment.busy)
        assert len(received) == 1, (label, received)
        record = received[0]
        saved = Path(record["record_dir"]) / "record.json"
        assert saved.is_file(), (label, record)
        persisted = json.loads(saved.read_text(encoding="utf-8"))
        assert persisted["record_id"] == record["record_id"]
        receipt["actions"].append({"label": label, "record_id": record["record_id"],
                                   "status": record["status"], "reason": record.get("reason"),
                                   "record_path": str(saved)})
        write_json(evidence / "receipt.json", receipt)
        assert record["status"] == "passed" and not record.get("stale"), (
            label, record["status"], record.get("reason"), str(saved))
        return record
    finally:
        window.experiment.completed.disconnect(received.append)


def summary(output):
    path = output / "run_summary.txt"
    assert path.is_file(), path
    return {k.strip(): v.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if "=" in line for k, v in [line.split("=", 1)]}


def check_run(output):
    """Check complete events and both simultaneous primaries in both volumes."""
    data = summary(output)
    assert data["status"] == data["macro_execution_status"] == "completed", data
    assert data["summary_write_status"] == "completed" and data["output_failure_status"] == "none"
    assert int(data["run_count"]) == 1
    assert int(data["run_0_planned_events"]) == int(data["run_0_completed_events"]) == EVENTS
    assert int(data["planned_event_count"]) == int(data["actual_completed_event_count"]) == EVENTS
    expected = {(0, event) for event in range(EVENTS)}
    event_keys = set()
    event_files = sorted(output.glob("*event_edep_t*.csv"))
    hit_files = sorted(output.glob("*hits_t*.csv"))
    assert event_files and hit_files, output
    for path in event_files:
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                key = int(row["runID"]), int(row["eventID"])
                assert key in expected and key not in event_keys, (path, key)
                event_keys.add(key)
    assert event_keys == expected, event_keys
    primaries = defaultdict(dict)
    hit_count = 0
    for path in hit_files:
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                key = int(row["runID"]), int(row["eventID"])
                assert key in event_keys, (path, row)
                volume = row["volume"].removesuffix("_PV")
                assert volume in {"Upstream", "Downstream"}, row
                length = float(row["stepLength_mm"])
                assert math.isfinite(length) and 0 <= length <= .5 + 1e-6, row
                hit_count += 1
                if int(row["parentID"]) == 0:
                    assert row["particle"] == "proton", row
                    primaries[key, volume].setdefault(int(row["trackID"]), float(row["kineticEnergy_MeV"]))
    for key in expected:
        track_sets = []
        for volume in ("Upstream", "Downstream"):
            tracks = primaries[key, volume]
            assert len(tracks) == 2, (key, volume, tracks)
            assert all(math.isclose(actual, target, rel_tol=1e-5, abs_tol=1e-5)
                       for actual, target in zip(sorted(tracks.values()), (10., 20.))), tracks
            track_sets.append(set(tracks))
        assert track_sets[0] == track_sets[1], (key, track_sets)
    return {"events": len(event_keys), "hits": hit_count, "volumes": ["Upstream", "Downstream"],
            "primaries_per_event_per_volume": 2, "max_step_mm": .5}


def physics_inventory(output, *, require_processes=True):
    path = output / "effective_config_finalization.json"
    assert path.is_file(), path
    document = json.loads(path.read_text(encoding="utf-8"))
    inventories = [row for row in document["evidence"]
                   if "registered_constructors" in row
                   and (not require_processes or "particle_processes" in row)]
    assert inventories, path
    return inventories[-1], document


def check_physics(output, baseline):
    inventory, document = physics_inventory(output)
    names = inventory["registered_constructors"]
    assert any("livermore" in name.lower() for name in names), names
    removed = {name for name in baseline["registered_constructors"]
               if "standard" in name.lower() and "em" in name.lower()}
    assert removed and not (removed & set(names)), (removed, names)
    assert "StepLimiter" in inventory["particle_processes"]["proton"], inventory
    regions = {row["path"] for row in document["evidence"]
               if row.get("observed") == "ActiveRegion"
               and row.get("evidence_level") == "kernel_constructed"}
    assert {"/geometry/objects/Upstream/region", "/geometry/objects/Downstream/region"} <= regions, regions
    return {"constructors": names, "removed_standard_em": sorted(removed),
            "proton_step_limiter_observed": True}


def memory_project(window, executable, root):
    """Use the actual new-blank entry, then apply a private candidate via K1."""
    project = G4USimProject(executable=str(executable), workspaceRoot=str(root / "workspace"),
                           runsRoot=str(root / "runs"))
    Path(project.workspaceRoot).mkdir()
    project.pathSettings = PathSettings(executable=project.executable,
                                       workspace_root=project.workspaceRoot, runs_root=project.runsRoot)
    window._set_project(project)
    assert window.new_blank_project()
    assert not window.project_file
    page = window.config_builder_page
    assert page.materials_summary is None and page.geometry_summary is None
    before = snapshot_fingerprint(window.capture_workspace())
    page.revert_geometry_button.click()
    page.revert_materials_button.click()
    window._finish_history_merge()
    assert snapshot_fingerprint(window.capture_workspace()) == before, "No-source Revert discarded memory input"
    assert not list(Path(project.workspaceRoot).iterdir()), "Blank creation required pre-existing source files"


def execute(app, executable, root, receipt):
    window = MainWindow()
    warnings = []
    try:
        window.show()
        memory_project(window, executable, root)
        assert window.experiment.runner is window.runner
        assert window.experiment.session is window._edit_session
        assert window.experiment._inspect is window._macro_inspection
        baseline = action(app, window, lambda: window._experiment_action("initialize"), root,
                          "blank-initialize", receipt)
        baseline_inventory, _ = physics_inventory(Path(baseline["output_dir"]), require_processes=False)
        candidate = copy.deepcopy(window.capture_workspace().project)
        candidate.editingState = None
        candidate.geometryEditor.volumes.extend([
            HierarchicalVolumeRow(name=name, parent="world", shape="box", size="10 mm,10 mm,2 mm",
                                  material="G4_Galactic", position=f"0,0,{z} mm", sensitive=True)
            for name, z in (("Upstream", -5), ("Downstream", 5))])
        candidate.sourceEditor.gps_sources = [
            GPSDefinition(name=name, particle="proton", energy=energy, center=f"{x},0,-20 mm")
            for name, x, energy in (("low", -2, "10 MeV"), ("high", 2, "20 MeV"))]
        candidate.sourceEditor.multiple_vertex = True
        candidate.physicsEditor.replace_modules = ["G4EmLivermorePhysics"]
        candidate.physicsEditor.regions = [RegionDefinition(name="ActiveRegion", volumes="Upstream,Downstream",
                                                           max_step="0.5 mm")]
        candidate.scoringEditor.hits = candidate.scoringEditor.event_edep = True
        candidate.runSettings.beam_on = EVENTS
        candidate.runSettings.threads = candidate.threads = 2
        candidate.sourceEditor.is_dirty = candidate.physicsEditor.is_dirty = candidate.scoringEditor.is_dirty = True
        action(app, window, lambda: window.experiment.apply(WorkspaceSnapshot(candidate)), root,
               "apply-two-sources-two-volumes", receipt)
        ids = [source.editor_id for source in window.project.sourceEditor.gps_sources]
        with patch.object(QMessageBox, "warning", side_effect=lambda *args: warnings.append(str(args[-1])) or QMessageBox.Ok):
            for token in ("validate", "generate", "initialize", "run"):
                record = action(app, window, lambda token=token: window._experiment_action(token), root, token, receipt)
        output = Path(record["output_dir"])
        receipt["qt_run"] = check_run(output)
        receipt["physics"] = check_physics(output, baseline_inventory)
        wait_for(app, lambda: window.output_page.file_tree.topLevelItemCount() > 0)
        assert window.run_page._result_state == "success" and window.run_page.result_label.text()
        assert Path(window.output_page._output_dir) == output
        assert window.output_page.summary_text.toPlainText(), "Actual results summary was not displayed"
        saved = root / "memory-project.json"
        assert window._save_project_to(saved)
        assert window._load_project_path(str(saved))
        assert [source.editor_id for source in window.project.sourceEditor.gps_sources] == ids
        assert window.project.sourceEditor.multiple_vertex
        assert len(window.project.geometryEditor.volumes) == 3
        for document in (window.project.materialEditor, window.project.geometryEditor):
            assert not document.source_path and not document.raw_source_text
        parent = root / "export"
        parent.mkdir()
        with patch.object(QFileDialog, "getExistingDirectory", return_value=str(parent)), \
             patch.object(QInputDialog, "getText", return_value=("portable", True)):
            action(app, window, lambda: window._experiment_action("export"), root, "export", receipt)
        assert not warnings, warnings
        bundle = parent / "portable"
        assert (bundle / "manifest.json").is_file()
    finally:
        close_window(app, window)
    moved = root / "offline moved bundle"
    assert bundle.resolve().is_relative_to(root.resolve()) and moved.resolve().is_relative_to(root.resolve())
    shutil.move(str(bundle), str(moved))
    # Keep all original evidence, but remove its old paths from availability.
    retired = root / "retired-runs"
    assert (root / "runs").resolve().is_relative_to(root.resolve()) and retired.resolve().is_relative_to(root.resolve())
    shutil.move(str(root / "runs"), str(retired))
    for item in receipt["actions"]:
        archived = retired / Path(item["record_path"]).relative_to(root / "runs")
        assert archived.is_file(), archived
        item["archived_record_path"] = str(archived)
    receipt["qt_output_archived"] = str(retired / output.relative_to(root / "runs"))
    assert (Path(receipt["qt_output_archived"]) / "run_summary.txt").is_file()
    saved.rename(root / "retired-project.json")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "gui") + os.pathsep + environment.get("PYTHONPATH", "")
    elsewhere = root / "offline-cwd"
    elsewhere.mkdir()
    for token in ("generate", "run"):
        command = [sys.executable, "-B", str(moved / "replay.py"), "--executable", str(executable),
                   "--runs-root", str(root / "cli-runs"), "--records", str(root / "cli-records"),
                   "--timeout", "180", token]
        process = subprocess.run(command, cwd=elsewhere, env=environment, capture_output=True, timeout=240)
        (root / f"cli-{token}.stdout.json").write_bytes(process.stdout)
        (root / f"cli-{token}.stderr.log").write_bytes(process.stderr)
        payload = json.loads(process.stdout)
        assert process.returncode == 0 and payload["ok"], (token, payload)
        terminal = payload["record"]
        assert terminal["status"] == "passed" and not terminal.get("stale"), terminal
        if token == "run":
            receipt["cli_run"] = check_run(Path(terminal["output_dir"]))
            check_physics(Path(terminal["output_dir"]), baseline_inventory)
    receipt["retired_original_runs"] = str(retired)
    receipt["offline_bundle"] = str(moved)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--allow-stale-backend", action="store_true")
    args = parser.parse_args()
    supplied = os.environ.get("G4USIM_EXE")
    assert supplied, "G4USIM_EXE is required; this integration test never skips or guesses a backend"
    executable = Path(supplied).resolve()
    assert executable.is_file(), executable
    temporary = None
    specified = args.evidence_dir or os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
    if specified:
        root = Path(specified).resolve()
        root.mkdir(parents=True, exist_ok=True)
        assert not list(root.iterdir()), "Use a fresh evidence directory; old results must be preserved"
    else:
        temporary = tempfile.TemporaryDirectory(prefix="g4usim-j2-e2e-")
        root = Path(temporary.name).resolve()
    receipt = {"scope": "Qt/K1 integration and actual CLI transport; no physical accuracy claim",
               "status": "running", "executable": str(executable), "actions": [],
               "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
               "source_fingerprint": workspace_source_fingerprint(), "diagnostic_allow_stale": args.allow_stale_backend}
    try:
        capabilities = subprocess.run([str(executable), "--capabilities"], cwd=root, capture_output=True, timeout=45)
        (root / "capabilities.stdout.json").write_bytes(capabilities.stdout)
        (root / "capabilities.stderr.log").write_bytes(capabilities.stderr)
        assert capabilities.returncode == 0
        receipt["capabilities"] = json.loads(capabilities.stdout)
        receipt["source_matches_backend"] = receipt["capabilities"].get("source_fingerprint") == receipt["source_fingerprint"]
        write_json(root / "receipt.json", receipt)
        assert args.allow_stale_backend or receipt["source_matches_backend"], "Fresh G4USIM_EXE required: backend source fingerprint differs"
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(root / "settings"))
        app = QApplication.instance() or QApplication([])
        app.setOrganizationName("G4UniversalSimSmoke")
        app.setApplicationName("J2EndToEnd")
        execute(app, executable, root, receipt)
        assert workspace_source_fingerprint() == receipt["source_fingerprint"], "C++ sources changed during evidence collection"
        assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == receipt["test_sha256"], "Test changed during evidence collection"
        receipt["status"] = "passed" if receipt["source_matches_backend"] else "diagnostic_passed_stale_backend"
        print("smoke_j2_end_to_end:", receipt["status"], flush=True)
    except BaseException as error:
        receipt.update(status="failed", failure=f"{type(error).__name__}: {error}")
        raise
    finally:
        write_json(root / "receipt.json", receipt)
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    main()
