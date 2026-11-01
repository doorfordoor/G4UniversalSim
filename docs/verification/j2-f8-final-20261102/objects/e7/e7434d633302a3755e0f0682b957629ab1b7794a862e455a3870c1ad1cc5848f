from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,time,hashlib,tempfile,argparse
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);parser.add_argument('--wizard-buttons',action='store_true');args=parser.parse_args();WORK=OUT/args.label;WORK.mkdir();tempfile.tempdir=str(WORK);os.environ['QT_QPA_PLATFORM']='offscreen';sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtCore import QSettings,Qt,QRect,QPoint,QTimer
from PySide6.QtWidgets import QApplication,QLabel,QScrollArea,QPlainTextEdit,QWizard
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.core.theme import apply_theme
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(WORK/'settings'));app=QApplication([]);app.setOrganizationName('IndependentReview');app.setApplicationName('F8Natural-'+args.label);app.setStyle('Fusion')
if os.name=='nt':
 for name in ('segoeui.ttf','msyh.ttc'):
  p=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name
  if p.is_file():QFontDatabase.addApplicationFont(str(p))
apply_theme(app,'light')
FILES=['gui/g4usim_gui/core/accessibility.py','gui/g4usim_gui/window/shell.py','gui/smoke_tests/smoke_f8_accessibility.py','gui/g4usim_gui/main_window.py','gui/g4usim_gui/widgets/start_page.py']
def hashes():return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}
start=hashes();w=MainWindow();w.config_builder_page._backend_timer.stop();w.config_builder_page.schedule_backend_geometry=lambda *a,**k:None;w.resize(1200,800);w._set_language('zh_CN',persist=False);w.show();w.activateWindow();QTest.qWait(60);app.processEvents();results=[];measurements=[]
def pump():app.processEvents();QTest.qWait(10);app.processEvents()
def keypage(i):w.activateWindow();QTest.keyClick(w,Qt.Key_1+i,Qt.ControlModifier|Qt.AltModifier);pump();assert w.page_stack.currentIndex()==i

