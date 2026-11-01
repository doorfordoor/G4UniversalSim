from pathlib import Path
import sys,subprocess,importlib.util,json
ROOT=Path.cwd();OUT=Path(__file__).resolve().parent;sys.path[:0]=[str(ROOT/'gui')]
name='g4usim_gui.core.experiment_bundle';spec=importlib.util.spec_from_file_location(name,OUT/'experiment_bundle.py');b=importlib.util.module_from_spec(spec);sys.modules[name]=b;spec.loader.exec_module(b)
case=OUT/'late-resource-policy-final';case.mkdir(exist_ok=False);source=case/'ordinary';source.mkdir();main=source/'main.ini';main.write_text('[run]\nseed=17\n');backup=case/'ordinary-moved';observed=[]
def read_then_link(path):
 data=b._read(path)
 assert source.resolve().is_relative_to(case.resolve()) and backup.absolute().is_relative_to(case.resolve())
 source.rename(backup)
 result=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(source.absolute()),str(backup.resolve())],capture_output=True)
 assert result.returncode==0,result.stdout+result.stderr
 assert main.samefile(backup/'main.ini')
 observed.append('resource became a real junction after read, before policy identity comparison')
 return data
closure=b._Closure(case.resolve(),{str(main.resolve()):{'distribution':'restricted','allow_redistribution':True}},reader=read_then_link)
try:closure.add(main,'main')
except ValueError as error:message=str(error)
else:assert False,'late junction passed the policy comparison'
assert 'linked path' in message or 'reparse point' in message,message
assert observed
(OUT/'late-resource-policy-final.json').write_text(json.dumps(dict(scope=observed,error=message),indent=2)+'\n')
print('late real NTFS junction refused before policy identity resolution PASS')
