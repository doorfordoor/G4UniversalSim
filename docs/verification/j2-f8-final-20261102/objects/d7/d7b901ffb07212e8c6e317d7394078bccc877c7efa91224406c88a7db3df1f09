"""Independent full-main F4 draft execution against hash-bound out product v2."""
import hashlib, importlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
DRAFT=ROOT/'out/collab/j2-static-fixture-patch-draft'
PRODUCT=ROOT/'out/collab/j2-f8-repair-draft-v2'
NAMES=('test_f4_producers.py','test_f4_document_diagnostics.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((PRODUCT/'manifest.json').read_bytes())
for row in manifest['files']:
    assert sha(ROOT/row['path'])==row['original_raw_sha256']
    assert sha(PRODUCT/'files'/row['path'])==row['candidate_sha256']
if len(sys.argv)>1:
    name=sys.argv[1];assert name in NAMES
    sys.dont_write_bytecode=True
    temporary=OUT/'temp-documents-v2-r2';temporary.mkdir(exist_ok=True);tempfile.tempdir=str(temporary)
    sys.path.insert(0,str(ROOT/'gui'))
    for short in ('core.i18n','editors.material_editor_model','editors.source_physics_scoring_model','validators.config_validator'):
        module=importlib.import_module('g4usim_gui.'+short)
        candidate=PRODUCT/'files'/Path(module.__file__).relative_to(ROOT)
        exec(compile(candidate.read_bytes(),str(candidate),'exec'),module.__dict__)
    spec=importlib.util.spec_from_file_location('independent_assert_probe',ROOT/'tools/test_assert_probe.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    target=(DRAFT/'proposed/scripts'/name).resolve()
    def draft_run(path,run_name=None,**kwargs):
        assert Path(path).resolve()==target
        ns={'__name__':run_name,'__file__':str(ROOT/'scripts'/name),'__package__':None}
        exec(compile(target.read_bytes(),str(target),'exec'),ns)
        return ns
    probe.runpy.run_path=draft_run
    raise SystemExit(probe.main(['probe',str(target)]))
assert not (OUT/'f4-v2-r2-execution.json').exists()
receipt={'method':'Full original __main__ entry with unchanged out draft bytes, standard assertion probe, original repository ROOT and four hash-bound v2 product modules substituted in process. No tracked source changes.', 'product_manifest_sha256':sha(PRODUCT/'manifest.json'),'product_patch_sha256':sha(PRODUCT/'product.patch'),'scripts':[]}
for name in NAMES:
    log=OUT/(name+'.v2-r2.log');assert not log.exists()
    result=subprocess.run([sys.executable,'-B',str(Path(__file__)),name],cwd=ROOT,capture_output=True)
    log.write_bytes(result.stdout+result.stderr)
    receipt['scripts'].append({'path':'scripts/'+name,'draft_sha256':sha(DRAFT/'proposed/scripts'/name),'exit_code':result.returncode,'log':str(log.relative_to(ROOT)),'log_sha256':sha(log)})
    print(name,result.returncode,result.stdout.decode(errors='replace')[-1200:],result.stderr.decode(errors='replace')[-2000:])
for row in manifest['files']:assert sha(ROOT/row['path'])==row['original_raw_sha256']
receipt['tracked_product_bytes_unchanged']=True
receipt['status']='pass' if all(x['exit_code']==0 for x in receipt['scripts']) else 'fail'
(OUT/'f4-v2-r2-execution.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
raise SystemExit(0 if receipt['status']=='pass' else 1)
