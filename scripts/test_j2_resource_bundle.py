"""J2 resource relocation stays portable without the original spectrum/map."""
from pathlib import Path
import copy
import hashlib
import os
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gui'))
from g4usim_gui.core.project import G4USimProject, load_project_snapshot
from g4usim_gui.core.project_snapshot import _geometry_resources
from g4usim_gui.core.wizard import blank_result, apply_to_project
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
from g4usim_gui.core.experiment_bundle import export_bundle, load_bundle, collect_bundle_resources
from g4usim_gui.core.run_editor_model import GPSDefinition, FieldDefinition
from g4usim_gui.core.run_editor_resources import materialize_run_resources, materialize_geometry_file
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.writers.package_writer import create_run_package


def assert_rejected(action, fragment):
    try:
        action()
    except ValueError as error:
        assert fragment in str(error), str(error)
    else:
        assert False, f'Expected rejection containing {fragment}'


def legacy_geometry_copy_cases(root):
    source = root / 'legacy-copy-inputs'
    source.mkdir()
    table = source / 'copies.csv'
    content = b'x_mm,y_mm,z_mm\n0,0,0\n'
    table.write_bytes(content)
    for index, version in enumerate(('', 'version = 1\r\n')):
        # Both exact duplicate and last-value semantics are compatibility
        # contracts. A missing shadowed path must not be read or materialized.
        for shadow in ('copies.csv', 'missing-shadow.csv'):
            raw = ('; untouched comment\r\n[global]\r\n'+version+
                   '[world]\r\nshape=box\r\nsize=10 mm,10 mm,10 mm\r\nmaterial=G4_AIR\r\n'+
                   '[volume.Copy]\r\nparent=world\r\nshape=box\r\nsize=1 mm,1 mm,1 mm\r\nmaterial=G4_AIR\r\n'+
                   'placement=parameterised\r\n  copies_file = '+shadow+' ; shadowed raw line\r\n'+
                   '  copies_file = copies.csv  # effective raw line\r\n').encode()
            path = source / f'legacy-{index}-{shadow}.ini'
            path.write_bytes(raw)
            destination = root / f'legacy-relocated-{index}-{shadow}'
            materialize_geometry_file(path, source_base=source, destination=destination)
            targets = list(destination.iterdir())
            assert len(targets) == 1
            assert targets[0].read_bytes() == content
            expected = raw.rsplit(b'copies.csv', 1)
            assert path.read_bytes() == expected[0]+str(targets[0].resolve()).replace('\\','/').encode()+expected[1]
            assert path.read_bytes().count(b'copies_file =') == 2
    # Case variants and repeated v1 sections preserve physical last declaration.
    raw = b'[global]\nversion=1\n[volume.Copy]\ncopies_file=missing.csv\n[Volume.COPY]\nCoPiEs_FiLe=copies.csv\n'
    path = source / 'case-sections.ini'
    path.write_bytes(raw)
    materialize_geometry_file(path, source_base=source, destination=root/'legacy-case-sections')
    assert b'copies_file=missing.csv\n[Volume.COPY]\nCoPiEs_FiLe=' in path.read_bytes()
    assert next((root/'legacy-case-sections').iterdir()).read_bytes() == content
    # Strict v2 and the version declaration itself retain their original guards.
    for index, raw in enumerate((
            b'[global]\nversion=2\n[volume.Copy]\ncopies_file=copies.csv\ncopies_file=copies.csv\n',
            b'[global]\nversion=2\n[volume.Copy]\ncopies_file=copies.csv\n[volume.Copy]\nsize=1 mm,1 mm,1 mm\n',
            b'[global]\nversion=1\nversion=1\n[volume.Copy]\ncopies_file=copies.csv\n')):
        path = source / f'strict-{index}.ini'
        path.write_bytes(raw)
        destination = root / f'strict-destination-{index}'
        assert_rejected(lambda: materialize_geometry_file(path,source_base=source,destination=destination), 'duplicate')
        assert path.read_bytes() == raw
        assert not destination.exists()
    # Exercise the actual source-copy package path, not just a scanner unit.
    path = source / 'source-copy.ini'
    raw = b'[world]\nshape=box\nsize=10 mm,10 mm,10 mm\nmaterial=G4_AIR\n[volume.Copy]\nparent=world\nshape=box\nsize=1 mm,1 mm,1 mm\nmaterial=G4_AIR\nplacement=parameterised\ncopies_file=copies.csv\ncopies_file=copies.csv\n'
    path.write_bytes(raw)
    project = G4USimProject(executable=sys.executable,workspaceRoot=str(source),runsRoot=str(root/'legacy-source-copy-runs'))
    project.pathSettings = PathSettings(executable=sys.executable,workspace_root=str(source),runs_root=project.runsRoot)
    apply_to_project(project,blank_result())
    project.geometrySettings.config_path = project.pathSettings.geometry_config = str(path)
    project.geometryEditor = geometry_document_from_summary(parse_geometry_text(raw.decode(),source_path=path,template_name='hierarchical'))
    project.geometryEditor.source_copy_mode = True
    package, _ = create_run_package(project=project,paths=project.pathSettings,run=project.runSettings,geometry=project.geometrySettings,
        source=project.sourceSettings,physics=project.physicsSettings,scoring=project.scoringSettings,
        material_document=project.materialEditor,geometry_document=project.geometryEditor,
        source_model=project.sourceEditor,physics_model=project.physicsEditor,scoring_model=project.scoringEditor)
    targets = list((Path(package.config_dir)/'geometry-resources').iterdir())
    assert len(targets) == 1 and targets[0].read_bytes() == content
    assert path.read_bytes() == raw
    generated = Path(package.geometry_ini_path).read_bytes()
    assert generated.count(b'copies_file=') == 2 and b'copies_file=copies.csv\n' in generated
    assert str(targets[0].resolve()).replace('\\','/').encode() in generated


