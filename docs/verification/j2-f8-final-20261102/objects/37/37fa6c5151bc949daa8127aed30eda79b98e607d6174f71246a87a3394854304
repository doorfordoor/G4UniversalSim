from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,subprocess,hashlib,re
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
PYTHON=Path('D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected={'gui/g4usim_gui/core/accessibility.py':'c9d87e23c88704fedc2c17a8a954aba9acf365c607ea47fe86b6c56854be2be7','gui/g4usim_gui/widgets/run_history_page.py':'cc98442e975cec3f1b33d556a8dabdd7381ec22368e94bd6124178edacb5a463','gui/smoke_tests/smoke_f8_accessibility.py':'943c92a0cdd0650511b7c8ce45378ebcbddc06b7f55b90835317eb44d3a59e95'}
applied=json.loads((OUT.parent/'receipt.json').read_text(encoding='utf-8'))
paths=sorted({row['target'] for patch in applied['preflight']['patches'] for row in patch['files']}|set(expected)|{'tools/test_assert_probe.py','gui/g4usim_gui/window/shell.py','gui/g4usim_gui/window/workspace_layout.py','gui/g4usim_gui/core/i18n.py'})
before={p:sha(ROOT/p) for p in paths};assert all(before[p]==v for p,v in expected.items())
basehead=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
receipt={'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),'base_head':basehead,'scope':'actual patched tree uncommitted, original v3 probe, no candidate source loader/monkeypatch','expected_candidate_sha256':expected,'source_sha256_before':before,'runs':[]}
def save():(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
save()
for scale in ['1.25','1.5']:
    artifacts=OUT/('scale'+scale)
    assert not artifacts.exists();artifacts.mkdir()
    env=os.environ.copy()
    for key in ['QT_SCREEN_SCALE_FACTORS','QT_AUTO_SCREEN_SCALE_FACTOR','QT_DEVICE_PIXEL_RATIO','QT_FONT_DPI','G4USIM_ENABLE_OFFSCREEN_PYVISTA','QT_QPA_PLATFORM_PLUGIN_PATH']:
        env.pop(key,None)
    env.update(QT_QPA_PLATFORM='offscreen',QT_SCALE_FACTOR=scale,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'gui'),QT_PLUGIN_PATH=str(PYTHON.parents[1]/'Lib/site-packages/PySide6/plugins'))
    command=[str(PYTHON),'-u','-B',str(ROOT/'tools/test_assert_probe.py'),str(ROOT/'gui/smoke_tests/smoke_f8_accessibility.py'),'--output',str(artifacts)]
    row={'scale':scale,'command':command,'qt_platform':'offscreen','output':str(artifacts),'started_utc':datetime.now(timezone.utc).isoformat()}
    receipt['runs'].append(row);save();print('START '+scale,flush=True)
    log=OUT/('scale'+scale+'.log')
    with log.open('wb') as stream:
        job=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        row['pid']=job.pid;save()
        try:code=job.wait(timeout=300)
        except subprocess.TimeoutExpired:
            job.kill();code=job.wait();row['timeout']=True
    raw=log.read_bytes();text=raw.decode('utf-8',errors='replace')
    markers=re.findall(r'^G4USIM_ASSERTS=(\d+)\s*$',text,re.M)
    after={p:sha(ROOT/p) for p in paths}
    row.update(exit_code=code,process_ended=job.poll() is not None,finished_utc=datetime.now(timezone.utc).isoformat(),assertions_markers=markers,log_sha256_raw_bytes=sha(log),runtime_warning_preserved='RuntimeWarning' in text,source_sha256_after=after,source_bytes_unchanged=before==after)
    save();print(json.dumps({k:row[k] for k in ['scale','pid','exit_code','process_ended','assertions_markers','source_bytes_unchanged','runtime_warning_preserved']}),flush=True)
    assert code==0 and markers==['595'] and before==after,row
receipt.update(status='passed',finished_utc=datetime.now(timezone.utc).isoformat(),source_sha256_after={p:sha(ROOT/p) for p in paths},head_after=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
assert receipt['source_sha256_after']==before
save();print('ACTUAL_PATCHED_F8_FINAL passed',flush=True)
