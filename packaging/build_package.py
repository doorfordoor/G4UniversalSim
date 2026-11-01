"""Builds the portable Windows package and, when Inno Setup is installed, the installer (roadmap D).

    gui\\.venv\\Scripts\\python.exe packaging\\build_package.py [--no-3d] [--skip-gui] [--no-installer]

Output (all under out/, which git ignores):
  out/package/G4UniversalSim-<version>-win64/     portable folder
  out/G4UniversalSim-<version>-win64.zip          the same folder zipped
  out/G4UniversalSim-<version>-win64-setup.exe    Inno Setup installer (packaging/installer.iss)

Package layout (see gui/g4usim_gui/core/install_layout.py):
  bin/   G4UniversalSim.exe, mergeHistograms.exe, the Geant4/Xerces-C DLLs they load
         (found with dumpbin), the MSVC runtime DLLs, geant4-data.txt (template)
  gui/   G4UniversalSimGUI.exe (PyInstaller onedir, windowed)
  config/ scenarios/ scripts/ test/geometry/ docs/ examples/  README.md CHANGELOG.md
  licenses/ + THIRD_PARTY_NOTICES.md
The Geant4 data (3+ GB) is NOT included: the package uses an existing Geant4 11.3 data
folder through GEANT4_DATA_DIR, the per-dataset variables, or bin/geant4-data.txt.

Checks before zipping: the backend source fingerprint matches the working tree, the
packaged backend runs with a clean PATH (no Geant4 or Visual Studio on it) and resolves
every required dataset through geant4-data.txt, a short simulation completes, and the
frozen GUI passes --self-test from inside the package.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from contextlib import nullcontext
from pathlib import Path

from windows_freeze import audit_binary_sources, freeze_environment
import freeze_identity

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
BUILD = ROOT / "build_vs2026" / "Release"
CACHE = ROOT / "build_vs2026" / "CMakeCache.txt"
SYSTEM_DLL = re.compile(r"^(api-ms-|ext-ms-|kernel32|user32|gdi32|advapi32|shell32|ole32|oleaut32|ws2_32|"
                        r"comdlg32|comctl32|crypt32|bcrypt|ntdll|rpcrt4|shlwapi|version|winmm|imm32|"
                        r"secur32|netapi32|userenv|dbghelp|psapi|setupapi|cfgmgr32|iphlpapi|mpr|"
                        r"opengl32|glu32|dwmapi|uxtheme|wtsapi32|normaliz|winspool|d3d|dxgi|dwrite)", re.I)
RESOURCES = ["config", "scenarios", "scripts", "docs", "examples", "test/geometry", "test/macros"]
SKIP_DIRS = {"__pycache__", "output", ".pytest_cache"}


def log(message: str) -> None:
    print(f"[package] {message}", flush=True)


def version() -> str:
    match = re.search(r"project\(G4UniversalSim VERSION (\S+)", (ROOT / "CMakeLists.txt").read_text(encoding="utf-8"))
    return match.group(1) if match else "0.0.0"


def visual_studio() -> Path:
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / \
        "Microsoft Visual Studio/Installer/vswhere.exe"
    path = subprocess.run([str(vswhere), "-latest", "-prerelease", "-property", "installationPath"],
                          capture_output=True, text=True, check=True).stdout.strip()
    return Path(path)


def geant4_prefix() -> Path:
    cache = CACHE.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Geant4_DIR:[A-Z_]+=(.+)$", cache, re.M)
    if not match:
        raise SystemExit(f"Geant4_DIR not found in {CACHE}")
    return Path(match.group(1).strip()).parents[2]   # <prefix>/lib/cmake/Geant4


def qt5_prefix() -> Path | None:
    """The Qt 5 that Geant4's visualisation/UI libraries were built against (from the CMake cache)."""
    cache = CACHE.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Qt5Core_DIR:PATH=(.+)$", cache, re.M)
    return Path(match.group(1).strip()).parents[2] if match else None   # <qt>/lib/cmake/Qt5Core


