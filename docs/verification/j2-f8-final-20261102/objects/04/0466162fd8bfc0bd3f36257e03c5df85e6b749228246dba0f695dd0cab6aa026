"""Re-execute frozen author's small real-junction probes under independent out root."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'junction-probes'
FINAL=ROOT/'out/collab/j2-resource-policy-path-review/final-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(FINAL/'experiment_bundle.py')=='4990d9f4439711f96aa5a5475f6f39ea3588b8c1e3fabf7e3e2eca0318a45610'
OUT.mkdir(exist_ok=False)
for name in ('experiment_bundle.py','link_probe.py','late_resource_policy_probe.py'):
    (OUT/name).write_bytes((FINAL/name).read_bytes())
rows=[]
for name in ('link_probe.py','late_resource_policy_probe.py'):
    result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/test_assert_probe.py'),str(OUT/name)],cwd=ROOT,capture_output=True)
    log=OUT/(name+'.log');log.write_bytes(result.stdout+result.stderr)
    rows.append(dict(script=name,exit_code=result.returncode,log_sha256=sha(log)))
    print((result.stdout+result.stderr).decode(errors='replace'))
assert all(r['exit_code']==0 for r in rows)
(OUT/'receipt.json').write_text(json.dumps(dict(status='pass',rows=rows,copy_product_sha256=sha(OUT/'experiment_bundle.py'),scope='Real junction rejection for policy and resource inputs, then a resource turned into a junction after read before policy comparison; all fixture paths in independent out root.'),indent=2)+'\n',encoding='utf-8')
