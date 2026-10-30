#!/usr/bin/env python3
"""Real F1 input readers -> final metadata -> automatic consumer regression.

This proves actual reader identities, not physics. Input mutation between STL
validation/construction is checked with a synchronized csh barrier.
"""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
import queue
import threading
import time
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.output.provenance import output_evidence
from test_geometry_a5 import GDML_SENSDET

POINT = "particle=proton\nenergy=1 MeV\nposition=0,0,-20 mm\ndirection=+z\n"
GEOMETRY = """[world]
shape=box
size=100 mm,100 mm,100 mm
material=G4_Galactic
[volume.Target]
parent=world
shape=box
size=10 mm,10 mm,10 mm
material=G4_Si
sensitive=true
"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Cases:
    def __init__(self, exe, work):
        self.exe, self.work = exe, work
        self.count = 0

    def run(self, name, source="[source]\n" + POINT, *, threads=1, files=None,
            geometry=GEOMETRY, template="hierarchical", extra="", macro=None, failed=False, after_configure=None):
        self.count += 1
        folder = self.work / name
        folder.mkdir()
        for filename, text in (files or {}).items():
            path = folder / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        geo = folder / "geometry.ini"
        geo.write_bytes(geometry.encode("utf-8"))
        ini = folder / "main.ini"
        ini.write_text(f"[run]\nthreads={threads}\nseed=137\n[output]\nformat=csv\n"
                       f"[geometry]\ntemplate={template}\nconfig={geo.as_posix()}\ncheck_overlaps=false\n"
                       "[physics]\nreference=FTFP_BERT\n[scoring]\nenabled=true\nevent_edep=true\n"
                       + source + extra, encoding="utf-8", newline="\n")
        mac = folder / "run.mac"
        mac.write_text(macro or "/run/initialize\n/run/beamOn 2\n", encoding="utf-8", newline="\n")
        # Freeze expectations before execution. Never manufacture consumed-byte
        # expectations by reopening input paths only after finalization.
        expected = {p.resolve(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        output = folder / "output"
        versions = {path: [data] for path, data in expected.items()}
        if after_configure is None:
            result = subprocess.run([str(self.exe), "--config", str(ini), "--macro", str(mac),
                                     "--output", str(output)], cwd=folder, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=180)
        else:
            result = self._interactive(folder, ini, output, after_configure, versions)
        (folder / "run.log").write_text(result.stdout + result.stderr, encoding="utf-8", newline="\n")
        assert (result.returncode != 0) if failed else (result.returncode == 0), (name, result.returncode, result.stdout[-3000:], result.stderr[-2000:])
        metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
        assert metadata["values"]["status"] == ("failed" if failed else "completed"), metadata["values"]
        inputs = metadata["provenance"]["inputs"]
        assert inputs and [r["sequence"] for r in inputs] == list(range(1, len(inputs)+1))
        assert metadata["provenance"]["input_observation"] == "bytes_read_not_semantic_acceptance"
        for row in inputs:
            if row["status"] == "recorded":
                path = Path(row["path"])
                path = path.resolve() if path.is_absolute() else (folder / path).resolve()
                assert path in expected, (name, row)
                assert any(row["sha256"] == digest(data) and row["size_bytes"] == len(data) for data in versions[path]), (name, row)
            else:
                assert row["status"] == "unobserved" and row["sha256"] is None and row["size_bytes"] is None
                assert row["reason"]
        evidence = output_evidence(output)
        assert evidence.status == "verified" and evidence.document["provenance"] == metadata["provenance"]
        return folder, output, metadata, inputs

    def _interactive(self, folder, ini, output, mutate, versions):
        """Consume stdout until the real csh echo barrier; no polling sleeps."""
        args = [str(self.exe), "--config", str(ini), "--output", str(output), "--ui", "--ui-session", "csh"]
        process = subprocess.Popen(args, cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
        messages, lines = queue.Queue(), []
        def read_output():
            try:
                for line in process.stdout:
                    lines.append(line)
                    messages.put(line)
            finally:
                messages.put(None)
        reader = threading.Thread(target=read_output, name="f1-csh-stdout", daemon=True)
        reader.start()
        marker = "F1_CONFIGURE_BARRIER_" + folder.name.replace("-", "_")
        try:
            process.stdin.write("/control/echo " + marker + "\n")
            process.stdin.flush()
            deadline = time.monotonic() + 90
            while True:
                remaining = deadline - time.monotonic()
                assert remaining > 0, "Timed out waiting for actual csh Configure barrier"
                try:
                    line = messages.get(timeout=remaining)
                except queue.Empty:
                    raise AssertionError("Timed out waiting for actual csh Configure barrier")
                assert line is not None, "csh exited before Configure barrier: " + "".join(lines)[-3000:]
                if marker in line:
                    break
            # The process is now configured and blocked on the next audited
            # csh command. Only task-local fixture bytes are changed here.
            mutate(folder, versions)
            process.stdin.write("/run/initialize\n/run/beamOn 2\nexit\n")
            process.stdin.flush()
            process.stdin.close()
            code = process.wait(timeout=120)
            reader.join(timeout=10)
            assert not reader.is_alive(), "stdout reader did not finish after backend exit"
            return subprocess.CompletedProcess(args, code, "".join(lines), "")
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=15)
            reader.join(timeout=10)
            (folder / "run.log").write_text("".join(lines), encoding="utf-8", newline="\n")
            raise
        finally:
            process.stdout.close()


def synchronized_cases(cases, stl):
    geometry = GEOMETRY + "[volume.Mesh]\nparent=world\nshape=tessellated\nfile=mesh.stl\nmaterial=G4_Galactic\nposition=-30,0,0 mm\n"
    original = stl.encode("utf-8")
    replacement = stl.replace("vertex 1 ", "vertex 2 ").replace(" 1 ", " 2 ").replace(" 1\n", " 2\n").encode("utf-8")
    assert original != replacement
    def replace_mesh(folder, versions):
        path = (folder / "mesh.stl").resolve()
        assert versions[path] == [original]
        path.write_bytes(replacement)
        versions[path].append(replacement)
    _, _, metadata, rows = cases.run("csh-stl-change", files={"mesh.stl": stl}, geometry=geometry,
                                     after_configure=replace_mesh)
    mesh_rows = [row for row in rows if row["kind"] == "stl"]
    validation = [row for row in mesh_rows if row["role"] == "geometry_validation"]
    construction = [row for row in mesh_rows if row["role"] == "geometry_construct"]
    assert validation and construction, mesh_rows
    assert all(row["sha256"] == digest(original) for row in validation), validation
    assert all(row["sha256"] == digest(replacement) for row in construction), construction
    assert max(row["sequence"] for row in validation) < min(row["sequence"] for row in construction)
    assert int(metadata["values"]["actual_completed_event_count"]) == 2

    material = "[element.C]\nsymbol=C\nz=6\na=12 g/mole\n[material.Coating]\ndensity=1 g/cm3\ncomponents=C:1\n"
    spectrum = "e_low_MeV,e_high_MeV,weight\n1,2,1\n2,3,1\n"
    changed_spectrum = "e_low_MeV,e_high_MeV,weight\n4,5,1\n5,6,1\n"
    def change_cached_sources(folder, versions):
        (folder / "main.ini").unlink()
        (folder / "materials.ini").unlink()
        (folder / "spectrum.csv").write_text(changed_spectrum, encoding="utf-8", newline="\n")
        # Intentionally do not add new versions: these are already cached inputs,
        # and any reread of their changed bytes must fail the ledger assertions.
    source = "[source.named]\nparticle=proton\nenergy_type=histogram\nspectrum_file=spectrum.csv\nposition=0,0,-20 mm\ndirection=+z\n"
    geometry = GEOMETRY.replace("material=G4_Si", "material=Coating")
    folder, output, _, rows = cases.run("csh-cached-input-change", source, geometry=geometry,
        files={"materials.ini": material, "spectrum.csv": spectrum}, extra="[materials]\nconfig=materials.ini\n",
        after_configure=change_cached_sources)
    assert not (folder / "main.ini").exists() and not (folder / "materials.ini").exists()
    assert (folder / "spectrum.csv").read_text(encoding="utf-8") == changed_spectrum
    for kind in ("main_ini", "material_ini", "spectrum"):
        observed = [row for row in rows if row["kind"] == kind]
        assert observed and len({row["sha256"] for row in observed}) == 1, observed
    assert next(row for row in rows if row["kind"] == "material_ini")["sha256"] == digest(material.encode("utf-8"))
    assert next(row for row in rows if row["kind"] == "spectrum")["sha256"] == digest(spectrum.encode("utf-8"))
    assert output_evidence(output).status == "verified"
    print("F1 synchronized csh: STL validation/construction versions and cached input deletion/change passed")


def main():
    exe = Path(os.environ["G4USIM_EXE"]).resolve()
    assert exe.is_file(), exe
    with contextlib.ExitStack() as stack:
        work = Path(os.environ["G4USIM_TEST_WORK"]).resolve() if os.environ.get("G4USIM_TEST_WORK") else Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="g4usim-f1-resources-")))
        work.mkdir(parents=True, exist_ok=True)
        cases = Cases(exe, work)
        vertices = ((0,0,0),(1,0,0),(0,1,0),(0,0,1))
        stl = "solid tetra\n"
        for face in ((0,2,1),(0,1,3),(0,3,2),(1,2,3)):
            stl += "facet normal 0 0 0\nouter loop\n" + "".join("vertex %s %s %s\n" % vertices[i] for i in face) + "endloop\nendfacet\n"
        stl += "endsolid tetra\n"
        if "--interactive-only" in sys.argv:
            synchronized_cases(cases, stl)
            return
        resource_geometry = GEOMETRY + """[volume.Mesh]
