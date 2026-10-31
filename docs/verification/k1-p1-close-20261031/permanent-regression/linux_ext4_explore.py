"""Use Linux native temporary filesystem for real renameat2 semantics."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import PySide6

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
owned = Path(tempfile.mkdtemp(prefix='k1-p1-permanent-regression-20261031-'))
assert owned.is_absolute() and owned.parent == Path(tempfile.gettempdir()).resolve()
case = owned / 'evidence'
probe_spec = importlib.util.spec_from_file_location('formal_probe', ROOT / 'tools/test_assert_probe.py')
probe = importlib.util.module_from_spec(probe_spec)
probe_spec.loader.exec_module(probe)
try:
    status = probe.main(['test_assert_probe.py', str(ROOT / 'scripts/test_k1_staging_alias.py'),
                         '--evidence-root', str(case)])
finally:
    copied = OUT / 'wsl-linux-ext4-current-evidence'
    assert copied.absolute().is_relative_to(OUT.resolve())
    shutil.copytree(case, copied)
    digests = lambda root: {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in root.rglob('*') if p.is_file()}
    assert digests(case) == digests(copied)
    (OUT / 'wsl-runtime.json').write_text(json.dumps({'python': sys.executable, 'python_version': sys.version,
        'qt': PySide6.__version__, 'platform': sys.platform, 'native_fixture': str(case),
        'copied_evidence': str(copied), 'native_fixture_retained': True,
        'copy_verified_sha256': digests(copied), 'geant4_backend': 'not_started'}, indent=2) + '\n')
raise SystemExit(status)
