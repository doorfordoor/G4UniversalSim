"""Owned application programmatic Qt acceptance; native visibility is root evidence."""
import os, sys, json, hashlib, copy, traceback, time
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
PREP=BASE.parent/'e6-visible-acceptance-a779634'
EXE=ROOT/'out/build-e6/Release/G4UniversalSim.exe'
os.environ['QT_QPA_PLATFORM']='windows'
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtCore import QTimer,QProcess,QSettings
from PySide6.QtWidgets import QApplication,QWidget,QMessageBox
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.widgets.migration_dialog import MigrationDialog
from g4usim_gui.window import project as project_window
from smoke_project_import_projection import snapshot

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
manifest=json.loads((PREP/'preparation-manifest.json').read_text(encoding='utf-8'))
sources=manifest.get('source_files',manifest.get('files',[]))
# All explicitly recorded path/hash pairs, regardless of manifest grouping.
def verify(node):
    if isinstance(node,dict):
        if 'path' in node and 'sha256' in node: assert sha(ROOT/node['path'])==node['sha256'],node['path']
        for v in node.values(): verify(v)
    elif isinstance(node,list):
        for v in node: verify(v)
verify(manifest)
assert sha(EXE)=='09dd7521be81f21c1c2a6f1b751eb1c6b171c70c4b206814a821b3e8b73aa3a5'
index=json.loads((PREP/'resource-index.json').read_text(encoding='utf-8'))
baseline={str(p):sha(p) for p in (PREP/'resources').rglob('*') if p.is_file()}
app=QApplication([])
app.setOrganizationName('G4USimAcceptanceIsolated')
app.setApplicationName('E6Visible20261030')
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(BASE/'settings'))
run_history_store.STATE_PATH=BASE/'history-state.json'
set_application_language(app,'zh_CN')
w=MainWindow()
for t in w.findChildren(QTimer): t.stop()
w.setWindowTitle('E6 Windows acceptance a779634')
w.resize(1180,820);w.show()
dialog=MigrationDialog(w,open_project=w._load_project_path)
dialog.source_path.setText(str(PREP/'resources/migration/legacy-v5.json'))
assert dialog.preview(),dialog.status.text()
dialog.show()
receipts=[]
def checkpoint(stage,**extra):
    receipt={'stage':stage,'time':time.time(),'pid':os.getpid(),'title':w.windowTitle(),'programmatic_qt_test':True,'native_visibility':'root must observe independently',**extra}
    receipts.append(receipt);save(BASE/'receipts.json',receipts);save(BASE/'checkpoint.json',receipt)
checkpoint('migration-preview',version=dialog.version_label.text(),boundary=dialog.boundary_label.text())
def unchanged(): assert all(sha(p)==digest for p,digest in baseline.items())
def current():
    candidate=copy.deepcopy(w._default_project());candidate.executable=str(EXE);candidate.runsRoot=str(BASE/'runs')
    candidate.threads=candidate.runSettings.threads=7;candidate.seed='999';candidate.runSettings.seed=999
    candidate.runName=candidate.runSettings.run_name='unrelated_current_run';w._set_project(candidate)
    for t in w.findChildren(QTimer): t.stop()
