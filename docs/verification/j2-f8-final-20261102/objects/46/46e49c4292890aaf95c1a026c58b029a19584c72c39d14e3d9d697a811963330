"""F4 material/geometry producer contracts, without opening desktop windows."""
from __future__ import annotations

from dataclasses import asdict
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from g4usim_gui.core.diagnostics import (
    collect_diagnostics, diagnostics_from_dict, diagnostics_to_dict, semantic_snapshot,
)
from g4usim_gui.editors.geometry_editor_model import (
    BooleanOperationRow, GeometryDocument, HierarchicalVolumeRow, LayerRow,
    geometry_document_from_dict, geometry_document_from_summary,
    geometry_document_to_snapshot, validate_geometry_document,
)
from g4usim_gui.editors.material_editor_model import (
    MaterialDocument, MaterialRow, clone_document, material_document_from_summary,
    material_document_to_snapshot, validate_material_document,
)
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.ini_light_parser import parse_ini_light
from g4usim_gui.parsers.materials_parser import parse_materials, NIST_QUICK_LIST
from g4usim_gui.core.nist_elements import NIST_MATERIALS
from g4usim_gui.validators.config_validator import ValidationReport, _include_messages


def selected(owner, code):
    return [item for item in collect_diagnostics(owner) if item.code == code]


def check_source_reads(temp: Path) -> None:
    path = temp / "syntax.ini"
    raw = b"outside = 4\r\n[material.A]\r\n= bad\r\nbroken\r\n"
    path.write_bytes(raw)
    ini = parse_ini_light(path)
    records = collect_diagnostics(ini)
    assert ini.errors == ["Line 1: key/value outside any section", "Line 3: empty key", "Line 4: invalid INI line: broken"]
    assert [item.source.line for item in records] == [1, 3, 4]
    assert [(item.source.section, item.source.key, item.source.value) for item in records] == [
        ("global", "outside", "4"), ("material.A", "", "bad"), ("material.A", "", "broken")]
    assert all(item.location is None for item in records)
    assert all(item.source.text_snapshot == ini.raw_text for item in records)
    assert records[0].source.text_sha256 == hashlib.sha256(ini.raw_text.encode("utf-8")).hexdigest()
    assert records[0].source.text_sha256 != hashlib.sha256(raw).hexdigest()
    original_id = records[0].identity
    path.write_text("[new]\nvalid = true\n", encoding="utf-8")
    assert records[0].source.text_snapshot == raw.decode().replace("\r\n", "\n")
    assert records[0].identity == original_id
    missing = collect_diagnostics(parse_ini_light(temp / "missing.ini"))[0]
    assert missing.code == "ini.read_failed" and missing.source.line is None
    assert missing.source.text_snapshot is None and not missing.source.text_sha256
    geometry = parse_geometry(temp / "missing.ini", "hierarchical")
    assert geometry.errors and collect_diagnostics(geometry)[0].source.text_snapshot is None


def check_material_sources(temp: Path) -> None:
    path = temp / "materials.ini"
    text = "[material.M]\nmode = mass_fraction\ndensity = 1 g/cm3\ncomponents = Si:1\nmisspelled = 5\n"
    path.write_text(text, encoding="utf-8")
    summary = parse_materials(path)
    source = selected(summary, "materials.source.unknown_key")[0]
    assert (source.source.line, source.source.section, source.source.key, source.source.value) == (5, "material.M", "misspelled", "5")
    assert source.message == summary.errors[0] and source.location is None
    document = material_document_from_summary(summary)
    initial_errors = list(document.errors)
    source_ids = {item.identity for item in collect_diagnostics(document) if item.source}
    assert source.identity in source_ids
    document.rows[0].density = "2 g/cm3"
    path.write_text("[NIST]\nmaterials = G4_Si\n", encoding="utf-8")
    for _ in range(2):
        validate_material_document(document)
        assert document.errors == initial_errors
        assert {item.identity for item in collect_diagnostics(document) if item.source} == source_ids
    cloned = clone_document(document)
    validate_material_document(cloned)
    assert selected(cloned, "materials.source.unknown_key")[0].source.text_snapshot == text
    assert selected(cloned, "materials.source.unknown_key")[0].identity == source.identity
    assert "_f4" not in json.dumps(asdict(document))
    assert "diagnostics" not in json.dumps(material_document_to_snapshot(document))


