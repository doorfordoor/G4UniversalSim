"""Independent F5 core review; no product edits and no Geant4 execution."""
import copy
import dataclasses
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'gui'))
sys.path.insert(0, str(ROOT/'scripts'))
from g4usim_gui.core.edit_snapshot import *
from g4usim_gui.core.edit_transactions import *
from g4usim_gui.core.project import *
from g4usim_gui.editors.material_editor_model import material_document_from_summary, generate_materials_ini_text
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.parsers.materials_parser import parse_materials_text
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.core.edit_state import empty_editing_state
from g4usim_gui.core.diagnostics import collect_diagnostics
from g4usim_gui.validators.config_validator import validate_config_builder
from g4usim_gui.models.package_model import PathSettings, GeometrySettings
from test_f5_transactions import fixture, changed, MATERIALS, GEOMETRY

facts = []

def reject(fn):
    try: fn()
    except (ValueError,TypeError): return True
    return False

# A: wire strictness and independently generated one-field corruptions.
base = fixture(); wire = snapshot_to_dict(base)
for path in [('project','materialEditor','rows',0,'density'), ('project','sourceEditor','isotropic'),
             ('project','geometryEditor','simple_box','target_sensitive')]:
    p = copy.deepcopy(wire); current = p
    for k in path[:-1]: current=current[k]
    current[path[-1]] = {'bad':'type'}
    assert reject(lambda: snapshot_from_dict(p)), path
for key in list(wire['project']):
    p=copy.deepcopy(wire); del p['project'][key]
    assert reject(lambda: snapshot_from_dict(p)), key
for key in list(wire['project']['geometryEditor']):
    if key=='preview': continue # redundant compatibility view isn't required data
    p=copy.deepcopy(wire); del p['project']['geometryEditor'][key]
    if key in {'volumes','boolean_ops'}:
        del p['project']['geometryEditor']['preview'][key]
    assert reject(lambda: snapshot_from_dict(p)), key
for alias in ['sourcePath','dirty','sourceCopyMode']:
    p=copy.deepcopy(wire); p['project']['geometryEditor'][alias] = 'conflict'
    assert reject(lambda: snapshot_from_dict(p)), alias
p=copy.deepcopy(wire); p['project']['sourceEditor']['position_mode']='plane'; p['project']['sourceEditor']['position_type']='point'
assert reject(lambda: snapshot_from_dict(p))
assert snapshot_to_dict(snapshot_from_json(snapshot_to_json(base))) == wire
facts.append({'category':'no_issue','case':'strict_codec_and_full_roundtrip','checks':'missing top/nested fields, wrong types, aliases, complete roundtrip'})

# B: apply-failure atomicity with saved marker, redo branch, capacity.
h=EditSession(base,max_commands=2)
h.replace('a',changed(base,'a')); h.mark_saved(); h.replace('b',changed(base,'b')); h.undo()
before=(snapshot_fingerprint(h.current()),h.revision,h.saved_fingerprint,h.history_count,h.can_redo,h.history_bytes)
external={'name':h.current().project.projectName}
calls=[]
def fail_once(s):
    calls.append(s.project.projectName); external['name']=s.project.projectName
    if len(calls)==1: raise RuntimeError('partial view publication')
try: h.replace('bad',changed(base,'bad'),apply=fail_once)
except TransactionApplyError as e: assert e.rollback is None
else: assert False
assert before==(snapshot_fingerprint(h.current()),h.revision,h.saved_fingerprint,h.history_count,h.can_redo,h.history_bytes)
assert external['name']=='a'
for op in [lambda:h.replace('stale',changed(base,'x'),expected_revision=True),
           lambda:h.transact('nested',lambda s:h.mark_saved()),
           lambda:h.transact('throw',lambda s: (_ for _ in ()).throw(ValueError('no publish')))]:
    assert reject(op)
assert before==(snapshot_fingerprint(h.current()),h.revision,h.saved_fingerprint,h.history_count,h.can_redo,h.history_bytes)
h.redo(); h.replace('c',changed(base,'c')); h.replace('d',changed(base,'d'))
assert h.history_count==2 and h.is_modified
h.undo(); h.undo(); assert h.current().project.projectName=='b' and not h.can_undo and h.is_modified
facts.append({'category':'no_issue','case':'failure_and_history_boundary','checks':'partial apply rollback; saved marker; redo preserved on reject; reentrant guard; whole-command trim'})

