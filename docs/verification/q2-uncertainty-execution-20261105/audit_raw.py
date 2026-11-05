"""Independent Decimal audit of the immutable Q2-4 run archive."""
from collections import Counter
import csv
from decimal import Decimal as D, getcontext
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

getcontext().prec = 64
base = Path(__file__).parent
repo = base.parents[2]
delivery = Path("D:/Geant4/G4UniversalSim")
freeze_path = delivery / "docs/collab/decisions/20261105-q2-uncertainty-freeze-v1.json"
freeze = json.loads(freeze_path.read_bytes())
sha = lambda b: sha256(b).hexdigest()
checks = Counter()
issues = []


def check(group, condition, detail):
    checks[group] += 1
    if not condition:
        issues.append((group, detail))


def bounds(text):
    x = D(text)
    h = D(5).scaleb(x.adjusted()-12) if x else D(0)
    return x-h, x+h


def sum_bounds(values, square=False):
    b = [bounds(v) for v in values]
    return tuple(sum((x[i]**2 if square else x[i] for x in b), D(0)) for i in (0,1))


def intersects(text, lo, hi=None):
    a,b = bounds(text)
    return a <= (lo if hi is None else hi) and lo <= b


def sq_intersects(text, lo, hi):
    a,b = bounds(text)
    return a*a <= hi and lo <= b*b


z = ZipFile(base/"original-v1.zip")
names = set(z.namelist())
read = z.read
def obj(p):
    return json.loads(read(p))


def rows(p):
    return list(csv.DictReader(read(p).decode("utf-8").splitlines()))


def summary(p):
    return dict(line.split(" = ",1) for line in read(p).decode("utf-8").splitlines() if " = " in line)


def metadata_id():
    ident = obj("identity.json")
    fsha = sha(freeze_path.read_bytes())
    check("identity", fsha == "5768cc413d7e05b586fdbe8074342e52ec14cdbf27fbc037163604775e0381b6", "freeze")
    mpath = delivery / freeze["inputs"]["manifest"]
    check("identity", sha(mpath.read_bytes()) == freeze["inputs"]["manifest_sha256"], "input manifest")
    manifest = json.loads(mpath.read_bytes())["files"]
    check("identity", len(manifest) == 17 and set(manifest) == set(ident["inputs"]), "frozen input closure")
    for name, expected in manifest.items():
        check("identity", expected == sha(read("inputs/"+name)) == ident["inputs"][name]["sha256"], name)
    exe = repo/"out/collab/q2-backend-864bc036/G4UniversalSim.exe"
    check("identity", sha(exe.read_bytes()) == "f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f", "C backend")
    for p,h in ident["component_production_sources"].items():
        check("identity", sha((repo/p).read_bytes()) == h, p)
    return ident


def run_identity(path, n, threads, seed, coverage):
    record = obj(path+"/record.json")
    out = path+"/output/"
    facts = summary(out+"run_summary.txt")
    m = obj(out+"run_metadata.json")
    vals = m["values"]
    for key,value in {"status":"completed","program_exit_code":"0","run_count":"1",
                      "actual_completed_event_count":str(n),"actual_threads":str(threads),
                      "seed":str(seed),"planned_seed":str(seed),"output_failure_status":"none",
                      "summary_write_status":"completed",
                      "build_git_commit":"864bc036d6d7752475e52db4efd2b950cabfcc3d"}.items():
        check("run", facts.get(key) == value, (path,key,facts.get(key),value))
    check("run", record["exit_code"] == 0 and record["expected_events"] == n and record["threads"] == threads
          and record["identity_sha256"] == sha(read("identity.json")), path)
    check("run", m["schema"] == "run_metadata_json_v1" and len(m["runs"]) == 1
          and m["runs"][0] == {"run_id":0,"planned_events":n,"completed_events":n}
          and int(vals["actual_completed_event_count"]) == n and int(vals["actual_threads"]) == threads, path)
    if coverage:
        cmd=record["command"]
        check("run", facts["effective_seed_origin_kind"] == "cli" and int(facts["effective_configured_seed"]) == seed
              and int(cmd[cmd.index("--seed")+1]) == seed, path)
    listed=set()
    for item in m["generated_files"]:
        basename=Path(item["path"]).name
        check("metadata", basename not in listed, (path,basename,"duplicate"))
        listed.add(basename)
        if basename == "run_metadata.json":
            check("metadata", item["integrity_status"] == "self_reference_excluded" and item["sha256"] is None, path)
            continue
        data=read(out+basename)
        check("metadata", sha(data) == item["sha256"] and len(data) == item["size_bytes"], (path,basename))
    check("metadata", listed == {x.removeprefix(out) for x in names if x.startswith(out)}, path)
    for item in record["artifacts"].values():
        b=read(item["path"].removeprefix("out/collab/q2-uncertainty-v1/"))
        check("record", sha(b)==item["sha256"] and len(b)==item["size_bytes"], item["path"])
    return out


