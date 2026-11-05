"""Verify the stopped r1 delivery against the pre-revision bytes."""
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

base=Path(__file__).parent
d=Path("D:/Geant4/G4UniversalSim")
src=d/"out/collab/q2-uncertainty-v1"
def readj(p):
    return json.loads(p.read_bytes())
def digest(b):
    return sha256(b).hexdigest()

v1=readj(base/"original-v1-manifest.json")
protected={n:v for n,v in v1.items()
           if n.startswith(("runs/","inputs/")) or n in ("identity.json","inputs_manifest.json")}
assert set(protected)=={p.relative_to(src).as_posix() for root in ("runs","inputs")
                        for p in (src/root).rglob("*") if p.is_file()} | {"identity.json","inputs_manifest.json"}
for n,v in protected.items():
    raw=(src/n).read_bytes()
    assert len(raw)==v["bytes"] and digest(raw)==v["sha256"], n

res=readj(src/"results.json")
ev=res["evaluation"]
checks={r["id"]:r["status"] for r in ev["checks"]}
assert ev["status"]=="pass" and len(checks)==len(ev["checks"]) and set(checks.values())=={"pass"}
assert checks["CMP-WORKER-MERGE"]==checks["MT-LET-MERGE"]==checks["COV-PATH"]=="pass"
neg=readj(src/"tamper-results.json")
assert neg["status"]=="pass" and neg["originals_unchanged"] and neg["detected"]==neg["cases_total"]==8
assert neg["additional_detected"]==neg["additional_total"]==2
for row in neg["cases"]+neg["additional_minimal_checks"]:
    assert row["detected"] and row["status"]=="fail" and row["expected_failed_check"] in row["failed_ids"],row
    if row["counterexample"]=="ce-worker-average":
        assert row["failed_ids"]==["MT-DOSE-STATS"],row

p=readj(src/"probe/probe_results.json")
assert p["build"]["exit_code"]==p["run_exit_code"]==0 and p["ok"] and len(p["fixtures"])==7
assert digest((src/"probe/history_statistics_probe.cc").read_bytes())==p["build"]["probe_sha256"]
assert digest((src/"probe/history_statistics_probe.exe").read_bytes())==p["binary_sha256"]
assert p["worker_merge"]["merged"]=={"sum":6,"sum_sq":18,"entries":3,"relative_error":.5}
assert p["worker_merge"]["wrong_average_relative_error"]==readj(base/"merge-probe.json")["wrong_average"]

selected={}
for path in src.rglob("*"):
    if not path.is_file() or path.suffix==".exe":
        continue
    n=path.relative_to(src).as_posix()
    if n not in protected and (n not in v1 or digest(path.read_bytes())!=v1[n]["sha256"]):
        selected[n]=path
selected["delivery-r1.md"]=d/"docs/collab/outbox/20261105-q2-uncertainty-v1-r1.md"
out=base/"revision-r1.zip"
m={}
with ZipFile(out,"x",ZIP_DEFLATED,compresslevel=3) as z:
    for n,path in sorted(selected.items()):
        raw=path.read_bytes()
        m[n]={"bytes":len(raw),"sha256":digest(raw)}
        z.writestr(n,raw)
with ZipFile(out) as z:
    assert z.testzip() is None and set(z.namelist())==set(m)
    assert all(digest(z.read(n))==r["sha256"] for n,r in m.items())
assert all(digest(selected[n].read_bytes())==r["sha256"] for n,r in m.items())
receipt=dict(status="passed", protected_files=len(protected), original_run_files=sum(n.startswith("runs/") for n in protected),
             author_positive_checks=len(checks), author_frozen_negatives=8, author_targeted_negatives=2,
             archive=dict(bytes=out.stat().st_size,sha256=digest(out.read_bytes()),members=len(m)),file_manifest=m)
(base/"r1-seal.json").write_bytes((json.dumps(receipt,indent=2)+"\n").encode())
print(json.dumps({k:v for k,v in receipt.items() if k!="file_manifest"}))
