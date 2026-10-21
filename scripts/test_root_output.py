"""Real Geant4 regression for the G4AnalysisManager ROOT output layer.

Runs the backend in isolated temporary directories and checks:
  * format=both: every ROOT object equals the CSV of the same run (2 threads, 2 runs,
    edep + dose + fluence), via scripts/compare_root_csv.py;
  * format=root: ROOT files only, no CSV data files;
  * default format: CSV only, no ROOT file (backward compatibility);
  * invalid [output]/format and /AIHL/output/setFormat after initialization fail;
  * --capabilities advertises the ROOT contract.
Requires uproot.
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
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import compare_root_csv  # noqa: E402  (needs uproot)
except SystemExit:
    print("SKIP: uproot is not installed")
    sys.exit(2)

CONFIG = """
[run]
threads = {threads}
seed = 4242
[output]
{format_line}
[materials]
file = {root}/config/materials/material.ini
[geometry]
template = simple_box
config = {root}/config/geometry/hit_smoke_box.ini
[physics]
reference = FTFP_BERT_EMZ
default_cut = 10 um
[source]
particle = e-
energy = 2 MeV
position_type = point
position = 0,0,-9 mm
direction = 0,0,1
[scoring]
enabled = true
hits = true
event_edep = true
edep = true
dose = true
fluence = true
auto_create_default_scorers = true
[scoring.edep]
bins = 50
min = 0 MeV
max = 2.5 MeV
"""

DATA_CSV_PREFIXES = ("hits", "event_edep", "hist_", "edep_", "dose_", "fluence_")


def run(work: Path, name: str, format_line: str, macro: str, threads: int = 2,
        expected_ok: bool = True) -> tuple[Path, str]:
    config = work / f"{name}.ini"
    config.write_text(CONFIG.format(threads=threads, format_line=format_line,
                                    root=ROOT.as_posix()), encoding="utf-8")
    mac = work / f"{name}.mac"
    mac.write_text(macro, encoding="utf-8")
    output = work / name
    result = subprocess.run([str(EXE), "--config", str(config), "--macro", str(mac), "--output", str(output)],
                            cwd=ROOT, capture_output=True, text=True, errors="replace", timeout=300)
    log = result.stdout + result.stderr
    (work / f"{name}.log").write_text(log, encoding="utf-8")
    if expected_ok:
        assert result.returncode == 0, f"{name}: exit={result.returncode}\n{log[-2000:]}"
    else:
        assert result.returncode != 0, f"{name}: expected failure but exit=0"
    return output, log


def data_csvs(output: Path) -> list[str]:
    return sorted(p.name for p in output.glob("*.csv") if p.name.startswith(DATA_CSV_PREFIXES))


def main() -> int:
    assert EXE.is_file(), f"backend executable missing: {EXE}"
    work = Path(tempfile.mkdtemp(prefix="g4usim_root_"))
    try:
        two_runs = "/run/initialize\n/run/beamOn 60\n/run/beamOn 20\n"

        # 1. both: ROOT == CSV for two runs on two worker threads.
        output, _ = run(work, "both", "format = both", two_runs)
        roots = sorted(p.name for p in output.glob("*.root"))
        assert roots == ["g4usim.root", "g4usim_r1.root"], roots
        for run_id in (0, 1):
            report = compare_root_csv.check(str(output), run_id)
            print(f"both run {run_id}: " + "; ".join(report))
            assert any(item.startswith("dose:") for item in report), report
            assert any(item.startswith("fluence:") for item in report), report
        metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
        assert metadata["schema"] == "run_metadata_json_v1"
        assert metadata["values"]["output_format"] == "both"
        assert metadata["values"]["output_root_schema_version"] == "2"
        assert [r["completed_events"] for r in metadata["runs"]] == [60, 20], metadata["runs"]
        schemas = {Path(f["path"]).name: f["schema"] for f in metadata["generated_files"]}
        assert schemas.get("g4usim.root") == "g4usim_root_v2", schemas
        assert schemas.get("g4usim_r1.root") == "g4usim_root_v2", schemas

        # 2. root only: no CSV data files.
        output, _ = run(work, "root_only", "format = root", "/run/initialize\n/run/beamOn 30\n")
        assert (output / "g4usim.root").is_file()
        assert data_csvs(output) == [], data_csvs(output)
        print("root-only: ok")

        # 3. default (no key): unchanged CSV behaviour, no ROOT file.
        output, _ = run(work, "default", "", "/run/initialize\n/run/beamOn 10\n")
        assert not list(output.glob("*.root")), list(output.glob("*.root"))
        assert any(name.startswith("hits_t") for name in data_csvs(output)), data_csvs(output)
        print("default csv: ok")

        # 4. invalid configuration value fails before the run.
        _, log = run(work, "bad_format", "format = parquet", "/run/initialize\n/run/beamOn 1\n", expected_ok=False)
        assert "Unknown output format" in log, log[-1500:]
        print("invalid format rejected: ok")

        # 5. format cannot change after initialization.
        _, log = run(work, "late_format", "format = csv",
                     "/run/initialize\n/AIHL/output/setFormat root\n/run/beamOn 1\n", expected_ok=False)
        print("late setFormat rejected: ok")

        # 6. capabilities.
        caps = json.loads(subprocess.run([str(EXE), "--capabilities"], capture_output=True, text=True,
                                         check=True, cwd=EXE.parent).stdout)
        outputs = caps["outputs"]
        assert outputs["formats"] == ["csv", "root", "both"], outputs
        assert outputs["root"]["thread_merge"] is True and outputs["root"]["schema_version"] == 2, outputs
        print("capabilities: ok")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_root_output: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