def snapshot_geometry_property_cases(root):
    package = root / 'resource-property-package'
    package.mkdir()
    main = package/'geometry.ini'
    main.write_text('[world]\n',encoding='utf-8')
    stl = package/'part.stl'
    stl.write_bytes(b'STL byte identity fixture; no physical validation\n')
    table = package/'copies.csv'
    table.write_bytes(b'x_mm,y_mm,z_mm\n0,0,0\n')
    def summary(current,legacy,shape='tessellated'):
        return SimpleNamespace(template_hint='hierarchical',volumes=[SimpleNamespace(name='Part',shape=shape,shape_properties=current,preview_properties=legacy)])
    for current,legacy in (({'file':'part.stl'},{}),({}, {'file':'part.stl'}),({'file':'part.stl'},{'file':'part.stl'})):
        inputs = _geometry_resources(summary(current,legacy),main,package)
        assert len(inputs) == 1 and inputs[0].role == 'geometry.Part.file'
        assert inputs[0].sha256 == hashlib.sha256(stl.read_bytes()).hexdigest()
    assert_rejected(lambda: _geometry_resources(summary({'file':'part.stl'},{'file':'other.stl'}),main,package),'Conflicting geometry resource')
    assert_rejected(lambda: _geometry_resources(summary({},{}),main,package),'Missing geometry resource declaration')
    missing = package/'not-found.stl'
    assert_rejected(lambda: _geometry_resources(summary({'file':str(missing)},{}),main,package),'resource is missing')
    external = root/'external.stl'
    external.write_bytes(b'outside accepted package root')
    for current,legacy in (({'file':str(external)},{}),({}, {'file':str(external)})):
        assert_rejected(lambda: _geometry_resources(summary(current,legacy),main,package),'escapes through a symbolic link')
    inputs = _geometry_resources(summary({'copies_file':'copies.csv'},{'placement':'parameterised'},shape='box'),main,package)
    assert len(inputs) == 1 and inputs[0].role == 'geometry.Part.copies_file'
    assert inputs[0].sha256 == hashlib.sha256(table.read_bytes()).hexdigest()
    assert _geometry_resources(summary({},{'placement':'parameterised','copies':'2','copy_step':'1 mm,0 mm,0 mm'},shape='box'),main,package) == []
    assert_rejected(lambda: _geometry_resources(summary({'copies_file':'copies.csv'},{'placement':'parameterised','copies_file':'other.csv'},shape='box'),main,package),'Conflicting geometry resource')


def parameterised_alias_package_cases(package, table, content, root):
    """Both backend spellings must enforce the actual CURRENT package closure."""
    geometry = Path(package.geometry_ini_path)
    original = geometry.read_bytes()
    assert b'parameterised' in original
    internal_path = table.resolve().as_posix().encode()
    assert internal_path in original
    outside = root / 'alias-outside-copies.csv'
    outside.write_bytes(content)
    hidden = table.with_name(table.name+'.alias-offline')
    try:
        for alias in ('parameterised', 'parameterized'):
            current = original.replace(b'parameterised',alias.encode())
            geometry.write_bytes(current)
            restored = load_project_snapshot(package.project_snapshot_path)
            evidence = [item for item in restored.inputs if item.role == 'geometry.part.copies_file']
            assert len(evidence) == 1
            assert Path(evidence[0].path).resolve() == table.resolve()
            assert evidence[0].sha256 == hashlib.sha256(content).hexdigest()
            assert geometry.read_bytes() == current
            table.rename(hidden)
            try:
                assert_rejected(lambda: load_project_snapshot(package.project_snapshot_path),'resource is missing')
                assert geometry.read_bytes() == current
            finally:
                hidden.rename(table)
            geometry.write_bytes(current.replace(internal_path,outside.resolve().as_posix().encode()))
            assert_rejected(lambda: load_project_snapshot(package.project_snapshot_path),'escapes through a symbolic link')
            assert outside.read_bytes() == content
    finally:
        if hidden.exists():
            hidden.rename(table)
        geometry.write_bytes(original)
    assert geometry.read_bytes() == original and table.read_bytes() == content


