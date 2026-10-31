"""K1 bundle model/closure/atomicity tests; no implicit backend execution."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from g4usim_gui.core import experiment_bundle as bundle
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_to_json
from g4usim_gui.core.project import G4USimProject, project_from_dict
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import material_document_from_summary
from g4usim_gui.models.package_model import PathSettings, GeometrySettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials

MATERIAL = "[NIST]\nmaterials = G4_Galactic, G4_Si\n"
GEOMETRY = """[world]
size = 100,100,100 mm
material = G4_Galactic
[target]
size = 10,10,10 mm
material = G4_Si
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def refused(call, contains=""):
    try:
        call()
    except (ValueError, OSError) as error:
        assert contains.lower() in str(error).lower(), (contains, str(error))
        return str(error)
    assert False, "Expected refusal"


def fixture(folder, *, generated=False, legacy=False):
    folder.mkdir(parents=True, exist_ok=True)
    materials = write(folder / "materials.ini", MATERIAL)
    geometry = write(folder / "geometry.ini", GEOMETRY)
    write(folder / "nested" / "events.mac", "/run/initialize\n/run/beamOn 3\n")
    macro = write(folder / "run.mac", "/control/execute nested/events.mac\n")
    main = write(folder / "main.ini", f"""[general]
schema_version = 1
[run]
threads = 1
seed = 4242
macro = run.mac
[materials]
file = materials.ini
[geometry]
template = simple_box
config = geometry.ini
[source]
particle = e-
energy = 1 MeV
position = 0,0,-20 mm
direction = 0,0,1
[output]
dir = {folder.as_posix()}/private-output
""")
    p = G4USimProject(projectName="K1 中文迁移", runInputMode="generated" if generated else "external",
        workspaceRoot=str(folder), executable=sys.executable, runsRoot=str(folder / "private-runs"),
        configPath=str(main), macroPath=str(macro), outputDir=str(folder / "old-output"))
    p.pathSettings = PathSettings(executable=sys.executable, workspace_root=str(folder), runs_root=p.runsRoot,
        materials_config=str(materials), geometry_config=str(geometry))
    p.geometrySettings = GeometrySettings(template="simple_box", config_path=str(geometry))
    p.materialEditor = material_document_from_summary(parse_materials(materials))
    p.geometryEditor = geometry_document_from_summary(parse_geometry(geometry, "simple_box"), "simple_box")
    p.runSettings.beam_on = 3
    if legacy:
        p = project_from_dict({"version": 1, "projectName": "旧项目", "workspaceRoot": str(folder),
            "configPath": str(main), "macroPath": str(macro)})
    return WorkspaceSnapshot(p)


def change_manifest(folder, mutate):
    file = folder / "manifest.json"
    data = json.loads(file.read_bytes())
    mutate(data)
    file.write_bytes(bundle._json(data))


