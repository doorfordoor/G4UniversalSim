from pathlib import Path
from dataclasses import asdict
import ast,copy,hashlib,json,os,sys,subprocess
ROOT=Path(__file__).resolve().parents[3];OWNER=ROOT/'out/collab/f8-history-label/v2';BASE=Path(__file__).resolve().parent
scale=sys.argv[1];OUT=BASE/('scale'+scale);OUT.mkdir(exist_ok=True)
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_SCALE_FACTOR=scale,G4USIM_RECOVERY_DIR=str(OUT/'recovery'))
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(OWNER/'run_history_page.proposed.py')=='cc98442e975cec3f1b33d556a8dabdd7381ec22368e94bd6124178edacb5a463'
assert sha(OWNER/'run_history_page.patch')=='c6f9a716e3f6d58050593bb33f8ada02f4432585ff03b8927aeac69f72a794de'
assert sha(OWNER/'smoke_f8_accessibility.patch')=='eefb54ee53de668796149d9c5d8de61ae8e18d7e6f100bbc6c0f5d65ff72cad8'
tracked=['gui/g4usim_gui/widgets/run_history_page.py','gui/g4usim_gui/core/accessibility.py','gui/g4usim_gui/window/shell.py','gui/smoke_tests/smoke_f8_accessibility.py','gui/g4usim_gui/core/i18n.py']
original={p:sha(ROOT/p) for p in tracked}
old=ast.parse((ROOT/tracked[3]).read_text(encoding='utf-8'));new=ast.parse((OWNER/'smoke_f8_accessibility.proposed.py').read_text(encoding='utf-8'))
funcs=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
a,b=funcs(old),funcs(new)
for name in a.keys()-{'main'}:assert ast.dump(a[name],include_attributes=False)==ast.dump(b[name],include_attributes=False),name
assert ast.unparse(b['main'].body[-2])=='test_history_directory_accessibility(app, args.output)'
del b['main'].body[-2];assert ast.dump(a['main'],include_attributes=False)==ast.dump(b['main'],include_attributes=False)
tree=ast.parse((OWNER/'run_history_page.proposed.py').read_text(encoding='utf-8'))
assignments=[]
for n in ast.walk(tree):
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_buddy':assignments.append(ast.unparse(n))
assert sorted(assignments)==sorted(['_buddy(runs_root_label, self.runs_root)','_buddy(search_label, self.search)','_buddy(status_label, self.status_filter)']),assignments
r=subprocess.run(['git','apply','--check',str(OWNER/'run_history_page.patch'),str(OWNER/'smoke_f8_accessibility.patch')],cwd=ROOT,capture_output=True,text=True);assert r.returncode==0,r.stderr
import g4usim_gui.widgets.run_history_page as module
candidate=OWNER/'run_history_page.proposed.py';exec(compile(candidate.read_text(encoding='utf-8'),str(candidate),'exec'),module.__dict__)
from PySide6.QtCore import Qt,QRect,QPoint,QSettings
from PySide6.QtWidgets import QApplication,QLabel,QScrollArea
from PySide6.QtGui import QAccessible,QFontDatabase
from PySide6.QtTest import QTest
from g4usim_gui.history import run_history_store
run_history_store.STATE_PATH=OUT/'history.json'
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(OUT/'settings'))
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.i18n import ui_text
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.core.accessibility import _reading_anchor
from smoke_k1_workflow import close_window
app=QApplication([]);app.setStyle('Fusion');app.setApplicationName('IndependentHistoryLabels');app.setOrganizationName('G4UniversalSimSmoke')
for name in ['segoeui.ttf','msyh.ttc']:QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
apply_theme(app,'light')
w=MainWindow(recovery_root=OUT/'recovery',offer_recovery=False)
p=w.project;runs=OUT/'not-created'/'long-history-runs-root';p.runsRoot=str(runs);p.pathSettings.runs_root=p.runsRoot;w._set_project(p);w._reset_edit_history()
w.config_builder_page._backend_timer.stop();w.config_builder_page.schedule_backend_geometry=lambda *a,**k:None
w.resize(760,640);w.show();w.activateWindow()
def settle():
 for _ in range(10):app.processEvents()
 QTest.qWait(30)
