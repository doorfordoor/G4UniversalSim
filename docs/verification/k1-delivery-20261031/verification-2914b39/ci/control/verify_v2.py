"""Verify approved UI bytes and existing official GUI observations, no execution."""
from pathlib import Path
import hashlib,json,subprocess

ci=Path(__file__).resolve().parent;root=ci.parents[3]
config=json.loads((ci/'watch-config.json').read_bytes())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==config['head']
for f in config['integrated_v2_files']:
    assert hashlib.sha256((root/f['path']).read_bytes()).hexdigest()==f['sha256']
ind=json.loads((ci/'independent-profiles.json').read_bytes());assert ind['checks_passed'] and ind['head']==config['head']
rows=[]
for r in ind['reports']:
    if r['profile']!='gui':continue
    report_path=Path(r['path']);report=json.loads(report_path.read_bytes())
    cases={x['name']:x for x in report['results']}
    workflow=cases['gui_k1_window'];panel=cases['gui_k1_panel']
    assert all(x['status']=='pass' and x['exit_code']==0 and x['assertions_executed']>0 for x in [workflow,panel])
    logs={x['case']:x for x in r['logs']};log=Path(logs['gui_k1_window']['path']);payload=log.read_bytes()
    assert hashlib.sha256(payload).hexdigest()==workflow['log_sha256']
    observations=[json.loads(line.split('=',1)[1]) for line in payload.decode('utf-8').splitlines() if line.startswith('external_completed_preview=')]
    assert len(observations)==10
    assert {(x['variant'],x['language']) for x in observations}=={(i,l) for i in range(5) for l in ['en','zh_CN']}
    for x in observations:
        assert x['package_present'] is False
        text=x['displayed'];logical=x['logical'];physical=x['physical']
        label='Logical working directory:' if x['language']=='en' else '逻辑工作目录：'
        physical_label='Process launch directory:' if x['language']=='en' else '进程启动目录：'
        unknown='Unknown' if x['language']=='en' else '未知'
        assert label+'\n  '+(logical or unknown)+'\n' in text
        if physical and physical!=logical:assert physical_label+'\n  '+physical+'\n' in text
        else:assert physical_label not in text
        assert 'human-readable:\n  '+' '.join(x['command']) in text
        assert 'editor-planned-command' not in text
    rows.append(dict(artifact=r['artifact'],workflow_assertions=workflow['assertions_executed'],panel_assertions=panel['assertions_executed'],workflow_log=str(log),workflow_log_sha256=workflow['log_sha256'],panel_log_sha256=panel['log_sha256'],observations=observations))
assert len(rows)==4
result=dict(head=config['head'],checks_passed=True,scope='Official offscreen GUI test observations and approved v2 byte identity; not native/scientific acceptance',integrated_v2_files=config['integrated_v2_files'],reports=rows,external_completion_observations=40,producer_pending_assertions='Verified by passed original candidate panel regression; does not promote any other evidence level',stage_acceptance='not_decided')
with (ci/'v2-formal-evidence.json').open('xb') as stream:stream.write((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(dict(checks_passed=True,GUI_reports=4,external_completion_observations=40)))
