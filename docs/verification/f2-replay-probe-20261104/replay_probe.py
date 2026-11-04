import hashlib,json,os,subprocess
from pathlib import Path
B=Path(__file__).resolve().parent
D=B/'replay-three-round';assert not D.exists(),'Inspect existing replay before reuse'
O=D/'output';O.mkdir(parents=True)
exe=Path('D:/Geant4/G4UniversalSim/build_vs2026/Release/G4UniversalSim.exe')
assert hashlib.sha256(exe.read_bytes()).hexdigest()=='18d58fab815b91e96c6c4b2c94704518d42885f163b54803072164a8a4f9c837'
data=(B/'three-round/stdin.txt').read_bytes();(D/'stdin.txt').write_bytes(data)
env=os.environ.copy();env['G4USIM_GEANT4_DATA']='D:/ProgramFiles/Geant4/share/Geant4/data'
argv=[str(exe),'--ui','--ui-session','csh','--config','main.ini','--output',str(O)]
p=subprocess.Popen(argv,cwd=B/'config',env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try: stdout,stderr=p.communicate(data,timeout=120)
except subprocess.TimeoutExpired:p.kill();stdout,stderr=p.communicate();raise
(D/'stdout.log').write_bytes(stdout);(D/'stderr.log').write_bytes(stderr)
old=B/'three-round/output';before={x.name:x for x in old.glob('*.csv')};after={x.name:x for x in O.glob('*.csv')}
rows=[]
for name in sorted(set(before)|set(after)):
 a=before[name].read_bytes() if name in before else None;b=after[name].read_bytes() if name in after else None
 rows.append({'file':name,'equal_raw_bytes':a==b,'before_sha256':hashlib.sha256(a).hexdigest() if a is not None else None,'after_sha256':hashlib.sha256(b).hexdigest() if b is not None else None})
r={'schema':'g4usim_f2_fixed_initial_state_replay_probe_v1','pid':p.pid,'argv':argv,'exit_code':p.returncode,'initial_seed':1904,'threads':1,'data_root':env['G4USIM_GEANT4_DATA'],'same_exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'comparison':'all raw CSV bytes, exact filenames; JSON identity/time/path metadata excluded, no tolerance or row filter','files':rows,'equal_file_sets':set(before)==set(after),'all_equal':all(x['equal_raw_bytes'] for x in rows)}
(B/'replay-report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print('exit',p.returncode,'csv',len(rows),'all_equal',r['all_equal'])
assert p.returncode==0 and r['equal_file_sets'] and r['all_equal']