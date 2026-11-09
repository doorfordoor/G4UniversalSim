"""Finite owned SDK process/guard tests. Fixtures are NOT Geant4 SDK builds."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from test_install_plan import arguments, fixture, service
from g4usim_gui.core import _install_sdk_process as adapter

assert Path(service.__file__).resolve() == ROOT / "gui/g4usim_gui/core/environment_install.py"
assert Path(adapter.__file__).resolve() == ROOT / "gui/g4usim_gui/core/_install_sdk_process.py"

HELPER = r'''
import json,os,sys,time,subprocess,signal
from pathlib import Path
sys.path.insert(0,sys.argv[3])
from g4usim_gui.core._install_sdk_process import owner_identity
mode,root=sys.argv[1],Path(sys.argv[2])
identity=owner_identity()
(root/(mode+'-identity.json')).write_text(json.dumps(identity))
print(json.dumps({'mode':mode,'argv':sys.argv,'cwd':os.getcwd(),'env':os.environ.get('AR5_QUOTED'),'identity':identity}),flush=True)
if mode=='child':
    while True:
        with (root/'heartbeat.txt').open('a') as f:f.write('tick\n');f.flush()
        time.sleep(.03)
if mode in ('timeout','orphan'):
    child=subprocess.Popen([sys.executable,__file__,'child',str(root),sys.argv[3]])
    if os.name!='nt':
        def stop(sig,frame):
            child.terminate();child.wait(timeout=3);sys.exit(143)
        signal.signal(signal.SIGTERM,stop)
    time.sleep(.3)
    if mode=='orphan':sys.exit(0)
    time.sleep(60)
if mode=='nonzero':sys.exit(7)
if mode=='handle':
    import ctypes
    from ctypes import wintypes as w
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.GetHandleInformation.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];k.GetHandleInformation.restype=w.BOOL
    flags=w.DWORD();ok=k.GetHandleInformation(int(os.environ['AR5_UNRELATED_HANDLE']),ctypes.byref(flags))
    (root/'handle-observation.json').write_text(json.dumps({'valid':bool(ok),'error':ctypes.get_last_error(),'flags':flags.value}))
'''


def expect_error(call, code):
    try:
        call()
    except service.InstallError as exc:
        assert exc.code == code, (code, exc.code, str(exc))
    else:
        raise AssertionError("Expected " + code)


def setup(root, name):
    folder = root / name
    folder.mkdir()
    catalog = fixture(folder)
    release = catalog["releases"][0]
    release.update(profile="sdk", dependencies=[{"id": "compiler"}, {"id": "cmake"}],
                   sdk={"geant4_dir": "sdk/geant4", "probe_source": "sdk/probe", "application_source": "sdk/probe"})
    args = arguments(catalog, folder)
    plan = service.create_plan(catalog, **args)
    receipt = service.execute_plan(plan)
    assert receipt["status"] == "published", receipt
    prefix = Path(args["prefix"])
    helper = folder / "父子 fixture.py"
    helper.write_text(HELPER, encoding="utf-8")
    return folder, prefix, helper, plan


def command(helper, folder, mode):
    return [getattr(sys, "_base_executable", sys.executable), str(helper), mode, str(folder),
            str(ROOT / "gui"), 'space and "quote" 中文']


def bounded_probe(folder, prefix, helper, mode, *, timeout=1.5, hooks=None):
    """Real public lock/report wrapper, real owned adapter; replace only SDK work."""
    retained = []
    update = service._guard_update
    guard_history = folder / "guard-history"
    guard_history.mkdir()
    transitions = []
    def trace_guard(path, guard, state, record):
        update(path, guard, state, record)
        raw = path.read_bytes()
        target = guard_history / f"{len(transitions):02d}-{state}.json"
        target.write_bytes(raw)
        transitions.append({"state": state, "path": str(target), "sha256": service._file_hash(target)})
        (guard_history / "transitions.json").write_text(json.dumps(transitions, indent=2))
    def finite(prefix, *, build_directory, _report, **kwargs):
        report = _report
        retained.append(report)
        installed = service._verify_installation(prefix)["receipt"]
        build = Path(build_directory)
        report.update(prefix=str(prefix), allowed_root=installed["allowed_root"], build_directory=str(build),
                      transaction_id=installed["transaction_id"])
        try:
            if service._run_sdk_command(report, installed, prefix, build, "configure", command(helper, folder, mode),
                                        dict(os.environ, AR5_QUOTED='value "含空格"'), timeout):
                report["status"] = "verified"
        finally:
            service._finish_sdk_operation(report, prefix)
        return report
    with ExitStack() as stack:
        stack.enter_context(patch.object(service, "_probe_sdk_unlocked", side_effect=finite))
        stack.enter_context(patch.object(service, "_guard_update", side_effect=trace_guard))
        for context in hooks or []:
            stack.enter_context(context)
        try:
            report = service.probe_sdk(prefix, build_directory=folder / "build 中文 with spaces", cmake=sys.executable)
        except BaseException:
            if retained:
                (folder / "interrupted-report.json").write_text(json.dumps(retained[0], indent=2))
            raise
    assert retained and report is retained[0], "public wrapper replaced the report owner"
    (folder / "returned-report.json").write_text(json.dumps(report, indent=2))
    return report


def assert_stopped(folder, report):
    record = report["commands"][0]
    assert record["root_waited"] and record["container_empty"] and record["handles_closed"], record
    assert record["log_finalized"] and record["cleanup_verified"], record
    assert service._file_hash(Path(record["log"])) == record["log_sha256"]
    heartbeat = folder / "heartbeat.txt"
    before = heartbeat.read_bytes() if heartbeat.exists() else b""
    time.sleep(.15)
    assert (heartbeat.read_bytes() if heartbeat.exists() else b"") == before
    if (folder / "child-identity.json").exists():
        assert before, "child identity existed but never exercised its writer"


def host_death_fixture(root):
    folder, prefix, helper, plan = setup(root, "owned")
    original = service._guard_update
    def exit_after_owned(path, guard, state, record):
        original(path, guard, state, record)
        if state == "owned_suspended":
            (root / "ready.json").write_text(json.dumps({"guard": str(path), "child": record["root_child"],
                                                       "prefix": str(prefix), "allowed_root": str(folder), "plan": plan}))
            deadline = time.monotonic() + 15
            while not (root / "release-host").exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError("host-death fixture was not released by its owner")
                time.sleep(.02)
            os._exit(73)  # deliberate death: only OS Job ownership can settle the suspended child
    bounded_probe(folder, prefix, helper, "normal", hooks=[patch.object(service, "_guard_update", side_effect=exit_after_owned)])


def main(root):
    root.mkdir(parents=True, exist_ok=False)
    results = []
    def save(case, result):
        results.append({"case": case, "result": result})
        (root / "results.json").write_text(json.dumps(results, indent=2))
        print("SDK_LIFECYCLE", case, result, flush=True)

    for mode in ("normal", "nonzero", "timeout", "orphan"):
        folder, prefix, helper, plan = setup(root, mode)
        report = bounded_probe(folder, prefix, helper, mode)
        expected = {"normal": None, "nonzero": "sdk_command", "timeout": "sdk_timeout", "orphan": "sdk_descendants_remaining"}[mode]
        if expected:
            assert report["status"] == "failed" and report["diagnostics"][0]["code"] == expected, report
        else:
            assert report["status"] == "verified" and report["commands"][0]["exit_code"] == 0, report
            raw = Path(report["commands"][0]["log"]).read_text(encoding="utf-8")
            observed = json.loads(raw.splitlines()[0])
            assert observed["argv"][-1] == 'space and "quote" 中文' and observed["env"] == 'value "含空格"'
            assert observed["cwd"] == report["build_directory"]
        if os.name != "nt" and not report["commands"][0]["container_empty"]:
            assert service._sdk_operation_pending(prefix)
            save(mode, "Linux remaining-group/zombie UNKNOWN; guard retained, not a pass for empty group")
            continue
        assert_stopped(folder, report)
        assert not service._sdk_operation_pending(prefix)
        # A new independent command only after prior stop/guard completion.
        next_folder = folder / "next";next_folder.mkdir()
        second = bounded_probe(next_folder, prefix, helper, "normal")
        assert second["status"] == "verified", second
        assert_stopped(next_folder, second)
        save(mode, {"exit": report["commands"][0]["exit_code"], "cleanup_verified": True, "next_operation": "verified"})

    folder, prefix, helper, plan = setup(root, "suspended-persist-failure")
    update = service._guard_update
    def fail_owned(path, guard, state, record):
        if state == "owned_suspended":
            raise OSError("injected owned_suspended persistence failure")
        return update(path, guard, state, record)
    if os.name == "nt":
        report = bounded_probe(folder, prefix, helper, "normal", hooks=[patch.object(service, "_guard_update", side_effect=fail_owned)])
        assert report["status"] == "failed" and not report["commands"][0]["resumed"]
        assert not (folder / "normal-identity.json").exists()
        assert_stopped(folder, report)
        save("suspended-persist-failure", "root terminated/waited before user code")

        folder, prefix, helper, plan = setup(root, "suspended-partial-persist")
        writer = service._write_json
        def leave_owned_temp(path, value, **kwargs):
            if path == service._sdk_guard_path(prefix) and value.get("state") == "owned_suspended":
                writer(path.with_name(path.name + ".new"), value, exclusive=True)
                raise OSError("injected interruption after owned temp write")
            return writer(path, value, **kwargs)
        report = bounded_probe(folder, prefix, helper, "normal", hooks=[patch.object(service, "_write_json", side_effect=leave_owned_temp)])
        assert not report["commands"][0]["resumed"] and not (folder / "normal-identity.json").exists()
        assert_stopped(folder, report)
        guard = service._sdk_guard_path(prefix)
        assert service.load_catalog(guard)["state"] == "intent"
        assert service.load_catalog(guard.with_name(guard.name + ".new"))["state"] == "owned_suspended"
        expect_error(lambda: service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard"), "sdk_guard_unsettled")
        save("suspended-partial-persist", "real owned root stopped; nonsettled durable pair retained")

    folder, prefix, helper, plan = setup(root, "timeout-receipt-unlock")
    unlock = service._unlock_prefix_descriptor
    close = service._close_prefix_descriptor
    closes = []
    def fail_unlock(fd):
        unlock(fd)
        raise OSError("injected unlock failure after real unlock")
    def track_close(fd):
        closes.append(fd)
        close(fd)
    report = bounded_probe(folder, prefix, helper, "timeout", hooks=[
        patch.object(service, "_persist_sdk_report", side_effect=OSError("injected receipt failure")),
        patch.object(service, "_unlock_prefix_descriptor", side_effect=fail_unlock),
        patch.object(service, "_close_prefix_descriptor", side_effect=track_close)])
    assert report["diagnostics"][0]["code"] == "sdk_timeout" and len(report["commands"]) == 1, report
    assert {d["stage"] for d in report["diagnostics"]} >= {"probe_receipt", "lock_unlock"}
    assert len(closes) == 1 and report["receipt_is_final"] is False
    assert_stopped(folder, report)
    guard_path = service._sdk_guard_path(prefix)
    assert service.load_catalog(guard_path)["state"] == "settled"
    assert service.verify_installation(prefix)["operation_pending"]
    blocked = service.probe_sdk(prefix, build_directory=folder / "must-not-create", cmake=sys.executable)
    assert blocked["diagnostics"][0]["code"] == "sdk_operation_pending" and not (folder / "must-not-create").exists()
    assert service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard")["cleanup_verified"]
    save("timeout-receipt-unlock", "first timeout / commands retained / close once / explicit settled recovery")

    folder, prefix, helper, plan = setup(root, "nonzero-log-close")
    close_log = service._close_sdk_log
    def fail_log_close(output):
        close_log(output)
        raise OSError("injected log close failure after real close")
    report = bounded_probe(folder, prefix, helper, "nonzero", hooks=[patch.object(service, "_close_sdk_log", side_effect=fail_log_close)])
    assert report["diagnostics"][0]["code"] == "sdk_command" and report["commands"][0]["exit_code"] == 7
    assert not report["commands"][0]["log_finalized"] and not report["commands"][0]["cleanup_verified"]
    assert service.load_catalog(service._sdk_guard_path(prefix))["state"] == "settling"
    expect_error(lambda: service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard"), "sdk_guard_unsettled")
    save("nonzero-log-close", "process cleaned; log evidence unknown; guard deliberately retained")

    folder, prefix, helper, plan = setup(root, "final-log-hash-failure")
    file_hash = service._file_hash
    def fail_final_hash(path, *args, **kwargs):
        if path == folder / "build 中文 with spaces" / "configure.log":
            raise OSError("injected final log hash failure")
        return file_hash(path, *args, **kwargs)
    report = bounded_probe(folder, prefix, helper, "normal", hooks=[patch.object(service, "_file_hash", side_effect=fail_final_hash)])
    record = report["commands"][0]
    assert record["exit_code"] == 0 and record["log_handle_closed"] and not record["log_finalized"]
    assert record["log_sha256"] is None and not record["cleanup_verified"] and report["status"] == "failed"
    assert service.load_catalog(service._sdk_guard_path(prefix))["state"] == "settling"
    expect_error(lambda: service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard"), "sdk_guard_unsettled")
    save("final-log-hash-failure", "handle closed but final hash unknown; no settled cleanup claim")

    folder, prefix, helper, plan = setup(root, "success-unlink-failure")
    unlink = Path.unlink
    def fail_unlink(path, *args, **kwargs):
        if path == service._sdk_guard_path(prefix):
            raise OSError("injected guard unlink failure")
        return unlink(path, *args, **kwargs)
    report = bounded_probe(folder, prefix, helper, "normal", hooks=[patch.object(Path, "unlink", fail_unlink)])
    assert report["status"] == "failed" and report["commands"][0]["exit_code"] == 0 and report["receipt_is_final"] is False
    disk = Path(report["build_directory"]) / "sdk-probe-receipt.json"
    assert service.load_catalog(disk)["status"] == "verified" and service._file_hash(disk) == report["persisted_receipt_sha256"]
    guard_path = service._sdk_guard_path(prefix)
    settled = service.load_catalog(guard_path)
    original_bytes = guard_path.read_bytes()
    (folder / "settled-guard-before.json").write_bytes(original_bytes)
    # Pair planning: valid settled temp cannot override a damaged/wrong base.
    temporary = guard_path.with_name(guard_path.name + ".new")
    temporary.write_bytes(original_bytes)
    bad = copy.deepcopy(settled);bad["operation_id"] = "0" * 32
    guard_path.write_text(json.dumps(bad))
    (folder / "invalid-pair-before.json").write_text(json.dumps({"base": bad, "temporary": settled}, indent=2))
    pair_before = [guard_path.read_bytes(), temporary.read_bytes()]
    expect_error(lambda: service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard"), "sdk_guard_invalid")
    assert pair_before == [guard_path.read_bytes(), temporary.read_bytes()]
    guard_path.write_bytes(original_bytes)
    log = Path(settled["record"]["log"])
    log_bytes = log.read_bytes()
    log.write_bytes(log_bytes + b"late mutation")
    expect_error(lambda: service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard"), "sdk_guard_invalid")
    assert guard_path.read_bytes() == original_bytes and temporary.read_bytes() == original_bytes
    log.write_bytes(log_bytes)  # fixture restoration, not production recovery
    # Legal settling base + settled temporary, including exact log SHA binding.
    base = copy.deepcopy(settled);base.update(state="settling", cleanup_verified=False);base["record"]["cleanup_verified"] = False
    guard_path.write_text(json.dumps(base))
    service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard")
    assert not guard_path.exists() and not temporary.exists()
    assert service._file_hash(disk) == report["persisted_receipt_sha256"]
    save("success-unlink-failure", "root0 retained / late failure separated / strict settled temp recovery")

    folder, prefix, helper, plan = setup(root, "close-once")
    calls = []
    def fail_close(fd):
        calls.append(fd);close(fd)
        raise OSError("injected descriptor close failure after real close")
    report = bounded_probe(folder, prefix, helper, "normal", hooks=[patch.object(service, "_close_prefix_descriptor", side_effect=fail_close)])
    assert len(calls) == 1 and report["diagnostics"][-1]["stage"] == "lock_close_unknown" and report["receipt_is_final"] is False
    assert report["commands"][0]["exit_code"] == 0
    save("close-once", "one close attempt; returned descriptor state unknown, disk not rewritten")

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes as w
        import _winapi
        folder, prefix, helper, plan = setup(root, "handle-whitelist")
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateEventW.argtypes = [ctypes.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]
        k.CreateEventW.restype = w.HANDLE
        event = k.CreateEventW(None, True, False, None)
        assert event
        try:
            os.set_handle_inheritable(event, True)
            with patch.dict(os.environ, {"AR5_UNRELATED_HANDLE": str(event)}):
                report = bounded_probe(folder, prefix, helper, "handle")
            assert report["status"] == "verified", report
            observation = json.loads((folder / "handle-observation.json").read_text())
            assert observation["valid"] is False and observation["error"] == 6, observation
            assert _winapi.WaitForSingleObject(event, 0) == _winapi.WAIT_TIMEOUT
        finally:
            _winapi.CloseHandle(event)
        save("handle-whitelist", "unrelated inheritable handle absent from actual child")

        folder, prefix, helper, plan = setup(root, "cancel-suspended")
        def cancel_owned(path, guard, state, record):
            update(path, guard, state, record)
            if state == "owned_suspended":
                raise KeyboardInterrupt("injected user cancellation")
        try:
            bounded_probe(folder, prefix, helper, "normal", hooks=[patch.object(service, "_guard_update", side_effect=cancel_owned)])
        except KeyboardInterrupt:
            report = json.loads((folder / "interrupted-report.json").read_text())
            assert not report["commands"][0]["resumed"]
            assert_stopped(folder, report)
        else:
            raise AssertionError("Cancellation swallowed")
        save("cancel-suspended", "KeyboardInterrupt propagated after owned cleanup")

        import _winapi
        folder = root / "host-death";folder.mkdir()
        argv = [getattr(sys, "_base_executable", sys.executable), "-B", str(Path(__file__).resolve()), "--host-death", str(folder)]
        handle = None
        with (folder / "host.log").open("xb") as output:
            host = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 15
                while not (folder / "ready.json").exists() and host.poll() is None and time.monotonic() < deadline:
                    time.sleep(.02)
                assert (folder / "ready.json").exists(), "host-death fixture did not reach durable owned_suspended"
                ready = json.loads((folder / "ready.json").read_text())
                handle = _winapi.OpenProcess(0x100000 | 0x1000, False, ready["child"]["pid"])
                assert adapter._win_creation(adapter._windows_api(), handle) == ready["child"]["creation"]
                (folder / "release-host").write_text("release only this fixture host")
                assert host.wait(timeout=10) == 73
                assert _winapi.WaitForSingleObject(handle, 10000) == _winapi.WAIT_OBJECT_0
                child_exit = _winapi.GetExitCodeProcess(handle)
            finally:
                if host.poll() is None:
                    host.kill();host.wait(timeout=10)  # exact Popen-owned fixture only
                if handle is not None:
                    _winapi.CloseHandle(handle)
        prefix = Path(ready["prefix"])
        guard_path = Path(ready["guard"])
        original_bytes = guard_path.read_bytes()
        assert service.load_catalog(guard_path)["state"] == "owned_suspended"
        assert service.verify_installation(prefix)["operation_pending"]
        expect_error(lambda: service.recover_installation(prefix, allowed_root=ready["allowed_root"], action="recover_sdk_guard"), "sdk_guard_unsettled")
        expect_error(lambda: service.uninstall_installation(prefix), "sdk_operation_pending")
        expect_error(lambda: service.recover_installation(prefix, allowed_root=ready["allowed_root"]), "sdk_operation_pending")
        rejected = service.execute_plan(ready["plan"])
        assert rejected["diagnostics"][0]["code"] == "sdk_operation_pending"
        rejected = service.probe_sdk(prefix, build_directory=folder / "no-overlap", cmake=sys.executable)
        assert rejected["diagnostics"][0]["code"] == "sdk_operation_pending" and not (folder / "no-overlap").exists()
        assert guard_path.read_bytes() == original_bytes
        observation = {"host_pid": host.pid, "host_exit": 73, "child": ready["child"], "child_exit": child_exit,
                       "same_handle_signalled": True, "guard_state": "owned_suspended", "recovery": "blocked"}
        (folder / "observation.json").write_text(json.dumps(observation, indent=2))
        save("host-death", observation)

    # Application-only switches: inspect actual configure construction, no build.
    folder, prefix, helper, plan = setup(root, "application-flags")
    captured = []
    def inspect_command(report, installed, selected, build, stage, argv, env, timeout):
        captured.append(argv)
        service._append_failure(report, stage, service.InstallError("fixture_stop", "no SDK execution"))
        return False
    for kind in ("consumer", "application"):
        with patch.object(service, "_run_sdk_command", side_effect=inspect_command):
            report = service.probe_sdk(prefix, build_directory=folder / kind, cmake=sys.executable, kind=kind)
        assert report["diagnostics"][0]["code"] == "fixture_stop"
    assert "-DG4USIM_STANDALONE_EXPORT=ON" not in captured[0] and "-DBUILD_TESTING=ON" not in captured[0]
    assert "-DG4USIM_STANDALONE_EXPORT=ON" in captured[1] and "-DBUILD_TESTING=ON" in captured[1]
    (folder / "argv.json").write_text(json.dumps(captured, indent=2))
    save("application-flags", "application only; no SDK built")
    # The installation wrapper must preserve real publication when unlock fails.
    folder = root / "install-unlock";folder.mkdir()
    catalog = fixture(folder);args = arguments(catalog, folder)
    plan = service.create_plan(catalog, **args)
    with patch.object(service, "_unlock_prefix_descriptor", side_effect=fail_unlock):
        report = service.execute_plan(plan)
    assert report["status"] == "published_with_warning" and report["events"] and report["receipt_is_final"] is False, report
    marker = Path(args["prefix"]) / service.MARKER
    assert service.load_catalog(marker)["status"] == "published" and service._file_hash(marker) == report["persisted_receipt_sha256"]
    (folder / "returned-report.json").write_text(json.dumps(report, indent=2))
    save("install-unlock", "published preserved; late failure does not rewrite marker")
    c3_controls(root, save)
    c4_controls(root, save)
    if os.name != "nt": c5_read_eio_control(root, save)
    print("SDK lifecycle finite tests completed", len(results), "platform", sys.platform)



def c3_controls(root, save):
    # C-L01: real command completes; independently withhold container proof.
    folder, prefix, helper, plan = setup(root, "c3-container-unknown")
    original_run = adapter.run_owned
    def unknown(*args, **kwargs):
        original_run(*args, **kwargs)
        kwargs["record"]["container_empty"] = False
        raise adapter.SDKProcessError("sdk_cleanup_unknown", "injected loss of empty-container proof after real cleanup")
    report = bounded_probe(folder, prefix, helper, "normal", hooks=[patch.object(adapter, "run_owned", side_effect=unknown)])
    rec = report["commands"][0]
    assert rec["exit_code"] == 0 and rec["log_handle_closed"] and not rec["container_empty"]
    assert rec["log_sha256"] is None and not rec["log_finalized"] and not rec["cleanup_verified"]
    assert service.load_catalog(service._sdk_guard_path(prefix))["state"] == "settling"
    save("C-L01", "real root0; missing container proof keeps final log SHA null and guard settling")

    # Obtain genuine writer-produced settled evidence, then mutate only fixtures.
    folder, prefix, helper, plan = setup(root, "c3-guard-validation")
    unlink = Path.unlink
    guard = service._sdk_guard_path(prefix); temporary = guard.with_name(guard.name + ".new")
    def keep_guard(path, *a, **k):
        if path == guard: raise OSError("fixture retains actual settled guard")
        return unlink(path, *a, **k)
    report = bounded_probe(folder, prefix, helper, "normal", hooks=[patch.object(Path, "unlink", keep_guard)])
    raw = guard.read_bytes(); good = json.loads(raw)
    def reject(code):
        before = {p: p.read_bytes() for p in (guard, temporary) if p.exists()}
        with patch.object(service.os, "replace", side_effect=AssertionError("recovery mutated invalid pair")), \
                patch.object(Path, "unlink", side_effect=AssertionError("recovery deleted invalid pair")):
            expect_error(lambda: service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard"), code)
        assert all(p.read_bytes() == data for p, data in before.items())
    bad = copy.deepcopy(good);bad.update(state="settling", cleanup_verified=False, record=None)
    guard.write_text(json.dumps(bad));temporary.write_bytes(raw)
    (folder/"null-record-pair.json").write_text(json.dumps({"base":bad,"temporary":good},indent=2))
    reject("sdk_guard_invalid");unlink(temporary)
    bad = copy.deepcopy(good);bad["record"]["spawned"] = False
    guard.write_text(json.dumps(bad));(folder/"false-spawn.json").write_text(json.dumps(bad,indent=2))
    reject("sdk_guard_invalid");guard.write_bytes(raw)
    for mutation in ("wrong-command", "final-without-proof", "running-not-resumed"):
        bad = copy.deepcopy(good);bad.update(state="settling", cleanup_verified=False)
        if mutation == "wrong-command": bad["record"]["argv"] = ["wrong"]
        elif mutation == "final-without-proof": bad["record"]["container_empty"] = False
        else:
            bad["state"] = "running";bad["record"]["resumed"] = False
        guard.write_text(json.dumps(bad));temporary.write_bytes(raw)
        reject("sdk_guard_invalid");unlink(temporary);guard.write_bytes(raw)
    save("C-G01", "actual settled evidence: null settling record and false no-spawn rejected with zero mutations")

    validate = service._validate_sdk_guard
    injected = []
    def add_member(*a, **k):
        result = validate(*a, **k)
        if not injected:
            temporary.write_bytes(raw);injected.append(True)
        return result
    with patch.object(service, "_validate_sdk_guard", side_effect=add_member):
        reject("sdk_guard_changed")
    assert guard.read_bytes() == raw and temporary.read_bytes() == raw
    unlink(temporary)
    verify = service._verify_installation; verify_calls = []
    def late_verify(*a, **k):
        result = verify(*a, **k);verify_calls.append(True)
        if len(verify_calls) == 3:  # last prefix read immediately before unlink
            temporary.write_bytes(raw)
        return result
    with patch.object(service, "_verify_installation", side_effect=late_verify):
        reject("sdk_guard_changed")
    assert len(verify_calls) == 3 and guard.read_bytes() == raw and temporary.read_bytes() == raw
    unlink(temporary)
    symlink_result = "not available"
    try:
        temporary.symlink_to(folder/"missing-link-target")
    except OSError as exc:
        symlink_result = "OS capability unavailable: " + str(exc)
    else:
        with patch.object(service.os, "replace", side_effect=AssertionError("replace dangling guard")), \
                patch.object(Path, "unlink", side_effect=AssertionError("unlink with dangling sibling")):
            expect_error(lambda: service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard"), "linked_path")
        assert guard.read_bytes() == raw and temporary.is_symlink()
        unlink(temporary);unlink(guard)
        guard.symlink_to(folder/"missing-base-target")
        expect_error(lambda: service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard"), "linked_path")
        unlink(guard);guard.write_bytes(raw)
        symlink_result = "actual dangling base and sibling rejected"
    (folder/"link-capability.json").write_text(json.dumps({"platform":sys.platform,"result":symlink_result}))
    # Same actual writer evidence remains normally recoverable.
    assert service.recover_installation(prefix, allowed_root=folder, action="recover_sdk_guard")["cleanup_verified"]
    assert not guard.exists() and not temporary.exists()
    save("C-G02", {"late_member":"zero mutations", "symlink":symlink_result, "positive":"actual settled recovery"})

    # C-R01: observe direct exit17 before injecting one cleanup failure.
    folder, prefix, helper, plan = setup(root, "c3-exit-first-cause")
    helper.write_text(HELPER.replace("if mode=='nonzero':sys.exit(7)", "if mode=='nonzero':sys.exit(17)"), encoding="utf-8")
    seen = []; active_record = []
    def fault_run(*args, **kwargs):
        rec = kwargs["record"];active_record.append(rec)
        if os.name == "nt":
            import _winapi
            close = _winapi.CloseHandle
            def faulty_close(handle):
                close(handle)
                seen.append(int(handle))
                if len(seen) == 3:  # two duplicates, then the actual thread handle
                    assert rec["exit_code"] == 17 and rec["root_waited"]
                    raise OSError("injected close after natural exit17 and actual close")
            with patch.object(_winapi, "CloseHandle", side_effect=faulty_close):
                return original_run(*args, **kwargs)
        members = adapter._group_members
        def faulty_members(pgid):
            result = members(pgid)
            if rec["root_waited"] and not seen:
                assert rec["exit_code"] == 17
                seen.append(pgid)
                raise OSError("injected group query failure after actual reap")
            return result
        with patch.object(adapter, "_group_members", side_effect=faulty_members):
            return original_run(*args, **kwargs)
    report = bounded_probe(folder, prefix, helper, "nonzero", hooks=[patch.object(adapter, "run_owned", side_effect=fault_run)])
    assert seen and report["commands"][0]["exit_code"] == 17
    assert report["diagnostics"][0]["code"] == "sdk_command", report
    assert any("injected" in x["message"] for x in report["diagnostics"][1:]), report
    if os.name == "nt": assert len(seen) == len(set(seen)) == 5, seen
    save("C-R01", "natural exit17 first; injected cleanup failure supplemental; timeout/cancel prior tests retained")

    # C-R02: two real stages, second receipt replaced then hash fails.
    folder, prefix, helper, plan = setup(root, "c3-second-receipt-hash")
    actual_hash = service._file_hash; previous=[]; receipt_hash_calls=[]
    def hash_receipt(path):
        if Path(path).name == "sdk-probe-receipt.json":
            receipt_hash_calls.append(str(path))
            if len(receipt_hash_calls) == 2:
                raise OSError("injected second receipt hash after replacement")
        return actual_hash(path)
    def two_stages(prefix, *, build_directory, _report, **kwargs):
        installed=service._verify_installation(prefix)["receipt"];build=Path(build_directory)
        _report.update(prefix=str(prefix),allowed_root=installed["allowed_root"],build_directory=str(build),transaction_id=installed["transaction_id"])
        for stage in ("configure", "build"):
            assert service._run_sdk_command(_report,installed,prefix,build,stage,command(helper,folder,"normal"),dict(os.environ),2)
            _report["status"]="verified"
            service._finish_sdk_operation(_report,prefix)
            if stage=="configure":
                previous.append(_report["persisted_receipt_sha256"])
                (folder/"first-receipt.json").write_bytes((build/"sdk-probe-receipt.json").read_bytes())
        return _report
    with patch.object(service,"_probe_sdk_unlocked",side_effect=two_stages), patch.object(service,"_file_hash",side_effect=hash_receipt):
        report=service.probe_sdk(prefix,build_directory=folder/"build",cmake=sys.executable)
    disk=Path(report["build_directory"])/"sdk-probe-receipt.json"
    assert len(receipt_hash_calls)==2 and len(report["commands"])==2
    assert all(c["exit_code"]==0 for c in report["commands"])
    assert report["persisted_receipt_sha256"] is None and report["receipt_is_final"] is False
    assert actual_hash(disk)!=previous[0] and len(json.loads(disk.read_bytes())["commands"])==2
    assert report["diagnostics"][0]["stage"]=="probe_receipt" and service._sdk_operation_pending(prefix)
    (folder/"returned-report.json").write_text(json.dumps(report,indent=2))
    (folder/"disk-comparison.json").write_text(json.dumps({"historical_sha":previous[0],"current_disk_sha":actual_hash(disk),"returned_current_sha":None},indent=2))
    save("C-R02", "two actual stage exits0; replacement succeeded; current SHA unknown, old SHA not reused")



def c4_controls(root, save):
    folder, prefix, helper, plan = setup(root, "c4-cleanup-mirror")
    guard = service._sdk_guard_path(prefix);temp = guard.with_name(guard.name+".new")
    unlink = Path.unlink
    def retain(path,*a,**k):
        if path == guard: raise OSError("retain actual writer pair")
        return unlink(path,*a,**k)
    report=bounded_probe(folder,prefix,helper,"normal",hooks=[patch.object(Path,"unlink",retain)])
    settled=guard.read_bytes()
    base_raw=next((folder/'guard-history').glob('*-settling.json')).read_bytes()
    base=json.loads(base_raw);assert base['cleanup_verified'] is False and base['record']['cleanup_verified'] is False
    bad=copy.deepcopy(base);bad['cleanup_verified']=True
    guard.write_text(json.dumps(bad));temp.write_bytes(settled)
    before=[guard.read_bytes(),temp.read_bytes()]
    with patch.object(service.os,'replace',side_effect=AssertionError('mutated conflicting mirror')), \
            patch.object(Path,'unlink',side_effect=AssertionError('deleted conflicting mirror')):
        expect_error(lambda:service.recover_installation(prefix,allowed_root=folder,action='recover_sdk_guard'),'sdk_guard_invalid')
    assert before==[guard.read_bytes(),temp.read_bytes()]
    (folder/'conflicting-base.json').write_bytes(before[0]);(folder/'writer-base.raw').write_bytes(base_raw)
    (folder/'writer-settled.raw').write_bytes(settled)
    guard.write_bytes(base_raw)
    assert service.recover_installation(prefix,allowed_root=folder,action='recover_sdk_guard')['cleanup_verified']
    save('C4-G01','actual settling/settled pair: top-only flip rejected zero writes; original pair accepted')
    if os.name == 'nt':
        return  # Job behavior unchanged; no POSIX evidence claim on Windows

    # Parent-only log with a pipe must drain far beyond pipe capacity.
    folder,prefix,helper,plan=setup(root,'c4-pipe-volume')
    helper.write_text("import os\nfor i in range(128): os.write(1,b'x'*65536)\n",encoding='utf-8')
    report=bounded_probe(folder,prefix,helper,'normal',timeout=5)
    rec=report['commands'][0]
    assert report['status']=='verified' and rec['pipe_eof'] and rec['pipe_reader_closed'] and not rec['pipe_write_failed'],report
    assert Path(rec['log']).stat().st_size==128*65536 and rec['log_finalized']
    save('C4-L5-volume','8MiB actual pipe drained without deadlock; EOF and exact byte count')

    # Test controller adopts only its two detached fixtures, to reap after their
    # own latch-driven normal exit. Production never signals these new groups.
    import ctypes
    libc=ctypes.CDLL(None,use_errno=True)
    assert libc.prctl(36,1,0,0,0)==0  # PR_SET_CHILD_SUBREAPER, fixture process only
    folder,prefix,helper,plan=setup(root,'c4-detached-writers')
    script=r"""
