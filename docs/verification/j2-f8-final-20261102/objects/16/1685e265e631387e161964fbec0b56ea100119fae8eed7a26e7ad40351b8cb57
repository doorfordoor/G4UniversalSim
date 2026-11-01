"""OUT-only real Windows short-path diagnosis and exact smoke proposal."""
import ast
import ctypes
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
TARGET = ROOT / 'gui/smoke_tests/smoke_j2_geometry.py'
PROPOSAL = OUT / 'smoke_j2_geometry.py'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    path = OUT / name
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')

def short_path(path):
    buffer = ctypes.create_unicode_buffer(32768)
    size = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    assert 0 < size < len(buffer), (size, str(path))
    result = Path(buffer.value)
    assert '~' in str(result) and result.samefile(path)
    return result

def child(mode):
    sys.path.insert(0, str(ROOT / 'gui'))
    if mode == 'diagnosis':
        import tempfile
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
        from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
        from g4usim_gui.editors.geometry_editor_model import geometry_document_to_snapshot
        app = QApplication.instance() or QApplication([])
        rows = []
        with tempfile.TemporaryDirectory(prefix='reload diagnosis ') as temporary:
            long_dir = Path(temporary).resolve()
            source = long_dir / 'geometry.ini'
            source.write_text('[geometry]\ntype=hierarchical\nworld=world\n[volume.world]\nshape=box\nsize=1 m,1 m,1 m\nmaterial=G4_AIR\n', encoding='utf-8')
            alias_source = short_path(long_dir) / 'geometry.ini'
            for requested in (source, alias_source):
                page = ConfigBuilderPage()
                try:
                    page.geometry_config.setText(str(requested))
                    page.reload_geometry()
                    actual = page.geometry_document.source_path
                    assert actual == str(requested.resolve())
                    assert Path(actual).samefile(requested)
                    assert sha(Path(actual)) == sha(requested)
                    assert not page.geometry_document.source_errors
                    before = geometry_document_to_snapshot(page.geometry_document)
                    page.geometry_config.setText(str(requested.parent / 'missing.ini'))
                    page.reload_geometry()
                    assert page.geometry_document.source_path == actual
                    assert page.geometry_document.source_errors
                    assert not getattr(page.geometry_summary, '_f4_read_success', True)
                    assert [v.name for v in page.geometry_document.volumes] == [v['name'] for v in before['volumes']]
                    rows.append(dict(requested=str(requested), actual=actual, resolved=str(requested.resolve()), literal_equal=actual == str(requested), samefile=Path(actual).samefile(requested), sha256=sha(requested), failed_reload_kept_original_anchor=True))
                finally:
                    page.close()
                    page.deleteLater()
                    app.processEvents()
                    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            assert rows[0]['literal_equal'] and not rows[1]['literal_equal']
            save('path-diagnosis.json', dict(rows=rows, temp_environment=os.environ.get('TEMP'), qt_platform=app.platformName()))
        return 0
    spec = importlib.util.spec_from_file_location('original_assert_probe', ROOT / 'tools/test_assert_probe.py')
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    target = TARGET if mode == 'baseline-short' else PROPOSAL
    if target == PROPOSAL:
        def run_target(path, run_name=None, **kwargs):
            assert Path(path).resolve() == target.resolve()
            namespace = {'__name__': run_name, '__file__': str(TARGET), '__package__': None}
            exec(compile(target.read_bytes(), str(target), 'exec'), namespace)
            return namespace
        probe.runpy.run_path = run_target
    return probe.main(['probe', str(target)])

if len(sys.argv) > 1:
    raise SystemExit(child(sys.argv[1]))

