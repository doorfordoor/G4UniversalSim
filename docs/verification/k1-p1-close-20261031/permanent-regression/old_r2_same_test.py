"""Load archived r2 only in this process; run the unchanged new formal test."""
import hashlib
import importlib.util
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'scripts')]
import g4usim_gui.core
product = ROOT / 'out/collab/k1-relocation-candidate/archive-r2/experiment_bundle.py'
assert hashlib.sha256(product.read_bytes()).hexdigest() == '34db09d96260841411dc92306f4eab438d75792a4f74abacde3322c10b3d66c2'
spec = importlib.util.spec_from_file_location('g4usim_gui.core.experiment_bundle', product)
bundle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bundle
spec.loader.exec_module(bundle)
g4usim_gui.core.experiment_bundle = bundle
probe_spec = importlib.util.spec_from_file_location('formal_probe', ROOT / 'tools/test_assert_probe.py')
probe = importlib.util.module_from_spec(probe_spec)
probe_spec.loader.exec_module(probe)
raise SystemExit(probe.main(['test_assert_probe.py', str(ROOT / 'scripts/test_k1_staging_alias.py'),
                            '--evidence-root', str(OUT / 'windows-old-r2-evidence')]))
