from pathlib import Path
import sys,importlib.util,subprocess,copy,json
ROOT=Path.cwd();OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'scripts')]
name='g4usim_gui.core.experiment_bundle';spec=importlib.util.spec_from_file_location(name,OUT/'experiment_bundle.py');b=importlib.util.module_from_spec(spec);sys.modules[name]=b;spec.loader.exec_module(b)
from test_k1_bundle import fixture
case=OUT/'real-junction-probe-final';case.mkdir(exist_ok=False);target=case/'ordinary';snapshot=fixture(target.resolve());main=target.resolve()/'main.ini';linked=case/'linked'
r=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(linked.resolve()),str(target.resolve())],capture_output=True);assert r.returncode==0,r.stdout+r.stderr
assert (linked/'main.ini').samefile(main)
observed=[]
for label,selected,policy in [('policy-link',snapshot,{str(linked/'main.ini'):{'distribution':'restricted','allow_redistribution':True}}),('resource-link',copy.deepcopy(snapshot),{str(main):{'distribution':'restricted','allow_redistribution':True}})]:
 if label=='resource-link':selected.project.configPath=str(linked/'main.ini')
 try:b.collect_bundle_resources(selected,resource_policy=policy)
 except ValueError as error:message=str(error)
 else:assert False,'linked path accepted'
 assert 'linked path' in message or 'reparse point' in message,message
 observed.append(dict(case=label,error=message))
(OUT/'link-facts.json').write_text(json.dumps(dict(real_windows_directory_junction=True,same_file=True,results=observed),indent=2)+'\n')
print('real NTFS resource and policy-key junction refusals PASS')
