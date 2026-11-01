"""Verify stored independent evidence without rerunning Geant4."""
from pathlib import Path
from collections import Counter
import hashlib, json, sys
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from run_m0_tests import workspace_source_fingerprint

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def receipt(name): return read(BASE/name/'receipt.json')
def rows(name): return [json.loads(x) for x in (BASE/name/'primaries.jsonl').read_text().splitlines()]
def summary(name):
    result={}
    for line in (BASE/name/'output/run_summary.txt').read_text().splitlines():
        if '=' in line:
            k,v=line.split('=',1);result[k.strip()]=v.strip()
    return result

identity=read(BASE/'identity.json')
assert workspace_source_fingerprint()==identity['source_fingerprint']==identity['binary_fingerprint']
assert hashlib.sha256(Path(identity['executable']).read_bytes()).hexdigest()==identity['exe_sha256']
for p in BASE.glob('*/receipt.json'):
    r=read(p)
    for stream in ('stdout','stderr'):
        assert hashlib.sha256((p.parent/(stream+'.log')).read_bytes()).hexdigest()==r[stream+'_sha256']
bad=receipt('em-macro');control=receipt('em-macro-control')
assert bad['exit_code']==control['exit_code']==0
assert bad['status']==control['status']=='completed'
assert any('G4EmPenelopePhysics' in c['cpp_type'] for c in bad['constructors'])
assert not any('G4EmLivermorePhysics' in c['cpp_type'] for c in bad['constructors'])
assert any('G4EmLivermorePhysics' in c['cpp_type'] for c in control['constructors'])
dump=read(BASE/'em-macro/processes.json')
gamma=next(p for p in dump['particles'] if p['name']=='gamma')
assert 'PenCompton' in str(gamma)
assert 'G4EmLivermore -> G4EmPenelope' in (BASE/'em-macro/stdout.log').read_text()
for name in ('clear-reference','csh-em-idle'):
    assert receipt(name)['exit_code']==1 and receipt(name)['status']=='failed'
    assert receipt(name)['rows']==0
mt=rows('mt-switch-600')
assert {r['thread'] for r in mt}=={0,1}
for run,n in ((0,1),(1,2)):
    subset=[r for r in mt if r['run']==run]
    assert {r['event'] for r in subset}==set(range(600))
    assert {r['thread'] for r in subset}=={0,1}
    assert all(r['vertex_count']==n for r in subset)
    assert set(Counter(r['event'] for r in subset).values())=={n}
    assert {r['vertex'] for r in subset}==set(range(n))
assert summary('mt-switch-600')['actual_completed_event_count']=='1200'
assert summary('mt-switch-600')['actual_threads']=='2'
assert all(r['primary_weight']==r['vertex_weight']==1 for r in rows('extreme-intensity'))
assert all(r['vertex_count']==2 for r in rows('extreme-intensity'))
point=rows('surface-native-point')
assert {r['thread'] for r in point}=={0,1}
assert {(r['x_mm'],r['y_mm'],r['z_mm']) for r in point}=={(2,3,4)}
assert receipt('multi-single-field')['exit_code']==3221226505
assert not (BASE/'multi-single-field/output/run_summary.txt').exists()
assert 'Fatal Exception' in (BASE/'multi-single-field/stderr.log').read_text()
result={'status':'evidence_verified','cases':10,'new_findings':1,
        'source_fingerprint':identity['source_fingerprint'],
        'limits':'Narrow runtime/command review, not physical validation or stage completion.'}
(BASE/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result))
