"""Real product import error modals; root owns native observation/dismissal."""
import sys,os,json,time,copy,hashlib,traceback
from pathlib import Path
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[3]
PREP=BASE.parent.parent/'e6-visible-acceptance-a779634'
os.environ['QT_QPA_PLATFORM']='windows'
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
sys.stdout=open(BASE/'stdout.log','w',encoding='utf-8',buffering=1)
sys.stderr=open(BASE/'stderr.log','w',encoding='utf-8',buffering=1)
from PySide6.QtCore import QTimer,QSettings
from PySide6.QtWidgets import QApplication,QWidget
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from smoke_project_import_projection import snapshot
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
baseline={str(p):sha(p) for p in (PREP/'resources').rglob('*') if p.is_file()}
index=json.loads((PREP/'resource-index.json').read_text(encoding='utf-8'))
app=QApplication([]);app.setOrganizationName('G4USimAcceptanceIsolated');app.setApplicationName('E6ImportSupplement')
QSettings.setDefaultFormat(QSettings.IniFormat);QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(BASE/'settings'))
run_history_store.STATE_PATH=BASE/'history-state.json'
set_application_language(app,'zh_CN')
w=MainWindow()
for t in w.findChildren(QTimer):t.stop()
c=copy.deepcopy(w._default_project());c.threads=c.runSettings.threads=7;c.seed='999';c.runSettings.seed=999
c.runsRoot=str(BASE/'runs');c.runName=c.runSettings.run_name='unrelated_current_run';w._set_project(c)
for t in w.findChildren(QTimer):t.stop()
w.setWindowTitle('E6 import acceptance a779634');w.resize(1180,820);w.show()
receipts=[]
def checkpoint(stage,**extra):
    r={'stage':stage,'pid':os.getpid(),'time':time.time(),'title':w.windowTitle(),'real_product_modal':True,**extra};receipts.append(r)
    for name,data in [('checkpoint.json',r),('receipts.json',receipts)]: (BASE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
checkpoint('ready')
busy=False
def tick():
    global busy
    p=BASE/'command.json'
    if busy or not p.exists():return
    busy=True
    try:
        cmd=json.loads(p.read_text(encoding='utf-8-sig'))['command'];p.unlink()
        if cmd=='close':
            assert all(sha(p)==s for p,s in baseline.items());checkpoint('closed');w.close();app.quit();return
        assert cmd in ('open','recent','snapshot','envelope')
        widgets=w.findChildren(QWidget);before=snapshot(w,widgets)
        source=index['snapshot']['snapshot'] if cmd=='envelope' else str(PREP/'resources/migration/projection-overflow.json')
        checkpoint('modal-pending-'+cmd,path=source,entry='_load_project_path',flags={'snapshot':cmd=='snapshot','recent':cmd=='recent'})
        result=w._load_project_path(source,snapshot=cmd=='snapshot',recent=cmd=='recent')
        assert result is False
        assert snapshot(w,widgets)==before,'import changed project/path/widgets/package state'
        assert all(sha(p)==s for p,s in baseline.items())
        checkpoint('passed-'+cmd,returned=result,state_unchanged=True,resources_unchanged=True)
    except Exception:checkpoint('ERROR',traceback=traceback.format_exc())
    finally:busy=False
timer=QTimer();timer.timeout.connect(tick);timer.start(300)
exit_code=app.exec()
(BASE/'gui-exit.json').write_text(json.dumps({'app_exec_exit_code':exit_code,'time':time.time()}),encoding='utf-8')
sys.exit(exit_code)
