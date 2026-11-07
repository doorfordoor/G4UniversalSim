"""Build and exercise the complete offline delivery on a native new work root.

This composes the normal producers and verify_installation_flow.py; it does not
implement another installer. Existing SDK/data inputs are read only. No network
download is performed by this coordinator. CI bootstrap supplies the SDK, data
discovery, Python build dependencies and host compiler/CMake.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import signal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.environment_install import _absolute, _file_hash, _host_tool, _no_links, load_catalog  # noqa: E402
from build_install_catalog import portable_sources  # noqa: E402
from build_package import geant4_version  # noqa: E402

SOURCE_DIRECTORIES = ("src", "include", "cmake", "gui", "scripts", "tools", "packaging", "config",
                      "macros", "schema", "scenarios", "examples", "test", "docs")
IGNORED = {"__pycache__", ".pytest_cache"}
OMITTED_SOURCE_PATHS = {"gui/.venv", "gui/venv", "gui/node_modules", "docs/verification", "docs/collab", "test/output"}
REQUIRED_PRODUCT_PATHS = ("gui/main.py", "gui/g4usim_gui/app.py", "gui/g4usim_gui/output/__init__.py",
                          "gui/g4usim_gui/output/provenance.py")


def describe_host_tools(cmake, compiler=None):
    """Resolve explicit executable selections before expensive delivery work."""
    result = {}
    for role, requested in (("cmake", cmake), ("compiler", compiler)):
        if requested is not None:
            resolved = _host_tool(requested)
            result[role] = {"requested": str(requested), "resolved": str(resolved),
                            "sha256": _file_hash(resolved), "scope": "Selected executable file identity; execution checked by SDK probes"}
    return result


def excluded_source_path(path):
    return any(part in IGNORED for part in path.parts) or path.as_posix() in OMITTED_SOURCE_PATHS


def snapshot_sources(destination):
    def ignore(directory, names):
        relative = Path(directory).relative_to(ROOT)
        return {name for name in names if excluded_source_path(relative / name) or name.endswith((".pyc", ".log"))}
    copied = {}
    destination.mkdir()
    for directory in SOURCE_DIRECTORIES:
        source = ROOT / directory
        if source.is_dir():
            shutil.copytree(source, destination / directory, ignore=ignore)
    for name in ("main.cc", "CMakeLists.txt", "CMakePresets.json", "README.md", "CHANGELOG.md"):
        if (ROOT / name).is_file():
            shutil.copy2(ROOT / name, destination / name)
    for file in destination.rglob("*"):
        if file.is_file():
            relative = file.relative_to(destination).as_posix()
            actual = _file_hash(file)
            if actual != _file_hash(ROOT / relative):
                raise ValueError(f"Source changed while creating the native delivery snapshot: {relative}")
            copied[relative] = actual
    # Freeze the GUI source set as well as the copied bytes. This rejects a source
    # added/removed during the snapshot instead of silently leaving it out.
    original_gui = {file.relative_to(ROOT).as_posix() for file in (ROOT / "gui").rglob("*.py")
                    if not excluded_source_path(file.relative_to(ROOT)) and not any(
                        parent.as_posix() in OMITTED_SOURCE_PATHS for parent in file.relative_to(ROOT).parents)}
    copied_gui = {name for name in copied if name.startswith("gui/") and name.endswith(".py")}
    if original_gui != copied_gui:
        raise ValueError("GUI source inventory changed while creating the delivery snapshot")
    for relative in REQUIRED_PRODUCT_PATHS:
        if relative not in copied or not (destination / relative).is_file():
            raise ValueError(f"Required product module was omitted from the delivery snapshot: {relative}")
    return {"schema": "g4usim_delivery_source_snapshot_v1", "origin": str(ROOT), "snapshot": str(destination), "files": copied}


def copy_reviewed_catalog(source, output):
    catalog = load_catalog(source)
    for release in catalog["releases"]:
        for artifact in release["artifacts"]:
            origin = artifact["source"]
            if origin["kind"] != "local":
                raise ValueError("CI input reuse requires local reviewed archives; this coordinator does not download")
            archive = _absolute(origin["path"])
            if archive.stat().st_size != artifact["size_bytes"] or _file_hash(archive) != artifact["sha256"]:
                raise ValueError(f"Reused archive differs from its reviewed identity: {archive}")
            target = output.parent / archive.name
            if target.exists():
                if target.stat().st_size != artifact["size_bytes"] or _file_hash(target) != artifact["sha256"]:
                    raise ValueError(f"CI input archive filename conflict: {target}")
            else:
                with archive.open("rb") as reader, target.open("xb") as writer:
                    shutil.copyfileobj(reader, writer, 1024 * 1024)
                if _file_hash(target) != artifact["sha256"]:
                    raise ValueError("Copied CI archive failed SHA256 verification")
            origin["path"] = str(target)
            origin.pop("catalog_reference", None)
    portable_sources(catalog, output.parent)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(catalog, stream, ensure_ascii=True, indent=2)
        stream.write("\n")


def archive_validation_evidence(work, source, *, reuse_gui=None, reuse_python_helper=None):
    """Preserve this invocation's actual freeze/probe receipts before cleanup."""
    work, source = Path(work), Path(source)
    evidence = work / "evidence"
    index_path = evidence / "index.json"
    records = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    known = {(record["source"], record["sha256"]) for record in records}
    selected = []
    output = source / "out"
    names = {"freeze.log", "binary-sources.json", "source-identity.json", "g4usim-freeze.json"}
    if output.exists():
        for path in output.rglob("*"):
            if path.is_file() and path.name in names:
                selected.append((path, evidence / "freeze/owned" / path.relative_to(output)))
    for kind, payload in (("gui", reuse_gui), ("python", reuse_python_helper)):
        if payload is not None:
            payload = Path(payload).absolute()
            for path in [payload / "g4usim-freeze.json", *(payload.parent.parent / name for name in names - {"g4usim-freeze.json"})]:
                if path.is_file():
                    selected.append((path, evidence / "freeze" / ("reused-" + kind) / path.name))
    for kind in ("consumer", "application"):
        build = work / "environments" / ("sdk-" + kind + "-build")
        if build.exists():
            for name in ("configure.log", "build.log", "run.log", "sdk-probe-receipt.json", "CMakeCache.txt"):
                path = build / name
                if path.is_file():
                    selected.append((path, evidence / "sdk" / kind / name))
            for path in (build / "CMakeFiles").glob("*/CMakeCXXCompiler.cmake"):
                selected.append((path, evidence / "sdk" / kind / path.relative_to(build)))
    for profile in ("runtime", "sdk"):
        parent = work / (profile + "-evidence")
        for name in ("flow-report.json", "sdk-consumer.json", "sdk-application.json"):
            path = parent / name
            if path.is_file():
                selected.append((path, evidence / profile / name))
    for original, target in selected:
        digest = _file_hash(original)
        if (str(original), digest) in known:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(target.stem + "-" + digest[:12] + target.suffix)
        with original.open("rb") as reader, target.open("xb") as writer:
            shutil.copyfileobj(reader, writer, 1024 * 1024)
        copied_digest = _file_hash(target)
        records.append({"source": str(original), "path": str(target.relative_to(work)), "sha256": copied_digest,
                        "size_bytes": target.stat().st_size, "source_stable_during_copy": digest == copied_digest == _file_hash(original),
                        "observed_time_ns": time.time_ns()})
        known.add((str(original), digest))
    if records:
        evidence.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps(records, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--geant4-prefix", type=Path, required=True)
    parser.add_argument("--discovery-json", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True, help="New or empty native directory; existing nonempty directories are refused")
    parser.add_argument("--cmake", required=True)
    parser.add_argument("--compiler")
    parser.add_argument("--generator")
    parser.add_argument("--patchelf", default=shutil.which("patchelf"))
    parser.add_argument("--reuse-gui", type=Path, help="Optional current sealed GUI; Windows only")
    parser.add_argument("--reuse-python-helper", type=Path, help="Optional current sealed helper; Windows only")
    parser.add_argument("--reuse-data-catalog", type=Path)
    parser.add_argument("--reuse-sdk-catalog", type=Path)
    parser.add_argument("--application-build", action="store_true", default=True, help="Full bundled SDK source build (always enabled for this acceptance gate)")
    parser.add_argument("--outer-zip", action="store_true", help="Explicitly retain an extra portable outer ZIP for local release delivery")
    parser.add_argument("--sdk-build-budget-bytes", type=int, default=512 * 1024 * 1024)
    parser.add_argument("--stage-timeout", type=float, default=3600)
    args = parser.parse_args(argv)
    work = _absolute(args.work_root.absolute())
    if work == ROOT or ROOT in work.parents and work.relative_to(ROOT).parts[0] != "out":
        parser.error("Work root cannot overlap the source inputs; use a native external directory or this checkout's out/")
    if work.exists() and any(work.iterdir()):
        parser.error("Work root is nonempty; choose a new directory to preserve prior evidence")
    if not 0 < args.stage_timeout <= 14400:
        parser.error("Stage timeout must be positive and at most 14400 seconds")
    if args.sdk_build_budget_bytes <= 0:
        parser.error("SDK build budget must be positive")
    build = _absolute(args.build_dir.absolute())
    prefix = _absolute(args.geant4_prefix.absolute())
    discovery_path = _absolute(args.discovery_json.absolute())
    g4_version = geant4_version(prefix)
    cache = (build / "CMakeCache.txt").read_text(encoding="utf-8", errors="replace")
    selected = re.search(r"^Geant4_DIR:[A-Z_]+=(.+)$", cache, re.M)
    if selected is None or Path(selected.group(1).strip()).resolve() != (prefix / "lib/cmake/Geant4").resolve():
        parser.error("CMake build and explicitly selected Geant4 SDK differ")
    host = "windows" if os.name == "nt" else platform.system().lower()
    if host not in ("windows", "linux"):
        parser.error("Only actual Windows/Linux delivery hosts are supported")
    if host == "linux" and (args.reuse_gui or args.reuse_python_helper):
        parser.error("Linux producer currently freezes its own current payloads; Windows reuse options do not apply")
    work.mkdir(parents=True, exist_ok=True)
    logs = work / "logs"
    logs.mkdir()
    report = {"schema": "g4usim_ci_delivery_v1", "status": "running", "stages": [], "platform": host,
              "geant4_version": g4_version, "origin_checkout": str(ROOT), "work_root": str(work),
              "host_boundary": "Caller-supplied local or CI host; a clean process environment alone is not a fresh OS claim"}
    report["initial_free_bytes"] = shutil.disk_usage(work).free
    report["space_checks"] = []
    report["owned_cleanup"] = []
    def checkpoint():
        (work / "delivery-report.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    def stage(name, arguments):
        entry = {"stage": name, "argv": list(map(str, arguments)), "log": str(logs / (name + ".log")), "exit_code": None}
        report["stages"].append(entry)
        checkpoint()
        started = time.monotonic()
        try:
            with Path(entry["log"]).open("xb") as log:
                process = subprocess.Popen(entry["argv"], cwd=source, stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=os.name != "nt",
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                entry["pid"] = process.pid
                try:
                    entry["exit_code"] = process.wait(timeout=args.stage_timeout)
                    entry["log_finalized"] = True
                except subprocess.TimeoutExpired:
                    entry["status"] = "timeout"
                    if os.name == "nt":
                        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/taskkill.exe"
                        termination = subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                                                     stdout=log, stderr=subprocess.STDOUT, timeout=30)
                        entry["termination_exit_code"] = termination.returncode
                        entry["log_finalized"] = termination.returncode == 0
                    else:
                        for signum in (signal.SIGTERM, signal.SIGKILL):
                            try:
                                os.killpg(process.pid, signum)
                            except ProcessLookupError:
                                pass
                            if signum == signal.SIGTERM:
                                try:
                                    process.wait(timeout=5)
                                except subprocess.TimeoutExpired:
                                    pass
                        entry["log_finalized"] = True
                    process.wait(timeout=30)
                    raise TimeoutError(f"Delivery stage {name} exceeded its limit; owned process tree termination is recorded")
            assert entry["exit_code"] == 0, f"Delivery stage {name} failed with exit {entry['exit_code']}; see {entry['log']}"
        finally:
            entry["elapsed_seconds"] = time.monotonic() - started
            log_path = Path(entry["log"])
            entry["log_sha256"] = _file_hash(log_path) if log_path.is_file() else None
            entry["log_hash_observed_time_ns"] = time.time_ns()
            try:
                report["archived_evidence_count"] = len(archive_validation_evidence(
                    work, source, reuse_gui=args.reuse_gui, reuse_python_helper=args.reuse_python_helper))
            except Exception as archive_error:
                entry["evidence_archive_error"] = str(archive_error)
                if entry.get("exit_code") == 0:
                    raise RuntimeError(f"Successful stage {name} could not retain its required evidence: {archive_error}") from archive_error
            checkpoint()
    def space_check(name, required, *, basis):
        available = shutil.disk_usage(work).free
        observation = {"stage": name, "required_additional_bytes": int(required), "available_bytes": available, "basis": basis}
        report["space_checks"].append(observation)
        checkpoint()
        if available < required:
            raise OSError(f"Insufficient native disk space before {name}: need {required} additional bytes, available {available}")
    def remove_owned(path):
        _no_links(path)
        resolved = path.resolve()
        if resolved == work.resolve() or not resolved.is_relative_to(work.resolve()):
            raise ValueError(f"Refusing to clean outside this coordinator's new work root: {path}")
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            digest = _file_hash(path)
            path.unlink()
            report["owned_cleanup"].append({"path": str(path), "sha256": digest, "status": "removed_owned_intermediate"})
            checkpoint()
            return
        report["owned_cleanup"].append({"path": str(path), "status": "removed_owned_intermediate"})
        checkpoint()
    checkpoint()
    try:
        source = work / "source"
        report["host_tools"] = describe_host_tools(args.cmake, args.compiler)
        args.cmake = report["host_tools"]["cmake"]["resolved"]
        if args.compiler is not None:
            args.compiler = report["host_tools"]["compiler"]["resolved"]
        checkpoint()
        # This is a lower-bound preflight while archive/frozen sizes are not yet
        # known. The complete measured runtime/SDK peak is checked before flows.
        data_discovery = load_catalog(discovery_path)
        data_size = 0
        for dataset in data_discovery.get("datasets", []):
            if dataset.get("found"):
                data_size += sum(file.stat().st_size for file in Path(dataset["path"]).rglob("*") if file.is_file())
        space_check("source-and-data", data_size * 3 + 256 * 1024 * 1024,
                    basis={"actual_discovered_data_bytes": data_size, "frozen_runtime_bytes": None,
                           "scope": "Provisional lower bound; full measured archive/payload peak checked later"})
        snapshot = snapshot_sources(source)
        (work / "source-snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        report["snapshot_file_count"] = len(snapshot["files"])
        report["source_snapshot_sha256"] = _file_hash(work / "source-snapshot.json")
        workflow = ROOT / ".github/workflows/full-installation.yml"
        report["workflow_sha256"] = _file_hash(workflow) if workflow.is_file() else None
        head = subprocess.run(["git", "-c", "core.longpaths=true", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=30)
        report["origin_git_commit"] = head.stdout.strip() if head.returncode == 0 else "unknown"
        output = source / "out"
        output.mkdir()
        environments = work / "environments"
        environments.mkdir()
        app_version_match = re.search(r"project\(G4UniversalSim VERSION (\S+)", (source / "CMakeLists.txt").read_text(encoding="utf-8"))
        if app_version_match is None:
            raise ValueError("Application version is unavailable in actual source")
        app_version = app_version_match.group(1)
        report["application_version"] = app_version
        python = sys.executable
        tools = source / "packaging"
        data_catalog = output / "data.catalog.json"
        if args.reuse_data_catalog:
            copy_reviewed_catalog(args.reuse_data_catalog.absolute(), data_catalog)
        else:
            stage("build-data", [python, tools / "build_data_artifact.py", "--platform", host,
                  "--version", app_version, "--discovery", discovery_path, "--output-archive", output / "geant4-data.zip",
                  "--output-catalog", data_catalog, "--source-page", f"Actual selected local SDK/data discovery receipt {discovery_path}"])
        if load_catalog(data_catalog)["releases"][0].get("geant4_version") != g4_version:
            raise ValueError("Actual data/SDK versions differ")
        data_plan = work / "data-plan.json"
        stage("plan-canonical-data", [python, tools / "install_plan.py", "--output", data_plan, "plan", "--catalog", data_catalog,
              "--profile", "runtime", "--platform", host, "--architecture", "x86_64", "--version", app_version,
              "--prefix", environments / "data-fixture", "--allowed-root", environments])
        stage("install-canonical-data", [python, tools / "install_plan.py", "--output", work / "data-install.json", "execute", "--plan", data_plan])
        package_name = f"G4UniversalSim-{app_version}-{'win64' if host == 'windows' else 'linux-x86_64'}"
        producer = tools / ("build_package.py" if host == "windows" else "build_linux_package.py")
        command = [python, producer, "--build-dir", build, "--data-dir", environments / "data-fixture/data"]
        if host == "windows":
            command += ["--no-installer"]
            if args.reuse_gui:
                command += ["--reuse-gui", args.reuse_gui.absolute()]
            if args.reuse_python_helper:
                command += ["--reuse-python-helper", args.reuse_python_helper.absolute()]
        else:
            if not args.patchelf:
                raise ValueError("An actual patchelf executable is required on the Linux host")
            command += ["--patchelf", args.patchelf, "--freeze-work-root", output / "linux-freeze-work"]
        stage("build-runtime", command)
        runtime_catalog = output / f"{package_name}-runtime.catalog.json"
        stage("uninstall-canonical-data", [python, tools / "install_plan.py", "--output", work / "data-uninstall.json",
              "uninstall", "--prefix", environments / "data-fixture"])
        sdk_catalog = output / "sdk.catalog.json"
        if args.reuse_sdk_catalog:
            copy_reviewed_catalog(args.reuse_sdk_catalog.absolute(), sdk_catalog)
        else:
            sdk_name = package_name + "-development-" + hashlib.sha256(str(work).encode()).hexdigest()[:8]
            sdk_command = [python, tools / "build_sdk_package.py", "--geant4-prefix", prefix, "--platform", host,
                           "--output-name", sdk_name, "--version", app_version, "--remove-staging"]
            if host == "windows":
                qt_match = re.search(r"^Qt5Core_DIR:PATH=(.+)$", cache, re.M)
                if qt_match:
                    sdk_command += ["--qt-prefix", Path(qt_match.group(1).strip()).parents[2]]
            stage("build-sdk", sdk_command)
            sdk_catalog = output / f"{sdk_name}-sdk.catalog.json"
        notices = None
        if (prefix / "conda-meta").is_dir():
            stage("dependency-licenses", [python, tools / "build_license_artifact.py", "--prefix", prefix,
                  "--platform", host, "--output-name", "dependency-notices"])
            notices = output / "dependency-notices.catalog.json"
        release = work / "release" / f"{package_name}-g4-{g4_version}"
        archive = work / (release.name + "-offline.zip")
        runtime_release = load_catalog(runtime_catalog)["releases"][0]
        sdk_release = load_catalog(sdk_catalog)["releases"][0]
        data_release = load_catalog(data_catalog)["releases"][0]
        artifacts = {artifact["sha256"]: artifact for release_record in (runtime_release, sdk_release, data_release)
                     for artifact in release_record["artifacts"]}
        if notices:
            artifacts.update({artifact["sha256"]: artifact for artifact in load_catalog(notices)["releases"][0]["artifacts"]})
        archive_bytes = sum(artifact["size_bytes"] for artifact in artifacts.values())
        payload_bytes = sum(artifact["unpacked_size_bytes"] for artifact in artifacts.values())
        launcher_bytes = sum(artifact["unpacked_size_bytes"] for artifact in runtime_release["artifacts"])
        space_check("outer-release", archive_bytes + launcher_bytes + 256 * 1024 * 1024,
                    basis={"actual_archives": archive_bytes, "actual_launcher_payload": launcher_bytes})
        command = [python, tools / "assemble_distribution.py", "--runtime-catalog", runtime_catalog,
                   "--sdk-catalog", sdk_catalog, "--data-catalog", data_catalog, "--package-root", output / "package" / package_name,
                   "--output", release]
        if args.outer_zip:
            space_check("explicit-outer-zip", archive_bytes * 2 + launcher_bytes * 2 + 256 * 1024 * 1024,
                        basis={"scope": "Explicit opt-in outer ZIP plus directory publication"})
            command += ["--archive-output", archive]
        if notices:
            command += ["--notices-catalog", notices]
        stage("assemble-offline-release", command)
        report["archived_evidence_count"] = len(archive_validation_evidence(
            work, source, reuse_gui=args.reuse_gui, reuse_python_helper=args.reuse_python_helper))
        # Every archive was independently hashed after copying into the release.
        # Only this invocation's intermediate copies are removed; inputs remain.
        for temporary in output.glob("*.zip"):
            remove_owned(temporary)
        for name in ("package", "package-build", "package-python-build", "linux-freeze-work"):
            if (output / name).exists():
                remove_owned(output / name)
        space_check("runtime-sdk-installation", archive_bytes + payload_bytes + args.sdk_build_budget_bytes + 256 * 1024 * 1024,
                    basis={"actual_all_archives": archive_bytes, "actual_full_sdk_payload": payload_bytes,
                           "sdk_compile_budget": args.sdk_build_budget_bytes, "scope": "Serial runtime then SDK, each independently uninstalled"})
        for profile in ("runtime", "sdk"):
            command = [python, tools / "verify_installation_flow.py", "--catalog", release / "install/catalog.json",
                       "--profile", profile, "--version", app_version, "--prefix", environments / profile,
                       "--allowed-root", environments, "--evidence-root", work / (profile + "-evidence")]
            if profile == "sdk":
                command += ["--cmake", args.cmake]
                if args.compiler:
                    command += ["--compiler", args.compiler]
                if args.generator:
                    command += ["--generator", args.generator]
                if args.application_build:
                    command += ["--application-build"]
            stage("verify-" + profile, command)
            flow = json.loads((work / (profile + "-evidence/flow-report.json")).read_text(encoding="utf-8"))
            assert flow["status"] == "verified" and flow["profile"] == profile, flow
            assert all(command["exit_code"] == 0 for command in flow["commands"]), flow
            assert not (environments / profile).exists(), "Verified profile was not independently uninstalled"
            uninstall = json.loads((work / (profile + "-evidence/uninstall-receipt.json")).read_text(encoding="utf-8"))
            assert uninstall["status"] == "uninstalled", uninstall
            if profile == "runtime":
                assert flow["completed_events"] == 5, flow
                assert [command["stage"] for command in flow["commands"]] == ["data-discovery", "simulation", "root-csv", "root-roundtrip", "frozen-gui"]
            else:
                sdk_consumer = json.loads((work / "sdk-evidence/sdk-consumer.json").read_text(encoding="utf-8"))
                sdk_app = json.loads((work / "sdk-evidence/sdk-application.json").read_text(encoding="utf-8"))
                assert sdk_consumer["status"] == sdk_app["status"] == "verified"
                assert [command["stage"] for command in sdk_consumer["commands"]] == ["configure", "build", "run"]
                assert [command["stage"] for command in sdk_app["commands"]] == ["configure", "build", "run"]
                for role, identity in report["host_tools"].items():
                    assert sdk_consumer["host_tools"][role]["sha256"] == identity["sha256"]
                    assert sdk_app["host_tools"][role]["sha256"] == identity["sha256"]
                assert all(command["exit_code"] == 0 for command in sdk_consumer["commands"] + sdk_app["commands"])
        report.update(status="verified", release_directory=str(release), offline_archive=str(archive) if args.outer_zip else None,
                      offline_archive_sha256=_file_hash(archive) if args.outer_zip else None, catalog=str(release / "install/catalog.json"))
    except Exception as exc:
        report.update(status="failed", error={"type": type(exc).__name__, "message": str(exc)})
    finally:
        if "source" in locals() and source.exists():
            try:
                report["archived_evidence_count"] = len(archive_validation_evidence(
                    work, source, reuse_gui=args.reuse_gui, reuse_python_helper=args.reuse_python_helper))
            except Exception as archive_error:
                report["evidence_archive_error"] = str(archive_error)
                report["status"] = "failed"
    checkpoint()
    print(json.dumps({"status": report["status"], "report": str(work / "delivery-report.json"), "error": report.get("error")}, ensure_ascii=True))
    return 0 if report["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
