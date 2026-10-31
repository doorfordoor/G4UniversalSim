"""Direct mirror smoke + unmodified assert probe, under a strict CP1252 pipe."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=('baseline', 'candidate'))
args = parser.parse_args()
branch = 'baseline' if args.mode == 'baseline' else 'files'
target = HERE / branch / 'gui/smoke_tests/smoke_k1_workflow.py'
probe = ROOT / 'tools/test_assert_probe.py'
temporary = HERE / 'tmp'
temporary.mkdir(exist_ok=True)
env = os.environ.copy()
env.update(PYTHONIOENCODING='cp1252', QT_QPA_PLATFORM='offscreen',
           PYTHONDONTWRITEBYTECODE='1', TEMP=str(temporary), TMP=str(temporary))
env['PYTHONPATH'] = os.pathsep.join([str(ROOT / p) for p in
    ['gui/smoke_tests', 'gui', 'scripts', 'tools']] + ([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
command = [sys.executable, '-B', str(probe), str(target)]
log = HERE / (args.mode + '-cp1252.log')
start = time.monotonic()
with log.open('xb') as output:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
raw = log.read_bytes()
observations = [json.loads(line.split(b'=', 1)[1].decode('ascii')) for line in raw.splitlines()
                if line.startswith(b'external_completed_preview=')]
receipt = dict(mode=args.mode, command=command, cwd=str(ROOT), exit_code=result.returncode,
    seconds=time.monotonic() - start, log=str(log), log_sha256=hashlib.sha256(raw).hexdigest(),
    assertions_executed=[int(value) for value in re.findall(rb'G4USIM_ASSERTS=(\d+)', raw)],
    diagnostic_rows=len(observations), languages=[row['language'] for row in observations],
    encoding='PYTHONIOENCODING=cp1252 (strict stdout default)',
    original_probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),
    mirrored_smoke_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
    harness='direct original assert probe/runpy execution; no import hooks or AST extraction',
    product_imports='unchanged actual sixth checkout via PYTHONPATH; no product candidate overlay',
    no_real_backend_simulation=True)
with (HERE / (args.mode + '-cp1252-receipt.json')).open('x', encoding='utf-8', newline='\n') as output:
    json.dump(receipt, output, ensure_ascii=True, indent=2); output.write('\n')
print(json.dumps(receipt, ensure_ascii=True), flush=True)
if result.returncode:
    print(raw.decode('cp1252', errors='backslashreplace')[-1800:].encode('ascii', errors='backslashreplace').decode('ascii'))
