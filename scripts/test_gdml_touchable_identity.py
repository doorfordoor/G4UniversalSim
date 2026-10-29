"""R24: GDML ordinary placement paths must identify distinct physical instances."""
from __future__ import annotations

import contextlib
import csv
import math
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import test_geometry_a5 as a5


def model(kind: str) -> str:
    tree = ET.fromstring(a5.GDML_SENSDET)
    materials = tree.find("materials")
    dense = ET.fromstring(ET.tostring(materials.find("material[@name='Water']")))
    dense.set("name", "Dense")
    dense.find("D").set("value", "2")
    materials.append(dense)
    solids = tree.find("solids")
    ET.SubElement(solids, "box", name="SmallBox", x="10", y="20", z="20", lunit="mm")
    ET.SubElement(solids, "box", name="ContainerBox", x="40", y="40", z="40", lunit="mm")
    structure = tree.find("structure")
    sensor_a = structure.find("volume[@name='Det_LV']")
    sensor_a.set("name", "SensorA")
    sensor_b = ET.fromstring(ET.tostring(sensor_a))
    sensor_b.set("name", "SensorB")
    sensor_b.find("materialref").set("ref", "Dense")
    sensor_b.find("solidref").set("ref", "SmallBox")
    structure.insert(1, sensor_b)
    world = structure.find("volume[@name='World_LV']")
    world.remove(world.find("physvol"))
    for index, (logical, x) in enumerate((("SensorA", -30), ("SensorB", 30))):
        parent = world
        nested = kind == "different_parents" or (kind == "separator_collision" and index == 1)
        if nested:
            container_name = f"Container{index}"
            container = ET.Element("volume", name=container_name)
            ET.SubElement(container, "materialref", ref="Vacuum")
            ET.SubElement(container, "solidref", ref="ContainerBox")
            # GDML resolves volume references in declaration order. In the
            # separator case only the second sensor has a container, so using
            # its sensor index could place that definition after the world.
            structure.insert(list(structure).index(world), container)
            placement = ET.SubElement(world, "physvol", name="A" if kind == "separator_collision" else f"Parent{index}", copynumber="0")
            ET.SubElement(placement, "volumeref", ref=container_name)
            ET.SubElement(placement, "position", name=f"ParentPos{index}", x=str(x), y="0", z="100", unit="mm")
            parent = container
        name = f"Unique{index}" if kind == "unique_names" else "SamePV"
        if kind == "separator_collision":
            name = "A#0/B" if index == 0 else "B"
        placement = ET.SubElement(parent, "physvol", name=name, copynumber=str(index if kind == "different_copies" else 0))
        ET.SubElement(placement, "volumeref", ref=logical)
        ET.SubElement(placement, "position", name=f"SensorPos{index}", x="0" if nested else str(x), y="0", z="0" if nested else "100", unit="mm")
    return ET.tostring(tree, encoding="unicode")


def run_case(work: Path, kind: str, threads: int) -> None:
    folder = work / f"{kind}_{threads}"
    folder.mkdir()
    (folder / "model.gdml").write_text(model(kind), encoding="utf-8")
    geometry = folder / "geometry.ini"
    geometry.write_text("[gdml]\nfile=model.gdml\n", encoding="utf-8")
    source = "".join(f"[source.s{index}]\nparticle=proton\nenergy=2 MeV\nposition_type=point\nposition={x},0,100 mm\ndirection=+z\n" for index, x in enumerate((-30, 30)))
    config = folder / "main.ini"
    config.write_text(a5.MAIN.replace("template = hierarchical", "template = gdml").replace(
        "threads = 2", f"threads = {threads}").replace("fluence = true", "fluence = false").format(
            seed=42, root=a5.ROOT.as_posix(), geometry=geometry.as_posix(), source=source), encoding="utf-8")
    macro = folder / "run.mac"
    macro.write_text("/gps/source/multiplevertex true\n/run/initialize\n/run/beamOn 4\n", encoding="utf-8")
    output = folder / "output"
    result = subprocess.run([str(a5.EXE), "--config", str(config), "--macro", str(macro), "--output", str(output)],
                            cwd=folder, capture_output=True, text=True, errors="replace", timeout=120)
    log = result.stdout + result.stderr
    (folder / "run.log").write_text(log, encoding="utf-8")
    summary = output / "run_summary.txt"
    assert summary.is_file(), (kind, threads, result.returncode, log[-3000:])
    facts = dict(line.split(" = ", 1) for line in summary.read_text(encoding="utf-8").splitlines() if " = " in line)
    if kind in ("duplicate", "separator_collision"):
        assert result.returncode == 1, (kind, threads, result.returncode, log[-3000:])
        assert "GDML ambiguous touchable path" in log, log[-3000:]
        assert facts["status"] == "failed" and facts["run_count"] == "0", facts
        assert not list(output.glob("dose_volume_summary*.csv")), kind
        assert not list(output.glob("scorer_statistics*.csv")), kind
    else:
        assert result.returncode == 0 and facts["status"] == "completed", (facts, log[-3000:])
        energies = {}
        for path in output.glob("dose_volume_summary_t*.csv"):
            with path.open(newline="", encoding="utf-8") as stream:
                for row in csv.DictReader(stream):
                    key = row["volume_path"]
                    energies[key] = energies.get(key, 0.0) + float(row["raw_edep_MeV"])
                    assert math.isclose(float(row["mass_kg"]), .008, rel_tol=1e-9), row
        assert len(energies) == 2, energies
        for path, energy in energies.items():
            assert math.isclose(energy, 8.0, rel_tol=1e-8), (path, energy)
        if kind == "different_copies":
            assert {path.rsplit("#", 1)[1] for path in energies} == {"0", "1"}, energies
        if kind == "different_parents":
            assert all(path.endswith("/SamePV#0") for path in energies), energies
    print(f"{kind}/{threads}: touchable identity contract checked")


def main() -> None:
    assert a5.EXE.is_file(), a5.EXE
    with contextlib.ExitStack() as stack:
        work = Path(os.environ["G4USIM_TEST_WORK"]).resolve() if os.environ.get("G4USIM_TEST_WORK") else Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="g4usim-gdml-identity-")))
        work.mkdir(parents=True, exist_ok=True)
        for threads in (1, 2):
            for kind in ("duplicate", "separator_collision", "unique_names", "different_copies", "different_parents"):
                run_case(work, kind, threads)
    print("GDML touchable identity: PASS")


if __name__ == "__main__":
    main()
