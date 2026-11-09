"""Narrow, same-host Windows SDK compile cleanup. No process discovery by name."""
from __future__ import annotations

import ctypes as c
from ctypes import wintypes as w
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time


@dataclass(frozen=True)
class Policy:
    image: Path
    sha256: str


def _discover_instances(argv, cwd, *, timeout=4):
    from . import _install_sdk_process as adapter
    record = {}

    def local_only():
        pass  # independent discovery Job; no SDK guard and no auxiliary policy

    limit = 64 * 1024
    with tempfile.TemporaryFile(mode="w+b") as output:
        adapter.run_owned(argv, cwd=cwd, env=os.environ.copy(), output=output, timeout=timeout,
                          record=record, owned=local_only, running=local_only, settling=local_only)
        if record["exit_code"] != 0 or record["cleanup_errors"]:
            raise RuntimeError("Visual Studio discovery did not settle cleanly")
        output.seek(0)
        raw = output.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("Visual Studio discovery output exceeds limit")
    instances = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(instances, list):
        raise ValueError("Visual Studio discovery did not return an instance list")
    return instances


def prepare(compiler):
    """Trust only an explicit cl.exe in a registered Visual Studio MSVC tree."""
    if os.name != "nt" or compiler is None or compiler.name.lower() != "cl.exe":
        return None
    try:
        folder = c.create_unicode_buffer(260)
        # CSIDL_PROGRAM_FILESX86: do not run a PATH or environment-selected vswhere.
        if c.WinDLL("shell32").SHGetFolderPathW(None, 0x002a, None, 0, folder):
            return None
        locator = Path(folder.value) / "Microsoft Visual Studio/Installer/vswhere.exe"
        if not locator.is_absolute() or locator.resolve(strict=True) != locator:
            return None
        instances = _discover_instances([str(locator), "-prerelease", "-products", "*", "-requires",
                                         "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                                         "-format", "json", "-utf8"], locator.parent)
        for instance in instances:
            if instance.get("isComplete") is not True or instance.get("isLaunchable") is not True:
                continue
            root = Path(instance["installationPath"])
            if not root.is_absolute() or not compiler.is_relative_to(root.resolve(strict=True)):
                continue
            parts = compiler.relative_to(root.resolve(strict=True)).as_posix()
            if not re.fullmatch(r"VC/Tools/MSVC/[0-9.]+/bin/Host(?:x64|x86|arm64)/(?:x64|x86|arm64|arm)/cl\.exe", parts, re.I):
                continue
            image = compiler.with_name("vctip.exe")
            if image.resolve(strict=True) != image or not image.is_file():
                return None
            with image.open("rb") as stream:
                return Policy(image, hashlib.file_digest(stream, "sha256").hexdigest())
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, AttributeError):
        return None
    return None


def pin(policy):
    """Hold a read-only file handle denying writes/deletes through the command."""
    import msvcrt
    import _winapi
    k = c.WinDLL("kernel32", use_last_error=True)
    create = k.CreateFileW
    create.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
    create.restype = w.HANDLE
    h = create(str(policy.image), 0x80000000, 1, None, 3, 0x80, None)
    if h == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(h, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        _winapi.CloseHandle(h)
        raise
    try:
        stream = os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise
    try:
        if not _bound_path(policy, stream) or hashlib.file_digest(stream, "sha256").hexdigest() != policy.sha256:
            raise RuntimeError("MSVC auxiliary file identity differs")
        return stream
    except BaseException:
        stream.close()
        raise


def _bound_path(policy, stream):
    return (policy.image.resolve(strict=True) == policy.image
            and os.path.samestat(policy.image.stat(), os.fstat(stream.fileno())))


def _require(value, message):
    if not value:
        raise RuntimeError(message)


def _checked(value):
    if not value:
        raise c.WinError(c.get_last_error())
    return value


def _times(k, process):
    times = [c.c_uint64() for _ in range(4)]
    _checked(k.GetProcessTimes(process, *(c.byref(t) for t in times)))
    return [t.value for t in times]


def _pid_array(k, job):
    # winnt.h JOBOBJECT_BASIC_PROCESS_ID_LIST; info class 3.
    class Pids(c.Structure):
        _fields_ = [("assigned", w.DWORD), ("listed", w.DWORD), ("values", c.c_size_t * 32)]

    ids, length = Pids(), w.DWORD()
    _checked(k.QueryInformationJobObject(job, 3, c.byref(ids), c.sizeof(ids), c.byref(length)))
    _require(ids.assigned == ids.listed <= 32 and
             Pids.values.offset + ids.listed * c.sizeof(c.c_size_t) <= length.value <= c.sizeof(ids),
             "Incomplete Job PID list")
    values = set(ids.values[:ids.listed])
    _require(len(values) == ids.listed and all(0 < pid <= 0xffffffff for pid in values), "Invalid Job PID list")
    return values


def reclaim(k, job, root, root_pid, accounting, expected, policy, stream, deadline, result):
    """Target only retained handles after a complete, stable same-Job census."""
    import _winapi
    total, count = expected
    handles = []
    result.update(status="rejected", members=[], handles_closed=True, expected_total=total)
    try:
        for name, args, restype in (
            ("OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            ("IsProcessInJob", [w.HANDLE, w.HANDLE, c.POINTER(w.BOOL)], w.BOOL),
            ("QueryFullProcessImageNameW", [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)], w.BOOL),
        ):
            fn = getattr(k, name)
            fn.argtypes, fn.restype = args, restype
        root_exit = _times(k, root)[1]
        _require(root_exit, "Missing root exit time")
        result["root_exit_filetime"] = str(root_exit)
        image = c.create_unicode_buffer(32768)

        def within_budget():
            _require(time.monotonic() < deadline, "Auxiliary cleanup budget exhausted")

        def check_handle(handle, row, existing):
            within_budget()
            member = w.BOOL()
            _checked(k.IsProcessInJob(handle, job, c.byref(member)))
            _require(member.value, "Retained handle is not in held Job")
            creation = _times(k, handle)[0]
            _require(0 < creation <= root_exit and (not existing or str(creation) == row["creation_filetime"]),
                     "New or unverified Job member creation identity")
            row["creation_filetime"] = str(creation)
            size = w.DWORD(len(image))
            _checked(k.QueryFullProcessImageNameW(handle, 0, image, c.byref(size)))
            path = Path(image[:size.value])
            row["image"] = str(path)
            _require(path == policy.image and _bound_path(policy, stream), "Job member image is outside bound policy")
            _require(_winapi.WaitForSingleObject(handle, 0) == _winapi.WAIT_TIMEOUT,
                     "Member not observed active on retained handle")
            row["identity_verified"] = True

        def stable_list(pids=None):
            within_budget()
            _require(accounting() == (total, count), "Job accounting changed before enumeration")
            observed = _pid_array(k, job)
            _require(len(observed) == count and root_pid not in observed and
                     accounting() == (total, count) and (pids is None or observed == pids),
                     "Job membership changed or cannot be established")
            return observed

        pids = stable_list()
        result["pid_list"] = sorted(pids)
        for pid in sorted(pids):
            # QUERY_LIMITED_INFORMATION | SYNCHRONIZE | TERMINATE
            handle = _checked(k.OpenProcess(0x1000 | 0x00100000 | 1, False, pid))
            row = {"pid": pid, "termination_requested": False, "exit_observed": False}
            handles.append((handle, row))
            result["members"].append(row)
            check_handle(handle, row, False)
        stable_list(pids)
        for handle, row in handles:
            check_handle(handle, row, True)
        stable_list(pids)  # all identities checked before any signal
        for handle, row in handles:
            check_handle(handle, row, True)
            _require(accounting()[0] == total, "New member joined the Job")
            within_budget()
            row["termination_requested"] = True
            _winapi.TerminateProcess(handle, 1)
        for handle, row in handles:
            within_budget()
            wait = _winapi.WaitForSingleObject(handle, max(0, int((deadline - time.monotonic()) * 1000)))
            _require(wait == _winapi.WAIT_OBJECT_0, "Targeted auxiliary did not signal")
            within_budget()
            row["exit_observed"] = True
            row["exit_code"] = _winapi.GetExitCodeProcess(handle)
        _require(accounting()[0] == total, "New member joined during targeted termination")
        result["status"] = "targets_waited"
    except Exception as exc:
        result["reason"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        for handle, row in handles:
            try:
                _winapi.CloseHandle(handle)
            except Exception as exc:
                result["handles_closed"] = False
                row["close_error"] = str(exc)
