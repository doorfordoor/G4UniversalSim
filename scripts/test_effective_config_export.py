#!/usr/bin/env python3
"""Real-backend configured subset export; no simulation output is allowed."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui"))
from g4usim_gui.core.effective_config import parse_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", default=os.environ.get("G4USIM_EXE"))
    args = parser.parse_args()
    assert args.executable, "Set G4USIM_EXE or --executable to a built backend"
    exe = Path(args.executable).resolve()
    assert exe.is_file(), exe
    with tempfile.TemporaryDirectory(prefix="g4usim-effective-export-") as temp:
        folder = Path(temp)
        output = folder / "simulation-output"
        config = folder / "input.ini"
        config.write_text("[run]\nthreads=1\nname=from_ini\n[output]\ndir=" + output.as_posix()
                          + "\n[source]\nparticle=proton\nenergy=2 MeV\n", encoding="utf-8")
        macro = folder / "never-executed.mac"
        macro.write_text("/run/initialize\n/run/beamOn 2\n", encoding="utf-8")

        def run(*extra):
            return subprocess.run([str(exe), "--config", str(config), *extra], cwd=folder,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

        def read(result):
            assert result.returncode == 0, result.stdout + result.stderr
            data = json.loads(result.stdout)
            assert parse_snapshot(result.stdout) == data, "Backend and viewer wire contracts differ"
            assert data["schema"] == "g4usim_effective_config_v1"
            assert data["scope"] == "manager_state_subset"
            assert data["stage"] == "configure" and data["run_id"] is None
            assert data["macro_execution_status"] == "not_executed" and not data["execution_performed"]
            assert data["origin_chain_coverage"] == "winning_source_only"
            assert data["input_hash_coverage"] == "not_recorded"
            assert all(f["application_status"] == "not_applied" and f["applied_revision"] is None
                       for f in data["fields"])
            assert all(f["evidence_level"] == "manager_accepted" for f in data["fields"])
            assert not output.exists(), "Inspection created simulation output"
            return {f["path"]: f for f in data["fields"]}

        first = run("--dump-effective-config", "-")
        fields = read(first)
        assert fields["/source/energy"]["resolved"] == 2.0
        assert fields["/source/energy"]["requested"] == "2 MeV"
        assert fields["/source/energy"]["unit"] == "MeV"
        assert fields["/source/energy"]["origins"][0]["line"] > 0
        assert "requested" not in fields["/scoring/enabled"]
        assert fields["/scoring/enabled"]["origins"] == []
        override = read(run("--dump-effective-config", "-", "--threads", "2", "--run-name", "cli"))
        assert override["/run/threads"]["resolved"] == 2 and override["/run/threads"]["requested"] == 2
        assert override["/run/threads"]["origins"][0]["kind"] == "cli"
        assert override["/run/name"]["resolved"] == "cli"
        read(run("--dump-effective-config", "-", "--macro", str(macro)))
        assert run("--dump-effective-config", "-").stdout == first.stdout
        exported = folder / "配置.json"
        saved = run("--dump-effective-config", str(exported))
        assert saved.returncode == 0 and not saved.stdout.strip(), saved.stdout + saved.stderr
        assert exported.read_text(encoding="utf-8") == first.stdout
        assert not output.exists()
        for extra in [("--inspect-run",), ("--inspect-macro",), ("--capabilities",),
                      ("--check-geant4-data",), ("--help",), ("--ui",), ("--dry-run",)]:
            failed = run("--dump-effective-config", "-", *extra)
            assert failed.returncode != 0 and "mutually exclusive" in failed.stderr, failed.stderr
        for extra in [("--dump-effective-config",), ("--dump-effective-config", ""),
                      ("--dump-effective-config", "--threads", "2"),
                      ("--dump-effective-config", "-", "--dump-effective-config", "-")]:
            assert run(*extra).returncode != 0
        assert run("--dump-effective-config", str(folder)).returncode != 0
        missing_parent = folder / "missing-parent" / "snapshot.json"
        assert run("--dump-effective-config", str(missing_parent)).returncode != 0
        assert not missing_parent.parent.exists()
        bad_macro = folder / "bad.mac"
        bad_macro.write_text("/control/execute missing-child.mac\n", encoding="utf-8")
        before = exported.read_bytes()
        assert run("--dump-effective-config", str(exported), "--macro", str(bad_macro)).returncode != 0
        assert exported.read_bytes() == before and not output.exists()
        for target in (config, macro, exported):
            before = target.read_bytes()
            assert run("--dump-effective-config", str(target)).returncode != 0
            assert target.read_bytes() == before
        alias = folder / "input-hardlink.ini"
        os.link(config, alias)
        before = config.read_bytes()
        assert run("--dump-effective-config", str(alias)).returncode != 0
        assert config.read_bytes() == before
        config.write_text("[source]\nparticle=proton\nenergy_type=uniform\nenergy_min=1 MeV\nenergy_max=3 MeV\n", encoding="utf-8")
        distributed = read(run("--dump-effective-config", "-"))
        assert "/source/energy" not in distributed and distributed["/source/particle"]["resolved"] == "proton"
        config.write_text("[source.named]\nparticle=electron\nenergy=3 MeV\nposition=0 0 0 mm\ndirection=0 0 1\n", encoding="utf-8")
        named = read(run("--dump-effective-config", "-"))
        assert "/source/particle" not in named and "/source/energy" not in named
        phase_space = folder / "source.csv"
        phase_space.write_text(
            "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight\n"
            "0,0,1,0,proton,2212,0,0,0,0,0,1,10,0,1\n", encoding="utf-8")
        config.write_text("[source]\nphase_space_file=source.csv\n", encoding="utf-8")
        replay = read(run("--dump-effective-config", "-"))
        assert "/source/particle" not in replay and "/source/energy" not in replay
        assert not (folder / "run_summary.txt").exists()
    print("EffectiveConfig configured subset export passed")


if __name__ == "__main__":
    main()
