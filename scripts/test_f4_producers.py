"""F4 producer targets, old report ordering, and repeat-validation contracts."""
from dataclasses import asdict, fields
import copy
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gui'))
from g4usim_gui.core.config_schema import check_diagnostic, check_value
from g4usim_gui.core.diagnostics import collect_diagnostics, diagnostics_from_dict
from g4usim_gui.editors.source_physics_scoring_model import (
    SourceEditableModel, PhysicsEditableModel, ScoringEditableModel,
    validate_source_model, validate_physics_model, validate_scoring_model,
    source_model_to_snapshot, physics_model_to_snapshot, scoring_model_to_snapshot,
)
from g4usim_gui.models.package_model import PathSettings, GeometrySettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.validators.config_validator import (
    ValidationReport, validate_config_builder, _validate_geometry_text,
    _validate_material_text, _source_field_location, _include_messages,
)
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary, validate_geometry_document
from g4usim_gui.editors.material_editor_model import (
    MaterialDocument, MaterialRow, material_document_from_summary, validate_material_document,
)


def model_cases():
    # Each case exercises a real user input or a preserved preview-only control.
    source = [
        ({'enabled':False}, {'disabled':'enabled'}),
        ({'preset':''}, {'preset.required':'preset'}),
        ({'preset':'custom'}, {'preset.unknown':'preset'}),
        ({'particle':''}, {'particle.required':'particle'}),
        ({'energy':''}, {'energy.required':'energy'}),
        ({'energy':'nan MeV'}, {'energy.invalid':'energy', 'value.nonfinite':'energy'}),
        ({'position_mode':'volume'}, {'position_mode.unsupported':'position_mode'}),
        ({'source_shape':'bad'}, {'shape.unknown':'source_shape', 'shape.ignored':'source_shape'}),
        ({'position':'1,2'}, {'position.components':'position'}),
        ({'position_mode':'plane','source_shape':'circle','radius':'bad'},
         {'radius.invalid':'radius','plane.limited':'normal'}),
        ({'position_mode':'plane','source_shape':'circle','normal':'1,2'},
         {'normal.components':'normal','radius.required':'radius'}),
        ({'position_mode':'plane','source_shape':'annulus','normal':'0,0,0'},
         {'normal.zero':'normal','inner_radius.required':'inner_radius','shape.preview_only':'source_shape'}),
        ({'position_mode':'plane','source_shape':'rectangle'},
         {'halfx.required':'halfx','halfy.required':'halfy'}),
        ({'position_mode':'plane','source_shape':'rectangle','halfx':'-1 mm','halfy':'0 mm','normal':'1,0,0'},
         {'halfx.positive':'halfx','halfy.positive':'halfy','normal.xy_only':'normal'}),
        ({'direction':'1,2'}, {'direction.components':'direction'}),
        ({'direction':'0,0,0'}, {'direction.zero':'direction'}),
        ({'angular_mode':'bad'}, {'angular_mode.unknown':'angular_mode'}),
        ({'theta_min':'bad'}, {'angle.invalid':'theta_min'}),
        ({'angular_mode':'cone','cone_half_angle':''},
         {'cone_half_angle.required':'cone_half_angle','cone.preview_only':'angular_mode'}),
        ({'angular_mode':'cone','cone_half_angle':'bad'}, {'cone_half_angle.invalid':'cone_half_angle'}),
        ({'angular_mode':'focused','focus_point':'1,2'},
         {'angular_mode.preview_only':'angular_mode','focus.components':'focus_point'}),
        ({'preview_ray_count':0}, {'preview_rays.positive':'preview_ray_count'}),
        ({'confine_volume':'Target'}, {'confine.not_generated':'confine_volume'}),
    ]
    physics = [
        ({'mode':'manual'}, {'mode.unsupported':'mode'}),
        ({'reference_list':''}, {'reference.required':'reference_list'}),
        ({'reference_list':'custom'}, {'reference.unknown':'reference_list'}),
        ({'default_cut':''}, {'cut.required':'default_cut'}),
        ({'default_cut':'bad'}, {'cut.invalid':'default_cut'}),
        ({'default_cut':'1'}, {'cut.unit_hint':'default_cut'}),
        ({'enable_biasing_physics':True}, {'biasing.not_editable':'enable_biasing_physics'}),
        ({'extra_modules':['em']}, {'extra_modules.not_editable':'extra_modules'}),
        ({'manual_modules':['em']}, {'manual_modules.not_generated':'manual_modules'}),
    ]
    scoring = [
        ({'hits':False,'event_edep':False,'edep':False},
         {'output.required':'enabled','histogram.edep_disabled':'edep'}),
        ({'hist_bins':0}, {'hist_bins.positive':'hist_bins','hist_value.invalid':'hist_bins'}),
        ({'hist_min':'','hist_max':''}, {'hist_min.required':'hist_min','hist_max.required':'hist_max'}),
        ({'hist_min':'10 MeV','hist_max':'1 MeV'}, {'hist_range.order':'hist_max'}),
        ({'raw_histogram':False,'weighted_histogram':False}, {'histogram.output_required':'raw_histogram'}),
        ({'let':True}, {'let.unsupported':'let'}),
        ({'dose':True,'fluence':True,'auto_create_default_scorers':False},
         {'dose.requires_default':'auto_create_default_scorers','fluence.requires_default':'auto_create_default_scorers'}),
        ({'trajectory_events':-1}, {'trajectories.range':'trajectory_events'}),
        ({'trajectory_events':101}, {'trajectories.size_hint':'trajectory_events'}),
    ]
    for editor, cls, validate, snapshot, cases in (
        ('source',SourceEditableModel,validate_source_model,source_model_to_snapshot,source),
        ('physics',PhysicsEditableModel,validate_physics_model,physics_model_to_snapshot,physics),
        ('scoring',ScoringEditableModel,validate_scoring_model,scoring_model_to_snapshot,scoring),
    ):
        for values, expected in cases:
            model=cls(**values)
            validate(model)
            records=collect_diagnostics(model)
            by_code={d.code:d for d in records}
            for code, field in expected.items():
                item=by_code.get(editor+'.'+code)
                assert item is not None, (editor,values,code,tuple(by_code))
                assert item.location.editor==editor and item.location.field==field
                assert item.source is None and not item.unavailable_reason
            assert [d.message for d in records if d.severity=='error']==model.errors
            assert [d.message for d in records if d.severity=='warning']==model.warnings
            assert all(d.location.field and hasattr(model,d.location.field) for d in records)
            assert len(records)==len({d.identity for d in records})
            before=[d.to_dict() for d in records]
            validate(model)
            assert [d.to_dict() for d in collect_diagnostics(model)]==before
            copied=copy.deepcopy(model)
            validate(copied)
            assert [d.identity for d in collect_diagnostics(copied)]==[d.identity for d in records]
            assert set(snapshot(model))=={f.name for f in fields(model)}
            assert '_f4_diagnostics' not in asdict(model)

    # Dynamic field rules must preserve each distinct same-code occurrence.
    model=SourceEditableModel(theta_min='bad',theta_max='bad',phi_min='bad',phi_max='bad',
                              energy='nan',position='nan,0,0',direction='0,inf,0',
                              radius='inf',halfx='nan',halfy='nan')
    validate_source_model(model)
    records=collect_diagnostics(model)
    assert {d.location.field for d in records if d.code=='source.angle.invalid'}=={'theta_min','theta_max','phi_min','phi_max'}
    assert {d.location.field for d in records if d.code=='source.value.nonfinite'}=={'energy','position','direction','radius','halfx','halfy'}
    model=ScoringEditableModel(hist_bins=-1,hist_min='bad',hist_max='bad',dose=True,fluence=True,
                               auto_create_default_scorers=False)
    validate_scoring_model(model)
    records=collect_diagnostics(model)
    assert {d.location.field for d in records if d.code=='scoring.hist_value.invalid'}=={'hist_bins','hist_min','hist_max'}
    assert len([d for d in records if d.location.field=='auto_create_default_scorers'])==2


