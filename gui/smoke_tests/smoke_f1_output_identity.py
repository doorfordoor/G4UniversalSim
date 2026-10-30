"""F1 strict identity and automatic-consumer regression."""
from pathlib import Path
import sys, json, tempfile, shutil, os, subprocess
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'scripts')]
from test_output_provenance import fixture, check
from g4usim_gui.output.identity import hash_file
from g4usim_gui.output.provenance import output_evidence
from g4usim_gui.output.merge_plan import build_merge_plan


def upgrade(root):
    doc=fixture(root)
    execution='a'*32
    doc['provenance']={'schema':'g4usim_provenance_v1','execution_id':execution,
      'build':{'git_commit':'b'*40,'git_source_state':'clean','source_fingerprint':'c'*64,'compiler_id':'test','compiler_version':'1','configuration':'test','geant4_version':'test'},
      'input_coverage':'project_readers_observed','input_observation':'bytes_read_not_semantic_acceptance',
      'input_exclusions':['geant4_internal_datasets','unobserved_native_command_inputs'],'inputs':[
      {'sequence':1,'path':'missing-original.ini','kind':'ini','role':'main','capture_method':'bytes','status':'recorded','sha256':'d'*64,'size_bytes':12,'reason':''},
      {'sequence':2,'path':'missing-original.ini','kind':'ini','role':'main','capture_method':'native','status':'unobserved','sha256':None,'size_bytes':None,'reason':'native unobserved'}]}
    for row in doc['generated_files']:
        path=root/Path(row['path']).name
        row.update(execution_id=execution,scope='thread' if '_t0' in path.name else 'process',run_id=0 if '_t0' in path.name else None,thread_id=0 if '_t0' in path.name else None)
        if path.name=='run_metadata.json':row.update(sha256=None,size_bytes=None,integrity_status='self_reference_excluded')
        else:
            sha,size=hash_file(path);row.update(sha256=sha,size_bytes=size,integrity_status='hashed')
    publish(root,doc)
    return doc


def publish(root,doc):
    (root/'run_metadata.json').write_text(json.dumps(doc),encoding='utf-8')