import os,sys,time,json,subprocess
from pathlib import Path
sys.path.insert(0,sys.argv[3])
from g4usim_gui.core._install_sdk_process import owner_identity
mode,folder=sys.argv[1],Path(sys.argv[2])
if mode=='normal':
    identity=owner_identity();identity.update(pgid=os.getpgrp(),sid=os.getsid(0))
    (folder/'root-identity.json').write_text(json.dumps(identity))
    for tag in ('writer-a','writer-b'):
        subprocess.Popen([sys.executable,__file__,tag,str(folder),sys.argv[3]],start_new_session=True,close_fds=True)
    deadline=time.monotonic()+5
    while not all((folder/(tag+'-identity.json')).exists() for tag in ('writer-a','writer-b')):
        if time.monotonic()>deadline:sys.exit(9)
        time.sleep(.01)
    os.write(1,b'root done\n')
else:
    identity=owner_identity();identity.update(pgid=os.getpgrp(),sid=os.getsid(0))
    (folder/(mode+'-identity.json')).write_text(json.dumps(identity))
    deadline=time.monotonic()+12
    while not (folder/'release-writers').exists() and time.monotonic()<deadline:time.sleep(.01)
    try:
        os.write(1,b'detached late write\n');result='write accepted'
    except BrokenPipeError:result='broken pipe; parent reader closed'
    (folder/(mode+'-result.json')).write_text(json.dumps({'result':result,'identity':identity}))
