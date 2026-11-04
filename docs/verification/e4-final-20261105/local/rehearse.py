import os,sys,time,json
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QFileDialog,QInputDialog,QMessageBox
from PySide6.QtCore import QSettings
repo=Path.cwd();sys.path.insert(0,str(repo/'gui'))
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.examples import find
from g4usim_gui.history import run_history_store
base=Path(os.environ.get('E4_RUN_ROOT',str(Path(__file__).resolve().parent/sys.platform)));base.mkdir(parents=True,exist_ok=False)
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(base/'settings'))
run_history_store.STATE_PATH=base/'history.json'
app=QApplication([]);exe=str(Path(sys.argv[1]).resolve());runs=base/'runs';runs.mkdir()
def wait(w):
 end=time.monotonic()+100
 while w.experiment.busy or getattr(w,'_experiment_loading',False):
  app.processEvents();time.sleep(.03);assert time.monotonic()<end,'timeout'
records=[]
w=MainWindow(recovery_root=base/'recovery',offer_recovery=False);w.experiment.completed.connect(records.append)
with patch.object(QMessageBox,'warning',side_effect=lambda *a: (_ for _ in ()).throw(RuntimeError(str(a[2])))):
 assert w.apply_simulation_wizard(replace(find('shielding_slab').spec(),events=100),run_after=False)
 w.project_page.executable.setText(exe);w.project_page.runs_root.setText(str(runs));w.flush_pending_edit()
 w._experiment_action('validate');wait(w);w.generate_package(True);wait(w)
 summaries=list(runs.rglob('run_summary.txt'));assert len(summaries)==1,[(r.get('action'),r.get('status'),r.get('diagnostics')) for r in records]
 s=summaries[0].read_text(encoding='utf-8');assert 'run_0_completed_events = 100' in s and 'status = completed' in s
 with patch.object(QFileDialog,'getExistingDirectory',return_value=str(base)),patch.object(QInputDialog,'getText',return_value=('exported',True)):
  w._experiment_action('export');wait(w)
 bundle=base/'exported';m=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'));assert m['outputs_included'] is False
 w2=MainWindow(recovery_root=base/'reload-recovery',offer_recovery=False)
 with patch.object(QFileDialog,'getExistingDirectory',side_effect=[str(bundle),str(runs)]),patch.object(QFileDialog,'getOpenFileName',return_value=(exe,'')):
  w2._experiment_action('import');wait(w2)
 assert w2.project.executable==exe,(w2.project.executable,exe)
 result={'qt_platform':app.platformName(),'backend':exe,'summary':str(summaries[0]),'events':100,'bundle':str(bundle),'imported_project':w2.project.projectName,'records':[(r.get('action'),r.get('status')) for r in records]}
 (base/'result.json').write_text(json.dumps(result,indent=2));print(result,flush=True)
from PySide6.QtCore import QCoreApplication,QEvent
for window in (w2,w):
 window._choose_unsaved_action=lambda: QMessageBox.Discard
 window.close();wait(window);assert window.experiment.close();window.close();app.processEvents();window.deleteLater()
 QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
