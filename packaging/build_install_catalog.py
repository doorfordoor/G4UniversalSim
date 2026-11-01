"""Create a catalog from actual reviewed local archives, never invented metadata.

Use --help. This records an explicitly supplied provenance and license text from
the archive; it does not prove the authenticity of a publisher or its license.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.environment_install import (  # noqa: E402
    CATALOG_SCHEMA, _artifact, _file_hash, _no_links, _select, inspect_archive,
)


def catalog_from_archive(archive, *, profile, platform, architecture, version, origin,
                         license_path, license_expression, license_source, entrypoints=None,
                         dependencies=None, components=None, sdk=None, geant4_version=None):
    archive = Path(archive).absolute()
    _no_links(archive)
    archive_format = "tar.gz" if archive.name.endswith(".tar.gz") else "zip"
    files = inspect_archive(archive, archive_format)
    license_file = next((file for file in files if file["path"] == license_path), None)
    if license_file is None:
        raise ValueError(f"License text is not present in archive: {license_path}")
    artifact = _artifact({"id": "application", "source": {"kind": "local", "path": str(archive), "origin": origin},
                          "format": archive_format, "size_bytes": archive.stat().st_size,
                          "unpacked_size_bytes": sum(file["size_bytes"] for file in files),
                          "sha256": _file_hash(archive), "target": "", "files": files,
                          "license": {"expression": license_expression, "source": license_source,
                                      "path": license_path, "sha256": license_file["sha256"]}})
    release = {"profile": profile, "platform": platform, "architecture": architecture, "version": version,
               "artifacts": [artifact], "entrypoints": entrypoints or {}, "dependencies": dependencies or [],
               "components": components or [], "sdk_build_status": "not_verified" if profile == "sdk" else "not_applicable"}
    if sdk:
        release["sdk"] = sdk
    if geant4_version is not None:
        if not __import__("re").fullmatch(r"\d+\.\d+\.\d+", geant4_version):
            raise ValueError("Geant4 version must be an exact independently sourced major.minor.patch")
        release["geant4_version"] = geant4_version
    result = {"schema": CATALOG_SCHEMA, "reviewed": True, "releases": [release],
              "provenance_notice": "Explicit local publisher input; SHA256 is byte identity, not source authenticity"}
    _select(result, profile, platform, architecture, version)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", required=True)
    parser.add_argument("--profile", choices=("runtime", "sdk"), required=True)
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--architecture", choices=("x86_64", "aarch64"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--license-path", required=True)
    parser.add_argument("--license-expression", required=True)
    parser.add_argument("--license-source", required=True)
    parser.add_argument("--entrypoints", help="JSON object mapping capability to archive-relative executable")
    parser.add_argument("--dependencies", help="JSON array; SDK requires explicit compiler and cmake requirements")
    parser.add_argument("--components", help="Comma separated actual component inventory")
    parser.add_argument("--sdk", help="JSON SDK probe descriptor (geant4_dir, probe_source, dependency_prefixes)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = catalog_from_archive(args.archive, profile=args.profile, platform=args.platform,
                                  architecture=args.architecture, version=args.version, origin=args.origin,
                                  license_path=args.license_path, license_expression=args.license_expression,
                                  license_source=args.license_source,
                                  entrypoints=json.loads(args.entrypoints) if args.entrypoints else None,
                                  dependencies=json.loads(args.dependencies) if args.dependencies else None,
                                  sdk=json.loads(args.sdk) if args.sdk else None,
                                  components=args.components.split(",") if args.components else None)
    output = Path(args.output)
    _no_links(output)
    portable_sources(result, output.parent)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write("\n")
    return 0


def portable_sources(catalog, catalog_directory):
    """Use relocatable descendant references; never create '..' escape references."""
    directory = Path(catalog_directory).absolute()
    for release in catalog["releases"]:
        for artifact in release["artifacts"]:
            source = artifact["source"]
            if source["kind"] == "local":
                try:
                    source["path"] = Path(source["path"]).relative_to(directory).as_posix()
                except ValueError:
                    raise ValueError("Portable catalogs require archives beside or below the catalog file")
    return catalog


if __name__ == "__main__":
    raise SystemExit(main())