def worker_rows(out, prefix):
    return [r for p in sorted(names) if p.startswith(out+prefix+"_t") and p.endswith(".csv") for r in rows(p)]


def dose(out,n,mass):
    ev=worker_rows(out,"event_edep")
    check("dose", sorted(int(r["eventID"]) for r in ev) == list(range(n)), out)
    d=worker_rows(out,"dose_volume_summary")
    check("dose", bool(d) and all(intersects(r["mass_kg"],mass) for r in d), out)
    stats={r["quantity"]:r for r in rows(out+"scorer_statistics.csv") if r["scorer"]=="dose"}
    check("dose", set(stats)=={"raw_dose","weighted_dose"}, out)
    factor=D("1.602176634e-13")/mass
    for mode in ("raw","weighted"):
        values=[r[mode+"_edep_MeV"] for r in ev]
        s=sum_bounds(values); s2=sum_bounds(values,True)
        a=sum_bounds([r[mode+"_dose_Gy"] for r in d])
        check("dose", a[0] <= s[1]*factor and a[1] >= s[0]*factor, (out,mode,"workers"))
        srow=stats[mode+"_dose"]
        check("dose", int(srow["n_events"])==n and int(srow["entries"])==sum(D(v)!=0 for v in values)
              and srow["unit"]=="Gy" and srow["uncertainty_estimator"]=="uncorrected_event_moments_v1"
              and srow["uncertainty_status"]=="approximate", (out,mode,"stat facts"))
        check("dose", intersects(srow["sum"],s[0]*factor,s[1]*factor)
              and intersects(srow["sum_sq"],s2[0]*factor**2,s2[1]*factor**2), (out,mode,"stat moments"))
        rlo=max(D(0),s2[0]/s[1]**2-1/D(n))
        rhi=max(D(0),s2[1]/s[0]**2-1/D(n))
        check("dose", sq_intersects(srow["rel_error"],rlo,rhi), (out,mode,"stat R"))
    return sum(D(r["raw_edep_MeV"])==0 for r in ev)


def let(out,n):
    workers=worker_rows(out,"let_volume_summary")
    sts={r["quantity"]:r for r in rows(out+"scorer_statistics.csv") if r["scorer"]=="let"}
    check("let", bool(workers) and set(sts)=={"let_t","let_d"},out)
    sums=["sum_wl_mm","sum_wSl_MeV","sum_wS2l_MeV2_per_mm"]
    squares=["sum_sq_wl_mm2","sum_sq_wSl_MeV2","sum_sq_wS2l_MeV4_per_mm2"]
    cross=["sum_wl_x_wSl_MeV_mm","sum_wSl_x_wS2l_MeV3_per_mm"]
    zsum=lambda key:sum_bounds([r[key] for r in workers])
    for i,q in enumerate(("let_t","let_d")):
        den,num,sd,sn,co=map(zsum,(sums[i],sums[i+1],squares[i],squares[i+1],cross[i]))
        row=sts[q]
        check("let", row["unit"]=="keV/um" and int(row["n_events"])==n
              and row["uncertainty_estimator"]=="uncorrected_delta_ratio_v1"
              and row["uncertainty_status"]=="approximate", (out,q,"stat facts"))
        check("let", intersects(row["value"],num[0]/den[1],num[1]/den[0]),(out,q,"ratio"))
        lo=sn[0]/num[1]**2+sd[0]/den[1]**2-2*co[1]/(num[0]*den[0])
        hi=sn[1]/num[0]**2+sd[1]/den[0]**2-2*co[0]/(num[1]*den[1])
        check("let", sq_intersects(row["rel_error"],max(D(0),lo),hi),(out,q,"covariance"))


