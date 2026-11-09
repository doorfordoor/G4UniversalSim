"""Assemble actual Geant4 development files and a reproducible consumer probe.

The SDK artifact can be added to an existing runtime/data catalog or installed
independently for development. Compiler and CMake are explicit host requirements;
this builder never installs them or modifies an existing SDK.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
import stat
import re
from pathlib import Path

import build_package
from build_install_catalog import catalog_from_archive, portable_sources

ROOT = build_package.ROOT
OUT = build_package.OUT
PROBE_CMAKE = '''cmake_minimum_required(VERSION 3.16)
project(G4UniversalSimSDKProbe LANGUAGES CXX)
find_package(Geant4 REQUIRED)
add_executable(g4usim_sdk_probe main.cc)
target_compile_features(g4usim_sdk_probe PRIVATE cxx_std_17)
target_include_directories(g4usim_sdk_probe PRIVATE ${Geant4_INCLUDE_DIRS})
target_link_libraries(g4usim_sdk_probe PRIVATE ${Geant4_LIBRARIES})
'''
PROBE_SOURCE = '''#include "G4Version.hh"
#include "G4ThreeVector.hh"
#include "G4UnitsTable.hh"
#include "G4SystemOfUnits.hh"
#include <iostream>
int main() {
    G4ThreeVector vector(1., 2., 3.);
    if (vector.mag2() != 14.) return 2;
    std::cout << G4Version << " " << G4BestUnit(1.*CLHEP::MeV, "Energy") << " SDK consumer link/run verified\\n";
    return 0;
}
'''


def copy_development_tree(source, target, *, selected_prefix, skipped, ancestors=()):
    """Dereference files, preserve real directories, omit cyclic legacy aliases."""
    canonical = source.resolve(strict=True)
    if not canonical.is_relative_to(selected_prefix.resolve(strict=True)):
        raise ValueError(f"SDK dependency link escapes its explicitly selected prefix: {source}")
    if canonical in ancestors:
        skipped.append(str(source))
        return
    target.mkdir(parents=True, exist_ok=True)
    for entry in source.iterdir():
        if entry.name in ("__pycache__", "terminfo") or entry.name.endswith((".pyc", ".pdb", ".ilk")) \
                or entry.name in ("python", "python3") or entry.name.startswith("python3."):
            continue
        if entry.is_dir():
            copy_development_tree(entry, target / entry.name, selected_prefix=selected_prefix,
                                  skipped=skipped, ancestors=(*ancestors, canonical))
        elif entry.is_file():
            resolved = entry.resolve(strict=True)
            if not resolved.is_relative_to(selected_prefix.resolve(strict=True)):
                raise ValueError(f"SDK file link escapes its selected prefix: {entry}")
            shutil.copy2(entry, target / entry.name, follow_symlinks=True)
        else:
            raise ValueError(f"SDK contains a dangling link or special file: {entry}")


def build_sdk(*, geant4_prefix, platform, architecture, version, output_name, runtime_catalog=None, qt_prefix=None, remove_staging=False):
    if output_name in (".", "..") or not isinstance(output_name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", output_name):
        raise ValueError("Output name must be a non-dot portable basename")
    geant4_prefix = Path(geant4_prefix).absolute()
    sys.path.insert(0, str(ROOT / "gui"))
    from g4usim_gui.core.environment_install import load_catalog, _no_links
    _no_links(geant4_prefix)
    if not (geant4_prefix / "lib/cmake/Geant4/Geant4Config.cmake").is_file():
        raise ValueError("The selected prefix is not an actual Geant4 development installation")
    # The standalone H2 component opens this exact path. Capture only its
    # required fixture, before replacing any existing SDK staging/publication.
    niel_relative = Path("scenarios/semiconductor/niel/si_proton.csv")
    niel_source = ROOT / niel_relative
    _no_links(niel_source)
    if not stat.S_ISREG(niel_source.lstat().st_mode):
        raise ValueError(f"SDK H2 component fixture is not a regular file: {niel_source}")
    niel_bytes = niel_source.read_bytes()
    staging_root = (Path.home() / ".cache/g4usim-sdk-package") if platform == "linux" else OUT / "sdk-package"
    _no_links(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)
    work = staging_root / output_name
    _no_links(work)
    resolved_root = staging_root.resolve()
    resolved_work = work.resolve()
    if resolved_work == resolved_root or not resolved_work.is_relative_to(resolved_root):
        raise ValueError("SDK staging target escaped its explicit root")
    for selected_source in [geant4_prefix, *([Path(qt_prefix).absolute()] if qt_prefix else [])]:
        _no_links(selected_source)
        resolved_source = selected_source.resolve()
        if resolved_source.is_relative_to(resolved_work) or resolved_work.is_relative_to(resolved_source):
            raise ValueError("SDK staging cleanup cannot overlap an input development prefix")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    destination = work / "sdk/geant4"
    skipped_aliases = []
    for directory in ("include", "lib", "bin", "libexec", "mkspecs", "plugins"):
        source = geant4_prefix / directory
        if source.is_dir():
            # Development distributions have conventional soname/header links.
            # Copy actual bytes into regular archive members, never archive links.
            copy_development_tree(source, destination / directory, selected_prefix=geant4_prefix, skipped=skipped_aliases)
    dependencies = ["sdk/geant4"]
    if qt_prefix:
        qt_prefix = Path(qt_prefix).absolute()
        _no_links(qt_prefix)
        for directory in ("include", "lib", "bin", "plugins", "mkspecs", "libexec"):
            source = qt_prefix / directory
            if source.is_dir():
                copy_development_tree(source, work / "sdk/qt" / directory, selected_prefix=qt_prefix, skipped=skipped_aliases)
        dependencies.append("sdk/qt")
    source_root = work / "sdk/g4usim-source"
    source_root.mkdir()
    for directory in ("src", "include", "cmake", "config", "schema", "scripts", "tools", "macros", "test"):
        source = ROOT / directory
        if source.is_dir():
            build_package.copy_tree(source, source_root / directory)
    for name in ("main.cc", "CMakeLists.txt"):
        shutil.copy2(ROOT / name, source_root / name)
    niel_target = source_root / niel_relative
    niel_target.parent.mkdir(parents=True)
    niel_target.write_bytes(niel_bytes)
    probe = work / "sdk/probe"
    probe.mkdir(parents=True)
    (probe / "CMakeLists.txt").write_text(PROBE_CMAKE, encoding="utf-8")
    (probe / "main.cc").write_text(PROBE_SOURCE, encoding="utf-8")
    (work / "sdk/source-copy-receipt.json").write_text(json.dumps({"selected_geant4_prefix": str(geant4_prefix),
                                                                 "skipped_cyclic_directory_aliases": skipped_aliases,
                                                                 "omitted_non_development_directories": ["terminfo", "__pycache__", "python* runtime packages"]}, indent=2) + "\n", encoding="utf-8")
    shutil.copytree(ROOT / "packaging/licenses", work / "sdk/licenses")
    (work / "sdk/SDK-NOTICES.md").write_text(
        "# SDK component notices\n\nGeant4 development headers/libraries: Geant4 Software License (licenses/Geant4-LICENSE.txt).\n"
        "Xerces-C where present: Apache-2.0 (licenses/Xerces-C-LICENSE.txt and NOTICE).\n"
        "Qt development dependencies where present: LGPL-3.0 / upstream distribution terms, https://www.qt.io/licensing.\n"
        "Compiler and CMake are selected host tools, not installed or modified by this SDK.\n"
        "The bundled consumer is a compile/link/run check; it does not validate simulation physics.\n", encoding="utf-8")
    archive = OUT / f"{output_name}-sdk.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=4) as output:
        for file in sorted(work.rglob("*")):
            if file.is_file():
                output.write(file, file.relative_to(work))
    sdk = {"geant4_dir": "sdk/geant4/lib/cmake/Geant4", "probe_source": "sdk/probe", "dependency_prefixes": dependencies,
           "application_source": "sdk/g4usim-source"}
    if platform == "linux":
        sdk["cmake_paths"] = {"EXPAT_INCLUDE_DIR": "sdk/geant4/include", "EXPAT_LIBRARY": "sdk/geant4/lib/libexpat.so",
                              "ZLIB_INCLUDE_DIR": "sdk/geant4/include", "ZLIB_LIBRARY": "sdk/geant4/lib/libz.so",
                              "FREETYPE_INCLUDE_DIRS": "sdk/geant4/include/freetype2", "FREETYPE_LIBRARY": "sdk/geant4/lib/libfreetype.so"}
    catalog = catalog_from_archive(archive, profile="sdk", platform=platform, architecture=architecture, version=version,
                                   origin=f"Actual local Geant4 SDK files copied from {geant4_prefix}",
                                   license_path="sdk/SDK-NOTICES.md", license_expression="LicenseRef-Bundled-SDK-Notices",
                                   license_source="Bundled development component notices and upstream license texts",
                                   dependencies=[{"id": "compiler", "required": True, "kind": "host_toolchain"},
                                                 {"id": "cmake", "required": True, "kind": "host_toolchain"}], sdk=sdk,
                                   components=["geant4_sdk", "g4usim_backend_source", "sdk_consumer_probe"],
                                   geant4_version=build_package.geant4_version(geant4_prefix))
    catalog["releases"][0]["artifacts"][0]["id"] = "development-sdk"
    if runtime_catalog:
        runtime = load_catalog(runtime_catalog)
        runtime_release = runtime["releases"][0]
        if any(runtime_release.get(key) != value for key, value in (("version", version), ("platform", platform), ("architecture", architecture),
                                                                  ("geant4_version", build_package.geant4_version(geant4_prefix)))):
            raise ValueError("SDK/runtime release identity mismatch")
        for key in ("entrypoints", "configuration"):
            if key in runtime_release:
                catalog["releases"][0][key] = runtime_release[key]
        catalog["releases"][0]["artifacts"] = runtime_release["artifacts"] + catalog["releases"][0]["artifacts"]
        catalog["releases"][0]["components"] = runtime_release.get("components", []) + catalog["releases"][0]["components"]
    portable_sources(catalog, OUT)
    catalog_path = OUT / f"{output_name}-sdk.catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    if remove_staging:
        _no_links(work)
        if work.resolve() == resolved_root or not work.resolve().is_relative_to(resolved_root):
            raise ValueError("SDK final cleanup escaped its explicit staging root")
        shutil.rmtree(work)
    print(json.dumps({"status": "assembled_not_compiled", "catalog": str(catalog_path), "archive": str(archive),
                      "archive_bytes": archive.stat().st_size}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--geant4-prefix", required=True)
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--architecture", choices=("x86_64", "aarch64"), default="x86_64")
    parser.add_argument("--version", default=build_package.version())
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--runtime-catalog")
    parser.add_argument("--qt-prefix")
    parser.add_argument("--remove-staging", action="store_true", help="Remove only this verified SDK staging copy after archive/catalog publication")
    args = parser.parse_args()
    if args.output_name in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", args.output_name):
        parser.error("Output name must be a portable basename")
    build_sdk(**vars(args))


if __name__ == "__main__":
    main()
