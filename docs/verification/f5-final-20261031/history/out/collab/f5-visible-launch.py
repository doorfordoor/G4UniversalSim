"""Launch the F5 QA host and retain the real child-process exit receipt."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--artifact-dir', type=Path, required=True)
parser.add_argument('--executable', type=Path, required=True)
parser.add_argument('--precheck', action='store_true')
parser.add_argument('--theme', choices=('light', 'dark'), default='light')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
artifacts = args.artifact_dir.resolve()
if not artifacts.is_relative_to((root / 'out').resolve()):
    raise SystemExit('Artifact directory must be beneath checkout/out.')
artifacts.mkdir(parents=True, exist_ok=True)
if any((artifacts / name).exists() for name in ('identity.json', 'launcher.json', 'host.log')):
    raise SystemExit('A fresh artifact directory is required.')
command = [sys.executable, '-B', str(Path(__file__).with_name('f5-visible-host.py')),
           '--artifact-dir', str(artifacts), '--executable', str(args.executable.resolve()), '--theme', args.theme]
if args.precheck:
    command.append('--precheck')
started = datetime.now(timezone.utc).isoformat()
with (artifacts / 'host.log').open('wb') as output:
    process = subprocess.Popen(command, cwd=root, stdout=output, stderr=subprocess.STDOUT)
    print(json.dumps({'host_pid': process.pid, 'artifacts': str(artifacts), 'mode': 'precheck' if args.precheck else 'native'}, ensure_ascii=False), flush=True)
    result = process.wait()
receipt = {'command': command, 'host_pid': process.pid, 'actual_process_exit': result,
           'started_utc': started, 'completed_utc': datetime.now(timezone.utc).isoformat(),
           'host_log_sha256': hashlib.sha256((artifacts / 'host.log').read_bytes()).hexdigest(),
           'launcher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'visual_acceptance': 'not_claimed'}
(artifacts / 'launcher.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False), flush=True)
raise SystemExit(result)
