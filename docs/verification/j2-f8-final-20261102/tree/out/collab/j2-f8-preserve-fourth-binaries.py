"""Preserve five exact formal binaries locally; no execution, no SDK copy."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'out/verification/j2-f8-2ec5b14'
HEAD = '2ec5b14fc823ad837dce3ea6f5d7c5ae3f66a3c8'
DEST = BASE / 'identity/frozen-binaries'
def sha(data):
    return hashlib.sha256(data).hexdigest()

assert not DEST.exists(), 'Refuse overwriting preserved evidence'
prepared = []
bindings = []
for version in ('1132', '1143'):
    lp = BASE / ('windows113-backend' if version == '1132' else 'windows114-backend') / 'launch.json'
    raw = lp.read_bytes()
    launch = json.loads(raw)
    assert launch['head'] == HEAD and launch['status'] == 'passed'
    assert launch['runner_exit_code'] == launch['gate_exit_code'] == 0
    assert launch['identity_errors'] == []
    bindings.append({'path': str(lp), 'sha256': sha(raw)})
    names = ('executable', 'merge', 'standalone_xerces_helper') if version == '1132' else ('executable', 'merge')
    for kind in names:
        identity = launch[kind]
        src = Path(identity['path'])
        data = src.read_bytes()
        assert sha(data) == identity['sha256'], (version, kind)
        target = DEST / version / src.name
        prepared.append((src, target, data, version, kind, identity['sha256']))
DEST.mkdir()
files = []
for src, target, data, version, kind, expected in prepared:
    target.parent.mkdir(exist_ok=True)
    with target.open('xb') as output:
        output.write(data)
    assert sha(target.read_bytes()) == sha(src.read_bytes()) == expected
    files.append({'version': version, 'kind': kind, 'source': str(src), 'copy': str(target), 'bytes': len(data), 'sha256': expected})
receipt = {'head': HEAD, 'scope': 'Exact app/merge/helper local byte preservation; no runtime or SDK certification; public archive metadata only', 'launch_bindings': bindings, 'files': files}
with (DEST / 'receipt.json').open('x', encoding='utf-8', newline='\n') as output:
    output.write(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'files': len(files), 'bytes': sum(x['bytes'] for x in files), 'receipt': str(DEST / 'receipt.json')}))