def test_safe_environment_history(root):
    from g4usim_gui.core.experiment_identity import canonical_digest, safe_environment

    snapshot = fixture(root / "source")
    private_data = root / "private-datasets"
    probe = {
        "schema": "g4usim_environment_probe_v1", "version": 1, "status": "available",
        "available": True, "geant4_version": "11.3.2", "binary_sha256": "a" * 64,
        "source_fingerprint": "b" * 64, "platform": "Windows",
        "identity": {"sha256": "a" * 64, "stable": True, "path": sys.executable},
        "architecture": {"format": "PE", "machine": "AMD64", "bits": 64},
        "build": {"compiler_id": "MSVC", "compiler_version": "19.50", "geant4_version_number": 1132},
        "capabilities": {"status": "available", "data": {
            "schema": "g4usim_capabilities_v1", "version": 1, "geant4_version": "11.3.2",
            "geant4_version_number": 1132, "source_fingerprint": "b" * 64,
            "root": False, "gdml": True, "multithreaded": True,
            "build_git_commit": "c" * 40, "build_git_source_state": "dirty",
            "build_compiler_id": "MSVC", "build_compiler_version": "19.50",
            "build_configuration": "Release"}},
        "data": {"status": "available", "required_complete": True,
            "probe": {"working_directory": str(private_data)}, "report": {"datasets": [
                {"env": "G4NEUTRONHPDATA", "folder": "G4NDL4.7.1", "required": True,
                 "found": True, "path": str(private_data / "G4NDL4.7.1")},
                {"env": "G4LEDATA", "folder": "G4EMLOW8.6.1", "required": True,
                 "found": True, "path": "G4EMLOW8.6.1"},
                {"env": "G4PARTICLEHPDATA", "folder": "G4TENDL1.4", "required": False,
                 "found": False, "path": ""}]}},
        "env": {"UNRELATED_VARIABLE": "private-value-not-a-fact"},
    }
    facts = safe_environment(probe)
    assert facts["binary"] == {"sha256": "a" * 64, "stable": True}
    assert facts["build"] == probe["build"]
    assert facts["capabilities"]["data"]["git_commit"] == "c" * 40
    assert facts["data"]["datasets"][0]["selected_path_sha256"] == canonical_digest(str((private_data / "G4NDL4.7.1").resolve()))
    assert facts["data"]["datasets"][1]["selected_path_sha256"] == canonical_digest(str((private_data / "G4EMLOW8.6.1").resolve()))
    assert facts["data"]["datasets"][2]["selected_path_sha256"] is None
    record = {"status": "passed", "revision": 19, "session_id": "historical-session",
              "identity": {"environment": facts, "execution_fingerprint": canonical_digest(facts)},
              "environment_facts": facts}
    before = copy.deepcopy(record)
    target = root / "exported"
    exported = bundle.export_bundle(snapshot, target, validation_records=[record])
    assert record == before
    assert exported["validation_records"][0]["record"] == record
    relocated = root / "relocated"
    target.rename(relocated)
    loaded = bundle.load_bundle(relocated)
    history = loaded.transient["bundle"]["validation_records"]
    assert history[0]["record"] == before
    assert history[0]["stale"] is True
    assert loaded.transient["bundle"]["replay_verified"] is False
    assert loaded.project.executable == ""
    text = (relocated / "validation_records.json").read_text(encoding="utf-8")
    assert str(private_data) not in text and "private-value-not-a-fact" not in text
    assert sys.executable not in text
    # Unknown fields at every level are removed, not admitted by a broad env
    # exception. The dataset 'env' is only a scalar variable identifier.
    injected = copy.deepcopy(facts)
    for node in (injected, injected["binary"], injected["build"], injected["architecture"],
                 injected["capabilities"], injected["capabilities"]["data"], injected["data"],
                 *injected["data"]["datasets"]):
        node["private_path"] = str(private_data)
        node["environment_variables"] = {"UNRELATED_VARIABLE": "private-value-not-a-fact"}
    injected["env"] = {"UNRELATED_VARIABLE": "private-value-not-a-fact"}
    clean = bundle.export_bundle(snapshot, root / "projected", validation_records=[{"environment": injected}])
    assert clean["validation_records"][0]["record"]["environment"] == facts
    assert bundle.load_bundle(root / "projected").transient["bundle"]["validation_records"][0]["record"]["environment"] == facts
    unknown = safe_environment({})
    default = bundle.export_bundle(snapshot, root / "unknown", validation_records=[{"environment": unknown}])
    assert default["validation_records"][0]["record"]["environment"] == unknown
    for name, mutate, reason in (
        ("env-dict", lambda f: f["data"]["datasets"][0].update(env={"PATH": "private"}), "scalar"),
        ("env-value", lambda f: f["data"]["datasets"][0].update(env="G4LEDATA=private"), "identifier"),
        ("hash-path", lambda f: f["data"]["datasets"][0].update(selected_path_sha256=str(private_data)), "path"),
        ("build-path", lambda f: f["build"].update(compiler_id=str(private_data)), "path"),
        ("build-secret", lambda f: f["build"].update(compiler_id="token=private-test-sentinel"), "credential"),
    ):
        bad = copy.deepcopy(facts)
        mutate(bad)
        refused(lambda: bundle.export_bundle(snapshot, root / name, validation_records=[{"environment": bad}]), reason)
        assert not (root / name).exists()


def test_build_version_text(root):
    snapshot = fixture(root / "source")
    versions = ("$Name: geant4-11-03-patch-02 [MT]$", "$Name: geant4-11-04-patch-03$",
                "$Name: geant4-11-04 [MT]$")
    records = [{"build": {"geant4_version": version}} for version in versions]
    bundle.export_bundle(snapshot, root / "bundle", validation_records=records)
    loaded = bundle.load_bundle(root / "bundle")
    history = loaded.transient["bundle"]["validation_records"]
    assert [item["record"]["build"]["geant4_version"] for item in history] == list(versions)
    assert all(item["stale"] for item in history)
    for value in ("$Name", "${PRIVATE_DATA}", "$Name: geant4-11-03-patch-02 [MT]$ $PRIVATE_DATA",
                  "$Name: geant4-private [MT]$"):
        refused(lambda: bundle._privacy({"build": {"geant4_version": value}}, []))
    refused(lambda: bundle._privacy({"source": versions[0]}, []))


