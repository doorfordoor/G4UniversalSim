from pathlib import Path
import ctypes,json,sys,copy
ROOT=Path.cwd();OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'scripts')]
from test_f5_transactions_backend import initial_state
from g4usim_gui.core.experiment_bundle import collect_bundle_resources,_no_links
root=OUT/'long-folder-with-alias-input';root.mkdir(exist_ok=True)
get_short=ctypes.windll.kernel32.GetShortPathNameW;get_short.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint];get_short.restype=ctypes.c_uint
buffer=ctypes.create_unicode_buffer(32768);n=get_short(str(root.resolve()),buffer,len(buffer));assert 0<n<len(buffer)
short=Path(buffer.value);facts=dict(long=str(root.resolve()),short=str(short),has_actual_alias='~' in str(short),same_file=short.samefile(root));assert facts['same_file']
snapshot,_=initial_state(short,Path(sys.executable));snapshot.project.runInputMode='external';main=short/'main.ini';macro=short/'top.mac';main.write_text('[run]\nseed=17\n');macro.write_text('# no dynamic inputs\n');snapshot.project.configPath=str(main);snapshot.project.macroPath=str(macro)
policy_key=str(main.resolve());facts.update(policy_key=policy_key,closure_lookup_key=str(_no_links(main)),same_actual_file=Path(policy_key).samefile(_no_links(main)))
for label,policy in [('no-policy',None),('restricted',{policy_key:{'distribution':'restricted'}}),('explicit-allow',{policy_key:{'distribution':'restricted','allow_redistribution':True}})]:
 try:
  resources=collect_bundle_resources(snapshot,resource_policy=policy)['resources'];facts[label]=dict(status='accepted',main_distribution=next(x['distribution'] for x in resources if x['role']=='main'))
 except ValueError as e:facts[label]=dict(status='rejected',message=str(e))
(OUT/'reproduction.json').write_text(json.dumps(facts,indent=2)+'\n',encoding='utf-8');print(json.dumps(facts,indent=2))
assert facts['has_actual_alias'] and facts['same_actual_file']
assert facts['restricted']['message'].startswith('Unused resource policy entries:')
assert facts['explicit-allow']['message'].startswith('Unused resource policy entries:')
