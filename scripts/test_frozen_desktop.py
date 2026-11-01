"""Build and execute desktop/helper packages on a clean native CI runtime.

This is a delivery test, independent of the Geant4 simulation/version matrix.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))
from build_package import build_gui, build_python_helper
from freeze_identity import verify as verify_frozen, RECEIPT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--reuse-gui", type=Path)
    parser.add_argument("--reuse-python-helper", type=Path)
    args = parser.parse_args()
    root = args.directory.absolute()
    root.mkdir(parents=True, exist_ok=False)
    package = root / "desktop"
    package.mkdir()
    for name in ("config", "scenarios", "test/geometry", "test/materials"):
        shutil.copytree(ROOT / name, package / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    gui_source = args.reuse_gui or build_gui(root / "gui-build", True)
    helper_source = args.reuse_python_helper or build_python_helper(root / "helper-build")
    verify_frozen(gui_source, root=ROOT, kind="gui", with_3d=True)
    verify_frozen(helper_source, root=ROOT, kind="python")
    shutil.copytree(gui_source, package / "gui")
    shutil.copytree(helper_source, package / "python")
    suffix = ".exe" if os.name == "nt" else ""
    gui = package / "gui" / ("G4UniversalSimGUI" + suffix)
    helper = package / "python" / ("G4USimPython" + suffix)
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith(("G4", "QT_")) and key.upper() not in
           {"GEANT4_DATA_DIR", "PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH"}}
    if os.name == "nt":
        system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        env["PATH"] = os.pathsep.join(map(str, (system / "System32", system)))
    else:
        env["PATH"] = "/usr/bin:/bin"
    env["QT_QPA_PLATFORM"] = "offscreen"
    results = []

    def execute(argv, name, timeout=180):
        result = subprocess.run(list(map(str, argv)), cwd=root, env=env, capture_output=True,
                                text=True, errors="replace", timeout=timeout)
        log = root / (name + ".log")
        log.write_bytes((result.stdout + result.stderr).replace("\r\n", "\n").encode("utf-8"))
        results.append({"name": name, "exit_code": result.returncode, "log": log.name,
                        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
        (root / "commands.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        return result

    report_path = root / "gui-self-test.json"
    launched = execute([gui, "--self-test", report_path], "frozen-gui")
    assert launched.returncode == 0, results[-1]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] and report["frozen"] and report["pages"] == 9
    assert report["plots"] and report["preview3d"]
    assert Path(report["application_root"]) == package
    assert Path(report["script_python"]) == helper
    assert report["zh_CN"] == "参数扫描"
    # Reuse of an evidence destination must fail instead of replacing it.
    original = report_path.read_bytes()
    refused = execute([gui, "--self-test", report_path], "existing-gui-report")
    assert refused.returncode != 0 and report_path.read_bytes() == original
    root_file = root / "helper.root"
    code = ("import numpy as np,uproot; p=" + repr(str(root_file)) + "; "
            "f=uproot.recreate(p); f['sample']={'value':np.array([1.,2.,3.])}; f.close(); "
            "r=uproot.open(p); assert list(r['sample']['value'].array(library='np'))==[1.,2.,3.]; "
            "r.close(); print('ROOT roundtrip verified')")
    scientific = execute([helper, "-c", code], "frozen-python-root")
    assert scientific.returncode == 0 and root_file.is_file()
    assert "ROOT roundtrip verified" in scientific.stdout
    # Real frozen-import failure, before Qt app.py can create a report itself.
    modules = list((package / "gui/_internal/PySide6").glob("QtCore.pyd" if os.name == "nt" else "QtCore*.so"))
    assert len(modules) == 1, modules
    original_module = modules[0]
    quarantined = original_module.with_name(original_module.name + ".test-disabled")
    original_module.rename(quarantined)
    try:
        failed_path = root / "gui-import-failure.json"
        failed = execute([gui, "--self-test", failed_path], "frozen-gui-import-failure", timeout=45)
        assert failed.returncode == 1
        failure = json.loads(failed_path.read_text(encoding="utf-8"))
        assert failure["ok"] is False and failure["stage"] == "startup"
    finally:
        quarantined.rename(original_module)
    identities = {}
    for component, kind, with_3d in (("gui", "gui", True), ("python", "python", False)):
        receipt = verify_frozen(package / component, root=ROOT, kind=kind, with_3d=with_3d)
        assert receipt["files"] and receipt["sources"]
        identities[component] = {"receipt_sha256": hashlib.sha256((package / component / RECEIPT).read_bytes()).hexdigest(),
                                 "files": len(receipt["files"]), "source_files": len(receipt["sources"])}
    evidence = {"schema": "g4usim_frozen_desktop_delivery_v1", "status": "passed",
                "platform": sys.platform, "package": str(package), "commands": results,
                "identities": identities,
                "scope": "frozen GUI startup/natural exit and Python ROOT read-write; no Geant4 simulation"}
    (root / "delivery.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("Frozen desktop and scientific helper delivery passed")


if __name__ == "__main__":
    main()
