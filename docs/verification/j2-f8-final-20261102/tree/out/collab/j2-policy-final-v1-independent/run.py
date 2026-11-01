"""Hash-bound final-v1 policy review, isolated component execution only."""
import ast,ctypes,hashlib,importlib.util,json,os,re,subprocess,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
FINAL=ROOT/'out/collab/j2-resource-policy-path-review/final-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
receipt=json.loads((FINAL/'receipt.json').read_bytes())
assert receipt['status']=='frozen_out_candidate_ready_for_independent_review'
assert sha(FINAL/'fix.patch')==receipt['patch_sha256']=='f705dc96bcfb4706e03d045a00e281c53ce0e8fe6eb9912c27579188e8a446de'
for row in receipt['files']:
    candidate=FINAL/Path(row['path']).name
    assert sha(candidate)==row['candidate_sha256']
    assert sha(ROOT/row['path'])==row['original_sha256']
    assert b'\r' not in candidate.read_bytes()
    compile(candidate.read_bytes(),str(candidate),'exec')
if len(sys.argv)>1:
    mode=sys.argv[1]
    sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'scripts')]
    folder=OUT/('temporary-'+mode);folder.mkdir(exist_ok=True)
    if mode.startswith('short'):
        buffer=ctypes.create_unicode_buffer(32768)
        n=ctypes.windll.kernel32.GetShortPathNameW(str(folder),buffer,len(buffer))
        assert 0<n<len(buffer) and '~' in buffer.value
        alias=Path(buffer.value);assert alias.samefile(folder)
        tempfile.tempdir=str(alias)
        (OUT/(mode+'-temp-identity.json')).write_text(json.dumps(dict(long=str(folder),short=str(alias),samefile=True),indent=2)+'\n')
    else:tempfile.tempdir=str(folder)
    if mode!='short-baseline':
        name='g4usim_gui.core.experiment_bundle'
        spec=importlib.util.spec_from_file_location(name,FINAL/'experiment_bundle.py')
        bundle=importlib.util.module_from_spec(spec);sys.modules[name]=bundle;spec.loader.exec_module(bundle)
    probe_spec=importlib.util.spec_from_file_location('independent_assert_probe',ROOT/'tools/test_assert_probe.py')
    probe=importlib.util.module_from_spec(probe_spec);probe_spec.loader.exec_module(probe)
    target=FINAL/'test_k1_bundle.py' if mode=='full' else ROOT/'scripts/test_k1_workflow.py'
    def run_target(path,run_name=None,**kwargs):
        assert Path(path).resolve()==target.resolve()
        ns={'__name__':run_name if mode=='full' else 'focused_original_source_capture','__file__':str(ROOT/'scripts'/target.name),'__package__':None}
        exec(compile(target.read_bytes(),str(target),'exec'),ns)
        if mode!='full':ns['source_capture_scope']()
        return ns
    probe.runpy.run_path=run_target
    args=['--component','--evidence-root',str(OUT/'full-k1-evidence')] if mode=='full' else []
    raise SystemExit(probe.main(['probe',str(target),*args]))
assert not (OUT/'execution.json').exists()
old_ast=ast.parse((ROOT/'scripts/test_k1_bundle.py').read_bytes())
new_ast=ast.parse((FINAL/'test_k1_bundle.py').read_bytes())
old_functions={n.name:ast.dump(n,include_attributes=False) for n in old_ast.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
new_functions={n.name:ast.dump(n,include_attributes=False) for n in new_ast.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
assert all(new_functions.get(name)==value for name,value in old_functions.items() if name!='main')
bound=[ROOT/row['path'] for row in receipt['files']]+[p for p in FINAL.iterdir() if p.is_file()]
bound += [ROOT/'out/verification/j2-f8-2901f42/ci/extracted/m0-report-windows-latest-13096301546/20261101-183520-77003a77/gui_k1_workflow.log']
before={str(p.relative_to(ROOT)):sha(p) for p in bound}
results=[]
for mode,expected in [('short-baseline',1),('short-candidate',0),('full',0)]:
    result=subprocess.run([sys.executable,'-B',str(Path(__file__)),mode],cwd=ROOT,capture_output=True)
    log=OUT/(mode+'.log');assert not log.exists();log.write_bytes(result.stdout+result.stderr)
    markers=re.findall(rb'G4USIM_ASSERTS=(\d+)',result.stdout)
    results.append(dict(mode=mode,exit_code=result.returncode,expected=expected,assertions=int(markers[-1]) if markers else None,log=log.name,log_sha256=sha(log)))
    print(mode,result.returncode,(result.stdout+result.stderr).decode(errors='replace')[-1800:],flush=True)
after={name:sha(ROOT/name) for name in before};assert before==after
output=dict(status='pass' if all(r['exit_code']==r['expected'] and r['assertions'] for r in results) else 'fail',frozen_receipt_sha256=sha(FINAL/'receipt.json'),patch_sha256=sha(FINAL/'fix.patch'),files=receipt['files'],original_test_functions_ast_unchanged=True,results=results,tracked_author_and_original_ci_log_bytes_unchanged=True,unchanged_sha256=before,method='Original source_capture_scope under real Windows 8.3 TEMP baseline red/candidate green; final draft full original __main__ --component with standard assert probe and in-memory candidate product only. All fixtures under independent out root; no GUI/backend/CI.')
(OUT/'execution.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
raise SystemExit(0 if output['status']=='pass' else 1)
