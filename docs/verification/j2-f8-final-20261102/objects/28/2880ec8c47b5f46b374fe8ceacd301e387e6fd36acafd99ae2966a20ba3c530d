from pathlib import Path
from datetime import datetime,timezone
import sys,os,tempfile,json,hashlib,copy,time,argparse,traceback
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args();WORK=OUT/args.label;WORK.mkdir();tempfile.tempdir=str(WORK)
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtCore import QSettings,Qt,QTimer,QPoint,QRect,QEvent
from PySide6.QtWidgets import QApplication,QPlainTextEdit,QDialog,QFormLayout,QLineEdit,QScrollArea,QWizard
from PySide6.QtTest import QTest
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.core.accessibility import ensure_focus_visible,decorate_accessibility
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(WORK/'settings'))
app=QApplication([]);app.setOrganizationName('IndependentReview');app.setApplicationName('F8-'+args.label)
FILES=['gui/g4usim_gui/core/accessibility.py','gui/g4usim_gui/widgets/start_page.py','gui/g4usim_gui/main_window.py','gui/g4usim_gui/window/shell.py','gui/smoke_tests/smoke_f8_accessibility.py']
def hashes():return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}
start=hashes();author=json.loads((ROOT/'out/collab/f8-accessibility/receipt.json').read_text(encoding='utf-8'))
w=MainWindow();w.show();w.activateWindow();QTest.qWait(50);app.processEvents();w.config_builder_page._backend_timer.stop();w.config_builder_page.schedule_backend_geometry=lambda *a,**k:None
results=[]
def pump(predicate=lambda:True,timeout=10):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  app.processEvents()
  if predicate():return
  QTest.qWait(5)
 assert predicate(),'Qt state deadline'
def case(name,fn):
 try:d=fn();r={'case':name,'status':'observed','detail':d}
 except Exception as e:r={'case':name,'status':'failure','error':type(e).__name__+': '+str(e),'traceback':traceback.format_exc()}
 results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
def snap():w._finish_history_merge();return snapshot_fingerprint(w.capture_workspace())
def keys():
 w.project_page.seed.setText('independent invalid seed');before=snap();runner=w.runner;session=w._edit_session;service=w.experiment;visited=[]
 for i in (8,0,6,2,7,1,4,3,5):
  w.activateWindow();QTest.keyClick(w,Qt.Key_1+i,Qt.ControlModifier|Qt.AltModifier);pump();assert w.page_stack.currentIndex()==i,(i,w.page_stack.currentIndex(),w.isActiveWindow())
  focused=QApplication.focusWidget();page=w._page_specs[i][0];assert focused is not None and (focused is page or page.isAncestorOf(focused));visited.append(i)
 QTest.keyClick(w,Qt.Key_F6);pump();QTest.keyClick(w,Qt.Key_F6,Qt.ShiftModifier);pump()
 assert snap()==before and w.runner is runner and w._edit_session is session and w.experiment is service
 return {'visited':visited,'same_snapshot_runner_session_workflow':True}
def foreign_scope():
 before=snap();foreign=QPlainTextEdit();foreign.setPlainText('foreign\ttext');assert not foreign.tabChangesFocus();foreign.show();foreign.setFocus();pump();assert not foreign.tabChangesFocus();assert not foreign.accessibleName();foreign.close()
 owned=QDialog(w);layout=QFormLayout(owned);field=QLineEdit('untouched');layout.addRow('Review &field:',field);owned.show();pump();assert field.accessibleName()=='Review field' and field.text()=='untouched';owned.reject();pump();assert snap()==before
 return {'unowned_multiline_untouched':True,'owned_dialog_named_without_value_mutation':True}
def multiline_and_busy():
 before=snap();w.focus_page(2);editor=w.config_builder_page.material_components;editor.setFocus();pump();assert editor.tabChangesFocus();text=editor.toPlainText();QTest.keyClick(editor,Qt.Key_Tab);pump();assert editor.toPlainText()==text and QApplication.focusWidget() is not editor;assert snap()==before
 # Existing mutation guard remains authoritative; no backend/process is started.
 with patch.object(w,'can_mutate_workspace',return_value=False):
  w.open_new_simulation_wizard()
 assert not w._f8_wizard_open and snap()==before
 return {'tab_changes_focus_not_text':True,'busy_guard_no_mutation_no_stuck_reentry_flag':True}
