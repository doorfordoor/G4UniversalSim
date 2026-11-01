from pathlib import Path
import ast,hashlib,json,os,sys,re,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
OWNER=ROOT/'out/collab/f8-project-dock150'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=ROOT/'gui/smoke_tests/smoke_f8_accessibility.py';new=OWNER/'smoke_f8_accessibility.proposed.py'
a=ast.parse(old.read_text(encoding='utf-8'));b=ast.parse(new.read_text(encoding='utf-8'))
functions=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
fa,fb=functions(a),functions(b)
for name in fa.keys()-{'main'}:assert ast.dump(fa[name],include_attributes=False)==ast.dump(fb[name],include_attributes=False),name
main=fb['main'];oldmain=fa['main'];extra=main.body[-2];assert ast.unparse(extra)=='test_retained_dock_focus(app, args.output)'
del main.body[-2];assert ast.dump(oldmain,include_attributes=False)==ast.dump(main,include_attributes=False)
receipt=json.loads((OWNER/'permanent-smoke-receipt.json').read_text())
for name,item in receipt['files'].items():assert sha(OWNER/name)==item['sha256']
for item in receipt['tests']:
    data=(OWNER/item['path']).read_text(encoding='utf-8');assert sha(OWNER/item['path'])==item['sha256']
    if item.get('assertions_v3'):assert re.findall(r'^G4USIM_ASSERTS=(\d+)',data,re.M)==['406']
result=subprocess.run(['git','apply','--check',str(OWNER/'accessibility.lf.patch'),str(OWNER/'smoke_f8_accessibility.patch')],cwd=ROOT,capture_output=True,text=True);assert result.returncode==0,result.stderr
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_SCALE_FACTOR='1.5',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase
import g4usim_gui.core.accessibility as access
candidate=OWNER/'accessibility.proposed.py';exec(compile(candidate.read_text(encoding='utf-8'),str(candidate),'exec'),access.__dict__)
ns={'__file__':str(old),'__name__':'independent_permanent'}
exec(compile(new.read_text(encoding='utf-8'),str(new),'exec'),ns)
app=QApplication([]);app.setStyle('Fusion');app.setApplicationName('F8-Accessibility-Smoke');app.setOrganizationName('G4UniversalSimSmoke')
QSettings.setDefaultFormat(QSettings.IniFormat)
for name in ['segoeui.ttf','msyh.ttc']:QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
trace=[];cls=ns['MainWindow'];original=cls.focus_page
def target(obj):
    return None if obj is None else {'type':type(obj).__name__,'name':obj.objectName(),'accessible':obj.accessibleName()}
def traced(w,index):
    ctrl=w.accessibility_controller
    pending=lambda:ctrl._pending_focus() if ctrl._pending_focus else None
    row={'index':index,'focus_before':target(app.focusWidget()),'pending_before':target(pending())}
    value=original(w,index)
    row.update(focus_after=target(app.focusWidget()),pending_after=target(pending()));trace.append(row);return value
cls.focus_page=traced
ns['test_retained_dock_focus'](app,OUT/'permanent-target150')
output={'old_functions_ast_unchanged':True,'main_only_appends_call':True,'owner_log_hashes_match':True,'owner_v3_markers':[406,406],'both_patches_check_exit':0,'independent_new_test150_pass':True,'focus_page_trace':trace,'tracked_smoke_sha256':sha(old),'new_test_sha256':sha(new)}
(OUT/'permanent-test-review.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(output,ensure_ascii=False,indent=2))