def check_material_rows() -> None:
    document = MaterialDocument(rows=[MaterialRow(enabled=False),
        MaterialRow(name="same", density="bad", components_text="Si:bad\nO:bad"),
        MaterialRow(name="same", density="bad", components_text="Si:bad\nO:bad")])
    validate_material_document(document)
    duplicate = selected(document, "materials.name.duplicate")
    assert [item.location.row for item in duplicate] == [1, 2]
    assert all(item.location.collection == "rows" and item.location.field == "name" for item in duplicate)
    assert len({item.identity for item in duplicate}) == 2
    density = selected(document, "materials.density.numeric")
    assert [item.location.row for item in density] == [1, 2]
    components = selected(document, "materials.component.numeric")
    assert len(components) == 4 and len({item.identity for item in components}) == 4
    assert all(item.location.field == "components_text" for item in components)
    assert {item.identity_parameters["component"] for item in components} == {1, 2}
    previous = [item.identity for item in collect_diagnostics(document)]
    errors = list(document.errors)
    validate_material_document(document)
    assert [item.identity for item in collect_diagnostics(document)] == previous
    assert document.errors == errors
    # Legacy text can deduplicate equal wording; the structured rows must remain distinct.
    assert document.errors.count("same: duplicate material name") == 1
    cycle = MaterialDocument(rows=[
        MaterialRow(name="A", mode="volume_fraction", density="auto", components_text="B:1"),
        MaterialRow(name="B", mode="volume_fraction", density="auto", components_text="A:1")])
    validate_material_document(cycle)
    record = selected(cycle, "materials.components.cycle")[0]
    assert record.location.field == "components_text" and record.location.row == 1
    assert record.message in cycle.errors
    nist = MaterialDocument(rows=[MaterialRow(name="Alias", mode="nist", nist_name="Unknown"),
                                 MaterialRow(name="Unknown", mode="nist"),
                                 MaterialRow(name="G4_F4_UNKNOWN", mode="nist")])
    validate_material_document(nist)
    targets = selected(nist, "materials.nist.unknown")
    assert len(targets) == 3 and all(item.severity == "error" for item in targets)
    assert not selected(nist, "materials.nist.unlisted")
    assert targets[0].location is None and targets[0].unavailable_reason == "unsupported_editor"
    assert targets[0].identity_parameters["field"] == "nist_name"
    # Keep the original non-prefixed editable-name case; do not mask its current
    # missing-location regression by renaming the fixture to start with G4_.
    assert targets[1].location is not None
    assert targets[1].location.field == "name" and targets[1].location.row == 1
    assert targets[2].location.field == "name" and targets[2].location.row == 2
    catalog_name = "G4_A-150_TISSUE"
    assert catalog_name in NIST_MATERIALS and catalog_name not in NIST_QUICK_LIST
    accepted = MaterialDocument(rows=[MaterialRow(name=catalog_name, mode="nist"),
        MaterialRow(name="Alias", mode="nist", nist_name=catalog_name)])
    validate_material_document(accepted)
    assert not accepted.errors and not selected(accepted, "materials.nist.unknown")
    assert not selected(accepted, "materials.nist.unlisted")


