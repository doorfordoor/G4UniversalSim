from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parent/'k1-delivery-packaged'
for name in ('failed-c644bb1','failed-11c92d3'):
    archive=root/(name+'-original-tree.zip')
    destination=root/'transport'/name
    destination.mkdir(parents=True,exist_ok=False)
    parts=[]; total=hashlib.sha256()
    with archive.open('rb') as original:
        for number,block in enumerate(iter(lambda:original.read(32*1024*1024),b''),1):
            filename=f'archive.zip.part-{number:03d}'
            with (destination/filename).open('xb') as out:out.write(block)
            parts.append({'file':filename,'bytes':len(block),'sha256':hashlib.sha256(block).hexdigest()})
            total.update(block)
    check=hashlib.sha256()
    for part in parts:
        data=(destination/part['file']).read_bytes()
        assert len(data)==part['bytes'] and hashlib.sha256(data).hexdigest()==part['sha256']
        check.update(data)
    assert check.hexdigest()==total.hexdigest()
    original_receipt=json.loads((root/(name+'-packaging.json')).read_bytes())
    assert total.hexdigest()==original_receipt['archive_sha256']
    shutil.copy2(root/(name+'-packaging.json'),destination/'original-packaging.json')
    manifest={'schema':'k1_evidence_transport_parts_v1','archive_name':archive.name,
              'archive_bytes':archive.stat().st_size,'archive_sha256':total.hexdigest(),
              'parts':parts,'source_archive':str(archive),'originals_modified':False,
              'operation':'parts of a new delivery wrapper only; original reports and official ZIP bytes unchanged',
              'whole_stream_verified':True,'independent_review':'pending'}
    (destination/'transport.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='parts'}|{'part_count':len(parts)}),flush=True)