def environment_singleton():
 from g4usim_gui.widgets import environment_dialog as module
 facts={'schema':'g4usim_environment_discovery_v1','host':{'tools':{}},'sdk':[],'environments':[]}
 before=snap();runner=w.runner;service=w.experiment
 with patch.object(module,'discover_environments',return_value=facts):
  w.show_environment_settings();dialog=w._environment_dialog;pump(lambda:dialog.facts is not None and not dialog.busy)
  w.show_environment_settings();assert w._environment_dialog is dialog
  w.show_environment_installer();installer=dialog._installation_dialog;pump();w.show_environment_installer();assert dialog._installation_dialog is installer
  assert installer.isVisible() and not installer.busy and installer.plan is None and installer.receipt is None
  assert sum(1 for x in QApplication.topLevelWidgets() if type(x) is type(installer) and x.isVisible())==1
  installer.reject();dialog.reject();pump()
 assert snap()==before and w.runner is runner and w.experiment is service
 return {'same_visible_I1_and_I2_instances':True,'no_install_plan_run_or_snapshot_mutation':True}
def wizard_cancel():
 before=snap();failures=[];dialogs=[]
 def during():
  try:
   dialog=QApplication.activeModalWidget();assert isinstance(dialog,NewSimulationWizard);dialogs.append(dialog);dialog.scenario_page.name.setText('discarded draft');dialog.next();dialog.geometry_page.thickness.setValue(6);dialog.next();dialog.back();assert dialog.geometry_page.thickness.value()==6
   w.open_new_simulation_wizard();assert QApplication.activeModalWidget() is dialog
   assert len([x for x in QApplication.topLevelWidgets() if isinstance(x,NewSimulationWizard) and x.isVisible()])==1
   assert dialog.findChildren(QScrollArea)
   QTest.keyClick(dialog,Qt.Key_Escape)
  except Exception as e:
   failures.append(str(e));modal=QApplication.activeModalWidget()
   if modal is not None:modal.reject()
 for _ in range(2):
  QTimer.singleShot(0,during);w.open_new_simulation_wizard();assert not failures,failures;assert snap()==before
 assert dialogs[0] is not dialogs[1] and not w._f8_wizard_open
 return {'modal_reentry_keeps_one_instance':True,'back_keeps_local_draft':True,'esc_and_reopen_keep_project_invalid_draft':True}
def short_layout():
 before=snap();w.focus_page(0)
 for dock in w.workspace_layout.docks.values():dock.hide()
 w.resize(760,480);pump();visible=[]
 for button in [*w.start_page.start_actions,w.theme_button,w.language_button]:
  button.setFocus(Qt.TabFocusReason);ensure_focus_visible(button);pump()
  parent=button.parentWidget();clips=[]
  while parent is not None:
   if isinstance(parent,QScrollArea) and parent.widget().isAncestorOf(button):
    rect=QRect(button.mapTo(parent.viewport(),QPoint(0,0)),button.size());assert parent.viewport().rect().contains(rect),(button.text(),parent.objectName(),list((rect.x(),rect.y(),rect.width(),rect.height())),parent.viewport().size());clips.append(parent.objectName())
   parent=parent.parentWidget()
  visible.append({'button':button.text(),'scroll_ancestors':clips})
 assert snap()==before
 return {'window_size':[w.width(),w.height()],'focused_full_rect_visible':visible}
try:
 for name,fn in [('keyboard-navigation-business-isolation',keys),('event-filter-owned-scope',foreign_scope),('multiline-tab-and-busy-guard',multiline_and_busy),('environment-installer-singletons',environment_singleton),('wizard-nesting-back-esc-reopen',wizard_cancel),('760x480-nested-scroll-focus',short_layout)]:case(name,fn)
finally:close_window(app,w)
end=hashes();receipt={'scope':'independent offscreen component review, no native UI or actual install/backend','DPR':w.devicePixelRatioF(),'available_geometry':[app.primaryScreen().availableGeometry().width(),app.primaryScreen().availableGeometry().height()],'author_hashes_match':start==author['files'],'source_sha256_before':start,'source_sha256_after':end,'five_files_unchanged':start==end,'cases':results};(WORK/'results.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('FIVE_FILES_UNCHANGED',start==end)
raise SystemExit(1 if any(x['status']!='observed' for x in results) else 0)
