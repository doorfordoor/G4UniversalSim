"""Read-only check of adopted design evidence; results only under out."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
PROPOSAL=ROOT/'out/collab/j2-ci-review/design-link-proposal'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
proposal=json.loads((PROPOSAL/'proposal.json').read_bytes())
applied=json.loads((ROOT/'out/collab/j2-f8-repair-applied/receipt.json').read_bytes())
assert proposal['candidate_files']==applied['design_files']
rows=[]
for row in proposal['candidate_files']:
    path=ROOT/row['path'];candidate=PROPOSAL/'candidate-tree'/row['path']
    assert path.read_bytes()==candidate.read_bytes(),row['path']
    assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],row['path']
    rows.append(row)
raw_paths=[]
for row in proposal['raw_files']:
    assert (ROOT/row['source']).read_bytes()==(ROOT/row['target']).read_bytes(),row['target']
    raw_paths.append(row['target'])
attrs_path=ROOT/'docs/collab/reviews/20261101-j2-f8-design-evidence/.gitattributes'
assert attrs_path.read_bytes()==b'raw/** -text\n'
attr_result=subprocess.check_output(['git','check-attr','-z','text','--',*raw_paths],cwd=ROOT)
parts=attr_result.split(b'\0');attrs=[]
for i in range(0,len(parts)-1,3):
    path,key,value=(x.decode() for x in parts[i:i+3]);assert key=='text' and value=='unset',(path,key,value)
    attrs.append({'path':path,'text':value})
assert len(attrs)==4
log=OUT/'doc-links.log';assert not log.exists()
result=subprocess.run([sys.executable,'-B','scripts/check_doc_links.py'],cwd=ROOT,capture_output=True)
log.write_bytes(result.stdout+result.stderr)
for row in rows:assert sha(ROOT/row['path'])==row['sha256']
receipt={'status':'pass' if result.returncode==0 else 'fail','candidate_file_sha256_all_match':True,'files':rows,'raw_files_match_original_source_bytes':True,'gitattributes_raw_bytes':'raw/** -text\n','effective_raw_text_attributes':attrs,'doc_links_exit_code':result.returncode,'doc_links_log_sha256':sha(log),'method':'Local bytes/proposal/apply receipt comparison plus effective git attributes and current complete doc_links; no tracked edits, staging, network or CI actions.'}
assert not (OUT/'receipt.json').exists()
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(result.stdout.decode(errors='replace'));print(result.stderr.decode(errors='replace'))
print(json.dumps({'status':receipt['status'],'sha_files':len(rows),'raw_original_byte_matches':len(raw_paths),'effective_text_unset':len(attrs)}))
raise SystemExit(result.returncode)
