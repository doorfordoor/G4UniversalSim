"""CI source closure and preservation of this flow's exact freeze/SDK evidence."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))
import ci_delivery
import build_sdk_package
import build_package
from g4usim_gui.core.environment_install import InstallError


def check_sdk_application_fixture(root):
    relative = "scenarios/semiconductor/niel/si_proton.csv"
    original = (ROOT / relative).read_bytes()
    original_sha = hashlib.sha256(original).hexdigest()
    source, geant4, output = (root / name for name in ("sdk-source", "synthetic-geant4", "sdk-output"))
    output.mkdir()
    for path, content in {
        source / "main.cc": b"// synthetic application entry\n",
        source / "CMakeLists.txt": b"# synthetic application CMake input\n",
        source / "packaging/licenses/synthetic.txt": b"synthetic fixture only\n",
        source / relative: original,
        source / "scenarios/semiconductor/niel/not-bundled.csv": b"unrelated scenario file\n",
        geant4 / "lib/cmake/Geant4/Geant4Config.cmake": b"# synthetic SDK marker, not a usable SDK\n",
        geant4 / "lib/cmake/Geant4/Geant4ConfigVersion.cmake": b'set(PACKAGE_VERSION "11.4.0")\n',
        geant4 / "include/Geant4/G4Version.hh": b"#define G4VERSION_NUMBER 1140\n",
    }.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def build():
        # The Windows staging branch uses the private OUT on every test host.
        build_sdk_package.build_sdk(geant4_prefix=geant4, platform="windows", architecture="x86_64",
                                    version="1.1.0", output_name="fixture")

    niel = source / relative
    archive = output / "fixture-sdk.zip"
    catalog = output / "fixture-sdk.catalog.json"
    with patch.object(build_sdk_package, "ROOT", source), patch.object(build_sdk_package, "OUT", output), \
            patch.object(sys, "path", sys.path.copy()):
        build()
        release, = json.loads(catalog.read_bytes())["releases"]
        application = release["sdk"]["application_source"]
        assert application == "sdk/g4usim-source"
        member = f"{application}/{relative}"
        staged = output / "sdk-package/fixture" / member
        with zipfile.ZipFile(archive) as bundle:
            assert [name for name in bundle.namelist() if name.startswith(f"{application}/scenarios/")] == [member]
            assert bundle.read(member) == staged.read_bytes() == original
        entry, = [item for item in release["artifacts"][0]["files"] if item["path"] == member]
        assert entry["sha256"] == original_sha and entry["size_bytes"] == len(original)
        assert release["sdk_build_status"] == "not_verified"
        published = archive.read_bytes(), catalog.read_bytes()

        def rejected(kind):
            try:
                build()
            except FileNotFoundError as exc:
                assert kind == "missing" and Path(exc.filename) == niel
            except InstallError as exc:
                assert kind != "missing" and exc.code == "linked_path"
            else:
                raise AssertionError(f"SDK accepted {kind} NIEL source")
            assert (archive.read_bytes(), catalog.read_bytes()) == published
            assert staged.read_bytes() == original

        niel.unlink()
        rejected("missing")
        link_checks = []
        real_file = niel.with_name("not-bundled.csv")
        try:
            niel.symlink_to(real_file)
        except OSError as exc:
            if os.name != "nt" or exc.winerror != 1314:
                raise
        else:
            rejected("file symlink")
            link_checks.append("file symlink")
            niel.unlink()

        # Also reject a linked ancestor, even when the target stays in this fixture.
        real_directory = niel.parent.with_name("actual-niel")
        niel.parent.rename(real_directory)
        (real_directory / niel.name).write_bytes(original)
        try:
            niel.parent.symlink_to(real_directory, target_is_directory=True)
        except OSError as exc:
            if os.name != "nt" or exc.winerror != 1314:
                raise
            subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", "niel", "actual-niel"],
                cwd=niel.parent.parent,
                check=True, capture_output=True,
            )
            link_checks.append("directory junction")
        else:
            link_checks.append("directory symlink")
        assert niel.read_bytes() == original
        rejected(link_checks[-1])
    print(json.dumps({"synthetic_fixture": True, "archive_member": member, "entry": entry,
                      "archive_sha256": hashlib.sha256(published[0]).hexdigest(),
                      "catalog_sha256": hashlib.sha256(published[1]).hexdigest(),
                      "missing_rejected": True, "links_rejected": link_checks,
                      "previous_publication_preserved": True}))



def check_runtime_build_layout(root):
    """Synthetic cache/layout controls only: dummy bytes are never executed."""
    root = root / "runtime-layout"
    root.mkdir()
    cases = []
    def make(name, generator="Ninja", build_type="Release", configs=None, location="root"):
        folder = root / name;folder.mkdir()
        lines = [f"CMAKE_CACHEFILE_DIR:INTERNAL={folder.as_posix()}"]
        for key, value in (("CMAKE_GENERATOR",generator),("CMAKE_BUILD_TYPE",build_type),("CMAKE_CONFIGURATION_TYPES",configs)):
            if value is not None: lines.append(f"{key}:STRING={value}")
        (folder / "CMakeCache.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
        target = folder if location == "root" else folder / location
        target.mkdir(exist_ok=True)
        for exe in ("G4UniversalSim.exe","mergeHistograms.exe"):
            (target / exe).write_bytes(b"synthetic non-executable fixture; not a real build")
        return folder
    def reject(folder):
        before = {str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        try: build_package.release_binary_directory(folder)
        except SystemExit as exc: assert str(exc), exc
        else: raise AssertionError("Invalid build layout accepted: " + str(folder))
        assert before == {str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        cases.append(folder.name)
    with patch.object(build_package.subprocess,"run",side_effect=AssertionError("synthetic exe executed")):
        single = make("ninja-release")
        assert build_package.release_binary_directory(single) == single
        for generator in ("Visual Studio 18 2026","Ninja Multi-Config"):
            folder=make("multi-"+str(len(cases)),generator,None,"Debug;Release", "Release")
            assert build_package.release_binary_directory(folder) == folder/"Release"
            cases.append(generator)
        for name,kwargs in (
            ("missing-type",{'build_type':None}), ("empty-type",{'build_type':''}),
            ("debug",{'build_type':'Debug'}), ("relwithdebinfo",{'build_type':'RelWithDebInfo'}),
            ("wrong-case",{'build_type':'release'}), ("single-conflict",{'configs':'Debug;Release'}),
            ("missing-generator",{'generator':None}), ("unknown-generator",{'generator':'Unknown'}),
            ("multi-no-types",{'generator':'Visual Studio 18 2026','build_type':None,'location':'Release'}),
            ("multi-no-release",{'generator':'Ninja Multi-Config','build_type':None,'configs':'Debug','location':'Release'}),
            ("multi-debug-conflict",{'generator':'Ninja Multi-Config','build_type':'Debug','configs':'Release','location':'Release'}),
            ("ninja-wrong-layout",{'location':'Release'})):
            reject(make(name,**kwargs))
        for name in ('missing-cache','duplicate','owner-conflict','missing-merge'):
            folder=make(name);cache=folder/'CMakeCache.txt'
            if name=='missing-cache':cache.unlink()
            elif name=='duplicate':cache.write_text(cache.read_text()+'CMAKE_BUILD_TYPE:STRING=Release\n')
            elif name=='owner-conflict':cache.write_text(cache.read_text().replace(folder.as_posix(),root.as_posix()))
            else:(folder/'mergeHistograms.exe').unlink()
            reject(folder)
    # Exercise main routing: selection must precede capability execution or cleanup.
    class StopBeforeProbe(Exception): pass
    for folder,target in ((single,single),):
        with patch.object(sys,'argv',['build_package.py','--build-dir',str(folder),'--skip-gui','--skip-python-helper']), \
                patch.object(build_package,'BUILD',build_package.BUILD), patch.object(build_package,'CACHE',build_package.CACHE), \
                patch.object(build_package,'geant4_prefix',side_effect=StopBeforeProbe):
            try: build_package.main()
            except StopBeforeProbe:
                assert build_package.BUILD==target and build_package.CACHE==folder/'CMakeCache.txt'
            else:raise AssertionError('main did not reach expected pre-probe boundary')
    print('Runtime Release layout controls passed: synthetic layouts only; no compiler/backend executed',len(cases)+1)


def main():
    if not __debug__:
        raise SystemExit("CI delivery tests require assertions; do not run with -O")
    with tempfile.TemporaryDirectory(prefix="g4usim-ci-delivery-") as temp:
        root = Path(temp)
        check_sdk_application_fixture(root)
        check_runtime_build_layout(root)
        origin = root / "origin"
        for relative in ci_delivery.REQUIRED_PRODUCT_PATHS:
            file = origin / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("# actual fixture module " + relative + "\n", encoding="utf-8")
        # The export-template identity declares CMakePresets.json as a root
        # member, so the native snapshot must copy it byte for byte and list it.
        presets_fixture = origin / "CMakePresets.json"
        presets_fixture.write_text(
            '{"version": 3, "configurePresets": [{"name": "fixture"}]}\n',
            encoding="utf-8")
        other = origin / "packaging/freeze_identity.py"
        other.parent.mkdir(parents=True)
        other.write_text("# fixture packaging source\n", encoding="utf-8")
        for relative in ("docs/verification/receipt.json", "test/output/generated.root", "gui/.venv/ignored.py"):
            file = origin / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("generated fixture\n", encoding="utf-8")
        destination = root / "native-snapshot"
        with patch.object(ci_delivery, "ROOT", origin):
            snapshot = ci_delivery.snapshot_sources(destination)
        for relative in ci_delivery.REQUIRED_PRODUCT_PATHS:
            assert (destination / relative).read_bytes() == (origin / relative).read_bytes()
            assert relative in snapshot["files"]
        assert (destination / "packaging/freeze_identity.py").is_file()
        assert (destination / "CMakePresets.json").read_bytes() == presets_fixture.read_bytes()
        assert "CMakePresets.json" in snapshot["files"]
        assert snapshot["files"]["CMakePresets.json"] == ci_delivery._file_hash(presets_fixture)
        assert not (destination / "gui/.venv").exists()
        assert not (destination / "docs/verification").exists()
        assert not (destination / "test/output").exists()
        work = root / "work"
        source = work / "source"
        files = {
            source / "out/package-build/freeze.log": b"actual freeze log\r\n",
            source / "out/package-build/binary-sources.json": b'{"source":"observed"}\n',
            source / "out/package-build/source-identity.json": b'{"source_hashes":{}}\n',
            source / "out/package/application/gui/g4usim-freeze.json": b'{"kind":"gui","files":{}}\n',
            source / "out/package/application/python/g4usim-freeze.json": b'{"kind":"python","files":{}}\n',
        }
        for kind in ("consumer", "application"):
            for name in ("configure.log", "build.log", "run.log", "sdk-probe-receipt.json"):
                files[work / "environments" / ("sdk-" + kind + "-build") / name] = (kind + " " + name + "\n").encode()
        for file, raw in files.items():
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
        archived = ci_delivery.archive_validation_evidence(work, source)
        assert len(archived) == len(files), archived
        for record in archived:
            copied = work / record["path"]
            assert copied.read_bytes() == files[Path(record["source"])], record
            assert ci_delivery._file_hash(copied) == record["sha256"] and record["source_stable_during_copy"]
        assert len(ci_delivery.archive_validation_evidence(work, source)) == len(files)
        changed = source / "out/package-build/freeze.log"
        changed.write_bytes(b"later observed failure log\n")
        newer = ci_delivery.archive_validation_evidence(work, source)
        assert len(newer) == len(files) + 1
        old = next(record for record in archived if record["source"] == str(changed))
        assert (work / old["path"]).read_bytes() == files[changed]
        assert len(json.loads((work / "evidence/index.json").read_text())) == len(newer)
        actual_host = Path(getattr(sys, "_base_executable", sys.executable))
        tools = ci_delivery.describe_host_tools(actual_host)
        assert Path(tools["cmake"]["resolved"]) == actual_host.resolve()
        assert tools["cmake"]["sha256"] == ci_delivery._file_hash(actual_host.resolve())
        missing_tool = root / "absent-cmake"
        try:
            ci_delivery.describe_host_tools(missing_tool)
        except OSError:
            assert not missing_tool.exists()
        else:
            assert False, "Missing selected host tool passed delivery preflight"
    print("I2 CI snapshot closure and evidence archival passed")


if __name__ == "__main__":
    main()
