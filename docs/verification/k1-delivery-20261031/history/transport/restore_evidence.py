"""Reassemble a K1 evidence ZIP without extracting it or overwriting a file."""
from pathlib import Path
import argparse,hashlib,json
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('manifest',type=Path)
parser.add_argument('--output-directory',type=Path,required=True)
args=parser.parse_args()
manifest=args.manifest.resolve()
d=json.loads(manifest.read_bytes())
if d['schema'] != 'k1_evidence_transport_parts_v1':
    raise ValueError('Unsupported transport schema')
name=d['archive_name']
if Path(name).name != name or '/' in name or '\\' in name:
    raise ValueError('Invalid archive name')
args.output_directory.mkdir(parents=True,exist_ok=True)
output=args.output_directory/name
if output.exists():
    raise FileExistsError('Output already exists; choose a fresh directory')
parts=[]
for row in d['parts']:
    part_name=row['file']
    if Path(part_name).name != part_name or '/' in part_name or '\\' in part_name:
        raise ValueError('Invalid part name')
    part=manifest.parent/part_name
    h=hashlib.sha256()
    with part.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    if part.stat().st_size != row['bytes'] or h.hexdigest() != row['sha256']:
        raise ValueError('Part identity mismatch: ' + part_name)
    parts.append(part)
h=hashlib.sha256(); size=0
with output.open('xb') as stream:
    for part in parts:
        with part.open('rb') as source:
            for block in iter(lambda:source.read(1024*1024),b''):
                stream.write(block);h.update(block);size+=len(block)
if size != d['archive_bytes'] or h.hexdigest() != d['archive_sha256']:
    raise ValueError('Reassembled ZIP identity mismatch; output is unverified')
print(json.dumps({'archive':str(output.resolve()),'bytes':size,'sha256':h.hexdigest(),'extracted':False}))
