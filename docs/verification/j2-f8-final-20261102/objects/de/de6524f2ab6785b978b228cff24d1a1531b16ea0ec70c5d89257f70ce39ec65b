from pathlib import Path
import json,sys,traceback,hashlib
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'gui'))
from g4usim_gui.core.project import load_project_snapshot
receipt=json.loads(Path((OUT/'latest-resource-receipt.txt').read_text()).read_text(encoding='utf-8'))
pkg=Path(receipt['results']['generated-STL-copies']['package'])
snapshot=pkg/'project_snapshot.json'
files=['core/project_snapshot.py','parsers/geometry_parser.py','core/run_editor_resources.py']
def hashes():return {p:hashlib.sha256((ROOT/'gui/g4usim_gui'/p).read_bytes()).hexdigest() for p in files}
start=hashes();results={}
def probe(name):
    try:
        loaded=load_project_snapshot(snapshot)
        results[name]={'accepted':True,'input_roles':[x.role for x in loaded.inputs],
            'stl_path_exists':Path(next(r for r in loaded.project.geometryEditor.volumes if r.name=='Mesh').shape_properties['file']).is_file()}
    except Exception as exc:results[name]={'accepted':False,'error':repr(exc),'traceback':traceback.format_exc()}
probe('intact-control')
mesh=pkg/'config/geometry-resources/g0000.stl';away=mesh.with_name('g0000-away.stl')
assert mesh.resolve().is_relative_to(OUT.resolve())
mesh.rename(away)
try:probe('missing-STL')
finally:away.rename(mesh)
table=pkg/'config/geometry-resources/g0001.csv';away=table.with_name('g0001-away.csv')
table.rename(away)
try:probe('missing-copies-control')
finally:away.rename(table)
result={'snapshot':str(snapshot),'before':start,'after':hashes(),'sources_unchanged':start==hashes(),'results':results}
(OUT/'package-load-resource-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
