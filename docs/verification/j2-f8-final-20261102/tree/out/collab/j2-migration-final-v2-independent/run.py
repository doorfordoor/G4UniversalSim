"""Narrow independent recheck; immutable old failure, full migration main only."""
import difflib, hashlib, importlib, importlib.util, json, re, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
DRAFT=ROOT/'out/collab/j2-static-fixture-patch-final-v2'
PRODUCT=ROOT/'out/collab/j2-f8-repair-draft-v2'
TARGET=DRAFT/'proposed/scripts/test_config_migration.py'
OLD=ROOT/'out/collab/j2-static-fixture-patch-draft/proposed/scripts/test_config_migration.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
expected={TARGET:'909cab4fc3a3f80a6816af0c4ee0e4985970b2f78c06a339cb5ff7edc1989166',DRAFT/'test_config_migration.patch':'a9953013c9dc8a9d6009356604874a730ff2b7843a312b4b24a5ad9abdfa0056',DRAFT/'tests.patch':'b240672c7e1c42b9b54075a7dc9e788a66ecc2ad7aed1237df6e09ee338c200f'}
for path,digest in expected.items():assert sha(path)==digest,(path,sha(path))
old=OLD.read_bytes()
corrected=old.replace(b'file = mesh.stl\\nunit = cm',b'file = mesh.stl\\nfile_unit = cm').replace(b'shape_properties["unit"]',b'shape_properties["file_unit"]')
assert corrected==TARGET.read_bytes(), 'Change extends beyond the two reviewed key corrections'
manifest=json.loads((PRODUCT/'manifest.json').read_bytes())
for row in manifest['files']:
    assert sha(ROOT/row['path'])==row['original_raw_sha256']
    assert sha(PRODUCT/'files'/row['path'])==row['candidate_sha256']
if '--worker' in sys.argv:
    sys.dont_write_bytecode=True
    temporary=OUT/'temporary';temporary.mkdir(exist_ok=True);tempfile.tempdir=str(temporary)
    sys.path.insert(0,str(ROOT/'gui'))
    for short in ('core.i18n','editors.material_editor_model','editors.source_physics_scoring_model','validators.config_validator'):
        module=importlib.import_module('g4usim_gui.'+short)
        candidate=PRODUCT/'files'/Path(module.__file__).relative_to(ROOT)
        exec(compile(candidate.read_bytes(),str(candidate),'exec'),module.__dict__)
    spec=importlib.util.spec_from_file_location('independent_assert_probe',ROOT/'tools/test_assert_probe.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    def draft_run(path,run_name=None,**kwargs):
        assert Path(path).resolve()==TARGET.resolve()
        ns={'__name__':run_name,'__file__':str(ROOT/'scripts/test_config_migration.py'),'__package__':None}
        exec(compile(TARGET.read_bytes(),str(TARGET),'exec'),ns)
        return ns
    probe.runpy.run_path=draft_run
    raise SystemExit(probe.main(['probe',str(TARGET)]))
assert not (OUT/'receipt.json').exists()
old_receipt=ROOT/'out/collab/j2-static-fixture-independent-review/geometry-execution.json'
old_log=ROOT/'out/collab/j2-static-fixture-independent-review/test_config_migration.py.log'
bound=[ROOT/'scripts/test_config_migration.py',old_receipt,old_log,OLD]+[ROOT/row['path'] for row in manifest['files']]
before={str(p.relative_to(ROOT)):sha(p) for p in bound}
result=subprocess.run([sys.executable,'-B',str(Path(__file__)),'--worker'],cwd=ROOT,capture_output=True)
log=OUT/'migration-full-main.log';assert not log.exists();log.write_bytes(result.stdout+result.stderr)
after={str(p.relative_to(ROOT)):sha(p) for p in bound};assert before==after
markers=re.findall(rb'G4USIM_ASSERTS=(\d+)',result.stdout)
receipt={'status':'pass' if result.returncode==0 and len(markers)==1 and int(markers[0])>0 else 'fail','exit_code':result.returncode,'assertions':int(markers[0]) if markers else None,'test_sha256':sha(TARGET),'migration_patch_sha256':sha(DRAFT/'test_config_migration.patch'),'tests_patch_sha256':sha(DRAFT/'tests.patch'),'product_manifest_sha256':sha(PRODUCT/'manifest.json'),'product_patch_sha256':sha(PRODUCT/'product.patch'),'only_two_reviewed_key_corrections':True,'method':'Complete unchanged draft __main__, original repository __file__/ROOT, standard assert probe; product v2 substituted only in memory; no K1/F4 execution. All temporary fixture writes under out.','log_sha256':sha(log),'preserved_source_and_prior_failure_sha256':before,'tracked_and_original_failure_bytes_unchanged':True}
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(result.stdout.decode(errors='replace'));print(result.stderr.decode(errors='replace'));print(json.dumps(receipt,indent=2))
raise SystemExit(0 if receipt['status']=='pass' else 1)
