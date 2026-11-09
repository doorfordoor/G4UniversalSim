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
XCB_CURSOR = "libxcb-cursor.so.0"
XCB_COPYRIGHT = "libxcb-cursor0-COPYRIGHT"
XCB_RECEIPT = "libxcb-cursor0.json"


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


def unpack_xcb_cursor(deb, expected_sha, staging, patchelf):
    """Use the pinned archive, or the distro package already installed in CI."""
    digest = windows.freeze_identity.digest
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    files = None
    if deb is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha) or digest(deb) != expected_sha:
            raise ValueError("libxcb-cursor0 .deb SHA-256 mismatch")
        fields = run(["dpkg-deb", "-f", deb, "Package", "Version", "Architecture"], env=env)
        control = dict(line.split(": ", 1) for line in fields.stdout.splitlines())
        root = staging
    else:
        package = "libxcb-cursor0:amd64"
        try:
            fields = run(["dpkg-query", "-s", package], env=env)
        except RuntimeError as error:
            raise ValueError("Provide --xcb-cursor-deb and --xcb-cursor-sha256; no installed amd64 libxcb-cursor0") from error
        control = dict(line.split(": ", 1) for line in fields.stdout.splitlines() if ": " in line and not line.startswith(" "))
        if control.get("Status") != "install ok installed" or run(["dpkg", "--verify", package], env=env).stdout.strip():
            raise ValueError("Installed libxcb-cursor0 is not verified; provide the pinned .deb")
        files = set(run(["dpkg-query", "-L", package], env=env).stdout.splitlines())
        root = Path("/")
    if control.get("Package") != "libxcb-cursor0" or control.get("Architecture") != "amd64" or not control.get("Version"):
        raise ValueError("Expected an amd64 libxcb-cursor0 package")
    if deb is not None:
        staging.mkdir()
        run(["dpkg-deb", "-x", deb, staging], env=env)
    library_dir = root / "usr/lib/x86_64-linux-gnu"
    library = (library_dir / XCB_CURSOR).resolve(strict=True)
    copyright = root / "usr/share/doc/libxcb-cursor0/copyright"
    if (library.parent != library_dir.resolve() or not library.is_relative_to(root.resolve())
            or not library.is_file() or not copyright.is_file() or copyright.is_symlink()
            or not copyright.resolve().is_relative_to(root.resolve()) or not copyright.stat().st_size
            or (files is not None and not {str(library), str(copyright)} <= files)):
        raise ValueError("libxcb-cursor0 package lacks a safe SONAME file or copyright notice")
    if run([patchelf, "--print-soname", library], env=env).stdout.strip() != XCB_CURSOR:
        raise ValueError("libxcb-cursor0 ELF SONAME mismatch")
    if deb is not None and digest(deb) != expected_sha:
        raise ValueError("libxcb-cursor0 .deb changed during extraction")
    return library, copyright, {"package": control["Package"], "version": control["Version"],
        "architecture": control["Architecture"], "deb_sha256": expected_sha,
        "library_sha256": digest(library), "copyright_sha256": digest(copyright)}


def stage_xcb_cursor(gui, library, expected_sha):
    """Add only the licensed SONAME to the owned PyInstaller payload before sealing."""
    target = gui / "_internal" / XCB_CURSOR
    digest = windows.freeze_identity.digest
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise ValueError("Expected an ordinary frozen GUI _internal directory")
    if target.is_symlink() or (target.exists() and (not target.is_file() or digest(target) != expected_sha)):
        raise ValueError("Conflicting frozen libxcb-cursor.so.0; use a clean producer")
    if not target.exists():
        shutil.copy2(library, target)
    if digest(target) != expected_sha:
        raise ValueError("Staged libxcb-cursor.so.0 differs from the approved input")


