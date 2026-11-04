from pathlib import Path
import subprocess,json,sys
b=Path(__file__).resolve().parent
with (b/'host.log').open('wb') as log:
 r=subprocess.run(['wsl.exe','-d','Ubuntu','--','bash','--noprofile','--norc','-s'],input=(b/'run.sh').read_bytes(),stdout=log,stderr=subprocess.STDOUT)
(b/'host-exit.json').write_text(json.dumps({'exit_code':r.returncode,'candidate':'864bc036d6d7752475e52db4efd2b950cabfcc3d'}),encoding='utf-8')
print('Linux native host exit',r.returncode,flush=True);sys.exit(r.returncode)
