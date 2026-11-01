from pathlib import Path
import ast,difflib,hashlib,json
root=Path.cwd();out=root/'out/collab/f8-project-dock150/v3';source=root/'gui/smoke_tests/smoke_f8_accessibility.py'
old=source.read_text(encoding='utf-8-sig');function=(out/'smoke-retained-function.py').read_text(encoding='utf-8-sig')
new=old.replace('\ndef main():','\n'+function+'def main():').replace("    print('F8 keyboard/start/environment/wizard/layout offscreen checks passed')", "    test_retained_dock_focus(app, args.output)\n    print('F8 keyboard/start/environment/wizard/layout offscreen checks passed')")
old_ast=ast.parse(old);new_ast=ast.parse(new);newdefs={n.name:n for n in new_ast.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
for node in old_ast.body:
 if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name!='main':assert ast.dump(node)==ast.dump(newdefs[node.name]),node.name
before=next(n for n in old_ast.body if isinstance(n,ast.FunctionDef) and n.name=='main');after=newdefs['main']
assert len(after.body)==len(before.body)+1
assert all(ast.dump(x)==ast.dump(y) for x,y in zip(before.body[:-1],after.body[:-2]))
assert ast.dump(before.body[-1])==ast.dump(after.body[-1])
(out/'smoke_f8_accessibility.proposed.py').write_bytes(new.encode('utf-8'))
(out/'smoke_f8_accessibility.patch').write_bytes(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/gui/smoke_tests/smoke_f8_accessibility.py',tofile='b/gui/smoke_tests/smoke_f8_accessibility.py')).encode('utf-8'))
print('all pre-existing function ASTs unchanged; main only adds new test call')
