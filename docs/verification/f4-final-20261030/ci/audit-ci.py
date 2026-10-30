"""Independent raw-byte CI audit. Writes only this new F4 ignored directory."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import hashlib, json, re, stat, subprocess, sys, zipfile

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
HEAD = 'a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9'
RUNS = (41056994075, 41056993987)
COUNTS = {'static': 28, 'gui': 44, 'backend': 59, 'integration': 21}
PROFILES = {'linux-evidence-11.3.2': set(COUNTS), 'linux-evidence-11.4.3': set(COUNTS),
            'm0-report-windows-latest': {'static', 'gui'}, 'm0-report-ubuntu-latest': {'static', 'gui'}}
BASELINE = ROOT / 'docs/verification/f1-automated-20261030/ci'

def load(path):
    return json.loads(path.read_text(encoding='utf8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, raw):
    if path.exists():
        assert path.read_bytes() == raw, f'Existing evidence differs: {path.name}'
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)

def json_save(path, value):
    save(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8'))

def main():
    partial = '--partial' in sys.argv
    frozen = load(BASE / 'frozen-case-manifest.json')
    assert frozen['head_sha'] == HEAD
    assert {key: len(value) for key, value in frozen['profiles'].items()} == COUNTS
    names = [n for values in frozen['profiles'].values() for n in values]
    assert len(names) == len(set(names)) == 152
    artifacts, runs, jobs, reports, case_logs, members = [], [], [], [], [], []
    qt_runtime, helper_builds, helper_runs = [], [], []
    problems, pairs = [], set()
    for run_id in RUNS:
        metadata = BASE / f'{run_id}-run.json'
        if not metadata.exists() and partial:
            continue
        run = load(metadata)
        assert run['id'] == run_id and run['head_sha'] == HEAD
        assert run['status'] == 'completed' and run['run_attempt'] == 1 and run['event'] == 'push'
        assert run['head_branch'] == 'roadmap/F4-validation-navigation'
        assert run['path'] == ('.github/workflows/linux-geant4.yml' if run_id == RUNS[0] else '.github/workflows/m0-static-gui.yml')
        runs.append({key: run[key] for key in ('id', 'head_sha', 'head_branch', 'name', 'status', 'conclusion', 'run_attempt', 'html_url')})
        if run['conclusion'] != 'success':
            problems.append(f'Run {run_id}: {run["conclusion"]}')
        job_info = load(BASE / f'{run_id}-jobs-api.json')
        assert job_info['total_count'] == len(job_info['jobs']) == 2
        normalized = load(BASE / f'{run_id}-jobs.json')['jobs']
        assert {j['id'] for j in normalized} == {j['id'] for j in job_info['jobs']}
        expected_jobs = ({'ubuntu-24.04 / Geant4 11.3.2', 'ubuntu-24.04 / Geant4 11.4.3'}
                         if run_id == RUNS[0] else {'windows-latest / Python 3.11', 'ubuntu-latest / Python 3.11'})
        assert {j['name'] for j in job_info['jobs']} == expected_jobs
        for job in job_info['jobs']:
            assert job['run_id'] == run_id and job['head_sha'] == HEAD and job['status'] == 'completed'
            assert job['run_attempt'] == 1
            log = BASE / f'job-{job["id"]}.log'
            raw = log.read_bytes()
            negative_control = None
            if run_id == RUNS[0]:
                steps = [s for s in job['steps'] if s['name'] == 'Verify the evidence gate rejects a tampered report']
                negative_control = len(steps) == 1 and steps[0]['conclusion'] == 'success' and b'evidence gate rejected the tampered log digest' in raw and b'log digest mismatch' in raw
                if not negative_control:
                    problems.append(f'Negative-control evidence absent for job {job["id"]}')
                built = {name: ('Built target ' + name).encode('ascii') in raw for name in ('gdmlInputCaptureCheck', 'scoringNumericCheck', 'randomCommandGuardCheck')}
                helper_builds.append({'job_id': job['id'], 'targets': built})
                if not all(built.values()):
                    problems.append(f'Helper build completion missing for job {job["id"]}')
            if job['conclusion'] != 'success':
                problems.append(f'Job {job["id"]}: {job["conclusion"]}')
            jobs.append({'id': job['id'], 'name': job['name'], 'run_id': run_id, 'head_sha': job['head_sha'],
                         'status': job['status'], 'conclusion': job['conclusion'], 'path': log.name,
                         'bytes': len(raw), 'sha256': sha(log), 'representation': 'connector-decoded UTF-8 text',
                         'negative_control_passed': negative_control})
        info = load(BASE / f'{run_id}-artifacts-api.json')
        assert info['total_count'] == len(info['artifacts']) == 2
        normalized_artifacts = load(BASE / f'{run_id}-artifacts.json')['artifacts']
        assert {a['id'] for a in info['artifacts']} == {a['id'] for a in normalized_artifacts}
        for artifact in info['artifacts']:
            assert artifact['name'] in PROFILES and artifact['expired'] is False
            assert artifact['workflow_run']['id'] == run_id and artifact['workflow_run']['head_sha'] == HEAD
            archive = BASE / (artifact['name'] + '.zip')
            actual = 'sha256:' + sha(archive)
            assert actual == artifact['digest'] and archive.stat().st_size == artifact['size_in_bytes']
            destination, seen = BASE / artifact['name'], set()
            with zipfile.ZipFile(archive) as source:
                for member in source.infolist():
                    rel = PurePosixPath(member.filename)
                    assert not rel.is_absolute() and '..' not in rel.parts and not PureWindowsPath(member.filename).drive and '\\' not in member.filename
                    assert not stat.S_ISLNK(member.external_attr >> 16)
                    path = destination.joinpath(*rel.parts)
                    resolved = path.resolve()
                    assert resolved.is_relative_to(destination.resolve()) and resolved not in seen
                    seen.add(resolved)
                    if member.is_dir():
                        continue
                    raw = source.read(member)
                    assert path.is_file() and path.read_bytes() == raw
                    members.append({'artifact': artifact['name'], 'member': member.filename, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            artifacts.append({'id': artifact['id'], 'run_id': run_id, 'name': artifact['name'], 'official_digest': artifact['digest'], 'local_sha256': actual, 'bytes': archive.stat().st_size})
    for artifact in artifacts:
        name = artifact['name']
        for path in sorted((BASE / name).rglob('report.json')):
            report = load(path)
            profile = report['profile']
            assert profile in PROFILES[name] and (name, profile) not in pairs
            pairs.add((name, profile))
            assert report['git_head'] == HEAD and report['tracked_source_gate'] == 'pass' and report['untracked_source_files'] == []
            for field in ('source_fingerprint', 'tests_content_fingerprint'):
                assert report[field] == frozen[field]
            assert report['skip_policy'] == 'failure'
            assert report['platform'].startswith('Windows-' if name == 'm0-report-windows-latest' else 'Linux-')
            if profile in {'backend', 'integration'}:
                assert report['backend_provenance'] == 'source_sha256_manifest_matches_executable'
                assert report['merge_provenance'] == 'source_sha256_matches_executable'
                identity = report['backend_build_identity']
                assert identity['geant4_version_number'] == (1132 if name == 'linux-evidence-11.3.2' else 1143)
                assert identity['multithreaded'] is True and identity['build_configuration'] == 'Release'
                assert identity['compiler_id'] == 'GNU' and identity['compiler_version']
            assert [r['name'] for r in report['results']] == frozen['profiles'][profile]
            assert len(report['results']) == COUNTS[profile]
            baseline_paths = [p for p in (BASELINE / name).rglob('report.json') if load(p)['profile'] == profile]
            assert len(baseline_paths) == 1
            baseline = baseline_paths[0]
            proc = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/check_report_evidence.py'), '--report', str(path), '--baseline', str(baseline)], cwd=ROOT, capture_output=True, timeout=120)
            gate_log = BASE / 'baseline-gates' / f'{name}-{profile}.log'
            save(gate_log, proc.stdout + proc.stderr)
            bad = []
            if proc.returncode:
                problems.append(f'Strict baseline gate failed: {name}/{profile}')
            for row in report['results']:
                leaf = PurePosixPath(row['log'].replace('\\', '/')).name
                candidates = [p for p in (path.parent / leaf, path.parent / 'logs' / leaf) if p.is_file()]
                assert len(candidates) == 1
                log = candidates[0]
                raw = log.read_bytes()
                assert log.resolve().is_relative_to(BASE.resolve()) and sha(log) == row['log_sha256']
                markers = re.findall(rb'^G4USIM_ASSERTS=(\d+)\r?$', raw, re.M)
                assert markers and int(markers[-1]) == row['assertions_executed']
                assert row['layer'] == profile and row['assert_probe'] == report['assert_probe'] == 'settrace_assert_lines_v3'
                if row['status'] != 'pass' or row['exit_code'] != 0 or row['assertions_executed'] <= 0:
                    bad.append(row['name'])
                case_logs.append({'artifact': name, 'profile': profile, 'case': row['name'], 'status': row['status'], 'exit_code': row['exit_code'], 'assertions': row['assertions_executed'], 'path': log.relative_to(BASE).as_posix(), 'bytes': len(raw), 'sha256': sha(log)})
                if row['name'] == 'gui_qt_binding_lifetime':
                    events = [json.loads(line) for line in raw.decode('utf8').splitlines() if line.startswith('{')]
                    identities = [event for event in events if 'PySide6' in event]
                    assert len(identities) == 1
                    identity = identities[0]
                    operations = [event for event in events if 'operation' in event]
                    expected_operations = {'QWidget.update', 'QObject.setObjectName', 'QObject.missing_property', 'QObject.existing_false_property'}
                    version = re.fullmatch(r'6\.11\.(\d+)', identity['PySide6'])
                    matched = bool(version and int(version.group(1)) >= 1 and identity['PySide6'] == identity['shiboken6'] == identity['Qt']
                                   and identity['implementation'] == 'CPython' and identity['python'].startswith('3.11.')
                                   and {event['operation'] for event in operations} == expected_operations and len(operations) == 4
                                   and all(event['iterations'] == 100 and event['none_ref_delta'] == 0 for event in operations)
                                   and row['status'] == 'pass' and row['exit_code'] == 0 and row['assertions_executed'] == 8)
                    qt_runtime.append({'artifact': name, 'identity': identity, 'operations': operations, 'pass': matched, 'log': log.relative_to(BASE).as_posix(), 'log_sha256': sha(log)})
                    if not matched:
                        problems.append(f'Qt runtime binding evidence rejected: {name}')
                if name.startswith('linux-evidence-') and row['name'] in {'effective_gdml', 'scoring_numeric', 'random_command_semantics'}:
                    helper_runs.append({'artifact': name, 'case': row['name'], 'status': row['status'], 'exit_code': row['exit_code'], 'assertions': row['assertions_executed'], 'log': log.relative_to(BASE).as_posix(), 'log_sha256': sha(log)})
            assert sum(r['assertions_executed'] for r in report['results']) == report['assertions_executed_total']
            if bad:
                problems.append(f'Nonpassing cases in {name}/{profile}: {bad}')
            reports.append({'artifact': name, 'profile': profile, 'path': path.relative_to(BASE).as_posix(), 'sha256': sha(path), 'cases': len(report['results']), 'assertions': report['assertions_executed_total'], 'git_dirty': report['git_dirty'], 'backend_build_identity': report['backend_build_identity'], 'backend_provenance': report['backend_provenance'], 'merge_provenance': report['merge_provenance'], 'strict_baseline_gate_exit': proc.returncode, 'baseline': baseline.relative_to(ROOT).as_posix(), 'baseline_sha256': sha(baseline), 'gate_log': gate_log.relative_to(BASE).as_posix(), 'failures': bad})
    expected_pairs = {(a, p) for a, profiles in PROFILES.items() for p in profiles}
    profile_coverage_complete = pairs == expected_pairs
    complete = len(runs) == 2 and len(jobs) == 4 and len(artifacts) == 4
    missing_profiles = sorted(expected_pairs - pairs)
    if missing_profiles:
        problems.append('Missing profiles after workflow failure: ' + repr(missing_profiles))
    if not partial and len(qt_runtime) != 4:
        problems.append('Four actual GUI runtime-version receipts required')
    if not partial and len(helper_runs) != 6:
        problems.append('All three helper cases required on both Linux versions')
    if not partial:
        assert complete
        if not problems:
            assert profile_coverage_complete and len(reports) == 12 and len(case_logs) == 448
    receipt = {'head_sha': HEAD, 'status': 'failed' if problems else ('passed' if complete else 'partial'), 'evidence_collection_complete': complete, 'problems': problems, 'runs': runs, 'jobs': jobs, 'artifacts': artifacts, 'reports': reports, 'case_executions': len(case_logs), 'all_case_logs_sha_marker_matched': True, 'all_zip_members_match': True, 'report_count': len(reports), 'case_logs': case_logs, 'zip_members': members, 'source_fingerprint': frozen['source_fingerprint'], 'tests_content_fingerprint': frozen['tests_content_fingerprint'], 'boundary': 'CI only; local Windows all-profile and native UI acceptance are separate. No physics validation is inferred.'}
    receipt['candidate_stage_status'] = 'ci_passed_other_acceptance_separate' if receipt['status'] == 'passed' else 'ci_not_accepted'
    receipt['report_profile_coverage_complete'] = profile_coverage_complete
    receipt['missing_profiles'] = missing_profiles
    receipt['qt_runtime'] = qt_runtime
    receipt['helper_builds'] = helper_builds
    receipt['helper_runs'] = helper_runs
    receipt['native_evidence_boundary'] = 'Native acceptance and Windows all-profile are handled by root; this receipt does not infer their result.'
    output = BASE / ('partial-m0-audit.json' if partial else 'evidence-integrity-audit.json')
    json_save(output, receipt)
    print(json.dumps({k: receipt[k] for k in ('head_sha', 'status', 'evidence_collection_complete', 'report_count', 'case_executions', 'problems')}, ensure_ascii=False))
    return 1 if problems else 0

if __name__ == '__main__':
    raise SystemExit(main())
