from pathlib import Path
from dataclasses import replace
import ast,hashlib,importlib,json,sys,tempfile,itertools,copy
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
DRAFT=ROOT/'out/collab/j2-f8-repair-draft'
sys.path.insert(0,str(ROOT/'gui'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((DRAFT/'manifest.json').read_text())
for item in manifest['files']:
    assert sha(ROOT/item['path'])==item['original_raw_sha256']
    assert sha(DRAFT/'files'/item['path'])==item['candidate_sha256']
mat=importlib.import_module('g4usim_gui.editors.material_editor_model')
old_density=mat.density_internal_value
old_acceptance={}
# Original function holds module globals; all density constants must also remain identical AST.
rel='gui/g4usim_gui/editors/material_editor_model.py'
def acceptance_ast(p):
    tree=ast.parse(p.read_text(encoding='utf-8'))
    return [ast.dump(n,include_attributes=False) for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name=='density_internal_value') or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and (t.id.startswith('_CLHEP_') or t.id.startswith('_DENSITY_')) for t in n.targets))]
assert acceptance_ast(ROOT/rel)==acceptance_ast(DRAFT/'files'/rel)
values=[n+s+u for n,s,u in itertools.product(['1','.125','+0x1.8p-2','1e-300','1e283','0','-0','-2','1e309','1e-999','nan','Inf','1e','1_0'],[' ','*',' ** '],['g/cm3','KG/M^3','mg/cm3','G/CM^3','g / cm3','wrong'])]
values += ['0x1p-1074 mg/cm3','0x1p-1075 g/cm3','1e287 g/cm3','-0x1p2000 g/cm3']
for value in values:old_acceptance[value]=old_density(value)
mods={}
for short in ['core.i18n','editors.material_editor_model','editors.source_physics_scoring_model','validators.config_validator']:
    module=importlib.import_module('g4usim_gui.'+short)
    candidate=DRAFT/'files'/Path(module.__file__).relative_to(ROOT)
    exec(compile(candidate.read_text(encoding='utf-8'),str(candidate),'exec'),module.__dict__)
    mods[short]=module
from g4usim_gui.core.diagnostics import collect_diagnostics,Diagnostic,EditorLocation,diagnostics_to_dict,diagnostics_from_dict
from g4usim_gui.core.project import G4USimProject,save_project,load_project
phy=mods['editors.source_physics_scoring_model']; val=mods['validators.config_validator']; i18n=mods['core.i18n']
for value,old in old_acceptance.items():assert mat.density_internal_value(value)==old,value
categories=[('', 'required'),('garbage','numeric'),('nan g/cm3','numeric'),('-inf kg/m3','numeric'),('. kg/m3','numeric'),('-0 * MG/CM^3','positive'),('-0x1p-5 g/cm3','positive'),('1e-999 g/cm3','positive'),('1e287 g/cm3','invalid'),('1e309 mg/cm3','invalid'),('0x1p-1075 g/cm3','positive'),('1 ** g/cm3','invalid'),('1_0 g/cm3','invalid'),('1e g/cm3','invalid'),('1 g / cm3','invalid'),('1e283 kg/m3',None),('0x1p-1074 mg/cm3',None)]
rows=[]
for value,expected in categories:
    doc=mat.MaterialDocument(rows=[mat.MaterialRow(name='Review',density=value,components_text='Si:1')],is_dirty=True)
    mat.validate_material_document(doc)
    records=[r for r in collect_diagnostics(doc) if r.code.startswith('materials.density.')]
    assert [r.code for r in records]==([] if expected is None else ['materials.density.'+expected]),(value,records)
    assert all(r.location==EditorLocation('materials','density','rows',0,'Review') for r in records)
    payload=diagnostics_to_dict(records)
    assert [r.identity for r in diagnostics_from_dict(json.loads(json.dumps(payload))).diagnostics]==[r.identity for r in records]
    rows.append({'value':value,'code':expected})
# All historical actual-runtime acceptance cases, without rewriting old runtime evidence.
runtime=json.loads((ROOT/'out/collab/j2-materials/density-runtime-final/receipt.json').read_text())
for case in runtime['cases']:
    assert (mat.density_internal_value(case['density']) is not None)==case['valid'],case
# Preserve M01/M02 permanent targeted density and material model checks (no Qt subsection).
ns={'__file__':str(ROOT/'gui/smoke_tests/smoke_j2_materials.py'),'__name__':'review_materials'}
exec(compile(Path(ns['__file__']).read_text(encoding='utf-8'),ns['__file__'],'exec'),ns)
with tempfile.TemporaryDirectory(prefix='material-',dir=OUT) as tmp:
    ns['density_checks'](Path(tmp)); ns['model_checks'](Path(tmp))
