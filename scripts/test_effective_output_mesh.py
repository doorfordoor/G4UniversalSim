#!/usr/bin/env python3
"""Real effective-config output/mesh projections; G4USIM_EXE must be a fresh build."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    executable = Path(os.environ["G4USIM_EXE"]).resolve()
    assert executable.is_file(), executable
    with tempfile.TemporaryDirectory(prefix="g4usim-effective-output-mesh-") as folder:
        work = Path(folder)
        serial = 0
        def dump(text, bad=False, cli_output=None):
            nonlocal serial
            serial += 1
            ini = work / f"input{serial}.ini"
            target = work / f"snapshot{serial}.json"
            ini.write_text("[physics]\nreference =\nmodules = G4EmStandardPhysics_option4\n" + text, encoding="utf-8")
            digest = hashlib.sha256(ini.read_bytes()).hexdigest()
            arguments=[str(executable), "--config", str(ini), "--dump-effective-config", str(target)]
            if cli_output is not None: arguments += ["--output",cli_output]
            result = subprocess.run(arguments,
                                    cwd=work, capture_output=True, text=True, timeout=90)
            if bad:
                assert result.returncode != 0, result.stdout + result.stderr
                assert not target.exists()
                return {}
            assert result.returncode == 0, result.stdout + result.stderr
            data = json.loads(target.read_text(encoding="utf-8"))
            fields = {field["path"]: field for field in data["fields"]}
            for field in fields.values():
                if field["path"].startswith(("/mesh/", "/output/")):
                    assert field["application_status"] == "not_applied", field
                    for origin in field["origins"]:
                        if origin["kind"] == "main_ini":
                            assert origin["input_sha256"] == digest, origin
            assert not (work / "must-not-create").exists()
            return fields
        for spelling in ("csv", "root", "both", "csv+root", "root+csv"):
            fields = dump(f"[output]\ndir = must-not-create\nformat = {spelling}\n")
            assert fields["/output/format"]["resolved"] == ("both" if "+" in spelling else spelling)
            assert fields["/output/format"]["requested"] == spelling
            assert fields["/output/thread_suffix"]["resolved"] is True
            assert "requested" not in fields["/output/thread_suffix"]
        cli_dir=str(work/"CLI original path")
        fields=dump("[output]\ndir = INI original\ndir = INI winner\noutputDir = ignored alias\n",cli_output=cli_dir)
        directory=fields["/output/dir"]
        assert directory["resolved"]==cli_dir and directory["requested"]==cli_dir
        ini_origins=[o for o in directory["origins"] if o["kind"]=="main_ini"]
        assert {o["raw"] for o in ini_origins}=={"INI original","INI winner","ignored alias"}
        assert all(o["disposition"]=="shadowed" for o in ini_origins)
        assert directory["origins"][-1]["kind"]=="cli" and directory["origins"][-1]["raw"]==cli_dir
        assert not Path(cli_dir).exists()
        fields=dump("[output]\ndir = \noutputDir = alias winner\n")
        assert fields["/output/dir"]["requested"]=="alias winner"
        fields=dump("[output]\ndir = canonical winner\noutputDir = ignored alias\n")
        assert fields["/output/dir"]["requested"]=="canonical winner"
        mesh = "[scoring.mesh.Grid]\nshape = box\nsize = 1 cm, 2 mm, 3 mm\nbins = 2,3,4\n[scoring.mesh.Grid.Edep]\ntype = energyDeposit\nunit = MeV\nparticles = proton, e-\nenergy_min = 100 keV\nenergy_max = 2 MeV\n"
        fields = dump(mesh)
        base = "/mesh/objects/Grid/"
        assert fields[base + "size"]["resolved"] == [10, 2, 3]
        assert fields[base + "bins"]["resolved"] == [2, 3, 4]
        assert fields[base + "center"]["resolved"] == [0, 0, 0]
        quantity = "/mesh/objects/Grid~1quantities~1Edep/"
        assert fields[quantity + "particles"]["resolved"] == ["proton", "e-"]
        assert fields[quantity + "energy_min"]["resolved"] == 0.1
        assert fields[quantity + "energy_max"]["unit"] == "MeV"
        fields = dump(mesh.replace("shape = box", "shape = cylinder").replace("1 cm, 2 mm, 3 mm", "1 cm, 2 mm"))
        assert fields[base + "size"]["resolved"] == [10, 2]
        dump(mesh.replace("bins = 2,3,4", "bins = 0,3,4"), bad=True)
        dump(mesh.replace("energy_max = 2 MeV", "energy_max = 0.01 MeV"), bad=True)
        dump("[output]\nformat = invalid\n", bad=True)
    print("effective output/mesh: OK")


if __name__ == "__main__":
    main()
