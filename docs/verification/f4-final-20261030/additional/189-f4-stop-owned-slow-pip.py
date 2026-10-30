"""Stop only the two task-owned online pip downloads before using verified wheels."""
from pathlib import Path
import os,signal,json
prefixes=[f'/home/u123/venvs/g4-f4-qt-{version}-20261030/bin/python' for version in ('6.11.1','6.11.3')]
matches=[]
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:args=proc.joinpath('cmdline').read_bytes().decode().split('\0')
    except (OSError,UnicodeError):continue
    if len(args)>4 and args[0] in prefixes and args[1:4]==['-m','pip','install']:
        matches.append({'pid':int(proc.name),'command':args})
for process in matches:os.kill(process['pid'],signal.SIGTERM)
print(json.dumps(matches),flush=True)
