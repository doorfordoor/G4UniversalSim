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
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
BUILD = ROOT / "build_vs2026" / "Release"
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
    cache = (ROOT / "build_vs2026" / "CMakeCache.txt").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Geant4_DIR:PATH=(.+)$", cache, re.M)
    if not match:
        raise SystemExit("Geant4_DIR not found in build_vs2026/CMakeCache.txt")
    return Path(match.group(1).strip()).parents[2]   # <prefix>/lib/cmake/Geant4


def qt5_prefix() -> Path | None:
    """The Qt 5 that Geant4's visualisation/UI libraries were built against (from the CMake cache)."""
    cache = (ROOT / "build_vs2026" / "CMakeCache.txt").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Qt5Core_DIR:PATH=(.+)$", cache, re.M)
    return Path(match.group(1).strip()).parents[2] if match else None   # <qt>/lib/cmake/Qt5Core


def check_fingerprint(exe: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_m0_tests   # noqa: E402  (source fingerprint of the C++ working tree)
    problem = run_m0_tests.executable_freshness(exe)
    if problem:
        raise SystemExit(f"{exe}: {problem}")


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
        return {n for n in names if n in SKIP_DIRS or n.endswith((".pyc", ".log"))}
    shutil.copytree(source, target, ignore=ignore, dirs_exist_ok=True)


def build_gui(work: Path, with_3d: bool) -> Path:
    """PyInstaller onedir build of gui/main.py; returns the folder holding G4UniversalSimGUI.exe."""
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
    result = subprocess.run(command, cwd=work, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise SystemExit("PyInstaller failed:\n" + (result.stdout + result.stderr)[-4000:])
    return work / "dist" / "G4UniversalSimGUI"


def third_party_notices(package: Path) -> None:
    licenses = package / "licenses"
    # Geant4 and Xerces-C license texts, copied unchanged from their source releases
    shutil.copytree(ROOT / "packaging" / "licenses", licenses)
    lines = ["# Third-party software in this package", "",
             "| Component | Version | License | Files |", "| --- | --- | --- | --- |",
             "| Geant4 (DLLs in bin/) | 11.3.2 | Geant4 Software License | licenses/Geant4-LICENSE.txt |",
             "| Apache Xerces-C (bin/) | 3.2.5 | Apache License 2.0 | licenses/Xerces-C-LICENSE.txt, -NOTICE.txt |",
             "| Microsoft Visual C++ runtime (bin/) | 14.x | Visual Studio redistributable terms | - |",
             "| Qt 5 (bin/, used by Geant4 visualisation/UI) | 5.15.2 | GNU LGPL v3 | https://www.qt.io/licensing |"]
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


def verify(package: Path, data_dir: Path) -> None:
    """Run the packaged backend and GUI with a clean environment."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("G4") and k not in {"GEANT4_DATA_DIR", "XercesC_ROOT"}}
    system = Path(env.get("SystemRoot", r"C:\Windows"))
    env["PATH"] = os.pathsep.join([str(system / "System32"), str(system)])
    exe = package / "bin" / "G4UniversalSim.exe"
    data_file = package / "bin" / "geant4-data.txt"
    template = data_file.read_text(encoding="utf-8")
    try:
        data_file.write_text(template + str(data_dir) + "\n", encoding="utf-8")
        result = subprocess.run([str(exe), "--check-geant4-data"], capture_output=True, text=True, env=env)
        report = json.loads(result.stdout)
        if result.returncode != 0 or not report["required_complete"]:
            raise SystemExit(f"packaged backend cannot resolve the Geant4 data:\n{result.stdout}{result.stderr}")
        log(f"data check: {sum(d['found'] for d in report['datasets'])}/{len(report['datasets'])} datasets via "
            f"{report['geant4_data_dir']}")
        with tempfile.TemporaryDirectory(prefix="g4usim-package-") as temp:
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
            summary = (run / "out" / "run_summary.txt")
            if result.returncode != 0 or "status = completed" not in summary.read_text(encoding="utf-8"):
                raise SystemExit("packaged backend run failed:\n" + (result.stdout + result.stderr)[-3000:])
            log("packaged backend: 50 neutrons with QGSP_BIC_HP, ROOT + CSV output, completed")
        gui = package / "gui" / "G4UniversalSimGUI.exe"
        if gui.is_file():
            with tempfile.TemporaryDirectory(prefix="g4usim-gui-") as temp:
                report_path = Path(temp) / "self_test.json"
                result = subprocess.run([str(gui), "--self-test", str(report_path)], env=env, timeout=300)
                report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
                if result.returncode != 0 or not report.get("ok") or not report.get("frozen") \
                        or Path(report.get("default_backend", "")) != exe:
                    raise SystemExit(f"frozen GUI self-test failed: {report}")
                log(f"frozen GUI self-test: {report['pages']} pages, plots={report['plots']}, "
                    f"3D preview={report['preview3d']}, backend found")
    finally:
        data_file.write_text(template, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-3d", action="store_true", help="leave PyVista/VTK out of the GUI (smaller)")
    parser.add_argument("--skip-gui", action="store_true", help="package without the frozen GUI")
    parser.add_argument("--no-installer", action="store_true", help="do not run Inno Setup")
    parser.add_argument("--data-dir", default="", help="Geant4 data folder used for the package checks")
    args = parser.parse_args()

    name = f"G4UniversalSim-{version()}-win64"
    package = OUT / "package" / name
    exe = BUILD / "G4UniversalSim.exe"
    check_fingerprint(exe)
    prefix = geant4_prefix()
    data_dir = Path(args.data_dir) if args.data_dir else prefix / "share" / "Geant4" / "data"
    if package.exists():
        shutil.rmtree(package)
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
        "# Folder that holds the Geant4 11.3 datasets (G4EMLOW8.6.1, G4NDL4.7.1, ...), for example\n"
        "# C:\\Program Files\\Geant4\\share\\Geant4\\data\n"
        "# Used only when neither GEANT4_DATA_DIR nor any G4...DATA variable is set.\n"
        "# Check with: bin\\G4UniversalSim.exe --check-geant4-data\n", encoding="utf-8")

    for resource in RESOURCES:
        copy_tree(ROOT / resource, package / resource)
    for file in ("README.md", "CHANGELOG.md"):
        shutil.copy2(ROOT / file, package / file)
    shutil.copy2(ROOT / "packaging" / "README-package.md", package / "README-package.md")

    if not args.skip_gui:
        work = OUT / "package-build"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        shutil.copytree(build_gui(work, not args.no_3d), package / "gui")
    third_party_notices(package)

    verify(package, data_dir)
    size = sum(p.stat().st_size for p in package.rglob("*") if p.is_file())
    log(f"package folder: {package} ({size / 1e6:.0f} MB)")

    archive = OUT / f"{name}.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                zf.write(path, Path(name) / path.relative_to(package))
    log(f"zip: {archive} ({archive.stat().st_size / 1e6:.0f} MB)")

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
