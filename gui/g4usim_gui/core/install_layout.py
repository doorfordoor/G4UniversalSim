"""Locate a source checkout or a Windows/Linux installation (I2).

Source checkout:  <repo>/gui/g4usim_gui/...   backend in <repo>/build_vs2026/Release
Installed package (packaging/build_package.py):
    <root>/bin/G4UniversalSim.exe, mergeHistograms.exe, Geant4 DLLs, geant4-data.txt
    <root>/gui/G4UniversalSimGUI.exe            (PyInstaller, frozen)
    <root>/config, scenarios, scripts, test/geometry, docs
In the frozen GUI sys.executable is the GUI itself. I2 packages provide a
G4USimPython helper for merge/JSON output. Older packages can use an explicit
G4USIM_PYTHON or a discovered Python; runs remain in a user-writable folder.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def application_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parents[1]
    return Path(__file__).resolve().parents[3]


def default_backend_executable() -> str:
    root = application_root()
    name = "G4UniversalSim.exe" if os.name == "nt" else "G4UniversalSim"
    candidates = [root / "bin" / name]
    if os.name == "nt":
        candidates.extend(root / build / "Release" / name for build in ("build_vs2026", "build"))
    else:
        candidates.extend(root / build / name for build in ("build_linux", "build"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def workspace_for_executable(executable: str | Path) -> Path:
    """Find the package/repository, including single-config Linux build trees.

    This locates files only. It does not establish backend compatibility or
    simulation readiness; those are reported by environment discovery.
    """
    path = Path(executable).resolve()
    if path.parent.name.lower() == "bin":
        return path.parents[1]
    for parent in path.parents:
        if (parent / "CMakeLists.txt").is_file() and (parent / "config").is_dir():
            return parent
    directory = path.parent
    if directory.name.lower() in {"release", "debug", "relwithdebinfo", "minsizerel"}:
        directory = directory.parent
    if directory.name.lower().startswith("build"):
        return directory.parent
    return path.parent


def default_runs_root() -> Path:
    if is_frozen():
        documents = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"
        return documents / "G4UniversalSim" / "gui_runs"
    return application_root() / "gui_runs"


def default_recovery_root() -> Path:
    """A per-user recovery store, separate from projects and installation files.

    Tests and portable deployments can explicitly supply G4USIM_RECOVERY_DIR.
    GenericDataLocation plus a fixed product name keeps self-tests and window
    application titles from silently selecting different recovery stores.
    """
    override = os.environ.get("G4USIM_RECOVERY_DIR", "")
    if override:
        return Path(override).expanduser().absolute()
    try:
        from PySide6.QtCore import QStandardPaths
        location = QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)
        if location:
            return Path(location) / "G4UniversalSim" / "recovery"
    except ImportError:
        pass  # The pure recovery model is also usable without Qt.
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "G4UniversalSim" / "recovery"


def scripts_dir() -> Path:
    return application_root() / "scripts"


def script_python() -> str | None:
    """A Python 3 interpreter for the helper scripts, or None when there is none."""
    if not is_frozen():
        return sys.executable
    configured = os.environ.get("G4USIM_PYTHON", "").strip()
    if configured and Path(configured).is_file():
        return configured
    helper_name = "G4USimPython.exe" if os.name == "nt" else "G4USimPython"
    helper = application_root() / "python" / helper_name
    if helper.is_file():
        return str(helper)
    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if found and "WindowsApps" not in found:   # skip the Microsoft Store stub
            return found
    return None
