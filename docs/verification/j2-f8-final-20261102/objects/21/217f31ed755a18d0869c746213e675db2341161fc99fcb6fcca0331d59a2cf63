from pathlib import Path
import os,sys,json,hashlib,traceback,ast
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/sys.argv[1]
OUT.mkdir(exist_ok=True)
scale=sys.argv[1].replace('candidate','')
os.environ.update(QT_QPA_PLATFORM='offscreen',QT_SCALE_FACTOR=scale,G4USIM_RECOVERY_DIR=str(OUT/'recovery'))
os.environ.pop('G4USIM_ENABLE_OFFSCREEN_PYVISTA',None)
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtCore import Qt,QRect,QPoint,QTimer,QSettings,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QScrollArea,QDialog,QLineEdit,QVBoxLayout,QWizard,QWidget,QLabel,QPushButton
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase
from shiboken6 import isValid
from g4usim_gui.history import run_history_store
run_history_store.STATE_PATH=OUT/'history.json'
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(OUT/'settings'))
import g4usim_gui.core.accessibility as access
candidate=ROOT/'out/collab/f8-project-dock150/accessibility.proposed.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(candidate)=='677a7b54c5ce876d663b6d986642ee5393a385b782a29dad695c2ed20d280b39'
tracked={p:sha(ROOT/p) for p in ['gui/g4usim_gui/core/accessibility.py','gui/g4usim_gui/window/shell.py','gui/g4usim_gui/window/workspace_layout.py','gui/smoke_tests/smoke_f8_accessibility.py']}
# Check that original minimal-reveal primitives are byte-equivalent AST.
oldtree=ast.parse((ROOT/'gui/g4usim_gui/core/accessibility.py').read_text(encoding='utf-8'))
newtree=ast.parse(candidate.read_text(encoding='utf-8'))
for name in ['_reading_anchor','_reveal_axis','ensure_focus_visible','_focus_control','owned_widget']:
    extract=lambda tree:ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
    assert extract(oldtree)==extract(newtree),name
exec(compile(candidate.read_text(encoding='utf-8'),str(candidate),'exec'),access.__dict__)
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from smoke_k1_workflow import close_window
app=QApplication([]);app.setStyle('Fusion');app.setOrganizationName('IndependentF8');app.setApplicationName('Candidate'+scale)
for filename in ['segoeui.ttf','msyh.ttc']:
    path=Path(os.environ['WINDIR'])/'Fonts'/filename
    if path.exists():QFontDatabase.addApplicationFont(str(path))
set_application_language(app,'zh_CN');apply_theme(app,'light')
w=MainWindow(recovery_root=OUT/'recovery',offer_recovery=False)
w.config_builder_page._backend_timer.stop();w.config_builder_page.schedule_backend_geometry=lambda *a,**k:None
w.resize(760,640);w.show();w.activateWindow()
def settle():
    for _ in range(8):app.processEvents()
    QTest.qWait(30)
def key(k,mod=Qt.NoModifier):
    w.activateWindow();QTest.qWait(15);QTest.keyClick(w,k,mod);settle()
nav=lambda k:key(Qt.Key_1+k,Qt.ControlModifier|Qt.AltModifier)
def union_observation(field):
    parent=field.parentWidget();answer=[]
    label=getattr(field,'_f8_accessible_label',None)
    while parent:
        if isinstance(parent,QScrollArea) and parent.widget() and parent.widget().isAncestorOf(field):
            vp=parent.viewport();box=QRect(field.mapTo(vp,QPoint()),field.size())
            if label and label.isVisible():box=box.united(QRect(label.mapTo(vp,QPoint()),label.size()))
            row={'viewport':list(vp.rect().getRect()),'union':list(box.getRect()),'scroll':[parent.horizontalScrollBar().value(),parent.verticalScrollBar().value()]}
            if box.width()<=vp.width():assert box.left()>=0 and box.right()<vp.width(),row
            if box.height()<=vp.height():assert box.top()>=0 and box.bottom()<vp.height(),row
            answer.append(row)
        parent=parent.parentWidget()
    return answer
