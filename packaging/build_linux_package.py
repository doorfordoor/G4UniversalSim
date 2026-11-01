"""Build and verify a relocatable Linux runtime archive from a real CMake build.

Requires PyInstaller and patchelf in the calling, preferably isolated Python
environment. Geant4 data remains a separate explicit artifact. System glibc and
graphics/display drivers are external prerequisites, never copied from the host.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import build_package as windows
from build_install_catalog import catalog_from_archive, portable_sources

ROOT = windows.ROOT
OUT = windows.OUT
SYSTEM_LIB = re.compile(r"^(?:ld-linux|lib(?:c|m|pthread|rt|dl|resolv|util|anl)\.so)")


def run(argv, **kwargs):
    result = subprocess.run(list(map(str, argv)), capture_output=True, text=True, errors="replace", **kwargs)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {argv}\n{(result.stdout + result.stderr)[-4000:]}")
    return result


def elf_dependencies(path):
    text = run(["ldd", path]).stdout
    if "not found" in text:
        raise RuntimeError(f"Unresolved shared-library dependency of {path}:\n{text}")
    return [Path(match) for match in re.findall(r"(?:=>\s*)?(/[^\s]+)\s+\(", text)]


def collect_libraries(binaries, package, patchelf):
    libraries = {}
    pending = list(binaries)
    while pending:
        source = pending.pop()
        for dependency in elf_dependencies(source):
            if SYSTEM_LIB.match(dependency.name) or dependency.name in libraries:
                continue
            libraries[dependency.name] = dependency
            pending.append(dependency)
    target_lib = package / "lib"
    target_lib.mkdir()
    for name, source in libraries.items():
        # Dereference the selected library but preserve the loader's soname.
        shutil.copy2(source, target_lib / name)
    for file in [*binaries, *target_lib.iterdir()]:
        target = package / "bin" / file.name if file in binaries else file
        run([patchelf, "--set-rpath", "$ORIGIN/../lib" if file in binaries else "$ORIGIN", target])
    return libraries


def clean_environment():
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("G4") and key not in {"GEANT4_DATA_DIR", "LD_LIBRARY_PATH", "PYTHONPATH", "PYTHONHOME",
                                                       "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"}}
    env["PATH"] = "/usr/bin:/bin"
    env["QT_QPA_PLATFORM"] = "offscreen"
    return env


def verify(package, data_dir):
    env = clean_environment()
    evidence_root = OUT / "package-verification"
    evidence_root.mkdir(exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="linux-", dir=evidence_root))
    backend = package / "bin/G4UniversalSim"
    gui_profile = None
    if (package / "gui/G4UniversalSimGUI").is_file():
        declaration = json.loads((package / "gui" / windows.freeze_identity.RECEIPT).read_text(encoding="utf-8"))
        gui_profile = declaration.get("with_3d")
        if type(gui_profile) is not bool:
            raise ValueError("Frozen GUI receipt has no explicit 3D profile")
        windows.freeze_identity.verify(package / "gui", root=ROOT, kind="gui", with_3d=gui_profile)
    if (package / "python/G4USimPython").is_file():
        windows.freeze_identity.verify(package / "python", root=ROOT, kind="python")
    pointer = package / "bin/geant4-data.txt"
    original = pointer.read_bytes()
    try:
        pointer.write_text(str(data_dir) + "\n", encoding="utf-8")
        discovery = run([backend, "--check-geant4-data"], env=env)
        data = json.loads(discovery.stdout)
        from build_data_artifact import geant4_version_from_discovery
        if geant4_version_from_discovery(data) != windows.geant4_version():
            raise RuntimeError("Packaged backend and selected Geant4 development prefix versions differ")
        (evidence / "data-discovery.json").write_text(discovery.stdout, encoding="utf-8")
        if not data.get("required_complete"):
            raise RuntimeError("Packaged backend could not locate required data")
        (evidence / "geo.ini").write_text("[world]\nshape=box\nsize=1 m, 1 m, 1 m\nmaterial=G4_Galactic\n"
                                            "[volume.Target]\nparent=world\nshape=box\nsize=10 cm, 10 cm, 1 cm\n"
                                            "material=G4_WATER\nposition=0 mm, 0 mm, 5 mm\nsensitive=true\n", encoding="utf-8")
        (evidence / "main.ini").write_text(
            "[run]\nthreads=2\nseed=1\n[output]\nformat=both\n[materials]\nfile=" + str(package / "config/materials/material.ini") +
            "\n[geometry]\ntemplate=hierarchical\nconfig=" + str(evidence / "geo.ini") +
            "\n[physics]\nreference=QGSP_BIC_HP\n[scoring]\nenabled=true\nhits=true\ndose=true\n"
            "[source]\nparticle=neutron\nenergy=2 MeV\nposition_type=point\nposition=0,0,-10 mm\ndirection=+z\n", encoding="utf-8")
        (evidence / "run.mac").write_text("/run/initialize\n/run/beamOn 50\n", encoding="utf-8")
        result = run([backend, "--config", "main.ini", "--macro", "run.mac", "--output", "result"], env=env, cwd=evidence, timeout=900)
        (evidence / "backend.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        sys.path.insert(0, str(ROOT / "gui"))
        from g4usim_gui.core.run_result import evaluate_run_result
        outcome = evaluate_run_result(evidence / "result/run_summary.txt", exit_code=result.returncode, summary_fresh=True)
        if outcome.state != "success" or outcome.completed_events != 50:
            raise RuntimeError(f"Packaged backend event evidence failed: {outcome}")
        helper = package / "python/G4USimPython"
        if helper.is_file():
            result = run([helper, package / "scripts/compare_root_csv.py", "--dir", evidence / "result"], env=env, timeout=180)
            (evidence / "root-csv.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            code = "import numpy as n,uproot; p=" + repr(str(evidence / "helper.root")) + "; f=uproot.recreate(p); f['probe']={'x':n.array([1.,2.,3.])}; f.close(); r=uproot.open(p); assert list(r['probe']['x'].array(library='np'))==[1.,2.,3.]; r.close()"
            run([helper, "-c", code], env=env, timeout=120)
        gui = package / "gui/G4UniversalSimGUI"
        if gui.is_file():
            gui_env = dict(env, G4USIM_RECOVERY_DIR=str(evidence / "recovery"))
            result = run([gui, "--self-test", evidence / "gui-selftest.json"], env=gui_env, timeout=300)
            report = json.loads((evidence / "gui-selftest.json").read_text(encoding="utf-8"))
            if not report.get("ok") or not report.get("frozen") or Path(report.get("default_backend", "")) != backend:
                raise RuntimeError(f"Frozen GUI failed: {report}")
        report = {"status": "verified", "backend_events": 50, "data_required_complete": True,
                  "python_root_read_write": helper.is_file(), "frozen_gui": gui.is_file(), "evidence_directory": str(evidence),
                  "frozen_gui_3d_profile": gui_profile,
                  "scope": "Clean PATH/environment on this Linux host; not a new operating-system image or physics benchmark"}
        (evidence / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return evidence
    finally:
        pointer.write_bytes(original)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--patchelf", default=shutil.which("patchelf"))
    parser.add_argument("--skip-gui", action="store_true")
    parser.add_argument("--skip-python-helper", action="store_true")
    parser.add_argument("--no-3d", action="store_true")
    parser.add_argument("--verify-existing", action="store_true", help="Reverify the previously assembled package without refreezing")
    parser.add_argument("--freeze-work-root", type=Path, help="Explicit native directory for isolated freeze intermediates")
    args = parser.parse_args()
    if not args.patchelf:
        parser.error("A patchelf executable is required")
    build = args.build_dir.absolute()
    windows.CACHE = build / "CMakeCache.txt"
    windows.BUILD = build
    exe = build / "G4UniversalSim"
    windows.check_fingerprint(exe)
    package = OUT / "package" / f"G4UniversalSim-{windows.version()}-linux-x86_64"
    if args.verify_existing:
        evidence = verify(package, args.data_dir.absolute())
        if not args.skip_gui and not args.no_3d and evidence:
            declaration = json.loads((package / "gui" / windows.freeze_identity.RECEIPT).read_text(encoding="utf-8"))
            if declaration.get("with_3d") is not True:
                raise ValueError("Final full 3D publication cannot reuse a degraded GUI profile")
        publish(package, build, evidence)
        return
    if package.exists():
        windows.clean_output_directory(package)
    (package / "bin").mkdir(parents=True)
    binaries = [exe, build / "mergeHistograms"]
    for binary in binaries:
        shutil.copy2(binary, package / "bin" / binary.name)
    libraries = collect_libraries(binaries, package, args.patchelf)
    (package / "bin/geant4-data.txt").write_text("# Select matching Geant4 data explicitly; or install the reviewed data artifact.\n", encoding="utf-8")
    for resource in windows.RESOURCES:
        windows.copy_tree(ROOT / resource, package / resource)
    for name in ("README.md", "CHANGELOG.md"):
        shutil.copy2(ROOT / name, package / name)
    shutil.copytree(ROOT / "packaging/licenses", package / "licenses")
    (package / "THIRD_PARTY_NOTICES.md").write_text(
        "# Linux runtime components\n\nGeant4 " + windows.geant4_version() +
        " (Geant4 Software License); Xerces-C (Apache-2.0); PySide6/Qt (LGPL-3.0); "
        "Python and scientific helper dependencies retain their included distribution notices.\n"
        "System glibc and graphics drivers remain host prerequisites.\n"
        "This archive does not contain Geant4 data; matching data can be installed as a separate reviewed artifact.\n",
        encoding="utf-8")
    # Freeze into a native filesystem. PyInstaller hardlinks/renames are not
    # assumed to work across /mnt/c and the Linux temporary filesystem.
    work_root = args.freeze_work_root.absolute() if args.freeze_work_root else Path.home() / ".cache/g4usim-package-work"
    work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="g4usim-package-freeze-", dir=work_root))
    if not args.skip_gui:
        shutil.copytree(windows.build_gui(work / "gui", not args.no_3d), package / "gui")
    if not args.skip_python_helper:
        shutil.copytree(windows.build_python_helper(work / "python"), package / "python")
        shutil.copytree(ROOT / "gui/g4usim_gui", package / "python_modules/g4usim_gui",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for distribution in __import__("importlib.metadata", fromlist=["distributions"]).distributions():
        for file in distribution.files or []:
            if re.search(r"LICEN[CS]E|COPYING|NOTICE", file.name, re.I) and ".dist-info" in str(file):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    shutil.copy2(source, package / "licenses" / f"{distribution.metadata['Name']}-{file.name}")
    evidence = verify(package, args.data_dir.absolute())
    publish(package, build, evidence, library_count=len(libraries))


def publish(package, build, evidence, library_count=None):
    archive = OUT / f"{package.name}-runtime.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=4) as output:
        for file in sorted(package.rglob("*")):
            if file.is_file():
                output.write(file, file.relative_to(package))
    entrypoints = {"backend": "bin/G4UniversalSim"}
    for key, relative in (("gui", "gui/G4UniversalSimGUI"), ("python", "python/G4USimPython")):
        if (package / relative).is_file():
            entrypoints[key] = relative
    catalog = catalog_from_archive(archive, profile="runtime", platform="linux", architecture="x86_64", version=windows.version(),
                                   origin=f"Actual local Linux build {build}; clean-environment receipt {evidence}",
                                   license_path="THIRD_PARTY_NOTICES.md", license_expression="LicenseRef-Bundled-Notices",
                                   license_source="Bundled component notices and licenses directory", entrypoints=entrypoints,
                                   dependencies=[{"id": "glibc", "required": True, "kind": "host_runtime"}],
                                   components=["application", "geant4_runtime", *entrypoints.keys()],
                                   geant4_version=windows.geant4_version())
    portable_sources(catalog, OUT)
    (OUT / f"{package.name}-runtime.catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "verified", "archive": str(archive), "catalog": str(OUT / f"{package.name}-runtime.catalog.json"),
                      "shared_libraries": library_count, "evidence": str(evidence)}), flush=True)


if __name__ == "__main__":
    main()
