"""Independent boundary check after source reconstruction and downgrade fix."""
import copy,json
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gui'));sys.path.insert(0,str(ROOT/'scripts'))
from test_f5_transactions import MATERIALS,GEOMETRY
from test_project_snapshot_compat import build_package_fixture
from g4usim_gui.core.project import *
from g4usim_gui.core.edit_state import empty_editing_state
from g4usim_gui.parsers.materials_parser import parse_materials_text
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.editors.material_editor_model import material_document_from_summary,generate_materials_ini_text
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text

def rejected(call):
    try:call()
    except (ValueError,OSError) as exc:return str(exc)
    raise AssertionError('accepted a path expected to reject')

with tempfile.TemporaryDirectory(prefix='f5-compat-independent-') as temporary:
    work=Path(temporary);mp=work/'materials.ini';gp=work/'geometry.ini'
    mt=MATERIALS+'unknown_parameter = 7\n';gt=GEOMETRY+'placement = replica\n'
    m=material_document_from_summary(parse_materials_text(mt,source_path=mp));m.is_dirty=True
    g=geometry_document_from_summary(parse_geometry_text(gt,source_path=gp,template_name='hierarchical'));g.is_dirty=True
    state=empty_editing_state();state['sources']={
      'materials':{'path':str(mp),'text':mt,'read_success':True,'template':''},
      'geometry':{'path':str(gp),'text':gt,'read_success':True,'template':'hierarchical'}}
    p=G4USimProject(materialEditor=m,geometryEditor=g,editingState=state)
    wire=project_to_dict(p)
    wire['materialEditor']['source_errors']=[];wire['materialEditor']['errors']=[]
    wire['geometryEditor']['source_errors']=[];wire['geometryEditor']['errors']=[]
    wire['geometryEditor']['round_trip_blockers']=[]
    versions=[]
    for version in range(1,8):
        data=copy.deepcopy(wire);data['version']=version
        with patch.object(Path,'read_text',side_effect=AssertionError('Unexpected current file IO')),patch.object(Path,'read_bytes',side_effect=AssertionError('Unexpected current file IO')):
            restored=project_from_dict(data)
        assert restored.version==7
        assert 'unknown_parameter' in rejected(lambda:generate_materials_ini_text(restored.materialEditor))
        assert rejected(lambda:generate_geometry_ini_text(restored.geometryEditor))
        assert restored.materialEditor.raw_source_text==mt and restored.geometryEditor.raw_source_text==gt
        versions.append(version)
    legacy_versions=[]
    for version in range(1,7):
        plain=work/f'legacy-{version}.json'
        payload={'version':version,'projectName':f'legacy {version}','macroPath':'old.mac'}
        plain.write_text(json.dumps(payload),encoding='utf-8')
        restored=load_project(plain)
        assert restored.version==7 and restored.materialEditor is None and restored.editingState is None
        assert restored.macroPath=='old.mac'
        as_snapshot=load_project_snapshot(plain)
        assert not as_snapshot.inputs and not as_snapshot.package_root
        assert any('not verified' in note for note in as_snapshot.notes)
        legacy_versions.append(version)

    # This uses the actual writer; its executable fixture is never executed.
    package,_=build_package_fixture(work)
    snapshot=Path(package.project_snapshot_path);original=snapshot.read_bytes()
    normal_refusal=rejected(lambda:load_project(snapshot))
    assert normal_refusal
    material=Path(package.materials_ini_path);geometry=Path(package.geometry_ini_path)
    material.write_bytes(material.read_bytes().replace(b'density = 2 g/cm3',b'density = 2.5 g/cm3'))
    geometry.write_bytes(geometry.read_bytes().replace(b'12 mm,14 mm,16 mm',b'13 mm,14 mm,16 mm'))
    restored=load_project_snapshot(snapshot)
    assert restored.project.editingState is None
    assert not restored.project.materialEditor.is_dirty and not restored.project.geometryEditor.is_dirty
    assert all(row.name!='UnwrittenDraft' for row in restored.project.materialEditor.rows)
    assert next(row for row in restored.project.materialEditor.rows if row.name=='ActiveMix').density=='2.5 g/cm3'
    assert next(row for row in restored.project.geometryEditor.volumes if row.name=='Target').size=='13 mm,14 mm,16 mm'
    assert restored.project.materialEditor.raw_source_text==material.read_text(encoding='utf-8')
    assert snapshot.read_bytes()==original
    print(json.dumps({'captured_source_downgrade_tags_blocked':versions,
      'genuine_legacy_without_captured_content_still_reads':legacy_versions,
      'ordinary_load_rejects_package_envelope':normal_refusal,
      'E6_current_package_inputs_remain_authoritative':True,
      'v7_unwritten_drafts_not_imported_from_package':True,
      'source_restoration_performed_without_current_source_IO':True,
      'snapshot_not_modified':True,'backend_executed':False},ensure_ascii=False,indent=2))
