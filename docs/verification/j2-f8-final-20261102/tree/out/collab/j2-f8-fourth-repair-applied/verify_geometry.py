import ctypes,hashlib,json,os,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'geometry'
OUT.mkdir(exist_ok=False)
script=ROOT/'gui/smoke_tests/smoke_j2_geometry.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=sha(script)
assert before=='b3fefeac58f044c99021d1caf7812fd66c8fe41bd14fb94ebcf8facf0c1cb6bd'
folder=OUT/'real short path temporary'
folder.mkdir()
buf=ctypes.create_unicode_buffer(32768)
n=ctypes.windll.kernel32.GetShortPathNameW(str(folder),buf,len(buf))
assert 0<n<len(buf) and '~' in buf.value and Path(buf.value).samefile(folder)
env=dict(os.environ)
for k in ('QT_SCALE_FACTOR','QT_SCREEN_SCALE_FACTORS','QT_PLUGIN_PATH','PYTHONPATH','PYTHONHOME'):
    env.pop(k,None)
env.update(QT_QPA_PLATFORM='offscreen',PYTHONDONTWRITEBYTECODE='1',TEMP=buf.value,TMP=buf.value)
command=[sys.executable,'-B',str(ROOT/'tools/test_assert_probe.py'),str(script)]
proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
output,_=proc.communicate()
(OUT/'geometry.log').write_bytes(output)
markers=re.findall(rb'G4USIM_ASSERTS=(\d+)',output)
count=int(markers[-1]) if markers else None
after=sha(script)
result={'status':'passed' if proc.returncode==0 and count==214 and before==after else 'failed','command':command,'pid':proc.pid,'exit_code':proc.returncode,'assertions_v3':count,'script_sha256_before':before,'script_sha256_after':after,'temp_long':str(folder),'temp_short':buf.value,'log_sha256':sha(OUT/'geometry.log'),'source':'actual tracked script through unchanged standard probe; no loader or product monkeypatch','scope':'offscreen only; no backend/native/profile'}
(OUT/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
raise SystemExit(0 if result['status']=='passed' else 1)