physics=[]
for mode in ['unknown','', 'Manual','reference_typo','手动']:
    model=phy.PhysicsEditableModel(mode=mode)
    phy.validate_physics_model(model)
    records=[r for r in collect_diagnostics(model) if r.location and r.location.field=='mode']
    assert len(records)==1 and records[0].code=='physics.mode.unsupported',records
    p=diagnostics_to_dict(records)
    assert diagnostics_from_dict(json.loads(json.dumps(p))).diagnostics[0].identity==records[0].identity
    with tempfile.TemporaryDirectory(prefix='project-',dir=OUT) as tmp:
        path=Path(tmp)/'project.json'; save_project(G4USimProject(physicsEditor=model),path)
        restored=load_project(path).physicsEditor
        assert restored.mode==mode,(mode,restored.mode)
        phy.validate_physics_model(restored)
        assert next(r for r in collect_diagnostics(restored) if r.location.field=='mode').identity==records[0].identity
    physics.append(mode)
# Legacy same-code record and identity remain readable; never rewrite history to regenerated identity.
legacy=Diagnostic('physics.mode.unsupported','error','physics.editor','manual physics mode is not generated by this GUI MVP',location=EditorLocation('physics','mode'),identity_parameters={'value':'unknown'})
p=diagnostics_to_dict([legacy]); assert diagnostics_from_dict(p).diagnostics[0].identity==legacy.identity
forged=copy.deepcopy(p); forged['diagnostics'][0]['code']='physics.structured.invalid'
try: diagnostics_from_dict(forged)
except ValueError: pass
else: assert False,'tampered identity accepted'
# Code decision must use supplied machine path; display deliberately lies about it.
orig_problem=importlib.import_module('g4usim_gui.core.run_editor_model').problem
runmodel=importlib.import_module('g4usim_gui.core.run_editor_model')
runmodel.problem=lambda path,reason:'unrelated translated display physics.mode / manual_modules'
for path,expected,field in [('physics.mode','physics.mode.unsupported','mode'),('physics.manual_modules','physics.structured.invalid','manual_modules'),('physics.extra_modules','physics.structured.invalid','extra_modules')]:
    model=phy.PhysicsEditableModel(); phy._record_structured(model,'physics',path,'misleading physics.mode prose')
    record=collect_diagnostics(model)[0]
    assert record.code==expected and record.location.field==field,(path,record)
runmodel.problem=orig_problem
manual=phy.PhysicsEditableModel(mode='manual'); phy.validate_physics_model(manual)
assert any(r.code=='physics.structured.invalid' and r.location.field=='manual_modules' for r in collect_diagnostics(manual))
manual.manual_modules=['G4EmStandardPhysics']; phy.validate_physics_model(manual); assert not manual.errors
# Source and experimental codes/line anchors unaffected by translations, and old non-editable codes disappear only for their two cases.
with tempfile.TemporaryDirectory(prefix='geometry-',dir=OUT) as tmp:
    path=Path(tmp)/'geometry.ini'
    path.write_text('[volume.A]\nshape = stl\nplacement=parameterized\n[volume.B]\nplacement=assembly\n')
    reports=[]
    for translate in [lambda s:i18n.ui_text(s,language='en'),lambda s:i18n.ui_text(s,language='zh_CN'),lambda s:'任意展示文案']:
        val.ui_text=translate; report=val.ValidationReport(); val._validate_geometry_text(path,report); reports.append(report)
        codes={r.code:r for r in report.diagnostics}
        assert codes['geometry.shape.experimental'].source.line==2
        assert codes['geometry.placement.experimental'].source.line==3
        assert codes['geometry.placement.unsupported'].source.line==5
        assert not report.can_run
        assert not any(r.code.endswith('.not_editable') for r in report.diagnostics)
        payload=diagnostics_to_dict(report.diagnostics)
        assert [r.identity for r in diagnostics_from_dict(payload).diagnostics]==[r.identity for r in report.diagnostics]
    assert [r.identity for r in reports[0].diagnostics]==[r.identity for r in reports[1].diagnostics]==[r.identity for r in reports[2].diagnostics]
    assert reports[0].diagnostics[0].message!=reports[1].diagnostics[0].message
for item in manifest['files']:assert sha(ROOT/item['path'])==item['original_raw_sha256']
result={'passed':True,'scope':'independent out-only candidate loading, no QApplication/render/backend; not new runtime evidence','density_acceptance_function_and_constants_ast_identical':True,'acceptance_comparisons':len(values),'density_categories':rows,'historical_actual_runtime_cases_reconciled':len(runtime['cases']),'targeted_permanent_material_checks':'density_checks and model_checks PASS (M01/M02)','unknown_mode_project_and_json_roundtrip':physics,'legacy_identity_reader_preserved':True,'tampered_identity_rejected':True,'machine_path_with_deceptive_display':'PASS three branches','geometry_en_zh_arbitrary_display_identity':'PASS','tracked_four_files_unchanged':True,'draft_manifest_sha256':sha(DRAFT/'manifest.json'),'product_patch_sha256':sha(DRAFT/'product.patch')}
(OUT/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
