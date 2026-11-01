"""Build an explicit local Geant4-data artifact from a backend discovery receipt.

The data is kept separate from the application archive. No URLs or hashes are
guessed: files are selected from an actual --check-geant4-data JSON report and
the local bytes are hashed. Upstream dataset notices are retained unchanged.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

from build_install_catalog import catalog_from_archive, portable_sources


def geant4_version_from_discovery(report):
    text = report.get("geant4_version", "")
    match = re.search(r"geant4-(\d+)-(\d+)(?:-patch-(\d+))?", text)
    if match is None:
        raise ValueError("The actual backend discovery receipt lacks a recognized exact Geant4 version")
    return ".".join(str(int(value or 0)) for value in match.groups())


def add_data(catalog_path, discovery_path, output_archive, output_catalog, *, source_page,
             platform=None, architecture="x86_64", version="1.0.0"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
    from g4usim_gui.core.environment_install import load_catalog, _no_links, _relative
    catalog = load_catalog(catalog_path) if catalog_path else {
        "schema": "g4usim_install_catalog_v1", "reviewed": True,
        "releases": [{"profile": "runtime", "platform": platform, "architecture": architecture,
                      "version": version, "artifacts": [], "entrypoints": {}, "components": []}]}
    report = load_catalog(discovery_path)
    if not report.get("required_complete") or not isinstance(report.get("datasets"), list):
        raise ValueError("A real complete backend data-discovery receipt is required")
    release = catalog["releases"][0]
    discovered_version = geant4_version_from_discovery(report)
    if release.get("geant4_version") not in (None, discovered_version):
        raise ValueError("Runtime/data Geant4 versions differ")
    release["geant4_version"] = discovered_version
    archive = Path(output_archive).absolute()
    _no_links(archive)
    notices = ["Geant4 data: upstream dataset notices", "", f"Upstream download/version source: {source_page}",
               "Files below are copied from the explicitly selected existing local data installation.",
               "Dataset-specific restrictions and attributions remain in their original README files.",
               "G4EMLOW README states that these data are not for commercial use and must be used within Geant4.", ""]
    # Canonical folder names come from the backend, not the host's conda naming.
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=4) as output:
        for dataset in report["datasets"]:
            folder = _relative(dataset["folder"])
            source = Path(dataset.get("path", ""))
            if not dataset.get("found") or not source.is_dir():
                raise ValueError(f"Missing selected dataset: {folder}")
            _no_links(source)
            notices.append(f"{folder}: {source}")
            for file in sorted(source.rglob("*")):
                _no_links(file)
                if file.is_file():
                    output.write(file, f"{folder}/{file.relative_to(source).as_posix()}")
        output.writestr("DATASET-NOTICES.txt", "\n".join(notices) + "\n")
    data_catalog = catalog_from_archive(archive, profile="runtime", platform=release["platform"],
                                        architecture=release["architecture"], version=release["version"],
                                        origin=f"Local Geant4 dataset installation selected by actual backend discovery; {source_page}",
                                        license_path="DATASET-NOTICES.txt", license_expression="LicenseRef-Upstream-Dataset-Notices",
                                        license_source=source_page, geant4_version=discovered_version)
    artifact = data_catalog["releases"][0]["artifacts"][0]
    artifact.update(id="geant4-data", target="data")
    release["artifacts"].append(artifact)
    if release.get("entrypoints", {}).get("backend"):
        release["configuration"] = {"data_root": "data", "data_pointer": "bin/geant4-data.txt"}
    release.setdefault("components", []).append("geant4_data")
    portable_sources(catalog, Path(output_catalog).absolute().parent)
    target = Path(output_catalog)
    _no_links(target)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(catalog, stream, ensure_ascii=True, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog")
    parser.add_argument("--platform", choices=("windows", "linux"))
    parser.add_argument("--architecture", choices=("x86_64", "aarch64"), default="x86_64")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--discovery", required=True)
    parser.add_argument("--output-archive", required=True)
    parser.add_argument("--output-catalog", required=True)
    parser.add_argument("--source-page", required=True)
    args = parser.parse_args()
    if not args.catalog and not args.platform:
        parser.error("--platform is required for a standalone data component")
    add_data(args.catalog, args.discovery, args.output_archive, args.output_catalog, source_page=args.source_page,
             platform=args.platform, architecture=args.architecture, version=args.version)


if __name__ == "__main__":
    main()
