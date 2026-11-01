"""OUT-only import overlay; the original backend smoke is executed unchanged."""
from pathlib import Path
import importlib.util
import runpy
import sys

ROOT = Path.cwd().resolve()
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "gui"), str(ROOT / "gui/smoke_tests"), str(ROOT / "scripts")]
name = "g4usim_gui.core.experiment_workflow"
spec = importlib.util.spec_from_file_location(name, OUT / "experiment_workflow.py")
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
target = sys.argv[1]
sys.argv = [str(ROOT / "tools/test_assert_probe.py"), target, *sys.argv[2:]]
runpy.run_path(str(ROOT / "tools/test_assert_probe.py"), run_name="__main__")
