from pathlib import Path
import os,sys,tempfile,json,time
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'wizard-diagnostic';OUT.mkdir();tempfile.tempdir=str(OUT);sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')];os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QWizard
from PySide6.QtCore import QSettings,QTimer
from PySide6.QtTest import QTest
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(OUT/'settings'));app=QApplication([]);app.setOrganizationName('IndependentReview');app.setApplicationName('WizardDelayedDiagnostic');w=MainWindow();w._set_language('zh_CN',persist=False);w.show();w.activateWindow();QTest.qWait(50);app.processEvents();rows=[]
def record(dialog,lang,phase):
 for role,key in [(QWizard.BackButton,'Back'),(QWizard.NextButton,'Next'),(QWizard.FinishButton,'Finish'),(QWizard.CancelButton,'Cancel')]:
  b=dialog.button(role);rows.append({'language':lang,'phase':phase,'key':key,'role_text':dialog.buttonText(role),'text':b.text(),'accessible_name':b.accessibleName(),'visible':b.isVisible(),'enabled':b.isEnabled()})
def inside():
 dialog=QApplication.activeModalWidget()
 try:
  for language in ['en','zh_CN','en']:
   w._set_language(language,persist=False);record(dialog,language,'immediate');app.processEvents();QTest.qWait(10);app.processEvents();record(dialog,language,'after-events')
 finally:dialog.reject()
try:QTimer.singleShot(0,inside);w.open_new_simulation_wizard()
finally:close_window(app,w)
(OUT/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(rows,ensure_ascii=False))
