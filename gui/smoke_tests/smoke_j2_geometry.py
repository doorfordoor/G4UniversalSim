"""J2 offline registry driven advanced geometry editing and lossless roundtrip checks.
No Geant4 runtime or physical-validation claim; all widgets run offscreen.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gui'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QLineEdit
from g4usim_gui.core.solid_registry_data import SOLIDS, ALIASES, SOURCE_SHA256, canonical_solid
from g4usim_gui.editors.geometry_editor_model import (
    GeometryDocument, HierarchicalVolumeRow, BooleanOperationRow, LayerRow,
    geometry_document_from_summary, geometry_document_to_snapshot, geometry_document_from_dict,
    validate_geometry_document,
)
from g4usim_gui.parsers.geometry_parser import parse_geometry_text, parse_geometry
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.widgets.config.geometry import GeometryDetailsWidget, GeometryMixin
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage

WORLD='[world]\nshape=box\nsize=2 m,2 m,2 m\nmaterial=G4_AIR\n'
TRD='dx1=10 mm\ndx2=20 mm\ndy1=10 mm\ndy2=20 mm\ndz=30 mm'
TRAP='dz=10 mm\ntheta=0 deg\nphi=0 deg\ndy1=10 mm\ndx1=10 mm\ndx2=10 mm\nalpha1=0 deg\ndy2=10 mm\ndx3=10 mm\ndx4=10 mm\nalpha2=0 deg'
BODIES={
 'box':'size=10 mm,20 mm,30 mm',
 'tubs':'parameters=0 mm,10 mm,20 mm,0 deg,360 deg',
 'sphere':'parameters=0 mm,10 mm,0 deg,360 deg,0 deg,180 deg',
 'orb':'parameters=10 mm',
 'cone':'parameters=0 mm,10 mm,0 mm,20 mm,30 mm,0 deg,360 deg',
 'trd':TRD,'trap':TRAP,
 'ellipsoid':'parameters=30 mm,20 mm,10 mm,-5 mm,8 mm',
 'eltube':'parameters=20 mm,10 mm,15 mm',
 'torus':'parameters=5 mm,10 mm,30 mm,0 deg,360 deg',
 'para':'parameters=10 mm,20 mm,30 mm,20 deg,10 deg,30 deg',
 'hype':'parameters=5 mm,15 mm,0.2 rad,0.3 rad,20 mm',
 'polycone':'parameters=0 deg,360 deg\nz_planes=-10 mm,10 mm\nr_inner=0 mm,0 mm\nr_outer=10 mm,10 mm',
 'polyhedra':'parameters=0 deg,360 deg,6\nz_planes=-10 mm,10 mm\nr_inner=0 mm,0 mm\nr_outer=10 mm,10 mm',
 'tessellated':'file=mesh.stl\nfile_unit=mm',
}


def document(text, source, mode='hierarchical'):
    summary=parse_geometry_text(text, source_path=source, template_name=mode)
    assert not summary.round_trip_blockers, summary.round_trip_blockers
    doc=geometry_document_from_summary(summary,mode)
    validate_geometry_document(doc, material_names={'G4_AIR','G4_WATER'})
    assert not doc.errors, doc.errors
    return doc


def semantics(doc):
    snapshot=geometry_document_to_snapshot(doc)
    for key in ('source_path','is_dirty','source_warnings','source_errors','validation_errors','validation_warnings'):
        snapshot.pop(key,None)
    for collection in ('volumes','boolean_ops'):
        for row in snapshot[collection]:
            row.pop('notes',None)
    snapshot.pop('preview',None)
    return snapshot


def p2_parser_parity(folder: Path) -> None:
    """Permanent controls from the independent r2 backend observations.

    Do not repair input strings: model errors/writer acceptance must follow the
    backend grouping and per-component unit semantics, while raw drafts stay put.
    """
    def model(body: str, world_size='100 mm,100 mm,100 mm'):
        raw = (f'[world]\nshape=box\nsize={world_size}\nmaterial=G4_AIR\n'
               f'[volume.V]\nparent=world\nmaterial=G4_AIR\n{body}\n')
        return geometry_document_from_summary(parse_geometry_text(
            raw, source_path=folder/'p2-source.ini', template_name='hierarchical'), 'hierarchical')
    def check(doc, accepted):
        before = copy.deepcopy(doc.volumes)
        validate_geometry_document(doc, material_names={'G4_AIR'})
        assert bool(doc.errors) is not accepted, doc.errors
        for old, current in zip(before, doc.volumes):
            assert (old.size, old.parameters, old.position, old.rotation) == (current.size, current.parameters, current.position, current.rotation)
        try:
            generated = generate_geometry_ini_text(doc)
        except ValueError:
            assert not accepted, doc.errors
            return ''
        assert accepted, 'backend-invalid draft was emitted'
        return generated
    # Six whitespace tokens become THREE pairs in the backend, not five scalar
    # quantities. A concatenated number/unit stream is one token, not five.
    for text, accepted in (
        ('0 10 20 0 360 deg', False),
        ('0mm10mm20mm0deg360deg', False),
        ('0 mm,10 mm,20 mm,0 deg,360 deg', True),
        ('0 mm 10 mm 20 mm 0 deg 360 deg', True),
        ('0 10 20 0 6.283185307179586', True),
    ):
        doc = model('shape=tubs\nparameters=' + text)
        generated = check(doc, accepted)
        assert doc.volumes[1].parameters == text
        if accepted:
            assert 'parameters = ' + text in generated
    copies = folder/'p2-copies.csv'
    copies.write_text('x_mm,y_mm,z_mm\n0,0,0\n2,0,0\n', encoding='utf-8')
    for position, rotation, accepted in (
        ('', '', True),
        (' 0 mm,0 mm,0 mm ', '', False),
        ('', ' 0 deg,0 deg,0 deg ', False),
        (' 0 mm,0 mm,0 mm ', ' 0 deg,0 deg,0 deg ', False),
    ):
        doc = model('shape=box\nsize=1 mm,1 mm,1 mm\nplacement=parameterised\ncopies_file=' + str(copies))
        row = doc.volumes[1]
        row.position, row.rotation = position, rotation
        check(doc, accepted)
        assert row.position == position and row.rotation == rotation
        if not accepted:
            from g4usim_gui.core.diagnostics import collect_diagnostics
            locations = [d.location.field for d in collect_diagnostics(doc) if d.location]
            assert ('position' in locations) if position else ('rotation' in locations)
    # Bare comma components remain mm; the final cm applies only to its own
    # component. The sketch helper's tail-unit propagation is irrelevant here.
    replica = ('shape=box\nsize=1 mm,1 mm,1 cm\nplacement=replica\n'
               'replica_axis=z\nreplica_count=2\nreplica_width=1 cm')
    for size in ('1,1,2 cm', '1 mm,1 mm,20 mm', '1 mm 1 mm 2 cm'):
        doc = model(replica, size)
        generated = check(doc, True)
        assert 'size = ' + size in generated
        assert doc.volumes[0].size == size
    wrong = model(replica.replace('1 mm,1 mm,1 cm', '10 mm,10 mm,1 cm'), '1,1,2 cm')
    check(wrong, False)
    assert any('Replica dimensions' in message for message in wrong.errors)
    # Delimiter ambiguity must also block a box before it reaches ParseLength.
    check(model('shape=box\nsize=1mm1mm20mm'), False)

def run():
    app=QApplication.instance() or QApplication([])
    for source_name, expected_digest in SOURCE_SHA256.items():
        assert hashlib.sha256((ROOT / source_name).read_bytes()).hexdigest()==expected_digest
    with tempfile.TemporaryDirectory(prefix='g4usim-j2-geometry-') as temporary:
        folder=Path(temporary)
        p2_parser_parity(folder)
        source=folder/'geometry.ini'
        (folder/'copies.csv').write_text('x_mm,y_mm,z_mm,material\n0,0,0,G4_AIR\n2,0,0,G4_WATER\n',encoding='utf-8')
        (folder/'mesh.stl').write_text('solid placeholder\nendsolid placeholder\n',encoding='utf-8')
        assert set(BODIES) == set(SOLIDS)
        text=WORLD
        for name, body in BODIES.items():
            text+=f'\n[volume.{name}]\nparent=world\nshape={name}\n{body}\nmaterial=G4_WATER\nsensitive=true\nregion=R_{name}\nvis.color=blue\nvis.alpha=0.4\nvis.visible=true\nvis.wireframe=false\ncut.gamma=0.2 mm\n'
        for index,name in enumerate(name for name,entry in SOLIDS.items() if entry['boolean_tool']):
            text+=f'\n[volume.box.boolean.{index}]\noperation=subtraction\nshape={name}\n{BODIES[name]}\nname=tool_{name}\n'
        source.write_text(text,encoding='utf-8')
        doc=document(text,source)
        assert len(doc.volumes)==len(SOLIDS)+1
        assert len(doc.boolean_ops)==7
        assert sum(row.sensitive for row in doc.volumes)==15
        generated=generate_geometry_ini_text(doc)
        assert f'file = {(folder / "mesh.stl").resolve()}' in generated
        second=folder/'generated.ini'; second.write_text(generated,encoding='utf-8')
        restored=document(generated,second)
        restored_mesh=next(row for row in restored.volumes if row.shape=='tessellated')
        restored_mesh_path=Path(restored_mesh.shape_properties['file'])
        assert restored_mesh_path.samefile(folder/'mesh.stl')
        assert hashlib.sha256(restored_mesh_path.read_bytes()).hexdigest()==hashlib.sha256((folder/'mesh.stl').read_bytes()).hexdigest()
        assert [r.shape for r in restored.volumes]==[r.shape for r in doc.volumes]
        for left,right in zip(doc.volumes,restored.volumes):
            assert left.sensitive==right.sensitive and left.parent==right.parent
            assert left.visual==right.visual and left.production_cuts==right.production_cuts
            if left.shape!='tessellated': assert left.shape_properties==right.shape_properties
        for left,right in zip(doc.boolean_ops,restored.boolean_ops):
            assert left.shape_properties==right.shape_properties and left.tool_shape==right.tool_shape
        short_ellipsoid=copy.deepcopy(doc)
        next(r for r in short_ellipsoid.volumes if r.shape=='ellipsoid').parameters='30 mm,20 mm,10 mm'
        assert 'parameters = 30 mm,20 mm,10 mm' in generate_geometry_ini_text(short_ellipsoid)
        loaded=geometry_document_from_dict(geometry_document_to_snapshot(doc))
        assert semantics(loaded)==semantics(doc)
        for alias,name in ALIASES.items():
            assert canonical_solid(alias)==name
        # Old preview-only fields migrate to editable properties without inventing values.
        legacy=geometry_document_to_snapshot(doc)
        row=next(r for r in legacy['volumes'] if r['shape']=='polycone')
        row['preview_properties'].update(row['shape_properties'])
        row['shape_properties']={}
        legacy.pop('preview')
        migrated=geometry_document_from_dict(legacy)
        assert next(r for r in migrated.volumes if r.shape=='polycone').shape_properties['z_planes']=='-10 mm,10 mm'
        # Unknown input and unsupported assembly never become silently writable.
        for bad in ('unknown_key=123','vis.unknown=123','cut.unknown=123'):
            parsed=parse_geometry_text(WORLD+'\n[volume.bad]\nshape=box\nsize=1 mm,1 mm,1 mm\nmaterial=G4_AIR\n'+bad,source_path=source,template_name='hierarchical')
            assert parsed.round_trip_blockers, bad
        for body in ('shape=box\nsize=1 mm,1 mm,1 mm\nplacement=assembly',
                     'shape=trap\n'+TRAP.replace('dz=10 mm','dz=nan mm'),
                     'shape=polycone\n'+BODIES['polycone'].replace('r_inner=0 mm,0 mm','r_inner=0 mm')):
            bad=geometry_document_from_summary(parse_geometry_text(WORLD+'\n[volume.bad]\nparent=world\nmaterial=G4_AIR\n'+body,source_path=source,template_name='hierarchical'),'hierarchical')
            validate_geometry_document(bad,material_names={'G4_AIR'})
            assert bad.errors, body
            try: generate_geometry_ini_text(bad)
            except ValueError: pass
            else: assert False,'invalid geometry was generated'
        for name, body in {
            'replica':'shape=box\nsize=10 mm,10 mm,1 mm\nplacement=replica\nreplica_axis=z\nreplica_count=10\nreplica_width=1 mm',
            'parameterised':'shape=box\nsize=1 mm,1 mm,1 mm\nplacement=parameterised\ncopies=3\ncopy_step=2 mm,0 mm,0 mm',
            'table':'shape=box\nsize=1 mm,1 mm,1 mm\nplacement=parameterised\ncopies_file=copies.csv',
        }.items():
            pdoc=document((WORLD.replace('2 m,2 m,2 m','10 mm,10 mm,10 mm') if name=='replica' else WORLD)+'\n[volume.copies]\nparent=world\nmaterial=G4_AIR\n'+body,source)
            roundtrip=document(generate_geometry_ini_text(pdoc),folder/f'{name}.ini')
            for key,value in pdoc.volumes[1].preview_properties.items():
                if key!='copies_file': assert roundtrip.volumes[1].preview_properties[key]==value
        # Selected entity details retain invalid raw values and never touch siblings.
        details=GeometryDetailsWidget('volume')
        selected=copy.deepcopy(next(r for r in doc.volumes if r.shape=='trap'))
        details.set_row(selected)
        details.fields['prop.theta'].setText(' 3 deg ')
        details.fields['vis.alpha'].setText(' nan ')
        details.fields['cut.gamma'].setText(' 0.3 mm ')
        details.apply_row(selected)
        assert selected.shape_properties['theta']==' 3 deg '
        assert selected.visual['vis.alpha']==' nan '
        assert selected.production_cuts['cut.gamma']==' 0.3 mm '
        details.fields['vis.alpha'].setText('   '); details.apply_row(selected)
        assert selected.visual['vis.alpha']=='   '
        details.fields['vis.alpha'].setText(' nan '); details.apply_row(selected)
        isolated=copy.deepcopy(doc); index=next(i for i,r in enumerate(isolated.volumes) if r.shape=='trap')
        isolated.volumes[index]=selected
        validate_geometry_document(isolated,material_names={'G4_AIR','G4_WATER'})
        assert any('vis.alpha' in e for e in isolated.errors)
        assert next(r for r in doc.volumes if r.shape=='trap').visual['vis.alpha']=='0.4'
        # Revert/Reload with no source must not delete the in-memory model.
        page=ConfigBuilderPage()
        page.geometry_document=copy.deepcopy(doc)
        page.geometry_document.source_path=''
        page.geometry_config.setText('')
        before=geometry_document_to_snapshot(page.geometry_document)
        page.seed.setText('  invalid-seed  ')
        page.volume_details.fields['parameters'].setText('  invalid-parameters  ')
        page.revert_geometry_button.click()
        assert geometry_document_to_snapshot(page.geometry_document)==before
        assert page.seed.text()=='  invalid-seed  '
        assert page.volume_details.fields['parameters'].text()=='  invalid-parameters  '
        assert page.geometry_document.source_path=='' and page.geometry_summary is None
        page.reload_geometry_button.click()
        assert geometry_document_to_snapshot(page.geometry_document)==before
        assert page.seed.text()=='  invalid-seed  '
        # A missing imported source remains an error and preserves current rows/drafts.
        page.geometry_document.source_path=str(source)
        page.geometry_config.setText(str(folder/'missing.ini'))
        before_names=[r.name for r in page.geometry_document.volumes]
        page.reload_geometry()
        assert [r.name for r in page.geometry_document.volumes]==before_names
        assert page.geometry_document.source_path==str(source)
        assert page.geometry_document.source_errors
        assert not getattr(page.geometry_summary,'_f4_read_success',True)
        assert page.seed.text()=='  invalid-seed  '
        assert page.volume_details.fields['parameters'].text()=='  invalid-parameters  '
        try: generate_geometry_ini_text(page.geometry_document)
        except ValueError: pass
        else: assert False,'failed source read was treated as an empty valid source'
        # Explicit import records the canonical source anchor (including Windows 8.3 aliases).
        page.geometry_config.setText(str(source)); page.reload_geometry()
        reloaded_source=Path(page.geometry_document.source_path)
        assert page.geometry_document.source_path==str(source.resolve()), (page.geometry_document.source_path, str(source), str(source.resolve()))
        assert reloaded_source.samefile(source)
        assert hashlib.sha256(reloaded_source.read_bytes()).hexdigest()==hashlib.sha256(source.read_bytes()).hexdigest()
        assert len(page.geometry_document.volumes)==len(doc.volumes)
        assert not page.geometry_document.source_errors
        page.geometry_document=copy.deepcopy(doc)
        page.geometry_config.setText('')
        page._populate_geometry_editor()
        page.geometry_table.selectRow(2)
        selected_index=page.geometry_table.currentRow()
        current=page.geometry_document.volumes[selected_index]
        page.volume_details.fields['vis.alpha'].setText(' 0.7 ')
        page._on_volume_details_changed()
        assert current.visual['vis.alpha']==' 0.7 '
        assert page.geometry_table.currentRow()==selected_index
        # Existing table editing remains the sensitivity/parent authority.
        from PySide6.QtWidgets import QTableWidgetItem
        before_sensitive=sum(r.sensitive for r in page.geometry_document.volumes)
        page.geometry_table.setItem(selected_index,8,QTableWidgetItem('false'))
        assert not current.sensitive
        assert sum(r.sensitive for r in page.geometry_document.volumes)==before_sensitive-1
        page.geometry_table.setItem(selected_index,2,QTableWidgetItem('box'))
        assert current.parent=='box'
        assert next(r for r in page.geometry_document.volumes if r.name=='box').parent=='world'
        page._move_hierarchical_volume(1)
        assert page.geometry_document.volumes[selected_index+1] is current
        assert current.parent=='box' and not current.sensitive
        original=len(page.geometry_document.volumes)
        page._duplicate_hierarchical_volume()
        assert len(page.geometry_document.volumes)==original+1
        # Layer properties use their own selected-row owner, no cross-volume state.
        layer=LayerRow(name='L',visual={'vis.color':'green'},region='R')
        ldetails=GeometryDetailsWidget('layer'); ldetails.set_row(layer)
        ldetails.fields['cut.e-'].setText(' 1 um '); ldetails.apply_row(layer)
        assert layer.production_cuts['cut.e-']==' 1 um '
        ldetails.fields['metadata'].setPlainText('metadata.first = alpha\nmetadata.second = beta')
        ldetails.apply_row(layer)
        assert layer.metadata=='metadata.first = alpha\nmetadata.second = beta'
        # Invalid stale fields and conflicting old/new property projections block.
        conflict=geometry_document_to_snapshot(doc); conflict.pop('preview')
        record=next(r for r in conflict['volumes'] if r['shape']=='polycone')
        record['preview_properties']['z_planes']='0 mm,1 mm'
        try: geometry_document_from_dict(conflict)
        except ValueError: pass
        else: assert False,'conflicting property projections were accepted'
        rejected=copy.deepcopy(doc)
        rejected.boolean_ops[0].tool_shape='torus'
        validate_geometry_document(rejected,material_names={'G4_AIR','G4_WATER'})
        assert rejected.errors
        replica_text=WORLD.replace('2 m,2 m,2 m','10 mm,10 mm,10 mm')+'\n[volume.S]\nparent=world\nmaterial=G4_AIR\nshape=box\nsize=10 mm,10 mm,1 mm\nplacement=replica\nreplica_axis=z\nreplica_count=9\nreplica_width=1 mm'
        rejected=geometry_document_from_summary(parse_geometry_text(replica_text,source_path=source,template_name='hierarchical'),'hierarchical')
        validate_geometry_document(rejected,material_names={'G4_AIR'})
        assert any('Replica dimensions' in message for message in rejected.errors)
        cycle=copy.deepcopy(doc); cycle.volumes[1].parent=cycle.volumes[2].name; cycle.volumes[2].parent=cycle.volumes[1].name
        validate_geometry_document(cycle,material_names={'G4_AIR','G4_WATER'})
        assert cycle.errors

        assert selected.production_cuts['cut.gamma']==' 0.3 mm '
        page.close(); details.close(); ldetails.close()
        page.deleteLater(); details.deleteLater(); ldetails.deleteLater()
        app.processEvents()
    print('J2 advanced geometry: registry/schema, all solids, boolean contracts, placements, vis/cuts, raw details and memory reload PASS')


if __name__=='__main__':
    run()
