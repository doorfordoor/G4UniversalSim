"""AUD03: bounded ownership smoke with real Python QProcesses, never Geant4.

Run directly with --output-dir. Only command construction is replaced; normal
project validation, launch planning, signals, scan scheduling and cleanup run.
FailedToStart alone supplies a missing-program launch plan to the real QProcess.
The report retains PID samples, rejection snapshots, callback failures and hashes.
It is lifecycle evidence, not simulation, protocol or physics acceptance.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import nullcontext
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from unittest.mock import patch

sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
GUI = Path(__file__).resolve().parents[1]
ROOT = GUI.parent
sys.path.insert(0, str(GUI))

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import QEventLoop, QProcess, QTimer
from PySide6.QtWidgets import QApplication

from g4usim_gui.core import runner as runner_module
from g4usim_gui.core.backend_run_ownership import BackendRunOwnership
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.core.scan import ScanManifest, ScanPoint
from g4usim_gui.core.scan_runner import ScanRunner
from g4usim_gui.core.session_client import SessionClient
from g4usim_gui.widgets.scan_page import ScanPage
from g4usim_gui.window.session import SessionMixin


# An OS lock is released even by terminate/kill. It supplements finite parent
# sampling: two children overlapping between samples leave an overlap record.
CHILD = r'''
import json, os, pathlib, sys, time, uuid
root, delay = pathlib.Path(sys.argv[1]), float(sys.argv[2])
record = root / (str(os.getpid()) + '-' + uuid.uuid4().hex + '.json')
data = {'pid': os.getpid(), 'started_ns': time.monotonic_ns(), 'overlap': False}
record.write_text(json.dumps(data), encoding='utf-8')
lock = (root / 'exclusive.lock').open('r+b')
try:
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    data['overlap'] = True
    record.write_text(json.dumps(data), encoding='utf-8')
    sys.exit(95)
print('OWNERSHIP_CHILD_PID=' + str(os.getpid()), flush=True)
print('[G4USimProgress] ' + json.dumps(dict(schema='g4usim_progress_v1',
    run_id=0, phase='begin', sequence=0, planned_events=1, completed_events=0,
    elapsed_s=0.0, rate_eps=None, eta_s=None)), flush=True)
time.sleep(delay)
data['ended_ns'] = time.monotonic_ns()
record.write_text(json.dumps(data), encoding='utf-8')
lock.close()
'''


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            # Access denied is uncertainty, not evidence of process exit.
            assert ctypes.get_last_error() == 87, (pid, ctypes.get_last_error())
            return False
        try:
            result = kernel.WaitForSingleObject(handle, 0)
            assert result in (0, 258), (pid, result)
            return result == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class Harness:
    def __init__(self, app: QApplication, root: Path, report: dict):
        self.app, self.root, self.report = app, root, report
        self.runners: list[G4USimRunner] = []
        self.scans: list[ScanRunner] = []
        self.pages: list[ScanPage] = []
        self.pids: set[int] = set()
        self.errors: list[str] = []
        self.case = ""
        self.counter = 0
        self.children = root / "children"
        self.children.mkdir()
        (self.children / "exclusive.lock").write_bytes(b"0")
        self.script = root / "controlled_child.py"
        self.script.write_text(CHILD, encoding="utf-8", newline="\n")
        self.timer = QTimer()
        self.timer.setInterval(5)
        self.timer.timeout.connect(self.guard(lambda: self.sample("timer")))
        self.timer.start()

    def guard(self, callback):
        # Python exceptions from Qt slots otherwise print and can yield a false PASS.
        def guarded(*args):
            try:
                return callback(*args)
            except Exception:
                self.errors.append(traceback.format_exc())
        return guarded

    def watch(self, runner: G4USimRunner):
        assert isinstance(runner._process, QProcess)
        self.runners.append(runner)
        runner.processStarted.connect(self.guard(lambda: self.sample("processStarted")))
        return runner

    def runner(self, owner=None):
        return self.watch(G4USimRunner(ownership=owner))

    def scan(self, owner=None):
        scan = ScanRunner(ownership=owner)
        self.scans.append(scan)
        self.watch(scan._runner)
        assert scan._runner._ownership is scan._ownership
        return scan

    def sample(self, where: str):
        states = []
        for number, runner in enumerate(self.runners):
            pid = int(runner._process.processId())
            if pid:
                self.pids.add(pid)
            states.append({"runner": number, "pid": pid,
                           "state": runner._process.state().name})
        live = sorted(pid for pid in self.pids if pid_alive(pid))
        row = {"case": self.case, "where": where, "ns": time.monotonic_ns(),
               "live_pids": live, "processes": [s for s in states if s["pid"]]}
        self.report["pid_samples"].append(row)
        assert len(live) <= 1, row
        return row

    def until(self, predicate, label: str, timeout=5.0):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents(QEventLoop.AllEvents, 5)
            self.sample("wait:" + label)
            time.sleep(0.002)
        assert predicate(), "timeout: " + label
        assert not self.errors, "Qt callback failures: " + "\n".join(self.errors)

    def project(self, *, valid=True):
        self.counter += 1
        directory = self.root / f"fixture-{self.counter:03d}"
        directory.mkdir()
        ini, macro = directory / "main.ini", directory / "run.mac"
        ini.write_text("[run]\ninteractive = false\n", encoding="utf-8")
        macro.write_text("# lifecycle-only fixture; never sent to Geant4\n", encoding="utf-8")
        return G4USimProject(projectName="AUD03", runInputMode="generated",
                            executable=sys.executable, workspaceRoot=str(directory),
                            configPath=str(ini), macroPath=str(macro),
                            outputDir=str(directory / "output"), threads=1 if valid else 0)

    def manifest(self, count=2, *, valid=True):
        projects = [self.project(valid=valid) for _ in range(count)]
        points = [ScanPoint(index=i, value=str(i), package_dir=p.workspaceRoot,
                            output_dir=p.outputDir, main_ini=p.configPath, macro=p.macroPath,
                            seed=i + 10) for i, p in enumerate(projects)]
        if not valid:
            for point in points:
                point.main_ini += ".missing"
        return ScanManifest(name="AUD03", parameter="run.seed", parameter_label="seed",
                            values=[p.value for p in points], scan_dir=projects[0].workspaceRoot,
                            created="lifecycle-fixture", points=points)

    def command(self, project):
        return [sys.executable, "-u", str(self.script), str(self.children), "0.18"]

    def reject(self, label, operation, owner):
        before = self.sample("before-reject:" + label)
        assert owner.busy, label
        result = operation()
        after = self.sample("after-reject:" + label)
        self.report["rejections"].append({"case": self.case, "label": label,
                                          "returned": result, "before": before, "after": after})
        assert result is False, (label, result)
        assert owner.busy, "rejected operation released current owner: " + label
        assert before["processes"] == after["processes"], label

    def settled(self, owner):
        self.until(lambda: not owner.busy, "ownership release")
        self.sample("released")
        assert not any(r.is_running() for r in self.runners)

    def recovery(self, runner, project):
        assert runner.start(project) is True
        self.until(lambda: bool(runner._process.processId()), "recovery PID")
        self.settled(runner._ownership)

    def failed_launch(self):
        def plan(command, cwd):
            launch = self.real_prepare(command, cwd)
            return replace(launch, program=str(self.root / "no-such-program.exe"))
        return patch.object(runner_module, "prepare_backend_launch", side_effect=plan)

    def cleanup(self):
        self.timer.stop()
        for scan in self.scans:
            scan.stop()
        for runner in self.runners:
            if runner.is_running():
                runner.kill()
                runner._process.waitForFinished(1500)
        for _ in range(5):
            self.app.processEvents(QEventLoop.AllEvents, 5)
        for page in self.pages:
            page.close()


def owner_model(h: Harness):
    owner, other = BackendRunOwnership(), BackendRunOwnership()
    assert owner.busy is False
    assert owner.claim(None) is None
    assert owner.release(None) is False
    assert owner.release_claim(None, None) is False
    lease = owner.acquire()
    assert lease is not None and owner.busy is True
    assert owner.acquire() is None
    assert owner.claim(object()) is None
    claim = owner.claim(lease)
    assert claim is not None
    assert owner.claim(lease) is None
    assert owner.release(lease) is False
    assert other.release(lease) is False
    assert other.claim(lease) is None
    assert owner.release_claim(lease, object()) is False
    assert owner.release_claim(object(), claim) is False
    assert owner.release_claim(lease, claim) is True
    assert owner.busy is True  # scan gap reservation
    next_claim = owner.claim(lease)
    assert next_claim is not None and next_claim is not claim
    assert owner.release_claim(lease, claim) is False
    assert owner.release_claim(lease, next_claim) is True
    assert owner.release(lease) is True
    newer = owner.acquire()
    assert newer is not None and newer is not lease
    assert owner.release(lease) is False
    assert owner.release_claim(lease, claim) is False
    assert owner.busy is True
    assert owner.release(newer) is True


def cached_page_orders(h: Harness):
    owner = BackendRunOwnership()
    runner = h.runner(owner)
    page = ScanPage(ownership=owner)
    h.pages.append(page)
    h.scans.append(page.runner)
    h.watch(page.runner._runner)
    assert page.runner._ownership is owner
    calls = []
    def provider():
        calls.append("called")
        raise AssertionError("cached executable must bypass provider")
    page.set_base_provider(provider)
    page._executable, page._workspace = sys.executable, str(h.root)
    for mode in ("start", "start_session"):
        manifest = h.manifest()
        page.load_scan(manifest)
        project = h.project()
        assert getattr(runner, mode)(project) is True
        h.until(lambda: bool(runner._process.processId()), mode + " PID")
        h.reject(mode + " -> cached ScanPage", lambda: page.run_scan(all_points=True), owner)
        h.settled(owner)
        assert page.run_scan(all_points=True) is True
        h.until(lambda: bool(page.runner._runner._process.processId()), "scan PID")
        h.reject("scan -> " + mode, lambda: getattr(runner, mode)(project), owner)
        h.settled(owner)
        h.recovery(runner, h.project())
    assert calls == []


def scan_reentry(h: Harness):
    owner = BackendRunOwnership()
    # Observe the real queued advance at its entry. Two overdue Qt timers have
    # unspecified ordering, so an independent timer cannot assert it wins a race.
    class ObservedScan(ScanRunner):
        gap_probe = None
        def _next(self):
            if (self.gap_probe is not None and self._current is None
                    and self._runner._run_claim is None and self.is_running()):
                probe, self.gap_probe = self.gap_probe, None
                probe()
            super()._next()
    scan = ObservedScan(ownership=owner)
    h.scans.append(scan)
    h.watch(scan._runner)
    rival, runner = h.scan(owner), h.runner(owner)
    manifest, other_manifest, project = h.manifest(3), h.manifest(1), h.project()
    started, finished, gaps = [], [], []
    def compete(label):
        h.reject(label + ":run", lambda: runner.start(project), owner)
        h.reject(label + ":session", lambda: runner.start_session(project), owner)
        h.reject(label + ":scan", lambda: rival.start(other_manifest, sys.executable,
                                                     str(h.root), [0]), owner)
    scan.pointStarted.connect(h.guard(lambda index: (started.append(index), compete("pointStarted"))))
    def point_done(index, state):
        finished.append((index, state))
        compete("pointFinished")
        before = list(started)
        # Force a queued continuation onto the stack while terminal claim lives.
        scan._schedule_next()
        deadline = time.monotonic() + .004
        while time.monotonic() < deadline:
            h.app.processEvents(QEventLoop.AllEvents, 1)
        assert started == before, "nested event loop advanced before terminal cleanup"
        assert scan.is_running() and owner.busy
        def gap():
            assert scan._current is None
            assert scan.is_running() and owner.busy
            assert scan._runner._run_claim is None
            gaps.append(index)
            compete("gap-timer")
        scan.gap_probe = h.guard(gap)
    scan.pointFinished.connect(h.guard(point_done))
    assert scan.start(manifest, sys.executable, str(h.root), [0, 1, 2]) is True
    h.settled(owner)
    assert started == [0, 1, 2]
    assert [index for index, _ in finished] == [0, 1, 2]
    assert gaps == [0, 1, 2]
    # No synthetic Geant4 summary: ordinary children must not claim run success.
    assert all(state != "success" for _, state in finished)
    h.recovery(runner, h.project())


def runner_reentry(h: Harness):
    for mode in ("start", "start_session"):
        owner = BackendRunOwnership()
        runner, rival, scan = h.runner(owner), h.runner(owner), h.scan(owner)
        project, rejected_project, manifest = h.project(), h.project(), h.manifest(1)
        hits = []
        def compete(label):
            hits.append(label)
            h.reject(label + ":same", lambda: getattr(runner, mode)(rejected_project), owner)
            h.reject(label + ":other", lambda: rival.start(rejected_project), owner)
            h.reject(label + ":scan", lambda: scan.start(manifest, sys.executable,
                                                        str(h.root), [0]), owner)
        runner.progressStateChanged.connect(h.guard(lambda state: compete("state:" + state)))
        runner.stateChanged.connect(h.guard(lambda state: compete("qprocess-starting")
                                             if state == "Starting" else None))
        runner.progressReceived.connect(h.guard(lambda _: compete("progress")))
        runner.sessionData.connect(h.guard(lambda *_: compete("sessionData")))
        runner.finished.connect(h.guard(lambda _: compete("finished")))
        assert getattr(runner, mode)(project) is True
        h.settled(owner)
        assert "state:starting" in hits and "finished" in hits and "qprocess-starting" in hits
        assert ("progress" if mode == "start" else "sessionData") in hits
        assert not Path(rejected_project.outputDir).exists()


def rejection_and_failures(h: Harness):
    for mode in ("start", "start_session"):
        for failure in ("validation", "FailedToStart"):
            owner = BackendRunOwnership()
            runner, rival = h.runner(owner), h.runner(owner)
            project, good = h.project(valid=failure != "validation"), h.project()
            errors, start_failed, pids = [], [], []
            runner.errorOccurred.connect(errors.append)
            runner.sessionStartFailed.connect(lambda: start_failed.append(True))
            runner.processStarted.connect(lambda: pids.append(True))
            # Every error signal retries unconditionally. Admission must be guarded
            # against recursive error emissions, including same-runner retries.
            runner.errorOccurred.connect(h.guard(lambda _: h.reject(
                "error-retry-self", lambda: getattr(runner, mode)(good), owner)))
            runner.errorOccurred.connect(h.guard(lambda _: h.reject(
                "error-retry-other", lambda: rival.start(good), owner)))
            with h.failed_launch() if failure == "FailedToStart" else nullcontext():
                accepted = getattr(runner, mode)(project)
                assert accepted is (failure == "FailedToStart")
                h.settled(owner)
            assert errors and pids == []
            assert bool(start_failed) is (mode == "start_session")
            assert runner._stdout_file is None and runner._stderr_file is None
            # Disconnect retry slots before recovery (normal completion is unrelated).
            runner.errorOccurred.disconnect()
            h.recovery(runner, good)


def scan_failures_and_cancel(h: Harness):
    for kind in ("validation", "FailedToStart", "cancel-active", "cancel-starting", "cancel-gap"):
        owner = BackendRunOwnership()
        scan, runner = h.scan(owner), h.runner(owner)
        manifest = h.manifest(2, valid=kind != "validation")
        done, started, terminal = [], [], []
        scan.pointFinished.connect(lambda index, state: done.append((index, state)))
        scan.pointStarted.connect(started.append)
        scan.allFinished.connect(lambda: terminal.append(True))
        if kind == "cancel-starting":
            scan._runner.progressStateChanged.connect(h.guard(
                lambda state: scan.stop() if state == "starting" else None))
        if kind == "cancel-gap":
            scan.pointFinished.connect(h.guard(lambda *_: scan.stop()))
        with h.failed_launch() if kind == "FailedToStart" else nullcontext():
            assert scan.start(manifest, sys.executable, str(h.root), [0, 1]) is True
            if kind == "cancel-active":
                h.until(lambda: bool(scan._runner._process.processId()), "cancel active PID")
                scan.stop()
            h.settled(owner)
        assert terminal == [True], (kind, terminal)
        assert [i for i, _ in done] == ([0, 1] if kind in ("validation", "FailedToStart") else [0])
        assert started == [i for i, _ in done]
        if kind in ("validation", "FailedToStart"):
            assert all(state == "failed" for _, state in done)
        assert scan._runner._run_claim is None
        h.recovery(runner, h.project())


def stale_claims(h: Harness):
    owner = BackendRunOwnership()
    runner = h.runner(owner)
    assert runner.start(h.project()) is True
    old_lease, old_claim = runner._ownership_lease, runner._run_claim
    old_done, old_error = runner._completion_slots
    h.settled(owner)
    for mode in ("start", "start_session"):
        assert getattr(runner, mode)(h.project()) is True
        h.until(lambda: bool(runner._process.processId()), "new claim PID")
        lease, claim = runner._ownership_lease, runner._run_claim
        before = h.sample("before stale dispatch")
        result, status, launch = runner.last_result, dict(runner._status_data), runner.last_launch
        runner._dispatch_finished(old_claim, 0, QProcess.NormalExit)
        runner._dispatch_error(old_claim, QProcess.FailedToStart)
        old_done(0, QProcess.NormalExit)
        old_error(QProcess.FailedToStart)
        assert owner.release(old_lease) is False
        assert owner.release_claim(old_lease, old_claim) is False
        assert owner.busy and runner._ownership_lease is lease and runner._run_claim is claim
        assert runner.last_result is result and runner.last_launch is launch
        assert runner._status_data == status
        assert h.sample("after stale dispatch")["processes"] == before["processes"]
        h.settled(owner)


def session_admission(h: Harness):
    owner = BackendRunOwnership()
    runner, rival, scan = h.runner(owner), h.runner(owner), h.scan(owner)
    project, manifest = h.project(), h.manifest(1)
    with runner.session_start_admission() as allowed:
        assert allowed is True and owner.busy
        h.reject("pre-session-run", lambda: rival.start(project), owner)
        h.reject("pre-session-scan", lambda: scan.start(manifest, sys.executable,
                                                       str(h.root), [0]), owner)
        with runner.session_start_admission() as nested:
            assert nested is False
        assert runner.start_session(project) is True
    assert owner.busy
    h.settled(owner)
    with runner.session_start_admission() as allowed:
        assert allowed is True
    assert not owner.busy
    try:
        with runner.session_start_admission() as allowed:
            assert allowed is True
            raise ValueError("controlled abandoned scope")
    except ValueError:
        pass
    assert not owner.busy
    h.recovery(rival, h.project())


def session_client_failures(h: Harness):
    class Panel:
        def set_session_active(self, active):
            self.active = active
        def set_message(self, *args):
            pass
    class WindowHarness(SessionMixin):
        def _set_session_owner_controls(self, active):
            self.controls_active = active
    for replay in (False, True):
        for failure in ("validation", "launch-exception", "FailedToStart"):
            owner = BackendRunOwnership()
            runner, rival, scan = h.runner(owner), h.runner(owner), h.scan(owner)
            client = SessionClient(runner)
            host = WindowHarness()
            host.runner, host.session_client, host.session_panel = runner, client, Panel()
            host.project = h.project(valid=failure != "validation")
            runner.sessionStartFailed.connect(host._session_start_failed)
            good, manifest, starting = h.project(), h.manifest(1), []
            def prestart(view):
                # Error messages can republish the same starting view. Probe
                # the first pre-start emission, rather than counting messages.
                if view["phase"] != "starting" or starting:
                    return
                starting.append(True)
                h.reject("client-prestart-run", lambda: rival.start(good), owner)
                h.reject("client-prestart-scan", lambda: scan.start(manifest, sys.executable,
                                                                  str(h.root), [0]), owner)
                h.app.processEvents(QEventLoop.AllEvents, 2)
            client.stateChanged.connect(h.guard(prestart))
            context = (h.failed_launch() if failure == "FailedToStart" else
                       patch.object(runner_module, "prepare_backend_launch", side_effect=RuntimeError("AUD03 launch"))
                       if failure == "launch-exception" else nullcontext())
            with context:
                host._launch_session_client(h.command(host.project), replay=replay)
                h.settled(owner)
            assert starting == [True]
            assert client._started is False and not client.is_active()
            assert not client._handshake_timer.isActive()
            assert client._request_timers == {} and client._pending == {}
            assert client.snapshot()["phase"] == "failed"
            h.report.setdefault("session_client_subcases", []).append(
                {"replay": replay, "failure": failure, "handshake_timer_active": False,
                 "pending_requests": len(client._pending), "phase": client.snapshot()["phase"]})
            h.recovery(rival, good)


def standalone_and_wiring(h: Harness):
    runner, scan = h.runner(), h.scan()
    assert runner._ownership is not scan._ownership
    assert runner.start(h.project()) is True
    h.settled(runner._ownership)
    manifest = h.manifest(1)
    assert scan.start(manifest, sys.executable, str(h.root), [0]) is True
    h.settled(scan._ownership)
    # Static MainWindow injection check keeps this smoke bounded and avoids
    # creating persistence/recovery/3D machinery unrelated to run admission.
    tree = ast.parse((GUI / "g4usim_gui/main_window.py").read_text(encoding="utf-8-sig"))
    assignments = {ast.unparse(node.targets[0]): node.value for node in ast.walk(tree)
                   if isinstance(node, ast.Assign) and len(node.targets) == 1}
    assert ast.unparse(assignments["self._backend_run_ownership"]) == "BackendRunOwnership()"
    for name in ("self.runner", "self.scan_page"):
        call = assignments[name]
        assert isinstance(call, ast.Call)
        assert any(k.arg == "ownership" and ast.unparse(k.value) == "self._backend_run_ownership"
                   for k in call.keywords)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    evidence_root = os.environ.get("G4USIM_TEST_EVIDENCE_DIR")
    output = (args.output_dir or (Path(evidence_root) / "run-ownership" if evidence_root else
                                 Path(tempfile.mkdtemp(prefix="g4usim-run-ownership-")))).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema": "aud03_run_ownership_smoke_v1", "status": "running",
              "python": sys.version, "executable": sys.executable, "pyside": PYSIDE_VERSION,
              "scope": "real QProcess Python children; no Geant4/build/registry changes",
              "limitations": ["finite Qt-thread lifecycle smoke, not thread/process-global admission",
                              "MainWindow injection is AST checked; no full window or native visual QA",
                              "no Geant4 physics, successful simulation summaries or full session protocol"],
              "cases": [], "pid_samples": [], "rejections": [], "source_sha256_before": {}}
    sources = [Path(__file__), GUI / "g4usim_gui/core/backend_run_ownership.py",
               GUI / "g4usim_gui/core/runner.py", GUI / "g4usim_gui/core/scan_runner.py",
               GUI / "g4usim_gui/core/scan.py", GUI / "g4usim_gui/widgets/scan_page.py",
               GUI / "g4usim_gui/main_window.py", GUI / "g4usim_gui/window/session.py",
               GUI / "g4usim_gui/core/session_client.py"]
    report["source_sha256_before"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in sources}
    app = QApplication.instance() or QApplication([])
    harness = None
    try:
        fixture_root = tempfile.mkdtemp(prefix="fixtures-", dir=output)
        report["fixture_root"] = fixture_root
        with nullcontext(fixture_root) as temporary:
            harness = Harness(app, Path(temporary), report)
            harness.real_prepare = runner_module.prepare_backend_launch
            with patch.object(G4USimRunner, "build_command", side_effect=harness.command):
                for case in (owner_model, cached_page_orders, scan_reentry, runner_reentry,
                             rejection_and_failures, scan_failures_and_cancel, stale_claims,
                             session_admission, session_client_failures, standalone_and_wiring):
                    harness.case = case.__name__
                    entry = {"name": harness.case, "status": "running"}
                    report["cases"].append(entry)
                    try:
                        case(harness)
                        entry["status"] = "passed"
                    except Exception:
                        entry.update(status="failed", traceback=traceback.format_exc())
                        print("FAIL", harness.case, entry["traceback"], flush=True)
                        break
                    finally:
                        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                    print("PASS", harness.case, flush=True)
            harness.cleanup()
            report["callback_errors"] = harness.errors
            report["children"] = [json.loads(p.read_text(encoding="utf-8"))
                                  for p in harness.children.glob("*.json")]
            assert not harness.errors, harness.errors
            assert not any(child["overlap"] for child in report["children"]), "child OS lock overlap"
            assert report["children"], "no controlled Python child executed"
            assert not any(pid_alive(pid) for pid in harness.pids), "child process leaked"
            report["max_sampled_live_pids"] = max(len(row["live_pids"]) for row in report["pid_samples"])
            report["status"] = "passed" if len(report["cases"]) == 10 and all(
                row["status"] == "passed" for row in report["cases"]) else "failed"
    except Exception:
        report.update(status="failed", fatal_traceback=traceback.format_exc())
        if harness is not None:
            harness.cleanup()
    finally:
        report["source_sha256_after"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in sources}
        report["source_unchanged_during_run"] = report["source_sha256_before"] == report["source_sha256_after"]
        if not report["source_unchanged_during_run"]:
            report["status"] = "failed"
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(report["status"].upper(), output / "report.json", flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
