"""GDML case collisions fail explicitly until bias targets support object identity."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import contextlib

import test_geometry_a5 as a5


def model(second_name: str) -> str:
    tree = ET.fromstring(a5.GDML_SENSDET)
    structure = tree.find("structure")
    first = structure.find("volume[@name='Det_LV']")
    first.set("name", "Sensor")
    second = ET.fromstring(ET.tostring(first))
    second.set("name", second_name)
    structure.insert(1, second)
    world = structure.find("volume[@name='World_LV']")
    first_pv = world.find("physvol")
    first_pv.find("volumeref").set("ref", "Sensor")
    first_pv.find("position").set("x", "-30")
    second_pv = ET.fromstring(ET.tostring(first_pv))
    second_pv.set("name", "Second_PV")
    second_pv.find("volumeref").set("ref", second_name)
    second_pv.find("position").set("name", "SecondPos")
    second_pv.find("position").set("x", "30")
    world.append(second_pv)
    return ET.tostring(tree, encoding="unicode")


def main():
    exe = Path(os.environ.get("G4USIM_EXE", a5.EXE))
    assert exe.is_file(), exe
    with contextlib.ExitStack() as stack:
        work = Path(os.environ["G4USIM_TEST_WORK"]).resolve() if os.environ.get("G4USIM_TEST_WORK") else Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="g4usim-gdml-bias-")))
        work.mkdir(parents=True, exist_ok=True)
        count = 0
        for second in ("sensor", "Other"):
            gdml = work / f"{second}.gdml"
            gdml.write_text(model(second), encoding="utf-8")
            selections = ("Sensor,sensor", "sensor,Sensor", "Sensor", "sensor") if second == "sensor" else ("Sensor,Other,Sensor", "Other,Sensor")
            for threads in (1, 2):
                for entry in ("geometry", "rule"):
                    for selection in selections:
                        count += 1
                        geometry = work / f"geometry{count}.ini"
                        geometry.write_text(f"[gdml]\nfile = {gdml.name}\n" +
                                            (f"bias_volumes = {selection}\n" if entry == "geometry" else ""), encoding="utf-8")
                        source = "[source]\nparticle = proton\nenergy = 100 MeV\nposition_type = point\nposition = -30,0,100 mm\ndirection = +z\n"
                        main_text = a5.MAIN.replace("threads = 2", f"threads = {threads}").replace(
                            "template = hierarchical", "template = gdml").replace("reference = FTFP_BERT", "reference = FTFP_BERT\nbiasing = true").format(
                                seed=1, root=a5.ROOT.as_posix(), geometry=geometry.as_posix(), source=source)
                        main_text += "\n[biasing]\nenabled = true\n[biasing.xs.proton.protonInelastic]\nfactor = 2\n"
                        if entry == "rule":
                            main_text += f"volumes = {selection}\n"
                        config = work / f"main{count}.ini"
                        config.write_text(main_text, encoding="utf-8")
                        dump = work / f"processes{count}.json"
                        macro = work / f"run{count}.mac"
                        macro.write_text(f"/run/initialize\n/AIHL/biasing/print\n/AIHL/physics/dumpProcesses {dump.as_posix()} proton\n/run/beamOn 10\n", encoding="utf-8")
                        output = work / f"out{count}"
                        completed = subprocess.run([str(exe), "--config", str(config), "--macro", str(macro), "--output", str(output)],
                                                   cwd=work, capture_output=True, text=True, errors="replace", timeout=120)
                        log = completed.stdout + completed.stderr
                        (work / f"case{count}.log").write_text(log, encoding="utf-8")
                        facts = dict(line.split(" = ", 1) for line in (output / "run_summary.txt").read_text(encoding="utf-8").splitlines() if " = " in line)
                        if second == "sensor":
                            assert completed.returncode != 0, (entry, selection, log[-3000:])
                            assert "ambiguous" in log.lower() and "bias" in log.lower(), log[-3000:]
                            assert facts["status"] == "failed" and facts["run_count"] == "0", facts
                        else:
                            assert completed.returncode == 0, log[-3000:]
                            assert "operatorsAttached=true, operatorCount=2" in log, log[-4000:]
                            assert facts["biasing_attached_operator_count"] == "2", facts
                            assert facts["biasing_process_match_status"] == "validated", facts
                            assert int(facts["biasing_matched_process_rule_count"]) >= 1, facts
                            processes = json.loads(dump.read_text(encoding="utf-8"))
                            assert "biasWrapper(protonInelastic)" in json.dumps(processes), processes
    print("GDML bias identity restriction: PASS (attachment/process evidence, no physical bias benchmark)")


if __name__ == "__main__":
    main()
