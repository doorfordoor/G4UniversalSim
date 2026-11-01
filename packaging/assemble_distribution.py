"""Publish an offline release launcher with discoverable runtime and SDK catalogs.

Payload archives are built and checked first. This outer release directory then
contains the launcher plus install/catalog.json and neighboring artifact archives,
avoiding a self-embedded runtime hash or a catalog tied to a build-machine path.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.environment_install import _file_hash, _no_links, _select, load_catalog


def assemble(*, runtime_catalog, sdk_catalog, package_root, output, data_catalog=None, notices_catalog=None, archive_output=None):
    runtime = load_catalog(runtime_catalog)["releases"][0]
    sdk = load_catalog(sdk_catalog)["releases"][0]
    data = load_catalog(data_catalog)["releases"][0] if data_catalog else None
    notices = load_catalog(notices_catalog)["releases"][0] if notices_catalog else None
    if runtime.get("profile") != "runtime" or sdk.get("profile") != "sdk":
        raise ValueError("Select an actual runtime catalog and SDK catalog")
    for release in (runtime, sdk, *([data] if data else []), *([notices] if notices else [])):
        if not isinstance(release.get("geant4_version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+", release["geant4_version"]):
            raise ValueError("Formal distributions require an independently sourced exact Geant4 version for every component")
    for key in ("version", "platform", "architecture", "geant4_version"):
        if runtime.get(key) != sdk.get(key) or data is not None and runtime.get(key) != data.get(key) \
                or notices is not None and runtime.get(key) != notices.get(key):
            raise ValueError(f"Release identity mismatch: {key}")
    package_root, output = Path(package_root).absolute(), Path(output).absolute()
    if ".." in output.parts:
        raise ValueError("Distribution output must not contain parent traversal")
    _no_links(package_root)
    _no_links(output)
    if output.exists() or output == package_root or package_root in output.parents:
        raise ValueError("The outer distribution must be a new directory outside the payload package")
    if not (package_root / runtime.get("entrypoints", {}).get("gui", "missing-gui")).is_file():
        raise ValueError("A real frozen GUI launcher is required for a discoverable desktop distribution")
    base_artifacts = list(runtime["artifacts"])
    if data:
        base_artifacts += data["artifacts"]
        runtime["configuration"] = {"data_root": "data", "data_pointer": "bin/geant4-data.txt"}
    if notices:
        base_artifacts += notices["artifacts"]
    # SDK can be standalone or previously combined. Deduplicate only identical
    # artifacts; a same-id/different-hash ambiguity always rejects publication.
    all_artifacts = {}
    for artifact in base_artifacts + sdk["artifacts"]:
        previous = all_artifacts.get(artifact["id"])
        if previous and previous["sha256"] != artifact["sha256"]:
            raise ValueError(f"Artifact id collision: {artifact['id']}")
        all_artifacts[artifact["id"]] = artifact
    runtime["artifacts"] = base_artifacts
    sdk["artifacts"] = list(all_artifacts.values())
    sdk["entrypoints"] = copy.deepcopy(runtime.get("entrypoints", {}))
    if runtime.get("configuration"):
        sdk["configuration"] = copy.deepcopy(runtime["configuration"])
    catalog = {"schema": "g4usim_install_catalog_v1", "reviewed": True, "releases": [runtime, sdk],
               "distribution_layout": "offline_launcher_with_neighbor_artifacts_v1",
               "provenance_notice": "Verified byte identity of explicit local publisher inputs; not a publisher signature"}
    for release in catalog["releases"]:
        _select(catalog, release["profile"], release["platform"], release["architecture"], release["version"])
    # Check every source before copying any package or archive.
    filenames = {}
    for artifact in all_artifacts.values():
        source = artifact["source"]
        if source["kind"] != "local":
            raise ValueError("A complete offline distribution requires every archive locally available")
        archive = Path(source["path"])
        _no_links(archive)
        if not archive.is_file() or archive.stat().st_size != artifact["size_bytes"] or _file_hash(archive) != artifact["sha256"]:
            raise ValueError(f"Artifact failed byte verification: {archive}")
        if archive.name.casefold() in filenames and filenames[archive.name.casefold()] != artifact["sha256"]:
            raise ValueError("Different artifacts cannot share a distribution filename")
        filenames[archive.name.casefold()] = artifact["sha256"]
    shutil.copytree(package_root, output, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "install"))
    artifacts_dir = output / "install/artifacts"
    artifacts_dir.mkdir(parents=True)
    copied = set()
    for release in catalog["releases"]:
        for artifact in release["artifacts"]:
            source = artifact["source"]
            archive = Path(source["path"])
            if archive.name not in copied:
                shutil.copy2(archive, artifacts_dir / archive.name)
                if _file_hash(artifacts_dir / archive.name) != artifact["sha256"]:
                    raise ValueError("Copied distribution archive failed byte verification")
                copied.add(archive.name)
            source["path"] = "artifacts/" + archive.name
            source.pop("catalog_reference", None)
    catalog_path = output / "install/catalog.json"
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    (output / "INSTALL-OFFLINE.md").write_text(
        "# Offline installation\n\nRun the GUI in gui/. Open Environment / Install. The neighboring install/catalog.json provides "
        "both runtime and SDK profiles; no build-machine path or unpublished URL is required.\n"
        "Install only to a new user-selected child directory. SDK compilation requires selected existing build tools.\n"
        "The launcher is an outer release directory; payload archive hashes do not include this catalog or themselves.\n", encoding="utf-8")
    report = {"schema": "g4usim_distribution_v1", "status": "published", "directory": str(output),
              "catalog": str(catalog_path), "profiles": ["runtime", "sdk"], "artifact_count": len(copied),
              "catalog_sha256": _file_hash(catalog_path)}
    if archive_output:
        archive = Path(archive_output).absolute()
        if ".." in archive.parts:
            raise ValueError("Outer archive output must not contain parent traversal")
        _no_links(archive)
        if archive == output or output in archive.parents:
            raise ValueError("The outer distribution archive cannot contain itself")
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=4) as package:
            for file in sorted(output.rglob("*")):
                if file.is_file():
                    package.write(file, Path(output.name) / file.relative_to(output),
                                  compress_type=zipfile.ZIP_STORED if file.suffix == ".zip" else zipfile.ZIP_DEFLATED)
        report.update(archive=str(archive), archive_sha256=_file_hash(archive), archive_bytes=archive.stat().st_size)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runtime-catalog", required=True)
    parser.add_argument("--sdk-catalog", required=True)
    parser.add_argument("--data-catalog")
    parser.add_argument("--notices-catalog")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--archive-output", help="Optional new outer ZIP, outside the release directory")
    args = parser.parse_args()
    print(json.dumps(assemble(**vars(args)), indent=2))


if __name__ == "__main__":
    main()
