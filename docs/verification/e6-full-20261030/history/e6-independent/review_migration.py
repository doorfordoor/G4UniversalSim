from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'gui'))
from g4usim_gui.core.config_migration import publish_migration
from g4usim_gui.core.geometry_migration import plan_geometry_migration
from g4usim_gui.core.project import project_from_dict, project_to_dict

WORK = Path(__file__).resolve().parent
facts = {}
for label, data in (
    ('string_false_becomes_true', {'geometryEditor': {'source_copy_mode': 'false', 'is_dirty': 'false'}}),
    ('fractional_threads_truncated', {'threads': 2.75}),
    ('source_error_string_splits', {'geometryEditor': {'source_errors': 'ERR'}}),
    ('null_path_stringifies', {'geometryEditor': {'source_path': None}}),
    ('preview_bool_integer_conflict', {'geometryEditor': {'volumes': [{'name':'V','sensitive':False}],
                                                          'preview': {'volumes': [{'name':'V','sensitive':0}]}}}),
):
    try:
        value = project_to_dict(project_from_dict(data))
        facts[label] = {'accepted':True, 'input':data,
                        'threads':value['threads'],
                        'geometry':{k:value['geometryEditor'][k] for k in ('source_copy_mode','is_dirty','source_errors','source_path','volumes')}}
    except Exception as error:
        facts[label] = {'accepted':False,'error':str(error),'input':data}

resource = 'x_mm,y_mm,z_mm,rot_x_deg,rot_y_deg,rot_z_deg,material\n-20,0,0,0,0,0,G4_Si\n20,0,0,0,0,0,G4_WATER\n'
(WORK / 'copies.csv').write_text(resource, encoding='utf-8')
(WORK / '\u00a0copies.csv').write_text(resource, encoding='utf-8')
geometry = WORK / 'unicode-leading-resource.ini'
geometry.write_text('[world]\nshape = box\nsize = 10 cm, 10 cm, 10 cm\nmaterial = G4_AIR\n'
                    '[volume.Target]\nparent = world\nshape = box\nsize = 1 cm, 1 cm, 1 cm\n'
                    'material = G4_Si\nplacement = parameterised\ncopies_file = \u00a0copies.csv\n',encoding='utf-8')
plan = plan_geometry_migration(geometry,'hierarchical')
migrated = WORK / 'unicode-leading-resource-v2.ini'
if not migrated.exists():
    publish_migration(plan,migrated)
exe = ROOT / 'out/build-2c/Release/G4UniversalSim.exe'
for label, source in (('source',geometry),('migrated',migrated)):
    ini = WORK / f'{label}.main.ini'
    ini.write_text(f'[run]\nthreads=1\nverbose=0\n[output]\ndir={(WORK/(label+"-out")).as_posix()}\nformat=csv\n'
                   f'[materials]\nfile={(ROOT/"config/materials/material.ini").as_posix()}\n'
                   f'[geometry]\ntemplate=hierarchical\nconfig={source.as_posix()}\n'
                   '[physics]\nreference=FTFP_BERT\n[source]\nparticle=geantino\nenergy=1 MeV\n'
                   'position_type=point\nposition=0 mm,0 mm,0 mm\ndirection=0,0,1\n[scoring]\nenabled=false\n', encoding='utf-8')
    macro=WORK/'init.mac'
    macro.write_text('/run/initialize\n',encoding='utf-8')
    result=subprocess.run([str(exe),'--config',str(ini),'--macro',str(macro)],cwd=ROOT,capture_output=True,timeout=90)
    log=WORK/f'{label}.log'
    log.write_bytes(result.stdout+result.stderr)
    facts[f'unicode_backend_{label}']={'exit':result.returncode,'log':str(log)}
(WORK/'review.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(facts,ensure_ascii=False,indent=2))