def check_geometry_sources(temp: Path) -> None:
    path = temp / "geometry.ini"
    text = "[global]\nversion = 99\n[volume.world]\nshape = box\nsize = 10 cm, 10 cm, 10 cm\nmaterial = G4_AIR\nLegacyTag = original\n"
    path.write_text(text, encoding="utf-8")
    summary = parse_geometry(path, "hierarchical")
    version = selected(summary, "geometry.source.unsupported_version")[0]
    blocker = selected(summary, "geometry.source.unrepresentable_editor_field")[0]
    assert (version.source.line, version.source.key, version.source.value) == (2, "version", "99")
    assert (blocker.source.line, blocker.source.key, blocker.source.value) == (7, "LegacyTag", "original")
    document = geometry_document_from_summary(summary, "hierarchical")
    source_errors = list(document.source_errors)
    assert source_errors and document.round_trip_blockers
    validate_geometry_document(document)
    first = [item.identity for item in collect_diagnostics(document)]
    validate_geometry_document(document)
    assert [item.identity for item in collect_diagnostics(document)] == first
    assert selected(document, "geometry.source.unsupported_version")[0].identity == version.identity
    assert selected(document, "geometry.source.unrepresentable_editor_field")[0].identity == blocker.identity
    document.source_copy_mode = True
    path.write_text("[global]\nversion = 2\n", encoding="utf-8")
    validate_geometry_document(document)
    assert document.errors == source_errors  # source-copy never cures a source schema error
    assert not selected(document, "geometry.source.unrepresentable_editor_field")
    assert selected(document, "geometry.source.unsupported_version")[0].source.text_snapshot == text
    copied = selected(document, "geometry.round_trip.source_copy")[0]
    assert copied.location.editor == "geometry" and copied.location.collection == ""
    document.source_copy_mode = False
    validate_geometry_document(document)
    assert selected(document, "geometry.source.unrepresentable_editor_field")[0].identity == blocker.identity
    assert "_f4" not in json.dumps(asdict(document))
    assert "_f4" not in json.dumps(geometry_document_to_snapshot(document))
    restored = geometry_document_from_dict(asdict(document))
    validate_geometry_document(restored)
    assert restored.source_errors == source_errors and restored.round_trip_blockers
    assert source_errors[0] in restored.errors


def check_geometry_targets() -> None:
    simple = GeometryDocument(mode="simple_box")
    simple.simple_box.world_size = "bad"
    simple.simple_box.target_name = ""
    simple.simple_box.target_material = "UnknownCustom"
    validate_geometry_document(simple)
    fields = {(item.location.collection, item.location.field) for item in collect_diagnostics(simple)}
    assert fields == {("simple_box", "world_size"), ("simple_box", "target_name"), ("simple_box", "target_material")}
    assert all(item.location.row is None for item in collect_diagnostics(simple))
    layered = GeometryDocument(mode="layered_device")
    layered.layered_device.axis = "x"
    layered.layered_device.layers = [LayerRow(enabled=False), LayerRow(name="same", thickness="bad"), LayerRow(name="same", thickness="bad")]
    for row in layered.layered_device.layers[1:]:
        row.visual = {"vis.alpha": "2"}
        row.metadata = "not a metadata line"
    validate_geometry_document(layered)
    thickness = selected(layered, "geometry.layer.thickness")
    assert [item.location.row for item in thickness] == [1, 2]
    assert all(item.location.collection == "layers" and item.location.editor == "layers" for item in thickness)
    alpha = selected(layered, "geometry.layer.alpha_range")
    assert len(alpha) == 2 and len({item.identity for item in alpha}) == 2
    assert [item.location.row for item in alpha] == [1, 2]
    assert all(item.location.editor == "layers" and item.location.collection == "layers"
               and item.location.field == "vis.alpha" and not item.unavailable_reason for item in alpha)
    metadata = selected(layered, "geometry.metadata.syntax")
    assert [item.location.row for item in metadata] == [1, 2]
    assert all(item.location.field == "metadata" and item.location.collection == "layers"
               and not item.unavailable_reason for item in metadata)
    assert selected(layered, "geometry.layered.axis")[0].location.collection == "layered_device"
    assert all(not any(key.startswith("_f4") for key in vars(row)) for row in layered.layered_device.layers)
    assert LayerRow(**vars(layered.layered_device.layers[1])).name == "same"
    assert "_f4" not in json.dumps(geometry_document_to_snapshot(layered))
    assert "_f4" not in json.dumps(vars(simple.simple_box))
    world = HierarchicalVolumeRow(name="world", shape="box", size="10 cm, 10 cm, 10 cm", material="G4_AIR")
    geometry = GeometryDocument(mode="hierarchical", volumes=[world,
        HierarchicalVolumeRow(enabled=False),
        HierarchicalVolumeRow(name="same", parent="world", shape="box", size="bad", material="G4_Si"),
        HierarchicalVolumeRow(name="same", parent="world", shape="box", size="bad", material="G4_Si")],
        boolean_ops=[BooleanOperationRow(enabled=False),
            BooleanOperationRow(target_volume="same", operation="wrong", tool_shape="box", tool_size="bad")])
    validate_geometry_document(geometry)
    duplicate = selected(geometry, "geometry.volume.duplicate_name")
    assert {item.location.row for item in duplicate} == {2, 3}
    assert len({item.identity for item in duplicate}) == 2
    size = selected(geometry, "geometry.solid.size")
    assert [item.location.row for item in size] == [2, 3]
    operation = selected(geometry, "geometry.boolean.operation")[0]
    assert (operation.location.editor, operation.location.collection, operation.location.row, operation.location.entity) == ("booleans", "boolean_ops", 1, "same[0]")
    assert not selected(geometry, "geometry.boolean.disabled")  # matches the existing document text channel
    trd = HierarchicalVolumeRow(name="shape", parent="world", shape="trd", material="G4_Si", visual={"vis.alpha": "2"})
    geometry.volumes = [world, trd]
    geometry.boolean_ops = []
    validate_geometry_document(geometry)
    required_fields = {"dx1", "dx2", "dy1", "dy2", "dz"}
    required = [item for item in collect_diagnostics(geometry)
                if item.code in {"geometry.solid." + field for field in required_fields}]
    assert len(required) == 5 and {item.location.field for item in required} == required_fields
    assert all(item.location.collection == "volumes" and item.location.row == 1
               and item.code == "geometry.solid." + item.location.field for item in required)
    visual = selected(geometry, "geometry.visual.alpha_range")[0]
    assert visual.location.field == "vis.alpha" and visual.location.collection == "volumes"
    assert visual.location.row == 1 and visual.location.entity == "shape"
    assert not visual.unavailable_reason
    identities = [item.identity for item in collect_diagnostics(geometry)]
    with patch("g4usim_gui.editors.geometry_editor_model.ui_text", lambda value: "translated:" + value), patch(
            "g4usim_gui.editors.geometry_editor_model.ui_format", lambda value, **kwargs: "translated:" + value.format(**kwargs)):
        validate_geometry_document(geometry)
    assert [item.identity for item in collect_diagnostics(geometry)] == identities
    assert any(item.message.startswith("[GEOMETRY][ERROR] shape: translated:") for item in collect_diagnostics(geometry))
    records = collect_diagnostics(geometry)
    bundle = diagnostics_from_dict(diagnostics_to_dict(records))
    assert [item.identity for item in bundle.diagnostics] == identities
    assert "_f4" not in json.dumps(asdict(geometry))
    assert semantic_snapshot(geometry) == semantic_snapshot(asdict(geometry))


