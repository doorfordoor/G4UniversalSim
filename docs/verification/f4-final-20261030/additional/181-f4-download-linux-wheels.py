"""Fetch official PyPI Linux wheels into task-owned wheelhouse, verify SHA256."""
import concurrent.futures,hashlib,json,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'out/collab/f4-qt-dependency-validation'
WHEELS=OUT/'wheelhouse';WHEELS.mkdir(exist_ok=True)
def fetch(spec):
    package,version=spec
    with urllib.request.urlopen(f'https://pypi.org/pypi/{package}/{version}/json',timeout=30) as stream:
        metadata=json.load(stream)
    item=next(f for f in metadata['urls'] if 'manylinux_2_34_x86_64' in f['filename'])
    target=WHEELS/item['filename'];partial=target.with_suffix('.part')
    begin=time.monotonic();hasher=hashlib.sha256()
    with urllib.request.urlopen(item['url'],timeout=60) as stream,partial.open('wb') as writer:
        while chunk:=stream.read(1024*1024):hasher.update(chunk);writer.write(chunk)
    assert hasher.hexdigest()==item['digests']['sha256']
    partial.replace(target)
    return {'package':package,'version':version,'filename':item['filename'],'url':item['url'],
            'sha256':hasher.hexdigest(),'bytes':target.stat().st_size,'seconds':time.monotonic()-begin}
specs=[(p,v) for v in ('6.11.1','6.11.3') for p in ('PySide6','PySide6_Addons','PySide6_Essentials','shiboken6')]
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for future in concurrent.futures.as_completed([pool.submit(fetch,spec) for spec in specs]):
        result=future.result();results.append(result)
        print(json.dumps(result),flush=True)
        (OUT/'wheelhouse-downloads.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
