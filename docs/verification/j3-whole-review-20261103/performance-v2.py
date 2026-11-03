import sys,os,json,time,statistics,tempfile,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(exist_ok=False)
sys.path[:0]=[str(root/'gui'),str(root/'gui/smoke_tests')]
from PySide6.QtCore import QSettings,qVersion,QThreadPool
from PySide6.QtWidgets import QApplication,QLabel
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.app import _close_self_test_window
from smoke_plots import fixture
from async_wait import wait_for_idle
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(out/'settings'))
run_history_store.STATE_PATH=out/'history.json'
app=QApplication([]);app.setOrganizationName('J3ReviewBench');app.setApplicationName(out.name);app.setStyle('Fusion')
apply_theme(app,'light','B');set_application_language(app,'zh_CN')
w=MainWindow(recovery_root=out/'recovery',offer_recovery=False);w.resize(1280,820);w.show();app.processEvents()
report={'head':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),'qt':qVersion(),'qpa':app.platformName(),'DPR':w.devicePixelRatioF(),'font':app.font().families(),'scenes':[]}
try:
 for scene in ['no-results','plot-fixture']:
  result=out/scene;result.mkdir()
  if scene=='plot-fixture':fixture(result)
  w.output_page.set_output_dir(str(result));wait_for_idle(w.output_page.plot_panel)
  w.page_stack.setCurrentWidget(w.output_page);w.workspace_layout.apply_preset('analysis');app.processEvents()
  w._set_theme('light',palette='B');app.processEvents()
  samples=[]
  for sid in ['C','K','B','C','K','B']:
   t=time.perf_counter();w._set_theme('dark') if sid=='C' else w._set_theme('light',palette=sid);a=time.perf_counter();app.processEvents();b=time.perf_counter()
   w._set_theme('dark') if sid=='C' else w._set_theme('light',palette=sid);c=time.perf_counter();app.processEvents();d=time.perf_counter()
   samples.append({'skin':sid,'handler_ms':(a-t)*1000,'through_events_ms':(b-t)*1000,'repeat_ms':(d-b)*1000})
  row={'scene':scene,'datasets':len(w.output_page.plot_panel.datasets()),'samples':samples}
  for field in ['handler_ms','through_events_ms','repeat_ms']:
   values=[x[field] for x in samples];row[field]={'median':statistics.median(values),'max':max(values)}
  report['scenes'].append(row)
 print(json.dumps(report,ensure_ascii=False),flush=True)
finally:
 report['closed']=_close_self_test_window(w,app,timeout=45);QThreadPool.globalInstance().waitForDone(45000);app.processEvents()
 (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 assert report['closed']