def schema_cases():
    for section,key,value,code in (
        ('run','threads','bad','integer'),('run','threads','2147483648','integer_overflow'),
        ('run','threads','0','bounds'),('run','check_overlaps','maybe','boolean'),
        ('source','energy','nan MeV','quantity'),('unknown','key','x','unknown_field'),
        ('run','name','one\ntwo','single_line'),
    ):
        issue=check_diagnostic(section,key,value)
        assert issue is not None and issue.code=='schema.'+code
        assert issue.message==check_value(section,key,value)
        assert dict(issue.identity_parameters)=={'section':section,'key':key,'value':value}
        assert issue.location is None and issue.unavailable_reason=='schema_field_without_editor'
    assert check_diagnostic('run','threads','1') is None and check_value('run','threads','1') is None


def report_cases(work):
    paths=PathSettings()
    run=RunSettings(threads=0,beam_on=-1)
    args=dict(paths=paths,run=run,geometry=GeometrySettings(template=''),source=SourceSettings(),
              physics=PhysicsSettings(),scoring=ScoringSettings())
    report=validate_config_builder(**args)
    assert report.errors==['Executable path is required.','Runs root is required.',
                           'Materials config is required.','Geometry template is required.',
                           'Geometry config is required.','Threads must be a positive integer.',
                           'BeamOn must be >= 0.']
    assert [(d.location.editor,d.location.field) for d in report.diagnostics if d.severity=='error']==[
        ('setup','executable'),('setup','runs_root'),('setup','materials_config'),
        ('setup','geometry_template'),('setup','geometry_config'),('run','threads'),('run','beam_on')]
    assert not any(d.code=='legacy.unstructured' for d in report.diagnostics)
    report.snapshot_id='state-1'
    payload=report.to_dict()
    loaded=diagnostics_from_dict(payload)
    assert loaded.errors==tuple(report.errors) and not loaded.can_run and loaded.snapshot_id=='state-1'
    assert report.to_text()=='\n'.join(['can_run = false','','[errors]',*report.errors,'','[warnings]',
                                      *(report.warnings or ['<none>']),'','[info]',*(report.info or ['<none>'])])
    # Public legacy string append remains readable and explicitly unlocated.
    report.errors.append('legacy opaque error')
    assert report.diagnostics[-1].raw_message=='legacy opaque error'
    assert report.diagnostics[-1].unavailable_reason=='legacy_unstructured'
    assert report.to_dict()['errors'][-1]=='legacy opaque error'

    exe=work/'G4UniversalSim.exe';exe.write_text('test fixture, never executed',encoding='utf-8')
    materials=work/'materials.ini';materials.write_text('[World]\nmaterial=G4_AIR\n[Silicon]\nmaterial=G4_Si\n',encoding='utf-8')
    geometry=work/'geometry.ini';geometry.write_text('[world]\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\n'
        '[target]\nshape=box\nsize=1 cm,1 cm,1 mm\nmaterial=MissingA\nposition=0,0,0 mm\nsensitive=true\n',encoding='utf-8')
    args.update(paths=PathSettings(str(exe),str(work),str(work/'runs'),str(materials),str(geometry)),
                run=RunSettings(seed=2147483648),geometry=GeometrySettings('simple_box',str(geometry)),
                source_model=SourceEditableModel(direction='0,0,0'),
                physics_model=PhysicsEditableModel(reference_list=''),
                scoring_model=ScoringEditableModel(hist_min='1 MeV',hist_max='0 MeV'))
    report=validate_config_builder(**args)
    by_code={d.code:d for d in report.diagnostics}
    assert by_code['config.run.field.invalid'].location.field=='seed'
    for code,prefix in (('source.direction.zero','Source: '),('physics.reference.required','Physics: '),
                        ('scoring.hist_range.order','Scoring: ')):
        assert by_code[code].message.startswith(prefix) and not by_code[code].raw_message.startswith(prefix)
    source=by_code['geometry.material.missing'].source
    assert source.filename==str(geometry.resolve()) and source.line==7
    assert (source.section,source.key,source.value)==('target','material','MissingA')
    assert source.text_snapshot==geometry.read_text(encoding='utf-8')
    assert diagnostics_from_dict(report.to_dict()).errors==tuple(report.errors)
    again=validate_config_builder(**args)
    assert again.to_text()==report.to_text()
    assert [d.identity for d in again.diagnostics]==[d.identity for d in report.diagnostics]