def reject(fn):
    try: fn()
    except ValueError: return
    assert False,'invalid F1 accepted'


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from g4usim_gui.widgets.output_page import OutputPage
    from g4usim_gui.output.merge_runner import MergeRunner
    from smoke_output_provenance import StartProbe
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)/'out';doc=upgrade(root)
        doc['runs'].append({'run_id':1,'completed_events':1})
        for prefix in ('effective_config_run_', 'effective_config_final_r'):
            for thread in (0, 1, -1, -2):
                path=root/f'{prefix}1_t{thread}.json';path.write_text('{}')
                sha,size=hash_file(path)
                doc['generated_files'].append({'path':path.resolve().as_posix(),'schema':'g4usim_effective_config_v1','execution_id':'a'*32,'scope':'run' if thread<0 else 'thread','run_id':1,'thread_id':None if thread<0 else thread,'sha256':sha,'size_bytes':size,'integrity_status':'hashed'})
        publish(root,doc)
        assert output_evidence(root).status=='verified'
        for scope,run,thread in [('thread',0,0),('run',1,None),('thread',1,2)]:
            bad=json.loads(json.dumps(doc));row=next(r for r in bad['generated_files'] if r['path'].endswith('effective_config_run_1_t0.json'));row.update(scope=scope,run_id=run,thread_id=thread)
            publish(root,bad);reject(lambda:output_evidence(root))
        bad=json.loads(json.dumps(doc));bad['provenance']['build']['source_fingerprint']='not-a-hash';publish(root,bad);reject(lambda:output_evidence(root))
        publish(root,doc)
        # Existing consumers must accept new extension and preserve values.
        from g4usim_gui.output.dose_summary import read_dose_summaries
        from g4usim_gui.output.fluence_summary import read_fluence_summaries
        from g4usim_gui.output import plot_data
        from g4usim_gui.history.run_history_model import RunHistoryEntry
        from g4usim_gui.history.run_history_scanner import _apply_identity
        read_dose_summaries(root);read_fluence_summaries(root);plot_data.discover(root)
        package=Path(temp)/'package';package.mkdir();shutil.copytree(root,package/'output')
        entry=RunHistoryEntry(str(package),status='failed');_apply_identity(entry,package)
        assert entry.status=='failed' and entry.identity_status=='verified'
        moved=Path(temp)/'moved';shutil.copytree(root,moved)
        removed=moved/'event_edep_t0.csv';saved=removed.read_bytes();removed.unlink()
        reject(lambda:output_evidence(moved))  # Original root still exists; never borrow its file.
        removed.write_bytes(saved)
        shutil.rmtree(root);assert output_evidence(moved).status=='verified'
        root=moved
        page=OutputPage();page.set_workspace_root(str(ROOT));page.set_output_dir(str(root))
        assert 'identity_status = verified' in page.summary_text.toPlainText()
        panel=page.identity_panel
        assert panel.build.topLevelItemCount() >= 8 and panel.inputs.topLevelItemCount()==2
        assert panel.outputs.topLevelItemCount()==len(doc['generated_files'])
        assert panel.raw.isHidden()
        from g4usim_gui.core.i18n import set_application_language
        set_application_language(app,'zh_CN');panel.refresh_language()
        assert panel.inputs.headerItem().text(0)=='读取序号'
        assert '历史实际读取字节' in panel.note.text()
        panel.inputs.topLevelItem(0).setSelected(True);panel.tabs.setCurrentWidget(panel.inputs);panel.copy_button.click()
        assert 'd'*64 in app.clipboard().text() and 'missing-original.ini' in app.clipboard().text()
        from g4usim_gui.widgets.run_history_page import RunHistoryPage
        from PySide6.QtWidgets import QTableWidgetItem
        history=RunHistoryPage();history._filtered=[entry];history.table.setRowCount(1);history.table.setItem(0,0,QTableWidgetItem('test'));history.table.setCurrentCell(0,0);history._show_selected()
        assert 'failed' in history.identity_panel.run_label.text() or '失败' in history.identity_panel.run_label.text()
        assert history.identity_panel.outputs.topLevelItemCount()==len(doc['generated_files'])
        history.close();history.deleteLater();app.processEvents()
        set_application_language(app,'en');panel.refresh_language()
        task=next(t for t in build_merge_plan(str(root),str(ROOT)).tasks if t.kind=='event_edep')
        data=root/'event_edep_t0.csv';before=data.read_bytes();stat=data.stat()
        data.write_bytes(before.replace(b'0',b'1',1));os.utime(data,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        assert data.stat().st_size==len(before)
        runner=MergeRunner();runner._process=probe=StartProbe();errors=[]
        runner.errorOccurred.connect(errors.append);runner.run_task(task,Path(temp)/"logs")
        assert errors and probe.starts==0 and "bytes mismatch" in errors[0]
        page.refresh();assert "identity_status = tampered" in page.summary_text.toPlainText()
        assert not page.plot_panel.datasets()
        assert panel.build.topLevelItemCount()==panel.inputs.topLevelItemCount()==panel.outputs.topLevelItemCount()==0
        assert panel.raw.toPlainText()==""
        assert "completed" in panel.run_label.text() or "完成" in panel.run_label.text()
        page.close();page.deleteLater();app.processEvents()
        for consume in (lambda:output_evidence(root),lambda:read_dose_summaries(root),lambda:read_fluence_summaries(root),lambda:plot_data.discover(root)):
            reject(consume)
        assert not any(t.available for t in build_merge_plan(str(root),str(ROOT)).tasks)
        for extension in ('dose_json','fluence_json'):
            target=Path(temp)/(extension+'.json')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/run_output_extension.py'),'--run',extension,'--input-dir',str(root),'--output',str(target)],capture_output=True,text=True)
            assert result.returncode != 0 and not target.exists()
        from merge_outputs import resolve_files
        reject(lambda:resolve_files(str(root),'event_edep_t*.csv',[]))
        data.write_bytes(before)
        assert output_evidence(root).status=='verified'
        for key,value in [('schema','future'),('execution_id','BAD'),('inputs',[{'sequence':True}])]:
            bad=json.loads(json.dumps(doc));bad['provenance'][key]=value;publish(root,bad);reject(lambda:output_evidence(root))
        for key,value in [('execution_id','b'*32),('run_id',3),('thread_id',True),('sha256','bad'),('integrity_status','self_reference_excluded'),('integrity_status','unavailable')]:
            bad=json.loads(json.dumps(doc));row=next(r for r in bad['generated_files'] if '_t0' in r['path']);row[key]=value
            publish(root,bad);reject(lambda:output_evidence(root))
        publish(root,doc)
        raw=(root/'run_metadata.json').read_text();(root/'run_metadata.json').write_text(raw[:-1]+',"provenance":{}}')
        reject(lambda:output_evidence(root))
        for marker,value in [('output_provenance_schema','g4usim_provenance_v1'),('execution_id','a'*32)]:
            bad=json.loads(json.dumps(doc));bad['values']={marker:value};publish(root,bad)
            assert output_evidence(root).status=='verified'
            del bad['provenance'];publish(root,bad);reject(lambda:output_evidence(root))
        for marker,value in [('output_provenance_schema','future'),('execution_id','b'*32),('output_provenance_schema',None),('execution_id',True)]:
            bad=json.loads(json.dumps(doc));bad['values']={marker:value};publish(root,bad);reject(lambda:output_evidence(root))
        bad=json.loads(json.dumps(doc));del bad['provenance'];publish(root,bad);reject(lambda:output_evidence(root))
        for marker in ('execution_id','scope','run_id','thread_id','sha256','size_bytes','integrity_status'):
            bad=json.loads(json.dumps(doc));del bad['provenance'];bad['generated_files']=[{'path':row['path'],'schema':row['schema']} for row in bad['generated_files']];bad['generated_files'][0][marker]=None
            publish(root,bad);reject(lambda:output_evidence(root))
        del doc['provenance'];doc['generated_files']=[{'path':row['path'],'schema':row['schema']} for row in doc['generated_files']];publish(root,doc)
        assert output_evidence(root).status=='registered_manifest'
        assert output_evidence(root).warnings
    print('F1 identity consumers passed')

if __name__=='__main__':main()
