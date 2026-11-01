"""Out-only candidate probe; imports production then substitutes draft source in memory."""
import ast
import importlib
import json
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'gui'))
manifest = json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
for name in ('core.i18n', 'editors.material_editor_model', 'editors.source_physics_scoring_model', 'validators.config_validator'):
    module = importlib.import_module('g4usim_gui.'+name)
    path = Path(module.__file__)
    draft = OUT/'files'/path.relative_to(ROOT)
    exec(compile(draft.read_text(encoding='utf-8'), str(draft), 'exec'), module.__dict__)
from g4usim_gui.editors.material_editor_model import MaterialRow, MaterialDocument, validate_material_document, density_internal_value
from g4usim_gui.editors.source_physics_scoring_model import PhysicsEditableModel, validate_physics_model
from g4usim_gui.core.diagnostics import collect_diagnostics, diagnostics_from_dict, diagnostics_to_dict
from g4usim_gui.validators.config_validator import ValidationReport, _validate_geometry_text
material = 'gui/g4usim_gui/editors/material_editor_model.py'
def density_ast(path):
    return ast.dump(next(node for node in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(node, ast.FunctionDef) and node.name=='density_internal_value'))
assert density_ast(ROOT/material) == density_ast(OUT/'files'/material)
cases = [('bad','numeric'), ('0 g/cm3','positive'), ('-1 G/CM3','positive'),
         ('-0x1p0 * g/cm3','positive'), ('1e-999 g/cm3','positive'),
         ('1e309 g/cm3','invalid'), ('1e308 g/cm3','invalid'), ('1 unknown','invalid'),
         ('1 G/CM3',None), ('2.7 * g/cm3',None), ('0x1p0 * G/CM3',None)]
results=[]
for value, expected in cases:
    doc=MaterialDocument(rows=[MaterialRow(name='M',density=value,components_text='Si:1')])
    validate_material_document(doc)
    records=[d for d in collect_diagnostics(doc) if d.code.startswith('materials.density.')]
    assert [d.code for d in records] == ([] if expected is None else ['materials.density.'+expected]), (value,records)
    assert (density_internal_value(value) is not None) == (expected is None)
    assert all(d.location.field=='density' and d.location.row==0 for d in records)
    payload=diagnostics_to_dict(collect_diagnostics(doc))
    assert [d.identity for d in diagnostics_from_dict(payload).diagnostics] == [d.identity for d in collect_diagnostics(doc)]
    results.append({'value':value,'code':expected})
for model, expected, field in (
    (PhysicsEditableModel(mode='bad'), 'physics.mode.unsupported', 'mode'),
    (PhysicsEditableModel(mode='manual'), 'physics.structured.invalid', 'manual_modules'),
    (PhysicsEditableModel(mode='manual',manual_modules=['G4EmStandardPhysics']), None, None)):
    validate_physics_model(model)
    errors=[d for d in collect_diagnostics(model) if d.severity=='error']
    assert ([d.code for d in errors] == [expected]) if expected else not errors, errors
    if expected:
        assert errors[0].location.field == field
with tempfile.TemporaryDirectory(prefix='j2-f4-draft-') as temp:
    path=Path(temp)/'geometry.ini'
    path.write_text('[volume.A]\nshape=tessellated\nplacement=replica\n[volume.B]\nplacement=assembly\n',encoding='utf-8')
    report=ValidationReport()
    _validate_geometry_text(path,report)
    codes={d.code:d for d in report.diagnostics}
    assert codes['geometry.shape.experimental'].source.line==2
    assert codes['geometry.placement.experimental'].source.line==3
    assert codes['geometry.placement.unsupported'].source.line==5 and not report.can_run
    assert not any('cannot edit' in d.message or d.code.endswith('not_editable') for d in report.diagnostics)
import hashlib
assert all(hashlib.sha256((ROOT/f['path']).read_bytes()).hexdigest()==f['original_raw_sha256'] for f in manifest['files'])
(OUT/'probe-receipt.json').write_text(json.dumps({'out_only':True,'tracked_sources_unchanged':True,'density_acceptance_function_ast_unchanged':True,'density_cases':results,'physics_cases':3,'source_diagnostic_cases':3},indent=2)+'\n',encoding='utf-8')
print('Out-only density categories, unknown/manual physics and experimental geometry diagnostics passed; product unchanged.')