def check_cut_region_identities() -> None:
    """Same target does not make different cut requirements the same issue."""
    for mode, code in (("hierarchical", "geometry.cut.region"),
                       ("layered_device", "geometry.layer.cut_region")):
        document = GeometryDocument(mode=mode)
        cuts = {"cut.gamma": "1 mm", "cut.e-": "1 mm"}
        if mode == "hierarchical":
            document.volumes = [
                HierarchicalVolumeRow(name="world", shape="box", size="10 cm,10 cm,10 cm", material="G4_AIR"),
                HierarchicalVolumeRow(name="target", parent="world", shape="box", size="1 cm,1 cm,1 cm",
                                      material="G4_Si", region="", production_cuts=cuts),
            ]
        else:
            document.layered_device.layers = [LayerRow(name="target", region="", production_cuts=cuts)]
        validate_geometry_document(document)
        original_text = list(document.errors)
        records = selected(document, code)
        assert len(records) == 2 and len({item.identity for item in records}) == 2
        assert {item.identity_parameters["cut_field"] for item in records} == set(cuts)
        assert all(item.location.field == "region" for item in records)
        assert [item.location.row for item in records] == ([1, 1] if mode == "hierarchical" else [0, 0])
        report = ValidationReport()
        _include_messages(report, document, "errors", "errors", "Geometry Editor: ", origin="geometry_document")
        assert report.errors == ["Geometry Editor: " + message for message in original_text]
        assert not any(item.code == "legacy.unstructured" for item in report.diagnostics)
        loaded = diagnostics_from_dict(report.to_dict())
        assert {item.identity for item in loaded.diagnostics if item.code == code} == {item.identity for item in records}
        assert loaded.errors == tuple(report.errors)
        identities = [item.identity for item in records]
        with patch("g4usim_gui.editors.geometry_editor_model.ui_format",
                   lambda value, **kwargs: "translated:" + value.format(**kwargs)):
            validate_geometry_document(document)
        assert [item.identity for item in selected(document, code)] == identities
        validate_geometry_document(document)
        assert document.errors == original_text
        target = document.volumes[1] if mode == "hierarchical" else document.layered_device.layers[0]
        target.region = "SV"
        validate_geometry_document(document)
        assert not selected(document, code)