def test_reference_source_urls(root):
    snapshot = fixture(root / "source")
    official = "https://geant4.web.cern.ch/documentation/pipelines/master/prm_html/PhysicsReferenceManual/index.html"
    reference = write(root / "source" / "reference.csv", "energy_MeV,dose_Gy\n1,2\n")
    records = [{"reference": {"source": official, "path": str(reference)}},
               {"reference": "http://geant4.web.cern.ch/docs/?version=11.3#reference"}]
    exported = bundle.export_bundle(snapshot, root / "bundle", validation_records=records)
    history = bundle.load_bundle(root / "bundle").transient["bundle"]["validation_records"]
    assert exported["validation_records"][0]["record"]["reference"]["source"] == official
    assert history[0]["record"]["reference"]["source"] == official
    assert history[0]["record"]["reference"]["sha256"] == hashlib.sha256(reference.read_bytes()).hexdigest()
    assert history[1]["record"]["reference"] == records[1]["reference"]
    assert all(row["stale"] for row in history)
    assert official in (root / "bundle" / "validation_records.json").read_text(encoding="utf-8")
    for index, value in enumerate((
        "C:/private/reference.csv", r"C:\private\reference.csv",
        official + " C:/private/reference.csv", official + r" C:\private\reference.csv",
        official + " /private/reference.csv", official + r" \\private\share\reference.csv",
        "https://geant4.web.cern.ch/C:/private/reference.csv",
        r"https://geant4.web.cern.ch/\private\reference.csv",
        "https:///private/reference.csv", "https://:invalid/private/reference.csv",
        official + "?token=private-test-sentinel",
        "https://fixture-user:fixture-pass@geant4.web.cern.ch/reference",
    )):
        target = root / f"refused-{index}"
        refused(lambda: bundle.export_bundle(snapshot, target, validation_records=[{"reference": {"source": value}}]))
        assert not target.exists()


def test_move_and_history(root):
    source = root / "原始工作区"
    snapshot = fixture(source, legacy=True)
    before = snapshot_to_json(snapshot)
    reference = write(source / "reference.csv", "energy_MeV,dose_Gy\n1,2\n")
    record = {"level": "physical_comparison", "status": "pass", "revision": 8,
              "environment": {"os": "Windows", "env": {"SECRET": "private"}},
              "reference": {"path": str(reference)}, "tolerance": 0.01,
              "unit": "Gy", "executable": sys.executable}
    write(source / "not-referenced-private.txt", "do-not-copy-this-file\n")
    exported = bundle.export_bundle(snapshot, root / "bundle", validation_records=[record])
    assert snapshot_to_json(snapshot) == before
    assert exported["replay_verified"] is False
    assert exported["validation_records"][0]["stale"] is True
    assert exported["validation_records"][0]["record"]["revision"] == 8
    assert exported["validation_records"][0]["record"]["environment"] == {"os": "Windows"}
    rewritten = next(row for row in exported["manifest"]["members"] if row["role"] == "main")
    assert rewritten["source_sha256"] != rewritten["sha256"]
    assert not any("not-referenced" in row["path"] for row in exported["manifest"]["members"])
    bound = exported["validation_records"][0]["record"]["reference"]
    assert bound["sha256"] == hashlib.sha256(reference.read_bytes()).hexdigest()
    assert record["reference"]["path"] == str(reference)
    payload = (root / "bundle" / "workspace.json").read_text(encoding="utf-8")
    history = (root / "bundle" / "validation_records.json").read_text(encoding="utf-8")
    assert str(source) not in payload + history
    assert sys.executable not in payload + history
    assert "private\"" not in history
    moved = root / "干净目录" / "搬移后的包"
    moved.parent.mkdir()
    shutil.move(root / "bundle", moved)
    shutil.rmtree(source)
    loaded = bundle.load_bundle(moved)
    assert loaded.project.version == 7
    assert loaded.project.executable == ""
    assert loaded.project.pathSettings.executable == ""
    assert loaded.project.outputDir == ""
    assert loaded.project.workspaceRoot == str(moved)
    assert Path(loaded.project.configPath).is_file()
    assert loaded.project.runInputMode == "external"
    assert loaded.transient["bundle"]["validation_records"][0]["stale"] is True
    assert bundle.load_bundle(moved, executable=sys.executable).project.executable == sys.executable
    replay = (moved / "replay.py").read_text(encoding="utf-8")
    assert "g4usim_gui.experiment_cli" in replay
    assert "--bundle" in replay
    assert "G4UniversalSim.exe" not in replay
    assert not (moved / "output").exists()
    assert all("source_path" not in item for item in exported["manifest"]["members"])