def verify_gui_xcb(package, evidence, expected):
    """Check ELF relocation with the bootloader's library root, without starting Qt."""
    internal = (package / "gui/_internal").resolve(strict=True)
    cursor = internal / XCB_CURSOR
    license_dir = package / "licenses"
    copyright = license_dir / XCB_COPYRIGHT
    receipt_path = license_dir / XCB_RECEIPT
    digest = windows.freeze_identity.digest
    if (license_dir.is_symlink() or any(path.is_symlink() or not path.is_file() or not path.stat().st_size
                                       for path in (receipt_path, copyright))):
        raise RuntimeError("xcb copyright and receipt must be nonempty ordinary files")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (receipt != expected or not cursor.is_file() or cursor.is_symlink()
            or digest(cursor) != expected["library_sha256"] or digest(copyright) != expected["copyright_sha256"]):
        raise RuntimeError("Bundled libxcb-cursor0 evidence differs from the approved package input")
    qt = internal / "PySide6/Qt/plugins"
    plugins = [qt / "platforms/libqxcb.so", *sorted((qt / "xcbglintegrations").glob("libqxcb-*-integration.so"))]
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LD_LIBRARY_PATH": str(internal)}
    system_roots = [Path(path).resolve() for path in ("/lib", "/lib64", "/usr/lib", "/usr/lib64")]
    for plugin in plugins:
        if not plugin.is_file() or not plugin.resolve().is_relative_to(internal):
            raise RuntimeError(f"Frozen xcb plugin is missing or escapes the payload: {plugin}")
        result = run(["ldd", "-r", plugin], env=env)
        output = result.stdout + result.stderr
        (evidence / (plugin.name + ".ldd.txt")).write_text(output, encoding="utf-8")
        if "not found" in output or "undefined symbol:" in output:
            raise RuntimeError(f"Unresolved xcb plugin dependencies of {plugin}:\n{output}")
        resolved = {name: Path(path).resolve() for name, path in
                    re.findall(r"^\s*(\S+)\s+=>\s+(/.+?)\s+\(0x", output, re.MULTILINE)}
        if (resolved.get(XCB_CURSOR) != cursor
                or not any(name.startswith("libQt6XcbQpa.so.") and path.is_relative_to(internal)
                           for name, path in resolved.items())):
            raise RuntimeError(f"{plugin} did not resolve the bundled xcb cursor and Qt platform library")
        if any((name.startswith("libQt6") and not path.is_relative_to(internal))
               or not any(path.is_relative_to(root) for root in (internal, *system_roots))
               for name, path in resolved.items()):
            raise RuntimeError(f"{plugin} resolved an unexpected external library; see {evidence}")
    return len(plugins)


def gui_entrypoint(package, expect_gui):
    folder = package / "gui"
    launcher = folder / "G4UniversalSimGUI"
    if not expect_gui:
        if os.path.lexists(folder):
            raise RuntimeError("--skip-gui requires a backend-only package without a GUI payload")
        return None
    if folder.is_symlink() or launcher.is_symlink() or not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise RuntimeError(f"Expected executable frozen GUI launcher: {launcher}")
    return launcher