def duplicate(case,real=False):
    current();old=snapshot(w,w.findChildren(QWidget));boxes=[];starts=[];inspections=[]
    def box(_p,title,message,*a,**kw): boxes.append([title,message])
    with patch.object(project_window.QMessageBox,'warning',side_effect=box):
        if real:
            original=w.runner.start
            def start(project,command):
                checkpoint('real-run-started',command=command,cwd=project.workspaceRoot,output=project.outputDir)
                return original(project,command)
            w.runner.start=start
            w.duplicate_history_package(case['package'],run_after=True)
            return
        with patch.object(w._macro_inspection,'start',side_effect=lambda: inspections.append(w._macro_inspection.arguments())),patch.object(w.runner,'start',side_effect=lambda p,c: starts.append(c)):
            w.duplicate_history_package(case['package'],run_after=True)
            if case['case']=='projection1025':
                assert len(boxes)==1 and '1025' in boxes[0][1],boxes
                assert snapshot(w,w.findChildren(QWidget))==old
                assert not inspections and not starts
            else:
                assert not boxes and len(inspections)==1,boxes
                plan={'schema':'G4UniversalSimRunPlan','version':1,'macro_plan':{'commands':[{'file':w.project.macroPath,'line':1,'category':'beam_on','text':'/run/beamOn 2'}]},'initial_configuration':[],'macro_execution_planned':True}
                with patch.object(w._macro_inspection,'readAllStandardOutput',return_value=json.dumps(plan).encode()),patch.object(w._macro_inspection,'readAllStandardError',return_value=b''):
                    w._on_macro_inspection_finished(0,QProcess.NormalExit)
                assert len(starts)==1
                cmd=starts[0]
                def arg(key): return cmd[cmd.index(key)+1] if key in cmd else None
                assert arg('--threads')==str(case['threads'])
                assert arg('--seed')==(None if case['seed'] is None else str(case['seed']))
                assert arg('--run-name')==case['run_name']
                assert cmd[0]==str(EXE)
    unchanged();checkpoint('duplicate-'+case['case'],command=starts,inspection=inspections,boxes=boxes,scope='synthetic Inspect; intercepted final Run command; no simulation')
    if boxes:
        msg=QMessageBox(QMessageBox.Warning,boxes[0][0],boxes[0][1],QMessageBox.Ok,w);msg.setAttribute(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.WA_DeleteOnClose);msg.show()
def advance(command):
    if command=='migration':
        before=w.project
        target=BASE/'migrated-v6.json';assert dialog.write_copy(target);assert w.project is before
        results=[]
        for target in ('legacy-v5.json','occupied-target.json','source-hardlink.json'):
            assert not dialog.write_copy(PREP/'resources/migration'/target);results.append(dialog.status.text())
        for target in ('future-version.json','malformed.json'):
            dialog.source_path.setText(str(PREP/'resources/migration'/target));assert not dialog.preview();assert not dialog.write_button.isEnabled()
        unchanged();checkpoint('migration-refusals',results=results,diagnostics=dialog.diagnostics.toPlainText())
    elif command=='snapshot':
        dialog.reject();assert w._load_project_path(index['snapshot']['snapshot'],snapshot=True)
        p=w.config_builder_page
        assert p.material_document.rows[0].density=='2.8 g/cm3'
        assert p.geometry_document.volumes[1].size.replace(' ','')=='3mm,4mm,5mm'
        assert w.project.runSettings.beam_on==2 and not w.project.configPath
        assert w._save_project_to(BASE/'restored-project.json')
        checkpoint('snapshot-restored',notes=p.validation_text.toPlainText(),materials=p.materials_config.text(),geometry=p.geometry_config.text())
    elif command=='generate':
        assert w._load_project_path(str(BASE/'restored-project.json'));w.generate_package(run_after_generate=False)
        assert w._generated_package_dir
        new=Path(w._generated_package_dir);old=Path(index['snapshot']['package'])
        for rel in ('config/materials/material.ini','config/geometry/geometry.ini'): assert (new/rel).read_bytes()==(old/rel).read_bytes()
        unchanged();checkpoint('snapshot-regenerated',package=str(new))
    elif command.startswith('duplicate:'): duplicate(next(c for c in index['duplicate_cases'] if c['case']==command.split(':')[1]))
    elif command=='real': duplicate(index['duplicate_cases'][0],real=True)
    elif command=='result':
        assert not w.runner.is_running()
        result=w.runner.last_result;assert result is not None
        unchanged();checkpoint('real-run-result',result=vars(result),output=w.project.outputDir)
    elif command=='close': unchanged();checkpoint('closed');w.close();app.quit()
    else: raise ValueError(command)
def tick():
    path=BASE/'command.json'
    if not path.exists(): return
    command=json.loads(path.read_text(encoding='utf-8-sig'));path.unlink()
    try: advance(command['command'])
    except Exception: checkpoint('ERROR',command=command,traceback=traceback.format_exc())
timer=QTimer();timer.timeout.connect(tick);timer.start(300)
sys.exit(app.exec())
