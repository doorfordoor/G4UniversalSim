from pathlib import Path
import sys,runpy,importlib.util
ROOT=Path.cwd();OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'scripts'),str(ROOT/'tools')]
mode,kind=sys.argv[1:3]
suffix='-'+sys.argv[3] if len(sys.argv)>3 else ''
if mode in ('candidate','pretail'):
 name='g4usim_gui.core.experiment_bundle';spec=importlib.util.spec_from_file_location(name,OUT/('experiment_bundle-v3-before-policy-tail.py' if mode=='pretail' else 'experiment_bundle.py'));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
target=OUT/'test_k1_bundle.py' if kind in ('policy','late','late-export') else ROOT/'scripts/test_k1_bundle.py' if kind=='refusals' else ROOT/'scripts/test_k1_workflow.py'
original_run=runpy.run_path

def focused(path,init_globals=None,run_name=None):
 if Path(path).resolve()!=target.resolve():return original_run(path,init_globals=init_globals,run_name=run_name)
 namespace={'__name__':'focused_policy_review','__file__':str(ROOT/'scripts/test_k1_bundle.py') if kind=='policy' else str(target),'__package__':None,'__spec__':None,'__cached__':None}
 exec(compile(target.read_bytes(),str(target.resolve()),'exec'),namespace)
 if kind in ('policy','late','late-export'):
  evidence=OUT/('focused-'+mode+suffix);evidence.mkdir(exist_ok=False);namespace['test_resource_policy_path_identity' if kind=='policy' else 'test_resource_policy_paths_late_guard'](evidence, **({'actions': ('export',)} if kind=='late-export' else {}))
 elif kind=='refusals':
  evidence=OUT/('refusals-'+mode+suffix);evidence.mkdir(exist_ok=False);namespace['test_refusals'](evidence)
 else:namespace['source_capture_scope']()
 return namespace
runpy.run_path=focused
import test_assert_probe
raise SystemExit(test_assert_probe.main(['test_assert_probe.py',str(target)]))
