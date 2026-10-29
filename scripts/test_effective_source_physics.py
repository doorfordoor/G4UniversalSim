#!/usr/bin/env python3
"""Actual 2C source/physics/field projection contract; requires newly built backend."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ["G4USIM_EXE"]) if os.environ.get("G4USIM_EXE") else None


def main():
    assert EXE is not None and EXE.is_file(), "Set G4USIM_EXE to the newly built candidate"
    with tempfile.TemporaryDirectory(prefix="g4usim-2c-consumers-") as temp:
        work = Path(temp)
        sequence = 0
        def dump(source, extra="", fail=False, physics="[physics]\nreference =\nmodules = G4EmStandardPhysics_option4\n"):
            nonlocal sequence
            sequence += 1
            ini = work / f"config{sequence}.ini"
            target = work / f"snapshot{sequence}.json"
            ini.write_text(physics + source + extra, encoding="utf-8")
            accepted = ini.read_bytes()
            process = subprocess.run([str(EXE), "--config", str(ini), "--dump-effective-config", str(target)],
                                     cwd=work, capture_output=True, text=True, timeout=90)
            if fail:
                assert process.returncode != 0, process.stdout + process.stderr
                assert not target.exists(), target
                return None
            assert process.returncode == 0, process.stdout + process.stderr
            document = json.loads(target.read_text(encoding="utf-8"))
            assert document["schema"] == "g4usim_effective_config_v1"
            fields = {field["path"]: field for field in document["fields"]}
            for field in fields.values():
                for origin in field["origins"]:
                    if origin["kind"] == "main_ini" and Path(origin["file"]) == ini:
                        assert origin["input_sha256"] == hashlib.sha256(accepted).hexdigest(), origin
            return fields

        for empty in ('', '   '):
            ref=dump('[source]\npreset=mono_proton\n',physics='[physics]\nreference=FTFP_BERT\nem='+empty+'\n')
            field=ref['/physics/reference']
            assert field['resolved']=='FTFP_BERT' and field['requested']=='FTFP_BERT',field
            assert all(o['disposition']=='shadowed' for o in field['origins'] if o['key']=='em'),field
            assert any(o['key']=='reference' and o['disposition']=='accepted' for o in field['origins'])
        selected=dump('[source]\npreset=mono_proton\n',physics='[physics]\nreference=FTFP_BERT\nem=option4\n')
        assert selected['/physics/reference']['resolved']=='FTFP_BERT_EMZ'
        assert any(o['key']=='em' and o['disposition']=='accepted' for o in selected['/physics/reference']['origins'])
        fields = dump("[source]\npreset = mono_proton\nenergy = 1 MeV\nenergy = 2 MeV\n")
        energy = fields["/source/energy"]
        assert energy["resolved"] == 2 and energy["unit"] == "MeV"
        assert [o["kind"] for o in energy["origins"]] == ["default", "main_ini", "preset", "main_ini", "main_ini"]
        assert [o["raw"] for o in energy["origins"][-2:]] == ["1 MeV", "2 MeV"]
        assert energy["origins"][-2]["disposition"] == "shadowed"
        assert energy["origins"][-1]["disposition"] == "accepted"
        assert energy["application_status"] == "not_applied"
        cases = {
            "mono": "energy = 2 MeV\n",
            "gauss": "energy = 2 MeV\nenergy_sigma = 0.1 MeV\n",
            "uniform": "energy_min = 1 MeV\nenergy_max = 2 MeV\n",
            "power": "energy_min = 1 MeV\nenergy_max = 2 MeV\nalpha = -1\n",
            "exp": "energy_min = 1 MeV\nenergy_max = 2 MeV\nezero = 1 MeV\n",
        }
        for kind, values in cases.items():
            fields = dump(f"[source]\nparticle = proton\nenergy_type = {kind}\n" + values)
            assert fields["/source/energy_type"]["resolved"] == kind
            assert ("/source/energy" in fields) == (kind in ("mono", "gauss"))
            assert ("/source/energy_sigma" in fields) == (kind == "gauss")
            assert ("/source/alpha" in fields) == (kind == "power")
            assert ("/source/ezero" in fields) == (kind == "exp")
        for kind, content in (("points", "energy_MeV,density\n1,1\n2,1\n"),
                              ("histogram", "e_low_MeV,e_high_MeV,weight\n1,2,1\n")):
            spectrum = work / f"{kind}.csv"
            spectrum.write_text(content, encoding="utf-8")
            fields = dump(f"[source]\nparticle = proton\nenergy_type = {kind}\nspectrum_file = {spectrum.as_posix()}\n")
            assert "/source/energy" not in fields
            assert fields["/source/spectrum_sha256"]["resolved"] == hashlib.sha256(spectrum.read_bytes()).hexdigest()
            assert len(fields["/source/spectrum"]["resolved"]) == 2
            assert any(origin.get("kind")=="spectrum_file" and Path(origin["file"])==spectrum and
                       origin["input_sha256"]==hashlib.sha256(spectrum.read_bytes()).hexdigest()
                       for origin in fields["/source/spectrum"]["origins"])
        fields = dump("[source.A/~B]\npreset = mono_proton\nintensity = 2\n[source.Second]\npreset = gamma_beam\n")
        assert fields["/source/objects/A~1~0B/intensity"]["resolved"] == 2
        assert "/source/energy" not in fields and "/source/particle" not in fields
        header = "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight\n"
        inputs = []
        for i in range(2):
            path = work / f"phase{i}.csv"
            path.write_text(header + f"0,{i},1,0,proton,2212,0,0,0,0,0,1,2,0,1\n", encoding="utf-8")
            inputs.append(path)
        fields = dump("[source]\nphase_space_file = " + ",".join(p.as_posix() for p in inputs) + "\nphase_space_recycle = true\n")
        assert fields["/source/phase_space_histories"]["resolved"] == 2
        assert fields["/source/phase_space_particles"]["resolved"] == 2
        observed_inputs=fields["/source/phase_space_inputs"]["resolved"]
        assert len(observed_inputs)==len(inputs), observed_inputs
        assert [Path(entry["path"]) for entry in observed_inputs]==inputs, observed_inputs
        assert [entry["sha256"] for entry in observed_inputs]==[hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs]
        assert "/source/particle" not in fields and "/source/energy" not in fields
        for path in inputs:
            assert any(origin.get("kind")=="phase_space_file" and Path(origin["file"])==path and
                       origin["input_sha256"]==hashlib.sha256(path.read_bytes()).hexdigest()
                       for origin in fields["/source/phase_space_inputs"]["origins"])
        fields = dump("[source]\nparticle = ion\nion = 6 12\nenergy = 0 MeV\n")
        assert fields["/source/ion_z"]["resolved"] == 6 and fields["/source/rest_energy"]["resolved"] is True
        fields = dump("[source]\npreset = mono_proton\n", "[physics.region.SV/~]\nmax_step = 1 mm\nvolumes = Target\n[field]\nmagnetic = 0,0,1 T\n")
        assert fields["/physics/objects/region:SV~1~0/max_step"]["resolved"] == 1
        assert fields["/field/magnetic"]["resolved"] == [0, 0, 1]
        assert fields["/physics/em"]["resolved"] == "G4EmStandardPhysics_option4"
        fields = dump("[source]\npreset = mono_proton\nposition_type = plane\nshape = rectangle\ncenter = 1,2,3 mm\nhalfx = 2 mm\nhalfy = 3 mm\nangular = focused\nfocus = 0,0,5 mm\n")
        assert fields["/source/center"]["resolved"] == [1, 2, 3]
        assert fields["/source/halfx"]["resolved"] == 2 and fields["/source/halfy"]["resolved"] == 3
        assert fields["/source/has_direction"]["resolved"] is False and "/source/direction" not in fields
        assert fields["/source/focus"]["resolved"] == [0, 0, 5]
        field_map = work / "magnetic.csv"
        field_map.write_text("x_mm,y_mm,z_mm,Bx_T,By_T,Bz_T\n" +
                             "".join(f"{x},{y},{z},0,0,1\n" for x in (0, 1) for y in (0, 1) for z in (0, 1)), encoding="utf-8")
        fields = dump("[source]\npreset = mono_proton\n", f"[field.Local]\nmagnetic_map = {field_map.as_posix()}\nvolumes = Target\n")
        mapped = fields["/field/objects/Local/magnetic_map"]["resolved"]
        assert mapped["sha256"] == hashlib.sha256(field_map.read_bytes()).hexdigest()
        assert mapped["grid_shape"] == [2, 2, 2] and mapped["outside"] == "zero"
        assert "/field/objects/Local/magnetic" not in fields
        assert mapped["field_unit"]=="T" and mapped["values"]==[[0,0,1]]*8
        assert any(origin.get("kind")=="field_map" and Path(origin["file"])==field_map and
                   origin["input_sha256"]==mapped["sha256"]
                   for origin in fields["/field/objects/Local/magnetic_map"]["origins"])
        off=dump("[source]\npreset=mono_proton\n", "[modules]\nfield=off\n")
        assert off["/field/module_enabled"]["resolved"] is False
        assert "/field/magnetic" not in off
        assert all(field["application_status"]!="applied" for field in off.values())
        ellipse=dump("[source]\nparticle=gamma\nenergy=1 MeV\nposition_type=plane\nshape=ellipse\ncenter=0,0,0 mm\nhalfx=2 mm\nhalfy=3 mm\n")
        assert ellipse["/source/halfy"]["resolved"]==3
        accepted=[origin for origin in ellipse["/source/halfy"]["origins"] if origin.get("disposition")=="accepted"]
        assert accepted[-1]["key"]=="halfy", accepted

        # Actual new-backend run gate: native source list replacement with the
        # same cardinality must not invent configured object identities.
        sequence+=1
        runtime=work/"runtime";runtime.mkdir()
        config=runtime/"main.ini";output=runtime/"output"
        geometry=runtime/"geometry.ini"
        geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n",encoding="utf-8")
        config.write_text("[run]\nthreads=1\n[output]\ndir="+output.as_posix()+
                          "\n[geometry]\ntemplate=hierarchical\nconfig="+geometry.as_posix()+
                          "\n[source.First]\nparticle=gamma\nenergy=1 MeV\nposition=0,0,0 mm\ndirection=0,0,1\n"
                          "[source.Second]\nparticle=gamma\nenergy=2 MeV\nposition=0,0,0 mm\ndirection=0,0,1\n",encoding="utf-8")
        macro=runtime/"native.mac"
        macro.write_text("/run/initialize\n/gps/source/delete 1\n/gps/source/add 1\n/gps/particle gamma\n/gps/energy 7 MeV\n/run/beamOn 2\n",encoding="utf-8")
        process=subprocess.run([str(EXE),"--config",str(config),"--macro",str(macro)],cwd=runtime,
                               capture_output=True,text=True,timeout=120)
        assert process.returncode==0,process.stdout+process.stderr
        snapshots=[json.loads(path.read_text(encoding="utf-8")) for path in output.glob("effective_config_run_*.json")]
        assert snapshots
        inventories=[]
        for snapshot in snapshots:
            for receipt in snapshot.get("evidence",[]):
                if "native_inventory" in receipt:
                    inventories.append(receipt)
                    assert receipt["application_status"]=="unknown"
                    assert receipt["path"]=="/source/mode"
                if receipt.get("path","").startswith("/source/objects/"):
                    assert not (receipt.get("application_status")=="applied" and receipt.get("matches_resolved_value") is True), receipt
        assert inventories, "native replacement inventory was not observed"
        dump("[source]\nparticle = proton\nenergy_type = uniform\nenergy = 3 MeV\nenergy_min = 1 MeV\nenergy_max = 2 MeV\n", fail=True)
    print("Effective source/physics/field backend projection passed")


if __name__ == "__main__":
    main()