assert not (OUT / 'receipt.json').exists()
original = TARGET.read_text(encoding='utf-8')
old = "        # Explicit import after a no-source document still replaces it normally.\n        page.geometry_config.setText(str(source)); page.reload_geometry()\n        assert page.geometry_document.source_path==str(source)\n"
new = "        # Explicit import records the canonical source anchor (including Windows 8.3 aliases).\n        page.geometry_config.setText(str(source)); page.reload_geometry()\n        reloaded_source=Path(page.geometry_document.source_path)\n        assert page.geometry_document.source_path==str(source.resolve()), (page.geometry_document.source_path, str(source), str(source.resolve()))\n        assert reloaded_source.samefile(source)\n        assert hashlib.sha256(reloaded_source.read_bytes()).hexdigest()==hashlib.sha256(source.read_bytes()).hexdigest()\n"
assert original.count(old) == 1
candidate = original.replace(old, new)
PROPOSAL.write_bytes(candidate.encode('utf-8'))
(OUT / 'baseline.py').write_bytes(TARGET.read_bytes())
(OUT / 'fix.patch').write_bytes(''.join(difflib.unified_diff(original.splitlines(keepends=True), candidate.splitlines(keepends=True), fromfile='a/gui/smoke_tests/smoke_j2_geometry.py', tofile='b/gui/smoke_tests/smoke_j2_geometry.py')).encode('utf-8'))
assert candidate.count('assert page.geometry_document.source_path==str(source)\n') == 1
compile(candidate, str(PROPOSAL), 'exec')
bound = [TARGET, ROOT / 'gui/g4usim_gui/widgets/config/geometry.py', ROOT / 'gui/g4usim_gui/parsers/geometry_parser.py', ROOT / 'gui/g4usim_gui/editors/geometry_editor_model.py', ROOT / 'tools/test_assert_probe.py']
before = {str(p.relative_to(ROOT)): sha(p) for p in bound}
temp_root = OUT / 'temporary folder with long name'
temp_root.mkdir()
alias = short_path(temp_root)
save('temporary-identity.json', dict(long=str(temp_root), short=str(alias), samefile=alias.samefile(temp_root)))
results = []
for mode, expected in [('diagnosis', 0), ('baseline-short', 1), ('candidate-short', 0), ('candidate-long', 0)]:
    env = dict(os.environ)
    for key in ('QT_SCALE_FACTOR', 'QT_SCREEN_SCALE_FACTORS', 'QT_PLUGIN_PATH', 'PYTHONHOME', 'PYTHONPATH'):
        env.pop(key, None)
    env.update(QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1', TEMP=str(alias if 'short' in mode else temp_root), TMP=str(alias if 'short' in mode else temp_root))
    result = subprocess.run([sys.executable, '-B', str(Path(__file__)), mode], cwd=ROOT, env=env, capture_output=True)
    log = OUT / (mode + '.log')
    log.write_bytes(result.stdout + result.stderr)
    markers = re.findall(rb'G4USIM_ASSERTS=(\d+)', result.stdout)
    row = dict(mode=mode, exit_code=result.returncode, expected_exit_code=expected, assertions=int(markers[-1]) if markers else None, log=log.name, log_sha256=sha(log))
    results.append(row)
    print(json.dumps(row), flush=True)
    if result.returncode != expected:
        print((result.stdout + result.stderr).decode(errors='replace')[-2200:], flush=True)
        break
after = {name: sha(ROOT / name) for name in before}
check = subprocess.run(['git', '-c', 'core.longpaths=true', 'apply', '--check', str(OUT / 'fix.patch')], cwd=ROOT, capture_output=True)
(OUT / 'patch-check.log').write_bytes(check.stdout + check.stderr)
receipt = dict(status='pass' if len(results) == 4 and all(row['exit_code'] == row['expected_exit_code'] for row in results) and before == after and check.returncode == 0 else 'fail', candidate_sha256=sha(PROPOSAL), patch_sha256=sha(OUT / 'fix.patch'), before=before, after=after, results=results, patch_check_exit=check.returncode, original_failed_read_literal_assert_retained=True, product_unchanged=True, source_loader='candidate bytes compiled at OUT filename for unchanged v3 probe; __file__ points at tracked script only to retain repository ROOT; no product monkeypatch', boundary='Local real Windows 8.3 alias reproduces old assertion. Actual CI trace has no actual/expected path; this is not proof of exact CI TEMP spelling. No native UI/backend/CI/profile/ tracked writes.')
save('receipt.json', receipt)
print(json.dumps({k: receipt[k] for k in ('status', 'candidate_sha256', 'patch_sha256')}), flush=True)
raise SystemExit(0 if receipt['status'] == 'pass' else 1)
