"""R27 portable manifests, stale workers, CLI/GUI agreement and explicit-list compatibility."""
from pathlib import Path
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
sys.path.insert(0, str(ROOT))
from g4usim_gui.output.provenance import output_evidence, ProvenanceError
from g4usim_gui.output.dose_summary import read_dose_summaries, COLUMNS as DOSE
from g4usim_gui.output.fluence_summary import read_fluence_summaries, COLUMNS as FLUENCE
from g4usim_gui.output import plot_data
from g4usim_gui.output.merge_plan import build_merge_plan
from scripts.extensions.dose_json_extension import process as dose_json
from scripts.extensions.fluence_json_extension import process as fluence_json
from scripts.merge_outputs import resolve_files


def reject(call):
    try:
        call()
    except (ProvenanceError, ValueError):
        return
    assert False, "invalid provenance was accepted"


def fixture(root):
    root.mkdir()
    def write(name, row):
        with (root / name).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, list(row)); writer.writeheader(); writer.writerow(row)
    dose = dict(runID=0,volume_path="/world/T",volume_name="T",mass_kg=1,raw_edep_MeV=1,
                weighted_edep_MeV=1,raw_dose_Gy=1.602176634e-13,weighted_dose_Gy=1.602176634e-13)
    assert set(dose) == DOSE
    write("dose_volume_summary_t0.csv",dose)
    fluence = dict(runID=0,volume_path="/world/T",volume_name="T",volume_mm3=1,raw_track_length_mm=1,
                   weighted_track_length_mm=1,**{"raw_fluence_mm-2":1,"weighted_fluence_mm-2":1})
    assert set(fluence) == FLUENCE
    write("fluence_volume_summary_t0.csv",fluence)
    write("event_edep_t0.csv",dict(runID=0,eventID=0,raw_edep_MeV=1,weighted_edep_MeV=1))
    (root / "run_summary.txt").write_text("status = completed\n")
    names=[p.name for p in root.iterdir()]+["run_metadata.json"]
    doc={"schema":"run_metadata_json_v1","runs":[{"run_id":0,"completed_events":1}],
         "generated_files":[{"path":(root.resolve()/n).as_posix(),"schema":"test_fixture"} for n in names]}
    (root / "run_metadata.json").write_text(json.dumps(doc))
    return doc


