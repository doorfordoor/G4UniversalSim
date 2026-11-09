"""Private SDK command ownership. No recovery by PID and no arbitrary-tree killer."""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path


class SDKProcessError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _windows_api():
    from ctypes import wintypes as w
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    for name, args, result in (
        ("CreateJobObjectW", [ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
        ("SetInformationJobObject", [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
        ("QueryInformationJobObject", [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p], w.BOOL),
        ("AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL),
        ("TerminateJobObject", [w.HANDLE, w.UINT], w.BOOL),
        ("ResumeThread", [w.HANDLE], w.DWORD),
        ("GetProcessTimes", [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p], w.BOOL),
    ):
        function = getattr(k, name)
        function.argtypes, function.restype = args, result
    return k


def _win_check(value):
    if not value:
        raise ctypes.WinError(ctypes.get_last_error())
    return value


def _win_creation(k, handle):
    times = [ctypes.c_uint64() for _ in range(4)]
    _win_check(k.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)))
    return str(times[0].value)


def _linux_process(pid):
    text = Path(f"/proc/{pid}/stat").read_text()
    fields = text[text.rfind(")") + 2:].split()
    return {"pid": pid, "creation": fields[19], "state": fields[0],
            "pgid": int(fields[2]), "session": int(fields[3])}


def owner_identity():
    if os.name == "nt":
        import _winapi
        return {"pid": os.getpid(), "creation": _win_creation(_windows_api(), _winapi.GetCurrentProcess()),
                "boot_identity": None}
    identity = _linux_process(os.getpid())
    return {"pid": identity["pid"], "creation": identity["creation"],
            "boot_identity": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def _cleanup_error(record, stage, exc):
    record.setdefault("cleanup_errors", []).append({"stage": stage, "code": getattr(exc, "code", "io_error"),
                                                    "message": str(exc), "type": type(exc).__name__})


def _wait_windows_root_with_job_sample(process, deadline, accounting):
    """Accept a sample only if the root is still unsignaled after the read."""
    import _winapi
    before_root = None
    while True:
        if time.monotonic() >= deadline:
            return _winapi.WAIT_TIMEOUT, before_root, None
        try:
            sample = accounting()
        except OSError as exc:
            remaining = deadline - time.monotonic()
            state = (_winapi.WaitForSingleObject(process, max(1, int(remaining * 1000)))
                     if remaining > 0 else _winapi.WAIT_TIMEOUT)
            return state, None, str(exc)
        state = _winapi.WaitForSingleObject(process, 0)
        remaining = deadline - time.monotonic()
        if state != _winapi.WAIT_TIMEOUT:
            return state, before_root, None
        if remaining <= 0:
            return state, before_root, None
        before_root = sample
        state = _winapi.WaitForSingleObject(process, max(1, int(min(.01, remaining) * 1000)))
        if state != _winapi.WAIT_TIMEOUT:
            return state, before_root, None
        if time.monotonic() >= deadline:
            return state, before_root, None


def _windows_command(argv, cwd, env, output, timeout, record, owned, running, settling, *, msvc_auxiliary=None):
    import _winapi
    import msvcrt
    from ctypes import wintypes as w

    class Limits(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64), ("flags", w.DWORD),
                    ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t), ("active", w.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("limits", Limits), ("io", ctypes.c_uint64 * 6), ("process_memory", ctypes.c_size_t),
                    ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

    class Accounting(ctypes.Structure):
        _fields_ = [("times", ctypes.c_int64 * 4), ("faults", w.DWORD), ("total", w.DWORD),
                    ("active", w.DWORD), ("terminated", w.DWORD)]

    k = _windows_api()
    job = process = thread = None
    duplicates = []
    assigned = False
    error = None
    record["job_termination_requested"] = False
    pinned = None
    residual = None
    auxiliary = None
    targets_verified = False
    command_deadline = None

    def accounting():
        info = Accounting()
        _win_check(k.QueryInformationJobObject(job, 1, ctypes.byref(info), ctypes.sizeof(info), None))
        return info.total, info.active

    def policy_budget_expired():
        return pinned is not None and command_deadline is not None and time.monotonic() >= command_deadline

    def command_timeout():
        return SDKProcessError("sdk_timeout", "SDK command exceeded its timeout")

    try:
        if msvc_auxiliary is not None:
            from . import _install_msvc_auxiliary as auxiliary_api
            auxiliary = record["msvc_auxiliary_cleanup"] = {
                "image": str(msvc_auxiliary.image), "sha256": msvc_auxiliary.sha256, "status": "unavailable",
            }
            try:
                pinned = auxiliary_api.pin(msvc_auxiliary)
                auxiliary["status"] = "bound"
            except Exception as exc:
                auxiliary["reason"] = {"type": type(exc).__name__, "message": str(exc)}
        job = _win_check(k.CreateJobObjectW(None, None))
        limits = Extended()
        limits.limits.flags = 0x2000  # KILL_ON_JOB_CLOSE; deliberately no BREAKAWAY flags
        _win_check(k.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        observed = Extended()
        _win_check(k.QueryInformationJobObject(job, 9, ctypes.byref(observed), ctypes.sizeof(observed), None))
        if observed.limits.flags != 0x2000:
            raise SDKProcessError("sdk_job_limits", "Job limits differ from kill-on-close/no-breakaway")
        record["container"] = {"kind": "windows_job", "creation_id": uuid.uuid4().hex,
                               "limit_flags": int(observed.limits.flags), "created_time_ns": time.time_ns()}
        current = _winapi.GetCurrentProcess()
        with open(os.devnull, "rb") as null:
            for stream in (null, output):
                duplicates.append(_winapi.DuplicateHandle(current, msvcrt.get_osfhandle(stream.fileno()),
                                                          current, 0, True, _winapi.DUPLICATE_SAME_ACCESS))
            startup = subprocess.STARTUPINFO()
            startup.dwFlags = _winapi.STARTF_USESTDHANDLES
            startup.hStdInput, startup.hStdOutput = duplicates
            startup.hStdError = duplicates[1]
            startup.lpAttributeList = {"handle_list": duplicates[:]}
            # CPython's native CreateProcess wrapper sets up the explicit handle
            # list / Unicode environment. Keep BOTH process/thread handles here.
            process, thread, pid, tid = _winapi.CreateProcess(
                argv[0], subprocess.list2cmdline(argv), None, None, True,
                0x4 | subprocess.CREATE_NO_WINDOW | 0x400, env, str(cwd), startup)
        record["spawned"] = True
        record["root_child"] = {"pid": pid, "creation": _win_creation(k, process), "thread_id": tid}
        _win_check(k.AssignProcessToJobObject(job, process))
        assigned = True
        owned()  # durable owned_suspended, before any user code is allowed
        if k.ResumeThread(thread) == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        record["resumed"] = True
        running()
        command_deadline = time.monotonic() + timeout
        before_root = None
        if pinned is None:
            wait = _winapi.WaitForSingleObject(process, max(1, int(timeout * 1000)))
        else:
            wait, before_root, observation_error = _wait_windows_root_with_job_sample(process, command_deadline, accounting)
            auxiliary["pre_root_total"] = before_root[0] if before_root is not None else None
            if observation_error is not None:
                auxiliary["pre_root_observation_error"] = observation_error
        if wait == _winapi.WAIT_TIMEOUT:
            raise command_timeout()
        if wait != _winapi.WAIT_OBJECT_0:
            raise SDKProcessError("sdk_wait", f"Unexpected process wait result: {wait}")
        record["exit_code"] = _winapi.GetExitCodeProcess(process)
        record["root_waited"] = True
        # A real signal proves exit, not that it was observed by our deadline.
        # This check covers sliced, zero and accounting-error fallback waits.
        if policy_budget_expired():
            raise command_timeout()
        if record["exit_code"] != 0:
            error = SDKProcessError("sdk_command", f"SDK command naturally exited with {record['exit_code']}")
        # A signalled process handle may precede the Job accounting decrement.
        # After exit 0, let owned tail work finish naturally, within both the
        # command budget and a short post-root cap. Keep the old nonzero grace.
        started = time.monotonic()
        cap = started + (5.0 if error is None else .5)
        deadline = min(cap, command_deadline) if error is None else cap
        drain = record["job_post_root_drain"] = {
            "budget_seconds": max(0.0, deadline - started),
            "limit": "command_timeout" if deadline < cap else "post_root_cap",
            "last_active": None, "outcome": "unknown",
        }
        try:
            first = last = accounting()
            if pinned is not None:
                auxiliary["root_signal_total"] = first[0]
            count = record["active_after_root_signal"] = drain["last_active"] = first[1]
            while count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(.01, remaining))
                if time.monotonic() >= deadline:
                    break
                observed = accounting()
                if time.monotonic() > deadline:
                    break  # a late observation can prove cleanup, not timely natural drain
                last = observed
                count = drain["last_active"] = observed[1]
            if error is None and policy_budget_expired():
                drain["outcome"] = "command_timeout"
                raise command_timeout()
            drain["outcome"] = "deadline" if count else "empty"
        finally:
            drain["elapsed_seconds"] = time.monotonic() - started
        if count:
            residual = SDKProcessError("sdk_descendants_remaining", "Owned Job was not observed empty before the post-root drain deadline")
            raise residual
        if pinned is None:
            record["job_drain_completion"] = "natural"
    except BaseException as exc:
        if error is not None:
            _cleanup_error(record, "post_exit", exc)
        error = error or exc
    finally:
        settling_persisted = False
        try:
            settling()
            settling_persisted = True
        except BaseException as exc:
            _cleanup_error(record, "guard_settling", exc)
            error = error or exc
        if (pinned is not None and residual is not None and error is residual and settling_persisted
                and record["root_waited"] and record["exit_code"] == 0):
            try:
                if policy_budget_expired():
                    auxiliary.update(status="rejected", reason={"message": "Command budget expired before auxiliary cleanup"})
                    error = command_timeout()
                elif before_root is None:
                    auxiliary.update(status="rejected", reason={"message": "No Job accounting sampled with an unsignaled root"})
                elif before_root[0] != first[0]:
                    auxiliary.update(status="rejected", reason={"message": "Job total changed across the root-signal observation interval"})
                elif first[0] != last[0]:
                    auxiliary.update(status="rejected", reason={"message": "New member joined after root signal"})
                else:
                    reclaim_deadline = min(command_deadline, time.monotonic() + 5)
                    auxiliary_api.reclaim(k, job, process, pid, accounting, last, msvc_auxiliary, pinned,
                                          reclaim_deadline, auxiliary)
                    if auxiliary["status"] == "targets_waited" and auxiliary["handles_closed"]:
                        while time.monotonic() < reclaim_deadline:
                            observed = accounting()
                            if time.monotonic() >= reclaim_deadline or observed[0] != last[0]:
                                break
                            if observed[1] == 0:
                                targets_verified = True
                                break
                            time.sleep(max(0., min(.02, reclaim_deadline - time.monotonic())))
                        if not targets_verified:
                            auxiliary.update(status="rejected", reason={"message": "Stable empty Job not proven within budget"})
                    if policy_budget_expired():
                        targets_verified = False
                        auxiliary.update(status="rejected", reason={"message": "Command budget expired during auxiliary cleanup"})
                        error = command_timeout()
            except BaseException as exc:
                auxiliary["status"] = "rejected"
                _cleanup_error(record, "msvc_auxiliary_cleanup", exc)
        try:
            if process is not None:
                if assigned:
                    before_cleanup = accounting()
                    if targets_verified and before_cleanup != (last[0], 0):
                        targets_verified = False
                        auxiliary.update(status="rejected", reason={"message": "Job accounting changed after targeted cleanup"})
                    if before_cleanup[1]:
                        record["job_termination_requested"] = True
                        _win_check(k.TerminateJobObject(job, 1))
                elif _winapi.WaitForSingleObject(process, 0) == _winapi.WAIT_TIMEOUT:
                    _winapi.TerminateProcess(process, 1)
                wait = _winapi.WaitForSingleObject(process, 10000)
                record["root_waited"] = wait == _winapi.WAIT_OBJECT_0
                if not record["root_waited"]:
                    raise SDKProcessError("sdk_cleanup_unknown", "Owned root did not signal after termination")
                record["exit_code"] = _winapi.GetExitCodeProcess(process)
            else:
                record["root_waited"] = True
            if job is not None:
                deadline = time.monotonic() + 5
                final_accounting = accounting()
                while final_accounting[1] and time.monotonic() < deadline:
                    time.sleep(0.02)
                    final_accounting = accounting()
                remaining_processes = final_accounting[1]
                if targets_verified and final_accounting != (last[0], 0):
                    targets_verified = False
                    auxiliary.update(status="rejected", reason={"message": "Final Job accounting changed"})
                record["active_processes_after"] = remaining_processes
                record["container_empty"] = remaining_processes == 0
                record["container_empty_source"] = "held JobObjectBasicAccountingInformation.ActiveProcesses"
            else:
                record["container_empty"] = not record["spawned"]
                record["container_empty_source"] = "no container or child created in current host"
        except BaseException as exc:
            _cleanup_error(record, "process_settle", exc)
            error = error or exc
        closed = auxiliary is None or auxiliary.get("handles_closed", True)
        for label, handle in [("stdout_or_stdin_duplicate", h) for h in duplicates] + [
                ("thread", thread), ("process", process), ("job", job)]:
            if handle is not None:
                try:
                    _winapi.CloseHandle(handle)  # each owned handle attempted exactly once
                except BaseException as exc:
                    closed = False
                    _cleanup_error(record, "close_" + label, exc)
                    error = error or exc
        if pinned is not None:
            try:
                pinned.close()
            except BaseException as exc:
                closed = False
                _cleanup_error(record, "close_msvc_auxiliary_image", exc)
                error = error or exc
        record["handles_closed"] = closed
        reclaimed = (targets_verified and closed and record["container_empty"] and record["root_waited"]
                     and record["exit_code"] == 0 and not record["cleanup_errors"] and not record["job_termination_requested"])
        # Settling, readback and handle closes may consume the last of the
        # budget. Do not publish either kind of late completion as success.
        if (error is None or reclaimed) and policy_budget_expired():
            if reclaimed:
                auxiliary.update(status="rejected", reason={"message": "Command budget expired before completion"})
            error = command_timeout()
        elif reclaimed:
            auxiliary["status"] = "verified"
            record["job_drain_completion"] = "known_msvc_auxiliary_reclaimed"
            error = None
        elif pinned is not None and error is None and record["container_empty"] and closed:
            record["job_drain_completion"] = "natural"
    if error is not None:
        raise error


def _group_members(pgid):
    members = []
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            try:
                item = _linux_process(int(path.name))
            except FileNotFoundError:
                continue
            if item["pgid"] == pgid:
                members.append(item)
    return members  # permission/parse failures deliberately propagate as unknown


def _posix_command(argv, cwd, env, output, timeout, record, owned, running, settling):
    process = None
    error = None
    record.update(log_transport="parent_pipe", pipe_eof=False, pipe_reader_closed=False, pipe_write_failed=False)

    def drain(delay=0):
        # The actual log descriptor is parent-only. Bound each drain batch so a
        # continuously writing child cannot starve timeout/cancellation checks.
        if process is None or process.stdout is None or record["pipe_eof"]:
            if delay:
                time.sleep(delay)
            return
        import select
        if not select.select([process.stdout], [], [], delay)[0]:
            return
        for _ in range(64):
            try:
                data = os.read(process.stdout.fileno(), 65536)
            except BlockingIOError:
                break
            if not data:
                record["pipe_eof"] = True  # only actual zero-byte read proves EOF
                break
            if not record["pipe_write_failed"]:
                try:
                    if output.write(data) != len(data):
                        raise OSError("Short SDK log write")
                except BaseException:
                    record["pipe_write_failed"] = True
                    raise

    try:
        if not hasattr(os, "WNOWAIT") or not Path("/proc/self/stat").is_file():
            raise SDKProcessError("sdk_process_unsupported", "Linux /proc and waitid WNOWAIT are required")
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, close_fds=True, start_new_session=True, bufsize=0)
        record["spawned"] = True
        os.set_blocking(process.stdout.fileno(), False)
        identity = _linux_process(process.pid)
        record["root_child"] = {"pid": process.pid, "creation": identity["creation"]}
        record["container"] = {"kind": "posix_process_group", "pgid": process.pid,
                               "session": identity["session"], "creation": identity["creation"],
                               "boot_identity": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
        if identity["pgid"] != process.pid or identity["session"] != process.pid:
            raise SDKProcessError("sdk_group_identity", "Child did not enter its owned session/group")
        record["resumed"] = True
        running()  # POSIX has no suspended/Job assignment claim
        deadline = time.monotonic() + timeout
        while True:
            drain()
            observed_exit = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if observed_exit is not None:
                break
            if time.monotonic() >= deadline:
                raise SDKProcessError("sdk_timeout", "SDK command exceeded its timeout")
            drain(0.02)
        natural_code = observed_exit.si_status if observed_exit.si_code == os.CLD_EXITED else -observed_exit.si_status
        record["exit_code"] = natural_code
        if natural_code != 0:
            error = SDKProcessError("sdk_command", f"SDK command naturally exited with {natural_code}")
        # Keep the unreaped leader identity until all group signalling is done.
        if any(member["pid"] != process.pid for member in _group_members(process.pid)):
            raise SDKProcessError("sdk_descendants_remaining", "Root exited while owned group members remain")
    except BaseException as exc:
        if error is not None:
            _cleanup_error(record, "post_exit", exc)
        error = error or exc
    finally:
        try:
            settling()
        except BaseException as exc:
            _cleanup_error(record, "guard_settling", exc)
            error = error or exc
        try:
            if process is not None:
                current = _linux_process(process.pid)
                expected = record.get("root_child")
                if expected is None or current["creation"] != expected["creation"] or current["pgid"] != process.pid:
                    raise SDKProcessError("sdk_cleanup_unknown", "Unreaped leader identity could not be established")
                members = _group_members(process.pid)
                if any(item["state"] != "Z" for item in members):
                    os.killpg(process.pid, signal.SIGTERM)
                    deadline = time.monotonic() + 2
                    drain_failed = False
                    while any(item["state"] != "Z" for item in _group_members(process.pid)) and time.monotonic() < deadline:
                        # Output transport is independent of owned-process
                        # termination. A read/write failure must not skip KILL
                        # or reap; record it once and stop retrying in this loop.
                        if drain_failed:
                            time.sleep(0.02)
                        else:
                            try:
                                drain(0.02)
                            except BaseException as exc:
                                _cleanup_error(record, "log_pipe_during_terminate", exc)
                                error = error or exc
                                drain_failed = True
                    if any(item["state"] != "Z" for item in _group_members(process.pid)):
                        os.killpg(process.pid, signal.SIGKILL)
                record["exit_code"] = process.wait(timeout=5)
                record["root_waited"] = True
                remaining = _group_members(process.pid)
                record["remaining_group_members"] = remaining
                record["container_empty"] = not remaining
                record["container_empty_source"] = "same-host owned session/group /proc scan after root reap"
            else:
                record.update(root_waited=True, container_empty=True, container_empty_source="no child created in current host")
        except BaseException as exc:
            _cleanup_error(record, "process_settle", exc)
            error = error or exc
        # Empty process group does not prove that detached inherited pipe
        # writers stopped. Wait only for a bounded real EOF; never kill them.
        try:
            if process is None:
                record["pipe_eof"] = True  # no writer/pipe was created
            else:
                deadline = time.monotonic() + .5
                while not record["pipe_eof"] and time.monotonic() < deadline:
                    drain(.02)
                if not record["pipe_eof"]:
                    raise SDKProcessError("sdk_log_writers_unknown", "SDK output pipe has no EOF; inherited writers may remain")
        except BaseException as exc:
            _cleanup_error(record, "log_pipe", exc)
            error = error or exc
        finally:
            try:
                if process is not None and process.stdout is not None:
                    process.stdout.close()  # exactly one parent-owned read endpoint
                record["pipe_reader_closed"] = True
            except BaseException as exc:
                _cleanup_error(record, "log_pipe_close", exc)
                error = error or exc
        record["handles_closed"] = record["pipe_reader_closed"]
    if error is not None:
        raise error


def run_owned(argv, *, cwd, env, output, timeout, record, owned, running, settling, msvc_auxiliary=None):
    record.update(spawned=False, resumed=False, root_waited=False, container_empty=False,
                  handles_closed=False, exit_code=None, root_child=None, container=None, cleanup_errors=[])
    function = _windows_command if os.name == "nt" else _posix_command
    options = {"msvc_auxiliary": msvc_auxiliary} if os.name == "nt" and msvc_auxiliary is not None else {}
    function(list(map(str, argv)), cwd, env, output, timeout, record, owned, running, settling, **options)
    if not all(record.get(key) for key in ("root_waited", "container_empty", "handles_closed")):
        raise SDKProcessError("sdk_cleanup_unknown", "Owned process/container cleanup is not proven")
