from pathlib import Path
import sys,os,time,json,hashlib,copy,traceback,shutil
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'gui'))
from g4usim_gui.core import wizard
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
from g4usim_gui.core.experiment_bundle import export_bundle,load_bundle
from g4usim_gui.editors.geometry_editor_model import HierarchicalVolumeRow as R,BooleanOperationRow as B,geometry_document_from_summary
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.writers.package_writer import create_run_package
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.core.run_editor_resources import materialize_geometry_file
FILES=['core/run_editor_resources.py','writers/package_writer.py','core/experiment_bundle.py','core/config_schema_data.py']
def hashes():return {p:hashlib.sha256((ROOT/'gui/g4usim_gui'/p).read_bytes()).hexdigest() for p in FILES}
start=hashes();WORK=OUT/('resources-'+str(time.time_ns()));WORK.mkdir()
original=WORK/'original';original.mkdir();assets=original/'assets';assets.mkdir()
mesh=assets/'mesh.stl';mesh.write_text('solid tetra\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid tetra\n',encoding='utf-8')
table=assets/'copies.csv';table.write_text('x_mm,y_mm,z_mm,material\n0,0,0,G4_Si\n2,0,0,G4_WATER\n',encoding='utf-8')
asset_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (mesh,table)}
p=G4USimProject(executable=sys.executable,workspaceRoot=str(original),runsRoot=str(WORK/'runs'))
p.pathSettings=PathSettings(executable=p.executable,workspace_root=p.workspaceRoot,runs_root=p.runsRoot)
wizard.apply_to_project(p,wizard.blank_result())
p.geometryEditor.volumes.extend([
 R(name='Mesh',parent='world',shape='tessellated',material='G4_Si',shape_properties={'file':str(mesh),'file_unit':'mm'}),
 R(name='RepeatMother',parent='world',shape='box',size='10 mm,10 mm,10 mm',material='G4_AIR'),
 R(name='Copy',parent='RepeatMother',shape='box',size='1 mm,1 mm,1 mm',material='G4_Si',preview_properties={'placement':'parameterised','copies_file':str(table)}),
 R(name='Base',parent='world',shape='box',size='30 mm,30 mm,30 mm',material='G4_Si'),
])
trd={'dx1':'1 mm','dx2':'2 mm','dy1':'1 mm','dy2':'1 mm','dz':'2 mm'}
trap={'dz':'1 mm','theta':'0 deg','phi':'0 deg','dy1':'1 mm','dx1':'1 mm','dx2':'1 mm','alpha1':'0 deg','dy2':'1 mm','dx3':'1 mm','dx4':'1 mm','alpha2':'0 deg'}
p.geometryEditor.boolean_ops=[B(target_volume='Base',operation='subtraction',tool_shape='trd',shape_properties=trd),B(target_volume='Base',index=1,operation='subtraction',tool_shape='trap',shape_properties=trap)]
results={}
def package(project):
 return create_run_package(project=project,paths=project.pathSettings,run=project.runSettings,geometry=project.geometrySettings,source=project.sourceSettings,physics=project.physicsSettings,scoring=project.scoringSettings,material_document=project.materialEditor,geometry_document=project.geometryEditor,source_model=project.sourceEditor,physics_model=project.physicsEditor,scoring_model=project.scoringEditor)[0]
def run(name,fn):
 try:results[name]=fn()
 except Exception as e:results[name]={'error':repr(e),'traceback':traceback.format_exc()}
 print(name,json.dumps(results[name],ensure_ascii=False),flush=True)
def generated_package():
 before=copy.deepcopy(p.geometryEditor)
 pkg=package(p);summary=parse_geometry(pkg.geometry_ini_path,'hierarchical')
 paths=[Path(next(v for v in summary.volumes if v.name=='Mesh').shape_properties['file']),Path(next(v for v in summary.volumes if v.name=='Copy').preview_properties['copies_file'])]
 expected=[asset_hashes['mesh.stl'],asset_hashes['copies.csv']]
 return {'package':pkg.package_dir,'paths':[str(v) for v in paths],'copied_bytes_match':[hashlib.sha256(v.read_bytes()).hexdigest()==h for v,h in zip(paths,expected)],'all_inside_package':all(v.resolve().is_relative_to(Path(pkg.package_dir).resolve()) for v in paths),'editor_resource_paths_unchanged':[(r.shape_properties.get('file'),r.preview_properties.get('copies_file')) for r in p.geometryEditor.volumes]==[(r.shape_properties.get('file'),r.preview_properties.get('copies_file')) for r in before.volumes],'bool_fields':[op.shape_properties for op in summary.boolean_ops]}
