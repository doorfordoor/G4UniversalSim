"""Independent out-only execution: draft bytes, original ROOT/main, standard assert probe."""
import hashlib, importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
DRAFT = ROOT / 'out/collab/j2-static-fixture-patch-draft'
NAMES = ('test_k1_bundle.py', 'test_config_migration.py')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

if len(sys.argv) > 1:
    name = sys.argv[1]
    assert name in NAMES
    sys.dont_write_bytecode = True
    temporary = OUT / ('temp-' + name)
    temporary.mkdir(exist_ok=True)
    tempfile.tempdir = str(temporary)
    spec = importlib.util.spec_from_file_location('independent_assert_probe', ROOT / 'tools/test_assert_probe.py')
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    target = (DRAFT / 'proposed/scripts' / name).resolve()
    original_run = probe.runpy.run_path
    def draft_run(path, run_name=None, **kwargs):
        assert Path(path).resolve() == target
        ns = {'__name__': run_name, '__file__': str(ROOT / 'scripts' / name), '__package__': None}
        exec(compile(target.read_bytes(), str(target), 'exec'), ns)
        return ns
    probe.runpy.run_path = draft_run
    args = ['--component', '--evidence-root', str(OUT / 'k1-evidence')] if name == NAMES[0] else []
    sys.path.insert(0, str(ROOT / 'scripts'))
    raise SystemExit(probe.main(['probe', str(target), *args]))

assert not (OUT / 'geometry-execution.json').exists(), 'Preserve previous receipts'
paths = [ROOT / 'scripts' / n for n in NAMES]
paths += list((ROOT / 'gui/g4usim_gui').rglob('*.py'))
before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
receipt = {'method': 'Standard assert probe executing complete unchanged draft bytes and __main__, with original repository __file__ for ROOT; no product module substitution; all fixtures/evidence under out.', 'scripts': []}
for name in NAMES:
    draft = DRAFT / 'proposed/scripts' / name
    log = OUT / (name + '.log')
    assert not log.exists()
    result = subprocess.run([sys.executable, '-B', str(Path(__file__)), name], cwd=ROOT, capture_output=True)
    log.write_bytes(result.stdout + result.stderr)
    receipt['scripts'].append({'path': 'scripts/' + name, 'draft_sha256': sha(draft), 'exit_code': result.returncode, 'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)})
    print(name, result.returncode, result.stdout.decode(errors='replace')[-1200:], result.stderr.decode(errors='replace')[-2000:])
after = {str(p.relative_to(ROOT)): sha(p) for p in paths}
assert before == after, 'Tracked script/product bytes changed'
receipt['tracked_script_and_gui_bytes_unchanged'] = True
receipt['status'] = 'pass' if all(x['exit_code'] == 0 for x in receipt['scripts']) else 'fail'
(OUT / 'geometry-execution.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
raise SystemExit(0 if receipt['status'] == 'pass' else 1)
