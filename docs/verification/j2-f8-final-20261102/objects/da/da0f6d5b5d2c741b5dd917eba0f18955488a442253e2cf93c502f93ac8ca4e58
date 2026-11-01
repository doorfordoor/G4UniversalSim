import os,sys,json,hashlib,dataclasses,copy
from pathlib import Path
ROOT=Path.cwd(); OUT=ROOT/'out/collab/f8-scan-hash'
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_SCALE_FACTOR']='1.25'
os.environ['G4USIM_RECOVERY_DIR']=str(OUT/'recovery')
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtCore import QSettings,Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from g4usim_gui.history import run_history_store
run_history_store.STATE_PATH=OUT/'history.json'
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(OUT/('settings-'+sys.argv[1])))
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint,snapshot_to_dict
from smoke_k1_workflow import close_window
app=QApplication([]);app.setApplicationName('J2 F8 Native Acceptance');app.setOrganizationName('G4UniversalSimAcceptance');app.setStyle('Fusion');apply_theme(app,'light');set_application_language(app,'zh_CN')
identity=json.loads((ROOT/'out/verification/j2-f8-56b689f/native125/identity.json').read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,default=str).encode()).hexdigest()
def diff(a,b,path=''):
 if type(a)!=type(b):return [{'path':path,'before':a,'after':b}]
 if isinstance(a,dict):return sum((diff(a.get(k),b.get(k),path+'.'+k) for k in sorted(a.keys()|b.keys())),[])
 if isinstance(a,list):
  if len(a)!=len(b):return [{'path':path,'before':a,'after':b}]
  return sum((diff(x,y,path+f'[{i}]') for i,(x,y) in enumerate(zip(a,b))),[])
 return [] if a==b else [{'path':path,'before':a,'after':b}]
def pump():
 for _ in range(8):app.processEvents()
def raw(w):return copy.deepcopy(dataclasses.asdict(w.project))
results=[]
for trial in [sys.argv[1]]:
 w=MainWindow(recovery_root=OUT/('recovery-'+trial),offer_recovery=False)
 p=w.project;p.executable=identity['exe'];p.pathSettings.executable=p.executable;p.runsRoot=str(ROOT/'out/verification/j2-f8-56b689f/native125/runs');p.pathSettings.runs_root=p.runsRoot;p.outputDir=str(ROOT/'out/verification/j2-f8-56b689f/native125/runs/demo/output');w._set_project(p);w._reset_edit_history();w.resize(1200,800)
 w.config_builder_page._backend_timer.stop();w.config_builder_page.schedule_backend_geometry=lambda*a,**k:None
 w.show();pump()
 try:
  initial=raw(w); history_before={'can_undo':w._edit_session.can_undo,'can_redo':w._edit_session.can_redo,'is_modified':w._edit_session.is_modified}
  # F5 capture is on a deep project copy. Instrument separately to detect side effects.
  snap_before=w.capture_workspace(); captured=raw(w)
  stages=[]
  provider=w.scan_page._provider
  def traced_provider():
   last=raw(w)
   for name,call in [('finish_history_merge',w._finish_history_merge),('collect_project',w._update_project_from_page_without_preview),('update_project',lambda:w.config_builder_page.update_project(w.project)),('validate_current',lambda:w.config_builder_page.validate_current(w.project))]:
    call();now=raw(w);stages.append({'operation':name,'diff':diff(last,now)});last=now
   return provider()
  if trial=='snapshot_first':w.scan_page._provider=traced_provider
  QTest.keyClick(w,Qt.Key_9,Qt.ControlModifier|Qt.AltModifier);pump()
  after=raw(w);snap_after=w.capture_workspace();after_capture=raw(w)
  history_after={'can_undo':w._edit_session.can_undo,'can_redo':w._edit_session.can_redo,'is_modified':w._edit_session.is_modified}
  first_after=copy.deepcopy(after)
  w.focus_page(0);pump();w.focus_page(8);pump();repeat=raw(w)
  row={'trial':trial,'page':w.page_stack.currentIndex(),'project_sha_before':digest(initial),'project_sha_after':digest(after),'raw_diff':diff(initial,after),'capture_before_side_effects':diff(initial,captured),'capture_after_side_effects':diff(after,after_capture),'snapshot_before':snapshot_fingerprint(snap_before),'snapshot_after':snapshot_fingerprint(snap_after),'snapshot_diff':diff(snapshot_to_dict(snap_before),snapshot_to_dict(snap_after)),'history_before':history_before,'history_after':history_after,'repeat_entry_diff':diff(first_after,repeat),'stages':stages}
  results.append(row)
  for name,payload in [('project-before',initial),('project-after',after),('snapshot-before',snapshot_to_dict(snap_before)),('snapshot-after',snapshot_to_dict(snap_after))]:(OUT/(trial+'-'+name+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 finally:close_window(app,w)
source_changed={}
for path,sha in identity['gui_files'].items():
 actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
 if actual!=sha:source_changed[path]={'native':sha,'current':actual}
report={'scope':'read-only product; independent offscreen process; no backend launched; no native UI interaction','dpr':1.25,'native_source_difference':source_changed,'results':results}
(OUT/(sys.argv[1]+'-results.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print('results', OUT/(sys.argv[1]+'-results.json'))
