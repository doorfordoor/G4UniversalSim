"""E6 migration copies: information preservation and fail-closed publication."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.config_migration import digest, load_json_strict, publish_migration
from g4usim_gui.core.geometry_migration import plan_geometry_migration
from g4usim_gui.core.project import G4USimProject, SCHEMA_VERSION, load_project, project_from_dict, project_to_dict, save_project
from g4usim_gui.core.project_migration import plan_project_migration
from g4usim_gui.editors.geometry_editor_model import (geometry_document_from_summary, validate_geometry_document,
                                                     geometry_document_from_dict, geometry_document_to_snapshot)
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel


HIERARCHICAL = """# preserve this comment
[world]
shape = box
size = 10 cm, 10 cm, 10 cm
material = G4_AIR
[volume.Target]
parent = world
shape = box
size = 1 cm, 1 cm, 1 cm
material = G4_Si
"""


def rejected(call, fragment=""):
    try:
        call()
    except (ValueError, OSError, TypeError) as error:
        assert fragment in str(error), str(error)
    else:
        assert False, "Migration unexpectedly accepted invalid or ambiguous input"


def project_contract(work):
    source = work / "old.json"
    for version in (None, *range(1, SCHEMA_VERSION + 1)):
        original = {"projectName": "中文项目", "macroPath": "old.mac",
                    "geometryEditor": {"mode": "hierarchical", "schemaVersion": 1,
                                       "preview": {"volumes": [], "boolean_ops": []}}}
        if version is not None:
            original["version"] = version
        source.write_text(json.dumps(original), encoding="utf-8")
        before = source.read_bytes()
        plan = plan_project_migration(source)
        assert plan.input_version == version
        assert plan.output_version == SCHEMA_VERSION
        target = work / f"project-{version}.json"
        result = publish_migration(plan, target)
        assert result.sha256 == digest(target.read_bytes())
        loaded = load_project(target)
        assert loaded.version == SCHEMA_VERSION and loaded.projectName == "中文项目"
        assert loaded.runInputMode == "external" and loaded.macroPath == "old.mac"
        assert loaded.geometryEditor.schema_version == 1
        assert source.read_bytes() == before
        saved = work / "normal-save.json"
        save_project(loaded, saved)
        assert project_to_dict(load_project(saved)) == project_to_dict(loaded)
    for invalid in (
        {"version": SCHEMA_VERSION + 1}, {"version": True}, {"unknown": 1},
        {"geometryEditor": {"preview": {"unknown": []}}},
        {"geometryEditor": {"sourcePath": "a", "source_path": "b"}},
        {"geometryEditor": {"preview": {"volumes": [{}]}, "volumes": []}},
        {"geometryEditor": {"preview": {"volumes": [{"unknown": 1}]}}},
        {"sourceEditor": {"energy": float("inf")}},
    ):
        rejected(lambda invalid=invalid: project_from_dict(invalid))
    for text in ('{"version":1,"version":6}', '{"seed":NaN}', '{"seed":1e999}'):
        rejected(lambda text=text: load_json_strict(text))


def geometry_contract(work):
    source = work / "geometry.ini"
    for index, prefix in enumerate(("", "[global]\nversion = 1\n", "[global]\nversion = 2\n")):
        source.write_text(prefix + HIERARCHICAL, encoding="utf-8")
        before = source.read_bytes()
        plan = plan_geometry_migration(source, "hierarchical")
        assert b"version = 2" in plan.payload and b"# preserve this comment" in plan.payload
        assert b"size = 1 cm, 1 cm, 1 cm" in plan.payload
        assert source.read_bytes() == before
        target = work / f"strict-{index}.ini"
        publish_migration(plan, target)
        summary = parse_geometry(target, "hierarchical")
        document = geometry_document_from_summary(summary, "hierarchical")
        validate_geometry_document(document)
        assert not document.errors and document.schema_version == 2
        assert "version = 2" in generate_geometry_ini_text(document)
    source.write_text(HIERARCHICAL + "LegacyTag = keep # preserve tail\n", encoding="utf-8")
    identities = None
    for _ in range(3):
        summary = parse_geometry(source, "hierarchical")
        current = [item.identity for item in summary.diagnostics]
        assert len(current) == len(set(current))
        assert identities is None or current == identities
        identities = current
        legacy = next(item for item in summary.diagnostics if item.code == "legacy_metadata")
        before_counts = (len(summary.warnings), len(summary.round_trip_blockers), len(summary.diagnostics))
        summary.record(legacy.code, legacy.severity, "a different display wording for the same source fact",
                       line=legacy.line, section=legacy.section.upper(), key=legacy.key.upper(), value=legacy.value)
        assert before_counts == (len(summary.warnings), len(summary.round_trip_blockers), len(summary.diagnostics))
        document = geometry_document_from_summary(summary, "hierarchical")
        validate_geometry_document(document)
        counts = (len(document.errors), len(document.warnings))
        for _ in range(3):
            validate_geometry_document(document)
            assert counts == (len(document.errors), len(document.warnings))
            document = geometry_document_from_dict(geometry_document_to_snapshot(document))
            validate_geometry_document(document)
            assert counts == (len(document.errors), len(document.warnings))
    rejected(lambda: plan_geometry_migration(source, "hierarchical"), "explicit legacy metadata")
    plan = plan_geometry_migration(source, "hierarchical", metadata_mapping={"[volume.Target]/LegacyTag": "metadata.LegacyTag"})
    assert b"metadata.LegacyTag = keep # preserve tail" in plan.payload
    for text, mapping in (
        (HIERARCHICAL + "LegacyTag = keep\nmetadata.LegacyTag = occupied\n", {"[volume.Target]/LegacyTag": "metadata.LegacyTag"}),
        (HIERARCHICAL + "vis.typo = red\n", {"[volume.Target]/vis.typo": "metadata.typo"}),
        (HIERARCHICAL, {"[volume.Target]/missing": "metadata.tag"}),
        (HIERARCHICAL + "Material = G4_Si\n", None),
        (HIERARCHICAL + "\n[WORLD]\n", None),
        ("[global]\nversion=999\n" + HIERARCHICAL, None),
        (HIERARCHICAL + "\n[unknown]\n", None),
        (HIERARCHICAL + "placement=assembly\n", None),
    ):
        source.write_text(text, encoding="utf-8")
        rejected(lambda mapping=mapping: plan_geometry_migration(source, "hierarchical", metadata_mapping=mapping))
    resource = work / "mesh.stl"
    resource.write_text("test placeholder; backend checks actual STL", encoding="utf-8")
    source.write_text(HIERARCHICAL.replace("shape = box\nsize = 1 cm, 1 cm, 1 cm", "shape = tessellated\nfile = mesh.stl"), encoding="utf-8")
    plan = plan_geometry_migration(source, "hierarchical")
    assert str(resource.resolve()).encode() in plan.payload
    assert any("Backend Inspect inputs" in item for item in plan.validation)
    target = work / "relocated" / "mesh.ini"
    target.parent.mkdir()
    publish_migration(plan, target)
    doc = geometry_document_from_summary(parse_geometry(target, "hierarchical"), "hierarchical")
    assert doc.round_trip_blockers  # migration cannot confer J2 editing support
    source.write_text("version = 1\n" + HIERARCHICAL, encoding="utf-8")
    assert plan_geometry_migration(source, "hierarchical").payload.replace(b"\r\n", b"\n").startswith(b"[global]\nversion = 2")
    for separator in ("\r", "\x85", "\u2028", "\u2029", "\u00a0"):
        extra = "version = 2" if separator == "\r" else ""
        source.write_bytes(("[global]\nversion = 1" + separator + extra + "\n" + HIERARCHICAL).encode("utf-8"))
        rejected(lambda: plan_geometry_migration(source, "hierarchical"))


def project_type_contract(work):
    # Keep the independent review's original fixtures verbatim. Validation must
    # happen before bool()/int()/str()/list() can change their meaning.
    fixtures = (
        ({"geometryEditor": {"source_copy_mode": "false", "is_dirty": "false"}}, "source_copy_mode"),
        ({"threads": 2.75}, "threads"),
        ({"geometryEditor": {"source_errors": "ERR"}}, "source_errors"),
        ({"geometryEditor": {"source_path": None}}, "source_path"),
        ({"geometryEditor": {"volumes": [{"name": "V", "sensitive": False}],
                            "preview": {"volumes": [{"name": "V", "sensitive": 0}]}}}, "Conflicting project fields"),
        ({"geometryEditor": {"is_dirty": "false"}}, "is_dirty"),
        ({"threads": True}, "threads"),
        ({"threads": 0}, "threads"),
        ({"threads": "2.75"}, "threads"),
        ({"configPath": None}, "configPath"),
        ({"pathSettings": {"geometry_config": None}}, "geometry_config"),
        ({"physicsEditor": {"enable_biasing_physics": "false"}}, "enable_biasing_physics"),
        ({"geometryEditor": {"source_errors": ["ERR", 1]}}, "source_errors[1]"),
        ({"geometryEditor": {"volumes": [{"name": "V", "sensitive": 0}]}}, "sensitive"),
        ({"runSettings": {"threads": 2.75}}, "runSettings.threads"),
        ({"geometryEditor": {"boolean_ops": [{"index": 1.25}]}}, "index"),
    )
    source = work / "invalid-types.json"
    for payload, fragment in fixtures:
        before = json.dumps(payload, sort_keys=True)
        rejected(lambda payload=payload: project_from_dict(payload), fragment)
        assert json.dumps(payload, sort_keys=True) == before
        source.write_text(json.dumps(payload), encoding="utf-8")
        raw = source.read_bytes()
        rejected(lambda: load_project(source), fragment)
        rejected(lambda: plan_project_migration(source), fragment)
        assert source.read_bytes() == raw
    rejected(lambda: geometry_document_from_dict({"source_copy_mode": "false"}), "source_copy_mode")
    # Explicitly retained historical conversions are narrow and lossless.
    legacy = project_from_dict({"threads": "2", "seed": None,
                                "geometryEditor": {"schemaVersion": "2", "sourceCopyMode": False}})
    assert legacy.threads == 2 and legacy.runSettings.threads == 2 and legacy.seed == ""
    assert legacy.geometryEditor.schema_version == 2 and legacy.geometryEditor.source_copy_mode is False
    empty = project_from_dict({"geometryEditor": {"layered_device": {"layers": []}}})
    assert empty.geometryEditor.layered_device.layers == []
    assert project_from_dict(project_to_dict(empty)).geometryEditor.layered_device.layers == []


def editor_presence_contract(work):
    explicit = (
        ({"sourceEditor": {"particle": "", "position_mode": "plane", "source_shape": "rectangle", "preview_ray_count": 88}},
         "sourceEditor", {"particle": "", "position_mode": "plane", "position_type": "plane", "source_shape": "rectangle", "preview_ray_count": 88}),
        ({"physicsEditor": {"mode": "manual", "reference_list": "", "enable_biasing_physics": True}},
         "physicsEditor", {"mode": "manual", "reference_list": "", "enable_biasing_physics": True}),
        ({"physicsEditor": {"mode": "manual", "reference_list": "", "manual_modules": ["G4EmStandardPhysics"]}},
         "physicsEditor", {"mode": "manual", "reference_list": "", "manual_modules": ["G4EmStandardPhysics"]}),
        ({"scoringEditor": {"hist_bins": 0, "dose": True, "trajectory_events": 7}},
         "scoringEditor", {"hist_bins": 0, "dose": True, "trajectory_events": 7}),
        ({"scoringEditor": {"hist_bins": -1, "fluence": True, "trajectory_events": 3}},
         "scoringEditor", {"hist_bins": -1, "fluence": True, "trajectory_events": 3}),
    )
    for index, (payload, editor, expected) in enumerate(explicit):
        source = work / f"explicit-editor-{index}.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        raw = source.read_bytes()
        model = load_project(source)
        for key, value in expected.items():
            assert getattr(getattr(model, editor), key) == value, (editor, key)
        plan = plan_project_migration(source)
        target = work / f"explicit-editor-copy-{index}.json"
        publish_migration(plan, target)
        reloaded = load_project(target)
        for key, value in expected.items():
            assert getattr(getattr(reloaded, editor), key) == value, (editor, key)
        assert source.read_bytes() == raw
    for version in (None, *range(1, SCHEMA_VERSION + 1)):
        historical = {"sourceSettings": {"particle": "gamma", "energy": "3 MeV"},
                      "physicsSettings": {"reference": "Shielding"},
                      "scoringSettings": {"dose": True, "hist_bins": 42, "trajectory_events": 7}}
        if version is not None:
            historical["version"] = version
        missing = project_from_dict(historical)
        assert missing.sourceEditor.particle == "gamma" and missing.sourceEditor.energy == "3 MeV"
        assert missing.physicsEditor.reference_list == "Shielding"
        assert missing.scoringEditor.dose is True and missing.scoringEditor.hist_bins == 42
        assert missing.scoringEditor.trajectory_events == 7
        for key in ("position_mode", "position_type"):
            for token in ("plane", "FuturePosition", ""):
                old = {"sourceEditor": {key: token, "source_shape": "circle", "radius": "2 mm"}}
                if version is not None:
                    old["version"] = version
                loaded = project_from_dict(old)
                assert loaded.sourceEditor.position_mode == token and loaded.sourceEditor.position_type == token
                saved = project_to_dict(loaded)
                assert saved["sourceEditor"]["position_mode"] == saved["sourceEditor"]["position_type"] == token
        supplied = dict(historical, sourceEditor={}, physicsEditor={}, scoringEditor={})
        preserved = project_from_dict(supplied)
        assert preserved.sourceEditor.particle == "proton"  # explicit editor defaults, not legacy gamma settings
        assert preserved.physicsEditor.reference_list == "FTFP_BERT_EMZ"
        assert preserved.scoringEditor.dose is False and preserved.scoringEditor.hist_bins == 100
    for index, (left, right) in enumerate((("plane", "point"), ("plane", ""), ("", "plane"), ("Plane", "plane"))):
        payload = {"sourceEditor": {"position_mode": left, "position_type": right}}
        rejected(lambda payload=payload: project_from_dict(payload), "Conflicting project fields")
        source = work / f"conflicting-source-position-{index}.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        raw = source.read_bytes()
        rejected(lambda: load_project(source), "Conflicting project fields")
        rejected(lambda: plan_project_migration(source), "Conflicting project fields")
        assert source.read_bytes() == raw
    # Preserve the established public model constructor used by existing smoke:
    # position_mode alone is authoritative when exporting an in-memory object.
    model = G4USimProject(sourceEditor=SourceEditableModel(position_mode="plane", source_shape="circle", radius="3 mm"))
    before_alias = model.sourceEditor.position_type
    path = work / "in-memory-plane.json"
    save_project(model, path)
    assert model.sourceEditor.position_type == before_alias  # serializer never edits the caller
    assert load_project(path).sourceEditor.position_type == "plane"


def publication_contract(work):
    source = work / "publish.json"
    source.write_text('{"version":1}', encoding="utf-8")
    before = source.read_bytes()
    plan = plan_project_migration(source)
    rejected(lambda: publish_migration(plan, source), "already exists")
    hardlink = work / "source-link.json"
    os.link(source, hardlink)
    rejected(lambda: publish_migration(plan, hardlink), "already exists")
    target = work / "target.json"
    target.write_bytes(b"occupied")
    rejected(lambda: publish_migration(plan, target), "already exists")
    assert target.read_bytes() == b"occupied" and source.read_bytes() == before
    target.unlink()
    for operation in ("fsync", "link"):
        with patch(f"g4usim_gui.core.config_migration.os.{operation}", side_effect=OSError("injected failure")):
            rejected(lambda: publish_migration(plan, target), "injected failure")
        assert not target.exists() and source.read_bytes() == before
        assert not list(work.glob(".target.json.*.tmp"))
    real_link = os.link
    def competing_link(temporary, destination):
        Path(destination).write_bytes(b"competing writer")
        real_link(temporary, destination)
    with patch("g4usim_gui.core.config_migration.os.link", side_effect=competing_link):
        rejected(lambda: publish_migration(plan, target))
    assert target.read_bytes() == b"competing writer"
    target.unlink()
    source.write_text('{"version":2}', encoding="utf-8")
    rejected(lambda: publish_migration(plan, target), "source changed")
    assert not target.exists()
    source.write_bytes(before)
    real_unlink = Path.unlink
    def failed_cleanup(path, *args, **kwargs):
        if path.name.startswith(".target.json."):
            raise OSError("injected cleanup failure")
        return real_unlink(path, *args, **kwargs)
    with patch.object(Path, "unlink", new=failed_cleanup):
        published = publish_migration(plan, target)
    assert target.read_bytes() == plan.payload and "cleanup failed" in published.cleanup_warning
    target.unlink()
    for temporary in work.glob(".target.json.*.tmp"):
        temporary.unlink()
    real_fsync = os.fsync
    def change_source_after_write(fd):
        real_fsync(fd)
        source.write_text('{"version":3}', encoding="utf-8")
    with patch("g4usim_gui.core.config_migration.os.fsync", side_effect=change_source_after_write):
        rejected(lambda: publish_migration(plan, target), "source changed")
    assert not target.exists() and not list(work.glob(".target.json.*.tmp"))


def main():
    with tempfile.TemporaryDirectory(prefix="e6-migration-") as temp:
        work = Path(temp)
        project_contract(work)
        geometry_contract(work)
        project_type_contract(work)
        editor_presence_contract(work)
        publication_contract(work)
    print("E6 migration copy contract: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
