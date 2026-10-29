from pathlib import Path
import copy
import hashlib
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'gui'))
from g4usim_gui.core.project import load_project, project_from_dict, project_to_dict, save_project
from g4usim_gui.core.project_migration import plan_project_migration
from g4usim_gui.core.config_migration import publish_migration
from g4usim_gui.models.run_model import RunSettings

WORK = Path(__file__).resolve().parent
facts = []
before = json.loads((WORK / 'review-before-types-fix.json').read_text(encoding='utf-8'))
after = json.loads((WORK / 'review.json').read_text(encoding='utf-8'))
labels = ['string_false_becomes_true','fractional_threads_truncated','source_error_string_splits',
          'null_path_stringifies','preview_bool_integer_conflict']
for label in labels:
    assert before[label]['input'] == after[label]['input']
    assert before[label]['accepted'] is True
    assert after[label]['accepted'] is False
    facts.append({'original_payload':label,'now_rejected':True,'error':after[label]['error']})

with tempfile.TemporaryDirectory(prefix='compat-types-',dir=WORK) as temporary:
    folder=Path(temporary)
    for version in (None,1,2,3,4,5,6):
        for geometry_version in ('1','2'):
            data={'projectName':'兼容检查','threads':'2','seed':None,
                  'macroPath':'old.mac','geometryEditor':{'schemaVersion':geometry_version,
                     'sourceCopyMode':False,'dirty':False,
                     'preview':{'volumes':[{'name':'target','sensitive':False}],'boolean_ops':[]}}}
            if version is not None: data['version']=version
            pristine=copy.deepcopy(data)
            loaded=project_from_dict(data)
            assert data==pristine
            assert loaded.threads==2 and type(loaded.threads) is int
            assert loaded.runSettings.threads==2
            assert loaded.seed=='' and loaded.runSettings.seed == RunSettings().seed
            assert loaded.geometryEditor.schema_version==int(geometry_version)
            assert loaded.geometryEditor.source_copy_mode is False
            assert loaded.geometryEditor.is_dirty is False
            assert loaded.geometryEditor.volumes[0].sensitive is False
            assert loaded.runInputMode=='external' and loaded.version==6
            source=folder/f'source-{version}-{geometry_version}.json'
            source.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            raw=source.read_bytes()
            plan=plan_project_migration(source)
            destination=folder/f'copy-{version}-{geometry_version}.json'
            publish_migration(plan,destination)
            assert project_to_dict(load_project(destination))==project_to_dict(loaded)
            assert source.read_bytes()==raw
            normal=folder/'normal-save.json'
            save_project(loaded,normal)
            assert project_to_dict(load_project(normal))==project_to_dict(loaded)
            facts.append({'input_version':version,'geometry_string_version':geometry_version,
                          'threads_string_seed_null_compatible':True,'migration_save_reload_equal':True})
    generated=project_from_dict({'threads':' +2 ','seed':None})
    assert generated.runInputMode=='generated' and generated.threads==2 and generated.seed==''

for script in ('gui/smoke_tests/smoke_project_io.py','scripts/test_config_migration.py'):
    result=subprocess.run([sys.executable,script],cwd=ROOT,capture_output=True,timeout=90)
    log=WORK/(Path(script).stem+'-types-fix.log')
    log.write_bytes(result.stdout+result.stderr)
    assert result.returncode==0,(script,result.returncode,result.stderr.decode('utf-8',errors='replace')[-1500:])
    facts.append({'script':script,'exit':result.returncode,'log':str(log)})

files=['gui/g4usim_gui/core/project_migration.py','gui/g4usim_gui/core/project.py',
       'gui/g4usim_gui/editors/geometry_editor_model.py',
       'out/verification/e6-independent/review_migration.py']
identities={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
(WORK/'types-fix-review.json').write_text(json.dumps({'facts':facts,'identities':identities},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Independent types fix: five unchanged payloads rejected; 14 legacy migration/save/reload combinations and actual project_io/core smoke passed.')
