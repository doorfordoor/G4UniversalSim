import os,sys,json,hashlib,dataclasses,copy
from pathlib import Path
ROOT=Path.cwd(); OUT=ROOT/('out/collab/f8-project-dock150/regression-final'+os.environ.get('F8_PROBE_SCALE','1.5'));OUT.mkdir(parents=True,exist_ok=True)
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_SCALE_FACTOR']=os.environ.get('F8_PROBE_SCALE','1.5')
os.environ['G4USIM_RECOVERY_DIR']=str(OUT/'recovery')
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtCore import QSettings,Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from g4usim_gui.history import run_history_store
run_history_store.STATE_PATH=OUT/'history.json'
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(OUT/'settings'))
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint,snapshot_to_dict
from smoke_k1_workflow import close_window
app=QApplication([]);app.setApplicationName('J2 F8 Native Acceptance');app.setOrganizationName('G4UniversalSimAcceptance');app.setStyle('Fusion');
from PySide6.QtGui import QFontDatabase
for font in ('segoeui.ttf','msyh.ttc'): QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/font))
apply_theme(app,'light');set_application_language(app,'zh_CN')
from PySide6.QtCore import QTimer,QRect,QPoint,QEvent
from PySide6.QtWidgets import QStackedWidget,QScrollArea,QWizard
identity=json.loads((ROOT/'out/verification/j2-f8-56b689f/native150/identity.json').read_text())
sys.path.insert(0,str(ROOT/'out/collab/f8-project-dock150'))
from candidate import install
import g4usim_gui.core.accessibility as access
install()
w=MainWindow(recovery_root=OUT/'recovery',offer_recovery=False)
p=w.project;p.executable=identity['exe'];p.pathSettings.executable=p.executable;p.runsRoot=str(OUT/'runs');p.pathSettings.runs_root=p.runsRoot;p.outputDir=str(OUT/'runs/demo/output');w._set_project(p);w._reset_edit_history();w.resize(760,640)
w.config_builder_page._backend_timer.stop();w.config_builder_page.schedule_backend_geometry=lambda*a,**k:None
w.show();w.activateWindow()
baseline=snapshot_fingerprint(w.capture_workspace())
rows=[]
def pump():
 for _ in range(15):app.processEvents()
def rect(x):return list(x.getRect())
def widget_info(x):
 return {'class':type(x).__name__,'name':x.objectName(),'accessible':x.accessibleName(),'visible':x.isVisible(),'geometry':rect(x.geometry()),'global':rect(QRect(x.mapToGlobal(QPoint()),x.size())),'minimum':list((x.minimumWidth(),x.minimumHeight())),'min_hint':list((x.minimumSizeHint().width(),x.minimumSizeHint().height())),'hint':list((x.sizeHint().width(),x.sizeHint().height()))}
def record(stage):
 pump();field=w.project_page.project_name;f=app.focusWidget();anc=[];parent=field.parentWidget()
 while parent:
  info=widget_info(parent)
  if isinstance(parent,QScrollArea):
   vp=parent.viewport();mapped=QRect(field.mapTo(vp,QPoint()),field.size());info.update(viewport=rect(vp.rect()),field_mapped=rect(mapped),intersection=rect(mapped.intersected(vp.rect())),h=[parent.horizontalScrollBar().value(),parent.horizontalScrollBar().maximum()],v=[parent.verticalScrollBar().value(),parent.verticalScrollBar().maximum()])
  anc.append(info);parent=parent.parentWidget()
 row={'stage':stage,'page':w.page_stack.currentIndex(),'stack':widget_info(w.page_stack),'actual_central':widget_info(QStackedWidget.currentWidget(w.page_stack)),'focus':widget_info(f) if f else None,'project_field':widget_info(field),'ancestors':anc,'docks':{k:widget_info(d) for k,d in w.workspace_layout.docks.items()},'content_h':[w.content_scroll.horizontalScrollBar().value(),w.content_scroll.horizontalScrollBar().maximum()],'content_v':[w.content_scroll.verticalScrollBar().value(),w.content_scroll.verticalScrollBar().maximum()]}
 rows.append(row);w.grab().save(str(OUT/(stage+'.png')))
def key(key,mod=Qt.NoModifier):
 w.activateWindow();QTest.qWait(40);QTest.keyClick(w,key,mod);pump()
