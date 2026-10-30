"""Targeted real-process validation for one isolated binding pair."""
import sys,os,subprocess,json,hashlib,time,re
from pathlib import Path
import PySide6,shiboken6
from PySide6.QtCore import qVersion
ROOT=Path(__file__).resolve().parents[2]
VERSION=sys.argv[1]
OUT=ROOT/'out/collab/f4-qt-dependency-validation'/('validation-'+VERSION+'-rpath-data')
OUT.mkdir(parents=True,exist_ok=True)
assert PySide6.__version__==VERSION and shiboken6.__version__==VERSION
assert str(Path(PySide6.__file__).resolve()).startswith(sys.prefix+'/')
assert str(Path(shiboken6.__file__).resolve()).startswith(sys.prefix+'/')
BUILD=Path('/home/u123/g4-f4-qt-validation-build114-20261030')
exe=BUILD/'G4UniversalSim'
env=os.environ.copy()
env.update(QT_QPA_PLATFORM='offscreen',QT_PLUGIN_PATH=str(Path(PySide6.__file__).parent/'Qt/plugins'),
           GEANT4_DATA_DIR='/home/u123/g4env114/share/Geant4/data',
           G4USIM_GEANT4_DATA='/home/u123/g4env114/share/Geant4/data',G4USIM_EXE=str(exe),
           G4USIM_MERGE_EXE=str(BUILD/'mergeHistograms'),PYTHONDONTWRITEBYTECODE='1',
           MPLCONFIGDIR=str(OUT/'matplotlib'),G4_F4_QA_STATE_ROOT=str(OUT/'state'))
env.pop('LD_LIBRARY_PATH',None)
data_variables={}
prefix=Path('/home/u123/g4env114')
for script in (prefix/'etc/conda/activate.d').glob('activate-geant4-data-*.sh'):
    for match in re.finditer(r'^export (G4[A-Z0-9_]*DATA)=\$\{CONDA_PREFIX\}/([^\s]+)$',script.read_text(),re.M):
        path=(prefix/match[2]).resolve()
        assert path.is_dir() and path.is_relative_to(prefix)
        data_variables[match[1]]=str(path)
assert len(data_variables)==12, data_variables
env.update(data_variables)
(OUT/'data-environment.json').write_text(json.dumps(data_variables,indent=2))
discovery=subprocess.run([str(exe),'--check-geant4-data'],env=env,capture_output=True,check=True)
(OUT/'data-discovery.json').write_bytes(discovery.stdout)
cap=subprocess.run([str(exe),'--capabilities'],env=env,capture_output=True,check=True)
(OUT/'capabilities.json').write_bytes(cap.stdout)
identity={'python':sys.version,'prefix':sys.prefix,'pyside':PySide6.__version__,'shiboken':shiboken6.__version__,
          'qt':qVersion(),'pyside_path':PySide6.__file__,'shiboken_path':shiboken6.__file__,
          'gui_native_git_receipt':json.loads((ROOT/'out/collab/f4-qt-dependency-validation/windows-checkout-receipt.json').read_text(encoding='utf-8-sig')),
          'backend':str(exe),'backend_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
          'capabilities':json.loads(cap.stdout)}
(OUT/'identity.json').write_text(json.dumps(identity,indent=2),encoding='utf-8')
cases=[('binding',ROOT/'out/collab/smoke_qt_binding_lifetime_candidate.py'),
       ('gui_f4_inspect_backend',ROOT/'gui/smoke_tests/smoke_f4_inspect_backend.py'),
       ('gui_run_inputs',ROOT/'gui/smoke_tests/smoke_run_input_modes.py'),
       ('gui_f4_layout',ROOT/'gui/smoke_tests/smoke_f4_layout.py')]
results=[]
for name,target in cases:
    begin=time.monotonic()
    result=subprocess.run([sys.executable,'-B',str(ROOT/'out/collab/f4-qt-test-wrapper.py'),str(target)],
                          cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    path=OUT/(name+'.log');path.write_bytes(result.stdout)
    record={'name':name,'exit_code':result.returncode,'seconds':time.monotonic()-begin,
            'log_sha256':hashlib.sha256(result.stdout).hexdigest(),'script_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'assert_markers':[line for line in result.stdout.decode('utf-8',errors='replace').splitlines() if line.startswith('G4USIM_ASSERTS=')]}
    results.append(record);print(json.dumps(record),flush=True)
    (OUT/'results.json').write_text(json.dumps(results,indent=2))
raise SystemExit(any(r['exit_code']!=0 for r in results))