def source_copy_package():
 text=generate_geometry_ini_text(p.geometryEditor).replace(str(mesh),'mesh.stl').replace(str(table),'copies.csv')
 source=assets/'source.ini';source.write_bytes(text.replace('\n','\r\n').encode())
 project=copy.deepcopy(p);project.geometryEditor=geometry_document_from_summary(parse_geometry(source,'hierarchical'),'hierarchical');project.geometryEditor.source_copy_mode=True
 project.geometrySettings.config_path=str(source);project.pathSettings.geometry_config=str(source)
 before=source.read_bytes();pkg=package(project)
 summary=parse_geometry(pkg.geometry_ini_path,'hierarchical')
 return {'package':pkg.package_dir,'source_unchanged':source.read_bytes()==before,'copy_byte_identical':Path(pkg.geometry_ini_path).read_bytes()==before,'resource_exists':Path(next(v for v in summary.volumes if v.name=='Mesh').shape_properties['file']).is_file(),'report_mentions_copy': 'copied from source' in Path(pkg.validation_report_path).read_text(encoding='utf-8')}
def duplicate_source_copy():
    from g4usim_gui.validators.config_validator import validate_config_builder
    project=copy.deepcopy(p)
    project.geometryEditor.volumes=[r for r in project.geometryEditor.volumes if r.name in {'world','RepeatMother','Copy'}]
    project.geometryEditor.boolean_ops=[]
    text=generate_geometry_ini_text(project.geometryEditor).replace(str(table),'copies.csv')
    text=text.replace('copies_file = copies.csv','copies_file = copies.csv\ncopies_file = copies.csv')
    source=assets/'duplicate-source.ini';source.write_text(text,encoding='utf-8')
    project.geometryEditor=geometry_document_from_summary(parse_geometry(source,'hierarchical'),'hierarchical')
    project.geometryEditor.source_copy_mode=True
    project.geometrySettings.config_path=str(source);project.pathSettings.geometry_config=str(source)
    report=validate_config_builder(paths=project.pathSettings,run=project.runSettings,geometry=project.geometrySettings,
        source=project.sourceSettings,physics=project.physicsSettings,scoring=project.scoringSettings,
        material_document=project.materialEditor,geometry_document=project.geometryEditor,
        source_model=project.sourceEditor,physics_model=project.physicsEditor,scoring_model=project.scoringEditor)
    result={'preflight_can_run':report.can_run,'preflight_errors':report.errors,'source_copy':True,'blockers':project.geometryEditor.round_trip_blockers}
    try:
        pkg=package(project);result['package_created']=True;result['package']=pkg.package_dir
    except Exception as exc:
        result['package_created']=False;result['exception']=repr(exc);result['traceback']=traceback.format_exc()
    return result

def export_move_load():
 bundle=WORK/'bundle';export_bundle(WorkspaceSnapshot(p),bundle)
 moved=WORK/'moved';moved.mkdir();destination=moved/'bundle'
 assert original.resolve().is_relative_to(OUT.resolve()) and bundle.resolve().is_relative_to(OUT.resolve())
 original.rename(WORK/'original-offline');bundle.rename(destination)
 restored=load_bundle(destination,executable=sys.executable)
 doc=restored.project.geometryEditor
 resource_paths=[Path(next(v for v in doc.volumes if v.name=='Mesh').shape_properties['file']),Path(next(v for v in doc.volumes if v.name=='Copy').preview_properties['copies_file'])]
 restored.project.pathSettings.runs_root=str(WORK/'replayed-runs');restored.project.runsRoot=restored.project.pathSettings.runs_root
 pkg=package(restored.project)
 generated=Path(pkg.geometry_ini_path).read_text(encoding='utf-8')
 return {'bundle':str(destination),'source_directory_unavailable':not original.exists(),'restored_paths':[str(v) for v in resource_paths],'all_inside_bundle':all(v.resolve().is_relative_to(destination.resolve()) for v in resource_paths),'all_exist':all(v.is_file() for v in resource_paths),'regenerated_package':pkg.package_dir,'old_prefix_in_generated':str(original) in generated,'boolean_fields_preserved':[op.shape_properties for op in doc.boolean_ops]==[trd,trap]}
run('generated-STL-copies',generated_package)
run('source-copy-with-resources',source_copy_package)
run('legacy-v1-duplicate-source-copy',duplicate_source_copy)
run('K1-export-move-load-regenerate',export_move_load)
result={'before':start,'after':hashes(),'sources_unchanged':start==hashes(),'asset_hashes':asset_hashes,'results':results}
(WORK/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'latest-resource-receipt.txt').write_text(str(WORK/'receipt.json'),encoding='utf-8')
print('receipt',WORK/'receipt.json',flush=True)
