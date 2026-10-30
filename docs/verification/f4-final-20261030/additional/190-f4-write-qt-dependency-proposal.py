from pathlib import Path
import difflib
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'out/collab/f4-qt-dependency-validation'
changes={}
path='gui/requirements.txt'
old=(ROOT/path).read_text(encoding='utf-8')
new=old.replace('PySide6\n', '# CPython 3.11: Qt 6.12.0 loses None refs on ordinary void-return calls.\n'
    '# Keep the verified 6.11 patch line; widen only after binding-lifetime and\n'
    '# Windows/Linux GUI + integration acceptance (including natural exits).\n'
    'PySide6>=6.11.1,<6.12\n',1)
assert old!=new
changes[path]=(old,new)
path='scripts/run_m0_tests.py'
old=(ROOT/path).read_text(encoding='utf-8')
anchor='    Case("gui_qt_combo_data", "gui/smoke_tests/smoke_qt_combo_data.py", "gui", ("qt",)),\n'
assert anchor in old
new=old.replace(anchor,anchor+'    Case("gui_qt_binding_lifetime", "gui/smoke_tests/smoke_qt_binding_lifetime.py", "gui", ("qt",)),\n',1)
changes[path]=(old,new)
path='gui/smoke_tests/smoke_qt_binding_lifetime.py'
new=(ROOT/'out/collab/smoke_qt_binding_lifetime_candidate.py').read_text(encoding='utf-8')
new=new.replace('Proposed GUI regression:', 'GUI regression:')
changes[path]=('',new)
parts=[]
for path,(before,after) in changes.items():
    parts.extend(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
                 fromfile='a/'+path if before else '/dev/null',tofile='b/'+path))
(OUT/'dependency-proposal.patch').write_text(''.join(parts),encoding='utf-8',newline='\n')
print('Wrote out-only patch for',list(changes))
