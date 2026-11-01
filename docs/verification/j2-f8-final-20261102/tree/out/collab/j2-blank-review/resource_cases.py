from pathlib import Path
import os,sys,tempfile,json,hashlib,copy,traceback,shutil,subprocess,runpy
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'resources-round';OUT.mkdir(exist_ok=True)
WORK=OUT/('runtime-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'));WORK.mkdir();tempfile.tempdir=str(WORK)
sys.path.insert(0,str(ROOT/'gui'))
FILES=['gui/g4usim_gui/core/run_editor_resources.py','gui/g4usim_gui/core/run_editor_model.py','gui/g4usim_gui/core/experiment_bundle.py','gui/g4usim_gui/core/edit_snapshot.py','gui/g4usim_gui/editors/source_physics_scoring_model.py','gui/g4usim_gui/editors/geometry_editor_model.py','gui/g4usim_gui/writers/package_writer.py','gui/g4usim_gui/writers/main_ini_writer.py','scripts/test_j2_resource_bundle.py']
def hashes():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}
start=hashes()
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.wizard import blank_result,apply_to_project
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot,snapshot_fingerprint
from g4usim_gui.core.experiment_bundle import export_bundle,load_bundle,collect_bundle_resources
from g4usim_gui.core import experiment_bundle as eb
from g4usim_gui.core.run_editor_model import GPSDefinition,FieldDefinition
from g4usim_gui.core.run_editor_resources import materialize_run_resources
from g4usim_gui.core.experiment_workflow import _field_report
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.writers.package_writer import create_run_package
from g4usim_gui.editors.source_physics_scoring_model import validate_source_model
results=[]
def case(name,fn):
    before=hashes()
    try:r={'case':name,'status':'observed','detail':fn()}
    except Exception as e:r={'case':name,'status':'execution_failure','error':type(e).__name__+': '+str(e),'traceback':traceback.format_exc()}
    r['selected_source_unchanged']=before==hashes();results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
def project(name):
    path=WORK/name;path.mkdir();original=path/'original';original.mkdir()
    p=G4USimProject(executable=sys.executable,workspaceRoot=str(original),runsRoot=str(path/'runs'))
    p.pathSettings=PathSettings(executable=sys.executable,workspace_root=str(original),runs_root=p.runsRoot)
    apply_to_project(p,blank_result(name));return p,path,original
SPEC=b'e_low_MeV,e_high_MeV,weight\n1,2,1\n2,3,2\n'
POINTS=b'energy_MeV,weight\n1,1\n2,2\n'
PHASE=b'runID,eventID,particle,energy_MeV,x_mm,y_mm,z_mm,dx,dy,dz,weight\n0,0,gamma,1,0,0,0,0,0,1,1\n'
MAP=b'x_mm,y_mm,z_mm,Bx_T,By_T,Bz_T\n0,0,0,0,0,1\n'
EMAP=b'x_mm,y_mm,z_mm,Ex_V_per_m,Ey_V_per_m,Ez_V_per_m\n0,0,0,0,0,1\n'
def package(p):return create_run_package(project=p,paths=p.pathSettings,run=p.runSettings,geometry=p.geometrySettings,source=p.sourceSettings,physics=p.physicsSettings,scoring=p.scoringSettings,material_document=p.materialEditor,geometry_document=p.geometryEditor,source_model=p.sourceEditor,physics_model=p.physicsEditor,scoring_model=p.scoringEditor)[0]
def paths(p):
    a=[]
    if p.sourceEditor.phase_space_file:a+=p.sourceEditor.phase_space_file.split(',')
    a += [x.spectrum_file for x in p.sourceEditor.gps_sources if x.spectrum_file]
    a += [getattr(x,k) for x in p.physicsEditor.fields for k in ('magnetic_map','electric_map') if getattr(x,k)]
    return a

def provided():
    runpy.run_path(str(ROOT/'scripts/test_j2_resource_bundle.py'),run_name='__main__');return {'independently_executed':True}