def check_fingerprint(exe: Path, runtime_paths: list[Path] | None = None) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_m0_tests   # noqa: E402  (source fingerprint of the C++ working tree)
    environment = os.environ.copy()
    if runtime_paths:
        environment["PATH"] = os.pathsep.join(map(str, runtime_paths)) + os.pathsep + environment.get("PATH", "")
    result = subprocess.run([str(exe), "--capabilities"], cwd=exe.parent, env=environment,
                            capture_output=True, text=True, errors="replace", timeout=30)
    if result.returncode:
        raise SystemExit(f"Backend capabilities probe failed (exit {result.returncode}); no fingerprint comparison was possible:\n{result.stderr[-2000:]}")
    if json.loads(result.stdout).get("source_fingerprint") != run_m0_tests.workspace_source_fingerprint():
        raise SystemExit(f"{exe}: actual backend source fingerprint differs from this worktree; rebuild")


def dependencies(binary: Path, dumpbin: Path) -> list[str]:
    text = subprocess.run([str(dumpbin), "/nologo", "/dependents", str(binary)], capture_output=True, text=True,
                          errors="replace", check=True).stdout
    # dependency lines are bare DLL names (the "Dump of file ..." header also ends in .dll)
    return [line.strip() for line in text.splitlines() if re.fullmatch(r"\s+[\w.+-]+\.dll", line, re.I)]


def collect_dlls(binaries: list[Path], search: list[Path], dumpbin: Path) -> dict[str, Path]:
    """Every non-system DLL the binaries load, found in the search folders."""
    found: dict[str, Path] = {}
    queue = list(binaries)
    missing: set[str] = set()
    while queue:
        for name in dependencies(queue.pop(), dumpbin):
            key = name.lower()
            if key in found or SYSTEM_DLL.match(name):
                continue
            location = next((folder / name for folder in search if (folder / name).is_file()), None)
            if location is None:
                missing.add(name)
                continue
            found[key] = location
            queue.append(location)
    unexpected = {m for m in missing if not (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / m).is_file()}
    if unexpected:
        raise SystemExit(f"DLLs not found in {search}: {sorted(unexpected)}")
    return found


