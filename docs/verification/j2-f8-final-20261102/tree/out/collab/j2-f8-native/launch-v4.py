"""Launch one isolated production window for manual native acceptance."""
import argparse, hashlib, json, os, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser()
p.add_argument('--scale',choices=('100','125','150'),required=True)
p.add_argument('--language',default='zh_CN')
a=p.parse_args()
head='2ec5b14fc823ad837dce3ea6f5d7c5ae3f66a3c8'
folder=ROOT/'out/verification/j2-f8-2ec5b14'/('native'+a.scale)
assert not folder.exists(), 'Never overwrite a native evidence run'
env=os.environ.copy()
removed=[]
for key in list(env):
    if (key.startswith('G4') and key.endswith('DATA')) or key in ('GEANT4_DATA_DIR','QT_SCALE_FACTOR','QT_SCREEN_SCALE_FACTORS','QT_AUTO_SCREEN_SCALE_FACTOR','QT_DEVICE_PIXEL_RATIO','QT_QPA_PLATFORM'):
        removed.append(key); env.pop(key)
env.update(G4USIM_EXE=str(ROOT/'out/build-i2-formal113/Release/G4UniversalSim.exe'),
    GEANT4_DATA_DIR='D:/ProgramFiles/Geant4/share/Geant4/data',
    QT_QPA_PLATFORM='windows',PYTHONDONTWRITEBYTECODE='1')
if a.scale!='125': env['QT_SCALE_FACTOR']={'100':'0.8','150':'1.2'}[a.scale]
env['PATH']=os.pathsep.join(['D:/ProgramFiles/Geant4/bin','D:/ProgramFiles/Qt/5.15.2/msvc2019_64/bin',env['PATH']])
count=int(env.get('GIT_CONFIG_COUNT','0'))
env.update({f'GIT_CONFIG_KEY_{count}':'core.longpaths',f'GIT_CONFIG_VALUE_{count}':'true','GIT_CONFIG_COUNT':str(count+1)})
def run(command):
    return subprocess.check_output(command,cwd=ROOT,env=env,text=True,encoding='utf-8',stderr=subprocess.PIPE).strip()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert run(['git','rev-parse','HEAD'])==head and not run(['git','status','--porcelain=v1'])
assert sha(env['G4USIM_EXE'])=='fe5d23d309106d9fca7ad179f6c0cb39fa8b98c6ef35286a0b21866b90d89f89'
host=ROOT/'out/collab/j2-f8-native/host-v2.py'
assert sha(host)=='b9c216045a478a5bffd503371405cf767b290ff87e811da3623dcbc89dad334a'
python=Path('D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe')
pythonw=python.with_name('pythonw.exe')
assert pythonw.is_file()
identity=json.loads(run([str(python),'-B','-c',
    'import sys,json,PySide6,shiboken6,pyvista,pyvistaqt,vtk,qtpy; from PySide6.QtCore import qVersion; '
    'print(json.dumps({"executable":sys.executable,"python":sys.version,"prefix":sys.prefix,"base_prefix":sys.base_prefix,"qt":qVersion(),'
    '"modules":{m.__name__:{"version":getattr(m,"__version__",None),"file":m.__file__} for m in (PySide6,shiboken6,pyvista,pyvistaqt,vtk,qtpy)}}))']))
caps=json.loads(run([env['G4USIM_EXE'],'--capabilities']))
assert caps['build_git_commit']==head and caps['build_git_source_state']=='clean'
assert caps['source_fingerprint']=='9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a'
folder.mkdir(parents=True)
command=[str(pythonw),'-B',str(host),'--output',str(folder),'--language',a.language,
    '--width','760' if a.scale=='150' else '1200','--height','640' if a.scale=='150' else '800',
    '--x','945' if a.scale=='150' else '300','--y','20']
receipt={'head':head,'host_sha256':sha(host),'capabilities':caps,'exe_sha256':sha(env['G4USIM_EXE']),
    'runtime':identity,'removed_keys':removed,'scale_env':env.get('QT_SCALE_FACTOR'),
    'qpa':'windows','command':command,'status':'starting','started':time.time()}
def save(): (folder/'launch.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
save()
with (folder/'host.stdout.log').open('wb') as out, (folder/'host.stderr.log').open('wb') as err:
    child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=out,stderr=err)
    receipt.update(pid=child.pid,status='running'); save()
    print(json.dumps({'pid':child.pid,'folder':str(folder)}),flush=True)
    code=child.wait()
receipt.update(process_exit_code=code,status='exited',ended=time.time(),
    ending_head=run(['git','rev-parse','HEAD']),ending_git_status=run(['git','status','--porcelain=v1']),
    ending_exe_sha256=sha(env['G4USIM_EXE']))
save()
print(json.dumps({'exit_code':code,'folder':str(folder)}),flush=True)
raise SystemExit(code)
