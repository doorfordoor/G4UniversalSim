"""Read-only independent checks of the archived DDD first-run subset."""
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath


def audit_ddd_evidence(report_path, record):
    report_path = Path(report_path)
    leaf = record['evidence_directory']
    assert isinstance(leaf, str) and leaf == 'displacement_damage-evidence'
    root = report_path.parent / leaf / 'first-run'
    manifest_path = root / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['schema'] == 'g4usim_ddd_first_run_evidence_v1' and manifest['returncode'] == 0
    files, seen = [], set()
    for row in manifest['files']:
        name = row['path']
        relative = PurePosixPath(name)
        assert not relative.is_absolute() and '..' not in relative.parts and '\\' not in name
        assert not PureWindowsPath(name).drive and relative.parts[0] in {'inputs', 'outputs'}
        path = root.joinpath(*relative.parts)
        assert path.resolve().is_relative_to(root.resolve()) and name not in seen and not path.is_symlink()
        seen.add(name)
        raw = path.read_bytes()
        assert len(raw) == row['size_bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
        files.append({'path': name, 'size_bytes': len(raw), 'sha256': row['sha256']})
    required = {'inputs/case01.ini', 'inputs/case01_geometry.ini', 'inputs/case01.mac',
                'inputs/material.ini', 'inputs/mu.csv', 'inputs/far.csv',
                'outputs/scorer_statistics.csv', 'outputs/run_metadata.json', 'outputs/run_summary.txt'}
    assert required <= seen
    actual = {p.relative_to(root).as_posix() for parent in ('inputs', 'outputs')
              for p in (root / parent).rglob('*') if p.is_file()}
    assert actual == seen
    worker_rows, event_counts, identities = [], {}, set()
    for path in sorted((root / 'outputs').glob('displacement_volume_summary_t*.csv')):
        worker = int(path.stem.rsplit('_t', 1)[1])
        assert worker in (0, 1) and worker not in event_counts
        with path.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        counts = {int(row['n_events']) for row in rows}
        assert len(counts) <= 1
        event_counts[worker] = next(iter(counts), None)
        assert (not rows and event_counts[worker] is None) or event_counts[worker] > 0
        for row in rows:
            assert row['runID'] == '0' and row['particle'] in {'mu-', 'e-'}
            key = worker, row['runID'], row['volume_path'], row['particle']
            assert key not in identities
            identities.add(key)
        worker_rows.append({'file': path.relative_to(root).as_posix(), 'worker': worker,
                            'row_count': len(rows), 'worker_events': event_counts[worker], 'rows': rows})
    observed_events = sum(count for count in event_counts.values() if count is not None)
    assert worker_rows and 0 < observed_events <= 200
    with (root / 'outputs/scorer_statistics.csv').open(encoding='utf-8', newline='') as stream:
        statistics = [row for row in csv.DictReader(stream) if row['scorer'] == 'displacement']
    assert statistics and all(int(row['n_events']) == 200 for row in statistics)
    metadata = json.loads((root / 'outputs/run_metadata.json').read_text(encoding='utf-8'))
    assert metadata['values']['status'] == metadata['values']['summary_write_status'] == 'completed'
    assert metadata['values']['output_failure_status'] == 'none'
    assert metadata['runs'] == [{'run_id': 0, 'planned_events': 200, 'completed_events': 200}]
    return {'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'files': files, 'raw_bytes': sum(row['size_bytes'] for row in files),
            'worker_rows': worker_rows, 'observed_worker_event_sum': observed_events,
            'master_events': 200, 'scope': 'Observed sparse-worker N is a lower bound, not full event coverage. '
                                        'A header-only worker has unknown N. Original first-run subset, not a runnable bundle.'}