def source_cases(work):
    path=work/'source.ini'
    text=('[world]\nshape=box\n[volume.A]\nshape=tessellated\nplacement=replica\n'
          '[volume.B]\nplacement=assembly\n[volume.B.boolean.0]\nmaterial=G4_Si\n')
    path.write_text(text,encoding='utf-8')
    report=ValidationReport();_validate_geometry_text(path,report)
    by_code={d.code:d for d in report.diagnostics}
    for code,line in (('geometry.shape.not_editable',4),('geometry.placement.not_editable',5),
                      ('geometry.placement.unsupported',7),('geometry.boolean.ignored_field',9)):
        assert by_code[code].source.line==line,(code,by_code[code].source)
        assert by_code[code].source.text_snapshot==text
        assert by_code[code].location is None and by_code[code].unavailable_reason=='source_only'
    path.write_text('[material.A]\ntemperature=300 K\npressure=1 atm\n',encoding='utf-8')
    report=ValidationReport();_validate_material_text(path,report)
    assert {d.source.key:d.source.line for d in report.diagnostics}=={'pressure':3,'temperature':2}
    assert _source_field_location(path,text,key='absent').line is None

    # Source blockers remain typed before and after model validation. Their
    # error-channel display prefix must never become a guessed source position.
    path.write_text('[world]\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\n'
                    '[array]\ncount=2\n',encoding='utf-8')
    document=geometry_document_from_summary(parse_geometry(path,'hierarchical'),'hierarchical')
    assert document.round_trip_blockers
    identities=[]
    for validated in (False,True,True):
        if validated:
            validate_geometry_document(document)
        report=ValidationReport()
        _include_messages(report,document,'round_trip_blockers','errors','Geometry round-trip blocker: ',
                          origin='geometry_document')
        assert report.errors==['Geometry round-trip blocker: '+item for item in document.round_trip_blockers]
        assert all(d.source is not None and d.code!='legacy.unstructured' for d in report.diagnostics)
        assert all(d.source.text_snapshot==path.read_text(encoding='utf-8') for d in report.diagnostics)
        identities.append([d.identity for d in report.diagnostics])
        assert diagnostics_from_dict(report.to_dict()).errors==tuple(report.errors)
    assert identities[0]==identities[1]==identities[2]

    path.write_text('[World]\nmaterial=G4_AIR\ninvalid syntax\n',encoding='utf-8')
    document=material_document_from_summary(parse_materials(path))
    assert document.source_errors
    for _ in range(2):
        validate_material_document(document)
        report=ValidationReport()
        _include_messages(report,document,'errors','errors','Materials Editor: ',origin='material_document')
        syntax=[d for d in report.diagnostics if d.code=='ini.invalid_line']
        assert len(syntax)==1 and syntax[0].source.line==3
        assert syntax[0].source.text_snapshot==path.read_text(encoding='utf-8')
        assert diagnostics_from_dict(report.to_dict()).errors==tuple(report.errors)


