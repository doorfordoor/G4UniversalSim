import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
HEAD='2ec5b14fc823ad837dce3ea6f5d7c5ae3f66a3c8'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def prepare(old,new,expected,changes):
    assert sha(old)==expected and not new.exists()
    raw=old.read_bytes()
    patched=raw
    for a,b in changes.items():
        assert patched.count(a.encode())==1,(str(old),a)
        patched=patched.replace(a.encode(),b.encode())
    new.write_bytes(patched)
    compile(patched,str(new),'exec')
    class Restore(ast.NodeTransformer):
        def visit_Constant(self,node):
            reverse={v:k for k,v in changes.items()}
            if isinstance(node.value,str) and node.value in reverse:
                node.value=reverse[node.value]
            return node
    restored=Restore().visit(ast.parse(patched))
    assert ast.dump(restored,include_attributes=False)==ast.dump(ast.parse(raw),include_attributes=False)
    return {'old':str(old.relative_to(ROOT)),'old_sha256':sha(old),'new':str(new.relative_to(ROOT)),'new_sha256':sha(new),'literal_changes':changes,'all_other_ast_unchanged':True,'compiled_only':True,'executed':False}
native=prepare(OUT/'launch-v3.py',OUT/'launch-v4.py','4376022fb76dece56e16ec3a61026b74dc367b35e0f247c8efaceecd1f565ce0',{
    '18c5858fd6e80a5cb6096beacebfef69c479ad49':HEAD,
    'out/verification/j2-f8-18c5858':'out/verification/j2-f8-2ec5b14',
    '01e0fb795f93772ccfa818d625fee145d8da1ad3ad80894372a9a855f0af108a':'fe5d23d309106d9fca7ad179f6c0cb39fa8b98c6ef35286a0b21866b90d89f89'})
audit=prepare(ROOT/'out/collab/j2-f8-final-local-audit-18c5858.py',ROOT/'out/collab/j2-f8-final-local-audit-2ec5b14.py','ac0528c6b93adf74c4576598513cfb11ab19238580a608368660bac62c4c33ce',{
    '18c5858fd6e80a5cb6096beacebfef69c479ad49':HEAD,
    'out/verification/j2-f8-18c5858':'out/verification/j2-f8-2ec5b14'})
receipt={'head':HEAD,'host_sha256':sha(OUT/'host-v2.py'),'native':native,'six_report_audit':audit,'pending_independent_review':True,'native_scope':'One representative125/100 supplemental run after GUI slot release; I1/I2 open/cancel, import existing offline bundle, template Finish and reentry Back/Esc. Old three native observations remain separate.','no_native_or_matrix_execution':True}
(OUT/'launch-v4-preparation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
