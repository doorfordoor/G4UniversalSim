"""Download an official artifact; ephemeral URL only on stdin, never logged."""
from pathlib import Path,PurePosixPath,PureWindowsPath
import hashlib,json,stat,sys,urllib.request,zipfile
BASE=Path(__file__).resolve().parent
if sys.platform=='win32' and sys.stdin.isatty():
    import ctypes
    kernel=ctypes.windll.kernel32
    handle=kernel.GetStdHandle(-10);mode=ctypes.c_ulong()
    assert kernel.GetConsoleMode(handle,ctypes.byref(mode))
    assert kernel.SetConsoleMode(handle,mode.value & ~4)  # never echo the signed URL
print('Artifact downloader ready; input echo disabled.',flush=True)
data=json.loads(sys.stdin.readline())
name=data['name']
assert name in {'m0-report-ubuntu-latest','m0-report-windows-latest','linux-evidence-11.3.2','linux-evidence-11.4.3'}
assert data['url'].startswith('https://')
try:
    with urllib.request.urlopen(data['url'],timeout=120) as response:
        raw=response.read(512*1024*1024+1)
except Exception as exc:
    print('Artifact download failed: '+type(exc).__name__,file=sys.stderr);sys.exit(1)
assert len(raw)<=512*1024*1024
assert len(raw)==data['size_in_bytes']
digest='sha256:'+hashlib.sha256(raw).hexdigest()
assert digest==data['digest'],(name,digest,data['digest'])
def save(path,payload):
    if path.exists():assert path.read_bytes()==payload,'Existing evidence differs: '+path.name
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(payload)
archive=BASE/(name+'.zip');save(archive,raw)
destination=BASE/name;seen=set();members=0
with zipfile.ZipFile(archive) as source:
    assert sum(m.file_size for m in source.infolist())<=1024*1024*1024
    for member in source.infolist():
        rel=PurePosixPath(member.filename)
        assert not rel.is_absolute() and '..' not in rel.parts and not PureWindowsPath(member.filename).drive
        assert '\\' not in member.filename and ':' not in member.filename
        assert all(part not in ('','.','..') and not part.endswith((' ','.')) for part in rel.parts)
        assert not stat.S_ISLNK(member.external_attr>>16)
        path=destination.joinpath(*rel.parts).resolve();key=str(path).casefold()
        assert path.is_relative_to(destination.resolve()) and key not in seen
        seen.add(key)
        if not member.is_dir():save(path,source.read(member));members+=1
print(json.dumps({'name':name,'official_sha_verified':digest,'bytes':len(raw),'file_members':members,
                  'reports':len(list(destination.rglob('report.json')))}),flush=True)
