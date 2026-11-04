#!/usr/bin/env python3
"""Preflight for the isolated Linux X11 verification host (J3 R2).

This script only *reads* the environment: it never starts Xvnc, twm, websockify
or the GUI, never touches an existing display, and never writes outside this
kit directory (``preflight.json``).  A green preflight therefore means "the
launch kit can be executed", not "a window was verified".

Run with the system python3 (standard library only)::

    python3 out/collab/j3-linux-candidate-r2/preflight.py

Exit status: 0 = every check passed, 3 = at least one check failed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

KIT = Path(__file__).resolve().parent
REPO = Path(os.environ.get("G4USIM_REPO", KIT.parents[2]))
ASSETS = Path(
    os.environ.get(
        "J3_R2_ASSETS",
        "/mnt/c/Users/123/.codex/worktrees/effective-config/G4UniversalSim/out/collab",
    )
)
DEDICATED = ASSETS / "l1-linux-dedicated-xvnc-assets-246" / "root"
SHARED = ASSETS / "l1-linux-existing-window-vnc-246" / "root"

def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


# The launcher exports these before invoking preflight, so both sides always
# check the same display/ports even when the defaults are overridden.
DISPLAY_NUM = _int_env("J3_R2_DISPLAY", 94)
RFB_PORT = _int_env("J3_R2_RFB_PORT", 5910)
WEB_PORT = _int_env("J3_R2_WEB_PORT", 6090)
GUI_PYTHON = Path(
    os.environ.get("J3_R2_GUI_PYTHON", "/home/u123/venvs/g4-j3-native-20261103/bin/python")
)
GUI_LIBS = Path(os.environ.get("J3_R2_GUI_LIBS", "/home/u123/g4gui-libs/usr/lib/x86_64-linux-gnu"))
THIN_ENTRY = REPO / "out/collab/j3-production-startup-r1/start_production.py"

EXPECTED_HEAD = "864bc036d6d7752475e52db4efd2b950cabfcc3d"
EXPECTED_FILES = {
    "gui/smoke_tests/smoke_config_agent_panel.py": "713619a3848e2637702396c824042f9c7ffccccf62e61b7bcf864b49a05b467e",
    "gui/smoke_tests/smoke_theme_state.py": "beb0f0d68753b19f6418175f8749ce414c00e0a4e1a921960bda65b564fff181",
    "gui/g4usim_gui/window/workspace_layout.py": "da297463859f4513202f3667673d2bd6abf1b58d1df1328076c5995b12909918",
    "gui/smoke_tests/smoke_workspace_layout.py": "1b91a27f767e996400ec2780e37e943f1ae881877b682a6a2acee525344bb778",
    "gui/g4usim_gui/core/fonts.py": "78432cc6774110706404572498ce786fea0cd5a81b6bfc2f4a24872d38609241",
    "gui/g4usim_gui/preview3d/pyvista_preview_widget.py": "d7a9dcffb620c6c245856b4f88ac618b03bbc4d6c34525fd479225f636dc422e",
    "gui/smoke_tests/smoke_vtk_axes_theme.py": "22030597e3028d59da54beb2e08ac10546d022272e0a2c8dd74215f12651fb58",
    "scripts/run_m0_tests.py": "5b8e6c62e9b5f8f2e62bb6043a9505ee7c5e4a43e12742a90e06721995ce2b8f",
    ".github/workflows/m0-static-gui.yml": "cf8e17c3920c3652cd82db991a377a6ab205f5edbeb12f2502add5a570a843a0",
    ".github/workflows/linux-geant4.yml": "b19365cf4f4e2179e1d0736f8d18651a6675b9709c8f91070f314bff1549640d"
}
EXPECTED_STATUS = []


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: list[str], *, env: dict[str, str] | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, **(env or {})},
    )


def check_repo() -> dict:
    ok = REPO.is_dir() and (REPO / "gui/g4usim_gui/main_window.py").is_file()
    return {"passed": ok, "detail": str(REPO)}


def check_source_identity() -> dict:
    head = run(["git", "-C", str(REPO), "rev-parse", "HEAD"])
    head_value = head.stdout.strip()
    status = run(["git", "-C", str(REPO), "status", "--porcelain", "--", "gui", "scripts", ".github"])
    lines = [line for line in status.stdout.splitlines() if line.strip()]
    files = {}
    for rel, expected in EXPECTED_FILES.items():
        path = REPO / rel
        files[rel] = {"expected": expected, "actual": sha256(path) if path.is_file() else None}
    mismatched = sorted(rel for rel, row in files.items() if row["actual"] != row["expected"])
    ok = (
        head.returncode == 0
        and head_value == EXPECTED_HEAD
        and status.returncode == 0
        and lines == EXPECTED_STATUS
        and not mismatched
    )
    return {
        "passed": ok,
        "detail": f"head={head_value} status_entries={len(lines)} mismatched_files={len(mismatched)}",
        "head": head_value,
        "status_entries": lines,
        "mismatched_files": mismatched,
        "files": files,
    }


def check_thin_entry() -> dict:
    exists = THIN_ENTRY.is_file()
    return {
        "passed": exists,
        "detail": str(THIN_ENTRY),
        "sha256": sha256(THIN_ENTRY) if exists else None,
    }


def check_vnc_assets() -> dict:
    bins = {
        "Xtigervnc": DEDICATED / "usr/bin/Xtigervnc",
        "twm": DEDICATED / "usr/bin/twm",
        "websockify": SHARED / "usr/bin/websockify",
    }
    rows = {
        name: {
            "path": str(path),
            "exists": path.is_file(),
            "executable": os.access(path, os.X_OK),
            "sha256": sha256(path) if path.is_file() else None,
        }
        for name, path in bins.items()
    }
    novnc = SHARED / "usr/share/novnc"
    rows["novnc"] = {"path": str(novnc), "exists": novnc.is_dir()}
    ok = all(row.get("exists") and row.get("executable", True) for row in rows.values())
    return {"passed": ok, "detail": f"{sum(1 for r in rows.values() if r['exists'])}/{len(rows)} assets present", "assets": rows}


def check_vnc_dependencies() -> dict:
    env = {
        "LD_LIBRARY_PATH": str(DEDICATED / "usr/lib/x86_64-linux-gnu"),
    }
    details = {}
    ok = True
    for name, relative in (("Xtigervnc", "usr/bin/Xtigervnc"), ("twm", "usr/bin/twm")):
        binary = DEDICATED / relative
        ldd = run(["ldd", str(binary)], env=env)
        missing = [line.strip() for line in ldd.stdout.splitlines() if "not found" in line]
        version = run([str(binary), "-version"], env=env) if name == "Xtigervnc" else None
        version_text = (version.stdout + version.stderr).strip().splitlines()[:1] if version else []
        details[name] = {
            "missing": missing,
            "version": version_text[0] if version_text else None,
        }
        ok = ok and not missing and ldd.returncode == 0
    xkb = Path("/usr/share/X11/xkb")
    details["xkbdir"] = {"path": str(xkb), "exists": xkb.is_dir()}
    ok = ok and xkb.is_dir()
    return {"passed": ok, "detail": "ldd clean for Xtigervnc/twm; xkbdir present" if ok else "missing libraries or xkbdir", "dependencies": details}


def check_gui_environment() -> dict:
    imports = (
        "import PySide6, pyvista, vtk;"
        "print('PySide6='+PySide6.__version__,"
        "      'pyvista='+pyvista.__version__,"
        "      'vtk='+vtk.vtkVersion.GetVTKVersion())"
    )
    result = run([str(GUI_PYTHON), "-c", imports], timeout=120)
    lib = GUI_LIBS / "libxcb-cursor.so.0"
    python_ok = result.returncode == 0
    ok = python_ok and lib.is_file()
    return {
        "passed": ok,
        "detail": (result.stdout.strip() or result.stderr.strip())
        + f"; gui_libs={'present' if lib.is_file() else 'missing'}",
        "python": str(GUI_PYTHON),
        "gui_libs": {"path": str(lib), "exists": lib.is_file()},
    }


def check_websockify() -> dict:
    pythonpath = SHARED / "usr/lib/python3/dist-packages"
    binary = SHARED / "usr/bin/websockify"
    result = run(
        ["/usr/bin/python3", "-c", "import websockify; print('websockify', websockify.__version__ if hasattr(websockify, '__version__') else 'loaded')"],
        env={"PYTHONPATH": str(pythonpath)},
    )
    return {
        "passed": result.returncode == 0,
        "detail": (result.stdout.strip() or result.stderr.strip()),
        "pythonpath": str(pythonpath),
        "binary": str(binary),
        "novnc": str(SHARED / "usr/share/novnc"),
    }


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def check_parameters() -> dict:
    ok = (
        0 <= DISPLAY_NUM <= 99
        and 1024 <= RFB_PORT <= 65535
        and 1024 <= WEB_PORT <= 65535
        and RFB_PORT != WEB_PORT
    )
    return {
        "passed": ok,
        "detail": f"display=:{DISPLAY_NUM} rfb={RFB_PORT} web={WEB_PORT} (same values launch.sh uses)",
        "source": "environment J3_R2_DISPLAY / J3_R2_RFB_PORT / J3_R2_WEB_PORT",
    }


def check_display_free() -> dict:
    lock = Path(f"/tmp/.X{DISPLAY_NUM}-lock")
    socket_path = Path(f"/tmp/.X11-unix/X{DISPLAY_NUM}")
    pgrep = run(["pgrep", "-af", rf"Xtigervnc :{DISPLAY_NUM}\b"], timeout=10)
    ports = {port: port_free(port) for port in (RFB_PORT, WEB_PORT)}
    ok = not lock.exists() and not socket_path.exists() and pgrep.returncode != 0 and all(ports.values())
    return {
        "passed": ok,
        "detail": f"display=:{DISPLAY_NUM} lock={lock.exists()} socket={socket_path.exists()} ports={ports}",
        "pgrep_stdout": pgrep.stdout.strip(),
        "lock": str(lock),
        "socket": str(socket_path),
        "ports": {str(k): v for k, v in ports.items()},
    }


def check_output_writable() -> dict:
    runs = KIT / "runs"
    try:
        runs.mkdir(parents=True, exist_ok=True)
        probe = runs / ".write-probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        ok = True
        detail = str(runs)
    except OSError as exc:  # pragma: no cover - environment failure
        ok = False
        detail = str(exc)
    return {"passed": ok, "detail": detail}


CHECKS = (
    ("parameters", check_parameters),
    ("repo_root", check_repo),
    ("source_identity", check_source_identity),
    ("thin_entry", check_thin_entry),
    ("vnc_assets", check_vnc_assets),
    ("vnc_dependencies", check_vnc_dependencies),
    ("gui_environment", check_gui_environment),
    ("websockify", check_websockify),
    ("display_free", check_display_free),
    ("output_writable", check_output_writable),
)


def main() -> int:
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    results = {}
    for name, check in CHECKS:
        try:
            results[name] = check()
        except Exception as exc:  # noqa: BLE001 - a failed check must not mask the rest
            results[name] = {"passed": False, "detail": f"{type(exc).__name__}: {exc}"}
    failed = sorted(name for name, row in results.items() if not row["passed"])
    report = {
        "schema": "g4usim_j3_linux_candidate_r2_preflight",
        "started": started,
        "repo": str(REPO),
        "candidate": {
            "head": EXPECTED_HEAD,
            "files": EXPECTED_FILES,
            "status_entries": EXPECTED_STATUS,
        },
        "display": {
            "number": DISPLAY_NUM,
            "rfb_port": RFB_PORT,
            "web_port": WEB_PORT,
            "source": "env J3_R2_DISPLAY / J3_R2_RFB_PORT / J3_R2_WEB_PORT (defaults 94/5910/6090)",
        },
        "assets": {"dedicated": str(DEDICATED), "shared": str(SHARED)},
        "gui_python": str(GUI_PYTHON),
        "thin_entry": str(THIN_ENTRY),
        "checks": results,
        "summary": {"passed": len(results) - len(failed), "failed": failed, "ok": not failed},
    }
    (KIT / "preflight.json").write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    for name, row in results.items():
        print(f"{'PASS' if row['passed'] else 'FAIL'} {name}: {row['detail']}")
    print(f"preflight: {'PASS' if not failed else 'FAIL'} ({len(results) - len(failed)}/{len(results)})")
    return 0 if not failed else 3


if __name__ == "__main__":
    raise SystemExit(main())
