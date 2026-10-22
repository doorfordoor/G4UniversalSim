"""Installs, checks and uninstalls the Inno Setup package silently (roadmap D).

    gui\\.venv\\Scripts\\python.exe packaging\\test_installer.py [out\\G4UniversalSim-<version>-win64-setup.exe]

Per-user silent install into a temporary folder with GEANT4_DATA_DIR set (the data
page takes it as its default, as it would show it to a user), then with a clean
environment: geant4-data.txt names that folder, --check-geant4-data finds every
required dataset, the installed GUI passes --self-test and finds the installed
backend; then the uninstaller removes the folder, the Start-menu group and its
registry entry.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "{6C1F4E2B-8A57-4B0D-9C3E-5D2A7F1B9E44}_is1"


def uninstall_entry() -> bool:
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}")
        return True
    except OSError:
        return False


def main() -> int:
    setups = sorted((ROOT / "out").glob("G4UniversalSim-*-win64-setup.exe"))
    setup = Path(sys.argv[1]) if len(sys.argv) > 1 else (setups[-1] if setups else None)
    if setup is None or not setup.is_file():
        print("installer not found; run packaging/build_package.py first")
        return 1
    if uninstall_entry():
        print("G4UniversalSim is already installed for this user; uninstall it before this test")
        return 1
    data = Path("D:/ProgramFiles/Geant4/share/Geant4/data")
    env = {k: v for k, v in os.environ.items() if not k.startswith("G4")}
    env["GEANT4_DATA_DIR"] = str(data)
    target = Path(tempfile.mkdtemp(prefix="g4usim-install-")) / "G4UniversalSim"
    start_menu = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/G4UniversalSim"
    try:
        result = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER",
                                 f"/DIR={target}"], env=env, timeout=900)
        assert result.returncode == 0, f"setup exit code {result.returncode}"
        assert uninstall_entry(), "no uninstall registry entry"
        assert (start_menu / "G4UniversalSim.lnk").is_file(), "no Start-menu shortcut"
        data_file = (target / "bin" / "geant4-data.txt").read_text(encoding="utf-8")
        assert str(data) in data_file, data_file
        print(f"installed to {target}; geant4-data.txt -> {data}")

        clean = {k: v for k, v in os.environ.items() if not k.startswith("G4") and k != "GEANT4_DATA_DIR"}
        system = Path(clean.get("SystemRoot", r"C:\Windows"))
        clean["PATH"] = os.pathsep.join([str(system / "System32"), str(system)])
        check = subprocess.run([str(target / "bin" / "G4UniversalSim.exe"), "--check-geant4-data"],
                               capture_output=True, text=True, env=clean)
        report = json.loads(check.stdout)
        assert check.returncode == 0 and report["required_complete"], check.stdout
        print(f"installed backend finds {sum(d['found'] for d in report['datasets'])} datasets "
              f"({report['note']})")
        report_path = target.parent / "self_test.json"
        gui = subprocess.run([str(target / "gui" / "G4UniversalSimGUI.exe"), "--self-test", str(report_path)],
                             env=clean, timeout=300)
        self_test = json.loads(report_path.read_text(encoding="utf-8"))
        assert gui.returncode == 0 and self_test["ok"] and self_test["frozen"], self_test
        assert Path(self_test["default_backend"]) == target / "bin" / "G4UniversalSim.exe", self_test
        print(f"installed GUI self-test ok: runs go to {self_test['runs_root']}")

        uninstaller = next(target.glob("unins*.exe"))
        result = subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=600)
        assert result.returncode == 0, f"uninstaller exit code {result.returncode}"
        # the uninstaller finishes from a temporary copy; give it a moment to delete itself
        for _ in range(60):
            if not target.exists() and not uninstall_entry():
                break
            subprocess.run(["timeout", "/t", "1", "/nobreak"], capture_output=True, shell=True)
        leftovers = [str(p) for p in target.rglob("*")] if target.exists() else []
        assert not leftovers, leftovers[:10]
        assert not uninstall_entry(), "registry entry left behind"
        assert not start_menu.exists(), "Start-menu group left behind"
        print("uninstalled: folder, Start-menu group and registry entry removed")
    finally:
        if uninstall_entry() and target.exists():
            uninstaller = next(target.glob("unins*.exe"), None)
            if uninstaller:
                subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=600)
        shutil.rmtree(target.parent, ignore_errors=True)
    print("test_installer: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
