from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.core import install_layout
from g4usim_gui.output.csv_preview import read_csv_preview
from g4usim_gui.output.file_classifier import OutputFileType, classify_files
from g4usim_gui.output.merge_plan import build_merge_plan, find_merge_histograms


def _legacy_checks() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "output"
        out.mkdir()
        (out / "hits_t0.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (out / "event_edep_t0.csv").write_text("runID,eventID,raw_edep,weighted_edep\n0,0,1,1\n", encoding="utf-8")
        (out / "event_edep_t0_r1.csv").write_text("runID,eventID,raw_edep,weighted_edep\n1,0,2,2\n", encoding="utf-8")
        (out / "hist_edep_raw_t0.csv").write_text("bin_low,bin_high,count\n0,1,2\n", encoding="utf-8")
        (out / "hist_edep_weighted_t0.csv").write_text("bin_low,bin_high,count\n0,1,2\n", encoding="utf-8")
        (out / "run_summary.txt").write_text("threads = 1\n", encoding="utf-8")

        types = {Path(info.path).name: info.file_type for info in classify_files(out)}
        assert types["hits_t0.csv"] == OutputFileType.HITS_THREAD_CSV
        assert types["event_edep_t0_r1.csv"] == OutputFileType.EVENT_EDEP_THREAD_CSV
        assert types["run_summary.txt"] == OutputFileType.RUN_SUMMARY

        preview = read_csv_preview(out / "hits_t0.csv", max_rows=1)
        assert preview.header == ["a", "b"]
        assert preview.rows == [["1", "2"]]

        plan = build_merge_plan(str(out), str(root))
        assert len(plan.tasks) == 4
        assert any(task.kind == "hits" for task in plan.tasks)
        event_task = next(task for task in plan.tasks if task.kind == "event_edep")
        assert len(event_task.matched_files) == 2
        custom = Path(tmp) / "custom backend"
        custom.mkdir()
        backend = custom / "G4UniversalSim.exe"
        backend.touch()
        (custom / "unrelated.exe").touch()
        fallback = find_merge_histograms(root)
        assert find_merge_histograms(root, str(backend)) == fallback
        sibling = custom / "mergeHistograms.exe"
        sibling.touch()
        assert find_merge_histograms(root, str(backend)) == sibling
        adjacent = build_merge_plan(str(out), str(root), backend_executable=str(backend))
        assert all(t.command_program == str(sibling) and t.available for t in adjacent.tasks if t.kind.startswith("hist"))
        explicit = Path(tmp) / "manual.exe"
        explicit.touch()
        manual = build_merge_plan(str(out), str(root), str(explicit), backend_executable=str(backend))
        assert all(t.command_program == str(explicit) for t in manual.tasks if t.kind.startswith("hist"))
        explicit.unlink()
        invalid = build_merge_plan(str(out), str(root), str(explicit), backend_executable=str(backend))
        assert all(not t.available and t.command_program == str(explicit) for t in invalid.tasks if t.kind.startswith("hist"))
        linux_backend = custom / "G4UniversalSim"
        linux_backend.touch()
        assert find_merge_histograms(root, str(linux_backend)) == fallback
        linux_merge = custom / "mergeHistograms"
        linux_merge.touch()
        assert find_merge_histograms(root, str(linux_backend)) == linux_merge

        assert plan.tasks[0].available and plan.tasks[0].provenance_status == "legacy_unverified"
        assert "Legacy/unverified" in plan.tasks[0].reason


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _files(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): _sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def _receipt(root: Path, value: dict) -> None:
    (root / "receipt.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _fixture(root: Path, *, histogram: bool = False) -> Path:
    """Synthetic F1-format data with absolute anchors at the original location."""
    original = root / "original output"
    original.mkdir(parents=True)
    identity = "a" * 32
    records = []

    def write(name, schema, text, run=None, thread=None):
        path = original / name
        if text is not None:
            path.write_bytes(text.encode("utf-8"))
        records.append(dict(path=path.as_posix(), schema=schema, execution_id=identity,
                            scope="thread" if thread is not None else "process", run_id=run, thread_id=thread,
                            sha256=_sha(path) if text is not None else None,
                            size_bytes=path.stat().st_size if text is not None else None,
                            integrity_status="hashed" if text is not None else "self_reference_excluded"))

    if histogram:
        for kind, values in (("raw", ((2, 3), (5, 7))), ("weighted", ((4, 6), (10, 14)))):
            for thread, (low, high) in enumerate(values):
                write(f"hist_edep_{kind}_t{thread}.csv", "histogram1d_csv_v3",
                      f"bin,low_edge_MeV,high_edge_MeV,center_MeV,count\n0,0,0.5,0.25,{low}\n1,0.5,1,0.75,{high}\n", 0, thread)
    else:
        hits_header = ("runID,eventID,trackID,parentID,particle,edep_MeV,ndep_MeV,stepLength_mm,"
                       "x0_mm,y0_mm,z0_mm,x1_mm,y1_mm,z1_mm,px,py,pz,kineticEnergy_MeV,process,volume,weight\n")
        for run in (0, 1):
            for thread in (0, 1):
                suffix = f"_t{thread}" + ("_r1" if run else "")
                energy = 1 + 4 * run + 2 * thread
                write(f"hits{suffix}.csv", "hits_csv_v3", hits_header +
                      f"{run},{thread},1,0,proton,{energy},0,1,0,0,0,0,0,1,0,0,1,10,ionIoni,Target,2\n", run, thread)
                write(f"event_edep{suffix}.csv", "event_edep_csv_v3",
                      f"runID,eventID,raw_edep_MeV,weighted_edep_MeV\n{run},{thread},{energy},{2 * energy}\n", run, thread)
    write("run_summary.txt", "run_summary_txt_v1", "status = completed\n")
    write("run_metadata.json", "run_metadata_json_v1", None)
    (original / "run_metadata.json").write_text(json.dumps({
        "schema": "run_metadata_json_v1",
        "runs": [{"run_id": n, "completed_events": 2} for n in range(1 if histogram else 2)],
        "generated_files": records,
        "provenance": {
            "schema": "g4usim_provenance_v1", "execution_id": identity,
            "build": {"git_commit": "b" * 40, "git_source_state": "clean", "source_fingerprint": "c" * 64,
                      "compiler_id": "synthetic", "compiler_version": "1", "configuration": "fixture",
                      "geant4_version": "synthetic"},
            "input_coverage": "project_readers_observed", "input_observation": "bytes_read_not_semantic_acceptance",
            "input_exclusions": ["geant4_internal_datasets", "unobserved_native_command_inputs"],
            "inputs": [{"sequence": 1, "path": "synthetic.ini", "kind": "ini", "role": "main",
                        "capture_method": "bytes", "status": "recorded",
                        "sha256": "d" * 64, "size_bytes": 12, "reason": ""}],
        },
    }, indent=2) + "\n", encoding="utf-8")
    copied = root / "copied package" / "output"
    shutil.copytree(original, copied)
    assert _files(copied) == _files(original)
    return copied


def _qt_run(runner, launch) -> dict:
    """Observe the existing QProcess; do not substitute a process or infer PID from a UI message."""
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance()
    process = runner._process
    tasks, started, finished, errors, done, dialogs = [], [], [], [], [], []
    runner.taskStarted.connect(tasks.append)
    runner.errorOccurred.connect(errors.append)
    runner.allFinished.connect(lambda: done.append(True))
    process.started.connect(lambda: started.append({
        "pid": process.processId(), "program": process.program(), "arguments": process.arguments(),
        "working_directory_setting": process.workingDirectory(), "gui_cwd": os.getcwd(),
        "started_unix": time.time(),
    }))
    process.finished.connect(lambda code, status: finished.append({
        "exit_code": code, "exit_status": status.name, "finished_unix": time.time(),
    }))
    # Suppress only modal presentation, preserving actual runner errors and Qt signals.
    with patch.object(QMessageBox, "warning", side_effect=lambda _, title, msg: dialogs.append([title, msg])):
        launch()
        deadline = time.monotonic() + 20
        while not (done or errors) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        if not done and process.state() != process.ProcessState.NotRunning:
            runner.kill()
            process.waitForFinished(3000)
            app.processEvents()
    return dict(task_started=tasks, started=started, finished=finished, errors=errors, dialogs=dialogs,
                queue_finished=bool(done), status="started" if started else "not_started")


def _csv(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.reader(stream))


def _check_process(task, actual, end, code=0):
    assert actual["pid"] > 0 and actual["program"] == task.command_program
    assert actual["arguments"] == task.command_args
    assert actual["working_directory_setting"] == "" and actual["gui_cwd"] == os.getcwd()
    assert end["exit_code"] == code and end["exit_status"] == "NormalExit", end


def _source_cases(root: Path) -> None:
    from async_wait import wait_for_idle
    from g4usim_gui.widgets.output_page import OutputPage

    app_root = install_layout.application_root()
    tools = [app_root / "scripts" / name for name in ("merge_outputs.py", "output_publication.py")]
    helper = Path(install_layout.script_python()).resolve()
    tool_before = {str(p): _sha(p) for p in [*tools, helper]}
    for name in ("copied_registered", "existing_after_plan", "provenance_changed_after_plan"):
        case = root / name
        out = _fixture(case)
        original = case / "original output"
        workspace = case / "user project"
        workspace.mkdir()
        for stem in ("hits", "event_edep"):
            (out / f"{stem}_t9.csv").write_bytes(b"unregistered,decoy\n99,99\n")
        initial = _files(out)
        original_before = _files(original)
        page = OutputPage()
        page.set_workspace_root(str(workspace))
        page.set_package_dir(str(out.parent), str(out))
        wait_for_idle(page)
        plan = page._merge_plan
        py_tasks = [t for t in plan.tasks if t.tool_type == "python_script"]
        logs = out.parent / "logs"
        info = dict(case_id=name, level="source_synthetic_f1", platform=sys.platform,
                    app_root=str(app_root), workspace=str(workspace), output=str(out),
                    original_output=str(original), log_directory=str(logs),
                    plan=[asdict(t) for t in plan.tasks], input_sha256=initial,
                    original_sha256=original_before, tool_sha256_before=tool_before,
                    process={"status": "not_started"})
        _receipt(case, info)  # Keep the unavailable plan if this is a regression.
        assert len(py_tasks) == 2 and all(t.available for t in py_tasks), info["plan"]
        for task in py_tasks:
            prefix = "hits" if task.kind == "hits" else "event_edep"
            expected = sorted(str(out / f"{prefix}_t{n}{suffix}.csv") for n in (0, 1) for suffix in ("", "_r1"))
            assert task.matched_files == expected and task.provenance_status == "verified"
            assert task.manifest_digest == initial["run_metadata.json"] and task.automatic_inputs
            assert task.command_program == install_layout.script_python()
            assert task.command_args == [str(tools[0]), "--output", task.output_file, *expected]
            assert Path(task.output_file).parent == out
        if name == "copied_registered":
            assert not (workspace / "scripts").exists() and not (out.parent / "scripts").exists()
            info["process"] = _qt_run(page._merge_runner, page.run_all_merge_button.click)
            _receipt(case, info)
            output_rows = {}
            for task in py_tasks:
                header, *rows = _csv(Path(task.output_file))
                input_rows = [row for path in task.matched_files for row in _csv(Path(path))[1:]]
                assert header == _csv(Path(task.matched_files[0]))[0] and rows == input_rows
                assert [(row[0], row[1]) for row in rows] == [("0", "0"), ("1", "0"), ("0", "1"), ("1", "1")]
                columns = ["edep_MeV"] if task.kind == "hits" else ["raw_edep_MeV", "weighted_edep_MeV"]
                totals = {k: sum(Decimal(row[header.index(k)]) for row in rows) for k in columns}
                assert list(totals.values()) == ([16] if task.kind == "hits" else [16, 32])
                output_rows[task.kind] = {"header": header, "rows": rows,
                                          "column_sums": {k: str(v) for k, v in totals.items()}}
            info["csv"] = output_rows
            expected_new = {Path(t.output_file).name for t in py_tasks}
            exit_codes = [0, 0]
        else:
            target = Path(py_tasks[0].output_file)
            if name == "existing_after_plan":
                target.write_bytes(b"sentinel: must not be overwritten\n")
                initial = {**initial, target.name: _sha(target)}
            else:
                manifest = out / "run_metadata.json"
                manifest.write_bytes(manifest.read_bytes() + b"\n")  # Valid F1, different digest.
                initial = {**initial, manifest.name: _sha(manifest)}
            info["pre_start_sha256"] = initial
            page.merge_table.selectRow(0)
            info["process"] = _qt_run(page._merge_runner, page.run_selected_merge_button.click)
            _receipt(case, info)
            expected_new = set()
            if name == "existing_after_plan":
                exit_codes = [1]
                assert "Output file already exists" in (logs / "merge_hits_stderr.log").read_text(encoding="utf-8")
            else:
                exit_codes = []
                assert info["process"]["errors"] and "provenance changed" in info["process"]["errors"][0]
        process = info["process"]
        _receipt(case, info)
        assert process["queue_finished"]
        assert process["task_started"] == [t.name for t in py_tasks[:len(exit_codes)]]
        assert len(process["started"]) == len(process["finished"]) == len(exit_codes), process
        for task, actual, end, code in zip(py_tasks, process["started"], process["finished"], exit_codes):
            _check_process(task, actual, end, code)
        after = _files(out)
        assert {k: after[k] for k in initial} == initial
        assert after.keys() - initial.keys() == expected_new
        assert _files(original) == original_before
        assert not (workspace / "scripts").exists() and not (out.parent / "scripts").exists()
        info["tool_sha256_after"] = {str(p): _sha(p) for p in [*tools, helper]}
        assert info["tool_sha256_after"] == tool_before
        info["output_sha256"] = after
        info["log_sha256"] = _files(logs)
        assert set(info["log_sha256"]) == {f"{t.log_prefix}_{stream}.log"
                                           for t in py_tasks[:len(exit_codes)] for stream in ("stdout", "stderr")}
        _receipt(case, info)
        wait_for_idle(page)
        page.close()
        page.deleteLater()


def _availability_cases(root: Path) -> None:
    case = root / "availability"
    out = _fixture(case)
    workspace = case / "user project"
    (workspace / "scripts").mkdir(parents=True)
    decoy = workspace / "scripts" / "merge_outputs.py"
    decoy.write_text("raise AssertionError('workspace decoy must not run')\n", encoding="utf-8")
    missing = case / "application without scripts" / "scripts"
    hist = case / "placeholder histogram tool"
    hist.touch()  # Path selection only; the real binary uses --hist-executable.
    hist_out = _fixture(case / "hist path selection", histogram=True)
    with patch.object(install_layout, "scripts_dir", return_value=missing):
        no_script = build_merge_plan(str(out), str(workspace))
    assert all(not t.available and t.command_args[0] == str(missing / decoy.name)
               and "Python merge script not found" in t.reason for t in no_script.tasks[:2])
    with patch.object(install_layout, "script_python", return_value=None):
        no_python = build_merge_plan(str(out), str(workspace))
        hist_only = build_merge_plan(str(hist_out), str(workspace), str(hist))
    assert all(not t.available and not t.command_program and "Python 3 is needed" in t.reason for t in no_python.tasks[:2])
    assert all(t.available and t.command_program == str(hist) for t in hist_only.tasks[2:])
    sentinel = out / "hits_merged.csv"
    sentinel.write_bytes(b"existing target\n")
    before = _sha(sentinel)
    existing = build_merge_plan(str(out), str(workspace))
    assert not existing.tasks[0].available and "Output file already exists" in existing.tasks[0].reason
    assert _sha(sentinel) == before and existing.tasks[1].available

    # A relative output remains relative to the GUI cwd, while histogram discovery
    # still uses the user workspace and the Python script uses the application.
    preferred = workspace / "bin" / "mergeHistograms.exe"
    older = workspace / "build" / "Release" / preferred.name
    for path in (preferred, older):
        path.parent.mkdir(parents=True)
        path.touch()  # Discovery only.
    cwd = Path.cwd()
    try:
        os.chdir(case)
        rel_out = out.relative_to(case)
        rel_workspace = workspace.relative_to(case)
        relative = build_merge_plan(str(rel_out), str(rel_workspace))
        event = relative.tasks[1]
        assert event.available and event.input_dir == str(rel_out)
        assert event.output_file == event.command_args[2] == str(rel_out / "event_edep_merged.csv")
        assert Path(event.command_args[0]) == install_layout.scripts_dir() / decoy.name
        assert all(t.command_program == str(preferred.relative_to(case)) for t in relative.tasks[2:])
    finally:
        os.chdir(cwd)
    _receipt(case, dict(level="source_with_layout_mocks_no_process", status="not_started",
                        workspace_decoy_sha256=_sha(decoy), sentinel_sha256=before,
                        missing_script=[asdict(t) for t in no_script.tasks],
                        missing_python=[asdict(t) for t in no_python.tasks],
                        existing=[asdict(t) for t in existing.tasks],
                        relative_plan=[asdict(t) for t in relative.tasks],
                        hist_path_only=[asdict(t) for t in hist_only.tasks]))


def _hist_case(root: Path, executable: Path) -> None:
    from g4usim_gui.output.merge_runner import MergeRunner

    out = _fixture(root, histogram=True)
    workspace = root / "user project"
    workspace.mkdir()
    before = _files(out)
    sha = _sha(executable)
    with patch.object(install_layout, "scripts_dir", return_value=root / "missing scripts"), \
            patch.object(install_layout, "script_python", return_value=None):
        plan = build_merge_plan(str(out), str(workspace), str(executable))
    assert [t.kind for t in plan.tasks if t.available] == ["hist_raw", "hist_weighted"]
    selected = plan.tasks[2:]
    logs = out.parent / "logs"
    runner = MergeRunner()
    process = _qt_run(runner, lambda: runner.run_tasks(selected, logs))
    info = dict(case_id="explicit_native_hist", level="source_synthetic_f1_with_layout_mocks",
                platform=sys.platform, workspace=str(workspace), output=str(out), log_directory=str(logs),
                executable=str(executable), executable_sha256=sha, input_sha256=before,
                plan=[asdict(t) for t in plan.tasks], process=process, log_sha256=_files(logs))
    _receipt(root, info)
    assert process["queue_finished"] and len(process["started"]) == len(process["finished"]) == 2
    results = {}
    for t, actual, end, counts in zip(selected, process["started"], process["finished"], ([7, 10], [14, 20])):
        assert t.command_program == str(executable) and t.provenance_status == "verified"
        _check_process(t, actual, end)
        path = Path(t.output_file)
        results[t.kind] = _csv(path)
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert [(float(row["bin_low_MeV"]), float(row["bin_high_MeV"]), float(row["sum"]))
                for row in rows] == [(0, .5, counts[0]), (.5, 1, counts[1])]
    after = _files(out)
    assert {k: after[k] for k in before} == before and _sha(executable) == sha
    assert after.keys() - before.keys() == {Path(t.output_file).name for t in selected}
    _receipt(root, {**info, "output_sha256": after, "csv": results})


def main() -> int:
    parser = argparse.ArgumentParser(description="Output merge smoke with optional real histogram tool.")
    parser.add_argument("--hist-executable", type=Path, help="Separate explicit native histogram execution only")
    args = parser.parse_args()
    executable = args.hist_executable.resolve() if args.hist_executable else None
    if executable is not None and not executable.is_file():
        parser.error("--hist-executable must name an existing native tool")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    evidence = os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
    if evidence:
        Path(evidence).mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="merge evidence ", dir=evidence)).resolve()
        print(f"merge evidence: {root}", flush=True)
        _run(root, executable)
    else:
        with tempfile.TemporaryDirectory(prefix="merge evidence ") as temp:
            _run(Path(temp).resolve(), executable)
    app.processEvents()
    print("smoke_output_tools: ok")
    return 0


def _run(root: Path, executable: Path | None) -> None:
    if executable is not None:
        _hist_case(root / "native histogram", executable)
        return
    _legacy_checks()
    _source_cases(root)
    _availability_cases(root)


if __name__ == "__main__":
    raise SystemExit(main())