def copy_tree(source: Path, target: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        historical = {"verification", "collab"} if Path(directory) == ROOT / "docs" else set()
        return {n for n in names if n in SKIP_DIRS | historical or n.endswith((".pyc", ".log"))}
    shutil.copytree(source, target, ignore=ignore, dirs_exist_ok=True)


def clean_output_directory(path: Path) -> None:
    """Remove only an actual descendant of this checkout's out directory."""
    # On Windows a junction is a reparse point, not a Python 3.11 symlink.
    # Reject each lexical ancestor before any recursive deletion, including an
    # out junction pointing at another directory inside the same checkout.
    current = path.absolute()
    output_path = (ROOT / "out").absolute()
    while current != ROOT.absolute():
        if not current.is_relative_to(output_path):
            raise ValueError(f"Output cleanup path escaped the expected directory: {path}")
        if current.exists() or current.is_symlink():
            facts = current.lstat()
            if stat.S_ISLNK(facts.st_mode) or getattr(facts, "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Output cleanup refuses linked directories: {current}")
        current = current.parent
    allowed = output_path.resolve()
    target = path.resolve()
    if (allowed != ROOT.resolve() / "out" or target == allowed
            or not target.is_relative_to(allowed)):
        raise ValueError(f"Refusing to clean a directory outside this checkout's output tree: {path}")
    if path.exists():
        shutil.rmtree(path)


def build_gui(work: Path, with_3d: bool) -> Path:
    """PyInstaller onedir build of gui/main.py; returns the folder holding G4UniversalSimGUI.exe."""
    work.mkdir(parents=True, exist_ok=True)
    before = freeze_identity.source_identity(ROOT, "gui")
    excludes = [] if with_3d else ["pyvista", "pyvistaqt", "vtk", "vtkmodules"]
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
               "--name", "G4UniversalSimGUI", "--distpath", str(work / "dist"), "--workpath", str(work / "build"),
               "--specpath", str(work), "--paths", str(ROOT / "gui"),
               "--collect-submodules", "g4usim_gui", "--hidden-import", "matplotlib.backends.backend_qtagg",
               "--collect-data", "matplotlib"]
    if with_3d:
        command += ["--collect-submodules", "pyvista", "--collect-data", "pyvista",
                    "--collect-submodules", "vtkmodules"]
    for module in excludes:
        command += ["--exclude-module", module]
    command.append(str(ROOT / "gui" / "main.py"))
    log("freezing the GUI with PyInstaller (this takes a few minutes)")
    result = subprocess.run(command, cwd=work, capture_output=True, text=True, errors="replace",
                            env=freeze_environment() if os.name == "nt" else None)
    (work / "freeze.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise SystemExit(f"PyInstaller failed; full log {work / 'freeze.log'}:\n" + (result.stdout + result.stderr)[-4000:])
    if os.name == "nt":
        audit_binary_sources(work, "G4UniversalSimGUI")
    after = freeze_identity.source_identity(ROOT, "gui")
    (work / "source-identity.json").write_text(json.dumps({"schema": "g4usim_gui_freeze_sources_v1",
        "stable": before == after, "sources_before": before, "sources_after": after}, indent=2), encoding="utf-8")
    if before != after:
        raise RuntimeError(f"GUI source changed while freezing; rebuild the stable candidate: {work}")
    result_path = work / "dist" / "G4UniversalSimGUI"
    freeze_identity.seal(result_path, kind="gui", sources=after, with_3d=with_3d)
    return result_path


def build_python_helper(work: Path) -> Path:
    """Bundle actual Python + ROOT reader/writer; no external interpreter needed."""
    before = freeze_identity.source_identity(ROOT, "python")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
               "--name", "G4USimPython", "--distpath", str(work / "dist"),
               "--workpath", str(work / "build"), "--specpath", str(work),
               "--collect-all", "uproot", "--collect-all", "awkward", "--collect-all", "awkward_cpp", "--collect-all", "numpy",
               "--hidden-import", "csv", "--hidden-import", "argparse", "--hidden-import", "tempfile",
               "--hidden-import", "concurrent.futures", "--hidden-import", "importlib.metadata",
               str(ROOT / "packaging/python_helper.py")]
    work.mkdir(parents=True, exist_ok=True)
    log("freezing Python scientific helper")
    result = subprocess.run(command, cwd=work, capture_output=True, text=True, errors="replace",
                            env=freeze_environment() if os.name == "nt" else None)
    (work / "freeze.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise SystemExit(f"Python helper freeze failed; see {work / 'freeze.log'}")
    if os.name == "nt":
        audit_binary_sources(work, "G4USimPython")
    after = freeze_identity.source_identity(ROOT, "python")
    if before != after:
        raise RuntimeError("Python helper source changed while freezing")
    result_path = work / "dist" / "G4USimPython"
    freeze_identity.seal(result_path, kind="python", sources=after)
    return result_path


def third_party_notices(package: Path) -> None:
    licenses = package / "licenses"
    # Geant4 and Xerces-C license texts, copied unchanged from their source releases
    shutil.copytree(ROOT / "packaging" / "licenses", licenses)
    lines = ["# Third-party software in this package", "",
             "| Component | Version | License | Files |", "| --- | --- | --- | --- |",
             f"| Geant4 (DLLs in bin/) | {geant4_version()} | Geant4 Software License | licenses/Geant4-LICENSE.txt |",
             "| Microsoft Visual C++ runtime (bin/) | 14.x | Visual Studio redistributable terms | - |"]
    if any((package / "bin").glob("xerces*.dll")):
        lines.append("| Apache Xerces-C (bin/) | see bundled DLL version | Apache License 2.0 | licenses/Xerces-C-LICENSE.txt, -NOTICE.txt |")
    if (package / "bin/Qt5Core.dll").is_file():
        lines.append("| Qt 5 (bin/, Geant4 visualisation/UI) | see bundled DLL version | GNU LGPL v3 | https://www.qt.io/licensing |")
    for dist in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        if name.lower() in {"pip", "setuptools", "pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile",
                            "pywin32-ctypes", "packaging", "wheel"}:
            continue
        license_text = dist.metadata.get("License-Expression") or dist.metadata.get("License") or ""
        license_text = license_text.splitlines()[0][:80] if license_text else "see license file"
        copied = []
        for file in dist.files or []:
            if re.search(r"(LICEN[CS]E|COPYING|NOTICE)", file.name, re.I) and ".dist-info" in str(file):
                target = licenses / f"{name}-{file.name}"
                source = Path(dist.locate_file(file))
                if source.is_file() and not target.exists():
                    shutil.copy2(source, target)
                    copied.append(target.name)
        lines.append(f"| {name} (gui/) | {dist.version} | {license_text} | {', '.join(copied) or '-'} |")
    lines += ["", "PySide6/Qt are used under the GNU LGPL v3 (dynamically linked Qt libraries in gui/_internal);",
              "their source is available from https://download.qt.io and https://code.qt.io/pyside/pyside-setup.",
              "The Geant4 physics data is not part of this package."]
    (package / "THIRD_PARTY_NOTICES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def geant4_version(prefix: Path | None = None) -> str:
    prefix = Path(prefix) if prefix is not None else geant4_prefix()
    config = prefix / "lib/cmake/Geant4/Geant4ConfigVersion.cmake"
    match = re.search(r'set\(PACKAGE_VERSION\s+"?([^"\s)]+)', config.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"Geant4 version not found in {config}")
    version = match.group(1)
    header = prefix / "include/Geant4/G4Version.hh"
    number = re.search(r"^\s*#\s*define\s+G4VERSION_NUMBER\s+(\d+)", header.read_text(encoding="utf-8"), re.M)
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdecimal() for part in parts) or number is None \
            or int(number.group(1)) != int(parts[0]) * 100 + int(parts[1]) * 10 + int(parts[2]):
        raise ValueError("Actual Geant4 CMake/header version identity is inconsistent")
    return version


def verify(package: Path, data_dir: Path, *, expected_geant4_version: str | None = None) -> None:
    """Run the packaged backend and GUI with a clean environment."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("G4") and k not in {"GEANT4_DATA_DIR", "XercesC_ROOT"}}
    system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    env["PATH"] = os.pathsep.join([str(system / "System32"), str(system)])
    exe = package / "bin" / "G4UniversalSim.exe"
    data_file = package / "bin" / "geant4-data.txt"
    template = data_file.read_text(encoding="utf-8")
    evidence_root = OUT / "package-verification"
    evidence_root.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="windows-", dir=evidence_root))
    try:
        data_file.write_text(template + str(data_dir) + "\n", encoding="utf-8")
        result = subprocess.run([str(exe), "--check-geant4-data"], capture_output=True, text=True, env=env)
        report = json.loads(result.stdout)
        (evidence / "data-discovery.json").write_text(result.stdout, encoding="utf-8")
        if expected_geant4_version is not None:
            from build_data_artifact import geant4_version_from_discovery
            if geant4_version_from_discovery(report) != expected_geant4_version:
                raise SystemExit("Packaged backend and selected Geant4 development prefix versions differ")
        if result.returncode != 0 or not report["required_complete"]:
            raise SystemExit(f"packaged backend cannot resolve the Geant4 data:\n{result.stdout}{result.stderr}")
        log(f"data check: {sum(d['found'] for d in report['datasets'])}/{len(report['datasets'])} datasets via "
            f"{report['geant4_data_dir']}")
        with nullcontext(str(evidence)) as temp:
            run = Path(temp)
            (run / "geo.ini").write_text("[world]\nshape = box\nsize = 1 m, 1 m, 1 m\nmaterial = G4_Galactic\n"
                                        "[volume.Target]\nparent = world\nshape = box\nsize = 10 cm, 10 cm, 1 cm\n"
                                        "material = G4_WATER\nposition = 0 mm, 0 mm, 5 mm\nsensitive = true\n",
                                        encoding="utf-8")
            (run / "main.ini").write_text(
                "[run]\nthreads = 2\nseed = 1\n[output]\nformat = both\n[materials]\nfile = "
                f"{(package / 'config/materials/material.ini').as_posix()}\n[geometry]\ntemplate = hierarchical\n"
                f"config = {(run / 'geo.ini').as_posix()}\n[physics]\nreference = QGSP_BIC_HP\n[scoring]\n"
                "enabled = true\nhits = false\ndose = true\n[source]\nparticle = neutron\nenergy = 2 MeV\n"
                "position_type = point\nposition = 0,0,-10 mm\ndirection = +z\n", encoding="utf-8")
            (run / "run.mac").write_text("/run/initialize\n/run/beamOn 50\n", encoding="utf-8")
            result = subprocess.run([str(exe), "--config", "main.ini", "--macro", "run.mac", "--output", "out"],
                                    cwd=run, capture_output=True, text=True, errors="replace", env=env, timeout=900)
            (evidence / "backend.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            summary = (run / "out" / "run_summary.txt")
            sys.path.insert(0, str(ROOT / "gui"))
            from g4usim_gui.core.run_result import evaluate_run_result
            outcome = evaluate_run_result(summary, exit_code=result.returncode, summary_fresh=summary.is_file())
            if outcome.state != "success" or outcome.completed_events != 50:
                raise SystemExit("packaged backend run failed:\n" + (result.stdout + result.stderr)[-3000:])
            log("packaged backend: 50 neutrons with QGSP_BIC_HP, ROOT + CSV output, completed")
            helper_name = "G4USimPython.exe" if os.name == "nt" else "G4USimPython"
            helper = package / "python" / helper_name
            if helper.is_file():
                check = subprocess.run([str(helper), str(package / "scripts/compare_root_csv.py"), "--dir", str(run / "out")],
                                       env=env, capture_output=True, text=True, errors="replace", timeout=180)
                (evidence / "root-csv.log").write_text(check.stdout + check.stderr, encoding="utf-8")
                if check.returncode:
                    raise SystemExit("Packaged Python ROOT/CSV read failed:\n" + (check.stdout + check.stderr)[-3000:])
                root_probe = run / "helper-root-roundtrip.root"
                code = "import numpy as np,uproot; p=" + repr(str(root_probe)) + "; f=uproot.recreate(p); f['check']={'value':np.array([1.,2.,3.])}; f.close(); r=uproot.open(p); assert list(r['check']['value'].array(library='np'))==[1.,2.,3.]; r.close(); print('ROOT roundtrip verified')"
                check = subprocess.run([str(helper), "-c", code], env=env, capture_output=True, text=True, timeout=120)
                if check.returncode:
                    raise SystemExit("Packaged Python ROOT write/read failed:\n" + check.stdout + check.stderr)
                log("packaged Python: actual simulation ROOT/CSV consistency + ROOT write/read roundtrip")
        gui = package / "gui" / "G4UniversalSimGUI.exe"
        if gui.is_file():
            gui_evidence = evidence / "gui"
            gui_evidence.mkdir()
            with nullcontext(str(gui_evidence)) as temp:
                report_path = Path(temp) / "self_test.json"
                gui_env = dict(env, G4USIM_RECOVERY_DIR=str(Path(temp) / "recovery"), QT_QPA_PLATFORM="offscreen")
                result = subprocess.run([str(gui), "--self-test", str(report_path)], env=gui_env, timeout=300)
                report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
                if result.returncode != 0 or not report.get("ok") or not report.get("frozen") \
                        or Path(report.get("default_backend", "")) != exe:
                    raise SystemExit(f"frozen GUI self-test failed: {report}")
                log(f"frozen GUI self-test: {report['pages']} pages, plots={report['plots']}, "
                    f"3D preview={report['preview3d']}, backend found")
        (evidence / "verification.json").write_text(json.dumps({"status": "verified", "backend_events": 50,
            "data_required_complete": True, "frozen_gui": gui.is_file(), "package": str(package),
            "geant4_version": expected_geant4_version, "scope": "Clean PATH/process environment on this Windows host; not a fresh OS image or physics benchmark"}, indent=2) + "\n", encoding="utf-8")
        log(f"retained verification evidence: {evidence}")
    finally:
        data_file.write_text(template, encoding="utf-8")


def main() -> int:
    global BUILD, CACHE
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-3d", action="store_true", help="leave PyVista/VTK out of the GUI (smaller)")
    parser.add_argument("--skip-gui", action="store_true", help="package without the frozen GUI")
    parser.add_argument("--no-installer", action="store_true", help="do not run Inno Setup")
    parser.add_argument("--data-dir", default="", help="Geant4 data folder used for the package checks")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build_vs2026", help="Actual CMake build tree")
    parser.add_argument("--skip-python-helper", action="store_true", help="Explicit partial package without bundled Python")
    parser.add_argument("--package-name", help="Explicit artifact basename for version/platform variants")
    parser.add_argument("--reuse-gui", type=Path, help="Explicit previously frozen GUI directory; reverified before publication")
    parser.add_argument("--reuse-python-helper", type=Path, help="Explicit previously frozen scientific helper; reverified")
    args = parser.parse_args()
    CACHE = args.build_dir.absolute() / "CMakeCache.txt"
    BUILD = args.build_dir.absolute() / "Release"

    name = args.package_name or f"G4UniversalSim-{version()}-win64"
    if name in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        parser.error("Package name must be a portable basename")
    package = OUT / "package" / name
    work = OUT / "package-build"
    helper_work = OUT / "package-python-build"
    if (args.reuse_gui and args.skip_gui) or (args.reuse_python_helper and args.skip_python_helper):
        parser.error("Cannot both skip and reuse the same application")
    # Validate every reused source before any output cleanup. In particular,
    # the normal previous work/dist directory is a valid source to preserve.
    changing = [package]
    if not args.skip_gui and not args.reuse_gui:
        changing.append(work)
    if not args.skip_python_helper and not args.reuse_python_helper:
        changing.append(helper_work)
    for source, kind, with_3d in ((args.reuse_gui, "gui", not args.no_3d),
                                 (args.reuse_python_helper, "python", False)):
        if source:
            freeze_identity.reject_overlap(source, changing)
            freeze_identity.verify(source, root=ROOT, kind=kind, with_3d=with_3d)
    exe = BUILD / "G4UniversalSim.exe"
    prefix = geant4_prefix()
    selected_qt = qt5_prefix()
    check_fingerprint(exe, [prefix / "bin"] + ([selected_qt / "bin"] if selected_qt else []))
    data_dir = Path(args.data_dir).absolute() if args.data_dir else prefix / "share" / "Geant4" / "data"
    clean_output_directory(package)
    (package / "bin").mkdir(parents=True)

    vs = visual_studio()
    msvc = sorted((vs / "VC" / "Tools" / "MSVC").iterdir())[-1]
    dumpbin = msvc / "bin" / "Hostx64" / "x64" / "dumpbin.exe"
    redist = sorted(p for p in (vs / "VC" / "Redist" / "MSVC").iterdir() if p.name[0].isdigit())[-1]
    crt = next((redist / "x64").glob("Microsoft.VC*.CRT"))
    binaries = [exe, BUILD / "mergeHistograms.exe"]
    qt5 = qt5_prefix()
    search = [prefix / "bin", crt] + ([qt5 / "bin"] if qt5 else [])
    dlls = collect_dlls(binaries, search, dumpbin)
    for binary in binaries:
        shutil.copy2(binary, package / "bin")
    for path in dlls.values():
        shutil.copy2(path, package / "bin")
    if qt5 and any(name.startswith("qt5") for name in dlls):
        # platform plugin for the backend's optional Qt UI session (--ui)
        (package / "bin" / "platforms").mkdir()
        shutil.copy2(qt5 / "plugins" / "platforms" / "qwindows.dll", package / "bin" / "platforms")
        for path in collect_dlls([qt5 / "plugins" / "platforms" / "qwindows.dll"], search, dumpbin).values():
            if not (package / "bin" / path.name).exists():
                shutil.copy2(path, package / "bin")
    log(f"backend: {len(dlls)} DLLs ({sum(p.stat().st_size for p in dlls.values()) / 1e6:.0f} MB)")
    (package / "bin" / "geant4-data.txt").write_text(
        f"# Folder holding datasets for Geant4 {geant4_version()}, for example\n"
        "# C:\\Program Files\\Geant4\\share\\Geant4\\data\n"
        "# Used only when neither GEANT4_DATA_DIR nor any G4...DATA variable is set.\n"
        "# Check with: bin\\G4UniversalSim.exe --check-geant4-data\n", encoding="utf-8")

    for resource in RESOURCES:
        copy_tree(ROOT / resource, package / resource)
    for file in ("README.md", "CHANGELOG.md"):
        shutil.copy2(ROOT / file, package / file)
    shutil.copy2(ROOT / "packaging" / "README-package.md", package / "README-package.md")

    if not args.skip_gui:
        if not args.reuse_gui:
            clean_output_directory(work)
            work.mkdir(parents=True)
        shutil.copytree(args.reuse_gui.absolute() if args.reuse_gui else build_gui(work, not args.no_3d), package / "gui")
        freeze_identity.verify(package / "gui", root=ROOT, kind="gui", with_3d=not args.no_3d)
    if not args.skip_python_helper:
        shutil.copytree(args.reuse_python_helper.absolute() if args.reuse_python_helper else build_python_helper(OUT / "package-python-build"), package / "python")
        freeze_identity.verify(package / "python", root=ROOT, kind="python")
        shutil.copytree(ROOT / "gui/g4usim_gui", package / "python_modules/g4usim_gui",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    third_party_notices(package)

    verify(package, data_dir, expected_geant4_version=geant4_version())
    size = sum(p.stat().st_size for p in package.rglob("*") if p.is_file())
    log(f"package folder: {package} ({size / 1e6:.0f} MB)")

    archive = OUT / f"{name}.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                zf.write(path, Path(name) / path.relative_to(package))
    log(f"zip: {archive} ({archive.stat().st_size / 1e6:.0f} MB)")

    # The transaction service publishes directly to the user prefix; its archive
    # has no extra top-level directory. Keep the traditional portable zip above.
    from build_install_catalog import catalog_from_archive, portable_sources
    runtime_archive = OUT / f"{name}-runtime.zip"
    runtime_archive.unlink(missing_ok=True)
    with zipfile.ZipFile(runtime_archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(package))
    catalog = catalog_from_archive(runtime_archive, profile="runtime", platform="windows", architecture="x86_64",
                                   version=version(), origin=f"Local build {BUILD}; validated by packaging/build_package.py",
                                   license_path="THIRD_PARTY_NOTICES.md", license_expression="LicenseRef-Bundled-Notices",
                                   license_source="Bundled third-party notices and licenses directory",
                                   entrypoints={"backend": "bin/G4UniversalSim.exe", **({"gui": "gui/G4UniversalSimGUI.exe"} if not args.skip_gui else {}),
                                                **({"python": "python/G4USimPython.exe"} if not args.skip_python_helper else {})},
                                   components=["application", "geant4_runtime"] + ([] if args.skip_gui else ["gui"]) +
                                              ([] if args.skip_python_helper else ["python_tools", "root_read_write"]),
                                   geant4_version=geant4_version())
    portable_sources(catalog, OUT)
    (OUT / f"{name}-runtime.catalog.json").write_text(json.dumps(catalog, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    if not args.no_installer:
        iscc = shutil.which("ISCC") or next((str(p) for p in (
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe") if p.is_file()), None)
        if iscc is None:
            log("Inno Setup (ISCC.exe) not found: installer skipped")
        else:
            result = subprocess.run([iscc, f"/DAppVersion={version()}", f"/DSourceDir={package}", f"/DOutputDir={OUT}",
                                     f"/DOutputName={name}-setup", str(ROOT / "packaging" / "installer.iss")],
                                    capture_output=True, text=True, errors="replace")
            if result.returncode != 0:
                raise SystemExit("Inno Setup failed:\n" + (result.stdout + result.stderr)[-4000:])
            setup = OUT / f"{name}-setup.exe"
            log(f"installer: {setup} ({setup.stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
