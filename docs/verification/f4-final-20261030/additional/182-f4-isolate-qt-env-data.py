"""Remove inherited site packages; install explicit numerical dependencies locally."""
from pathlib import Path
import sys,subprocess,json,importlib.metadata as metadata
version=sys.argv[1]
assert version in ('6.11.1','6.11.3')
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'out/collab/f4-qt-dependency-validation'
env=Path('/home/u123/venvs')/('g4-f4-qt-'+version+'-20261030')
cfg=env/'pyvenv.cfg'
text=cfg.read_text();assert 'include-system-site-packages = true' in text
cfg.write_text(text.replace('include-system-site-packages = true','include-system-site-packages = false'))
requirements=[f'{name}=={metadata.version(name)}' for name in ('numpy','matplotlib','uproot')]
command=[str(env/'bin/python'),'-m','pip','install','--report',str(OUT/f'numerical-pip-{version}.json'),*requirements]
with (OUT/f'numerical-install-{version}.log').open('wb') as log:
    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
print(json.dumps({'version':version,'requirements':requirements,'exit_code':result.returncode}),flush=True)
raise SystemExit(result.returncode)