# C: saved diagnostic caches can disagree with source text. Exercise the real
# project/snapshot codecs and both writers, then the public config validator.
with tempfile.TemporaryDirectory(prefix='f5-core-review-') as tmp:
    work=Path(tmp); material_source=work/'materials.ini'; geometry_source=work/'geometry.ini'
    material_text=MATERIALS+'unknown_parameter = 7\n'
    geometry_text=GEOMETRY+'placement = replica\n'
    material_source.write_text(material_text,encoding='utf-8'); geometry_source.write_text(geometry_text,encoding='utf-8')
    m=material_document_from_summary(parse_materials_text(material_text,source_path=material_source)); m.is_dirty=True
    g=geometry_document_from_summary(parse_geometry_text(geometry_text,source_path=geometry_source,template_name='hierarchical')); g.is_dirty=True
    assert m.source_errors and g.round_trip_blockers
    assert reject(lambda:generate_materials_ini_text(m))
    assert reject(lambda:generate_geometry_ini_text(g))
    p=G4USimProject(materialEditor=m,geometryEditor=g)
    p.pathSettings.materials_config=str(material_source); p.pathSettings.geometry_config=str(geometry_source)
    p.geometrySettings=GeometrySettings(template='hierarchical',config_path=str(geometry_source))
    state=empty_editing_state(); state['sources']={
      'materials':{'path':str(material_source),'text':material_text,'read_success':True,'template':''},
      'geometry':{'path':str(geometry_source),'text':geometry_text,'read_success':True,'template':'hierarchical'}}
    full=snapshot_to_dict(WorkspaceSnapshot(p,state))
    full['project']['materialEditor']['source_errors']=[]
    full['project']['materialEditor']['errors']=[]
    full['project']['geometryEditor']['source_errors']=[]
    full['project']['geometryEditor']['errors']=[]
    full['project']['geometryEditor']['round_trip_blockers']=[]
    restored=snapshot_from_dict(full)
    material_output=generate_materials_ini_text(restored.project.materialEditor)
    geometry_output=generate_geometry_ini_text(restored.project.geometryEditor)
    assert 'unknown_parameter' not in material_output and 'placement' not in geometry_output
    # Provide a fake existing executable for validation only; never execute it.
    executable=work/'backend-not-executed'; executable.write_bytes(b'fixture only')
    paths=PathSettings(executable=str(executable),workspace_root=str(work),runs_root=str(work),
                       materials_config=str(material_source),geometry_config=str(geometry_source))
    report=validate_config_builder(paths=paths,run=p.runSettings,geometry=p.geometrySettings,
        source=p.sourceSettings,physics=p.physicsSettings,scoring=p.scoringSettings,
        material_document=restored.project.materialEditor,geometry_document=restored.project.geometryEditor,
        source_model=p.sourceEditor,physics_model=p.physicsEditor,scoring_model=p.scoringEditor)
    codes=[d.code for d in collect_diagnostics(report)]
    facts.append({'category':'confirmed','case':'source_cache_blocker_bypass',
        'original_material_errors':m.source_errors,'original_geometry_blockers':g.round_trip_blockers,
        'restored_accepted':True,'material_unknown_dropped':True,'geometry_placement_dropped':True,
        'validator_errors':report.errors,'validator_codes':codes})

# D: double projection failure is explicit but does not freeze the pure session.
h=EditSession(base)
def broken(s): raise RuntimeError('view unavailable')
try: h.replace('broken',changed(base,'broken'),apply=broken)
except TransactionApplyError as e: assert e.rollback is not None
else: assert False
assert h.revision==0
h.replace('after failure',changed(base,'accepted after failed rollback'))
assert h.revision==1
facts.append({'category':'needs_experiment','case':'rollback_failure_no_core_freeze',
  'explicit_error':True,'subsequent_replace_accepted':True,'boundary':'GUI must freeze/resynchronize if projection and rollback both failed'})
print(json.dumps(facts,ensure_ascii=False,indent=2))