def portable(kind):
    p,base,orig=project('portable-'+kind)
    resources={'magnetic.csv':MAP,'electric.csv':EMAP}
    p.physicsEditor.fields=[FieldDefinition(magnetic='',magnetic_map='magnetic.csv',electric_map='electric.csv')]
    if kind=='gps':
        resources.update({'hist.csv':SPEC,'points.csv':POINTS})
        p.sourceEditor.gps_sources=[GPSDefinition(name='hist',energy_type='histogram',spectrum_file='hist.csv'),GPSDefinition(name='points',energy_type='points',spectrum_file='points.csv')]
    else:
        resources['phase.csv']=PHASE;p.sourceEditor.phase_space_file='phase.csv'
    for name,raw in resources.items():(orig/name).write_bytes(raw)
    snap=WorkspaceSnapshot(p);before=snapshot_fingerprint(snap)
    bundle=base/'bundle';export_bundle(snap,bundle)
    assert snapshot_fingerprint(snap)==before
    for name in resources:(orig/name).unlink()
    moved=base/'moved-中文 bundle';assert bundle.resolve().is_relative_to(OUT.resolve()) and moved.resolve().is_relative_to(OUT.resolve());shutil.move(str(bundle),str(moved))
    loaded=load_bundle(moved,executable=sys.executable);refs=paths(loaded.project)
    assert all(Path(x).is_relative_to(moved) and Path(x).is_file() for x in refs)
    assert {Path(x).read_bytes() for x in refs}==set(resources.values())
    loaded.project.pathSettings.runs_root=loaded.project.runsRoot=str(base/'replayed-runs')
    elsewhere=base/'elsewhere';elsewhere.mkdir();cwd=Path.cwd();os.chdir(elsewhere)
    try:pkg=package(loaded.project)
    finally:os.chdir(cwd)
    copies=list((Path(pkg.config_dir)/'resources').iterdir());assert {x.read_bytes() for x in copies}==set(resources.values())
    main=Path(pkg.main_ini_path).read_text(encoding='utf-8');assert str(orig) not in main and str(bundle) not in main
    return {'deleted_original_resources':len(resources),'moved_bundle':str(moved),'all_snapshot_paths_inside_moved_bundle':True,'copied_resource_count':len(copies),'original_snapshot_unchanged':True,'main_ini':str(pkg.main_ini_path)}

def phase_list():
    p,base,orig=project('phase-list')
    for name in ['a.csv','b.csv']:(orig/name).write_bytes(PHASE)
    p.sourceEditor.phase_space_file='a.csv, b.csv';validate_source_model(p.sourceEditor);errors=list(p.sourceEditor.errors)
    assert not errors,errors
    out={}
    for label,fn in [('closure',lambda:collect_bundle_resources(WorkspaceSnapshot(p))),('export',lambda:export_bundle(WorkspaceSnapshot(p),base/'bundle')),('materialize',lambda:materialize_run_resources(p.sourceEditor,p.physicsEditor,workspace=orig,destination=base/'copies')),('package',lambda:package(p))]:
        try:fn();out[label]={'accepted':True}
        except Exception as e:out[label]={'accepted':False,'type':type(e).__name__,'message':str(e)}
    out['source_validation_errors']=errors;out['target_published']=(base/'bundle').exists();return out

def inactive():
    p,base,orig=project('inactive')
    p.sourceEditor.gps_sources=[GPSDefinition(energy_type='mono',spectrum_file='previous-hist.csv')]
    pkg=package(p)
    out={'package_accepted':True,'runtime_resources_directory':(Path(pkg.config_dir)/'resources').exists()}
    try:export_bundle(WorkspaceSnapshot(p),base/'bundle');out['export_accepted']=True
    except Exception as e:out.update(export_accepted=False,error=type(e).__name__+': '+str(e))
    out['target_published']=(base/'bundle').exists();return out

