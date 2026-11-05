"""Show whether the two frozen numeric checks catch specific bad CSV values."""
import csv
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from zipfile import ZipFile

base=Path(__file__).parent
version=sys.argv[1]
assert version in ("v1","r1")
work=base/("witness-"+version)
work.mkdir()
with ZipFile(base/"original-v1.zip") as z:
    if version=="v1":
        compare=z.read("compare.py")
    else:
        compare=Path("D:/Geant4/G4UniversalSim/out/collab/q2-uncertainty-v1/compare.py").read_bytes()
    (work/"compare.py").write_bytes(compare)
    spec=importlib.util.spec_from_file_location("compare",work/"compare.py")
    m=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=m
    spec.loader.exec_module(m)
    for p in z.namelist():
        if (p.endswith(".csv") and (p.startswith("runs/unc_mt_sparse/output/") or
                (p.startswith("runs/unc_coverage/") and p.endswith(("fluence_volume_summary_t0.csv","scorer_statistics.csv"))))):
            dst=work/p
            dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_bytes(z.read(p))
    records={}
    for i in range(64):
        rel=f"unc_coverage/batch_{i:03d}"
        r=json.loads(z.read("runs/"+rel+"/record.json"))
        r["output_dir"]=str((work/"runs"/rel/"output").resolve())
        records[f"UNC-COVERAGE/batch_{i:03d}"]=r
    identity=json.loads(z.read("identity.json"))


def change(path,q,key,text):
    with path.open(encoding="utf-8",newline="") as s:
        rows=list(csv.DictReader(s))
    [row]=[r for r in rows if r["quantity"]==q]
    old=row[key]
    row[key]=text
    with path.open("w",encoding="utf-8",newline="") as s:
        w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return old


def test(fn,key):
    ch=[]
    fn(ch)
    [r]=[x for x in ch if x["id"]==key]
    return r["status"]


mt=work/"runs/unc_mt_sparse/output"
mc=lambda ch:m.mt_checks(ch,mt)
cc=lambda ch:m.coverage_checks(ch,identity,records)
base_mt=test(mc,"MT-LET-MERGE")
base_cov=test(cc,"COV-PATH")
old_let=change(mt/"scorer_statistics.csv","let_t","value","100")
old_entry=change(work/"runs/unc_coverage/batch_000/output/scorer_statistics.csv","raw_fluence","entries","1")
got=dict(version=version,compare_sha256=sha256(compare).hexdigest(),
         mt=dict(baseline=base_mt,old=old_let,new="100",tampered=test(mc,"MT-LET-MERGE")),
         coverage=dict(baseline=base_cov,old=old_entry,new="1",tampered=test(cc,"COV-PATH")))
(work/"report.json").write_bytes((json.dumps(got,indent=2)+"\n").encode())
print(json.dumps(got))
assert base_mt==base_cov=="pass"
assert all(got[p]["tampered"]==("pass" if version=="v1" else "fail") for p in ("mt","coverage")),got