"""
    helper.write_text(script,encoding='utf-8')
    report=bounded_probe(folder,prefix,helper,'normal',timeout=3)
    rec=report['commands'][0]
    assert rec['exit_code']==0 and rec['container_empty'] and rec['root_waited']
    assert report['status']=='failed' and report['diagnostics'][0]['code']=='sdk_log_writers_unknown',report
    assert not rec['pipe_eof'] and rec['pipe_reader_closed'] and rec['log_handle_closed']
    assert not rec['log_finalized'] and not rec['cleanup_verified'] and rec['log_sha256'] is None
    assert service.load_catalog(service._sdk_guard_path(prefix))['state']=='settling'
    root_id=json.loads((folder/'root-identity.json').read_text())
    writers=[json.loads((folder/(tag+'-identity.json')).read_text()) for tag in ('writer-a','writer-b')]
    for ident in writers:
        live=adapter._linux_process(ident['pid']);assert live['creation']==ident['creation']
        assert live['pgid']!=root_id['pgid'] and live['session']!=root_id['sid']
    before=service._file_hash(Path(rec['log']))
    (folder/'release-writers').write_text('fixture-owned latch; no signal')
    waits=[]
    for ident in writers:
        deadline=time.monotonic()+5
        while True:
            pid,status=os.waitpid(ident['pid'],os.WNOHANG)
            if pid:break
            assert time.monotonic()<deadline,'fixture writer failed to finish normally'
            time.sleep(.01)
        assert os.waitstatus_to_exitcode(status)==0
        waits.append({'pid':pid,'creation':ident['creation'],'exit':0,'controller_signal':False})
    after=service._file_hash(Path(rec['log']));assert before==after
    assert all(json.loads((folder/(tag+'-result.json')).read_text())['result'].startswith('broken pipe') for tag in ('writer-a','writer-b'))
    (folder/'detached-observation.json').write_text(json.dumps({'root':root_id,'writers':writers,'waits':waits,'observed_before_sha':before,'observed_after_sha':after,'reported_final_sha':rec['log_sha256']},indent=2))
    save('C4-L5-detached','two real detached writers alive at return; unknown guard, no final SHA, later writes cannot mutate parent-only file; both exit0 without signals')



def c5_read_eio_control(root, save):
    """Permanent real Linux EIO+TERM-ignore regression, no controller rescue."""
    assert os.name != "nt"
    import errno
    import signal
    folder,prefix,helper,plan=setup(root,'c5-persistent-read-eio')
    helper.write_text(r"""
