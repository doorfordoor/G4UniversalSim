"""Out-only code loader; original __file__ for ROOT and official v3 probe for candidate bytes."""
import sys,os,json,hashlib,runpy,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
draft=ROOT/'out/verification/j2-f8-56b689f/windows-gui/test-fix-draft'/sys.argv[1]
OUT=Path(sys.argv[2]);OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
original=ROOT/'gui/smoke_tests'/draft.name
before={str(p.resolve()):sha(p) for p in (ROOT/'gui/g4usim_gui').rglob('*.py')}
base_temp=tempfile.TemporaryDirectory
class EvidenceTemporaryDirectory(base_temp):
 def cleanup(self):
  if not getattr(self,'_audit_copied',False) and Path(self.name).exists():
   self._audit_copied=True
   target=OUT/'temp-evidence'/Path(self.name).name
   target.parent.mkdir(exist_ok=True)
   shutil.copytree(self.name,target)
  return super().cleanup()
tempfile.TemporaryDirectory=EvidenceTemporaryDirectory
real_run_path=runpy.run_path
def load_out(path,init_globals=None,run_name=None):
 if Path(path).resolve()!=draft.resolve():return real_run_path(path,init_globals=init_globals,run_name=run_name)
 namespace=dict(init_globals or {});namespace.update(__file__=str(original),__name__=run_name or '__main__',__package__=None,__cached__=None,__spec__=None)
 exec(compile(draft.read_bytes(),str(draft.resolve()),'exec'),namespace)
 return namespace
runpy.run_path=load_out
sys.path.insert(0,str(ROOT/'tools'))
import test_assert_probe
status=1
try:
 status=test_assert_probe.main(['test_assert_probe.py',str(draft)])
finally:
 files=sorted({str(Path(m.__file__).resolve()) for m in list(sys.modules.values()) if getattr(m,'__file__',None) and str(Path(m.__file__).resolve()).startswith(str((ROOT/'gui/g4usim_gui').resolve())) and Path(m.__file__).suffix=='.py'})
 dependencies=[dict(path=p,sha256_before=before.get(p),sha256_after=sha(Path(p))) for p in files]
 (OUT/'entry-identity.json').write_text(json.dumps(dict(python=sys.executable,original_file_binding=str(original),candidate_code=str(draft),candidate_sha256=sha(draft),assert_probe='settrace_assert_lines_v3',qt_qpa_platform=os.environ.get('QT_QPA_PLATFORM'),dependencies=dependencies,dependencies_unchanged=all(x['sha256_before']==x['sha256_after'] for x in dependencies)),indent=2)+'\n',encoding='utf-8')
raise SystemExit(status)
