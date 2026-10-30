"""Exclusive safe extraction of the official ZIPs already collected in this round."""
from pathlib import Path,PurePosixPath,PureWindowsPath
import json,hashlib,stat,zipfile
BASE=Path(__file__).resolve().parent
HEAD='7d718d038a00d89995ea773b4772764116b620c3'
ALLOWED={'m0-report-windows-latest','m0-report-ubuntu-latest','linux-evidence-11.3.2','linux-evidence-11.4.3'}
def main():
 results=[]
 for rid in (41054895374,41054895506):
  metadata=BASE/f'{rid}-artifacts.json'
  if not metadata.exists():metadata=BASE/f'{rid}-artifacts-partial.json'
  if not metadata.exists():continue
  for item in json.loads(metadata.read_text())['artifacts']:
   assert item['name'] in ALLOWED and item['workflow_run']['head_sha']==HEAD and item['workflow_run']['id']==rid
   archive=BASE/(item['name']+'.zip')
   if not archive.exists():continue
   actual='sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest();assert actual==item['digest']
   target=BASE/item['name'];seen=set();written=reused=0
   with zipfile.ZipFile(archive) as source:
    for entry in source.infolist():
     rel=PurePosixPath(entry.filename);assert not rel.is_absolute() and '..' not in rel.parts and not PureWindowsPath(entry.filename).drive and '\\' not in entry.filename and not stat.S_ISLNK(entry.external_attr>>16)
     path=target.joinpath(*rel.parts);key=path.resolve();assert key.is_relative_to(target.resolve()) and key not in seen;seen.add(key)
     if entry.is_dir():path.mkdir(parents=True,exist_ok=True);continue
     raw=source.read(entry);path.parent.mkdir(parents=True,exist_ok=True)
     if path.exists():assert path.is_file() and path.read_bytes()==raw;reused+=1
     else:
      with path.open('xb') as f:f.write(raw)
      written+=1
   results.append({'artifact':item['name'],'official_sha256':actual,'written':written,'reused_identical':reused})
 print(json.dumps(results))
if __name__=='__main__':main()