def test_resource_kinds_and_identity(root):
    source = root / "kinds"
    snapshot = fixture(source)
    geometry = source / "geometry.ini"
    write(source / "solid.stl", "solid mesh\nendsolid mesh\n")
    write(source / "copies.csv", "x_mm,y_mm,z_mm\n0,0,0\n")
    write(geometry, """[world]
size = 100,100,100 mm
material = G4_Galactic
[volume.test]
parent = world
shape = tessellated
material = G4_Si
file = solid.stl
placement = parameterised
copies_file = copies.csv
""")
    main = source / "main.ini"
    text = main.read_text(encoding="utf-8").replace("template = simple_box", "template = hierarchical")
    text += "\n[scoring.displacement]\nproton = niel.csv\n[source.named]\nspectrum_file = spectrum.csv\n[field]\nmagnetic_map = field.csv\n"
    write(main, text)
    for name in ("niel.csv", "spectrum.csv", "phase-a.csv", "phase-b.csv"):
        write(source / name, "x,y\n1,2\n")
    external_table = write(root / "external-niel.csv", "x,y\n1,5\n")
    text = text.replace("proton = niel.csv", f"proton = {external_table.as_posix()}")
    write(main, text)
    write(source / "field.csv", "x_mm,y_mm,z_mm,Bx_T,By_T,Bz_T\n0,0,0,0,0,1\n")
    # Avoid stale captured preview resources: external model has an intentional
    # empty document and uses backend files, never the GUI editor writer.
    snapshot.project.geometryEditor.source_path = ""
    snapshot.project.geometryEditor.raw_source_text = ""
    snapshot.project.geometrySettings.template = "hierarchical"
    collected = bundle.collect_bundle_resources(snapshot)
    assert {"stl", "copies", "niel", "spectrum", "field_map"} <= {r["role"] for r in collected["resources"]}
    assert any(r["source_sha256"] == bundle.digest(external_table.read_bytes()) for r in collected["resources"] if r["role"] == "niel")
    before = [r["sha256"] for r in collected["resources"]]
    original_stat = (source / "spectrum.csv").stat()
    write(source / "spectrum.csv", "x,y\n1,9\n")
    os.utime(source / "spectrum.csv", ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    after = bundle.collect_bundle_resources(snapshot)
    assert before != [r["sha256"] for r in after["resources"]]
    assert (source / "spectrum.csv").stat().st_size == original_stat.st_size
    write(main, text.replace("particle = e-", "phase_space_file = phase-a.csv,phase-b.csv\nparticle = e-"))
    phases = bundle.collect_bundle_resources(snapshot)
    assert len([r for r in phases["resources"] if r["role"] == "phase_space"]) == 2
    # An absolute nested macro and cwd-relative random/GPS input are distinct.
    write(source / "state.rndm", "synthetic state bytes; transport test only\n")
    write(source / "run.mac", f"/control/execute '{(source / 'nested/events.mac').as_posix()}'\n/random/resetEngineFrom state.rndm\n/gps/hist/file spectrum.csv\n")
    result = bundle.export_bundle(snapshot, root / "kind-bundle")
    assert "random_state" in {r["role"] for r in result["manifest"]["members"]}
    assert all(str(source) not in (root / "kind-bundle" / r["path"]).read_text(encoding="utf-8")
               for r in result["manifest"]["members"])
    # Same basename, different actual bytes stays two distinct resources.
    write(source / "a" / "same.csv", "a\n")
    write(source / "b" / "same.csv", "b\n")
    write(main, text + "\n[source.second]\nspectrum_file = a/same.csv\n[source.third]\nspectrum_file = b/same.csv\n")
    same = [r for r in bundle.collect_bundle_resources(snapshot)["resources"] if r["path"].endswith("same.csv")]
    assert len(same) == 2
    assert same[0]["sha256"] != same[1]["sha256"]
    assert same[0]["path"] != same[1]["path"]


def test_generated(root):
    snapshot = fixture(root / "generated-source", generated=True)
    before = snapshot_to_json(snapshot)
    exported = bundle.export_bundle(snapshot, root / "generated-bundle")
    assert snapshot_to_json(snapshot) == before
    assert exported["replay_inputs"]["config"]
    assert exported["replay_inputs"]["macro"]
    assert not (root / "generated-source" / "private-runs").exists()
    assert not any("project_snapshot" in r["path"] for r in exported["manifest"]["members"])
    moved = root / "generated-moved"
    shutil.move(root / "generated-bundle", moved)
    shutil.rmtree(root / "generated-source")
    loaded = bundle.load_bundle(moved, executable=sys.executable)
    assert loaded.project.runInputMode == "generated"
    assert loaded.project.configPath == ""
    assert loaded.project.macroPath == ""
    # Basic generated/editor inputs can be re-exported using the existing writer.
    second = bundle.export_bundle(loaded, root / "generated-again")
    assert second["replay_verified"] is False


def test_refusals(root):
    snapshot = fixture(root / "refusal-source")
    source = Path(snapshot.project.workspaceRoot)
    target = root / "refused-bundle"
    macro = source / "run.mac"
    initial = macro.read_text(encoding="utf-8")
    for bad in ("/control/execute missing.mac", "/control/execute run.mac",
                "/control/loop run.mac n 1 2", "/custom/load mystery.csv",
                "/gps/pos/type {dynamic}", "/AIHL/output/setDir private/output"):
        write(macro, bad + "\n")
        refused(lambda: bundle.export_bundle(snapshot, target))
        assert not target.exists()
        assert not list(root.glob(".refused-bundle.k1-*"))
    write(macro, initial)
    main = source / "main.ini"
    original = main.read_text(encoding="utf-8")
    for bad in (original + "\n[unknown]\nfile = mystery.csv\n",
                original.replace("schema_version = 1", "schema_version = 99"),
                original + "\n[run]\nmacro = other.mac\n"):
        write(main, bad)
        refused(lambda: bundle.collect_bundle_resources(snapshot))
    write(main, original)
    for private in ("C:/Users/private/hidden.csv", "/home/private/hidden.csv", "%PRIVATE_ENV%",
                    "$env:PRIVATE", "api_key=credential-material", "token=synthetic-private",
                    "https://fixture-user:fixture-pass@example.invalid/data"):
        candidate = copy.deepcopy(snapshot)
        candidate.state["drafts"]["config.opaque"] = private
        refused(lambda: bundle.export_bundle(candidate, target))
        candidate = copy.deepcopy(snapshot)
        candidate.project.geometryEditor.raw_source_text += "\n# " + private + "\n"
        refused(lambda: bundle.export_bundle(candidate, target))
        refused(lambda: bundle.export_bundle(snapshot, target, validation_records=[{"note": private}]))
    source_file = str(source / "materials.ini")
    refused(lambda: bundle.export_bundle(snapshot, target, resource_policy={source_file: {"distribution": "restricted"}}), "restricted")
    allowed = bundle.export_bundle(snapshot, root / "restricted-explicit", resource_policy={source_file: {"distribution": "restricted", "allow_redistribution": True}})
    assert any(r.get("distribution") == "restricted" for r in allowed["manifest"]["members"])
    assert any(r.get("distribution") == "unknown" for r in allowed["manifest"]["members"])
    refused(lambda: bundle.export_bundle(snapshot, target, resource_policy={"unused": {}}), "unused")
    reference = write(source / "reference.csv", "x,y\n1,2\n")
    refused(lambda: bundle.export_bundle(snapshot, target, validation_records=[{"reference": {"path": str(reference), "sha256": "0" * 64}}]), "hash changed")
    # Known absolute raw draft paths receive logical names instead of leaking.
    candidate = copy.deepcopy(snapshot)
    candidate.state["drafts"]["config.materials_config"] = str(source / "materials.ini")
    result = bundle.collect_bundle_resources(candidate)
    assert result["snapshot"]["state"]["drafts"]["config.materials_config"].startswith("resources/")
    write(reference, "MZdisguised executable fixture")
    refused(lambda: bundle.collect_bundle_resources(snapshot, validation_records=[{"reference_file": str(reference)}]), "executable binary")
    if os.name != "nt":
        link = source / "linked-folder"
        link.symlink_to(source / "nested", target_is_directory=True)
        refused(lambda: bundle._no_links(link / ".." / "materials.ini"), "linked path")


def test_atomic_and_tamper(root):
    snapshot = fixture(root / "atomic-source")
    target = root / "atomic-target"
    target.mkdir()
    sentinel = write(target / "sentinel", "keep\n")
    refused(lambda: bundle.export_bundle(snapshot, target), "exists")
    assert sentinel.read_bytes() == b"keep\n"
    target = root / "publish-failed"
    with patch.object(bundle, "_write", side_effect=OSError("injected write failure")):
        refused(lambda: bundle.export_bundle(snapshot, target), "write failure")
    assert not target.exists()
    assert not list(root.glob(".publish-failed.k1-*"))
    with patch.object(bundle, "_publish_directory", side_effect=OSError("injected publication failure")):
        refused(lambda: bundle.export_bundle(snapshot, target), "injected")
    assert not target.exists()
    assert not list(root.glob(".publish-failed.k1-*"))
    # A racing creator wins, including an otherwise empty destination directory.
    original_publish = bundle._publish_directory
    def competing(source, destination):
        destination.mkdir()
        original_publish(source, destination)
    with patch.object(bundle, "_publish_directory", side_effect=competing):
        refused(lambda: bundle.export_bundle(snapshot, target))
    assert target.is_dir()
    assert not list(target.iterdir())
    target.rmdir()
    bundle.export_bundle(snapshot, target)
    entry = json.loads((target / "manifest.json").read_bytes())["members"][0]
    file = target / entry["path"]
    initial = file.read_bytes()
    file.write_bytes(initial + b"changed")
    refused(lambda: bundle.load_bundle(target), "mismatch")
    file.write_bytes(initial)
    write(target / "unregistered", "unexpected")
    refused(lambda: bundle.inspect_bundle(target), "unlisted")
    (target / "unregistered").unlink()
    original_manifest = (target / "manifest.json").read_bytes()
    change_manifest(target, lambda m: m["members"].append(dict(m["members"][0])))
    refused(lambda: bundle.inspect_bundle(target), "collid")
    (target / "manifest.json").write_bytes(original_manifest)
    change_manifest(target, lambda m: m["members"][0].update(path="../escape.ini"))
    refused(lambda: bundle.inspect_bundle(target), "escape")
    (target / "manifest.json").write_bytes(original_manifest)
    change_manifest(target, lambda m: m.update(version=999))
    refused(lambda: bundle.inspect_bundle(target), "version")
    (target / "manifest.json").write_bytes(original_manifest)
    # Even an attacker who recomputes a member hash cannot turn a path escape
    # into a closed supported bundle. This is integrity, not authentication.
    manifest = json.loads(original_manifest)
    main_entry = next(e for e in manifest["members"] if e["role"] == "main")
    main = target / main_entry["path"]
    main_initial = main.read_bytes()
    altered = main_initial.replace(b"file = resources/", b"file = ../../escape/resources/")
    main.write_bytes(altered)
    change_manifest(target, lambda m: next(e for e in m["members"] if e["path"] == main_entry["path"]).update(sha256=bundle.digest(altered), bytes=len(altered)))
    refused(lambda: bundle.inspect_bundle(target))
    main.write_bytes(main_initial)
    (target / "manifest.json").write_bytes(original_manifest)
    # Hard links are reproducible on Windows without symlink privileges.
    linked = target / "linked"
    os.link(file, linked)
    refused(lambda: bundle.inspect_bundle(target), "unlinked")
    linked.unlink()
    assert bundle.inspect_bundle(target)["replay_verified"] is False


def test_gdml(root):
    snapshot = fixture(root / "gdml-source")
    source = Path(snapshot.project.workspaceRoot)
    write(source / "main.ini", "[geometry]\ntemplate = gdml\nconfig = gdml.ini\n[run]\nmacro = run.mac\n")
    write(source / "gdml.ini", "[gdml]\nfile = self.gdml\n")
    gdml = write(source / "self.gdml", "<gdml><materials/><solids/><structure/><setup name='S' version='1'/></gdml>\n")
    result = bundle.collect_bundle_resources(snapshot)
    assert "gdml" in {r["role"] for r in result["resources"]}
    for bad in ("<!DOCTYPE gdml SYSTEM 'private.dtd'><gdml/>",
                "<gdml><file name='module.gdml'/></gdml>",
                "<gdml xmlns:xi='http://www.w3.org/2001/XInclude'><xi:include href='other'/></gdml>"):
        write(gdml, bad)
        refused(lambda: bundle.collect_bundle_resources(snapshot), "gdml")


def test_independent_review_regressions(root):
    """Plato's original five findings, plus parsed blocker/macro state controls."""
    snapshot = fixture(root / "source")
    target = root / "bundle"
    bundle.export_bundle(snapshot, target, validation_records=[{"level": "physical_comparison", "status": "failed"}])
    raw_read = bundle._read
    workspace = target / "workspace.json"
    original_workspace = workspace.read_bytes()
    expected_seed = snapshot.project.runSettings.seed
    changed = False
    reads = 0
    def workspace_race(path):
        nonlocal changed, reads
        raw = raw_read(path)
        if Path(path) == workspace:
            reads += 1
            if not changed:
                changed = True
                data = json.loads(raw)
                data["project"]["runSettings"]["seed"] = 991337
                workspace.write_bytes(bundle._json(data))
        return raw
    with patch.object(bundle, "_read", side_effect=workspace_race):
        loaded = bundle.load_bundle(target)
    assert loaded.project.runSettings.seed == expected_seed
    assert loaded.project.runSettings.seed != 991337
    assert reads == 1
    refused(lambda: bundle.inspect_bundle(target), "mismatch")
    workspace.write_bytes(original_workspace)
    history = target / "validation_records.json"
    original_history = history.read_bytes()
    changed = False
    reads = 0
    def history_race(path):
        nonlocal changed, reads
        raw = raw_read(path)
        if Path(path) == history:
            reads += 1
            if not changed:
                changed = True
                data = json.loads(raw)
                data["records"][0]["status"] = "pass"
                history.write_bytes(bundle._json(data))
        return raw
    with patch.object(bundle, "_read", side_effect=history_race):
        inspected = bundle.inspect_bundle(target)
    assert inspected["validation_records"][0]["record"]["status"] == "failed"
    assert inspected["validation_records"][0]["stale"] is True
    assert reads == 1
    refused(lambda: bundle.inspect_bundle(target), "mismatch")
    history.write_bytes(original_history)
    original_manifest = (target / "manifest.json").read_bytes()
    binary = b"MZK1_FAKE_UNREFERENCED_BINARY"
    (target / "backend.exe").write_bytes(binary)
    change_manifest(target, lambda m: m["members"].append({"path": "backend.exe", "role": "backend",
        "bytes": len(binary), "sha256": bundle.digest(binary)}))
    refused(lambda: bundle.inspect_bundle(target), "whitelist")
    (target / "backend.exe").unlink()
    (target / "manifest.json").write_bytes(original_manifest)
    macro = Path(snapshot.project.macroPath)
    original_macro = macro.read_bytes()
    for comment in ("# token=K1_FAKE_SECRET_ONLY_47812\n", "/run/verbose 1 # token=K1_FAKE_SECRET_ONLY_47812\n"):
        write(macro, comment + original_macro.decode("utf-8"))
        refused(lambda: bundle.export_bundle(snapshot, root / "secret-refused"), "credential")
        assert not (root / "secret-refused").exists()
    macro.write_bytes(original_macro)
    for record in ({"access_token": "K1_FAKE_SECRET_ONLY_47812"}, {"parameters": {"apiKey": "FAKE"}}):
        refused(lambda: bundle.export_bundle(snapshot, root / "secret-refused", validation_records=[record]), "credential")
    # project_to_dict intentionally shares preview/volumes containers. Traversal
    # must relocate copies_file exactly once and retain source-copy blockers.
    geometry = Path(snapshot.project.pathSettings.geometry_config)
    hierarchical = """[world]
shape = box
size = 100,100,100 mm
material = G4_Galactic
[volume.det]
parent = world
shape = box
size = 3,3,3 mm
material = G4_Si
placement = parameterised
copies_file = copies.csv
"""
    write(geometry, hierarchical)
    copies = write(geometry.parent / "copies.csv", "x_mm,y_mm,z_mm\n0,0,0\n0,0,10\n")
    snapshot.project.geometrySettings.template = "hierarchical"
    snapshot.project.geometryEditor = geometry_document_from_summary(parse_geometry(geometry, "hierarchical"), "hierarchical")
    snapshot.project.geometryEditor.source_copy_mode = True
    main = Path(snapshot.project.configPath)
    write(main, main.read_text(encoding="utf-8").replace("template = simple_box", "template = hierarchical"))
    collected = bundle.collect_bundle_resources(snapshot)
    assert any(row["role"] == "copies" for row in collected["resources"])
    assert collected["snapshot"]["project"]["geometryEditor"]["round_trip_blockers"]
    assert all(str(geometry) not in msg for msg in collected["snapshot"]["project"]["geometryEditor"]["round_trip_blockers"])
    exported = bundle.export_bundle(snapshot, root / "copies-bundle")
    restored = bundle.load_bundle(root / "copies-bundle")
    assert restored.project.geometryEditor.source_copy_mode is True
    assert restored.project.geometryEditor.round_trip_blockers
    assert sum(row.get("role") == "copies" for row in exported["manifest"]["members"]) == 1
    assert copies.is_file()
    # Template changes in a nested macro affect later parent loadConfig commands.
    write(geometry.parent / "select.mac", "/AIHL/geometry/setTemplate hierarchical\n")
    write(macro, "/control/execute select.mac\n/AIHL/geometry/loadConfig geometry.ini\n/run/initialize\n/run/beamOn 1\n")
    assert bundle.collect_bundle_resources(snapshot)["resources"]


def backend_check(root, executable):
    snapshot = fixture(root / "backend-source")
    result = bundle.export_bundle(snapshot, root / "backend-bundle")
    moved = root / "backend-clean"
    shutil.move(root / "backend-bundle", moved)
    shutil.rmtree(root / "backend-source")
    loaded = bundle.load_bundle(moved, executable=str(executable))
    inputs = result["replay_inputs"]
    request_id = uuid.uuid4().hex
    command = [str(executable), "--config", str(moved / inputs["config"]), "--macro", str(moved / inputs["macro"]),
               "--output", str(root / "backend-output"), "--run-name", request_id]
    process = subprocess.run(command, cwd=moved, capture_output=True, timeout=120)
    (root / "backend.log").write_bytes(process.stdout + process.stderr)
    assert process.returncode == 0, process.stdout[-3000:] + process.stderr[-3000:]
    summary = (root / "backend-output" / "run_summary.txt").read_text(encoding="utf-8")
    assert "status=completed" in summary or "status = completed" in summary
    values = dict(line.split("=", 1) for line in summary.splitlines() if "=" in line)
    values = {key.strip(): value.strip() for key, value in values.items()}
    assert values.get("actual_run_name", values.get("effective_run_name", values.get("run_name"))) == request_id
    assert values["run_0_completed_events"] == values["run_0_planned_events"] == "3"
    metadata = json.loads((root / "backend-output" / "run_metadata.json").read_bytes())
    observed = metadata.get("provenance", {}).get("inputs")
    if observed is not None:
        from g4usim_gui.output.provenance import output_evidence
        evidence = output_evidence(root / "backend-output", fresh=True)
        assert evidence.status == "verified"
        planned = {str((moved / row["path"]).resolve()).casefold(): row
                   for row in result["manifest"]["members"] if row["path"].startswith("resources/")}
        for sequence, row in enumerate(observed, 1):
            assert row["sequence"] == sequence
            assert row["status"] == "recorded", row
            observed_path = Path(row["path"])
            if not observed_path.is_absolute():
                observed_path = moved / observed_path
            expected = planned[str(observed_path.resolve()).casefold()]
            assert row["sha256"] == expected["sha256"], row
            assert row["size_bytes"] == expected["bytes"], row
        assert observed
        actual_input_status = "f1_sequence_matches_planned_bundle_bytes"
    else:
        actual_input_status = "unknown_no_F1_input_sequence"
    assert loaded.transient["bundle"]["replay_verified"] is False
    return {"backend_exit_code": process.returncode, "backend_sha256": bundle.digest(executable.read_bytes()),
            "log_sha256": bundle.digest((root / "backend.log").read_bytes()), "request_id": request_id,
            "actual_input_status": actual_input_status, "unified_cli_replay_verified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", action="store_true", help="Never invoke a backend, including G4USIM_EXE")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--executable", default=os.environ.get("G4USIM_EXE", ""))
    args = parser.parse_args()
    if args.evidence_root is None and os.environ.get("G4USIM_TEST_EVIDENCE_DIR"):
        parent = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"]).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        args.evidence_root = parent / ("k1-bundle-" + uuid.uuid4().hex[:10])
    if not args.component and not args.executable:
        parser.error("real backend mode requires --executable or G4USIM_EXE; use --component for component tests")
    if args.evidence_root:
        args.evidence_root.mkdir(parents=True, exist_ok=False)
        root = args.evidence_root.resolve()
        temporary = None
    else:
        temporary = tempfile.TemporaryDirectory(prefix="k1-bundle-")
        root = Path(temporary.name)
    cases = []
    try:
        for case in (test_safe_environment_history, test_build_version_text, test_reference_source_urls, test_move_and_history, test_resource_kinds_and_identity, test_generated,
                     test_refusals, test_atomic_and_tamper, test_gdml, test_independent_review_regressions):
            folder = root / case.__name__
            folder.mkdir()
            case(folder)
            cases.append(case.__name__)
            print("PASS", case.__name__, flush=True)
        backend = {"unified_cli_replay_verified": False, "backend_execution": "not_requested"}
        if not args.component:
            folder = root / "backend"
            folder.mkdir()
            backend = backend_check(folder, Path(args.executable).resolve(strict=True))
            print("PASS direct_backend_move (unified CLI replay remains unverified)", flush=True)
        (root / "result.json").write_bytes(bundle._json({"cases": cases, "backend": backend, "all_passed": True}))
        print(f"K1 bundle: {len(cases)} case groups passed; evidence={root}")
    finally:
        if temporary:
            temporary.cleanup()


if __name__ == "__main__":
    main()
