from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.core.project import G4USimProject, load_project, save_project


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "project.json"
        project = G4USimProject(projectName="smoke", threads=2, seed="123")
        project.runSettings.run_name = "smoke_run"
        save_project(project, path)
        loaded = load_project(path)
        assert loaded.projectName == "smoke"
        assert loaded.threads == 2
        assert loaded.runSettings.run_name == "smoke_run"
    print("smoke_project_io: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
