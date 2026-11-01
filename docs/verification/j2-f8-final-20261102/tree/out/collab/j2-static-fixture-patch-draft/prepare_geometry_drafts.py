import ast,difflib,hashlib,json,subprocess
from pathlib import Path
ROOT=Path.cwd(); OUT=ROOT/'out/collab/j2-static-fixture-patch-draft'
OUT.mkdir(parents=True,exist_ok=True)
records=[]
def proposal(file,text):
 original=(ROOT/file).read_bytes(); before=original.decode('utf-8-sig').replace('\r\n','\n')
 ast.parse(text,filename=file)
 path=OUT/'proposed'/file; path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(text.encode())
 patch=''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='a/'+file,tofile='b/'+file))
 (OUT/(Path(file).stem+'.patch')).write_bytes(patch.encode())
 records.append({'path':file,'base_sha256_raw':hashlib.sha256(original).hexdigest(),'proposed_sha256':hashlib.sha256(text.encode()).hexdigest(),'patch':Path(file).stem+'.patch','syntax':'ast.parse only; not executed or applied'})
 return before
file='scripts/test_k1_bundle.py'; text=(ROOT/file).read_text(encoding='utf-8-sig')
text=text.replace('from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary','from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary, validate_geometry_document\nfrom g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text')
text=text.replace('    # must relocate copies_file exactly once and retain source-copy blockers.','    # must relocate copies_file exactly once. J2 supports editing these volumes;\n    # unknown-field blockers are exercised separately below.')
text=text.replace('    snapshot.project.geometryEditor.source_copy_mode = True\n    main = Path(snapshot.project.configPath)', '''    document = snapshot.project.geometryEditor
    validate_geometry_document(document, material_names={"G4_Galactic", "G4_Si"})
    assert not document.round_trip_blockers and not document.errors
    det = next(row for row in document.volumes if row.name == "det")
    assert det.preview_properties == {"placement": "parameterised", "copies_file": "copies.csv"}
    generated = generate_geometry_ini_text(document)
    assert "placement = parameterised" in generated
    assert f"copies_file = {copies.resolve()}" in generated
    # Explicit source-copy remains a separate user choice, not a fabricated blocker.
    document.source_copy_mode = True
    main = Path(snapshot.project.configPath)''',1)
text=text.replace('    assert collected["snapshot"]["project"]["geometryEditor"]["round_trip_blockers"]\n    assert all(str(geometry) not in msg for msg in collected["snapshot"]["project"]["geometryEditor"]["round_trip_blockers"])','''    portable = collected["snapshot"]["project"]["geometryEditor"]
    assert not portable["round_trip_blockers"] and portable["source_copy_mode"] is True
    receipts = [row for row in collected["resources"] if row["role"] == "copies"]
    assert len(receipts) == 1 and receipts[0]["source_sha256"] == bundle.digest(copies.read_bytes())
    portable_det = next(row for row in portable["volumes"] if row["name"] == "det")
    assert portable_det["preview_properties"]["copies_file"] == receipts[0]["path"]''',1)
text=text.replace('    assert restored.project.geometryEditor.round_trip_blockers\n    assert sum(row.get("role") == "copies" for row in exported["manifest"]["members"]) == 1\n    assert copies.is_file()','''    assert not restored.project.geometryEditor.round_trip_blockers
    assert sum(row.get("role") == "copies" for row in exported["manifest"]["members"]) == 1
    assert copies.is_file()
    copies_before = copies.read_bytes()
    # Relocate the bundle and take its original source tree offline. New input paths
    # must resolve inside the moved bundle; the old workspace must fail closed.
    moved = root / "copies-moved"
    (root / "copies-bundle").rename(moved)
    original_source = Path(snapshot.project.workspaceRoot)
    parked_source = root / "source-offline"
    original_source.rename(parked_source)
    try:
        refused(lambda: bundle.collect_bundle_resources(snapshot))
        refused(lambda: bundle.export_bundle(snapshot, root / "missing-source-refused"))
        assert not (root / "missing-source-refused").exists()
        relocated = bundle.load_bundle(moved)
        moved_doc = relocated.project.geometryEditor
        moved_det = next(row for row in moved_doc.volumes if row.name == "det")
        table = Path(moved_det.preview_properties["copies_file"])
        assert table.resolve().is_relative_to(moved.resolve())
        assert table.read_bytes() == copies_before
        moved_doc.source_copy_mode = False
        emitted = generate_geometry_ini_text(moved_doc)
        assert f"copies_file = {table.resolve()}" in emitted
        assert str(original_source) not in emitted
        table.unlink()
        try:
            refused(lambda: bundle.load_bundle(moved))
        finally:
            table.write_bytes(copies_before)
        assert bundle.inspect_bundle(moved)["replay_verified"] is False
    finally:
        parked_source.rename(original_source)
    assert copies.read_bytes() == copies_before''',1)
