#!/usr/bin/env python3
"""PID-bound RSS observer for the F3-2 memory phase (preflight tool, not product code).

This is an ordinary Python child process launched by the measurement script.  It
binds to exactly one OS process by PID *and* verifies that process image path,
creation time and executable SHA-256 match the identity supplied by the launcher
before recording any sample, so it cannot absorb a same-named process, an
ancestor accumulator, or another task's memory.  It samples WorkingSet64 /
PeakWorkingSet64 every ~100 ms.  The process-handle exit status decides between
a normal exit, a timeout while the process is still alive, and a failed liveness
query; the latter two are reported with a non-zero exit code instead of being
mistaken for success.  Every successful working-set reading (first, loop and
final) contributes to the reported maxima, and an unavailable final query is
recorded as a failure flag rather than zero.

Exit codes: 0 = sampled until a normal exit; 3 = identity mismatch;
4 = process could not be opened / first sample failed; 5 = unsupported platform;
6 = timeout while the process was still alive; 7 = liveness query failed.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x10
STILL_ACTIVE = 259
MAX_CONSECUTIVE_FAILURES = 3


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def filetime_to_utc(value):
    seconds = value / 10_000_000.0 - 11_644_473_600.0
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def image_path(kernel32, handle):
    size = wintypes.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(size.value)
    if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
        return ""
    return buffer.value


def creation_filetime(kernel32, handle):
    created = wintypes.FILETIME()
    exited = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()
    if not kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                    ctypes.byref(kernel), ctypes.byref(user)):
        return None
    return (created.dwHighDateTime << 32) | created.dwLowDateTime


def memory_info(psapi, handle):
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return None
    return {"working_set_bytes": int(counters.WorkingSetSize),
            "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
            "pagefile_usage_bytes": int(counters.PagefileUsage)}


def exit_code_of(kernel32, handle):
    code = wintypes.DWORD()
    if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
        return None
    return int(code.value)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def maxima(samples):
    if not samples:
        return {"peak_working_set_bytes": None, "os_peak_working_set_bytes": None}
    return {
        "peak_working_set_bytes": max(sample["working_set_bytes"] for sample in samples),
        "os_peak_working_set_bytes": max(sample["peak_working_set_bytes"] for sample in samples),
    }


def intervals(samples):
    gaps = []
    for previous, current in zip(samples, samples[1:]):
        gaps.append(round(current["t_s"] - previous["t_s"], 6))
    return {"min": min(gaps) if gaps else None,
            "max": max(gaps) if gaps else None,
            "mean": (sum(gaps) / len(gaps)) if gaps else None}


def write_payload(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--expected-exe", default=None,
                        help="required in production; only synthetic controls omit it")
    parser.add_argument("--expected-creation-filetime", type=int, default=None,
                        help="required in production; omitted only by synthetic time-source controls")
    parser.add_argument("--expected-exe-sha256", default=None)
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args(argv)
    if os.name != "nt":
        print("pid_observer: this F3-2 observer only supports Windows", file=sys.stderr)
        return 5

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                                    wintypes.LPWSTR,
                                                    ctypes.POINTER(wintypes.DWORD))
    kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                         ctypes.POINTER(wintypes.FILETIME),
                                         ctypes.POINTER(wintypes.FILETIME),
                                         ctypes.POINTER(wintypes.FILETIME))
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD)
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    expected_exe = os.path.normcase(os.path.abspath(args.expected_exe)) if args.expected_exe else None
    started_utc = utc_now()
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False,
                                  args.pid)
    if not handle:
        write_payload(args.output, {
            "schema": "g4usim_pid_observer_v1", "pid": args.pid,
            "expected_exe": expected_exe, "status": "open_failed",
            "error_code": ctypes.get_last_error(), "samples": [],
            "final_query_ok": False, "final_working_set_bytes": None,
            "started_utc": started_utc, "finished_utc": utc_now(),
        })
        print("pid_observer: OpenProcess failed", file=sys.stderr)
        return 4
    try:
        observed_exe = image_path(kernel32, handle)
        expected_exe = (os.path.normcase(os.path.abspath(args.expected_exe))
                        if args.expected_exe else os.path.normcase(os.path.abspath(observed_exe)))
        observed_created = creation_filetime(kernel32, handle)
        try:
            observed_sha = sha256_file(observed_exe) if observed_exe else None
        except OSError:
            observed_sha = None
        bound = (args.expected_creation_filetime is not None
                 and args.expected_exe_sha256 is not None)
        identity_ok = True
        if bound:
            identity_ok = (
                os.path.normcase(os.path.abspath(observed_exe)) == expected_exe
                and observed_created == args.expected_creation_filetime
                and observed_sha is not None
                and observed_sha.lower() == args.expected_exe_sha256.lower())
        base = {
            "schema": "g4usim_pid_observer_v1", "pid": args.pid,
            "expected_exe": expected_exe, "observed_exe": observed_exe,
            "expected_creation_filetime": args.expected_creation_filetime,
            "observed_creation_filetime": observed_created,
            "creation_utc": filetime_to_utc(observed_created) if observed_created else None,
            "expected_exe_sha256": (args.expected_exe_sha256 or "").lower() or None,
            "observed_exe_sha256": observed_sha,
            "identity_ok": identity_ok, "identity_bound": bound,
            "interval_target_s": args.interval,
            "started_utc": started_utc,
        }
        if not identity_ok:
            payload = dict(base, status="identity_mismatch", samples=[],
                           sample_count=0, final_query_ok=False,
                           final_working_set_bytes=None,
                           peak_working_set_bytes=None,
                           os_peak_working_set_bytes=None,
                           finished_utc=utc_now())
            write_payload(args.output, payload)
            print(f"pid_observer: PID {args.pid} does not match the expected backend identity",
                  file=sys.stderr)
            return 3

        started = time.perf_counter()
        samples = []
        failures = 0
        status = "completed"
        first = memory_info(psapi, handle)
        if first is None:
            payload = dict(base, status="first_sample_failed", samples=[],
                           sample_count=0, final_query_ok=False,
                           final_working_set_bytes=None,
                           peak_working_set_bytes=None,
                           os_peak_working_set_bytes=None,
                           finished_utc=utc_now())
            write_payload(args.output, payload)
            print("pid_observer: first memory sample failed", file=sys.stderr)
            return 4
        samples.append({"t_s": 0.0, **first})
        while True:
            now = time.perf_counter() - started
            exit_code = exit_code_of(kernel32, handle)
            if exit_code is not None and exit_code != STILL_ACTIVE:
                status = "completed"
                break
            info = memory_info(psapi, handle)
            if info is None:
                failures += 1
                if failures > MAX_CONSECUTIVE_FAILURES:
                    status = "query_failed"
                    break
            else:
                failures = 0
                samples.append({"t_s": round(now, 6), **info})
            if now > args.timeout:
                status = "timeout"
                break
            time.sleep(max(args.interval, 0.01))
        final = memory_info(psapi, handle)
        final_query_ok = final is not None
        if final is not None:
            duration_now = time.perf_counter() - started
            samples.append({"t_s": round(duration_now, 6),
                            "working_set_bytes": final["working_set_bytes"],
                            "peak_working_set_bytes": final["peak_working_set_bytes"],
                            "pagefile_usage_bytes": final["pagefile_usage_bytes"]})
        maximums = maxima(samples)
        exit_code = exit_code_of(kernel32, handle)
        payload = dict(
            base, status=status, sample_count=len(samples), samples=samples,
            interval_actual_s=intervals(samples),
            **maximums,
            final_query_ok=final_query_ok,
            final_working_set_bytes=final["working_set_bytes"] if final else None,
            last_success=samples[-1] if samples else None,
            process_exit_code=exit_code,
            process_alive_at_end=(exit_code == STILL_ACTIVE) if exit_code is not None else None,
            duration_s=round(time.perf_counter() - started, 6),
            finished_utc=utc_now(),
        )
        write_payload(args.output, payload)
        if status == "timeout":
            print(f"pid_observer: PID {args.pid} still alive after {args.timeout} s",
                  file=sys.stderr)
            return 6
        if status == "query_failed":
            print(f"pid_observer: PID {args.pid} liveness/memory query failed", file=sys.stderr)
            return 7
        return 0
    finally:
        kernel32.CloseHandle(handle)


if __name__ == "__main__":
    sys.exit(main())
