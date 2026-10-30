"""Early strict per-profile gate; the final audit covers all artifacts together."""
from pathlib import Path
import json,runpy,subprocess,sys
BASE=Path(__file__).resolve().parent
audit=runpy.run_path(str(BASE/'audit-ci.py'),run_name='audit_util')
name=sys.argv[1];assert name in audit['PROFILES']
frozen=audit['load'](BASE/'frozen-case-manifest.json');records=[];seen=set()
for path in sorted((BASE/name).rglob('report.json')):
    report=audit['load'](path);profile=report['profile'];assert profile not in seen;seen.add(profile)
    assert report['git_head']==audit['HEAD']
    assert report['source_fingerprint']==frozen['source_fingerprint']
    assert report['tests_content_fingerprint']==frozen['tests_content_fingerprint']
    assert [r['name'] for r in report['results']]==frozen['profiles'][profile]
    baselines=[p for p in (audit['BASELINE']/name).rglob('report.json') if audit['load'](p)['profile']==profile]
    assert len(baselines)==1
    proc=subprocess.run([sys.executable,'-B',str(audit['ROOT']/'scripts/check_report_evidence.py'),'--report',str(path),'--baseline',str(baselines[0])],cwd=audit['ROOT'],capture_output=True,timeout=120)
    gate=BASE/'baseline-gates'/f'{name}-{profile}.log';audit['save'](gate,proc.stdout+proc.stderr)
    records.append({'artifact':name,'profile':profile,'cases':len(report['results']),
                    'assertions':report['assertions_executed_total'],'git_dirty':report['git_dirty'],'gate_exit':proc.returncode})
assert seen==audit['PROFILES'][name]
print(json.dumps(records,indent=2))
assert all(r['gate_exit']==0 for r in records)