parent=world
shape=tessellated
file=mesh.stl
file_unit=mm
material=G4_Galactic
position=-30,0,0 mm
[volume.Array]
parent=world
shape=box
size=20 mm,20 mm,20 mm
material=G4_Galactic
position=30,0,0 mm
[volume.Copy]
parent=Array
shape=box
size=2 mm,2 mm,2 mm
material=Coating
placement=parameterised
copies_file=copies.csv
"""
        resources = {
            "materials.ini": "[element.C]\nsymbol=C\nz=6\na=12 g/mole\n[material.Coating]\ndensity=1 g/cm3\ncomponents=C:1\n",
            "mesh.stl": stl,
            "copies.csv": "x_mm,y_mm,z_mm\n-5,0,0\n5,0,0\n",
            "niel.csv": "energy_MeV,niel_MeV_cm2_g\n0.001,0.002\n100,0.002\n",
            "field.csv": "x_m,y_m,z_m,Bx_T,By_T,Bz_T\n" + "".join(f"{x},{y},{z},0,0,0\n" for x in (-1,1) for y in (-1,1) for z in (-1,1)),
            "spectrum.csv": "e_low_MeV,e_high_MeV,weight\n1,2,1\n2,3,1\n",
            "macros/outer.mac": "/control/execute inner.mac\n/control/execute inner.mac\n",
            "macros/inner.mac": "/control/echo F1_NESTED_RESOURCE\n",
        }
        source = "[source.named]\nparticle=proton\nenergy_type=histogram\nspectrum_file=spectrum.csv\nposition=0,0,-20 mm\ndirection=+z\n"
        extra = "[materials]\nconfig=materials.ini\n[scoring.displacement]\nproton=niel.csv\n[field]\nmagnetic_map=field.csv\n"
        # displacement activation belongs to [scoring], avoid duplicate sections.
        source = source.replace("[source.named]", "displacement=true\n[source.named]")
        macro = "/control/execute macros/outer.mac\n/run/initialize\n/run/beamOn 2\n/run/beamOn 2\n"
        expected_kinds = {"main_ini", "geometry_ini", "material_ini", "copies_table", "stl", "spectrum", "niel_table", "field_map", "macro"}
        for threads in (1,2,4):
            _, output, metadata, inputs = cases.run(f"resources-{threads}", source, threads=threads,
                files=resources, geometry=resource_geometry, extra=extra, macro=macro)
            assert expected_kinds <= {r["kind"] for r in inputs}, {r["kind"] for r in inputs}
            stls = [r for r in inputs if r["kind"] == "stl"]
            assert {r["role"] for r in stls} >= {"geometry_validation", "geometry_construct"}
            assert len(stls) >= 2 and len({r["sha256"] for r in stls}) == 1
            nested = [r for r in inputs if Path(r["path"]).name == "inner.mac"]
            assert len(nested) == 2 and nested[0]["sequence"] < nested[1]["sequence"]
            assert len(metadata["runs"]) == 2, metadata["runs"]
            # Copying/moving outputs cannot require original input files to exist.
            moved = work / f"moved-{threads}"
            shutil.copytree(output, moved)
            assert output_evidence(moved).status == "verified"
        header = "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight\n"
        phase = {f"phase{i}.csv": header + f"0,{i},1,0,proton,2212,0,0,-20,0,0,1,1,0,1\n" for i in (0,1)}
        _, _, _, inputs = cases.run("phase-space", "[source]\nphase_space_file=phase0.csv,phase1.csv\n", files=phase, threads=2)
        assert len([r for r in inputs if r["kind"] == "phase_space"]) == 2
        _, _, _, inputs = cases.run("native-spectrum", files={"native-spectrum.dat": "0 0\n1 1\n2 1\n"},
            macro="/run/particle/retrievePhysicsTable OFF\n/run/initialize\n/run/beamOn 2\n"
                  "/gps/ene/type User\n/gps/hist/type energy\n/gps/hist/file native-spectrum.dat\n")
        native = [r for r in inputs if r["kind"] == "native_command"]
        assert len(native) == 1 and native[0]["role"] == "/gps/hist/file" and native[0]["status"] == "unobserved", native
        # Reuse a real native-saved status, then check successful and rejected reads.
        states = work / "native-states"
        states.mkdir()
        cases.run("save-rng", macro=f"/random/setDirectoryName {states.as_posix()}/\n/random/setSavingFlag true\n/run/initialize\n/run/beamOn 2\n")
        candidates = sorted(states.glob("*currentRun.rndm"))
        state = next((p for p in candidates if "Master" in p.name), next((p for p in candidates if p.name == "currentRun.rndm"), None))
        assert state is not None, list(states.iterdir())
        # Put fixtures inside each case so byte expectations are frozen pre-run.
        state_text = state.read_text(encoding="utf-8")
        for invalid in (False, True):
            _, _, _, inputs = cases.run("restore-" + str(invalid), files={"state.rndm": "malformed complete state\n" if invalid else state_text},
                macro="/random/resetEngineFrom state.rndm\n/run/initialize\n/run/beamOn 2\n", failed=invalid)
            restore = [r for r in inputs if r["kind"] == "random_restore"]
            assert len(restore) == 1 and restore[0]["role"] == "engine_restore_validation"
        capabilities = subprocess.run([str(exe), "--capabilities"], capture_output=True, text=True, check=True)
        gdml = next(item for item in json.loads(capabilities.stdout)["templates"] if item["id"] == "gdml")
        if gdml["runtime"]:
            materials_begin, materials_end = GDML_SENSDET.index("  <materials>"), GDML_SENSDET.index("  </materials>") + len("  </materials>")
            fragment = GDML_SENSDET[materials_begin:materials_end]
            model = GDML_SENSDET[:materials_begin] + "&materials;" + GDML_SENSDET[materials_end:]
            model = model.replace('<gdml xmlns:xsi=', '<!DOCTYPE gdml [<!ENTITY materials SYSTEM "materials.fragment">]>\n<gdml xmlns:xsi=', 1)
            _, _, _, inputs = cases.run("gdml", template="gdml", geometry="[gdml]\nfile=model.gdml\nvalidate=false\n",
                files={"model.gdml": model, "materials.fragment": fragment})
            observed = {Path(r["path"]).name for r in inputs if r["kind"] == "gdml_dependency" and r["status"] == "recorded"}
            assert {"model.gdml", "materials.fragment"} <= observed, observed
        else:
            assert gdml["runtime"] is False
            print("GDML unavailable in this build; native dependency runtime case not executed")
        synchronized_cases(cases, stl)
        print(f"F1 backend input resources: {cases.count} real cases passed")


if __name__ == "__main__":
    main()