def check_geometry_read_evidence(temp: Path) -> None:
    """A genuine empty file and an unsuccessful read have different evidence."""
    missing = temp / "never-read.ini"
    failed = geometry_document_from_summary(parse_geometry(missing, "hierarchical"), "hierarchical")
    validate_geometry_document(failed)
    derived = selected(failed, "geometry.hierarchical.empty")[0]
    assert derived.source is not None and derived.source.filename == str(missing.resolve())
    assert derived.source.text_snapshot is None and not derived.source.text_sha256
    source_errors = list(failed.source_errors)
    failed_identity = derived.identity
    missing.write_text("[world]\nmaterial=G4_AIR\n", encoding="utf-8")
    for document in (failed, copy.deepcopy(failed)):
        # Creating the file later must not manufacture evidence for the old read.
        with patch.object(Path, "read_text", side_effect=AssertionError("validation reread the source")):
            validate_geometry_document(document)
        item = selected(document, "geometry.hierarchical.empty")[0]
        assert item.identity == failed_identity and item.source.text_snapshot is None
        assert not item.source.text_sha256 and document.source_errors == source_errors

    empty_path = temp / "empty.ini"
    empty_path.write_bytes(b"")
    previous = Path.cwd()
    try:
        os.chdir(temp)
        empty = geometry_document_from_summary(parse_geometry("empty.ini", "hierarchical"), "hierarchical")
    finally:
        os.chdir(previous)
    validate_geometry_document(empty)
    record = selected(empty, "geometry.hierarchical.empty")[0]
    assert record.source.filename == str(empty_path.resolve())
    assert record.source.text_snapshot == "" and record.source.text_sha256 == hashlib.sha256(b"").hexdigest()
    identity = record.identity
    empty_path.unlink()
    for document in (empty, copy.deepcopy(empty)):
        validate_geometry_document(document)
        item = selected(document, "geometry.hierarchical.empty")[0]
        assert item.identity == identity and item.source.text_snapshot == ""
        assert item.source.text_sha256 == record.source.text_sha256
        assert "_f4" not in json.dumps(asdict(document))
        assert "_f4" not in json.dumps(geometry_document_to_snapshot(document))

    # Restoring old model data carries no proof of a successful source read.
    restored = geometry_document_from_dict(asdict(empty))
    validate_geometry_document(restored)
    assert selected(restored, "geometry.hierarchical.empty")[0].source is None
    denied_path = temp / "denied.ini"
    denied_path.write_text("real content", encoding="utf-8")
    with patch.object(Path, "read_text", side_effect=PermissionError("test read denied")):
        denied = geometry_document_from_summary(parse_geometry(denied_path, "hierarchical"), "hierarchical")
    validate_geometry_document(denied)
    assert denied.source_errors
    assert all(item.source is None or item.source.text_snapshot is None for item in collect_diagnostics(denied))


def check_density_machine_categories() -> None:
    # Every invalid density has one category and one identity at the real row.
    for value, suffix in (("bad", "numeric"), ("0 g/cm3", "positive"),
                          ("-1 G/CM3", "positive"), ("-0x1p0 * g/cm3", "positive"),
                          ("1e-999 g/cm3", "positive"), ("1 unknown", "invalid"),
                          ("1e309 g/cm3", "invalid"), ("1e308 g/cm3", "invalid")):
        document = MaterialDocument(rows=[MaterialRow(name="M", density=value, components_text="Si:1")])
        validate_material_document(document)
        records = [item for item in collect_diagnostics(document) if item.code.startswith("materials.density.")]
        assert [item.code for item in records] == ["materials.density." + suffix], (value, records)
        assert len({item.identity for item in records}) == 1
        record = records[0]
        assert record.severity == "error" and record.location.field == "density"
        assert record.location.row == 0 and record.location.collection == "rows"
        validate_material_document(document)
        assert [item.identity for item in collect_diagnostics(document) if item.code.startswith("materials.density.")] == [record.identity]
    for value in ("1 G/CM3", "2.7 * g/cm3", "0x1p0 * G/CM3"):
        document = MaterialDocument(rows=[MaterialRow(name="M", density=value, components_text="Si:1")])
        validate_material_document(document)
        assert not document.errors, (value, document.errors)
        assert not [item for item in collect_diagnostics(document) if item.code.startswith("materials.density.")]


