"""In-memory source overlay for narrow UI checks. No tracked edits."""
from pathlib import Path
import argparse
import importlib.abc
import importlib.util
import json
import os
import runpy
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('target')
parser.add_argument('--baseline', action='store_true')
parser.add_argument('--case', default='cwd')
args = parser.parse_args()
overlay = HERE / ('baseline' if args.baseline else 'files')
temporary = HERE / 'tmp'
temporary.mkdir(exist_ok=True)
os.environ.update(TEMP=str(temporary), TMP=str(temporary), QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1')
tempfile.tempdir = None
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'gui/smoke_tests'), str(ROOT / 'gui'), str(ROOT / 'scripts'), str(ROOT / 'tools')]

class Overlay(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        relative = Path('gui') / Path(*fullname.split('.')).with_suffix('.py') if fullname.startswith('g4usim_gui.') else Path('gui/smoke_tests') / (fullname + '.py')
        candidate = overlay / relative
        if candidate.is_file():
            spec = importlib.util.spec_from_loader(fullname, self, origin=str(candidate))
            spec.loader_state = (candidate, ROOT / relative)
            return spec
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        source, original = module.__spec__.loader_state
        module.__file__ = str(original)
        exec(compile(source.read_bytes(), str(source), 'exec'), module.__dict__)

sys.meta_path.insert(0, Overlay())
if args.target == 'reproduce':
    target = HERE / 'reproduce.py'
    original = target
    target_args = ['--case', args.case, '--label', 'baseline' if args.baseline else 'candidate']
else:
    target = HERE / 'files/gui/smoke_tests' / args.target
    original = ROOT / 'gui/smoke_tests' / args.target
    target_args = []
actual_run_path = runpy.run_path
def run_path(path, init_globals=None, run_name=None):
    if Path(path).resolve() != target.resolve():
        return actual_run_path(path, init_globals, run_name)
    sys.path.insert(0, str(original.parent))
    namespace = dict(init_globals or {}, __file__=str(original), __name__=run_name or '<run_path>', __package__=None)
    exec(compile(target.read_bytes(), str(target), 'exec'), namespace)
    return namespace
runpy.run_path = run_path
import test_assert_probe
raise SystemExit(test_assert_probe.main(['probe', str(target), *target_args]))
