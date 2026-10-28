"""Regression for locating the Geant4 data of an installed package (roadmap D).

The test builds a temporary "data root" whose entry names match the Geant4 dataset
folder names reported by the backend itself, then runs a copy of the backend in a
temporary folder with every Geant4 data variable removed from the environment:

  1. no geant4-data.txt: Geant4's own fallback (the compiled install prefix) is reported;
  2. geant4-data.txt with comments and a blank line names the data root: GEANT4_DATA_DIR
     is set from it and every dataset resolves under it;
  3. geant4-data.txt naming an empty folder: the required datasets are missing, the
     report says so and --check-geant4-data exits 1;
  4. a missing folder is reported in the note and Geant4 falls back again;
  5. with G4LEDATA set, the file is ignored (the user's environment wins).

Building the data root from the reported folder names keeps the check meaningful on
every installation layout: the Windows installer, conda-forge and Linux package trees
do not agree on folder names (``G4EMLOW8.6.1`` vs ``EMLOW8.6.1``), and the test must
not assume one of them. It also no longer hard-codes the Windows install directory nor
returns success when the datasets are absent: a silent zero-assertion "SKIP" used to
look like a green case in the report.
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


def check(exe: Path, env: dict[str, str]) -> tuple[int, dict]:
    result = subprocess.run([str(exe), "--check-geant4-data"], capture_output=True, text=True, env=env, timeout=120)
    return result.returncode, json.loads(result.stdout)


def discover(exe: Path) -> dict:
    """Ask the backend, with its current environment, which datasets Geant4 knows."""
    code, report = check(exe, dict(os.environ))
    assert code == 0, report
    assert report["required_complete"], report
    return report


def build_data_root(report: dict, root: Path) -> int:
    """Mirror every discovered dataset into ``root`` under its canonical folder name."""
    linked = 0
    for dataset in report["datasets"]:
        source = dataset.get("path")
        folder = dataset.get("folder")
        if not source or not folder or not Path(source).is_dir():
            continue
        target = root / folder
        if target.exists():
            continue
        target.symlink_to(Path(source), target_is_directory=True)
        linked += 1
    return linked


def main() -> int:
    if not EXE.is_file():
        print(f"backend executable missing: {EXE}")
        return 1
    work = Path(tempfile.mkdtemp(prefix="g4usim-data-"))
    try:
        # The required dataset folder is version-specific (11.3 ships
        # G4EMLOW8.6.1, 11.4 G4EMLOW8.8), so take it from the backend itself
        # instead of pinning one Geant4 release in the test.
        discovery = discover(EXE)
        dataset_folder = discovery["datasets"][0]["folder"]
        env = {k: v for k, v in os.environ.items() if not k.startswith("G4") and k != "GEANT4_DATA_DIR"}
        exe = work / "G4UniversalSim.exe"
        shutil.copy2(EXE, exe)
        data_file = work / "geant4-data.txt"

        provided = os.environ.get("G4USIM_GEANT4_DATA")
        if provided and (Path(provided) / dataset_folder).is_dir():
            data = Path(provided)
            print(f"data root from G4USIM_GEANT4_DATA: {data}")
        else:
            data = work / "data"
            data.mkdir()
            linked = build_data_root(discovery, data)
            print(f"data root mirrored into {data}: {linked} datasets")
            assert linked >= 5, linked

        code, report = check(exe, env)
        print(f"no file: exit {code}, GEANT4_DATA_DIR={report['geant4_data_dir']}, "
              f"G4LEDATA={report['datasets'][0]['path']}")
        assert report["schema"] == "g4usim_geant4_data_v1" and report["note"] == ""
        assert len(report["datasets"]) == 12 and sum(d["required"] for d in report["datasets"]) == 5

        data_file.write_text(f"# Geant4 data\n\n   {data}   \n# trailing comment\n", encoding="utf-8")
        code, report = check(exe, env)
        assert code == 0 and report["required_complete"], report
        assert Path(report["geant4_data_dir"]) == data and "geant4-data.txt" in report["note"], report
        assert all(Path(d["path"]).parent == data for d in report["datasets"] if d["found"]), report
        print(f"file: {sum(d['found'] for d in report['datasets'])} datasets under {report['geant4_data_dir']}")

        empty = work / "empty_data"
        empty.mkdir()
        data_file.write_text(f"{empty}\n", encoding="utf-8")
        code, report = check(exe, env)
        missing = [d["env"] for d in report["datasets"] if not d["found"]]
        unavailable = [d["env"] for d in report["datasets"] if d["required"] and not d["found"]]
        print(f"empty folder: exit {code}, missing {missing}")
        # An empty data root must not report completeness. Counting the exact number
        # of missing datasets would encode one installation layout: Geant4 also falls
        # back to its compiled prefix, so conda-forge still resolves the datasets whose
        # folder names it ships there.
        assert code == 1 and not report["required_complete"] and unavailable, report
        assert all(d["path"] is None for d in report["datasets"] if not d["found"]), report
        print(f"empty folder: required missing {unavailable}")

        data_file.write_text(f"{work / 'no_such_folder'}\n", encoding="utf-8")
        code, report = check(exe, env)
        assert "missing directory" in report["note"] and report["geant4_data_dir"] is None, report

        data_file.write_text(f"{empty}\n", encoding="utf-8")
        code, report = check(exe, {**env, "G4LEDATA": str(data / dataset_folder)})
        assert report["note"] == "" and report["geant4_data_dir"] is None, report
        assert report["datasets"][0]["path"] == str(data / dataset_folder), report["datasets"][0]
        print("G4LEDATA set: geant4-data.txt ignored")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_geant4_data_locator: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