def check_legacy_code_json_unchanged() -> None:
    # Golden synthesized with 5fe0a10's serializer, not a claimed old run receipt.
    # Changing today's capability must not rewrite yesterday's code or identity.
    payload = json.loads('{"schema":"g4usim_diagnostics_v1","snapshot_id":"historical-code-golden","can_run":false,"errors":["legacy numeric","legacy positive","legacy manual unsupported"],"warnings":[],"info":[],"diagnostics":[{"identity":"825163aaecb59795030073ce1be05176f120e5430079ba8b1a6d65cfe5151214","code":"materials.density.numeric","severity":"error","origin":"materials.editor","message":"legacy numeric","message_key":"","params":{},"identity_parameters":{"value":"bad"},"raw_message":"","unavailable_reason":"","location":{"editor":"materials","field":"density","collection":"rows","row":0,"entity":"M","snapshot_id":""},"source":null,"related_locations":[]},{"identity":"8846271706903ded5fe458a8c514e5176e73992916457aa0f53a96e6a95bd486","code":"materials.density.positive","severity":"error","origin":"materials.editor","message":"legacy positive","message_key":"","params":{},"identity_parameters":{"value":"0 g/cm3"},"raw_message":"","unavailable_reason":"","location":{"editor":"materials","field":"density","collection":"rows","row":1,"entity":"N","snapshot_id":""},"source":null,"related_locations":[]},{"identity":"3e1098535a7dd5c237ab6f509ea127267212aba88776537e6131316198491abe","code":"physics.mode.unsupported","severity":"error","origin":"physics.editor","message":"legacy manual unsupported","message_key":"","params":{},"identity_parameters":{"value":"manual"},"raw_message":"","unavailable_reason":"","location":{"editor":"physics","field":"mode","collection":"","row":null,"entity":"","snapshot_id":""},"source":null,"related_locations":[]}]}')
    original = copy.deepcopy(payload)
    loaded = diagnostics_from_dict(payload)
    assert [item.code for item in loaded.diagnostics] == ["materials.density.numeric", "materials.density.positive", "physics.mode.unsupported"]
    assert diagnostics_to_dict(loaded.diagnostics, snapshot_id=loaded.snapshot_id) == original
    assert payload == original


def check_nist_alias_source(temp: Path) -> None:
    path = temp / "nist-alias.ini"
    text = "[Alias]\nmaterial = G4_F4_UNKNOWN\n"
    path.write_text(text, encoding="utf-8")
    document = material_document_from_summary(parse_materials(path))
    validate_material_document(document)
    records = selected(document, "materials.nist.unknown")
    assert len(records) == 1 and records[0].severity == "error"
    record = records[0]
    assert record.location is None and record.unavailable_reason == "unsupported_editor"
    assert record.identity_parameters["field"] == "nist_name" and record.identity_parameters["row"] == 0
    assert record.source.filename == str(path.resolve()) and record.source.line is None
    assert record.source.text_snapshot == text
    path.write_text("[Alias]\nmaterial = G4_Si\n", encoding="utf-8")
    validate_material_document(document)
    assert selected(document, "materials.nist.unknown")[0].identity == record.identity
    assert selected(document, "materials.nist.unknown")[0].source.text_snapshot == text
    refreshed = material_document_from_summary(parse_materials(path))
    validate_material_document(refreshed)
    assert not selected(refreshed, "materials.nist.unknown")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="g4usim-f4-documents-") as raw:
        temp = Path(raw)
        check_source_reads(temp)
        check_material_sources(temp)
        check_material_rows()
        check_density_machine_categories()
        check_legacy_code_json_unchanged()
        check_nist_alias_source(temp)
        check_geometry_sources(temp)
        check_geometry_targets()
        check_cut_region_identities()
        check_geometry_read_evidence(temp)
    print("test_f4_document_diagnostics: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
