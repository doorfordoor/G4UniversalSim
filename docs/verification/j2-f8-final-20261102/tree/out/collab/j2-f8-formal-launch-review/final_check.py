from pathlib import Path
from types import SimpleNamespace
import ast,copy,hashlib,json,os,subprocess
ROOT=Path.cwd();LAUNCH=ROOT/'out/collab/j2-f8-formal-launch.py';OUT=ROOT/'out/collab/j2-f8-formal-launch-review/final';OUT.mkdir(exist_ok=True)
raw=LAUNCH.read_bytes();digest=hashlib.sha256(raw).hexdigest();tree=ast.parse(raw.decode('utf-8'));compile(tree,str(LAUNCH),'exec')
functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['final_identity_errors','source_identities']]
assert len(functions)==2
child_calls=[]
env=os.environ.copy();count=int(env.get('GIT_CONFIG_COUNT','0'));env.update({f'GIT_CONFIG_KEY_{count}':'core.longpaths',f'GIT_CONFIG_VALUE_{count}':'true','GIT_CONFIG_COUNT':str(count+1),'PYTHONDONTWRITEBYTECODE':'1'})
def checked(args):
    assert args[:3]==['D:\\Geant4\\G4UniversalSim\\gui\\.venv\\Scripts\\python.exe','-B','-c'] or args[:3]==['D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe','-B','-c'],args
    assert "runpy.run_path('scripts/run_m0_tests.py')" in args[3]
    p=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
    child_calls.append({'command':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    assert p.returncode==0,(p.stdout,p.stderr)
    return p.stdout
ns={'Path':Path,'json':json,'checked':checked,'PYTHON':Path('D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe')}
exec(compile(ast.Module(body=functions,type_ignores=[]),'<extracted-launcher-functions>','exec'),ns)
start=ns['source_identities']();end=ns['source_identities']();assert start==end
assert all(len(v)==64 for v in start.values())
# Instantiate the actual expected_identity dictionary AST, avoiding the launcher top level.
assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected_identity' for t in n.targets))
exe=ROOT/'out/build-i2-formal113/Release/G4UniversalSim.exe';merge=exe.with_name('mergeHistograms.exe')
caps={'build_configuration':'Release','compiler_id':'MSVC','compiler_version':'19.51','geant4_version_number':1132,'multithreaded':True}
helpers={str(i):str(i)*64 for i in range(5)}
context={'Path':Path,'a':SimpleNamespace(head='candidate',profile='gui',exe_sha256='a'*64),'starting_sources':start,'exe':exe,'merge':merge,'caps':caps,'receipt':{'merge':{'sha256':'b'*64},'standalone_xerces_helper':{'sha256':'c'*64,'inputs':helpers}}}
expected=eval(compile(ast.Expression(assignment.value),'<actual-expected-identity>','eval'),context)
check=ns['final_identity_errors'];payload=copy.deepcopy(expected['report']);ending=copy.deepcopy(expected['ending']);assert check(payload,ending,expected)==[]
rows=[]
for section in ['report','ending']:
 for key in expected[section]:
  for variant in ['changed','missing']:
   p=copy.deepcopy(payload);e=copy.deepcopy(ending);dest=p if section=='report' else e
   if variant=='missing':del dest[key]
   else:dest[key]='DIFFERENT'
   errors=check(p,e,expected);assert section+'.'+key in errors,(section,key,variant,errors)
   rows.append({'section':section,'field':key,'variant':variant,'rejected':True,'errors':errors})
for key in caps:
 p=copy.deepcopy(payload);p['backend_build_identity'][key]='DIFFERENT';errors=check(p,ending,expected);assert 'report.backend_build_identity' in errors
 rows.append({'field':'backend_build_identity.'+key,'rejected':True})
for key in helpers:
 e=copy.deepcopy(ending);e['helper_inputs'][key]='DIFFERENT';assert 'ending.helper_inputs' in check(payload,e,expected)
 rows.append({'field':'helper_inputs.'+key,'rejected':True})
for key in start:
 e=copy.deepcopy(ending);e['sources'][key]='DIFFERENT';assert 'ending.sources' in check(payload,e,expected)
 rows.append({'field':'ending.sources.'+key,'rejected':True})
p=copy.deepcopy(payload);p['backend_executable']=str(exe.parent/'x'/ '..'/exe.name);assert check(p,ending,expected)==[]
# Data binding block only: verified receipt/SDK/published-receipt bytes, no discovery exe or payload rehash.
block=next(n for n in tree.body if isinstance(n,ast.If) and any(isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='reuse_path' for t in x.targets) for x in n.body))
reuse=json.loads((ROOT/'out/collab/j2-114-data-reuse/receipt.json').read_text(encoding='utf-8'))
data=ROOT/'out/i2-controlled/windows114-data/data';sdk=ROOT/'out/dependencies/geant4-11.4.3/geant4-11.4.3-win64'
def data_case(folders):
 n={'a':SimpleNamespace(series='114'),'ROOT':ROOT,'Path':Path,'json':json,'data':data,'sdk':sdk,'sha':lambda p:hashlib.sha256(p.read_bytes()).hexdigest(),'discovery':{'datasets':[{'folder':f} for f in folders]},'receipt':{}}
 exec(compile(ast.Module(body=[block],type_ignores=[]),'<actual-data-binding-block>','exec'),n)
 return n['receipt']
folders=[r['folder'] for r in reuse['datasets']];binding=data_case(folders)
for invalid in [folders[:-1],folders+folders[:1],['wrong-folder']+folders[1:]]:
 try:data_case(invalid)
 except AssertionError:pass
 else:assert False,'wrong dataset set accepted'
assert len(reuse['published_receipts'])==2
assert hashlib.sha256(LAUNCH.read_bytes()).hexdigest()==digest
result={'passed':True,'launcher_sha256':digest,'syntax':'PASS compile only; no launcher execution','matching_identity_accepted':True,'identity_mutations_rejected':len(rows),'variants':rows,'normalized_equivalent_path_accepted':True,'actual_fingerprint_child_runs':child_calls,'fingerprints_stable':start,'data_binding_block':'PASS actual receipt/SDK/2published SHA/exact12, 3 bad dataset variants rejected','no_launcher_build_profile_or_ui':True,'script_bytes_unchanged':True}
(OUT/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['variants','actual_fingerprint_child_runs']},indent=2))
