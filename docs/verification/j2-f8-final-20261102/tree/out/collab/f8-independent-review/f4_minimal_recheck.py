from pathlib import Path
import os,sys,subprocess,json,hashlib,re
ROOT=Path.cwd();OUT=ROOT/'out/collab/f8-independent-review/f4-viewport-final';freeze=json.loads((ROOT/'out/collab/f8-f4-viewport/freeze.json').read_text(encoding='utf-8'))
def hashes():return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in freeze['files']}
assert hashes()==freeze['files'];source=ROOT/'gui/smoke_tests/smoke_f4_layout.py';assert hashlib.sha256(source.read_bytes()).hexdigest()==freeze['original_f4_layout_test_sha256']
rows=[]
bootstrap="import sys,runpy,tempfile; from pathlib import Path; from PySide6.QtCore import QSettings; p=Path(sys.argv[1]); tempfile.tempdir=str(p); QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(p/'settings')); probe=sys.argv[2]; sys.argv=[probe,sys.argv[3]]; runpy.run_path(probe,run_name='__main__')"
for label,scale in [('default',None),('125','1.25')]:
 work=OUT/label;work.mkdir();env=os.environ.copy()
 for k in ['QT_SCALE_FACTOR','QT_SCREEN_SCALE_FACTORS','QT_AUTO_SCREEN_SCALE_FACTOR','QT_DEVICE_PIXEL_RATIO']:env.pop(k,None)
 env.update(QT_QPA_PLATFORM='offscreen',PYTHONDONTWRITEBYTECODE='1')
 if scale:env['QT_SCALE_FACTOR']=scale
 before=hashes();log=OUT/(label+'.log')
 with log.open('wb') as stream:p=subprocess.run([sys.executable,'-B','-c',bootstrap,str(work),str(ROOT/'tools/test_assert_probe.py'),str(source)],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
 text=log.read_text(encoding='utf-8',errors='replace');markers=re.findall(r'G4USIM_ASSERTS=(\d+)',text)
 row={'case':'original-f4-layout-'+label,'exit_code':p.returncode,'assertions_executed':int(markers[-1]) if markers else None,'selected_sources_unchanged':before==hashes(),'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()};rows.append(row);print(json.dumps(row),flush=True)
write={'scope':'independent minimal review; original F4 test unmodified; no native UI','source_sha256':freeze['files'],'original_test_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_matches_freeze_after':hashes()==freeze['files'],'cases':rows};(OUT/'results.json').write_text(json.dumps(write,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');assert all(r['exit_code']==0 and r['assertions_executed']==265 and r['selected_sources_unchanged'] for r in rows)
