"""Reject non-finite numeric configuration values before Geant4 objects are created."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def run_dry(exe: Path, config: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(exe), "--config", str(config), "--dry-run", "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=180, check=False,
    )


def main() -> int:
    exe = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    assert exe.is_file(), exe
    with tempfile.TemporaryDirectory(prefix="g4usim-finite-") as directory:
        temp = Path(directory)
        config_dir = temp / "config"
        shutil.copytree(ROOT / "config", config_dir)
        main_ini = config_dir / "main.ini"
        original = main_ini.read_text(encoding="utf-8")

        completed = run_dry(exe, main_ini, temp / "out-valid")
        assert completed.returncode == 0, (completed.stdout + completed.stderr)[-4000:]
        assert "dry-run completed" in completed.stdout, completed.stdout[-2000:]

        main_ini.write_text(original + "\n[biasing]\nenabled = true\n\n[biasing.xs.proton.elastic]\nfactor = inf\n", encoding="utf-8")
        completed = run_dry(exe, main_ini, temp / "out-inf")
        text = completed.stdout + completed.stderr
        assert completed.returncode != 0, text[-4000:]
        assert "Config value 'inf' is not a finite double" in text, text[-4000:]

        main_ini.write_text(original + "\n[biasing]\nenabled = true\n\n[biasing.xs.proton.elastic]\nfactor = 2.0\nmin_weight = nan\n", encoding="utf-8")
        completed = run_dry(exe, main_ini, temp / "out-nan")
        text = completed.stdout + completed.stderr
        assert completed.returncode != 0, text[-4000:]
        assert "Config value 'nan' is not a finite double" in text, text[-4000:]

        main_ini.write_text(original, encoding="utf-8")
        completed = run_dry(exe, main_ini, temp / "out-restored")
        assert completed.returncode == 0, (completed.stdout + completed.stderr)[-4000:]

    print("config value finiteness: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
