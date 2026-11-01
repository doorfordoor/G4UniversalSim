"""Independent mode/identity probes; no author regression imports."""
from pathlib import Path
import sys,copy,tempfile,importlib.util,json
ROOT=Path.cwd();OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'scripts')]
mode=sys.argv[1]
if mode=='candidate':
 name='g4usim_gui.core.experiment_workflow';spec=importlib.util.spec_from_file_location(name,ROOT/'out/collab/j2-external-inspect-fix/experiment_workflow.py');m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
from test_f5_transactions_backend import initial_state
from g4usim_gui.core.experiment_workflow import _field_report,_original_inspection_identity
from g4usim_gui.core.edit_snapshot import snapshot_to_dict
changed=lambda snapshot:{x.raw_message for x in _field_report(snapshot).diagnostics if x.code=='experiment.captured_source.changed'}
with tempfile.TemporaryDirectory(prefix='j2-independent-modes-') as tmp:
 root=Path(tmp);g,files=initial_state(root,Path(sys.executable));assert _field_report(g).can_run
 ext=copy.deepcopy(g);ext.project.runInputMode='external';ext.project.configPath='actual-main.ini';ext.project.macroPath='actual.mac';ext.project.outputDir=str(root/'never-created')
 main=root/'actual-main.ini';macro=root/'actual.mac';main.write_text('[run]\nseed=17\n');macro.write_text('# original macro\n')
 # Dormant editor files now disappear; actual inputs stay valid and relative.
 files[0].unlink();files[1].write_text('# external edit\n')
 before=snapshot_to_dict(ext)
 assert _field_report(ext).can_run,[(x.code,x.raw_message) for x in _field_report(ext).diagnostics]
 assert not changed(ext)
 assert snapshot_to_dict(ext)==before
 identity=_original_inspection_identity(ext,7)
 assert set(identity['declared_source_receipts'])=={str(main.resolve()),str(macro.resolve())}
 assert identity['recursive_closure']=='unobserved'
 old=identity['resource_fingerprint'];macro.write_text('# actual macro changed\n');assert _original_inspection_identity(ext,7)['resource_fingerprint']!=old
 old=_original_inspection_identity(ext,7)['resource_fingerprint'];main.write_text('[run]\nseed=18\n');assert _original_inspection_identity(ext,7)['resource_fingerprint']!=old
 for one in ('configPath','macroPath'):
  single=copy.deepcopy(ext);setattr(single.project,one,'');assert _field_report(single).can_run
 neither=copy.deepcopy(ext);neither.project.configPath='';neither.project.macroPath='';assert not _field_report(neither).can_run
 for field in ('configPath','macroPath'):
  invalid=copy.deepcopy(ext);setattr(invalid.project,field,'absent-file');assert not _field_report(invalid).can_run
 invalid=copy.deepcopy(ext);invalid.project.runInputMode='unrecognized';report=_field_report(invalid);assert not report.can_run and any(x.code=='project.input_mode' for x in report.diagnostics)
 # Switching mode reactivates captures, rather than clearing saved history.
 back=copy.deepcopy(ext);back.project.runInputMode='generated';assert not _field_report(back).can_run and changed(back)=={'materials','geometry'}
 back.project.runInputMode='external';assert _field_report(back).can_run and not changed(back)
 assert snapshot_to_dict(ext)==before
 # A failed capture-read remains a generated rejection even if its current file is restored.
 files[0].write_text(g.state['sources']['materials']['text']);files[1].write_text(g.state['sources']['geometry']['text'])
 assert _field_report(g).can_run
 for kind in ('materials','geometry'):
  broken=copy.deepcopy(g);broken.state['sources'][kind]['read_success']=False;assert kind in changed(broken)
  if kind=='materials':broken.project.pathSettings.materials_config=str(main)
  else:broken.project.geometrySettings.config_path=str(main)
  assert kind in changed(broken)
 assert not Path(ext.project.outputDir).exists()
(OUT/('mode-'+mode+'-facts.json')).write_text(json.dumps(dict(mode=mode,relative_external_inputs=True,main_only_macro_only=True,mode_toggle_captures_preserved=True,original_identity_changed_for_each_actual_file=True,recursive_closure_unobserved=True,output_not_created=True),indent=2)+'\n')
print('independent mode / relative origin / actual input identity / generated negative matrix PASS')
