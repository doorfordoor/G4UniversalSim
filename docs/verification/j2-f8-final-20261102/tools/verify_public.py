"""Self-contained raw-byte/closure/link verification; no acceptance CLI or product run."""
import hashlib,importlib.util,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def load_module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def verify(root):
 root=Path(root).resolve();m=json.loads((root/'manifest.json').read_text(encoding='utf-8'));ex=json.loads((root/'metadata-only.json').read_text(encoding='utf-8'));blocked={x['sha256'] for x in ex['entries'] if x.get('sha256')};objects={};paths={}
 for e in m['entries']:
  assert e['sha256'] not in blocked,('excluded SHA referenced',e['original_logical_path'])
  q=(root/e['public_path']).resolve();obj=(root/e['object']).resolve();assert q.is_relative_to(root) and obj.is_relative_to(root);assert q.is_file() and q.stat().st_size==e['bytes'];assert obj.is_file();paths[q]=e;objects[e['sha256']]=obj
 actual_objects={p.relative_to(root).as_posix() for p in (root/'objects').rglob('*') if p.is_file()};assert actual_objects=={p.relative_to(root).as_posix() for p in objects.values()},'orphan or excluded object in projection'
 for h,p in objects.items():
  assert digest(p)==h
  with p.open('rb') as f:assert f.read(4) not in [b'PK\x03\x04',b'PK\x05\x06',b'PK\x07\x08'],'opaque ZIP payload not permitted'
 actual_tree={p.resolve() for p in (root/'tree').rglob('*') if p.is_file()};assert actual_tree==set(paths),'unreferenced tree payload'
 for q,e in paths.items():assert os.path.samefile(q,objects[e['sha256']]) or digest(q)==e['sha256']
 checker=load_module('_public_frozen_evidence_checker',root/'tree/scripts/check_report_evidence.py');reports=[];log_checks=0
 for q,e in paths.items():
  if Path(e['original_logical_path']).name!='report.json':continue
  x=json.loads(q.read_text(encoding='utf-8-sig'))
  if x.get('schema')!=checker.REPORT_SCHEMA or not isinstance(x.get('results'),list):continue
  logrows=[]
  for row in x['results']:
   p=checker.resolve_log(row,q);assert p is not None and p.resolve().is_relative_to(root),('forbidden original path fallback',e['original_logical_path'],row.get('name'))
   # Object hashes checked once; compare exact local binding rather than rehash live/original CI logs.
   p=p.resolve();assert p in paths and paths[p]['sha256']==row['log_sha256'];log_checks+=1;logrows.append({'case':row['name'],'path':p.relative_to(root).as_posix(),'sha256':row['log_sha256'],'original_status':row['status']})
  reports.append({'path':q.relative_to(root).as_posix(),'sha256':e['sha256'],'original_head':x.get('git_head'),'original_git_dirty':x.get('git_dirty'),'cases':len(x['results']),'logs':logrows})
 md=list(root.rglob('*.md'));assert [p.relative_to(root).as_posix() for p in md]==['README.md'],'only generated public Markdown may remain active'
 links=load_module('_unchanged_doc_link_rules',root/'tools/check_doc_links_source.py');checked=0;broken=[]
 for p in md:
  for n,line in enumerate(links.strip_fenced_blocks(p.read_text(encoding='utf-8')).splitlines(),1):
   for mat in links.LINK_RE.finditer(line):
    target=mat.group(1)
    if target.startswith(links.SKIP_PREFIXES):continue
    target=target.split('#',1)[0]
    if not target:continue
    relative=links.repo_relative(target,str(root));candidate=relative if relative is not None else target;q=(root/candidate) if relative is not None else p.parent/candidate
    if not q.exists():candidate=links.LINE_SUFFIX_RE.sub('',candidate);q=(root/candidate) if relative is not None else p.parent/candidate
    checked+=1
    if not q.exists():broken.append({'file':p.relative_to(root).as_posix(),'line':n,'target':target})
 assert checked>0 and not broken,broken
 return {'schema':'j2_f8_public_projection_raw_verification_v1','status':'raw_bytes_and_self_contained_closure_verified','payload_files':len(paths),'objects':len(objects),'excluded_SHA_references':0,'orphan_objects_or_tree_files':0,'formal_or_historical_report_count':len(reports),'report_log_local_bindings_checked':log_checks,'report_closures':reports,'old_absolute_log_fallback':False,'original_report_log_bytes_or_status_rewritten':False,'CI_checker_CLI_or_product_run':False,'readable_MD_files':len(md),'readable_MD_links_checked':checked,'raw_original_MD_renamed_not_rewritten':True,'small_opaque_ZIP_payloads':0,'stage_complete':False}
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('root',type=Path,nargs='?',default=Path(__file__).resolve().parent.parent);a=p.parse_args();result=verify(a.root);print(json.dumps({k:v for k,v in result.items() if k!='report_closures'},ensure_ascii=False))
