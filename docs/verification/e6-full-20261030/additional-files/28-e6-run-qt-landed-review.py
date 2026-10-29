import ast, hashlib, json, os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'out/verification/e6-qt-landed-independent'
OUT.mkdir(parents=True,exist_ok=True)
path='gui/smoke_tests/smoke_project_import_projection.py'
old=subprocess.check_output(['git','show','5bf479d85ba7c12e0f71984d31b8335c47c5a8c3:'+path],cwd=ROOT).decode('utf-8-sig')
new=(ROOT/path).read_text(encoding='utf-8-sig')
asserts=lambda s:[ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Assert)]
assert asserts(old)==asserts(new)
records=[]
for name,command in [('semantics_product','out/collab/e6-qt-landed-independent.py --product'),('formal_helper','tools/test_assert_probe.py gui/smoke_tests/smoke_qt_combo_data.py'),*[(f'formal_projection_{i}','tools/test_assert_probe.py '+path) for i in range(1,4)]]:
    bash='cd /mnt/c/Users/123/.codex/worktrees/effective-config/G4UniversalSim && QT_QPA_PLATFORM=offscreen QT_PLUGIN_PATH=/home/u123/g4ci/lib/python3.11/site-packages/PySide6/Qt/plugins /home/u123/g4ci/bin/python -B '+command
    p=subprocess.run(['wsl','-d','Ubuntu','--','bash','-lc',bash],cwd=ROOT,capture_output=True,timeout=180)
    for suffix,data in [('stdout',p.stdout),('stderr',p.stderr)]: (OUT/(name+'.'+suffix+'.log')).write_bytes(data)
    record={'case':name,'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'fatal_none_dealloc':b'none_dealloc' in p.stderr,'markers':[line for line in p.stdout.decode('utf-8',errors='replace').splitlines() if 'G4USIM_ASSERTS=' in line]}
    records.append(record)
    (OUT/'results.json').write_text(json.dumps({'original_assert_AST_unchanged':True,'results':records},indent=2),encoding='utf-8')
    print(json.dumps(record),flush=True)
    assert p.returncode==0 and not record['fatal_none_dealloc'],record
print('independent landed review complete',flush=True)
