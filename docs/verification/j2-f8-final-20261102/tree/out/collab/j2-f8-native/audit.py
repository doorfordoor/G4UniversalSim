"""Audit original native artifacts without relabeling or rewriting them."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'out/verification/j2-f8-56b689f'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
result = {'head': '56b689fb9ac920cbb1203b2b94dae2483d25f622', 'stage_accepted': False,
          'open_issue': 'native150 retained dock / Project focus outside viewport; independent reproduction in out/collab/f8-project-dock150',
          'observations': {}, 'limitations': ['Representative effective DPR 1.0/1.25/1.5 via Qt scale; not physical monitor hotplug.',
             'Unrelated QQ overlay pixels excluded from visual acceptance.',
             'Base Python lacked PyVista; native host used its explicit text fallback. Separate complete-venv native 3D test covers rendering.',
             'Blank run has no sensitive detector; it proves workflow and completion, not physics accuracy.']}
for name in ('native100', 'native125', 'native150'):
    folder = BASE / name
    identity = json.loads((folder / 'identity.json').read_text(encoding='utf-8'))
    ending = json.loads((folder / 'exit.json').read_text(encoding='utf-8'))
    entries = [json.loads(line) for line in (folder / 'observations.jsonl').read_text(encoding='utf-8').splitlines()]
    assert ending['exit_code'] == 0 and ending['visible'] is False
    mismatches = [key for key, digest in identity['gui_files'].items() if sha(ROOT / key) != digest]
    assert not mismatches, mismatches
    assert sha(Path(identity['exe'])) == identity['exe_sha256']
    result['observations'][name] = {'identity': str((folder/'identity.json').relative_to(ROOT)),
        'exit': ending, 'dpr': sorted({item['dpr'] for item in entries}),
        'visited_pages': sorted({item['page'] for item in entries}),
        'observation_count': len(entries), 'gui_sources_match_audit_time': True,
        'raw_project_fingerprints': sorted({item['project_sha'] for item in entries}),
        'screenshots': {p.name: sha(p) for p in sorted(folder.glob('*.png'))},
        'observation_sha256': sha(folder/'observations.jsonl')}
bundle = BASE/'native100/blank-offline-bundle'
manifest = json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
for member in manifest['members']:
    member_path = (bundle/member['path']).resolve()
    assert member_path.is_relative_to(bundle.resolve()) and member_path.is_file()
    assert member_path.stat().st_size == member['bytes'] and sha(member_path) == member['sha256']
result['export'] = {'path': str(bundle.relative_to(ROOT)), 'manifest_sha256': sha(bundle/'manifest.json'),
                    'members_verified': len(manifest['members']), 'history_trust': manifest['history_trust']}
records = []
for path in sorted((BASE/'native100/runs/experiment-records').glob('*/record.json')):
    data = json.loads(path.read_text(encoding='utf-8'))
    records.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'action': data.get('action'),
                    'state': data.get('state'), 'result': data.get('result'), 'status': data.get('status')})
result['records'] = records
summaries = []
for path in (BASE/'native100/runs').rglob('run_summary.txt'):
    values = dict(line.split('=',1) for line in path.read_text(encoding='utf-8').splitlines() if '=' in line)
    values = {k.strip(): v.strip() for k,v in values.items()}
    summaries.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
        **{key: values.get(key) for key in ('status','run_count','planned_event_count','actual_completed_event_count','run_0_planned_events','run_0_completed_events')}})
assert any(s['status']=='completed' and s['actual_completed_event_count']=='100'
           and s['planned_event_count']=='100' and s['run_count']=='1'
           and s['run_0_planned_events']=='100' and s['run_0_completed_events']=='100' for s in summaries), summaries
result['run_summaries'] = summaries
(BASE/'native-audit.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
print(json.dumps({'native_hosts': list(result['observations']), 'exit_codes': [v['exit']['exit_code'] for v in result['observations'].values()], 'bundle_members': len(manifest['members']), 'summary_count': len(summaries), 'stage_accepted': False}))