try:
 pump();key(Qt.Key_2,Qt.ControlModifier|Qt.AltModifier);record('01-project-initial')
 key(Qt.Key_3,Qt.ControlModifier|Qt.AltModifier);record('02-config')
 key(Qt.Key_F6);record('03-f6')
 def wizard_steps():
  z=app.activeModalWidget()
  assert isinstance(z,QWizard),repr(z)
  for _ in range(3):QTest.keyClick(z,Qt.Key_Return);pump()
  QTest.keyClick(z,Qt.Key_Left,Qt.AltModifier);pump();QTest.keyClick(z,Qt.Key_Escape);pump()
 QTimer.singleShot(200,wizard_steps);key(Qt.Key_N,Qt.ControlModifier);record('04-cancel')
 w._theme_actions['dark'].trigger();record('05-dark')
 key(Qt.Key_2,Qt.ControlModifier|Qt.AltModifier);record('06-project-final')
 # Observe settled layout too, without scrolling or changing focus.
 QTest.qWait(500);record('07-project-settled')
 def assert_union_visible():
  field=w.project_page.project_name;label=field._f8_accessible_label;parent=field.parentWidget()
  while parent:
   if isinstance(parent,QScrollArea) and parent.widget().isAncestorOf(field):
    vp=parent.viewport();union=QRect(field.mapTo(vp,QPoint()),field.size()).united(QRect(label.mapTo(vp,QPoint()),label.size()))
    if union.width()<=vp.width():assert union.left()>=0 and union.right()<vp.width(),(parent.objectName(),union,vp.rect())
    if union.height()<=vp.height():assert union.top()>=0 and union.bottom()<vp.height(),(parent.objectName(),union,vp.rect())
   parent=parent.parentWidget()
 assert w.page_stack.currentIndex()==1
 assert_union_visible()
 assert w.workspace_layout.docks['configuration'].isVisible() and w.workspace_layout.docks['preview'].isVisible()
 docks=dict(w.workspace_layout.docks);owners={k:v.parentWidget() for k,v in docks.items()}
 # Retained peer docks; nine-page navigation and F6 must preserve instances.
 for page in range(9):
  key(Qt.Key_1+page,Qt.ControlModifier|Qt.AltModifier)
  assert w.page_stack.currentIndex()==page
  focus=app.focusWidget();assert focus is not None and w.page_stack.currentWidget().isAncestorOf(focus)
  key(Qt.Key_F6)
  focus=app.focusWidget();assert focus is not None and access.owned_widget(w,focus)
  assert all(w.workspace_layout.docks[k] is dock and dock.parentWidget() is owners[k] for k,dock in docks.items())
 key(Qt.Key_2,Qt.ControlModifier|Qt.AltModifier);QTest.qWait(100);assert_union_visible();record('08-ninepage-return')
 # A stale pending request must not reveal an old control after new navigation.
 w.focus_page(1);w.focus_page(0);pump();QTest.qWait(60)
 assert w.page_stack.currentIndex()==0 and w.start_page.isAncestorOf(app.focusWidget())
 # Foreign window gets focus before the pending callback; neither scroll changes.
 from PySide6.QtWidgets import QDialog,QLineEdit,QVBoxLayout
 foreign=QDialog();box=QVBoxLayout(foreign);foreign_field=QLineEdit();box.addWidget(foreign_field)
 w.focus_page(1);before_foreign=w.content_scroll.horizontalScrollBar().value()
 foreign.show();foreign.activateWindow();foreign_field.setFocus();QTest.qWait(80);pump()
 assert app.focusWidget() is foreign_field
 assert w.content_scroll.horizontalScrollBar().value()==before_foreign
 assert foreign_field.text()==''
 foreign.close();foreign.deleteLater();w.activateWindow();QTest.qWait(30)
 # Deleted owned focus target: QTimer must not dereference invalid C++ wrappers.
 owned=QDialog(w);box=QVBoxLayout(owned);doomed=QLineEdit();box.addWidget(doomed);owned.show();owned.activateWindow();doomed.setFocus();owned.deleteLater()
 from PySide6.QtCore import QCoreApplication
 QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);pump();QTest.qWait(60)
 w.activateWindow();key(Qt.Key_2,Qt.ControlModifier|Qt.AltModifier);QTest.qWait(80);assert_union_visible()
 assert snapshot_fingerprint(w.capture_workspace())==baseline
 assert not w._edit_session.can_undo and not w._edit_session.is_modified
 from smoke_f8_accessibility import test_minimal_scroll
 test_minimal_scroll(app)
 print('candidate retained-dock / ninepage+F6 / stale+foreign+deleted / no-business-change / union assertions passed')

finally:
 (OUT/'results.json').write_text(json.dumps({'rows':rows,'deferred_reveals':getattr(w.accessibility_controller,'reveal_evidence',[]),'gui_source_differences':[path for path,sha in identity['gui_files'].items() if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha]},ensure_ascii=False,indent=2),encoding='utf-8');close_window(app,w)
print('completed',len(rows),'stages')
