"""Focused candidate validation; never rewrites the first formal reports."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = Path.cwd().resolve()
OUT = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

original = ROOT / "gui/g4usim_gui/core/experiment_workflow.py"
smoke = ROOT / "gui/smoke_tests/smoke_f4_inspect_backend.py"
tracked_before = subprocess.check_output(["git", "-c", "core.longpaths=true", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT).decode()
receipt = {"kind": "OUT-only focused candidate; not a formal matrix rerun", "head": subprocess.check_output(["git", "rev-parse", "HEAD"],cwd=ROOT).decode().strip(), "original_product_sha256": sha(original), "unchanged_old_smoke_sha256": sha(smoke), "candidate_product_sha256": sha(OUT / "experiment_workflow.py"), "results": []}
cases = [
    ("permanent-regression", OUT / "test_external_inspect_source_scope.py", None, None, None),
    ("windows113-old-f4-inspect", smoke, ROOT / "out/build-i2-formal113/Release/G4UniversalSim.exe", Path("D:/ProgramFiles/Geant4/bin"), Path("D:/ProgramFiles/Geant4/share/Geant4/data")),
    ("windows114-old-f4-inspect", smoke, ROOT / "out/build-i2-windows114/Release/G4UniversalSim.exe", ROOT / "out/dependencies/geant4-11.4.3/geant4-11.4.3-win64/bin", ROOT / "out/i2-controlled/windows114-data/data"),
]
for name, target, exe, sdk_bin, data in cases:
    env = dict(os.environ)
    removed = [key for key in env if (key.upper().startswith("G4") and key.upper().endswith("DATA")) or key.upper() == "GEANT4_DATA_DIR"]
    for key in removed:
        env.pop(key)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if exe:
        assert exe.is_file() and sdk_bin.is_dir() and data.is_dir()
        expected = "ea4427f57ef65d176144e1ea8f7a5914dff66265b8179989eca851588a2a133f" if "113" in name else "bf75f92288577ed7d7e24163e973de71d81afb79866c9080e588d790bd0e05ec"
        assert sha(exe) == expected
        env.update(G4USIM_EXE=str(exe), GEANT4_DATA_DIR=str(data), G4USIM_GEANT4_DATA=str(data))
        env["PATH"] = str(sdk_bin) + os.pathsep + env.get("PATH", "")
    command = [sys.executable, "-B", str(OUT / "run_overlay.py"), str(target)]
    log = OUT / (name + ".log")
    assert not log.exists(), "Preserve first candidate run logs; choose a new attempt directory"
    print("START", name, flush=True)
    start = time.monotonic()
    with log.open("wb") as stream:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        row = {"name": name, "pid": process.pid, "command": command, "log": str(log), "status": "running", "cleared_data_variables": sorted(removed)}
        if exe:
            row.update(executable=str(exe), executable_sha256=sha(exe), sdk_bin=str(sdk_bin), data_root=str(data))
        receipt["results"].append(row)
        (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        code = process.wait()
    markers = re.findall(rb"G4USIM_ASSERTS=(\d+)", log.read_bytes())
    row.update(exit_code=code, seconds=round(time.monotonic()-start, 3), assertion_entrances=int(markers[-1]) if markers else 0, log_sha256=sha(log), status="passed" if code == 0 and markers else "failed")
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("END", name, row["status"], code, row["assertion_entrances"], flush=True)
    if code:
        print(log.read_text(encoding="utf-8", errors="replace")[-3500:], flush=True)
receipt["original_product_unchanged"] = sha(original) == receipt["original_product_sha256"]
receipt["original_smoke_unchanged"] = sha(smoke) == receipt["unchanged_old_smoke_sha256"]
receipt["tracked_status_unchanged"] = tracked_before == subprocess.check_output(["git", "-c", "core.longpaths=true", "status", "--porcelain", "--untracked-files=no"],cwd=ROOT).decode()
(OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
raise SystemExit(0 if all(row["status"] == "passed" for row in receipt["results"]) and receipt["original_product_unchanged"] and receipt["original_smoke_unchanged"] else 1)
