"""Independent synthetic logic probes only; never supplies or maps a real future HEAD."""
from pathlib import Path
import importlib.util,copy,json
ROOT=Path.cwd();OUT=Path(__file__).resolve().parent;PREP=ROOT/'out/collab/j2-f8-native-fourth-mapping-prep'
spec=importlib.util.spec_from_file_location('reviewed_mapping',PREP/'check_mapping.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def forbidden_git(*args,**kwargs):raise AssertionError('Pure logic review must never call Git')
m.git=forbidden_git
future='a'*40;anchor={'scope_sha256':'b'*64};smokes=sorted(m.SMOKES)
def base():
 old={p:b'old' for p in smokes};new={p:b'new' for p in smokes}
 before={p:{'mode':'100644','kind':'blob','oid':'1'*40} for p in smokes};after={p:{'mode':'100644','kind':'blob','oid':'2'*40} for p in smokes}
 plan={'schema':'g4usim_native_mapping_allowlist_v1','status':'frozen','frozen_by':'main','base_head':m.BASE,'candidate_head':future,'scope_sha256':'b'*64,'allowed_changes':[{'path':p,'kind':'smoke','before_sha256':m.digest(old[p]),'after_sha256':m.digest(new[p])} for p in smokes]}
 return plan,before,after,old,new

def reject(call):
 rejected=False
 try:call()
 except m.Rejected:rejected=True
 assert rejected,'Expected controlled rejection'
# Concrete exact paths, with a documentation add and delete, are allowed only by frozen SHA.
p,b,a,old,new=base()
for path,prior,next_ in [('docs/old.md',b'old doc',None),('gui/docs/new.md',None,b'new doc')]:
 if prior is not None:b[path]={'mode':'100644','kind':'blob','oid':'3'*40};old[path]=prior
 if next_ is not None:a[path]={'mode':'100644','kind':'blob','oid':'4'*40};new[path]=next_
 p['allowed_changes'].append({'path':path,'kind':'docs','before_sha256':m.digest(prior) if prior is not None else None,'after_sha256':m.digest(next_) if next_ is not None else None})
m.check_diff(b,a,m.allowlist(p,future,anchor),old,new)
# Documentation is root anchored, not a substring or basename permission.
for path in ['docs-extra/a.md','gui/docs-extra/a.md','schema/docs/help.md','packaging/docs/help.md','.github/docs/help.md','gui/README.md','gui/g4usim_gui/docs/a.md','gui/g4usim_gui/resources/native.json']:
 p,*_=base();p['allowed_changes'].append({'path':path,'kind':'docs','before_sha256':None,'after_sha256':'c'*64});reject(lambda:m.allowlist(p,future,anchor))
# No glob expansion: a literal docs/*.md entry cannot approve another path.
p,b,a,old,new=base();p['allowed_changes'].append({'path':'docs/*.md','kind':'docs','before_sha256':None,'after_sha256':m.digest(b'doc')});a['docs/actual.md']={'mode':'100644','kind':'blob','oid':'5'*40};new['docs/actual.md']=b'doc';reject(lambda:m.check_diff(b,a,m.allowlist(p,future,anchor),old,new))
# Frozen smoke additions/deletions, wrong roles and metadata extras are rejected.
for field in ('before_sha256','after_sha256'):
 p,*_=base();p['allowed_changes'][0][field]=None;reject(lambda:m.allowlist(p,future,anchor))
p,*_=base();p['allowed_changes'][0]['kind']='docs';reject(lambda:m.allowlist(p,future,anchor))
p,*_=base();p['allowed_changes'][0]['recursive']=True;reject(lambda:m.allowlist(p,future,anchor))
# Modes and object kinds are checked for both old and new versions, including documents.
for side in ('old','new'):
 for mode,kind in [('100755','blob'),('120000','blob'),('160000','commit'),('040000','tree')]:
  p,b,a,old,new=base();target=b if side=='old' else a;target[smokes[0]]={'mode':mode,'kind':kind,'oid':'6'*40};reject(lambda:m.check_diff(b,a,m.allowlist(p,future,anchor),old,new))
# A legal allowlist cannot absorb an unlisted runtime deletion.
p,b,a,old,new=base();b['config/runtime.ini']={'mode':'100644','kind':'blob','oid':'7'*40};old['config/runtime.ini']=b'runtime';reject(lambda:m.check_diff(b,a,m.allowlist(p,future,anchor),old,new))
# Omitted fixed smoke or changed docs without matching new bytes do not pass.
p,*_=base();p['allowed_changes'].pop();reject(lambda:m.allowlist(p,future,anchor))
p,b,a,old,new=base();new[smokes[0]]=b'unfrozen';reject(lambda:m.check_diff(b,a,m.allowlist(p,future,anchor),old,new))
# Real preparation template remains pending, never a candidate approval.
template=m.read_json(PREP/'allowlist.template.json');reject(lambda:m.allowlist(template,future,anchor))
for value in ('HEAD','A'*40,'a'*39,'a'*41):reject(lambda:m.full_head(value))
for text in ('{"x":1,"x":2}','{"allowed_changes":[],"allowed_changes":{}}'):reject(lambda:json.loads(text,object_pairs_hook=m.unique_object))
(OUT/'logic-results.json').write_bytes((json.dumps({'status':'synthetic_logic_only_passed','actual_future_head_used':False,'actual_mapping_run':False,'git_calls':0,'qt_or_runtime_imports':0,'groups':['explicit_docs_add_delete','root_anchored_docs','no_glob_expansion','fixed_smokes_and_fields','old_new_object_modes','unlisted_runtime_deletion','missing_or_tampered','pending_template_and_identity_syntax']},indent=2)+'\n').encode())
print('Independent synthetic allowlist/mode/identity logic PASS; no Git or actual mapping')
