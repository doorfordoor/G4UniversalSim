"""Delegate replay to the installed unified CLI; no backend orchestration here."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "g4usim_gui.experiment_cli",
        "--bundle", str(Path(__file__).resolve().parent), *sys.argv[1:]]))
