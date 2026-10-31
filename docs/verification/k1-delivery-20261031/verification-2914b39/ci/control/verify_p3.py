"""Read official GUI case evidence only; never executes product or regression."""
from pathlib import Path
import hashlib,json

ci=Path(__file__).resolve().parent
config=json.loads((ci/'watch-config.json').read_bytes())
ind=json.loads((ci/'independent-profiles.json').read_bytes())
assert ind['head']==config['head']
expected={'cancel_error_finished','error_finished','init_cancel_error_finished','init_error_finished','late_cancel','late_edit','persistence_failure','late_work','finished_before_error','cancel_work_delivery','edit_work_delivery'}
rows=[]
for report_row in ind['reports']:
    if report_row['profile']!='gui':continue
    path=Path(report_row['path']);report=json.loads(path.read_bytes())
    case=next(r for r in report['results'] if r['name']=='gui_k1_terminal_publication')
    assert case['status']=='pass' and case['exit_code']==0 and case['assertions_executed']>0
    evidence=path.parent/case['evidence_directory']
    receipts=[p for p in evidence.rglob('receipt.json') if json.loads(p.read_bytes()).get('scope')=='component_terminal_lifecycle_only']
    assert len(receipts)==1
    receipt=json.loads(receipts[0].read_bytes())
    assert receipt['cases']==11 and len(receipt['results'])==11
    assert {r['mode'] for r in receipt['results']}==expected and all(r['status']=='passed' for r in receipt['results'])
    observations=[]
    for mode in ['cancel_work_delivery','edit_work_delivery']:
        p=receipts[0].parent/mode/'observed.json';v=json.loads(p.read_bytes())
        assert v['mode']==mode and v['completed_count']==1 and v['disk_matches_callback'] is True
        if mode=='cancel_work_delivery':
            assert v['status']=='cancelled' and v['reason']=='experiment.cancelled'
            assert v['revision_after']==v['revision_before'] and v['snapshot_changed'] is False
        else:
            assert v['status']=='stale' and v['reason']=='experiment.inputs_changed'
            assert v['revision_after']>v['revision_before'] and v['snapshot_changed'] is True
        observations.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),observed=v))
    rows.append(dict(artifact=report_row['artifact'],case=case['name'],assertions=case['assertions_executed'],case_log_sha256=case['log_sha256'],receipt=str(receipts[0]),receipt_sha256=hashlib.sha256(receipts[0].read_bytes()).hexdigest(),observations=observations))
assert len(rows)==4
result=dict(head=config['head'],scope='Official component regressions only; not native simulation or stage acceptance',source_files=config['source_files'],reports=rows,controlled_mode_observations=8,old_and_new_modes_per_report=11,checks_passed=True,stage_acceptance='not_decided')
with (ci/'p3-evidence.json').open('xb') as stream:stream.write((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(dict(checks_passed=True,reports=len(rows),controlled_observations=8)))
