"""13-state offscreen interactions plus fixture-generation/lifetime controls."""
import faulthandler
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

ROOT=Path(__file__).resolve().parents[2]
out=Path(tempfile.mkdtemp(prefix='f4-v2-full-eventloop-',dir=ROOT/'out/collab'))
print('ARTIFACTS',out,flush=True)
os.environ['QT_QPA_PLATFORM']='offscreen'
faulthandler.enable(all_threads=True)
path=ROOT/'out/collab/f4-visible-host-v2.py'
identity=json.loads((ROOT/'out/verification/f4-visible-096f4b3/identity.json').read_text(encoding='utf-8'))
sys.argv=[str(path),'--executable',identity['executable'],'--artifact-dir',str(out),'--precheck']
ns={'__file__':str(path),'__name__':'f4_v2_full_test'}
exec(compile(path.read_text(encoding='utf-8').split('\nhost = Host()\n',1)[0],str(path),'exec'),ns)
app,Host,QTimer,CASES=ns['app'],ns['Host'],ns['QTimer'],ns['CASES']
from PySide6 import __version__
from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWizard
host=Host()
results=[]
failures=[]
index=0
waits=0
before=''
generation_check={}

def safe(function):
    def call():
        try:
            function()
        except Exception:
            failures.append(traceback.format_exc())
            traceback.print_exc()
            app.exit(1)
    return call
def later(delay,function):
    QTimer.singleShot(delay,safe(function))
def begin():
    global waits
    key=CASES[index][0]
    print('PREPARE',key,flush=True)
    waits=0
    host.prepare(key)
    later(25,act)
def act():
    global waits,before
    key=CASES[index][0]
    if not host.ready:
        waits+=1
        assert waits<300,'fixture readiness timeout'
        later(50,act)
        return
    panel=host.panel
    assert panel.records and panel.selected_diagnostic() is not None
    before=ns['normalized_hash'](host.business())
    if key in ('source','history'):
        assert panel.source_button.isEnabled()
        QTest.mouseClick(panel.source_button,Qt.LeftButton)
    elif key=='stale':
        assert panel.stale and not panel.locate_button.isEnabled()
    elif key=='backend':
        receipt=host._inspect_receipts[-1]
        assert receipt['exit_code']!=0 and receipt['exit_status']==0
        assert not receipt['runner_running'] and not receipt['run_summary_files']
        assert 'conflicts with an explicit CLI lock' in receipt['stderr']
        assert not panel.locate_button.isEnabled() and not panel.source_button.isEnabled()
        assert panel.records[0].raw_message==receipt['stderr']
    elif key=='geometry':
        panel.table.scrollToItem(panel.table.currentItem())
        point=panel.table.visualItemRect(panel.table.currentItem()).center()
        QTest.mouseClick(panel.table.viewport(),Qt.LeftButton,pos=point)
        QTest.mouseDClick(panel.table.viewport(),Qt.LeftButton,pos=point)
    elif key=='material':
        panel.table.setFocus()
        QTest.keyClick(panel.table,Qt.Key_Return)
    else:
        assert panel.locate_button.isEnabled()
        QTest.mouseClick(panel.locate_button,Qt.LeftButton)
    later(160,check)
def check():
    global index
    key=CASES[index][0]
    after=ns['normalized_hash'](host.business())
    assert after==before,(key,'observer/product interaction changed business state')
    if key not in ('source','history','stale','backend'):
        assert host.view()['highlighted'],(key,'navigation did not highlight any target')
    if key=='geometry':
        assert (host.window.config_builder_page.geometry_table.currentRow(),
                host.window.config_builder_page.geometry_table.currentColumn())==(2,6)
    if key=='material':
        assert host.window.config_builder_page.materials_table.currentRow()==1
    if key=='layer':
        assert host.window.config_builder_page._selected_layer_row==1
    if key=='boolean':
        assert (host.window.config_builder_page.boolean_table.currentRow(),
                host.window.config_builder_page.boolean_table.currentColumn())==(0,3)
    if key in ('source','history'):
        assert host.panel.source_view.isVisible() and 'mystery' in host.panel.source_view.toPlainText()
    if key=='wizard':
        assert host.wizard.currentId()==1
        QTest.mouseClick(host.wizard.button(QWizard.CancelButton),Qt.LeftButton)
    results.append({'case':key,'business_before':before,'business_after':after,
        'navigation_executed':key not in ('stale','backend'),'visual_observation':False})
    print('PASS',key,flush=True)
    index+=1
    if index<len(CASES):
        later(100,begin)
    else:
        later(100,generation_start)
def generation_start():
    host.prepare('wizard')
    QTest.mouseClick(host.wizard.run_page.diagnostics_panel.locate_button,Qt.LeftButton)
    generation_check['old_generation']=host._generation
    # Replace before the observer's 80 ms receipt. No stale after record may be
    # attached to the new scan fixture or keep its input dispatch locked.
    host.prepare('scan')
    generation_check['new_generation']=host._generation
    later(160,generation_verify)
def generation_verify():
    records=[json.loads(line) for line in (out/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    discarded=[r for r in records if r['kind']=='product_input_discarded' and
               r['originating_generation']==generation_check['old_generation']]
    assert len(discarded)==1
    assert generation_check['old_generation']<generation_check['new_generation']
    assert host.ready and not host._in_dispatch
    QTest.mouseClick(host.panel.locate_button,Qt.LeftButton)
    later(160,generation_after)
def generation_after():
    records=[json.loads(line) for line in (out/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert records[-1]['kind']=='product_input_after' and records[-1]['case']=='scan'
    assert records[-1]['model_unchanged'] is True
    generation_check['passed']=True
    # Wait past the product highlight timeout without disabling its timer.
    later(4000,finish)
def finish():
    assert len(results)==13
    (out/'full-interactions.json').write_text(json.dumps({'results':results,'generation_check':generation_check,
        'pyside':__version__,'visual_acceptance':False},ensure_ascii=False,indent=2),encoding='utf-8')
    host.window.close()
later(0,begin)
QTimer.singleShot(60000,safe(lambda: (_ for _ in ()).throw(AssertionError('event loop timeout'))))
code=app.exec()
app.removeEventFilter(host)
host.ready=False
host._generation+=1
host.window.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
app.processEvents()
(out/'exit.json').write_text(json.dumps({'event_loop_exit':code,'failure_count':len(failures),
    'failures':failures,'states_completed':len(results),'main_close_requested':host.closed,
    'generation_check':generation_check,'pyside':__version__,'host_sha256':ns['IDENTITY']['host_sha256'],
    'product_sha':ns['IDENTITY']['gui_head'],'visual_acceptance':False},indent=2),encoding='utf-8')
print('NATURAL EXIT',code,'states',len(results),'generation',generation_check,flush=True)
raise SystemExit(code)
