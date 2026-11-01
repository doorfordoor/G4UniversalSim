import ast,difflib,hashlib,json,subprocess,sys,types
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'out/collab/j2-static-fixture-patch-draft';records=json.loads((OUT/'draft-files-stage1.json').read_text())
def proposal(file,text):
 original=(ROOT/file).read_bytes();before=original.decode('utf-8-sig').replace('\r\n','\n');ast.parse(text,filename=file)
 p=OUT/'proposed'/file;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(text.encode())
 (OUT/(Path(file).stem+'.patch')).write_bytes(''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='a/'+file,tofile='b/'+file)).encode())
 records.append({'path':file,'base_sha256_raw':hashlib.sha256(original).hexdigest(),'proposed_sha256':hashlib.sha256(text.encode()).hexdigest(),'patch':Path(file).stem+'.patch','syntax':'ast.parse only'})
file='scripts/test_f4_producers.py';text=(ROOT/file).read_text(encoding='utf-8-sig')
text=text.replace('from g4usim_gui.core.config_schema import check_diagnostic, check_value','from g4usim_gui.core.config_schema import check_diagnostic, check_value\nfrom g4usim_gui.core.run_editor_model import BiasRuleDefinition')
text=text.replace("({'mode':'manual'}, {'mode.unsupported':'mode'}),","({'mode':'future'}, {'mode.unsupported':'mode'}),\n        ({'mode':'manual'}, {'structured.invalid':'manual_modules'}),")
text=text.replace("({'enable_biasing_physics':True}, {'biasing.not_editable':'enable_biasing_physics'}),","({'enable_biasing_physics':True}, {'structured.invalid':'bias_rules'}),")
text=text.replace("({'extra_modules':['em']}, {'extra_modules.not_editable':'extra_modules'}),","({'extra_modules':['G4EmStandardPhysics']}, {'structured.invalid':'extra_modules'}),")
text=text.replace("({'manual_modules':['em']}, {'manual_modules.not_generated':'manual_modules'}),","({'manual_modules':['G4EmStandardPhysics']}, {'structured.invalid':'manual_modules'}),")
anchor='    # Dynamic field rules must preserve each distinct same-code occurrence.'
extra='''    # J2 supports manual constructors, reference extensions/replacements and
    # process rules. These are editor-validation positives, not physics proof.
    legacy_codes = {'physics.biasing.not_editable', 'physics.extra_modules.not_editable',
                    'physics.manual_modules.not_generated', 'physics.mode.unsupported'}
    for values in (
        {'mode':'manual', 'manual_modules':['G4EmStandardPhysics']},
        {'extra_modules':['G4OpticalPhysics']},
        {'replace_modules':['G4EmStandardPhysics_option4']},
        {'enable_biasing_physics':True, 'bias_rules':[BiasRuleDefinition(volumes='Target')]},
    ):
        model = PhysicsEditableModel(**values)
        validate_physics_model(model)
        records = collect_diagnostics(model)
        assert not model.errors, (values, model.errors)
        assert not legacy_codes.intersection(d.code for d in records)
        assert physics_model_to_snapshot(model)['mode'] == model.mode
    unknown = PhysicsEditableModel(mode='future')
    validate_physics_model(unknown)
    errors = [d for d in collect_diagnostics(unknown) if d.severity == 'error']
    assert [d.code for d in errors] == ['physics.mode.unsupported']
    assert errors[0].location.field == 'mode' and errors[0].location.collection == ''

'''
text=text.replace(anchor,extra+anchor,1)
text=text.replace("(('geometry.shape.not_editable',4),('geometry.placement.not_editable',5),","(('geometry.shape.experimental',4),('geometry.placement.experimental',5),",1)
text=text.replace("    path.write_text('[material.A]\\ntemperature=300 K\\npressure=1 atm\\n',encoding='utf-8')",'''    for code in ('geometry.shape.experimental', 'geometry.placement.experimental'):
        assert by_code[code].severity == 'warning'
        assert 'cannot edit' not in by_code[code].message
    assert by_code['geometry.placement.unsupported'].severity == 'error' and not report.can_run
    assert 'geometry.shape.not_editable' not in by_code and 'geometry.placement.not_editable' not in by_code
    path.write_text('[material.A]\\ntemperature=300 K\\npressure=1 atm\\n',encoding='utf-8')''',1)
proposal(file,text)
file='scripts/test_f4_document_diagnostics.py';text=(ROOT/file).read_text(encoding='utf-8-sig')
text=text.replace('from g4usim_gui.parsers.materials_parser import parse_materials','from g4usim_gui.parsers.materials_parser import parse_materials, NIST_QUICK_LIST\nfrom g4usim_gui.core.nist_elements import NIST_MATERIALS')
old='''    nist = MaterialDocument(rows=[MaterialRow(name="Alias", mode="nist", nist_name="Unknown"),
                                 MaterialRow(name="Unknown", mode="nist")])
    validate_material_document(nist)
    targets = selected(nist, "materials.nist.unlisted")
    assert targets[0].location is None and targets[0].unavailable_reason == "unsupported_editor"
    assert targets[0].identity_parameters["field"] == "nist_name"
    assert targets[1].location.field == "name" and targets[1].location.row == 1'''
