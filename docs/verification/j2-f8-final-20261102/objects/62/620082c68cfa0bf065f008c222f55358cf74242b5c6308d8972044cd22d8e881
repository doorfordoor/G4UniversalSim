from pathlib import Path
import os,sys,json,hashlib,subprocess,copy
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'gui'))
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from g4usim_gui.widgets.config.geometry import GeometryDetailsWidget
from g4usim_gui.editors.geometry_editor_model import GeometryDocument,HierarchicalVolumeRow as R,BooleanOperationRow as B,LayerRow,validate_geometry_document
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
OUT=Path(__file__).resolve().parent/'details-r2';OUT.mkdir(exist_ok=False)
app=QApplication([]);results=[]
for kind,row in [('volume',R(shape='trap',shape_properties={'dz':' 2 mm ','theta':' 0.3 rad ','phi':'0 deg','dy1':'1 mm','dx1':'1 mm','dx2':'1 mm','alpha1':'0 rad','dy2':'1 mm','dx3':'1 mm','dx4':'1 mm','alpha2':'0 rad'},preview_properties={'placement':' normal '},visual={'vis.alpha':' bad '},production_cuts={'cut.gamma':' -2 um '},metadata='metadata.x = preserve')),
                 ('boolean',B(tool_shape='trd',shape_properties={'dx1':' 1 mm ','dx2':'bad','dy1':'2 mm','dy2':'2 mm','dz':'3 mm'},name=' named ')),
                 ('layer',LayerRow(visual={'vis.visible':' invalid '},production_cuts={'cut.e-':' -1 mm '},metadata='metadata.a = b'))]:
 w=GeometryDetailsWidget(kind);before=asdict(row);w.set_row(row);w.apply_row(row)
 assert asdict(row)==before,(kind,before,asdict(row))
 results.append({'kind':kind,'set_apply_raw_drafts_identical':True})
 w.close();w.deleteLater();app.processEvents()
# A valid backend vector uses independent units for comma components.
raw='[world]\nshape=box\nsize=1,1,2 cm\nmaterial=G4_Galactic\n[volume.V]\nparent=world\nshape=box\nsize=1 mm,1 mm,1 cm\nmaterial=G4_Galactic\nplacement=replica\nreplica_axis=z\nreplica_count=2\nreplica_width=1 cm\n'
d=geometry_document_from_summary(parse_geometry_text(raw,source_path=OUT/'geometry.ini',template_name='hierarchical'))
validate_geometry_document(d,material_names={'G4_Galactic'})
result={'case':'mixed-vector-replica','gui_errors':d.errors}
try:generate_geometry_ini_text(d);result['writer_accepted']=True
except Exception as e:result.update(writer_accepted=False,writer_error=str(e))
(OUT/'geometry.ini').write_text(raw)
(OUT/'main.ini').write_text('[materials]\nfile='+str(ROOT/'config/materials/material.ini')+'\n[geometry]\ntemplate=hierarchical\nconfig=geometry.ini\n[physics]\nreference=FTFP_BERT\n[source]\npreset=mono_proton\n')
env=dict(os.environ)
for k in list(env):
 if k.startswith('G4') and k.endswith('DATA'):env.pop(k,None)
env['PATH']='D:/ProgramFiles/Geant4/bin;D:/ProgramFiles/Qt/5.15.2/msvc2019_64/bin;'+env.get('PATH','')
env['GEANT4_DATA_DIR']=env['G4USIM_GEANT4_DATA']='D:/ProgramFiles/Geant4/share/Geant4/data'
r=subprocess.run([str(ROOT/'out/build-i2-formal113/Release/G4UniversalSim.exe'),'--config','main.ini','--inspect-run'],cwd=OUT,env=env,capture_output=True,timeout=45)
(OUT/'stdout.log').write_bytes(r.stdout);(OUT/'stderr.log').write_bytes(r.stderr);result['backend_exit']=r.returncode
results.append(result)
(OUT/'receipt.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2));app.processEvents()
