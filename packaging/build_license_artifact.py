"""Retain actual local dependency license texts and source package records.

For a conda-style SDK prefix this reads each selected package's installed record
and existing package-cache info/licenses directory. No terms or source URLs are
invented, and nothing in the selected environment/cache is modified.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.parse
import zipfile
from pathlib import Path

from build_install_catalog import catalog_from_archive, portable_sources
from build_package import OUT, geant4_version, version


def build(prefix, *, platform, output_name):
    prefix = Path(prefix).absolute()
    work = Path(tempfile.mkdtemp(prefix="g4usim-license-evidence-"))
    records = []
    for record_path in sorted((prefix / "conda-meta").glob("*.json")):
        package = json.loads(record_path.read_text(encoding="utf-8"))
        if not any(name.startswith(("include/", "lib/", "bin/", "libexec/", "plugins/", "mkspecs/"))
                   and not name.startswith("lib/python") for name in package.get("files", [])):
            continue
        name = package["name"] + "-" + package["version"] + "-" + package.get("build", "unknown")
        cache = Path(package.get("link", {}).get("source", ""))
        license_root = cache / "info/licenses"
        copied = []
        if license_root.is_dir():
            for source in sorted(license_root.rglob("*")):
                if source.is_file():
                    relative = Path(name) / source.relative_to(license_root)
                    target = work / "texts" / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    copied.append("texts/" + relative.as_posix())
        url = package.get("url", "")
        parsed = urllib.parse.urlparse(url)
        if parsed.username or parsed.password or parsed.query:
            url = None
        records.append({"name": package["name"], "version": package["version"], "build": package.get("build"),
                        "declared_license": package.get("license"), "source_package_url": url,
                        "original_record": str(record_path), "copied_license_texts": copied})
    if not records:
        raise ValueError("The selected prefix has no actual source package records")
    evidence = {"schema": "g4usim_dependency_license_evidence_v1", "selected_prefix": str(prefix), "packages": records,
                "scope": "Actual package records and available unmodified upstream license texts; precise payload inventory determines bundled files"}
    (work / "LICENSE-EVIDENCE.json").write_text(json.dumps(evidence, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    archive = OUT / f"{output_name}.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as output:
        for file in sorted(work.rglob("*")):
            if file.is_file():
                output.write(file, file.relative_to(work))
    catalog = catalog_from_archive(archive, profile="runtime", platform=platform, architecture="x86_64", version=version(),
                                   origin=f"Actual dependency package-cache license texts selected by installed records under {prefix}",
                                   license_path="LICENSE-EVIDENCE.json", license_expression="LicenseRef-Upstream-Component-Notices",
                                   license_source="Unmodified upstream texts and exact source package records in this artifact",
                                   geant4_version=geant4_version(prefix), components=["dependency_license_evidence"])
    artifact = catalog["releases"][0]["artifacts"][0]
    artifact.update(id="dependency-notices", target="licenses/component-evidence")
    portable_sources(catalog, OUT)
    target = OUT / f"{output_name}.catalog.json"
    with target.open("x", encoding="utf-8") as output:
        json.dump(catalog, output, ensure_ascii=True, indent=2)
        output.write("\n")
    print(json.dumps({"status": "assembled", "catalog": str(target), "package_records": len(records),
                      "copied_license_texts": sum(len(record["copied_license_texts"]) for record in records)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--output-name", required=True)
    arguments = parser.parse_args()
    if arguments.output_name in (".", "..") or not __import__("re").fullmatch(r"[A-Za-z0-9_.-]+", arguments.output_name):
        parser.error("Output name must be a portable basename")
    build(**vars(arguments))