def main():
    with tempfile.TemporaryDirectory(prefix='j2-resource-') as tmp:
        root = Path(tmp).resolve()
        original = root / 'original'
        original.mkdir()
        spectrum = original / 'spectrum.csv'
        raw = b'e_low_MeV,e_high_MeV,weight\n1,2,1\n2,3,1\n'
        spectrum.write_bytes(raw)
        project = G4USimProject(executable=sys.executable, workspaceRoot=str(original), runsRoot=str(root/'runs'))
        project.pathSettings = PathSettings(executable=sys.executable, workspace_root=str(original), runs_root=project.runsRoot)
        apply_to_project(project, blank_result())
        project.sourceEditor.gps_sources = [GPSDefinition(energy_type='histogram', spectrum_file='spectrum.csv')]
        before = copy.deepcopy(project)
        closed = collect_bundle_resources(WorkspaceSnapshot(project))
        assert any(r['role'] == 'spectrum' for r in closed['resources'])
        bundle = root / 'portable'
        export_bundle(WorkspaceSnapshot(project), bundle)
        # The original document remains byte-for-byte equivalent as data.
        assert project == before
        spectrum.unlink()
        loaded = load_bundle(bundle, executable=sys.executable).project
        relocated = Path(loaded.sourceEditor.gps_sources[0].spectrum_file)
        assert relocated.is_relative_to(bundle) and relocated.read_bytes() == raw
        loaded.pathSettings.runs_root = str(root / 'replayed')
        package, _ = create_run_package(project=loaded, paths=loaded.pathSettings, run=loaded.runSettings,
            geometry=loaded.geometrySettings, source=loaded.sourceSettings, physics=loaded.physicsSettings,
            scoring=loaded.scoringSettings, material_document=loaded.materialEditor,
            geometry_document=loaded.geometryEditor, source_model=loaded.sourceEditor,
            physics_model=loaded.physicsEditor, scoring_model=loaded.scoringEditor)
        main_ini = Path(package.main_ini_path).read_text(encoding='utf-8')
        assert 'original' not in main_ini
        copies = list((Path(package.config_dir) / 'resources').iterdir())
        assert len(copies) == 1 and copies[0].read_bytes() == raw
        # Map resources use the same explicit closure, not filename heuristics.
        map_file = original / 'field.csv'
        map_file.write_text('field map fixture', encoding='utf-8')
        project.sourceEditor.gps_sources = []
        project.physicsEditor.fields = [FieldDefinition(magnetic='', magnetic_map=str(map_file))]
        projected = collect_bundle_resources(WorkspaceSnapshot(project))
        assert any(r['role'] == 'field_map' for r in projected['resources'])
        src, physics = materialize_run_resources(project.sourceEditor, project.physicsEditor,
            workspace=original, destination=root/'maps')
        assert Path(physics.fields[0].magnetic_map).read_bytes() == map_file.read_bytes()
        assert project.physicsEditor.fields[0].magnetic_map == str(map_file)
        phases = [original / 'phase-a.csv', original / 'phase-b.csv']
        for index, phase in enumerate(phases):
            phase.write_bytes(f'phase-space copy fixture {index}\n'.encode())
        project.physicsEditor.fields = []
        project.sourceEditor.phase_space_file = ','.join(p.name for p in phases)
        phase_bundle = root / 'phase-portable'
        export_bundle(WorkspaceSnapshot(project), phase_bundle)
        for phase in phases:
            phase.unlink()
        replay = load_bundle(phase_bundle, executable=sys.executable).project
        moved = replay.sourceEditor.phase_space_file.split(',')
        assert len(moved) == 2
        assert all(Path(path).is_relative_to(phase_bundle) for path in moved)
        src, physics = materialize_run_resources(replay.sourceEditor, replay.physicsEditor,
            workspace=original, destination=root/'phase-copies')
        copied = src.phase_space_file.split(',')
        assert len(copied) == 2 and copied != moved
        assert [Path(p).read_bytes() for p in copied] == [f'phase-space copy fixture {i}\n'.encode() for i in range(2)]
        for kind in ('stl', 'copies'):
            resource = original / ('part.stl' if kind == 'stl' else 'copies.csv')
            content = (b'solid path_copy_fixture\nendsolid path_copy_fixture\n' if kind == 'stl'
                       else b'x_mm,y_mm,z_mm\n0,0,0\n2,0,0\n')
            resource.write_bytes(content)
            body = ('shape=tessellated\nfile=part.stl\nfile_unit=mm' if kind == 'stl' else
                    'shape=box\nsize=1 mm,1 mm,1 mm\nplacement=parameterised\ncopies_file=copies.csv')
            text = '[global]\nversion=2\n[world]\nshape=box\nsize=10 mm,10 mm,10 mm\nmaterial=G4_AIR\n[volume.part]\nparent=world\nmaterial=G4_AIR\n'+body+'\n'
            input_file = original / (kind+'.ini')
            input_file.write_text(text, encoding='utf-8')
            wizard_project = copy.deepcopy(project)
            apply_to_project(wizard_project, blank_result())
            doc = geometry_document_from_summary(parse_geometry_text(text, source_path=input_file, template_name='hierarchical'))
            doc.is_dirty = True
            wizard_project.geometryEditor = doc
            wizard_project.geometrySettings.config_path = str(input_file)
            wizard_project.pathSettings.geometry_config = str(input_file)
            wizard_project.pathSettings.runs_root = str(root / ('geometry-runs-'+kind))
            before_geometry = copy.deepcopy(doc)
            arguments = dict(project=wizard_project, paths=wizard_project.pathSettings, run=wizard_project.runSettings,
                geometry=wizard_project.geometrySettings, source=wizard_project.sourceSettings, physics=wizard_project.physicsSettings,
                scoring=wizard_project.scoringSettings, material_document=wizard_project.materialEditor,
                geometry_document=doc, source_model=wizard_project.sourceEditor, physics_model=wizard_project.physicsEditor,
                scoring_model=wizard_project.scoringEditor)
            generated, _ = create_run_package(**arguments)
            assert doc.source_path == before_geometry.source_path and doc.raw_source_text == before_geometry.raw_source_text
            assert doc.volumes[1].shape_properties == before_geometry.volumes[1].shape_properties
            assert doc.volumes[1].preview_properties == before_geometry.volumes[1].preview_properties
            assert input_file.read_text(encoding='utf-8') == text and resource.read_bytes() == content
            copies = list((Path(generated.config_dir) / 'geometry-resources').iterdir())
            assert len(copies) == 1 and copies[0].read_bytes() == content
            generated_text = Path(generated.geometry_ini_path).read_text(encoding='utf-8')
            assert str(copies[0]).replace('\\','/') in generated_text
            assert str(resource).replace('\\','/') not in generated_text
            # CURRENT snapshot reads the actual copied STL/table and registers
            # its hash. Missing each kind must refuse the whole package load.
            restored = load_project_snapshot(generated.project_snapshot_path)
            role = 'geometry.part.file' if kind == 'stl' else 'geometry.part.copies_file'
            evidence = [item for item in restored.inputs if item.role == role]
            assert len(evidence) == 1
            assert evidence[0].sha256 == hashlib.sha256(content).hexdigest()
            hidden = copies[0].with_name(copies[0].name+'.offline')
            copies[0].rename(hidden)
            try:
                assert_rejected(lambda: load_project_snapshot(generated.project_snapshot_path),'resource is missing')
            finally:
                hidden.rename(copies[0])
            if kind == 'copies':
                parameterised_alias_package_cases(generated,copies[0],content,root)
            geometry_bundle = root / ('geometry-portable-'+kind)
            export_bundle(WorkspaceSnapshot(wizard_project), geometry_bundle)
            resource.unlink()
            input_file.unlink()
            reopened = load_bundle(geometry_bundle, executable=sys.executable).project
            assert reopened.geometryEditor.volumes[1].shape == ('tessellated' if kind == 'stl' else 'box')
            # Byte closure only: this STL fixture is deliberately not a physical solid.
            assert any(path.read_bytes() == content for path in (geometry_bundle/'resources').iterdir() if path.is_file())
        legacy_geometry_copy_cases(root)
        snapshot_geometry_property_cases(root)
    print('J2 editor resources, missing-original replay inputs, map copying passed')


if __name__ == '__main__':
    main()
