"""Frozen F1 visible host: identity receipts only; no desktop automation or close-file control."""
from pathlib import Path
import argparse, json, os, sys, tempfile, shutil, hashlib
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests'),str(ROOT/'scripts')]
import run_m0_tests as frozen_runner

def load_identity():
    return {'captured_utc':datetime.now(timezone.utc).isoformat(),'git_head':frozen_runner.git_value('rev-parse','HEAD'),'source_fingerprint':frozen_runner.workspace_source_fingerprint(),'tests_content_fingerprint':frozen_runner.tests_content_fingerprint(),'git_dirty':bool(frozen_runner.git_value('status','--porcelain')),'case_count':len(frozen_runner.CASES),'host_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'host_path':str(Path(__file__).resolve()),'fingerprint_method':'unchanged scripts/run_m0_tests.py functions'}

IDENTITY_BEFORE_IMPORT=load_identity()

from PySide6.QtWidgets import QApplication,QMainWindow,QTabWidget,QWidget,QVBoxLayout,QLabel
from PySide6.QtCore import QTimer
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.output.identity import hash_file
from g4usim_gui.core.run_result import summary_fingerprint
from g4usim_gui.widgets.output_page import OutputPage
from g4usim_gui.widgets.run_history_page import RunHistoryPage
from smoke_f1_output_identity import upgrade,publish

IDENTITY_AFTER_IMPORT=load_identity()


class ReadOnlyOutputPage(OutputPage):
    """Host-only read-only observation: production verification is unchanged."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.plot_panel is not None:
            original=self.plot_panel._update_buttons
            def read_only_plot_buttons():
                original()
                self.plot_panel.export_png_button.setEnabled(False)
                self.plot_panel.export_csv_button.setEnabled(False)
            self.plot_panel._update_buttons=read_only_plot_buttons
            read_only_plot_buttons()
    def _update_merge_buttons(self,running):
        super()._update_merge_buttons(running)
        for name in ('run_selected_merge_button','run_all_merge_button'):
            button=getattr(self,name,None)
            if button:button.setEnabled(False)
    def _update_extension_buttons(self):
        super()._update_extension_buttons()
        for name in ('export_dose_button','export_fluence_button'):
            button=getattr(self,name,None)
            if button:button.setEnabled(False)
    def run_output_extension(self,*args,**kwargs):return False
    def _run_merge_tasks(self,*args,**kwargs):return None


class ReadOnlyHistoryPage(RunHistoryPage):
    def _update_action_buttons(self):
        super()._update_action_buttons()
        for name in ('load_snapshot_button','duplicate_button','duplicate_run_button'):
            button=getattr(self,name,None)
            if button:button.setEnabled(False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real-dir',action='append',default=[]);parser.add_argument('--exit-after',type=int,default=0);parser.add_argument('--expected-head');parser.add_argument('--expected-source-fingerprint');parser.add_argument('--expected-test-fingerprint');parser.add_argument('--freeze-manifest',type=Path);parser.add_argument('--state-file',default=str(ROOT/'out/collab/f1-visible-final-state.json')) ;args=parser.parse_args()
    if not args.real_dir:parser.error('Final host requires an explicitly selected frozen real auto output directory; no backend is launched')
    expected={}
    if args.freeze_manifest:
        manifest=json.loads(args.freeze_manifest.read_text(encoding='utf-8'))
        expected={'git_head':manifest.get('head_sha',manifest.get('git_head')),'source_fingerprint':manifest.get('source_fingerprint'),'tests_content_fingerprint':manifest.get('tests_content_fingerprint')}
    for key,value in (('git_head',args.expected_head),('source_fingerprint',args.expected_source_fingerprint),('tests_content_fingerprint',args.expected_test_fingerprint)):
        if value is not None:expected[key]=value
    for key,value in expected.items():
        if value is not None and IDENTITY_AFTER_IMPORT[key]!=value:raise RuntimeError('Final host code identity differs from expected '+key)
    if any(IDENTITY_BEFORE_IMPORT[key]!=IDENTITY_AFTER_IMPORT[key] for key in ('git_head','source_fingerprint','tests_content_fingerprint')):raise RuntimeError('Code identity changed while the final host was importing')
    for value in args.real_dir:
        if not (Path(value)/'run_metadata.json').is_file():parser.error('Real output directory has no run_metadata.json: '+value)
    state_path=Path(args.state_file).resolve()
    if state_path.exists():raise FileExistsError('Final host state already exists; choose a new receipt path')
    def save_receipt(value,initial=False):
        raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        state_path.parent.mkdir(parents=True,exist_ok=True)
        if initial:
            with state_path.open('xb') as stream:stream.write(raw)
        else:
            temporary=state_path.with_name(state_path.name+'.tmp-'+str(os.getpid()))
            with temporary.open('xb') as stream:stream.write(raw)
            os.replace(temporary,state_path)
    base=ROOT/'out/collab';base.mkdir(exist_ok=True)
    fixtures=Path(tempfile.mkdtemp(prefix='f1-final-visible-',dir=base))
    app=QApplication.instance() or QApplication([]);set_application_language(app,'zh_CN')
    host=QMainWindow();host.setWindowTitle('G4UniversalSim F1 冻结实窗验收 '+IDENTITY_AFTER_IMPORT['git_head'][:12]+'（观察待完成）');host.resize(1500,960)
    tabs=QTabWidget();center=QWidget();layout=QVBoxLayout(center);identity_label=QLabel('载入代码身份：'+IDENTITY_AFTER_IMPORT['git_head']+'\nsource='+IDENTITY_AFTER_IMPORT['source_fingerprint']+'  tests='+IDENTITY_AFTER_IMPORT['tests_content_fingerprint']);identity_label.setWordWrap(True);layout.addWidget(identity_label);layout.addWidget(tabs,1);host.setCentralWidget(center);pages=[];directories={}
    def add_output(label,path,synthetic):
        wrap=QWidget();layout=QVBoxLayout(wrap)
        note=QLabel(('合成展示用例：仅用于界面状态检查，不是实际模拟或物理验证。' if synthetic else '真实F1运行目录：身份一致性与运行状态分别展示，不代表物理验证。')+'\n'+str(path));note.setWordWrap(True);layout.addWidget(note)
        page=ReadOnlyOutputPage();page.set_workspace_root(str(ROOT));page.set_output_dir(str(path));layout.addWidget(page,1);tabs.addTab(wrap,label);pages.append(page);directories[label]=str(path)
    for state,label in [('verified','合成：字节一致'),('failed','合成：运行失败／字节一致'),('tampered','合成：字节不一致'),('legacy','合成：旧v1'),('missing','合成：缺登记文件')]:
        package=fixtures/state;package.mkdir();(package/'logs').mkdir();path=package/'output';doc=upgrade(path)
        failed=state=='failed';code=1 if failed else 0
        summary='\n'.join(['status = '+('failed' if failed else 'completed'),f'program_exit_code = {code}','summary_write_status = completed','run_count = 1','planned_event_count = 1','actual_completed_event_count = 1','run_0_planned_events = 1','run_0_completed_events = 1','macro_execution_status = completed','simulation_executed = true'])+'\n'
        (path/'run_summary.txt').write_bytes(summary.encode())
        row=next(r for r in doc['generated_files'] if r['path'].endswith('run_summary.txt'));sha,size=hash_file(path/'run_summary.txt');row.update(sha256=sha,size_bytes=size)
        if state=='legacy':
            del doc['provenance'];doc['generated_files']=[{'path':r['path'],'schema':r['schema']} for r in doc['generated_files']]
        publish(path,doc)
        (package/'project_snapshot.json').write_text(json.dumps({'runName':label,'runSettings':{'threads':1,'beam_on':1}}),encoding='utf-8')
        (package/'run_status.json').write_text(json.dumps({'state':'failed' if failed else 'success','exitCode':code,'resultVersion':1,'summaryFresh':True,'summaryFingerprint':summary_fingerprint(path/'run_summary.txt')}),encoding='utf-8')
        if state=='tampered':
            target=path/'event_edep_t0.csv';target.write_bytes(target.read_bytes().replace(b'0',b'1',1))
        if state=='missing':(path/'event_edep_t0.csv').unlink()
        add_output(label,path,True)
    history=ReadOnlyHistoryPage();history.set_runs_root(str(fixtures));history.refresh();tabs.addTab(history,'合成：历史独立状态')
    selector=QTimer(host)
    def choose_history():
        if not history._scan_job.pending and history.table.rowCount():
            history.table.selectRow(0);selector.stop()
    selector.timeout.connect(choose_history);selector.start(50)
    for i,path in enumerate(args.real_dir,1):add_output(f'真实F1 {i}',Path(path).resolve(),False)
    state={'pid':os.getpid(),'ready':False,'constructed':True,'synthetic_root':str(fixtures),'directories':directories,'real_directories':args.real_dir,'purpose':'UI observation only; synthetic fixtures are not simulations','identity_before_import':IDENTITY_BEFORE_IMPORT,'identity_at_load':IDENTITY_AFTER_IMPORT,'expected_identity':expected,'observation_acceptance':'pending','host_read_only_actions':True,'launch_platform':os.environ.get('QT_QPA_PLATFORM','native/default')}
    save_receipt(state,initial=True)
    ready_timer=QTimer(host)
    def publish_ready():
        pending=any(page._identity_job.pending or (page.plot_panel is not None and page.plot_panel._identity_job.pending) for page in pages)
        pending=pending or history._scan_job.pending or history._selection_job.pending or selector.isActive()
        if not pending:
            state['ready']=True
            host.setWindowTitle('G4UniversalSim F1 '+IDENTITY_AFTER_IMPORT['git_head'][:12]+' | 身份请求完成 | 观察pending')
            state['identity_states']={label:('verified' if page.identity_panel._evidence is not None and page.identity_panel._evidence.verification_status=='verified' else ('legacy' if page.identity_panel._evidence is not None else 'unavailable_or_mismatch')) for label,page in zip(directories,pages)}
            state['real_output_records']=[]
            for label,page in zip(directories,pages):
                if not label.startswith('真实F1'):continue
                evidence=page.identity_panel._evidence
                if evidence is None:
                    state['real_output_records'].append({'label':label,'path':directories[label],'identity_status':'unavailable_or_mismatch','error':page.identity_panel._error})
                    continue
                document=evidence.document or {};values=document.get('values',{});provenance=document.get('provenance',{});build=provenance.get('build',{})
                state['real_output_records'].append({'label':label,'path':directories[label],'identity_status':evidence.verification_status,'manifest_sha256':evidence.manifest_digest,'execution_id':provenance.get('execution_id'),'recorded_build':build,'output_format_requested':values.get('output_format_requested'),'output_format_actual':values.get('output_format'),'output_format_selection_reason':values.get('output_format_selection_reason'),'recorded_run_status':values.get('status'),'explicit_auto_recorded':values.get('output_format_requested')=='auto','source_matches_loaded_code':build.get('source_fingerprint')==IDENTITY_AFTER_IMPORT['source_fingerprint'],'build_commit_matches_expected_head':build.get('git_commit')==expected.get('git_head') if expected.get('git_head') else None})
            save_receipt(state)
            ready_timer.stop()
    ready_timer.timeout.connect(publish_ready);ready_timer.start(50)
    host.show()
    if args.exit_after:QTimer.singleShot(args.exit_after,host.close)
    def close_pages():
        for page in pages:page.close()
    app.aboutToQuit.connect(close_pages)
    app.exec()
    state['closed']=True;state['closed_utc']=datetime.now(timezone.utc).isoformat();state['identity_at_exit']=load_identity();save_receipt(state)

if __name__=='__main__':main()