import os,sys,signal,time,json
from pathlib import Path
sys.path.insert(0,sys.argv[3])
from g4usim_gui.core._install_sdk_process import owner_identity
signal.signal(signal.SIGTERM,signal.SIG_IGN)
folder=Path(sys.argv[2]);ident=owner_identity();ident.update(pgid=os.getpgrp(),sid=os.getsid(0))
(folder/'term-ignored-identity.json').write_text(json.dumps(ident))
os.write(1,b'ready after ignoring TERM\n')
while True: time.sleep(.02)
""",encoding='utf-8')
    popen=adapter.subprocess.Popen;read=adapter.os.read;killpg=adapter.os.killpg
    owned=[];errors=[];signals=[]
    def track_popen(*a,**k):
        proc=popen(*a,**k);owned.append(proc);return proc
    def persistent_read(fd,n):
        if owned and owned[0].stdout is not None and fd==owned[0].stdout.fileno():
            identity=json.loads((folder/'term-ignored-identity.json').read_text())
            assert identity['pid']==owned[0].pid
            try:
                current=adapter._linux_process(owned[0].pid)
                assert current['creation']==identity['creation']
            except FileNotFoundError:
                assert owned[0].returncode==-signal.SIGKILL  # exact Popen already reaped
            errors.append({'fd':fd,'pid':identity['pid'],'creation':identity['creation']})
            raise OSError(errno.EIO,'fixture persistent pipe read EIO')
        return read(fd,n)
    def tracked_killpg(pgid,sig):
        assert owned and pgid==owned[0].pid
        signals.append({'pgid':pgid,'signal':int(sig)})
        return killpg(pgid,sig)
    report=bounded_probe(folder,prefix,helper,'normal',timeout=3,hooks=[
        patch.object(adapter.subprocess,'Popen',side_effect=track_popen),
        patch.object(adapter.os,'read',side_effect=persistent_read),
        patch.object(adapter.os,'killpg',side_effect=tracked_killpg)])
    rec=report['commands'][0]
    assert [x['signal'] for x in signals]==[signal.SIGTERM,signal.SIGKILL],signals
    assert len(errors)>=2 and owned[0].returncode==-signal.SIGKILL
    assert rec['root_waited'] and rec['container_empty'] and rec['remaining_group_members']==[]
    assert rec['exit_code']==-signal.SIGKILL and rec['pipe_reader_closed'] and rec['handles_closed']
    assert not rec['pipe_eof'] and not rec['log_finalized'] and rec['log_sha256'] is None and not rec['cleanup_verified']
    assert report['diagnostics'][0]['code']=='io_error' and 'persistent pipe read EIO' in report['diagnostics'][0]['message']
    assert service.load_catalog(service._sdk_guard_path(prefix))['state']=='settling'
    try: adapter._linux_process(owned[0].pid)
    except FileNotFoundError: pass
    else: raise AssertionError('owned root remains after product wait')
    (folder/'eio-observation.json').write_text(json.dumps({'errors':errors,'signals':signals,'popen_returncode':owned[0].returncode,'product_reaped':True,'controller_signals':False,'record':rec},indent=2))
    save('C5-read-EIO','persistent read EIO first; TERM then KILL; actual root reap -9, empty group; no EOF/final; no controller rescue')


def c5_focused(root):
    assert os.name != 'nt'
    root.mkdir(parents=True,exist_ok=False)
    results=[]
    def save(case,result):
        results.append({'case':case,'result':result})
        (root/'results.json').write_text(json.dumps(results,indent=2))
        print('C5_FOCUSED',case,result,flush=True)
    for mode,expected in (('normal',None),('nonzero','sdk_command'),('timeout','sdk_timeout')):
        folder,prefix,helper,plan=setup(root,'c5-'+mode)
        report=bounded_probe(folder,prefix,helper,mode)
        assert_stopped(folder,report)
        if expected: assert report['diagnostics'][0]['code']==expected,report
        else: assert report['status']=='verified',report
        save(mode,{'status':report['status'],'exit':report['commands'][0]['exit_code'],'cleanup_verified':True})
    c5_read_eio_control(root,save)
    c4_controls(root,save)  # limited adjacent EOF/escaped-writer and mirror controls
    print('C5 focused controls completed',len(results),flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--c5-focused":
        c5_focused(Path(sys.argv[2]).absolute())
    elif sys.argv[1] == "--host-death":
        host_death_fixture(Path(sys.argv[2]).absolute())
    else:
        main(Path(sys.argv[1]).absolute())
