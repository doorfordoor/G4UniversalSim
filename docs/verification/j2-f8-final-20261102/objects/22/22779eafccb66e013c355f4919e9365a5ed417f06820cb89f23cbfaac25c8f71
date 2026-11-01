"""Prepare an unapplied product patch; never write tracked candidate files."""
from pathlib import Path
import difflib
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
changes = {}
def edit(name, old, new):
    before, current = changes.get(name, (None, None))
    if before is None:
        before = current = (ROOT/name).read_text(encoding='utf-8')
    assert current.count(old) == 1, name
    changes[name] = before, current.replace(old, new)

material = 'gui/g4usim_gui/editors/material_editor_model.py'
edit(material, 'def _validate_density(row: MaterialRow) -> None:\n', '''def _density_failure_code(text: str) -> str:
    """Keep established F4 categories without weakening density acceptance."""
    match = _DENSITY_NUMBER.match(text.strip())
    if match is None:
        return 'materials.density.numeric'
    try:
        number = match.group()
        value = float.fromhex(number) if '0x' in number.lower() else float(number)
    except (ValueError, OverflowError):
        return 'materials.density.invalid'
    if math.isfinite(value) and value <= 0:
        return 'materials.density.positive'
    return 'materials.density.invalid'


def _validate_density(row: MaterialRow) -> None:
''')
edit(material, '''    if density_internal_value(row.density) is None:
        _issue(row, 'materials.density.invalid', 'error', ui_format(
            "Density must be finite and positive with a supported unit (g/cm3, kg/m3, mg/cm3): {value}", value=row.density), 'density')
''', '''    if density_internal_value(row.density) is None:
        code = _density_failure_code(row.density)
        if code == 'materials.density.numeric':
            message = "density should start with a positive number or be auto for volume_fraction"
        elif code == 'materials.density.positive':
            message = "density must be > 0"
        else:
            message = ui_format(
                "Density must be finite and positive with a supported unit (g/cm3, kg/m3, mg/cm3): {value}", value=row.density)
        _issue(row, code, 'error', message, 'density')
''')
edit(material,
     "            editable_target = target == row.name and row.name.startswith('G4_')\n",
     "            editable_target = not row.nist_name.strip() or (target == row.name and row.name.startswith('G4_'))\n")
physics = 'gui/g4usim_gui/editors/source_physics_scoring_model.py'
edit(physics, "    emit_diagnostic(model, f'{editor}.structured.invalid', 'error', problem(path, reason),\n", "    code = 'physics.mode.unsupported' if editor == 'physics' and path == 'physics.mode' else f'{editor}.structured.invalid'\n    emit_diagnostic(model, code, 'error', problem(path, reason),\n")
validator = 'gui/g4usim_gui/validators/config_validator.py'
shape_message = 'STL geometry is editable in the GUI and remains experimental; validate the resource and Geant4 initialization before running.'
placement_message = 'Replica and parameterised placement are editable in the GUI and remain experimental; validate placement constraints and Geant4 initialization before running.'
edit(validator, '''        report.add('geometry.shape.not_editable', 'warning', "Geometry uses shape = tessellated (STL, backend-supported); the GUI geometry "
                               "editors cannot edit it.", origin='config.source', source=_source_field_location(path, text, key='shape', allowed_values=('tessellated', 'stl')), unavailable_reason='source_only')
''', f"        report.add('geometry.shape.experimental', 'warning', ui_text({shape_message!r}), origin='config.source', source=_source_field_location(path, text, key='shape', allowed_values=('tessellated', 'stl')), unavailable_reason='source_only')\n")
edit(validator, '''    # Roadmap A5: the backend builds replica/parameterised placement from a
    # hand-written geometry INI; the GUI editors cannot edit them.
''', '''    # J2 exposes A5 placement editing; experimental runtime boundaries remain.
''')
edit(validator, '''        report.add('geometry.placement.not_editable', 'warning', "Geometry uses placement=replica/parameterised (backend-supported); "
                               "the GUI geometry editors cannot edit these volumes.", origin='config.source', source=_source_field_location(path, text, key='placement', allowed_values=('replica', 'parameterised', 'parameterized')), unavailable_reason='source_only')
''', f"        report.add('geometry.placement.experimental', 'warning', ui_text({placement_message!r}), origin='config.source', source=_source_field_location(path, text, key='placement', allowed_values=('replica', 'parameterised', 'parameterized')), unavailable_reason='source_only')\n")
edit('gui/g4usim_gui/core/i18n.py', 'def default_language() -> LanguageCode:\n',
     f"ZH_CN.update({{\n    {shape_message!r}: 'GUI 可编辑 STL 几何，其运行能力仍属实验性；运行前须校验资源并完成 Geant4 初始化检查。',\n    {placement_message!r}: 'GUI 可编辑 replica 和 parameterised 放置，其运行能力仍属实验性；运行前须校验放置约束并完成 Geant4 初始化检查。',\n}})\n\n\ndef default_language() -> LanguageCode:\n")
patch = []
manifest = []
for name, (before, after) in changes.items():
    target = OUT/'files'/name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(after.encode('utf-8'))
    patch.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
    manifest.append({'path': name, 'original_raw_sha256': hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),
                     'candidate_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
(OUT/'product.patch').write_bytes(''.join(patch).encode('utf-8'))
(OUT/'manifest.json').write_text(json.dumps({'applied': False, 'files': manifest}, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'applied': False, 'files': len(changes), 'patch': str(OUT/'product.patch')}))
