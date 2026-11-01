"""Independent narrow J2 backend command-boundary review; no product edits."""
from pathlib import Path
import os, sys, json, subprocess, hashlib, datetime

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
EXE = ROOT / 'out/build-i2-formal113/Release/G4UniversalSim.exe'
sys.path.insert(0, str(ROOT / 'scripts'))
from run_m0_tests import workspace_source_fingerprint

ENV = dict(os.environ)
ENV['PATH'] = r'D:\ProgramFiles\Geant4\bin;D:\ProgramFiles\Qt\5.15.2\msvc2019_64\bin;' + ENV['PATH']
ENV['GEANT4_DATA_DIR'] = r'D:\ProgramFiles\Geant4\share\Geant4\data'
POINT = '[source]\nparticle=gamma\nenergy=1 MeV\nposition_type=point\nposition=0,0,0 mm\ndirection=0,0,1\n'
NAMED = '''[source]
multiple_vertex=true
[source.a]
particle=gamma
energy=1 MeV
position_type=surface
shape=sphere
center=0,0,0 mm
radius=5 mm
angular=fixed
direction=0,0,1
intensity=1
[source.b]
particle=gamma
energy=2 MeV
position_type=point
position=0,0,0 mm
direction=0,0,1
intensity=3
'''

def write(p, text):
    p.write_text(text, encoding='utf-8', newline='\n')

def run(name, physics, commands, source=POINT, threads=2, stdin=None):
    directory = BASE / name
    directory.mkdir(exist_ok=False)
    write(directory/'geometry.ini', '[world]\nshape=box\nsize=1 m,1 m,1 m\nmaterial=G4_Galactic\n')
    write(directory/'main.ini', f'[run]\nthreads={threads}\nseed=435\n[output]\nformat=csv\n'
          f'[materials]\nfile={(ROOT / "config/materials/material.ini").as_posix()}\n'
          '[geometry]\ntemplate=hierarchical\nconfig=geometry.ini\n'
          f'[physics]\n{physics}\n[scoring]\nenabled=false\n{source}')
    write(directory/'run.mac', commands)
    args = [str(EXE),'--config','main.ini','--macro','run.mac','--output','output']
    if stdin is not None: args += ['--ui','--ui-session','csh']
    env = dict(ENV, G4USIM_TEST_PRIMARY_VERTICES=str(directory/'primaries.jsonl'))
    result = subprocess.run(args, cwd=directory, env=env, capture_output=True,
                            input=stdin.encode() if stdin is not None else None, timeout=60)
    (directory/'stdout.log').write_bytes(result.stdout)
    (directory/'stderr.log').write_bytes(result.stderr)
    summary = {}
    if (directory/'output/run_summary.txt').exists():
        for line in (directory/'output/run_summary.txt').read_text(encoding='utf-8').splitlines():
            if '=' in line:
                k,v=line.split('=',1); summary[k.strip()]=v.strip()
    rows = [json.loads(x) for x in (directory/'primaries.jsonl').read_text().splitlines()] if (directory/'primaries.jsonl').exists() else []
    dump = json.loads((directory/'processes.json').read_text()) if (directory/'processes.json').exists() else None
    receipt = dict(name=name, exit_code=result.returncode, argv=args,
                   status=summary.get('status'), completed=summary.get('actual_completed_event_count'),
                   output_failure=summary.get('output_failure_status'), rows=len(rows),
                   worker_ids=sorted({x['thread'] for x in rows}),
                   vertex_counts=sorted({x['vertex_count'] for x in rows}),
                   constructors=dump['physics_list'].get('constructor_details') if dump else None,
                   stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
                   stderr_sha256=hashlib.sha256(result.stderr).hexdigest())
    write(directory/'receipt.json', json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('name','exit_code','status','completed','rows','worker_ids','vertex_counts')}),flush=True)
    return receipt

if __name__ == '__main__':
    caps = subprocess.run([str(EXE),'--capabilities'],cwd=ROOT,env=ENV,capture_output=True,timeout=15)
    (BASE/'capabilities.json').write_bytes(caps.stdout)
    cap = json.loads(caps.stdout)
    identity = dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    executable=str(EXE),exe_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),
                    source_fingerprint=workspace_source_fingerprint(),binary_fingerprint=cap.get('source_fingerprint'))
    write(BASE/'identity.json',json.dumps(identity,indent=2)+'\n')
    assert identity['source_fingerprint']==identity['binary_fingerprint'], identity
    write(BASE/'progress.md','只读独审 Source/Physics baseline fc606739。产品不改；仅本目录写反例。\n已读根 AGENTS、history A4/A6 与 Q1 源边界；核对二进制身份。\n正在运行独立 macro/csh/MT 边界用例，未复跑已有三套测试。\n')
    cases = [
      ('em-macro', 'reference=FTFP_BERT\nreplace_modules=penelope', '/AIHL/physics/setEM livermore\n/run/initialize\n/run/beamOn 8\n/AIHL/physics/dumpProcesses processes.json\n', POINT, 2, None),
      ('clear-reference', 'reference=FTFP_BERT\nreplace_modules=penelope', '/AIHL/physics/clearReferenceList\n/run/initialize\n/run/beamOn 8\n', POINT, 2, None),
      ('native-single', 'reference=FTFP_BERT', '/gps/source/multiplevertex false\n/run/initialize\n/run/beamOn 24\n/run/beamOn 24\n', NAMED, 2, None),
      ('native-multiple', 'reference=FTFP_BERT', '/gps/source/multiplevertex false\n/run/initialize\n/run/beamOn 16\n/gps/source/multiplevertex true\n/run/beamOn 16\n', NAMED, 2, None),
      ('csh-em-idle', 'reference=FTFP_BERT\nreplace_modules=penelope', '/run/initialize\n', POINT, 2, '/AIHL/physics/setEM livermore\n/run/beamOn 8\nexit\n'),
    ]
    receipts=[run(*case) for case in cases]
    write(BASE/'receipts.json',json.dumps(receipts,indent=2)+'\n')
    final_fp=workspace_source_fingerprint()
    write(BASE/'end-identity.json',json.dumps(dict(source_fingerprint=final_fp,unchanged=final_fp==identity['source_fingerprint']),indent=2)+'\n')
