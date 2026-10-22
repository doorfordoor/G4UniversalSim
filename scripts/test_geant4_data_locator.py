"""Regression for locating the Geant4 data of an installed package (roadmap D).

A copy of the backend in a temporary folder (DLLs still from PATH) with every Geant4
data variable removed from the environment:
  1. no geant4-data.txt: Geant4's own fallback (the compiled install prefix) is reported;
  2. geant4-data.txt with comments and a blank line names the data folder: GEANT4_DATA_DIR
     is set from it and every dataset resolves under it;
  3. geant4-data.txt naming an empty folder: the required datasets are missing, the
     report says so and --check-geant4-data exits 1;
  4. a missing folder is reported in the note and Geant4 falls back again;
  5. with G4LEDATA set, the file is ignored (the user's environment wins).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
DATA = Path(os.environ.get("G4USIM_GEANT4_DATA", "D:/ProgramFiles/Geant4/share/Geant4/data"))


def check(exe: Path, env: dict[str, str]) -> tuple[int, dict]:
    result = subprocess.run([str(exe), "--check-geant4-data"], capture_output=True, text=True, env=env, timeout=120)
    return result.returncode, json.loads(result.stdout)


def main() -> int:
    if not EXE.is_file():
        print(f"backend executable missing: {EXE}")
        return 1
    if not (DATA / "G4EMLOW8.6.1").is_dir():
        print(f"SKIP: Geant4 data not found at {DATA} (set G4USIM_GEANT4_DATA)")
        return 0
    env = {k: v for k, v in os.environ.items() if not k.startswith("G4") and k != "GEANT4_DATA_DIR"}
    work = Path(tempfile.mkdtemp(prefix="g4usim-data-"))
    try:
        exe = work / "G4UniversalSim.exe"
        shutil.copy2(EXE, exe)
        data_file = work / "geant4-data.txt"

        code, report = check(exe, env)
        print(f"no file: exit {code}, GEANT4_DATA_DIR={report['geant4_data_dir']}, "
              f"G4LEDATA={report['datasets'][0]['path']}")
        assert report["schema"] == "g4usim_geant4_data_v1" and report["note"] == ""
        assert len(report["datasets"]) == 12 and sum(d["required"] for d in report["datasets"]) == 5

        data_file.write_text(f"# Geant4 data\n\n   {DATA}   \n# trailing comment\n", encoding="utf-8")
        code, report = check(exe, env)
        assert code == 0 and report["required_complete"], report
        assert Path(report["geant4_data_dir"]) == DATA and "geant4-data.txt" in report["note"], report
        assert all(Path(d["path"]).parent == DATA for d in report["datasets"] if d["found"]), report
        print(f"file: {sum(d['found'] for d in report['datasets'])} datasets under {report['geant4_data_dir']}")

        empty = work / "empty_data"
        empty.mkdir()
        data_file.write_text(f"{empty}\n", encoding="utf-8")
        code, report = check(exe, env)
        missing = [d["env"] for d in report["datasets"] if d["required"] and not d["found"]]
        print(f"empty folder: exit {code}, missing required {missing}")
        assert code == 1 and not report["required_complete"] and len(missing) == 5, report

        data_file.write_text(f"{work / 'no_such_folder'}\n", encoding="utf-8")
        code, report = check(exe, env)
        assert "missing directory" in report["note"] and report["geant4_data_dir"] is None, report

        data_file.write_text(f"{empty}\n", encoding="utf-8")
        code, report = check(exe, {**env, "G4LEDATA": str(DATA / "G4EMLOW8.6.1")})
        assert report["note"] == "" and report["geant4_data_dir"] is None, report
        assert report["datasets"][0]["path"] == str(DATA / "G4EMLOW8.6.1"), report["datasets"][0]
        print("G4LEDATA set: geant4-data.txt ignored")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_geant4_data_locator: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
