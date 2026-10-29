"""Focused Q1 GDML bias/region and parameterised-mother evidence probes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import test_geometry_a5 as a5


def main():
    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    tree = ET.fromstring(a5.GDML_SENSDET)
    structure = tree.find("structure")
    upper = structure.find("volume[@name='Det_LV']")
    upper.set("name", "Sensor")
    lower = ET.fromstring(ET.tostring(upper))
    lower.set("name", "sensor")
    structure.insert(1, lower)
    world = structure.find("volume[@name='World_LV']")
    first = world.find("physvol")
    first.find("volumeref").set("ref", "Sensor")
    first.find("position").set("x", "-30")
    second = ET.fromstring(ET.tostring(first))
    second.set("name", "Other_PV")
    second.find("volumeref").set("ref", "sensor")
    second.find("position").set("name", "OtherPos")
    second.find("position").set("x", "30")
    world.append(second)
    (work / "case.gdml").write_text(ET.tostring(tree, encoding="unicode"), encoding="utf-8")
    geometry = work / "geometry.ini"
    geometry.write_text("[gdml]\nfile = case.gdml\nbias_volumes = Sensor,sensor\n", encoding="utf-8")
    dump = work / "physics.json"
    config = work / "main.ini"
    source = "[source]\nparticle = proton\nenergy = 20 MeV\nposition_type = point\nposition = -30,0,100 mm\ndirection = +z\n"
    config.write_text(a5.MAIN.replace("template = hierarchical", "template = gdml").format(
        seed=1, root=a5.ROOT.as_posix(), geometry=geometry.as_posix(), source=source) +
        "\n[physics.region.Upper]\nvolumes = Sensor\ngamma = 0.2 mm\n"
        "[physics.region.Lower]\nvolumes = sensor\ngamma = 0.4 mm\n", encoding="utf-8")
    macro = work / "run.mac"
    macro.write_text("/run/initialize\n/AIHL/detector/printBiasVolumes\n"
                     f"/AIHL/physics/dumpProcesses {dump.as_posix()} proton\n/run/beamOn 1\n", encoding="utf-8")
    result = subprocess.run([str(a5.EXE), "--config", str(config), "--macro", str(macro),
                             "--output", str(work / "out")], cwd=work,
                            text=True, capture_output=True, errors="replace", timeout=90)
    log = result.stdout + result.stderr
    (work / "run.log").write_text(log, encoding="utf-8")
    print("exit", result.returncode)
    print("\n".join(line for line in log.splitlines() if "bias volumes" in line or "  - sensor" in line))
    assert result.returncode == 0, log[-3000:]
    data = json.loads(dump.read_text(encoding="utf-8"))
    (work / "dump-keys.json").write_text(json.dumps(data.get("regions"), indent=2), encoding="utf-8")
    print(json.dumps(data.get("regions")))
    regions = {region["name"]: region for region in data["regions"]}
    assert regions["Upper"]["root_volumes"] == ["Sensor"], regions
    assert regions["Lower"]["root_volumes"] == ["sensor"], regions
    assert regions["Upper"]["production_cuts_mm"]["gamma"] == .2
    assert regions["Lower"]["production_cuts_mm"]["gamma"] == .4
    # Parameterised mother (different copy materials), with a normal daughter.
    (work / "copies.csv").write_text("x_mm,y_mm,z_mm,material\n-50,0,0,G4_WATER\n50,0,0,G4_Si\n", encoding="utf-8")
    nested = a5.WORLD + a5.volume("Container", "shape = box\nsize = 200 mm,100 mm,100 mm", sensitive=False) + \
        a5.volume("Mother", "shape = box\nsize = 20 mm,20 mm,20 mm\nplacement = parameterised\ncopies_file = copies.csv", parent="Container") + \
        a5.volume("Child", "shape = box\nsize = 10 mm,10 mm,10 mm", parent="Mother", material="G4_Pb")
    r = a5.Runner(work)
    original_main = a5.MAIN
    a5.MAIN = a5.MAIN.replace("fluence = true", "fluence = false")
    try:
        masses = {}
        for x in (-50, 50):
            source = f"[source]\nparticle = proton\nenergy = 100 MeV\nposition_type = point\nposition = {x},0,-9 mm\ndirection = +z\n"
            output, log = r.run(nested, source, 20)
            (work / f"nested_{x}.log").write_text(log, encoding="utf-8")
            masses[x] = a5.by_volume(output, "dose_volume_summary", "raw_edep_MeV")
        (work / "nested_masses.json").write_text(json.dumps(masses, indent=2), encoding="utf-8")
        print("nested", json.dumps(masses))
        if "--fixed" in sys.argv:
            for x, mother_mass in ((-50, .007), (50, .01631)):
                observed = masses[x]
                mother = [v for k, v in observed.items() if k.rsplit("/", 1)[1].startswith("Mother_PV")]
                child = [v for k, v in observed.items() if k.rsplit("/", 1)[1].startswith("Child_PV")]
                assert len(mother) == len(child) == 1, observed
                assert abs(mother[0]["mass_kg"] / mother_mass - 1) < 1e-9, observed
                assert abs(child[0]["mass_kg"] / .01135 - 1) < 1e-9, observed
    finally:
        a5.MAIN = original_main


if __name__ == "__main__":
    main()