def check(root):
    d,w=read_dose_summaries(root);f,fw=read_fluence_summaries(root)
    assert all("content hashes" in item for item in [*w, *fw]) and w and fw and len(d)==len(f)==1
    assert d[0].raw_edep_MeV == f[0].raw_track_length_mm == 1
    assert dose_json(root)["volumes"][0]["raw_edep_MeV"] == d[0].raw_edep_MeV
    assert fluence_json(root)["provenance"] == "registered_manifest"
    datasets=plot_data.discover(root)
    pulse=next(d for d in datasets if d.kind=="pulse")
    p=plot_data.build_plot(root,pulse)
    assert any(args.get("events")==1 for _,args in p.notes)
    task=next(t for t in build_merge_plan(str(root),str(ROOT)).tasks if t.kind=="event_edep")
    assert task.available and len(task.matched_files)==1
    assert "--input" not in task.command_args


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--backend",action="store_true");args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="q1-provenance-") as temp:
        work=Path(temp);root=work/"results";doc=fixture(root)
        check(root)
        for extension in ("dose_json", "fluence_json"):
            exported=work/f"{extension}.json"
            result=subprocess.run([sys.executable,str(ROOT/"scripts/run_output_extension.py"),"--run",extension,
                                   "--input-dir",str(root),"--output",str(exported)],capture_output=True,text=True)
            assert result.returncode==0,result.stderr
            assert json.loads(exported.read_text())["data"]["provenance"]=="registered_manifest"
        for stem in ("dose_volume_summary","fluence_volume_summary","event_edep"):
            shutil.copyfile(root/f"{stem}_t0.csv",root/f"{stem}_t1.csv")
            shutil.copyfile(root/f"{stem}_t0.csv",root/f"{stem}_t1_r1.csv")
        check(root)
        moved=work/"portable";shutil.copytree(root,moved);check(moved)
        assert len(resolve_files(str(root),"event_edep_t*.csv",[]))==1
        assert len(resolve_files(None,"",[str(root/"event_edep_t1.csv")]))==1
        manifest=root/"run_metadata.json"
        relative_doc={**doc,"generated_files":[{**row,"path":row["path"].rsplit("/",1)[-1]} for row in doc["generated_files"]]}
        manifest.write_text(json.dumps(relative_doc));check(root)
        for source in (doc, relative_doc):
            for required in ("run_metadata.json", "run_summary.txt"):
                omitted={**source,"generated_files":[row for row in source["generated_files"] if not row["path"].endswith(required)]}
                manifest.write_text(json.dumps(omitted));reject(lambda: output_evidence(root))
        for mutation in ({**doc,"generated_files":[]}, "broken", {**doc,"schema":"bad"}, {**doc,"generated_files":None},
                         {**doc,"generated_files":doc["generated_files"]+[doc["generated_files"][0]]},
                         {**doc,"generated_files":[{"path":"../escape.csv","schema":"x"}]}):
            manifest.write_text(mutation if isinstance(mutation,str) else json.dumps(mutation))
            reject(lambda: read_dose_summaries(root));reject(lambda: dose_json(root))
            reject(lambda: plot_data.discover(root))
            assert not any(t.available for t in build_merge_plan(str(root),str(ROOT)).tasks)
        manifest.write_text(json.dumps(doc))
        (root/"event_edep_t0.csv").unlink()
        reject(lambda: read_fluence_summaries(root))  # even an unrelated missing registered file invalidates the set
        failed=work/"must-not-publish.json"
        result=subprocess.run([sys.executable,str(ROOT/"scripts/run_output_extension.py"),"--run","dose_json",
                               "--input-dir",str(root),"--output",str(failed)],capture_output=True,text=True)
        assert result.returncode!=0 and not failed.exists()
        manifest.unlink()
        assert output_evidence(root).status=="legacy_unverified"
        assert any("Legacy/unverified" in w for w in read_dose_summaries(root)[1])
        assert dose_json(root)["provenance"]=="legacy_unverified"
        if args.backend:
            from test_q1_results_backend import run
            exe=Path(os.environ["G4USIM_EXE"])
            for threads in (1,2):
                output=run(exe,work/f"real-{threads}",[1]*4,threads=threads)
                before=read_dose_summaries(output)[0]
                selected=output_evidence(output).matching("dose_volume_summary_t*.csv")
                shutil.copyfile(selected[0],output/"dose_volume_summary_t99.csv")
                assert read_dose_summaries(output)[0]==before
                clone=work/f"clone-{threads}";shutil.copytree(output,clone)
                assert read_dose_summaries(clone)[0]==before
                mac=output.parent/"multi.mac";mac.write_text("/run/initialize\n/run/beamOn 2\n/run/beamOn 2\n")
                command=[str(exe),"--config",str(output.parent/"main.ini"),"--macro",str(mac),"--output",str(output)]
                result=subprocess.run(command,capture_output=True,timeout=120)
                assert result.returncode==0,result.stderr[-2000:]
                assert {r.run_id for r in read_dose_summaries(output)[0]}=={0,1}
                mac.write_text("/run/initialize\n/run/beamOn 1\n")
                result=subprocess.run(command+["--threads","1"],capture_output=True,timeout=120)
                assert result.returncode==0,result.stderr[-2000:]
                assert {r.run_id for r in read_dose_summaries(output)[0]}=={0}
                assert len(output_evidence(output).matching("dose_volume_summary_t*.csv"))==1
    print("test_output_provenance: OK")


if __name__=="__main__":main()
