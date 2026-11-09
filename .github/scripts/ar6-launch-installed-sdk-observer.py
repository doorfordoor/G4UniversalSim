import subprocess,sys
from pathlib import Path
repo, root, cmake, compiler=map(Path,sys.argv[1:])
environments=root/'environments'
environments.mkdir()
evidence=root/'sdk-evidence'
log=root/'installed-sdk-flow.log'
command=[sys.executable,'-B',str(repo/'packaging/verify_installation_flow.py'),
         '--catalog',str(repo/'out/ar6sdkdiag-sdk.catalog.json'),'--profile','sdk','--version','1.1.0',
         '--prefix',str(environments/'sdk'),'--allowed-root',str(environments),'--evidence-root',str(evidence),
         '--cmake',str(cmake),'--compiler',str(compiler),'--generator','Ninja']
with log.open('xb') as stream:
    p=subprocess.Popen(command,cwd=repo,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    code=p.wait()
print(log.read_text(encoding='utf-8',errors='replace'))
raise SystemExit(code)
