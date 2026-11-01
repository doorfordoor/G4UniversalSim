from pathlib import Path
import tempfile,sys,json,shutil,hashlib
from unittest.mock import patch
sys.path.insert(0,str(Path.cwd()/'packaging'));import ci_delivery as ci
out=Path('out/collab/i2-ci-review');result={}
with tempfile.TemporaryDirectory(prefix='ci-final-small-review-') as temp:
 root=Path(temp)/'origin';root.mkdir()
 files=(*ci.REQUIRED_PRODUCT_PATHS,'gui/g4usim_gui/output/extra.py','packaging/freeze_identity.py','packaging/ci_fetch_geant4_data.py','gui/.venv/ignored.py','test/output/ignored.txt')
 for name in files:
  p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture '+name,encoding='utf-8')
 with patch.object(ci,'ROOT',root):snap=ci.snapshot_sources(Path(temp)/'snapshot')
 assert all(name in snap['files'] for name in files[:7])
 assert 'gui/.venv/ignored.py' not in snap['files'] and 'test/output/ignored.txt' not in snap['files']
 result['snapshot']={'product_output_preserved':True,'extra_gui_module_preserved':True,'new_packaging_tools_preserved':True,'only_expected_generated_paths_omitted':True}
 (root/'gui/g4usim_gui/output/provenance.py').unlink()
 with patch.object(ci,'ROOT',root):
  try:ci.snapshot_sources(Path(temp)/'missing-product')
  except ValueError as e:assert 'Required product' in str(e);result['snapshot']['missing_product_rejected']=True
  else:assert False,'missing product was accepted'
 work=Path(temp)/'work';source=work/'source'
 sources={source/'out/package-build/freeze.log':b'freeze detail',source/'out/package-build/source-identity.json':b'{"stable":true}',source/'out/package/gui/g4usim-freeze.json':b'seal',source/'out/package-python-build/binary-sources.json':b'audit',work/'environments/sdk-consumer-build/configure.log':b'consumer configure',work/'environments/sdk-consumer-build/build.log':b'consumer build',work/'environments/sdk-application-build/build.log':b'application build',work/'environments/sdk-application-build/sdk-probe-receipt.json':b'probe receipt',work/'environments/sdk-application-build/CMakeFiles/3.28/CMakeCXXCompiler.cmake':b'compiler facts'}
 for p,data in sources.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 records=ci.archive_validation_evidence(work,source)
 assert len(records)==len(sources) and all(r['source_stable_during_copy'] for r in records)
 assert all(hashlib.sha256((work/r['path']).read_bytes()).hexdigest()==r['sha256'] for r in records)
 assert len(ci.archive_validation_evidence(work,source))==len(records)
 first=next(r for r in records if Path(r['source']).parent.name=='sdk-application-build' and Path(r['source']).name=='build.log')
 original=(work/first['path']).read_bytes();Path(first['source']).write_bytes(b'later application failure detail')
 second=ci.archive_validation_evidence(work,source)
 assert len(second)==len(records)+1 and (work/first['path']).read_bytes()==original
 target=source/'out';assert target.resolve().is_relative_to(work.resolve());shutil.rmtree(target)
 assert all((work/r['path']).is_file() for r in second)
 result['archive']={'all_selected_freeze_and_sdk_files_copied':True,'hashes_verified':True,'unchanged_sources_deduplicated':True,'changed_logs_versioned':True,'evidence_survives_owned_output_cleanup':True,'records':len(second)}
(out/'ci-fixes-small-review-evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