def measure(label,control):
 rows=[]
 for target,role in [(label,'label'),(control,'control')]:
  if target is None:continue
  parent=target.parentWidget()
  while parent is not None:
   if isinstance(parent,QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(target):
    r=QRect(target.mapTo(parent.viewport(),QPoint()),target.size());v=parent.viewport().rect();fit=r.width()<=v.width();okay=v.contains(r) if fit else v.contains(r.topLeft());rows.append({'role':role,'control_type':type(control).__name__,'control_name':control.accessibleName(),'label_text':label.text() if label is not None else '', 'scroll':parent.objectName(),'rect':[r.x(),r.y(),r.width(),r.height()],'viewport':[v.width(),v.height()],'horizontal_value':parent.horizontalScrollBar().value(),'fits':fit,'visible':okay})
   parent=parent.parentWidget()
 return rows

def case(name,fn):
 try:detail=fn();r={'case':name,'status':'observed','detail':detail}
 except Exception as e:r={'case':name,'status':'failure','error':type(e).__name__+': '+str(e)}
 results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
def check_field(page_index,field):
 keypage(page_index);focused=QApplication.focusWidget();labels=[x for x in w.findChildren(QLabel) if x.buddy() is field];assert labels,'Missing actual form label buddy';label=labels[0];rows=measure(label,field);measurement={'page':page_index,'focus_type':type(focused).__name__,'focus_is_scroll_container':isinstance(focused,QScrollArea),'field_is_focused':focused is field,'rows':rows};measurements.append(measurement)
 assert not isinstance(focused,QScrollArea),measurement
 assert focused is not None and (w._page_specs[page_index][0] is focused or w._page_specs[page_index][0].isAncestorOf(focused)),measurement
 assert rows and all(x['visible'] for x in rows),measurement
 return measurement
try:
 w.project_page.seed.setText('preserved natural-focus invalid seed');w._finish_history_merge();before=snapshot_fingerprint(w.capture_workspace());runner=w.runner;service=w.experiment
 case('natural-CtrlAlt2-project-label',lambda:check_field(1,w.project_page.project_name))
 case('natural-CtrlAlt3-config-label',lambda:check_field(2,w.config_builder_page.run_name))
 def navigation():
  visited=[]
  for i in (0,8,1,6,2,7,3,5,4):
   keypage(i);focus=QApplication.focusWidget();page=w._page_specs[i][0];assert focus is not None and (focus is page or page.isAncestorOf(focus));assert not isinstance(focus,QScrollArea),(i,type(focus).__name__);visited.append(i)
  QTest.keyClick(w,Qt.Key_F6);pump();QTest.keyClick(w,Qt.Key_F6,Qt.ShiftModifier);pump();return {'visited':visited}
 case('all-nine-and-F6',navigation)
 def tab_and_foreign():
  keypage(1)
  for _ in range(6):
   focus=QApplication.focusWidget();labels=[x for x in w.findChildren(QLabel) if x.buddy() is focus];rows=measure(labels[0],focus) if labels else []
   if rows:assert all(x['visible'] for x in rows),rows
   QTest.keyClick(focus,Qt.Key_Tab);pump()
  return {'natural_Tab_label_bounds':True}
 case('natural-Tab-label-bounds',tab_and_foreign)
 def foreign_boundary():
  foreign=QPlainTextEdit();foreign.setPlainText('foreign content');foreign.show();foreign.setFocus();pump();assert not foreign.tabChangesFocus() and not foreign.accessibleName() and foreign.toPlainText()=='foreign content';foreign.close();return {'foreign_scope_untouched':True}
 case('foreign-boundary',foreign_boundary)
 if args.wizard_buttons:
  def wizard_buttons():
   failures=[];observed=[]
   expected={'en':{'Next':'Next','Back':'Back','Finish':'Finish','Cancel':'Cancel'},'zh_CN':{'Next':'下一步','Back':'上一步','Finish':'完成','Cancel':'取消'}}
   roles=((QWizard.BackButton,'Back'),(QWizard.NextButton,'Next'),(QWizard.FinishButton,'Finish'),(QWizard.CancelButton,'Cancel'))
   def inside():
    try:
     dialog=QApplication.activeModalWidget();assert isinstance(dialog,NewSimulationWizard)
     for stage in ('start','geometry','source','run','back-source'):
      if stage in ('geometry','source','run'):dialog.next()
      elif stage=='back-source':
       back=dialog.button(QWizard.BackButton);assert back.isEnabled();back.setFocus();QTest.keyClick(back,Qt.Key_Space);pump();assert dialog.currentId()==2
      for language in ('en','zh_CN','en'):
       w._set_language(language,persist=False);pump()
       for role,key in roles:
        label=expected[language][key];button=dialog.button(role)
        assert dialog.buttonText(role)==label,(stage,language,key,dialog.buttonText(role))
        assert button.accessibleName()==label,(stage,language,key,button.accessibleName())
        assert (key=='Back' and not button.text()) or button.text().replace('&','')==label,(stage,language,key,button.text())
       observed.append({'stage':stage,'language':language,'four_button_texts_and_names':True})
     QTest.keyClick(dialog,Qt.Key_Escape)
    except Exception as error:
     failures.append(str(error));modal=QApplication.activeModalWidget()
     if modal is not None:modal.reject()
   QTimer.singleShot(0,inside);w.open_new_simulation_wizard();assert not failures,failures;assert not w._f8_wizard_open
   return {'stages':observed,'cancel_does_not_apply':True}
  case('wizard-four-buttons-en-zh-en',wizard_buttons)
 w._finish_history_merge();assert snapshot_fingerprint(w.capture_workspace())==before;assert w.runner is runner and w.experiment is service
finally:close_window(app,w)
receipt={'scope':'natural Qt shortcuts/focus; no scrollbar writes/forced-zero/explicit ensureWidgetVisible; no native UI','DPR':w.devicePixelRatioF(),'window':[w.width(),w.height()],'source_sha256_before':start,'source_sha256_after':hashes(),'source_unchanged':start==hashes(),'cases':results,'measurements':measurements};(WORK/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('SOURCE_UNCHANGED',start==hashes());raise SystemExit(1 if any(x['status']!='observed' for x in results) else 0)