insert='''def test_unknown_geometry_blocker_controls(root):
    """An unknown field stays blocked; source-copy is not a K1 grammar bypass."""
    snapshot = fixture(root / "source")
    geometry = Path(snapshot.project.pathSettings.geometry_config)
    text = GEOMETRY + "placement_future = replica\\n"
    write(geometry, text)
    document = geometry_document_from_summary(parse_geometry(geometry, "simple_box"), "simple_box")
    snapshot.project.geometryEditor = document
    before = geometry.read_bytes()
    blockers = list(document.round_trip_blockers)
    assert blockers and any("placement_future" in item for item in blockers)
    assert document.raw_source_text == text
    for source_copy in (False, True):
        document.source_copy_mode = source_copy
        if source_copy:
            refused(lambda: generate_geometry_ini_text(document), "original source copy mode")
        else:
            refused(lambda: generate_geometry_ini_text(document), "round-trip is blocked")
        refused(lambda: bundle.collect_bundle_resources(snapshot), "Unknown resource grammar")
        destination = root / ("unknown-copy-refused" if source_copy else "unknown-editor-refused")
        refused(lambda: bundle.export_bundle(snapshot, destination), "Unknown resource grammar")
        assert not destination.exists() and geometry.read_bytes() == before
        assert document.round_trip_blockers == blockers and document.raw_source_text == text
    # A captured blocker must not turn a vanished source into an empty geometry.
    parked = geometry.with_suffix(".offline")
    geometry.rename(parked)
    try:
        refused(lambda: bundle.collect_bundle_resources(snapshot))
        refused(lambda: bundle.export_bundle(snapshot, root / "unknown-missing-refused"))
        assert not (root / "unknown-missing-refused").exists()
        assert document.source_path == str(geometry)
        assert document.raw_source_text == text and document.round_trip_blockers == blockers
    finally:
        parked.rename(geometry)
    assert geometry.read_bytes() == before


'''
text=text.replace('def backend_check(root, executable):',insert+'def backend_check(root, executable):',1)
text=text.replace('test_refusals, test_atomic_and_tamper, test_gdml, test_independent_review_regressions):','test_refusals, test_atomic_and_tamper, test_gdml, test_independent_review_regressions,\n                     test_unknown_geometry_blocker_controls):',1)
proposal(file,text)
file='scripts/test_config_migration.py'; text=(ROOT/file).read_text(encoding='utf-8-sig')
text=text.replace('from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text','from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text, write_geometry_ini')
text=text.replace('    source.write_text(HIERARCHICAL.replace("shape = box\\nsize = 1 cm, 1 cm, 1 cm", "shape = tessellated\\nfile = mesh.stl"), encoding="utf-8")','''    mesh_text = HIERARCHICAL.replace("shape = box\\nsize = 1 cm, 1 cm, 1 cm",
                                    "shape = tessellated\\nfile = mesh.stl\\nunit = cm")
    mesh_text += ("position = 2 mm,3 mm,4 mm\\nrotation = 0 deg,0 deg,30 deg\\n"
                  "sensitive = true\\ncopyNo = 7\\nvis.alpha = 0.4\\nmetadata.Note = mesh-token\\n")
    source.write_text(mesh_text, encoding="utf-8")
    mesh_before = source.read_bytes()
    original_doc = geometry_document_from_summary(parse_geometry(source, "hierarchical"), "hierarchical")''',1)
text=text.replace('    assert doc.round_trip_blockers  # migration cannot confer J2 editing support','''    validate_geometry_document(doc)
    assert not doc.round_trip_blockers and not doc.errors
    assert doc.source_path == str(target) and doc.schema_version == 2
    original_row = next(row for row in original_doc.volumes if row.name == "Target")
    migrated_row = next(row for row in doc.volumes if row.name == "Target")
    retained = ("name", "parent", "shape", "size", "parameters", "material", "position", "rotation",
                "sensitive", "bias", "region", "copy_no", "metadata", "visual", "production_cuts",
                "preview_properties")
    for field in retained:
        assert getattr(migrated_row, field) == getattr(original_row, field), field
    expected_properties = {**original_row.shape_properties, "file": str(resource.resolve())}
    assert migrated_row.shape_properties == expected_properties
    assert migrated_row.shape == "tessellated" and migrated_row.shape_properties["unit"] == "cm"
    migrated_bytes = target.read_bytes()
    assert source.read_bytes() == mesh_before
    written = work / "writer-output" / "mesh.ini"
    write_geometry_ini(str(written), doc)
    generated = generate_geometry_ini_text(doc)
    assert written.read_text(encoding="utf-8") == generated
    assert f"file = {resource.resolve()}" in generated and "version = 2" in generated
    round_trip = geometry_document_from_summary(parse_geometry(written, "hierarchical"), "hierarchical")
    validate_geometry_document(round_trip)
    assert not round_trip.errors and not round_trip.round_trip_blockers
    written_row = next(row for row in round_trip.volumes if row.name == "Target")
    for field in retained:
        assert getattr(written_row, field) == getattr(migrated_row, field), field
    assert written_row.shape_properties == expected_properties
    assert source.read_bytes() == mesh_before and target.read_bytes() == migrated_bytes
    # A genuine unknown field still blocks editing and strict migration.
    unknown = work / "unknown-mesh.ini"
    unknown_text = mesh_text + "placement_future = replica\\n"
    unknown.write_text(unknown_text, encoding="utf-8")
    blocked = geometry_document_from_summary(parse_geometry(unknown, "hierarchical"), "hierarchical")
    assert blocked.round_trip_blockers and any("placement_future" in item for item in blocked.round_trip_blockers)
    rejected(lambda: generate_geometry_ini_text(blocked), "round-trip is blocked")
    rejected(lambda: plan_geometry_migration(unknown, "hierarchical"), "explicit legacy metadata")
    assert unknown.read_text(encoding="utf-8") == unknown_text
    # Valid STL editing support does not bypass migration source identity checks.
    stale_target = work / "stale-mesh.ini"
    source.write_bytes(mesh_before + b"# changed after planning\\n")
    try:
        rejected(lambda: publish_migration(plan, stale_target), "source changed")
        assert not stale_target.exists() and target.read_bytes() == migrated_bytes
    finally:
        source.write_bytes(mesh_before)''',1)
proposal(file,text)
(OUT/'draft-files-stage1.json').write_bytes((json.dumps(records,indent=2)+'\n').encode())
print(json.dumps(records,indent=2))
