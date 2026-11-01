from pathlib import Path
import ast,difflib
root=Path.cwd();out=root/'out/collab/f8-layout-item-compat';old=(root/'gui/smoke_tests/smoke_f8_accessibility.py').read_text(encoding='utf-8-sig');extra=(out/'smoke-function.py').read_text(encoding='utf-8-sig')
new=old.replace('\ndef main():','\n'+extra+'def main():').replace("    print('F8 keyboard/start/environment/wizard/layout offscreen checks passed')", "    test_layout_item_compatibility(app)\n    print('F8 keyboard/start/environment/wizard/layout offscreen checks passed')")
a=ast.parse(old);b=ast.parse(new);definitions={n.name:n for n in b.body if isinstance(n,ast.FunctionDef)}
for n in a.body:
 if isinstance(n,ast.FunctionDef) and n.name!='main':assert ast.dump(n)==ast.dump(definitions[n.name]),n.name
out.joinpath('smoke_f8_accessibility.proposed.py').write_bytes(new.encode('utf-8'))
out.joinpath('smoke_f8_accessibility.patch').write_bytes(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/gui/smoke_tests/smoke_f8_accessibility.py',tofile='b/gui/smoke_tests/smoke_f8_accessibility.py')).encode('utf-8'))
# Scroll/union/deferred helpers are all unchanged in the product candidate.
oldcore=ast.parse((root/'gui/g4usim_gui/core/accessibility.py').read_text(encoding='utf-8-sig'));newcore=ast.parse((out/'accessibility.proposed.py').read_text(encoding='utf-8'))
for name in ('_reading_anchor','_reveal_axis','ensure_focus_visible','focus_first','AccessibilityController'):
 left=next(n for n in oldcore.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name);right=next(n for n in newcore.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name);assert ast.dump(left)==ast.dump(right),name
print('old416 tests/union/deferred helpers unchanged')
