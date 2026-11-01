"""Offline I2 plans: malformed catalogs, target paths, profile and fact boundaries."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import platform
import sys
import tempfile
import zipfile
import shutil
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core import environment_install as service

spec = importlib.util.spec_from_file_location("g4usim_catalog_builder", ROOT / "packaging/build_install_catalog.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def fixture(root):
    archive = root / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("bin/backend", b"fixture backend bytes, not executable simulation")
        output.writestr("licenses/LICENSE.txt", b"test fixture license text\n")
        output.writestr("sdk/geant4/Geant4Config.cmake", b"# fixture only\n")
        output.writestr("sdk/probe/CMakeLists.txt", b"# fixture only\n")
    return builder.catalog_from_archive(
        archive, profile="runtime", platform="windows" if os.name == "nt" else "linux",
        architecture={"amd64": "x86_64", "arm64": "aarch64"}.get(platform.machine().lower(), platform.machine().lower()),
        version="1.2.3", origin="local test fixture, not a published product",
        license_path="licenses/LICENSE.txt", license_expression="LicenseRef-TestFixture",
        license_source="local test fixture", entrypoints={"backend": "bin/backend"})


def arguments(catalog, root):
    release = catalog["releases"][0]
    return {key: release[key] for key in ("profile", "platform", "architecture", "version")} | {
        "prefix": str(root / "installed"), "allowed_root": str(root)}


def rejected(catalog, args, code):
    result = service.create_plan(catalog, **args)
    assert not result["executable"] and result["status"] == "rejected", result
    assert result["diagnostics"][0]["code"] == code, result
    return result


def main():
    with tempfile.TemporaryDirectory(prefix="g4usim-install-plan-") as temp:
        root = Path(temp)
        catalog = fixture(root)
        args = arguments(catalog, root)
        before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("planning network")), \
                patch("subprocess.run", side_effect=AssertionError("planning subprocess")), \
                patch("pathlib.Path.mkdir", side_effect=AssertionError("planning mkdir")):
            plan = service.create_plan(catalog, **args, facts={"schema": "g4usim_environment_v1", "status": "historical"})
        assert plan["executable"] and plan["status"] == "planned", plan
        assert plan["capability_status"] == "not_probed"
        assert all(step["status"] == "planned" for step in plan["steps"])
        assert plan["environment_facts"]["status"] == "historical"
        assert plan["space"]["required_bytes"] > 0 and plan["space"]["available_bytes"] > 0
        assert sorted(str(path.relative_to(root)) for path in root.rglob("*")) == before
        assert not any(dependency["id"] == "compiler" for dependency in plan["dependencies"])
        for mutation, code in (
            (lambda value: value.update(schema="future"), "catalog_schema"),
            (lambda value: value.update(reviewed=False), "catalog_unreviewed"),
            (lambda value: value["releases"][0]["artifacts"][0].update(sha256="no"), "invalid_sha256"),
            (lambda value: value["releases"][0]["artifacts"][0].update(size_bytes=True), "invalid_size"),
            (lambda value: value["releases"][0]["artifacts"][0].update(license={}), "license_missing"),
            (lambda value: value["releases"][0]["artifacts"][0]["files"][0].update(path="../escape"), "archive_path"),
            (lambda value: value["releases"][0]["artifacts"][0]["files"][0].update(path="C:/escape"), "archive_path"),
            (lambda value: value["releases"][0]["artifacts"][0]["files"][0].update(path="CON.txt"), "archive_path"),
            (lambda value: value["releases"][0].update(dependencies=[{"id": "compiler"}]), "runtime_compiler"),
        ):
            changed = copy.deepcopy(catalog)
            mutation(changed)
            rejected(changed, args, code)
        rejected(catalog, args | {"version": "latest"}, "version")
        rejected(catalog, args | {"version": "9.9.9"}, "release_unavailable")
        rejected(catalog, args | {"profile": "unknown"}, "profile")
        rejected(catalog, args | {"prefix": "relative"}, "absolute_path_required")
        rejected(catalog, args | {"prefix": str(root)}, "root_prefix")
        rejected(catalog, args | {"prefix": str(root.parent / "outside")}, "outside_root")
        rejected(catalog, args | {"prefix": str(root / "missing" / "target")}, "parent_missing")
        (root / "installed").mkdir()
        rejected(catalog, args, "prefix_occupied")
        (root / "installed").rmdir()
        tx = root / ".installed.g4usim-install"
        tx.mkdir()
        rejected(catalog, args, "transaction_exists")
        tx.rmdir()
        changed = copy.deepcopy(catalog)
        changed["releases"][0]["profile"] = "sdk"
        rejected(changed, args | {"profile": "sdk"}, "sdk_dependencies")
        changed["releases"][0]["dependencies"] = [{"id": "compiler", "required": True}, {"id": "cmake", "required": True}]
        rejected(changed, args | {"profile": "sdk"}, "sdk_probe_missing")
        changed["releases"][0]["sdk"] = {"geant4_dir": "sdk/geant4", "probe_source": "sdk/probe"}
        sdk = service.create_plan(changed, **(args | {"profile": "sdk"}))
        assert sdk["executable"] and sdk["steps"][-1]["id"] == "sdk_compile_probe"
        assert sdk["capability_status"] == "not_probed"
        bad_json = root / "duplicate.json"
        bad_json.write_text('{"schema":1,"schema":2}', encoding="utf-8")
        try:
            service.load_catalog(bad_json)
        except service.InstallError as exc:
            assert exc.code == "duplicate_key"
        else:
            assert False, "Duplicate JSON keys accepted"
        outside = root / "real"
        outside.mkdir()
        link = root / "alias"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
        else:
            rejected(catalog, args | {"prefix": str(link / "installed")}, "linked_path")
            link.unlink()
        # The release launcher exposes both profiles through a neighbor catalog,
        # and remains installable after moving the entire release directory.
        distribution_spec = importlib.util.spec_from_file_location("g4usim_distribution", ROOT / "packaging/assemble_distribution.py")
        distribution_builder = importlib.util.module_from_spec(distribution_spec)
        distribution_spec.loader.exec_module(distribution_builder)
        runtime_catalog = copy.deepcopy(catalog)
        runtime_catalog["releases"][0]["geant4_version"] = "11.4.3"
        runtime_catalog["releases"][0]["entrypoints"]["gui"] = "bin/backend"
        sdk_catalog = copy.deepcopy(runtime_catalog)
        sdk_release = sdk_catalog["releases"][0]
        sdk_release["profile"] = "sdk"
        sdk_release["dependencies"] = [{"id": "compiler", "required": True}, {"id": "cmake", "required": True}]
        sdk_release["sdk"] = {"geant4_dir": "sdk/geant4", "probe_source": "sdk/probe"}
        runtime_path, sdk_path = root / "runtime-catalog.json", root / "sdk-catalog.json"
        runtime_path.write_text(json.dumps(runtime_catalog), encoding="utf-8")
        sdk_path.write_text(json.dumps(sdk_catalog), encoding="utf-8")
        launcher = root / "fixture-launcher"
        with zipfile.ZipFile(root / "runtime.zip") as source:
            source.extractall(launcher)  # This is the test's own fixed archive.
        distribution = root / "release"
        incompatible = copy.deepcopy(sdk_catalog)
        incompatible["releases"][0]["geant4_version"] = "11.3.2"
        sdk_path.write_text(json.dumps(incompatible), encoding="utf-8")
        try:
            distribution_builder.assemble(runtime_catalog=runtime_path, sdk_catalog=sdk_path,
                                           package_root=launcher, output=distribution)
        except ValueError as exc:
            assert "geant4_version" in str(exc)
        else:
            assert False, "Mixed Geant4 versions were published"
        assert not distribution.exists()
        incompatible["releases"][0].pop("geant4_version")
        sdk_path.write_text(json.dumps(incompatible), encoding="utf-8")
        try:
            distribution_builder.assemble(runtime_catalog=runtime_path, sdk_catalog=sdk_path,
                                           package_root=launcher, output=distribution)
        except ValueError as exc:
            assert "exact Geant4 version" in str(exc)
        else:
            assert False, "Unknown SDK Geant4 version was published"
        sdk_path.write_text(json.dumps(sdk_catalog), encoding="utf-8")
        distribution_report = distribution_builder.assemble(runtime_catalog=runtime_path, sdk_catalog=sdk_path,
                                                            package_root=launcher, output=distribution,
                                                            archive_output=root / "release.zip")
        assert distribution_report["profiles"] == ["runtime", "sdk"] and distribution_report["artifact_count"] == 1
        assert (root / "release.zip").is_file() and distribution_report["archive_bytes"] > 0
        with zipfile.ZipFile(root / "release.zip") as outer:
            assert "release/install/catalog.json" in outer.namelist()
        moved = root / "moved-release"
        distribution.rename(moved)
        published_catalog = service.load_catalog(moved / "install/catalog.json")
        assert {release["profile"] for release in published_catalog["releases"]} == {"runtime", "sdk"}
        assert not distribution.exists()
        moved_plan = service.create_plan(published_catalog, **args)
        assert moved_plan["executable"], moved_plan
        moved_receipt = service.execute_plan(moved_plan)
        assert moved_receipt["status"] == "published", moved_receipt
        assert service.verify_installation(args["prefix"])["file_count"] == 4
        assert service.uninstall_installation(args["prefix"])["status"] == "uninstalled"
        # Legacy directory aliases in an SDK must not recursively expand.
        sys.path.insert(0, str(ROOT / "packaging"))
        from build_sdk_package import copy_development_tree, build_sdk
        for bad_name in (".", "..", "../escape"):
            try:
                build_sdk(geant4_prefix=root, platform=args["platform"], architecture=args["architecture"],
                          version=args["version"], output_name=bad_name)
            except ValueError as exc:
                assert "basename" in str(exc)
            else:
                assert False, "Unsafe SDK cleanup basename accepted"
        sdk_source = root / "sdk-source"
        (sdk_source / "lib/compat").mkdir(parents=True)
        (sdk_source / "lib/library.so").write_bytes(b"fixture development library")
        alias = sdk_source / "lib/compat/ancestor"
        try:
            alias.symlink_to(sdk_source / "lib", target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
        else:
            copied = root / "sdk-copy"
            skipped = []
            copy_development_tree(sdk_source, copied, selected_prefix=sdk_source, skipped=skipped)
            assert (copied / "lib/library.so").read_bytes() == b"fixture development library"
            assert skipped == [str(alias)] and not (copied / "lib/compat/ancestor").exists()
            alias.unlink()
            host_tool = root / "compiler"
            host_tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            host_tool.chmod(0o755)
            host_alias = root / "compiler-alias"
            host_alias.symlink_to(host_tool)
            assert service._host_tool(host_alias) == host_tool.resolve()
            try:
                service._absolute(host_alias)
            except service.InstallError as exc:
                assert exc.code == "linked_path"
            else:
                assert False, "Host aliases must not loosen installation path checks"
            host_alias.unlink()
    print("I2 offline installation plans passed")


if __name__ == "__main__":
    main()
