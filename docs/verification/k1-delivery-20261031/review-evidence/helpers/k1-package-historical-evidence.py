"""Losslessly wrap immutable evidence; never rewrite its reports or official ZIPs."""
from pathlib import Path
import argparse, hashlib, json, zipfile
root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('names',nargs='+')
args=parser.parse_args()
sources=root/'out/collab/k1-delivery-staging'
dest=root/'out/collab/k1-delivery-packaged'
dest.mkdir(exist_ok=True)
def digest_stream(stream):
    h=hashlib.sha256()
    for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()
def digest(path):
    with path.open('rb') as stream:return digest_stream(stream)
for name in args.names:
    source=(sources/name).resolve()
    assert source.parent==sources.resolve() and source.is_dir()
    output=dest/(name+'-original-tree.zip')
    receipt=dest/(name+'-packaging.json')
    assert not output.exists() and not receipt.exists()
    paths=sorted(p for p in source.rglob('*') if p.is_file())
    before={p.relative_to(source).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p)} for p in paths}
    assert not any(p.suffix.lower() in ('.exe','.dll','.pdb') for p in paths), 'No new independent binary distribution'
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in paths:
            z.write(p,p.relative_to(source).as_posix(),compress_type=zipfile.ZIP_STORED if p.suffix.lower() in ('.zip','.jpg','.png','.gz') else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(output) as z:
        assert sorted(z.namelist())==sorted(before)
        for info in z.infolist():
            with z.open(info) as stream: actual=digest_stream(stream)
            assert info.file_size==before[info.filename]['bytes'] and actual==before[info.filename]['sha256']
    assert before=={p.relative_to(source).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p)} for p in paths}
    data={'operation':'new lossless delivery wrapper, original archive unchanged',
          'source':str(source.relative_to(root)),'source_files':len(before),
          'source_bytes':sum(r['bytes'] for r in before.values()),'archive':output.name,
          'archive_bytes':output.stat().st_size,'archive_sha256':digest(output),
          'members':before,'all_members_verified':True,'originals_unchanged':True,
          'official_zip_bytes_preserved_as_members':True,
          'github_regular_git_file_limit_bytes':100*1024*1024,
          'hosting_policy_source':'https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github',
          'below_regular_git_limit':output.stat().st_size<100*1024*1024,
          'independent_review':'pending','new_test_or_simulation':False}
    receipt.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in data.items() if k!='members'},ensure_ascii=False),flush=True)
