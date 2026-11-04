#!/usr/bin/env python3
"""Probe whether an X display actually accepts client connections.

The R3 launcher waited for the filesystem socket `/tmp/.X11-unix/X<n>`.  On a
system where that directory is not writable by the VNC user, TigerVNC reports
"failed to create listener for unix" yet still registers the display through the
Linux abstract socket namespace (and/or keeps the VNC port open).  Checking the
file alone therefore produces a false negative.

This probe is read-only and bounded:
  * it connects to the abstract socket name ``\\0/tmp/.X11-unix/X<n>`` (the name
    the X server uses on Linux when the filesystem socket cannot be created);
  * it connects to the filesystem socket path when it exists;
  * it runs ``xdpyinfo -display :<n>`` with a timeout when xdpyinfo exists;
  * it reports each result as JSON and exits 0 only when a real client
    connection succeeded (socket connect or xdpyinfo success).

It never starts, stops or reconfigures a display server.
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ABSTRACT_TEMPLATE = "\0/tmp/.X11-unix/X{display}"
FILESYSTEM_TEMPLATE = "/tmp/.X11-unix/X{display}"


def connect_unix(name: str, timeout: float) -> tuple[bool, str | None]:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(name)
        return True, None
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        sock.close()


def run_xdpyinfo(display: int, timeout: float) -> dict:
    executable = shutil.which("xdpyinfo")
    if executable is None:
        return {"available": False, "connected": False, "returncode": None,
                "stderr_tail": "xdpyinfo not found", "duration_s": 0.0}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [executable, "-display", f":{display}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"available": True, "connected": False, "returncode": None,
                "stderr_tail": f"timeout after {timeout:g}s",
                "duration_s": round(time.monotonic() - started, 3)}
    stderr = (completed.stderr or "").strip()
    return {
        "available": True,
        "connected": completed.returncode == 0,
        "returncode": completed.returncode,
        "stderr_tail": stderr[-400:],
        "duration_s": round(time.monotonic() - started, 3),
    }


def probe(display: int, timeout: float) -> dict:
    abstract_name = ABSTRACT_TEMPLATE.format(display=display)
    filesystem_path = Path(FILESYSTEM_TEMPLATE.format(display=display))
    abstract_ok, abstract_error = connect_unix(abstract_name, timeout)
    filesystem_ok = False
    filesystem_error: str | None = None
    if filesystem_path.exists():
        filesystem_ok, filesystem_error = connect_unix(str(filesystem_path), timeout)
    else:
        filesystem_error = "socket file does not exist"
    xdpyinfo = run_xdpyinfo(display, timeout)
    connected = abstract_ok or filesystem_ok or xdpyinfo["connected"]
    errors = []
    if not abstract_ok:
        errors.append(f"abstract: {abstract_error}")
    if not filesystem_ok:
        errors.append(f"filesystem: {filesystem_error}")
    if not xdpyinfo["connected"]:
        errors.append(f"xdpyinfo: {xdpyinfo['stderr_tail']}")
    return {
        "display": f":{display}",
        "abstract_socket": abstract_ok,
        "abstract_error": abstract_error,
        "filesystem_socket": filesystem_ok,
        "filesystem_path": str(filesystem_path),
        "filesystem_present": filesystem_path.exists(),
        "filesystem_error": filesystem_error,
        "xdpyinfo": xdpyinfo,
        "connected": connected,
        "error": None if connected else "; ".join(errors),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--display", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args(argv)
    result = probe(args.display, args.timeout)
    text = json.dumps(result, indent=2)
    if args.json_path:
        Path(args.json_path).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["connected"] else 1


if __name__ == "__main__":
    sys.exit(main())