def path_moments(out,n):
    [p]=rows(out+"fluence_volume_summary_t0.csv")
    stats={r["quantity"]:r for r in rows(out+"scorer_statistics.csv")}
    k=int((10*D(p["raw_track_length_mm"])).to_integral_value())
    check("coverage", intersects(p["volume_mm3"],D(10)) and int(p["n_events"])==n and 0<k<n, out)
    check("coverage", set(stats)=={"raw_fluence","weighted_fluence"},out)
    s=D(k)/100
    s2=D(k)/10000
    r2=1/D(k)-1/D(n)
    for mode in ("raw","weighted"):
        row=stats[mode+"_fluence"]
        check("coverage", intersects(p[mode+"_track_length_mm"],D(k)/10)
              and intersects(p[mode+"_track_length_sum_sq_mm2"],D(k)/100)
              and intersects(p[mode+"_fluence_mm-2"],s),(out,mode,"path"))
        check("coverage", int(row["entries"])==k and int(row["n_events"])==n and row["unit"]=="mm-2"
              and row["uncertainty_estimator"]=="uncorrected_event_moments_v1" and row["uncertainty_status"]=="approximate",
              (out,mode,"stat facts"))
        check("coverage", intersects(row["value"],s) and intersects(row["sum"],s)
              and intersects(row["sum_sq"],s2) and sq_intersects(row["rel_error"],r2,r2),
              (out,mode,"moments"))
    return k


metadata_id()
fixed = {"unc_tot":(20,1,20261120),"unc_n1":(1,1,20261121),"unc_zero":(100,1,20261122),
         "unc_let_cov":(2000,1,20261123),"unc_mt_sparse":(2,4,20261124)}
coverage = {f"unc_coverage/batch_{i:03d}":(2000,1,220001+i) for i in range(64)}
expected = fixed | coverage
check("run", {p.removeprefix("runs/").removesuffix("/record.json") for p in names if p.startswith("runs/")
              and p.endswith("/record.json")} == set(expected), "exactly 69 records")
outs = {p:run_identity("runs/"+p,*spec,p in coverage) for p,spec in expected.items()}
zeros=dose(outs["unc_tot"],20,D("4.66e-6"))
dose(outs["unc_mt_sparse"],2,D("4.66e-4"))
for p in ("unc_let_cov","unc_mt_sparse"):
    let(outs[p],fixed[p][0])
n1 = rows(outs["unc_n1"]+"scorer_statistics.csv")
check("boundaries", len(n1)==4 and all(r["n_events"]=="1" and r["uncertainty_status"]=="insufficient_events"
      and D(r["value"])>0 for r in n1), "N1")
zero=outs["unc_zero"]
check("boundaries", zero+"scorer_statistics.csv" not in names and not worker_rows(zero,"dose_volume_summary")
      and not worker_rows(zero,"let_volume_summary")
      and all(zero+name+"_t0.csv" in names for name in ("dose_volume_summary","let_volume_summary")), "ZERO")
ks=[path_moments(outs[p],2000) for p in coverage]
covered=[2000*(144*k-200000)**2 <= 4*144**2*k*(2000-k) for k in ks]
check("coverage", sum(covered)>=57 and 88464<=sum(ks)<=89313,"aggregate")
check("coverage", covered==[1347<=k<=1429 for k in ks],"integer test range")
report=dict(status="failed" if issues else "passed", checks=checks, problems=issues, run_count=len(outs),
            planned_events=sum(n for n,_,_ in expected.values()), zero_dose_events=zeros,
            K=ks, covered=sum(covered), total_K=sum(ks),
            uncovered=[dict(batch=i,K=k,seed=220001+i) for i,k in enumerate(ks) if not covered[i]])
(base/"independent-raw-report.json").write_bytes((json.dumps(report,indent=2)+"\n").encode())
print({k:v for k,v in report.items() if k not in ("K","problems")},issues[:12])
raise SystemExit(bool(issues))
