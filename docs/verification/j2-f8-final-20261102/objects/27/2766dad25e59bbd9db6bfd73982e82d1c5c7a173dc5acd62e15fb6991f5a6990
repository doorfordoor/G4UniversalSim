"""Independent out-only path assertion/closure review. No QApplication or backend."""
import difflib,hashlib,importlib.util,json,re,subprocess,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
AUTHOR=ROOT/'out/collab/j2-geometry-ci-path'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if len(sys.argv)>1:
    temp=OUT/'temporary';temp.mkdir(exist_ok=True);tempfile.tempdir=str(temp)
    spec=importlib.util.spec_from_file_location('independent_assert_probe',ROOT/'tools/test_assert_probe.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    target=OUT/'diagnose_path_identity.py' if sys.argv[1]=='proof' else ROOT/'scripts/test_j2_resource_bundle.py'
    raise SystemExit(probe.main(['probe',str(target)]))
assert not (OUT/'receipt.json').exists()
receipt=json.loads((AUTHOR/'receipt.json').read_bytes())
identity=json.loads((AUTHOR/'source-identity.json').read_bytes())
for name,digest in identity['files'].items():assert sha(ROOT/name)==digest,name
assert sha(AUTHOR/'fix.patch')==receipt['patch_sha256']=='2b3f9b12c58c6c2dcc97ac35d9448897fdf6592518639b7aa644296be7ad6a74'
assert sha(AUTHOR/'smoke_j2_geometry.py')==receipt['candidate_smoke_sha256']=='579c6a7a00a93a41570aa28357053d3009b1c2758cf005ccf6de78477fb5b671'
original=(ROOT/'gui/smoke_tests/smoke_j2_geometry.py').read_text(encoding='utf-8')
candidate=(AUTHOR/'smoke_j2_geometry.py').read_text(encoding='utf-8')
expected=original.replace('assert f\'file = {folder / "mesh.stl"}\' in generated','assert f\'file = {(folder / "mesh.stl").resolve()}\' in generated')
anchor='        restored=document(generated,second)\n'
extra="        restored_mesh=next(row for row in restored.volumes if row.shape=='tessellated')\n        restored_mesh_path=Path(restored_mesh.shape_properties['file'])\n        assert restored_mesh_path.samefile(folder/'mesh.stl')\n        assert hashlib.sha256(restored_mesh_path.read_bytes()).hexdigest()==hashlib.sha256((folder/'mesh.stl').read_bytes()).hexdigest()\n"
assert expected.replace(anchor,anchor+extra)==candidate,'Unexpected candidate change'
for name,row in receipt['tests'].items():assert sha(AUTHOR/name)==row['sha256'],name
before={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/n for n in identity['files']]+list(AUTHOR.glob('*')) if p.is_file()}
copy=OUT/'diagnose_path_identity.py';assert not copy.exists();copy.write_bytes((AUTHOR/'diagnose_path_identity.py').read_bytes())
results=[]
for kind in ('proof','closure'):
    log=OUT/(kind+'.log');assert not log.exists()
    result=subprocess.run([sys.executable,'-B',str(Path(__file__)),kind],cwd=ROOT,capture_output=True)
    raw=result.stdout+result.stderr;log.write_bytes(raw)
    markers=re.findall(rb'G4USIM_ASSERTS=(\d+)',raw)
    results.append(dict(kind=kind,exit_code=result.returncode,assertions=int(markers[-1]) if markers else None,log=log.name,log_sha256=sha(log)))
    print(raw.decode(errors='replace')[-2200:])
after={name:sha(ROOT/name) for name in before};assert before==after
proof=json.loads((OUT/'path-proof.json').read_bytes())
assert [r['old_text_assert'] for r in proof['results']]==[True,False]
assert all(r['samefile'] and r['sha256']==r['closure_receipt_sha256'] for r in proof['results'])
assert proof['missing_resource_rejected'] and proof['outside_resource_rejected']
status=subprocess.run(['git','-c','core.longpaths=true','status','--porcelain','--untracked-files=no'],cwd=ROOT,capture_output=True,check=True)
output=dict(status='pass' if all(r['exit_code']==0 and r['assertions'] for r in results) else 'fail',patch_sha256=sha(AUTHOR/'fix.patch'),candidate_smoke_sha256=sha(AUTHOR/'smoke_j2_geometry.py'),only_resolve_expectation_and_samefile_sha_added=True,results=results,real_windows_short_alias_old_assert_failure_reproduced=True,generated_reparsed_same_stl_identity_and_sha=True,missing_and_outside_rejections_preserved=True,original_tracked_and_author_evidence_bytes_unchanged=True,source_sha256=identity['files'],tracked_status_longpaths=status.stdout.decode(),full_gui_smoke_run=False,native_or_backend_run=False)
(OUT/'receipt.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
print(json.dumps(output,indent=2))
raise SystemExit(0 if output['status']=='pass' else 1)
