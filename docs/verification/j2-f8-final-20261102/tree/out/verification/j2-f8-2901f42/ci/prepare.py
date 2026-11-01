"""Bind offline collection tools to second candidate; write only this out root."""
import hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
HEAD='2901f4254303c3a9089c9025717908c0d77ff190'
OLD='56b689fb9ac920cbb1203b2b94dae2483d25f622'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip()==HEAD
def save(name,value):
    p=ROOT/name;assert not p.exists();p.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())
spec=importlib.util.spec_from_file_location('candidate_runner',REPO/'scripts/run_m0_tests.py')
runner=importlib.util.module_from_spec(spec);sys.modules[spec.name]=runner;spec.loader.exec_module(runner)
save('frozen-local-identity.json',dict(candidate_head=HEAD,source_fingerprint=runner.workspace_source_fingerprint(),tests_content_fingerprint=runner.tests_content_fingerprint()))
raw=subprocess.check_output(['git','show',HEAD+':scripts/check_report_evidence.py'],cwd=REPO)
p=ROOT/'checker-2901f42.py';assert not p.exists();p.write_bytes(raw)
save('checker-identity.json',dict(head=HEAD,sha256=hashlib.sha256(raw).hexdigest()))
for name in ('analyze_reports.py','verify_installation.py'):
    text=(REPO/'out/verification/j2-f8-56b689f/ci'/name).read_text(encoding='utf-8')
    text=text.replace(OLD,HEAD).replace('checker-56b689f.py','checker-2901f42.py').replace('j2_candidate_56b689f_gate','j2_candidate_2901f42_gate')
    if name=='analyze_reports.py':
        text=text.replace("c.read(p).get('artifacts',[])","(c.read(p).get('structuredContent') or c.read(p)).get('artifacts',[])")
    p=ROOT/name;assert not p.exists();p.write_text(text,encoding='utf-8',newline='\n')
for name in ('artifacts','extracted'): (ROOT/name).mkdir(exist_ok=True)
status=subprocess.run(['git','status','--porcelain','-z','--untracked-files=no'],cwd=REPO,capture_output=True)
records=[s.decode(errors='replace') for s in status.stdout.split(b'\0') if s]
save('local-worktree-observation.json',dict(head=HEAD,tracked_status_count=len(records),records=records,diagnostic=status.stderr.decode(errors='replace'),note='Previously observed long-path historical checkout deletions remain distinct from remote CI. No checkout/config repair performed.'))
print(json.dumps(json.loads((ROOT/'frozen-local-identity.json').read_bytes())))