new='''    nist = MaterialDocument(rows=[MaterialRow(name="Alias", mode="nist", nist_name="Unknown"),
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
    assert not selected(accepted, "materials.nist.unlisted")'''
assert old in text;text=text.replace(old,new,1)
text=text.replace('    assert all(item.location is None and item.unavailable_reason == "unsupported_editor" for item in alpha)','''    assert [item.location.row for item in alpha] == [1, 2]
    assert all(item.location.editor == "layers" and item.location.collection == "layers"
               and item.location.field == "vis.alpha" and not item.unavailable_reason for item in alpha)''',1)
text=text.replace('    assert all(item.location is None for item in selected(layered, "geometry.metadata.syntax"))','''    metadata = selected(layered, "geometry.metadata.syntax")
    assert [item.location.row for item in metadata] == [1, 2]
    assert all(item.location.field == "metadata" and item.location.collection == "layers"
               and not item.unavailable_reason for item in metadata)''',1)
text=text.replace('    size = selected(geometry, "geometry.vector.components")','    size = selected(geometry, "geometry.solid.size")',1)
text=text.replace('    assert {item.location.field for item in selected(geometry, "geometry.trd.length")} == {"dx1", "dx2", "dy1", "dy2", "dz"}','''    required_fields = {"dx1", "dx2", "dy1", "dy2", "dz"}
    required = [item for item in collect_diagnostics(geometry)
                if item.code in {"geometry.solid." + field for field in required_fields}]
    assert len(required) == 5 and {item.location.field for item in required} == required_fields
    assert all(item.location.collection == "volumes" and item.location.row == 1
               and item.code == "geometry.solid." + item.location.field for item in required)''',1)
text=text.replace('''    assert visual.location is None and visual.identity_parameters["field"] == "vis.alpha"
    assert visual.unavailable_reason == "unsupported_editor"''','''    assert visual.location.field == "vis.alpha" and visual.location.collection == "volumes"
    assert visual.location.row == 1 and visual.location.entity == "shape"
    assert not visual.unavailable_reason''',1)
# Golden v1 wire payload is synthesized by the historical serializer, then frozen
# as literal JSON; the current serializer is not used to manufacture expected IDs.
historical=subprocess.run(['git','show','5fe0a1052e33c96d033375d0920f29b15d432dcc:gui/g4usim_gui/core/diagnostics.py'],capture_output=True,check=True).stdout.decode('utf-8-sig')
module=types.ModuleType('_j2_historical_diagnostics');sys.modules[module.__name__]=module;exec(compile(historical,'<historical diagnostics.py>','exec'),module.__dict__)
rows=[module.Diagnostic(code='materials.density.numeric',severity='error',origin='materials.editor',message='legacy numeric',location=module.EditorLocation('materials','density','rows',0,'M'),identity_parameters={'value':'bad'}),module.Diagnostic(code='materials.density.positive',severity='error',origin='materials.editor',message='legacy positive',location=module.EditorLocation('materials','density','rows',1,'N'),identity_parameters={'value':'0 g/cm3'}),module.Diagnostic(code='physics.mode.unsupported',severity='error',origin='physics.editor',message='legacy manual unsupported',location=module.EditorLocation('physics','mode'),identity_parameters={'value':'manual'})]
golden=module.diagnostics_to_dict(rows,snapshot_id='historical-code-golden'); wire=json.dumps(golden,separators=(',',':'),ensure_ascii=False)
extra='''def check_density_machine_categories() -> None:
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
    payload = json.loads(GOLDEN)
    original = copy.deepcopy(payload)
    loaded = diagnostics_from_dict(payload)
    assert [item.code for item in loaded.diagnostics] == ["materials.density.numeric", "materials.density.positive", "physics.mode.unsupported"]
    assert diagnostics_to_dict(loaded.diagnostics, snapshot_id=loaded.snapshot_id) == original
    assert payload == original


def check_nist_alias_source(temp: Path) -> None:
    path = temp / "nist-alias.ini"
    text = "[Alias]\\nmaterial = G4_F4_UNKNOWN\\n"
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
    path.write_text("[Alias]\\nmaterial = G4_Si\\n", encoding="utf-8")
    validate_material_document(document)
    assert selected(document, "materials.nist.unknown")[0].identity == record.identity
    assert selected(document, "materials.nist.unknown")[0].source.text_snapshot == text
    refreshed = material_document_from_summary(parse_materials(path))
    validate_material_document(refreshed)
    assert not selected(refreshed, "materials.nist.unknown")


'''.replace('json.loads(GOLDEN)','json.loads('+repr(wire)+')')
text=text.replace('def main() -> int:',extra+'def main() -> int:',1)
text=text.replace('        check_material_rows()','        check_material_rows()\n        check_density_machine_categories()\n        check_legacy_code_json_unchanged()\n        check_nist_alias_source(temp)',1)
proposal(file,text)
(OUT/'draft-files.json').write_bytes((json.dumps(records,ensure_ascii=False,indent=2)+'\n').encode())
(OUT/'tests.patch').write_bytes(b''.join((OUT/r['patch']).read_bytes() for r in records))
print('Four syntax-checked draft sources and tests.patch written; no application.')
