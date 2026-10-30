"""Independent recheck of the exact source-cache P1, after the author fix."""
import copy,json
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gui'));sys.path.insert(0,str(ROOT/'scripts'))
from test_f5_transactions import MATERIALS,GEOMETRY
from g4usim_gui.core.edit_snapshot import *
from g4usim_gui.core.edit_state import empty_editing_state
from g4usim_gui.core.edit_transactions import EditSession
from g4usim_gui.core.project import *
from g4usim_gui.parsers.materials_parser import parse_materials_text
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.editors.material_editor_model import material_document_from_summary,generate_materials_ini_text
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.validators.config_validator import validate_config_builder
from g4usim_gui.models.package_model import PathSettings,GeometrySettings

def refused(call):
    try:call()
    except ValueError as exc:return str(exc)
    assert False,'writer lost its captured source rejection'

with tempfile.TemporaryDirectory(prefix='f5-source-fix-review-') as temporary:
    root=Path(temporary); mp=root/'materials.ini';gp=root/'geometry.ini'
    mt=MATERIALS+'unknown_parameter = 7\n';gt=GEOMETRY+'placement = replica\n'
    mp.write_text(mt,encoding='utf-8');gp.write_text(gt,encoding='utf-8')
    m=material_document_from_summary(parse_materials_text(mt,source_path=mp));m.is_dirty=True
    g=geometry_document_from_summary(parse_geometry_text(gt,source_path=gp,template_name='hierarchical'));g.is_dirty=True
    p=G4USimProject(materialEditor=m,geometryEditor=g)
    p.geometrySettings=GeometrySettings(template='hierarchical',config_path=str(gp))
    state=empty_editing_state();state['sources']={
      'materials':{'path':str(mp),'text':mt,'read_success':True,'template':''},
      'geometry':{'path':str(gp),'text':gt,'read_success':True,'template':'hierarchical'}}
    snapshot=WorkspaceSnapshot(p,state);wire=snapshot_to_dict(snapshot)
    wire['project']['materialEditor']['source_errors']=[];wire['project']['materialEditor']['errors']=[]
    wire['project']['geometryEditor']['source_errors']=[];wire['project']['geometryEditor']['errors']=[]
    wire['project']['geometryEditor']['round_trip_blockers']=[]
    with patch.object(Path,'read_text',side_effect=AssertionError('Current source was read during restoration')),patch.object(Path,'read_bytes',side_effect=AssertionError('Current source bytes read during restoration')):
        restored=snapshot_from_dict(wire)
        ordinary=project_from_dict(dict(wire['project'],editingState=wire['state']))
    for project in (restored.project,ordinary):
        assert project.materialEditor.raw_source_text==mt and project.geometryEditor.raw_source_text==gt
        assert project.materialEditor.source_errors and project.geometryEditor.round_trip_blockers
        assert project.materialEditor.rows[0].components_text==m.rows[0].components_text
        assert 'unknown_parameter' in refused(lambda:generate_materials_ini_text(project.materialEditor))
        assert refused(lambda:generate_geometry_ini_text(project.geometryEditor))
    history=EditSession(snapshot)
    def clear_cached_blocks(candidate):
        candidate.project.materialEditor.source_errors=[];candidate.project.materialEditor.errors=[]
        candidate.project.geometryEditor.source_errors=[];candidate.project.geometryEditor.errors=[]
        candidate.project.geometryEditor.round_trip_blockers=[]
    history.transact('automatic attempted cache clear',clear_cached_blocks)
    assert history.current().project.materialEditor.source_errors
    assert history.current().project.geometryEditor.round_trip_blockers
    assert snapshot_fingerprint(history.current())==snapshot_fingerprint(snapshot)
    copied=copy.deepcopy(wire);copied['project']['geometryEditor']['source_copy_mode']=True
    copied=snapshot_from_dict(copied)
    assert copied.project.geometryEditor.source_copy_mode
    assert copied.project.geometryEditor.round_trip_blockers
    bad=copy.deepcopy(wire);bad['state']['sources']['geometry']['text']='different captured text'
    assert 'disagrees' in refused(lambda:snapshot_from_dict(bad))
    paths=PathSettings(executable='',workspace_root=str(root),runs_root=str(root),materials_config=str(mp),geometry_config=str(gp))
    report=validate_config_builder(paths=paths,run=p.runSettings,geometry=p.geometrySettings,source=p.sourceSettings,
       physics=p.physicsSettings,scoring=p.scoringSettings,material_document=restored.project.materialEditor,
       geometry_document=restored.project.geometryEditor,source_model=p.sourceEditor,physics_model=p.physicsEditor,scoring_model=p.scoringEditor)
    assert report.errors
    assert any('unknown_parameter' in item for item in report.errors)
    assert any('placement' in item for item in report.errors)
    print(json.dumps({'original_reproducer_now_rejected':True,'plain_project_and_snapshot_sources_rebuilt':True,
      'no_current_source_io_during_restore':True,'automatic_transaction_cannot_clear_blocks':True,
      'explicit_source_copy_remains_explicit':True,'mismatched_source_text_refused':True,
      'validator_errors':report.errors},ensure_ascii=False,indent=2))
