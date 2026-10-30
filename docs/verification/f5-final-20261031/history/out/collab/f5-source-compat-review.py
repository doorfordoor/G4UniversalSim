"""Independent compatibility checks after the captured-source repair."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'scripts')]
from test_f5_transactions import MATERIALS, GEOMETRY
from g4usim_gui.core.edit_state import empty_editing_state
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_from_json, snapshot_to_json, snapshot_to_dict
from g4usim_gui.core.project import G4USimProject, project_from_dict, project_to_dict
from g4usim_gui.editors.material_editor_model import MaterialDocument, material_document_from_summary, generate_materials_ini_text
from g4usim_gui.editors.geometry_editor_model import GeometryDocument, geometry_document_from_summary
from g4usim_gui.parsers.materials_parser import parse_materials_text
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text

evidence = {}
with tempfile.TemporaryDirectory(prefix='f5-source-compat-review-') as temporary:
    root = Path(temporary)
    first, second = root / 'first', root / 'second'
    first.mkdir(); second.mkdir()
    material_path, geometry_path = first / 'materials.ini', first / 'geometry.ini'
    material_text, geometry_text = MATERIALS + 'unknown_parameter = 7\n', GEOMETRY + 'placement = replica\n'
    p = G4USimProject()
    p.materialEditor = material_document_from_summary(parse_materials_text(material_text, source_path=material_path))
    p.geometryEditor = geometry_document_from_summary(parse_geometry_text(geometry_text, source_path=geometry_path, template_name='hierarchical'))
    p.materialEditor.is_dirty = p.geometryEditor.is_dirty = True
    state = empty_editing_state()
    state['sources'] = {
        'materials': {'path': str(material_path), 'text': material_text, 'read_success': True, 'template': ''},
        'geometry': {'path': str(geometry_path), 'text': geometry_text, 'read_success': True, 'template': 'hierarchical'},
    }
    original = WorkspaceSnapshot(p, state)
    encoded = snapshot_to_json(original)
    previous = Path.cwd()
    try:
        os.chdir(second)
        with patch.object(Path, 'read_text', side_effect=AssertionError('source reread')):
            restored = snapshot_from_json(encoded)
        before = original.project.materialEditor._f4_source_diagnostics
        after = restored.project.materialEditor._f4_source_diagnostics
        assert [x.identity for x in after] == [x.identity for x in before]
        assert after[0].source.filename == str(material_path)
        assert restored.project.geometryEditor.round_trip_blockers == original.project.geometryEditor.round_trip_blockers
        evidence['cross_cwd_captured_absolute_source'] = 'passed: same diagnostic identity/path/text, no filesystem reads'
    finally:
        os.chdir(previous)

    empty_project = G4USimProject(materialEditor=MaterialDocument(), geometryEditor=GeometryDocument())
    empty_project.editingState = copy.deepcopy(state)
    loaded_empty = project_from_dict(project_to_dict(empty_project))
    assert loaded_empty.materialEditor is not None and loaded_empty.materialEditor.rows == []
    assert loaded_empty.geometryEditor.volumes == []
    assert not loaded_empty.materialEditor.source_errors and not loaded_empty.geometryEditor.round_trip_blockers
    evidence['explicit_v7_empty_editor'] = 'passed: explicit empty documents retained, no old-preview fallback'

    for version in range(1, 7):
        old = project_from_dict({'schema': 'G4UniversalSimProject', 'version': version,
                                 'projectName': 'legacy', 'seed': '21', 'runSettings': {'seed': None}})
        assert old.materialEditor is None and old.editingState is None
        assert old.runSettings.seed == 21
    evidence['legacy_omitted_sources_v1_v6'] = 'passed: None distinction and flat seed compatibility retained'

    wire = snapshot_to_dict(original)['project']
    wire['materialEditor']['source_errors'] = []
    wire['materialEditor']['errors'] = []
    wire['geometryEditor']['round_trip_blockers'] = []
    wire['geometryEditor']['source_errors'] = []
    wire['geometryEditor']['errors'] = []
    wire['version'] = 6
    legacy_label = project_from_dict(wire)
    material_written = generate_materials_ini_text(legacy_label.materialEditor)
    geometry_written = generate_geometry_ini_text(legacy_label.geometryEditor)
    evidence['v6_label_with_v7_raw_documents'] = {
        'material_cache_rebuilt': bool(legacy_label.materialEditor.source_errors),
        'geometry_blockers_rebuilt': bool(legacy_label.geometryEditor.round_trip_blockers),
        'writers_discard_source_fields': 'unknown_parameter' not in material_written and 'placement' not in geometry_written,
        'scope': 'direct ordinary project loader; changing only version to 6 and removing redundant editingState reaches legacy gate',
    }
destination = ROOT / 'out/collab/f5-source-compat-review.json'
destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(evidence, ensure_ascii=False, indent=2))
