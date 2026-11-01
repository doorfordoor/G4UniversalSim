from pathlib import Path
import ast,difflib
root=Path.cwd();out=root/'out/collab/f8-history-label';source=root/'gui/smoke_tests/smoke_f8_accessibility.py';old=source.read_text(encoding='utf-8-sig');extra=(out/'smoke-function.py').read_text(encoding='utf-8-sig')
new=old.replace('\ndef main():','\n'+extra+'def main():').replace("    print('F8 keyboard/start/environment/wizard/layout offscreen checks passed')", "    test_history_directory_accessibility(app, args.output)\n    print('F8 keyboard/start/environment/wizard/layout offscreen checks passed')")
a=ast.parse(old);b=ast.parse(new);definitions={n.name:n for n in b.body if isinstance(n,ast.FunctionDef)}
for n in a.body:
 if isinstance(n,ast.FunctionDef) and n.name!='main':assert ast.dump(n)==ast.dump(definitions[n.name]),n.name
oldmain=next(n for n in a.body if isinstance(n,ast.FunctionDef) and n.name=='main');newmain=definitions['main'];assert len(newmain.body)==len(oldmain.body)+1
assert all(ast.dump(x)==ast.dump(y) for x,y in zip(oldmain.body[:-1],newmain.body[:-2]))
assert ast.dump(oldmain.body[-1])==ast.dump(newmain.body[-1])
(out/'smoke_f8_accessibility.proposed.py').write_bytes(new.encode('utf-8'))
(out/'smoke_f8_accessibility.patch').write_bytes(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/gui/smoke_tests/smoke_f8_accessibility.py',tofile='b/gui/smoke_tests/smoke_f8_accessibility.py')).encode('utf-8'))
print('old416 functions+union AST unchanged; main only appends History test')