def missing_resource():
    p,base,orig=project('missing')
    (orig/'a.csv').write_bytes(SPEC)
    p.sourceEditor.gps_sources=[GPSDefinition(name='a',energy_type='histogram',spectrum_file='a.csv'),GPSDefinition(name='b',energy_type='histogram',spectrum_file='absent.csv')]
    snap=WorkspaceSnapshot(p);before=snapshot_fingerprint(snap)
    try:export_bundle(snap,base/'bundle')
    except (ValueError,OSError) as e:error=type(e).__name__+': '+str(e)
    else:assert False,'Missing active resource accepted'
    assert not (base/'bundle').exists() and not list(base.glob('.bundle.k1-*')) and snapshot_fingerprint(snap)==before
    return {'error':error,'target_not_published':True,'staging_removed':True,'snapshot_unchanged':True}

def change_during_export():
    p,base,orig=project('changed');f=orig/'a.csv';f.write_bytes(SPEC)
    p.sourceEditor.gps_sources=[GPSDefinition(energy_type='histogram',spectrum_file='a.csv')]
    snap=WorkspaceSnapshot(p);before=snapshot_fingerprint(snap);real=eb._collected
    def collected(*a,**kw):
        r=real(*a,**kw);f.write_bytes(SPEC.replace(b'2,3,2',b'2,3,3'));return r
    try:
        with patch.object(eb,'_collected',side_effect=collected):export_bundle(snap,base/'bundle')
    except (ValueError,OSError) as e:error=type(e).__name__+': '+str(e)
    else:assert False,'Changed source accepted'
    assert not (base/'bundle').exists() and not list(base.glob('.bundle.k1-*')) and snapshot_fingerprint(snap)==before
    return {'error':error,'target_not_published':True,'staging_removed':True,'snapshot_unchanged':True}

def dirty_draft():
    p,base,orig=project('dirty')
    (orig/'a.csv').write_bytes(SPEC);p.sourceEditor.gps_sources=[GPSDefinition(energy_type='histogram',spectrum_file='a.csv')]
    snap=WorkspaceSnapshot(p);snap.state['drafts']['config.seed']='BAD-SEED'
    before=snapshot_fingerprint(snap);export_bundle(snap,base/'bundle');assert snapshot_fingerprint(snap)==before
    (orig/'a.csv').unlink();loaded=load_bundle(base/'bundle',executable=sys.executable)
    assert loaded.state['drafts']['config.seed']=='BAD-SEED'
    report=_field_report(loaded);codes=[x.code for x in report.diagnostics if x.severity=='error'];assert not report.can_run and 'experiment.raw_seed.invalid' in codes
    return {'invalid_draft_preserved':True,'field_actions_rejected':True,'diagnostic_codes':codes,'original_snapshot_unchanged':True}

def tampered():
    p,base,orig=project('tamper');(orig/'a.csv').write_bytes(SPEC);p.sourceEditor.gps_sources=[GPSDefinition(energy_type='histogram',spectrum_file='a.csv')]
    export_bundle(WorkspaceSnapshot(p),base/'bundle');manifest=json.loads((base/'bundle'/'manifest.json').read_text(encoding='utf-8'))
    entry=next(x for x in manifest['members'] if x.get('role')=='spectrum');target=base/'bundle'/entry['path'];target.write_bytes(target.read_bytes()+b'3,4,1\n')
    try:load_bundle(base/'bundle',executable=sys.executable)
    except ValueError as e:return {'rejected':True,'error':str(e)}
    assert False,'Tampered resource accepted'

for name,fn in [('provided-resource-test-independent',provided),('portable-gps-and-both-field-maps',lambda:portable('gps')),('portable-single-phase-and-both-field-maps',lambda:portable('phase')),('comma-separated-phase-space-list',phase_list),('inactive-spectrum-path',inactive),('missing-active-resource-atomic-failure',missing_resource),('source-changed-mid-export',change_during_export),('invalid-draft-preserved-and-rejected',dirty_draft),('tampered-resource-refused',tampered)]:case(name,fn)
end=hashes();report={'utc':datetime.now(timezone.utc).isoformat(),'runtime_root':str(WORK),'source_sha256_before':start,'source_sha256_after':end,'selected_source_unchanged':start==end,'cases':results}
(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('SELECTED_SOURCE_UNCHANGED',start==end,flush=True)
raise SystemExit(1 if any(x['status']!='observed' for x in results) else 0)
