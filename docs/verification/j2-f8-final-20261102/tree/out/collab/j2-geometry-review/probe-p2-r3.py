from pathlib import Path
import os,sys,json,hashlib,subprocess,copy
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'gui'))
from g4usim_gui.editors.geometry_editor_model import GeometryDocument,HierarchicalVolumeRow as R,BooleanOperationRow as B,geometry_document_from_summary,geometry_document_from_dict,validate_geometry_document
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from dataclasses import asdict
OUT=Path(__file__).resolve().parent/'p2-recheck/r3';OUT.mkdir(exist_ok=False)
ENV=dict(os.environ)
for k in list(ENV):
 if k.startswith('G4') and k.endswith('DATA'):ENV.pop(k,None)
ENV['GEANT4_DATA_DIR']=ENV['G4USIM_GEANT4_DATA']='D:/ProgramFiles/Geant4/share/Geant4/data'
ENV['PATH']='D:/ProgramFiles/Geant4/bin;D:/ProgramFiles/Qt/5.15.2/msvc2019_64/bin;'+ENV.get('PATH','')
EXE=ROOT/'out/build-i2-formal113/Release/G4UniversalSim.exe'
FILES=['gui/g4usim_gui/editors/geometry_editor_model.py','gui/g4usim_gui/parsers/geometry_parser.py','gui/g4usim_gui/writers/geometry_ini_writer.py','gui/g4usim_gui/widgets/config/geometry.py','gui/g4usim_gui/widgets/config/booleans.py','gui/g4usim_gui/widgets/config/layers.py','gui/g4usim_gui/core/solid_registry_data.py','scripts/generate_solid_registry.py']
BEFORE={x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in FILES}
SNAP=OUT/'snapshot';SNAP.mkdir()
for x in FILES:(SNAP/Path(x).name).write_bytes((ROOT/x).read_bytes())
RESULTS=[]
def doc(v):return GeometryDocument(mode='hierarchical',volumes=[R(name='world',shape='box',size='100 mm,100 mm,100 mm',material='G4_Galactic'),v])
def run(name,d,backend=True):
 folder=OUT/name;folder.mkdir()
 validate_geometry_document(d,material_names={'G4_Galactic'})
 record={'name':name,'gui_errors':d.errors,'gui_warnings':d.warnings}
 try:
  text=generate_geometry_ini_text(d);record['writer_accepted']=True
  (folder/'geometry.ini').write_text(text,encoding='utf-8')
 except Exception as e:record.update(writer_accepted=False,writer_error=str(e));text=None
 if text and backend:
  ini='[materials]\nfile='+str(ROOT/'config/materials/material.ini')+'\n[geometry]\ntemplate=hierarchical\nconfig=geometry.ini\n[physics]\nreference=FTFP_BERT\n[source]\npreset=mono_proton\n'
  (folder/'main.ini').write_text(ini,encoding='utf-8')
  result=subprocess.run([str(EXE),'--config','main.ini','--inspect-run'],cwd=folder,env=ENV,capture_output=True,timeout=45)
  (folder/'stdout.log').write_bytes(result.stdout);(folder/'stderr.log').write_bytes(result.stderr)
  record['backend_exit']=result.returncode
  record['backend_error_excerpt']=(result.stdout+result.stderr).decode('utf-8','replace')[-2300:] if result.returncode else ''
 RESULTS.append(record)
 print(name,'GUI',len(d.errors),'writer',record['writer_accepted'],'backend',record.get('backend_exit'),flush=True)
 return record
# Independent parameter-token grammar controls, not author's geometry tests.
for name,params in [('tubs-comma-control','0 mm,10 mm,20 mm,0 deg,360 deg'),('tubs-space-mixed-unit','0 10 20 0 360 deg'),('tubs-no-separators','0mm10mm20mm0deg360deg')]:
 run(name,doc(R(name='V',parent='world',shape='tubs',parameters=params,material='G4_Galactic')))
# The table owns per-copy transforms, so a second position/rotation must fail GUI.
resources=OUT/'resources';resources.mkdir();csv=resources/'copies.csv';csv.write_text('x_mm,y_mm,z_mm\n0,0,0\n2,0,0\n')
for name,position in [('table-control',''),('table-conflicting-position','0 mm,0 mm,0 mm')]:
 run(name,doc(R(name='V',parent='world',shape='box',size='1 mm,1 mm,1 mm',material='G4_Galactic',position=position,preview_properties={'placement':'parameterised','copies_file':str(csv.resolve())})))
# Bare angular parameters are rad; raw strings and named Boolean fields survive.
v=R(name='V',parent='world',shape='hype',parameters='0 mm,2 mm,0.1,0.2,5 mm',material='G4_Galactic',region='R',visual={'vis.alpha':'0.4','vis.color':'cyan','vis.wireframe':'yes'},production_cuts={'cut.e-':'2 um'},metadata='metadata.origin = preserved')
run('angular-vis-cuts-control',doc(v))
d=doc(R(name='V',parent='world',shape='box',size='20 mm,20 mm,20 mm',material='G4_Galactic'))
d.boolean_ops=[B(target_volume='V',operation='subtraction',tool_shape='trd',shape_properties={'dx1':'1 mm','dx2':'2 mm','dy1':'1 mm','dy2':'1 mm','dz':'2 mm'})]
r=run('boolean-trd-control',d)
if r['writer_accepted']:
 raw=(OUT/'boolean-trd-control/geometry.ini').read_text();restored=geometry_document_from_summary(parse_geometry_text(raw,source_path=OUT/'boolean-trd-control/geometry.ini',template_name='hierarchical'))
 r['boolean_properties_preserved']=restored.boolean_ops[0].shape_properties==d.boolean_ops[0].shape_properties
# Imported relative resource anchor, dictionary replay, source-only blocker retention.
raw='[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n[volume.V]\nparent=world\nshape=box\nsize=1 mm,1 mm,1 mm\nmaterial=G4_Galactic\nplacement=parameterised\ncopies_file=copies.csv\n'
summary=parse_geometry_text(raw,source_path=resources/'original.ini',template_name='hierarchical')
d=geometry_document_from_summary(summary);replay=geometry_document_from_dict(asdict(d))
r=run('source-resource-replay-control',replay)
r['absolute_resource_preserved']=str(csv.resolve()) in (OUT/'source-resource-replay-control/geometry.ini').read_text() if r['writer_accepted'] else False
bad=raw+'mystery_payload=keep-me\n';d=geometry_document_from_summary(parse_geometry_text(bad,source_path=resources/'original.ini',template_name='hierarchical'))
r=run('source-unknown-blocker',d,False);r['blockers_after_validate']=d.round_trip_blockers
csv.rename(resources/'moved.csv')
d=geometry_document_from_summary(summary);run('source-resource-disappeared',d,False)
AFTER={x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in FILES}
receipt={'review_source_before':BEFORE,'review_source_after':AFTER,'source_unchanged_during_probe':BEFORE==AFTER,'results':RESULTS}
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Saved',OUT/'receipt.json',flush=True)