def verify(package, data_dir, *, expect_gui, require_3d, xcb_receipt):
    gui = gui_entrypoint(package, expect_gui)
    env = clean_environment()
    evidence_root = OUT / "package-verification"
    evidence_root.mkdir(exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="linux-", dir=evidence_root))
    backend = package / "bin/G4UniversalSim"
    gui_profile = None
    xcb_plugins = 0
    if gui is not None:
        declaration = json.loads((package / "gui" / windows.freeze_identity.RECEIPT).read_text(encoding="utf-8"))
        gui_profile = declaration.get("with_3d")
        if type(gui_profile) is not bool:
            raise ValueError("Frozen GUI receipt has no explicit 3D profile")
        if require_3d and not gui_profile:
            raise ValueError("Final full 3D publication cannot reuse a degraded GUI profile")
        windows.freeze_identity.verify(package / "gui", root=ROOT, kind="gui", with_3d=gui_profile)
        xcb_plugins = verify_gui_xcb(package, evidence, xcb_receipt)
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
        if gui is not None:
            gui_env = dict(env, G4USIM_RECOVERY_DIR=str(evidence / "recovery"))
            result = run([gui, "--self-test", evidence / "gui-selftest.json"], env=gui_env, timeout=300)
            report = json.loads((evidence / "gui-selftest.json").read_text(encoding="utf-8"))
            if not report.get("ok") or not report.get("frozen") or Path(report.get("default_backend", "")) != backend:
                raise RuntimeError(f"Frozen GUI failed: {report}")
        report = {"status": "verified", "backend_events": 50, "data_required_complete": True,
                  "python_root_read_write": helper.is_file(), "frozen_gui": gui is not None, "evidence_directory": str(evidence),
                  "frozen_gui_3d_profile": gui_profile, "xcb_elf_plugins_checked": xcb_plugins,
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
    parser.add_argument("--xcb-cursor-deb", type=Path, help="Approved local amd64 libxcb-cursor0 Debian package")
    parser.add_argument("--xcb-cursor-sha256", help="SHA-256 of the approved .deb")
    args = parser.parse_args()
    if not args.patchelf:
        parser.error("A patchelf executable is required")
    if (args.xcb_cursor_deb is None) != (args.xcb_cursor_sha256 is None):
        parser.error("Provide --xcb-cursor-deb and --xcb-cursor-sha256 together")
    if args.skip_gui and args.xcb_cursor_deb is not None:
        parser.error("xcb cursor input options require a GUI profile")
    build = args.build_dir.absolute()
    windows.CACHE = build / "CMakeCache.txt"
    windows.BUILD = build
    exe = build / "G4UniversalSim"
    package = OUT / "package" / f"G4UniversalSim-{windows.version()}-linux-x86_64"
    if args.verify_existing:
        gui_entrypoint(package, not args.skip_gui)
    windows.check_fingerprint(exe)
    # Validate the explicit dependency before replacing any owned package staging.
    if not args.verify_existing or not args.skip_gui:
        work_root = args.freeze_work_root.absolute() if args.freeze_work_root else Path.home() / ".cache/g4usim-package-work"
        work_root.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="g4usim-package-freeze-", dir=work_root))
    xcb_receipt = None
    if not args.skip_gui:
        library, copyright, xcb_receipt = unpack_xcb_cursor(
            args.xcb_cursor_deb, args.xcb_cursor_sha256, work / "xcb-cursor", args.patchelf)
    verify_options = {"expect_gui": not args.skip_gui, "require_3d": not args.no_3d, "xcb_receipt": xcb_receipt}
    if args.verify_existing:
        evidence = verify(package, args.data_dir.absolute(), **verify_options)
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
        if resource == windows.EXPORT_TEMPLATE_RESOURCE:
            # Materialized from packaging/export_template_manifest.json below;
            # the repository has no export-template/ directory.
            continue
        windows.copy_tree(ROOT / resource, package / resource)
    windows.build_export_template(package)
    for name in ("README.md", "CHANGELOG.md"):
        shutil.copy2(ROOT / name, package / name)
    shutil.copytree(ROOT / "packaging/licenses", package / "licenses")
    xcb_notice = (f"libxcb-cursor0 {xcb_receipt['version']} is included for Qt xcb; "
                  f"see licenses/{XCB_COPYRIGHT} and licenses/{XCB_RECEIPT}.\n"
                  if not args.skip_gui else "")
    (package / "THIRD_PARTY_NOTICES.md").write_text(
        "# Linux runtime components\n\nGeant4 " + windows.geant4_version() +
        " (Geant4 Software License); Xerces-C (Apache-2.0); PySide6/Qt (LGPL-3.0); "
        "Python and scientific helper dependencies retain their included distribution notices.\n"
        + xcb_notice +
        "System glibc, graphics/display drivers and remaining system ELF dependencies are host prerequisites.\n"
        "This archive does not contain Geant4 data; matching data can be installed as a separate reviewed artifact.\n",
        encoding="utf-8")
    if not args.skip_gui:
        # Freeze on native Linux storage; the cursor participates in the normal GUI seal.
        shutil.copytree(windows.build_gui(work / "gui", not args.no_3d,
            prepare_payload=lambda gui: stage_xcb_cursor(gui, library, xcb_receipt["library_sha256"])),
            package / "gui")
        shutil.copy2(copyright, package / "licenses" / XCB_COPYRIGHT)
        (package / "licenses" / XCB_RECEIPT).write_text(json.dumps(xcb_receipt, indent=2) + "\n", encoding="utf-8")
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
    evidence = verify(package, args.data_dir.absolute(), **verify_options)
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
