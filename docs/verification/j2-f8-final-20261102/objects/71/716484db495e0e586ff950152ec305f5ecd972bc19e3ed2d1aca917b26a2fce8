"""Run the remaining two complete draft component entries against v2 in memory."""
import contextlib,hashlib,importlib,json,subprocess,sys,tempfile,time,traceback
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'out/collab/j2-static-fixture-patch-final';PRODUCT=ROOT/'out/collab/j2-f8-repair-draft-v2'
work=OUT/'runtime-work';work.mkdir(exist_ok=True);tempfile.tempdir=str(work)
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'gui'))
manifest=json.loads((PRODUCT/'manifest.json').read_text());sources=json.loads((OUT/'draft-files.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for row in manifest['files']:
 assert sha(ROOT/row['path'])==row['original_raw_sha256'];assert sha(PRODUCT/'files'/row['path'])==row['candidate_sha256']
for name in ('core.i18n','editors.material_editor_model','editors.source_physics_scoring_model','validators.config_validator'):
 module=importlib.import_module('g4usim_gui.'+name);draft=PRODUCT/'files'/Path(module.__file__).relative_to(ROOT)
 exec(compile(draft.read_text(encoding='utf-8'),str(draft),'exec'),module.__dict__)
receipt={'product_patch_sha256':sha(PRODUCT/'product.patch'),'product_manifest_sha256':sha(PRODUCT/'manifest.json'),'full_scripts':[],'method':'Complete draft main entries; K1 --component, migration main. Product v2 module source substituted in memory; test __file__ anchors repository reads. All evidence and temporary writes under out. No backend, profile or native launched.'}
for name in ['test_k1_bundle.py','test_config_migration.py']:
 script='scripts/'+name;draft=OUT/'proposed'/script;log=OUT/(Path(name).stem+'-combination-v2-r1.log');assert not log.exists()
 ns={'__name__':'out_only_complete_components','__file__':str(ROOT/script)}
 argv=[str(ROOT/script)]
 if name=='test_k1_bundle.py':argv+=['--component','--evidence-root',str(OUT/'runtime-evidence'/'k1-v2-r1')]
 (OUT/'runtime-evidence').mkdir(exist_ok=True)
 before=time.monotonic();sys.argv=argv
 entry={'script':script,'draft_sha256':sha(draft),'argv':argv,'log':str(log),'started_unix':time.time()}
 print('START',name,flush=True)
 with log.open('w',encoding='utf-8',newline='\n') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
  try:
   exec(compile(draft.read_text(encoding='utf-8'),str(draft),'exec'),ns)
   value=ns['main']();entry['status']='pass';entry['entry_return']=value
  except BaseException as error:
   entry['status']='fail';entry['traceback']=traceback.format_exc();print(entry['traceback'])
 entry['duration_seconds']=round(time.monotonic()-before,3);entry['log_sha256']=sha(log);receipt['full_scripts'].append(entry)
 print('DONE',name,entry['status'],entry['duration_seconds'],flush=True)
 (OUT/'geometry-components-v2-r1.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
for row in manifest['files']:assert sha(ROOT/row['path'])==row['original_raw_sha256']
for row in sources:assert sha(ROOT/row['path'])==row['base_sha256_raw']
receipt['tracked_sources_unchanged']=True;receipt['status']='pass' if all(x['status']=='pass' for x in receipt['full_scripts']) else 'fail'
receipt['head_after']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();receipt['git_status_after']=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],text=True)
(OUT/'geometry-components-v2-r1.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
print('COMPLETE',receipt['status'],flush=True)
sys.exit(0 if receipt['status']=='pass' else 1)
