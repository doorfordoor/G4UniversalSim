"""F1 FE-01..04: relocation, process roles, stale selection, scoped IO and async publication."""
from pathlib import Path
import sys,os,json,shutil,tempfile,time,threading
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from PySide6.QtCore import QTimer
from async_wait import wait_for_idle
from smoke_f1_output_identity import upgrade,publish,reject
from g4usim_gui.output import identity,plot_data
from g4usim_gui.output.provenance import output_evidence,evidence_operation,evidence_key
from g4usim_gui.history.run_history_scanner import scan_package
from g4usim_gui.widgets.run_history_page import RunHistoryPage
from g4usim_gui.widgets.output_page import OutputPage


def spin(predicate,timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        QApplication.processEvents()
        if predicate():return
        time.sleep(.005)
    assert False,'condition timed out'


def main():
    app=QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        work=Path(tmp);a=work/'A';a.mkdir();doc=upgrade(a/'output')
        snapshot={'runName':'relocation','runPackage':{'output_dir':str(a/'output'),'main_ini_path':str(a/'config/main.ini'),'run_macro_path':str(a/'macros/run.mac')}}
        (a/'project_snapshot.json').write_text(json.dumps(snapshot))
        b=work/'B';shutil.copytree(a,b)
        # A is still present and is now a different valid execution; B must never use it.
        doc['provenance']['execution_id']='b'*32
        for row in doc['generated_files']:row['execution_id']='b'*32
        publish(a/'output',doc)
        entry=scan_package(b)
        assert entry.identity_status=='verified' and Path(entry.output_dir)==b/'output'
        assert entry.recorded_output_dir==str(a/'output')
        assert Path(entry.config_path)==b/'config/main.ini' and Path(entry.macro_path)==b/'macros/run.mac'
        history=RunHistoryPage();history._entries=history._filtered=[entry];history.table.setRowCount(1);history.table.setItem(0,0,QTableWidgetItem('B'));history.table.setCurrentCell(0,0);history._show_selected();wait_for_idle(history)
        opened=[];history.openOutputRequested.connect(lambda package,output:opened.append((package,output)));history._emit_open_output()
        assert opened==[(str(b),str(b/'output'))]
        assert json.loads(history.identity_panel.raw.toPlainText())['provenance']['execution_id']=='a'*32
        target=b/'output/event_edep_t0.csv';before=target.read_bytes();oldstat=target.stat();target.write_bytes(before.replace(b'0',b'1',1));os.utime(target,ns=(oldstat.st_atime_ns,oldstat.st_mtime_ns))
        prior_run=entry.status;history._show_selected()
        assert 'identity_status = verified' not in history.details.toPlainText()
        wait_for_idle(history)
        assert entry.identity_status=='tampered' and entry.status==prior_run
        assert 'identity_status = verified' not in history.details.toPlainText() and 'Verified against recorded hashes' not in history.details.toPlainText()
        assert history.identity_panel.outputs.topLevelItemCount()==0
        history.close();history.deleteLater();app.processEvents()
        target.write_bytes(before)
        # Fixed process roles cannot be relabelled as a thread/run with unchanged bytes.
        root=a/'output'
        for name in ('effective_config_configure.json','effective_config_finalization.json'):
            path=root/name;path.write_text('{}');sha,size=identity.hash_file(path)
            doc['generated_files'].append({'path':str(path.resolve()),'schema':'g4usim_effective_config_v1','execution_id':'b'*32,'scope':'process','run_id':None,'thread_id':None,'sha256':sha,'size_bytes':size,'integrity_status':'hashed'})
        publish(root,doc);assert output_evidence(root).status=='verified'
        for name in ('run_summary.txt','effective_config_configure.json','effective_config_finalization.json'):
            for scope,thread in (('run',None),('thread',0)):
                bad=json.loads(json.dumps(doc));row=next(r for r in bad['generated_files'] if r['path'].endswith(name));row.update(scope=scope,run_id=0,thread_id=thread);publish(root,bad);reject(lambda:output_evidence(root))
        publish(root,doc)
        calls=[];real_hash=identity.hash_file
        with patch.object(identity,'hash_file',side_effect=lambda path:(calls.append(str(path)),real_hash(path))[1]):
            assert plot_data.discover(root)
            assert len(calls)==len(doc['generated_files'])-1 and len(set(calls))==len(calls),calls
        calls=[]
        counted_page=OutputPage();counted_page.set_workspace_root(str(ROOT))
        with patch.object(identity,'hash_file',side_effect=lambda path:(calls.append(str(path)),real_hash(path))[1]):
            counted_page.set_output_dir(str(root));wait_for_idle(counted_page)
            assert len(calls)==len(doc['generated_files'])-1 and len(set(calls))==len(calls),calls
        counted_page.close();counted_page.deleteLater();app.processEvents()
        old_evidence=output_evidence(root);target=root/'event_edep_t0.csv';before=target.read_bytes();oldstat=target.stat();target.write_bytes(before.replace(b'0',b'1',1));os.utime(target,ns=(oldstat.st_atime_ns,oldstat.st_mtime_ns))
        reject(lambda:plot_data.discover(root))  # New independent operation must hash anew.
        with evidence_operation({evidence_key(root):old_evidence}):reject(lambda:output_evidence(root,fresh=True))
        target.write_bytes(before)
        # Hold the FIRST verification in a worker: the GUI must keep processing events,
        # a newer directory must publish before that worker completes, and old results drop.
        started=threading.Event();release=threading.Event();finished=threading.Event();blocked=[False]
        def delayed(path):
            if Path(path).parent==root and not blocked[0]:
                blocked[0]=True;started.set();release.wait(10);finished.set()
            return real_hash(path)
        page=OutputPage();page.set_workspace_root(str(ROOT));heartbeat=[]
        with patch.object(identity,'hash_file',side_effect=delayed):
            begin=time.monotonic();page.set_output_dir(str(root));elapsed=time.monotonic()-begin
            QTimer.singleShot(0,lambda:heartbeat.append(True));spin(lambda:started.is_set() and heartbeat)
            assert elapsed < .25 and page.identity_panel.outputs.topLevelItemCount()==0
            page.set_output_dir(str(b/'output'));wait_for_idle(page)
            assert json.loads(page.identity_panel.raw.toPlainText())['provenance']['execution_id']=='a'*32 and not release.is_set()
            release.set();spin(finished.is_set);wait_for_idle(page)
            assert json.loads(page.identity_panel.raw.toPlainText())['provenance']['execution_id']=='a'*32
        page.close();page.deleteLater();app.processEvents()
        started.clear();release.clear();finished.clear();blocked[0]=False
        page=OutputPage()
        with patch.object(identity,'hash_file',side_effect=delayed):
            page.set_output_dir(str(root));spin(started.is_set)
            begin=time.monotonic();page.close();assert time.monotonic()-begin < .25
            page.deleteLater();app.processEvents();release.set();spin(finished.is_set)
        # Hold A's actual hash while a newer directory/plot B completes.
        from g4usim_gui.core import examples
        example=examples.find('shielding_slab')
        selection=OutputPage()
        started.clear();release.clear();finished.clear();blocked[0]=False
        from g4usim_gui.core import evidence_job as job_module
        original_submit=job_module._pool.submit;submitted=[]
        def capture_submit(*args,**kwargs):
            future=original_submit(*args,**kwargs);submitted.append(future);return future
        with patch.object(identity,'hash_file',side_effect=delayed), patch.object(job_module._pool,'submit',side_effect=capture_submit):
            selection.set_output_dir(str(root))
            assert submitted
            late_a=submitted[0]
            assert selection.show_plot('event_edep/r0')
            spin(started.is_set)
            selection.set_output_dir(str(example.output_dir()))
            assert selection.show_plot(example.plot)
            wait_for_idle(selection)
            assert not release.is_set() and not finished.is_set()
            assert Path(selection.plot_panel._output_dir)==example.output_dir()
            assert selection.plot_panel.current_dataset().key==example.plot
            assert selection.plot_panel.current_plot() is not None
            release.set();spin(late_a.done);wait_for_idle(selection)
            assert Path(selection.plot_panel._output_dir)==example.output_dir()
            assert selection.plot_panel.current_dataset().key==example.plot
            assert selection.plot_panel.current_plot() is not None
        selection.refresh();wait_for_idle(selection)
        assert selection.plot_panel.current_dataset().key==example.plot
        # Unknown keys must not leave the previous/default plot on screen.
        assert not selection.show_plot('not-present-ready/r0')
        assert selection.plot_panel.current_dataset() is None and selection.plot_panel.current_plot() is None
        assert 'not-present-ready/r0' in selection.plot_panel.message.text() and 'unavailable' in selection.plot_panel.message.text()
        selection.refresh()
        assert selection.show_plot('not-present-queued/r0')
        wait_for_idle(selection)
        assert selection.plot_panel.current_dataset() is None and selection.plot_panel.current_plot() is None
        assert 'not-present-queued/r0' in selection.plot_panel.message.text() and 'unavailable' in selection.plot_panel.message.text()
        selection.close();selection.deleteLater();app.processEvents()
        # Actual MainWindow accepted/ignored ancestor closes, not direct page.close.
        from g4usim_gui.main_window import MainWindow
        from g4usim_gui.core.evidence_job import EvidenceJob
        from PySide6.QtCore import QProcess
        from PySide6.QtWidgets import QMessageBox
        with patch('g4usim_gui.main_window.save_state'), patch('g4usim_gui.main_window.load_state',return_value={}), patch.object(QMessageBox,'warning',return_value=QMessageBox.Ok):
            window=MainWindow();window.show()
            original_find=window.findChildren
            class StuckProcess:
                def state(self):return QProcess.Running
                def terminate(self):pass
                def kill(self):pass
                def waitForFinished(self,timeout):return False
            stuck=StuckProcess()
            def find(kind,*args):return [stuck] if kind is QProcess else original_find(kind,*args)
            started.clear();release.clear();finished.clear();blocked[0]=False
            with patch.object(identity,'hash_file',side_effect=delayed):
                window.output_page.set_output_dir(str(root));spin(started.is_set)
                window.findChildren=find
                assert not window.close()  # Owned producer cannot stop: close ignored.
                assert not window.output_page._identity_job._closed
                assert window.output_page._identity_job.pending and not window.output_page._identity_job._event.is_set()
                window.findChildren=original_find
                window.output_page.set_output_dir(str(b/'output'));wait_for_idle(window.output_page)
                assert json.loads(window.output_page.identity_panel.raw.toPlainText())['provenance']['execution_id']=='a'*32
                release.set();spin(finished.is_set)
            started.clear();release.clear();finished.clear();blocked[0]=False
            with patch.object(identity,'hash_file',side_effect=delayed):
                window.output_page.set_output_dir(str(root));spin(started.is_set)
                jobs=window.findChildren(EvidenceJob);assert len(jobs)>=6
                begin=time.monotonic();assert window.close();assert time.monotonic()-begin < .5
                assert all(job._closed and not job.pending and job._event.is_set() for job in jobs)
                assert window.output_page.identity_panel.outputs.topLevelItemCount()==0
                release.set();spin(finished.is_set);app.processEvents()
                assert window.output_page.identity_panel.outputs.topLevelItemCount()==0
            window.deleteLater();app.processEvents()
    print('F1 async identity and independent review regressions passed')

if __name__=='__main__':main()
