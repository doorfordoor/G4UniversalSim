"""Own isolated WSL virtualenvs; never mutates the existing g4ci/Windows env."""
import json,sys,subprocess,urllib.request,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'out/collab/f4-qt-dependency-validation'
OUT.mkdir(exist_ok=True)
version=sys.argv[1]
assert version in ('6.11.1','6.11.3','6.10.3')
env=Path('/home/u123/venvs')/('g4-f4-qt-'+version+'-20261030')
assert not env.exists(), 'Task venv already exists; inspect it before reusing'
metadata_url=f'https://pypi.org/pypi/PySide6/{version}/json'
metadata=json.load(urllib.request.urlopen(metadata_url,timeout=30))
info={'url':metadata_url,'requires_python':metadata['info']['requires_python'],
      'requires_dist':metadata['info']['requires_dist'],
      'wheels':[{'filename':f['filename'],'sha256':f['digests']['sha256'],'url':f['url'],
                 'upload_time':f['upload_time_iso_8601']} for f in metadata['urls']
                if 'manylinux' in f['filename'] and 'x86_64' in f['filename']]}
(OUT/f'pypi-{version}.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
# Shared read-only numeric/plot packages keep those variables unchanged; the four
# Qt wheels are installed locally and their actual resolved import paths recorded.
subprocess.run([sys.executable,'-m','venv','--system-site-packages',str(env)],check=True)
command=[str(env/'bin/python'),'-m','pip','install','--report',str(OUT/f'pip-{version}.json'),
         f'PySide6=={version}']
with (OUT/f'install-{version}.log').open('wb') as log:
    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
print(json.dumps({'version':version,'environment':str(env),'pip_exit_code':result.returncode}),flush=True)
raise SystemExit(result.returncode)