def key(k,mod=Qt.NoModifier):
 w.activateWindow();QTest.qWait(15);QTest.keyClick(w,k,mod);settle()
nav=lambda i:key(Qt.Key_1+i,Qt.ControlModifier|Qt.AltModifier)
page=w.run_history_page;field=page.runs_root
result={'scale':scale,'candidate_sha256':sha(candidate),'observations':[]}
def measure(control,label):
 parent=control.parentWidget();rows=[];inner_fit=True
 while parent:
  if isinstance(parent,QScrollArea) and parent.widget() and parent.widget().isAncestorOf(control):
   vp=parent.viewport();full=QRect(control.mapTo(vp,QPoint()),control.size());lab=QRect(label.mapTo(vp,QPoint()),label.size());joint=full.united(lab)
   prefix=QRect(full);prefix.setWidth(min(full.width(),128));context=lab.united(prefix)
   assert vp.rect().contains(context),(joint,context,vp.rect())
   inner_fit=inner_fit and joint.width()<=vp.width() and joint.height()<=vp.height()
   if inner_fit:assert vp.rect().contains(joint),(joint,vp.rect())
   rows.append({'viewport':list(vp.rect().getRect()),'joint':list(joint.getRect()),'field':list(full.getRect()),'reading_anchor':list(_reading_anchor(control,vp).getRect()),'h':parent.horizontalScrollBar().value(),'inner_all_fit':inner_fit})
  parent=parent.parentWidget()
 return rows
try:
 settle();baseline=snapshot_fingerprint(w.capture_workspace());history=(w._edit_session.can_undo,w._edit_session.can_redo,w._edit_session.is_modified)
 nav(2);key(Qt.Key_F6);docks=dict(w.workspace_layout.docks)
 for language in ['en','zh_CN','en']:
  w._set_language(language,persist=False);settle();nav(0);nav(7);assert app.focusWidget() is field
  pairs=[]
  for name,source in [('runs_root','Runs root'),('search','Search'),('status_filter','Status')]:
   control=getattr(page,name);label=next(l for l in page.findChildren(QLabel) if l.text()==ui_text(source));interface=QAccessible.queryAccessibleInterface(control)
   assert label.buddy() is control and control._f8_accessible_label is label
   assert interface and interface.text(QAccessible.Text.Name)==control.accessibleName()==ui_text(source)
   pairs.append({'field':name,'label':label.text(),'property':control.accessibleName(),'interface_name':interface.text(QAccessible.Text.Name),'role':str(interface.role())})
  lab=field._f8_accessible_label;rows=measure(field,lab)
  result['observations'].append({'language':language,'names':pairs,'viewports':rows})
  assert snapshot_fingerprint(w.capture_workspace())==baseline
  assert (w._edit_session.can_undo,w._edit_session.can_redo,w._edit_session.is_modified)==history
 assert any(not r['inner_all_fit'] for r in result['observations'][1]['viewports'])
 offset=w.content_scroll.horizontalScrollBar().value();assert offset>0;settle();assert w.content_scroll.horizontalScrollBar().value()==offset
 visited=[]
 for _ in range(16):
  QTest.keyClick(app.focusWidget(),Qt.Key_Tab);settle();focused=app.focusWidget()
  for name in ['search','status_filter']:
   if focused is getattr(page,name) and name not in visited:
    visited.append(name);measure(focused,focused._f8_accessible_label)
  if len(visited)==2:break
 assert sorted(visited)==['search','status_filter'],visited
 # Widen naturally and reenter History: whenever all inner layers fit, require full joint.
 w.resize(1600,900);settle();nav(0);nav(7);wide=measure(field,field._f8_accessible_label)
 result['wide_viewports']=wide;assert any(r['inner_all_fit'] for r in wide)
 assert all(w.workspace_layout.docks[k] is v for k,v in docks.items())
 assert snapshot_fingerprint(w.capture_workspace())==baseline and not runs.exists()
 assert all(sha(ROOT/p)==v for p,v in original.items())
 result.update(passed=True,actual_tab_visited=visited,old_functions_AST_unchanged=True,main_only_appends=True,explicit_buddy_calls=assignments,tracked_unchanged=True,no_business_change=True,no_native_or_backend=True)
finally:
 (OUT/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');close_window(app,w)
print(json.dumps(result,ensure_ascii=False,indent=2))
