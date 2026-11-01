from pathlib import Path
import ast,hashlib,json,os,sys,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'v3-stale';OUT.mkdir(exist_ok=True)
OWNER=ROOT/'out/collab/f8-project-dock150/v3';PRODUCT=ROOT/'out/collab/f8-project-dock150/accessibility.proposed.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=OWNER/'smoke_f8_accessibility.proposed.py';patch=OWNER/'smoke_f8_accessibility.patch';old=ROOT/'gui/smoke_tests/smoke_f8_accessibility.py'
assert sha(source)=='69b11a915a0864110171df75a1a2402ea3025f0a3a01b79d31af8ee26bd9f0e6'
assert sha(patch)=='247e4a6925906471d0b40dd70800149c37fc4aa963d379888c6ada321c3cb6ce'
assert b'\r\n' not in source.read_bytes() and b'\r\n' not in patch.read_bytes()
a=ast.parse(old.read_text(encoding='utf-8'));b=ast.parse(source.read_text(encoding='utf-8'))
func=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
fa,fb=func(a),func(b)
for name in fa.keys()-{'main'}:assert ast.dump(fa[name],include_attributes=False)==ast.dump(fb[name],include_attributes=False)
main=fb['main'];assert ast.unparse(main.body[-2])=='test_retained_dock_focus(app, args.output)';del main.body[-2]
assert ast.dump(main,include_attributes=False)==ast.dump(fa['main'],include_attributes=False)
r=subprocess.run(['git','apply','--check',str(ROOT/'out/collab/f8-project-dock150/accessibility.lf.patch'),str(patch)],cwd=ROOT,capture_output=True,text=True);assert r.returncode==0,r.stderr
# Extract exactly the permanent stale block. Its setup is independent and minimal.
lines=source.read_text(encoding='utf-8').splitlines()
start=next(i for i,l in enumerate(lines) if '# First leave Project naturally' in l)
end=next(i for i,l in enumerate(lines[start:],start) if '# A foreign QWidget focus' in l)
import textwrap
block=textwrap.dedent('\n'.join(lines[start:end]));(OUT/'extracted-stale.py').write_text(block,encoding='utf-8')
scale=sys.argv[1];os.environ.update(QT_QPA_PLATFORM='offscreen',QT_SCALE_FACTOR=scale)
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
import g4usim_gui.core.accessibility as access
assert sha(PRODUCT)=='677a7b54c5ce876d663b6d986642ee5393a385b782a29dad695c2ed20d280b39'
exec(compile(PRODUCT.read_text(encoding='utf-8'),str(PRODUCT),'exec'),access.__dict__)
from PySide6.QtCore import Qt,QRect,QPoint,QSettings
from PySide6.QtWidgets import QApplication,QScrollArea
from PySide6.QtTest import QTest
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.core.i18n import set_application_language
app=QApplication([]);app.setStyle('Fusion');app.setApplicationName('IndependentV3Stale');app.setOrganizationName('G4UniversalSimSmoke')
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(OUT/('settings-'+scale)))
set_application_language(app,'zh_CN')
window=MainWindow();window.config_builder_page._backend_timer.stop();window.config_builder_page.schedule_backend_geometry=lambda *a,**k:None
window.resize(760,640);window.show();window.activateWindow()
def settle():
 for _ in range(8):app.processEvents()
 QTest.qWait(30)
def key(w,k,mod=Qt.NoModifier):
 w.activateWindow();QTest.qWait(20);QTest.keyClick(w,k,mod);settle()
observations=[]
try:
 settle();key(window,Qt.Key_3,Qt.ControlModifier|Qt.AltModifier);key(window,Qt.Key_2,Qt.ControlModifier|Qt.AltModifier)
 field=window.project_page.project_name
 baseline=snapshot_fingerprint(window.capture_workspace());history=(window._edit_session.can_undo,window._edit_session.can_redo,window._edit_session.is_modified)
 calls=[];original=access.ensure_focus_visible
 def track(control):calls.append(control);return original(control)
 access.ensure_focus_visible=track
 # Execute the actual v3 stale assertions, without rewriting them.
 exec(compile(block,str(OUT/'extracted-stale.py'),'exec'),globals())
 assert observations[0]['pending_is_project'] and observations[0]['timer_active']
 assert not observations[1]['old_project_pending']
 assert snapshot_fingerprint(window.capture_workspace())==baseline
 assert (window._edit_session.can_undo,window._edit_session.can_redo,window._edit_session.is_modified)==history
 assert sha(old)=='7087edc6ae93bb666020eb06fb46bd8a60b2539c0213b5058276daf385d04c8e'
 result={'passed':True,'scale':scale,'observations':observations,'exact_permanent_stale_block_executed':True,'old_functions_ast_unchanged':True,'main_only_appends_call':True,'both_patches_check_exit':0,'LF':True,'tracked_unchanged':True,'product_sha256':sha(PRODUCT),'test_sha256':sha(source),'scope':'stale-only offscreen, not full416 rerun'}
 (OUT/('receipt-'+scale+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
finally:
 access.ensure_focus_visible=locals().get('original',access.ensure_focus_visible);close_window(app,window)