result={'scale':scale,'candidate_sha256':sha(candidate),'groups':[]}
try:
    settle();baseline=snapshot_fingerprint(w.capture_workspace());docks=dict(w.workspace_layout.docks);parents={k:v.parentWidget() for k,v in docks.items()}
    nav(1);nav(2);key(Qt.Key_F6)
    wizard_errors=[]
    def cancel_natural():
        dialog=app.activeModalWidget()
        try:
            assert isinstance(dialog,QWizard),dialog
            for _ in range(3):QTest.keyClick(dialog,Qt.Key_Return);settle()
            QTest.keyClick(dialog,Qt.Key_Left,Qt.AltModifier);settle()
            QTest.keyClick(dialog,Qt.Key_Escape)
        except BaseException:
            wizard_errors.append(traceback.format_exc())
            if dialog:dialog.reject()
    QTimer.singleShot(100,cancel_natural);key(Qt.Key_N,Qt.ControlModifier)
    assert not wizard_errors,wizard_errors
    w._theme_actions['dark'].trigger();settle();nav(1)
    assert w.page_stack.currentIndex()==1 and app.focusWidget() is w.project_page.project_name
    result['retained_project_union']=union_observation(w.project_page.project_name)
    assert all(w.workspace_layout.docks[k] is v and v.parentWidget() is parents[k] for k,v in docks.items())
    assert docks['configuration'].isVisible() and docks['preview'].isVisible()
    result['groups'].append('natural F6/wizard Back/Esc/dark/Project retained docks')
    for page in [8,4,0,7,3,6,2,5,1]:
        nav(page);assert w.page_stack.currentIndex()==page
        focus=app.focusWidget();assert focus and (focus is w.page_stack.currentWidget() or w.page_stack.currentWidget().isAncestorOf(focus))
        key(Qt.Key_F6);assert access.owned_widget(w,app.focusWidget())
    nav(1);union_observation(w.project_page.project_name)
    result['groups'].append('nine pages/F6 preserve dock identity and F5 snapshot')
    calls=[];original=access.ensure_focus_visible
    def record(control):
        calls.append(control);return original(control)
    access.ensure_focus_visible=record
    controller=w.accessibility_controller
    # Old request superseded by natural immediate navigation before event loop settles.
    w.focus_page(1);old=w.project_page.project_name
    w.focus_page(0);calls.clear();settle()
    assert old not in calls and w.page_stack.currentIndex()==0
    result['groups'].append('stale focus cannot return to old Project')
    nav(1);controller._queue_focus_reveal(w.project_page.project_name)
    foreign=QDialog();layout=QVBoxLayout(foreign);foreign_field=QLineEdit();layout.addWidget(foreign_field)
    foreign.show();foreign.activateWindow();foreign_field.setFocus();calls.clear();offset=w.content_scroll.horizontalScrollBar().value();settle()
    assert app.focusWidget() is foreign_field
    assert not calls,calls
    assert w.content_scroll.horizontalScrollBar().value()==offset
    foreign.close();foreign.deleteLater();settle();w.activateWindow()
    result['groups'].append('foreign focus cancels queued owned reveal')
    owned=QDialog(w);layout=QVBoxLayout(owned);doomed=QLineEdit();layout.addWidget(doomed);owned.show();owned.activateWindow();doomed.setFocus()
    controller._queue_focus_reveal(doomed);owned.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);calls.clear();settle()
    assert not isValid(doomed) and not calls
    result['groups'].append('deleted C++ control drops pending reveal')
    nav(1);field=w.project_page.project_name;controller._queue_focus_reveal(field)
    field.setEnabled(False);calls.clear();settle();assert field not in calls
    field.setEnabled(True);nav(1)
    assert snapshot_fingerprint(w.capture_workspace())==baseline
    assert not w._edit_session.can_undo and not w._edit_session.is_modified
    result['groups'].append('disabled target and no F5/undo/draft mutation')
    controller._queue_focus_reveal(field);controller.close();calls.clear();settle()
    assert not controller._reveal_timer.isActive() and controller._pending_focus is None and not calls
    result['groups'].append('close cancels pending task')
    # Independent 5px union and nonzero-pan test, avoiding focus-event side effects.
    s=QScrollArea();s.resize(320,180);content=QWidget();content.resize(1200,150);s.setWidget(content)
    button=QPushButton('Read',content);button.setGeometry(600,20,100,30)
    label=QLabel('Context',content);label.setGeometry(580,70,120,30)
    edit=QLineEdit(content);edit.setGeometry(710,70,100,30);label.setBuddy(edit);edit._f8_accessible_label=label
    s.show();settle();bar=s.horizontalScrollBar();bar.setValue(500)
    original(button);assert bar.value()==500
    original(s);assert bar.value()==500
    bar.setValue(810-s.viewport().width()-5);initial=bar.value();original(edit)
    assert bar.value()==initial+5,(initial,bar.value())
    box=QRect(edit.mapTo(s.viewport(),QPoint()),edit.size()).united(QRect(label.mapTo(s.viewport(),QPoint()),label.size()))
    assert s.viewport().rect().contains(box)
    stable=bar.value();original(edit);assert bar.value()==stable
    s.close();s.deleteLater();settle()
    result['groups'].append('nonzero pan preserved; exact 5px union reveal/idempotence')
    assert all(sha(ROOT/p)==before for p,before in tracked.items())
    result.update(passed=True,tracked_sha256=tracked,tracked_unchanged=True)
except BaseException:
    result.update(passed=False,error=traceback.format_exc());raise
finally:
    (OUT/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    access.ensure_focus_visible=locals().get('original',access.ensure_focus_visible)
    close_window(app,w)
print(json.dumps(result,ensure_ascii=False,indent=2))
