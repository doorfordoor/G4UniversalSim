#!/usr/bin/env python3
"""Real 2C biasing origin/default/identity and scoped worker evidence regression."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def identity(particle, process):
    token = "xs:" + json.dumps([particle.lower(), process], separators=(",", ":"))
    return "/biasing/objects/" + token.replace("~", "~0").replace("/", "~1") + "/"


def main():
    exe = Path(os.environ["G4USIM_EXE"]).resolve()
    assert exe.is_file(), exe
    with tempfile.TemporaryDirectory(prefix="g4usim-2c-bias-") as temp:
        work=Path(temp)
        geometry=work/"geometry.ini"
        geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n[volume.Target]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\nmaterial=G4_WATER\nbias=true\n",encoding="utf-8")
        counter=0
        def config(rules,threads=1,mode=None,enabled=True):
            nonlocal counter
            counter+=1
            path=work/f"case{counter}.ini"
            policy="" if mode is None else f"[modules]\nbiasing={mode}\n"
            gate="" if enabled is None else "[biasing]\nenabled="+("true" if enabled else "false")+"\n"
            path.write_text(policy+f"[run]\nthreads={threads}\nseed=12345\n[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\n[physics]\nreference=\nmodules=G4EmStandardPhysics_option4\n[source]\npreset=mono_proton\nenergy=2 MeV\nposition=0,0,0 mm\n"+gate+rules,encoding="utf-8")
            return path
        def dump(rules,mode=None,enabled=True,bad=False):
            ini=config(rules,mode=mode,enabled=enabled);target=work/f"dump{counter}.json"
            result=subprocess.run([str(exe),"--config",str(ini),"--dump-effective-config",str(target)],cwd=work,capture_output=True,text=True,timeout=90)
            if bad:
                assert result.returncode!=0,result.stdout+result.stderr
                assert not target.exists(),target
                return {}
            assert result.returncode==0,result.stdout+result.stderr
            data=json.loads(target.read_text());fields={f["path"]:f for f in data["fields"]}
            for f in fields.values():
                if f["path"].startswith("/biasing/"):
                    assert f["application_status"]=="not_applied",f
                    for o in f["origins"]:
                        if o["kind"]=="main_ini":assert o["input_sha256"]==hashlib.sha256(ini.read_bytes()).hexdigest(),o
            return fields
        rule="[biasing.xs.proton.hIoni]\nname=same\nfactor=2\nfactor=3\nvolumes=Target\n"
        candidate="[biasing.xs.proton.hIoni]\nfactor=2\nvolumes=Target\n"
        for mode in ("auto","on"):
            discovered=dump(candidate,mode=mode,enabled=None)
            assert discovered[identity("proton","hIoni")+"factor"]["resolved"]==2
            assert discovered["/biasing/enabled"]["resolved"] is True
            dump(candidate,mode=mode,enabled=False,bad=True)
            legacy_rules="[biasing.xs]\nparticles=proton\nprocesses=hIoni\nfactor=2\nvolumes=Target\n"
            expanded=dump(legacy_rules,mode=mode,enabled=None)
            assert expanded[identity("proton","hIoni")+"factor"]["resolved"]==2
            dump("[biasing.xs]\nparticles=proton\nvolumes=Target\n",mode=mode,enabled=None,bad=True)
            dump("[biasing.xs]\nprocesses=hIoni\nvolumes=Target\n",mode=mode,enabled=None,bad=True)
        legacy_disabled=dump(candidate,enabled=None)
        assert legacy_disabled["/biasing/enabled"]["resolved"] is False
        assert identity("proton","hIoni")+"factor" not in legacy_disabled
        fields=dump(rule+"[biasing.xs.e-.eIoni]\nname=same\nfactor=4\nvolumes=Target\n")
        proton=identity("proton","hIoni");electron=identity("e-","eIoni")
        assert fields[proton+"name"]["resolved"]==fields[electron+"name"]["resolved"]=="same"
        assert fields[proton+"factor"]["resolved"]==3 and fields[electron+"factor"]["resolved"]==4
        origins=[o for o in fields[proton+"factor"]["origins"] if o["key"]=="factor"]
        assert [o["raw"] for o in origins]==["2","3"]
        assert origins[0]["disposition"]=="shadowed" and origins[1]["disposition"]=="accepted"
        assert any(o["section"]=="biasing.xs.proton.hIoni" and o["key"]=="" for o in fields[proton+"process"]["origins"])
        fields=dump("[biasing.xs.A.a]\nparticle=proton\nprocess=hIoni\nfactor=8\nvolumes=Target\n[biasing.xs.B.b]\nparticle=proton\nprocess=hIoni\nvolumes=Target\n")
        assert fields[proton+"factor"]["resolved"]==1 and "requested" not in fields[proton+"factor"]
        assert any(o["raw"]=="8" and o["disposition"]=="shadowed" for o in fields[proton+"factor"]["origins"])
        fields=dump("[biasing.xs]\nparticles=proton\nprocesses=hIoni\nfactor=2\nvolumes=Target\n"+rule)
        assert fields[proton+"factor"]["resolved"]==3
        assert any(o["section"]=="biasing.xs" and o["raw"]=="2" and o["disposition"]=="shadowed" for o in fields[proton+"factor"]["origins"])
        fields=dump("[biasing.xs.proton.hIoni]\nonly_primary=true\napply_to_secondaries=true\nvolumes=Target\n")
        assert fields[proton+"only_primary"]["requested"] is True
        assert fields[proton+"only_primary"]["resolved"] is False
        # True worker receipts are checked independently of global callback counts.
        for threads in (1,2):
            ini=config("[biasing.xs.proton.hIoni]\nfactor=2\nvolumes=Target\nmin_weight=0\nmax_interactions=-1\n",threads)
            macro=work/f"run{threads}.mac"
            macro.write_text("/AIHL/biasing/xs/setRuleFactor proton hIoni 2\n/run/initialize\n/run/beamOn 4\n/run/beamOn 4\n",encoding="utf-8")
            output=work/f"output{threads}"
            result=subprocess.run([str(exe),"--config",str(ini),"--macro",str(macro),"--output",str(output)],cwd=work,capture_output=True,text=True,timeout=180)
            assert result.returncode==0,result.stdout+result.stderr
            final=json.loads((output/"effective_config_finalization.json").read_text())
            factor=next(f for f in final["fields"] if f["path"]==proton+"factor")
            assert factor["requested"]==2 and any(o["kind"]=="macro" and "setRuleFactor" in o["raw"] for o in factor["origins"])
            scopes=set()
            for snapshot in output.glob("effective_config_final_r*_t*.json"):
                document=json.loads(snapshot.read_text())
                for receipt in document.get("evidence",[]):
                    if receipt["path"]==proton+"factor" and receipt["stage"]=="run_end":
                        assert receipt["observed"]==2 and receipt["tls_verified"] is True
                        assert receipt["end_run_completed"] is True and receipt["physical_effect_status"]=="unknown"
                        assert receipt["matches_resolved_value"] is True
                        scopes.add((receipt["run_id"],receipt["thread_id"]))
            assert len(scopes)==threads*2,scopes
        # Every controlled command failure must preserve the accepted field
        # transaction and stop both later mutations and later beamOn commands.
        invalid_commands=(
            "/AIHL/biasing/xs/setRuleFactor proton hIoni -1",
            "/AIHL/biasing/xs/setRuleFactor proton hIoni nan",
            "/AIHL/biasing/xs/setRuleFactor proton hIoni inf",
            "/AIHL/biasing/xs/setRuleFactor proton hIoni",
            "/AIHL/biasing/xs/setRuleMinWeight proton hIoni nan",
            "/AIHL/biasing/xs/setRuleMaxInteractions proton hIoni 2x",
        )
        for index,command in enumerate(invalid_commands):
            ini=config("[biasing.xs.proton.hIoni]\nfactor=2\nvolumes=Target\n")
            macro=work/f"bad{index}.mac"
            macro.write_text(command+"\n/AIHL/biasing/xs/setRuleFactor proton hIoni 9\n/run/beamOn 1\n",encoding="utf-8")
            output=work/f"failed{index}"
            result=subprocess.run([str(exe),"--config",str(ini),"--macro",str(macro),"--output",str(output)],cwd=work,capture_output=True,text=True,timeout=90)
            assert 0<result.returncode<256,(command,result.returncode,result.stdout,result.stderr)
            summary=dict((key.strip(),value.strip()) for line in (output/"run_summary.txt").read_text().splitlines() if "=" in line for key,_,value in [line.partition("=")])
            assert summary["status"]=="failed",(command,summary)
            assert summary["macro_failure_code_available"]=="false",(command,summary)
            assert summary["macro_failure_line"]=="1" and summary["macro_failure_command"]==command,(command,summary)
            assert Path(summary["macro_failure_file"])==macro,(command,summary)
            assert int(summary["actual_completed_event_count"])==0,(command,summary)
            configured=json.loads((output/"effective_config_configure.json").read_text())
            final=json.loads((output/"effective_config_finalization.json").read_text())
            factor=next(f for f in final["fields"] if f["path"]==proton+"factor")
            original=next(f for f in configured["fields"] if f["path"]==proton+"factor")
            assert final["revision"]==configured["revision"],(command,configured["revision"],final["revision"])
            for key in ("requested","resolved","origins","revision","configuration_generation"):
                assert factor.get(key)==original.get(key),(command,key,factor,original)
            assert factor["resolved"]==2 and not any(o["kind"]=="macro" for o in factor["origins"])
            assert not list(output.glob("effective_config_run_*.json")),command
            assert not list(output.glob("event_edep*.csv")),command
    print("effective biasing config and actual worker evidence: OK")


if __name__=="__main__":main()
