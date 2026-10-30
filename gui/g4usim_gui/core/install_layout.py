"""Where things are in a source checkout and in an installed package (roadmap D).

Source checkout:  <repo>/gui/g4usim_gui/...   backend in <repo>/build_vs2026/Release
Installed package (packaging/build_package.py):
    <root>/bin/G4UniversalSim.exe, mergeHistograms.exe, Geant4 DLLs, geant4-data.txt
    <root>/gui/G4UniversalSimGUI.exe            (PyInstaller, frozen)
    <root>/config, scenarios, scripts, test/geometry, docs
In the frozen GUI sys.executable is the GUI itself, so the Python helper scripts
(merge, JSON export) need a separate Python 3 (G4USIM_PYTHON or python on PATH), and
runs go to a user-writable folder instead of the (read-only) install directory.
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
    for candidate in (root / "bin" / "G4UniversalSim.exe", root / "build_vs2026" / "Release" / "G4UniversalSim.exe"):
        if candidate.is_file():
            return str(candidate)
    return ""


def workspace_for_executable(executable: str | Path) -> Path:
    """Package root for <root>/bin/<exe>, repository root for <repo>/<build>/<config>/<exe>."""
    path = Path(executable).resolve()
    if path.parent.name.lower() == "bin":
        return path.parents[1]
    return path.parents[2] if len(path.parents) > 2 else path.parent


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
    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if found and "WindowsApps" not in found:   # skip the Microsoft Store stub
            return found
    return None
