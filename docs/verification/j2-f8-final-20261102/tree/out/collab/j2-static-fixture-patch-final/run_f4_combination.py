"""Execute draft tests against main's out-only product modules; never patch disk sources."""
import hashlib,importlib,inspect,json,sys,tempfile,traceback
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'out/collab/j2-static-fixture-patch-final';PRODUCT=ROOT/'out/collab/j2-f8-repair-draft-v2'
work=OUT/'runtime-work';work.mkdir(exist_ok=True);tempfile.tempdir=str(work)
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'gui'))
manifest=json.loads((PRODUCT/'manifest.json').read_text());sources=json.loads((OUT/'draft-files.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for row in manifest['files']:
 assert sha(ROOT/row['path'])==row['original_raw_sha256'],row['path']
 assert sha(PRODUCT/'files'/row['path'])==row['candidate_sha256'],row['path']
for name in ('core.i18n','editors.material_editor_model','editors.source_physics_scoring_model','validators.config_validator'):
 module=importlib.import_module('g4usim_gui.'+name);path=Path(module.__file__);draft=PRODUCT/'files'/path.relative_to(ROOT)
 exec(compile(draft.read_text(encoding='utf-8'),str(draft),'exec'),module.__dict__)
receipt={'method':'In-memory product-module substitution plus draft test execution; __file__ anchored to original repository for test ROOT. All temporary fixture writes constrained to out. No tracked source edits or formal profile rerun.','product_manifest_sha256':sha(PRODUCT/'manifest.json'),'product_patch_sha256':sha(PRODUCT/'product.patch'),'full_scripts':[],'post_failure_independent_groups':[]}
for name in ['test_f4_producers.py','test_f4_document_diagnostics.py']:
 script='scripts/'+name;draft=OUT/'proposed'/script
 assert sha(draft)==next(x for x in sources if x['path']==script)['proposed_sha256']
 ns={'__name__':'out_only_f4_combination','__file__':str(ROOT/script)}
 exec(compile(draft.read_text(encoding='utf-8'),str(draft),'exec'),ns)
 log=OUT/(Path(name).stem+'-combination-v2.log')
 assert not log.exists(),'Preserve first validation log; use a distinct revision for a future changed draft'
 result={'script':script,'draft_sha256':sha(draft),'log':str(log)}
 try:
  ns['main']();result['status']='pass';log.write_text('Draft main completed without exception. Not a formal profile result.\n',encoding='utf-8')
 except Exception:
  result['status']='fail';result['traceback']=traceback.format_exc();log.write_text(result['traceback'],encoding='utf-8');print(result['traceback'])
 result['log_sha256']=sha(log);receipt['full_scripts'].append(result)
 if result['status']=='fail':
  # No weakened main result: independently execute every remaining test function
  # to expose failures hidden by the first one, retaining the original failure.
  for fn_name in ['check_density_machine_categories','check_legacy_code_json_unchanged','check_nist_alias_source','check_geometry_sources','check_geometry_targets','check_cut_region_identities','check_geometry_read_evidence']:
   if fn_name not in ns:continue
   entry={'script':script,'group':fn_name}
   try:
    with tempfile.TemporaryDirectory(prefix=fn_name+'-') as tmp:
     args=[Path(tmp)] if inspect.signature(ns[fn_name]).parameters else []
     ns[fn_name](*args)
    entry['status']='pass'
   except Exception:
    entry['status']='fail';entry['traceback']=traceback.format_exc();print(entry['traceback'])
   receipt['post_failure_independent_groups'].append(entry)
for row in manifest['files']:assert sha(ROOT/row['path'])==row['original_raw_sha256']
for row in sources:assert sha(ROOT/row['path'])==row['base_sha256_raw']
receipt['tracked_sources_unchanged']=True;receipt['status']='pass' if all(x['status']=='pass' for x in receipt['full_scripts']) else 'fail'
(OUT/'f4-combination-v2.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({'status':receipt['status'],'full_scripts':[(x['script'],x['status']) for x in receipt['full_scripts']],'independent_groups':[(x['group'],x['status']) for x in receipt['post_failure_independent_groups']]},ensure_ascii=False))
sys.exit(0 if receipt['status']=='pass' else 1)