def duplicate_row_cases():
    document=MaterialDocument(rows=[
        MaterialRow(name='same',density='bad',components_text='Si:1'),
        MaterialRow(name='same',density='bad',components_text='Si:1'),
    ])
    validate_material_document(document)
    legacy=list(document.errors)
    records=collect_diagnostics(document)
    assert {d.location.row for d in records if d.code=='materials.name.duplicate'}=={0,1}
    report=ValidationReport()
    _include_messages(report,document,'errors','errors','Materials: ',origin='materials')
    assert report.errors==['Materials: '+message for message in legacy]
    assert {d.location.row for d in report.diagnostics if d.code=='materials.name.duplicate'}=={0,1}
    assert {d.location.row for d in report.diagnostics if d.code=='materials.density.numeric'}=={0,1}
    assert not any(d.code=='legacy.unstructured' for d in report.diagnostics)
    payload=report.to_dict()
    loaded=diagnostics_from_dict(payload)
    assert loaded.errors==tuple(report.errors)
    assert {d.location.row for d in loaded.diagnostics if d.code=='materials.name.duplicate'}=={0,1}
    assert len(loaded.diagnostics)>len(loaded.errors)

    # A second display context preserves its original text and typed provenance.
    _include_messages(report,document,'errors','errors','Materials Editor: ',origin='material_document')
    assert report.errors==['Materials: '+message for message in legacy]+['Materials Editor: '+message for message in legacy]
    assert diagnostics_from_dict(report.to_dict()).errors==tuple(report.errors)
    assert len({d.identity for d in report.diagnostics})==len(report.diagnostics)


def main():
    model_cases()
    schema_cases()
    duplicate_row_cases()
    with tempfile.TemporaryDirectory(prefix='g4usim-f4-producers-') as temp:
        work=Path(temp)
        report_cases(work)
        source_cases(work)
    print('F4 source/physics/scoring fields, schema facts, source lines and legacy report contracts passed')


if __name__=='__main__':
    main()
