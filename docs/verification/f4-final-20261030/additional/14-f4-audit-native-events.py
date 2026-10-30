"""Read-only native evidence audit. Never opens/runs Qt or infers image content.

--structural-only permits exercising the event parser on historical offscreen
receipts. Its result cannot be promoted to current native/visual acceptance.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CASES = ('energy', 'geometry', 'material', 'layer', 'boolean', 'stale', 'source', 'history',
         'project', 'scenario', 'wizard', 'scan', 'backend')
NAVIGABLE = set(CASES) - {'stale', 'backend'}
HOST_SHA = 'aa59397f4711c17f7edcc9a39d927c9c4197e124d98ccafb58b8d1d886c11d6c'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def valid_sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def audit(args):
    evidence = args.evidence_root.resolve()
    failures, caveats, pairs, discarded, pending = [], [], [], [], []
    sources = []

    def check(condition, message):
        if not condition:
            failures.append(message)

    def load(name, required=True):
        path = evidence / name
        if not path.is_file():
            if required:
                failures.append('Missing evidence: ' + name)
            return None
        raw = path.read_bytes()
        sources.append({'path': str(path), 'bytes': len(raw), 'sha256': sha(raw)})
        return json.loads(raw)

    identity = load('identity.json') or {}
    final_state = load('state.json', not args.structural_only) or {}
    host_exit = load('exit.json', not args.structural_only) or {}
    launcher = None
    if not args.structural_only:
        launcher_path = args.launcher or evidence / 'launcher.json'
        if launcher_path.is_file():
            launcher = read_json(launcher_path)
            sources.append({'path': str(launcher_path), 'bytes': launcher_path.stat().st_size,
                            'sha256': sha(launcher_path.read_bytes())})
        else:
            failures.append('Missing independent launcher process exit receipt')

    path = evidence / 'events.jsonl'
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_bytes()
    sources.append({'path': str(path), 'bytes': len(raw), 'sha256': sha(raw)})
    events = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
    check([row.get('sequence') for row in events] == list(range(1, len(events) + 1)), 'Event sequence must be unique, monotonic and complete from 1')
    check(all(row.get('visual_acceptance') == 'not_claimed' for row in events), 'Host events may not self-claim visual acceptance')
    prepared = []
    for row in events:
        kind, case, sequence = row.get('kind'), row.get('case'), row.get('sequence')
        if kind == 'state_prepared':
            check(case in CASES, f'Unknown prepared case {case}')
            check(valid_sha(row.get('business_sha256')), f'Missing business hash at state {sequence}')
            prepared.append(case)
        elif kind == 'product_input_before':
            check(valid_sha(row.get('before')), f'Invalid before hash at {sequence}')
            check(row.get('event_type') in (2, 4, 6), f'Unsupported input event {sequence}')
            pending.append(row)
        elif kind == 'product_input_after':
            candidates = [before for before in pending if before.get('case') == case and before.get('before') == row.get('before')]
            if len(candidates) != 1:
                failures.append(f'After {sequence} has {len(candidates)} matching pending before records; ambiguous/unmatched pairing is not accepted')
                continue
            before = candidates[0]
            pending.remove(before)
            check(row.get('model_unchanged') is True and row.get('before') == row.get('after'), f'Business state changed for {case} at {sequence}')
            check(not any(item.get('kind') == 'state_prepared' for item in events[before['sequence']:sequence-1]),
                  f'Pair {before["sequence"]}/{sequence} crossed fixture replacement')
            presentation = row.get('presentation', {})
            pair = {'case': case, 'before_sequence': before['sequence'], 'after_sequence': sequence,
                    'event_type': before.get('event_type'), 'control': before.get('control'),
                    'business_sha256': row.get('after'), 'model_unchanged': row.get('model_unchanged'),
                    'before_presentation': before.get('presentation'), 'after_presentation': presentation}
            pairs.append(pair)
        elif kind == 'product_input_discarded':
            candidates = [before for before in pending if before.get('case') == row.get('originating_case')]
            if len(candidates) != 1:
                failures.append(f'Discard {sequence} has {len(candidates)} pending origin candidates; do not guess missing generation identity')
                continue
            before = candidates[0]
            pending.remove(before)
            check(row.get('reason') == 'fixture_replaced_or_closed', f'Unknown discard reason at {sequence}')
            discarded.append({'before_sequence': before['sequence'], 'discard_sequence': sequence,
                              'originating_case': row.get('originating_case'),
                              'originating_generation': row.get('originating_generation'),
                              'current_generation': row.get('current_generation')})
        elif kind in ('preparation_failed', 'host_exception'):
            failures.append(f'Host failure event {sequence}: {kind}')
    check(not pending, 'Unmatched before inputs remain: ' + str([row['sequence'] for row in pending]))
    check(set(prepared) == set(CASES), 'Prepared cases differ from complete 13-case set')

    def completed_target(pair):
        case, after = pair['case'], pair['after_presentation']
        status = after.get('status') or ''
        highlighted = bool(after.get('highlighted'))
        fields = {'energy': 'energy', 'material': 'density', 'layer': 'thickness', 'boolean': 'operation',
                  'project': 'executable', 'scenario': 'pore_fraction', 'wizard': 'target_material', 'scan': 'values'}
        if case == 'geometry':
            return after.get('geometry_cell') == [2, 6] and after.get('config_tab') == 1 and highlighted and 'size' in status
        if case == 'material':
            return after.get('material_row') == 1 and highlighted and fields[case] in status
        if case == 'layer':
            return after.get('layer_row') == 1 and highlighted and fields[case] in status
        if case == 'boolean':
            return after.get('boolean_cell') == [0, 3] and highlighted and fields[case] in status
        if case in ('source', 'history'):
            return after.get('source_visible') is True and 'mystery' in (after.get('source_text') or '') and (
                '快照一致' in status if case == 'source' else '当前文件已改变或不可用' in status)
        if case == 'project':
            return after.get('main_page') != (pair['before_presentation'] or {}).get('main_page') and highlighted and fields[case] in status
        if case == 'scenario':
            return after.get('scenario_advanced') is True and highlighted and fields[case] in status
        if case == 'wizard':
            return after.get('wizard_page') == 1 and highlighted and fields[case] in status
        return case in fields and highlighted and fields[case] in status

    coverage = {case: [pair['after_sequence'] for pair in pairs if pair['case'] == case and completed_target(pair)]
                for case in sorted(NAVIGABLE)}
    for case, sequences in coverage.items():
        check(bool(sequences), f'No matched completed target receipt for {case}; preparation/selection alone is insufficient')

    started = [row for row in events if row.get('kind') == 'actual_backend_started']
    finished = [row for row in events if row.get('kind') == 'actual_backend_finished']
    check(len(started) == len(finished) and len(finished) >= 1, 'Actual Inspect start/finish count differs or missing')
    for start, finish in zip(started, finished):
        check(start['sequence'] < finish['sequence'], 'Inspect finish precedes start')
        check(start.get('program') == finish.get('program') == identity.get('executable'), 'Inspect executable identity differs')
        check(start.get('arguments') == finish.get('arguments'), 'Inspect arguments changed between start/finish')
        argv = finish.get('arguments', [])
        check('--inspect-run' in argv and '--config' in argv and '--macro' in argv and '--output' in argv,
              'Real Inspect command not recorded with required inputs')
        check(finish.get('exit_code') not in (0, None) and finish.get('exit_status') == 0, 'Expected normal nonzero Inspect refusal is missing')
        check(finish.get('simulation_requested') is False and start.get('simulation_requested') is False,
              'Inspect event must explicitly not request simulation')
        check(finish.get('runner_running') is False and finish.get('run_summary_files') == [], 'Inspect unexpectedly ran simulation or generated run summary')
        stderr = finish.get('stderr')
        check(isinstance(stderr, str) and 'conflicts with an explicit CLI lock' in stderr, 'Expected CLI-lock backend raw refusal missing')
        check(finish.get('executable_sha256') == start.get('executable_sha256') == identity.get('executable_sha256'), 'Inspect executable SHA does not match host identity')
        stderr_file = evidence / 'inspect.stderr'
        if stderr_file.is_file():
            check(sha(stderr_file.read_bytes()) == finish.get('stderr_sha256'), 'Inspect raw stderr bytes differ from receipt')
            check(stderr_file.read_bytes().decode('utf-8', errors='replace') == stderr, 'Decoded stderr differs from original raw file')
        else:
            failures.append('Missing actual inspect.stderr raw file')
    if final_state.get('case') == 'backend':
        records = final_state.get('records', [])
        check(bool(records), 'Backend final state lacks raw diagnostic')
        if records and finished:
            check(records[0].get('raw_message') == finished[-1].get('stderr'), 'GUI raw message differs from backend stderr')
            check(records[0].get('location') is None and records[0].get('source') is None, 'Backend raw diagnostic acquired a fabricated location')
    else:
        caveats.append('Final state is not backend: inspect raw GUI record requires the per-step native observation/state, not invented reconstruction')

    check(identity.get('host_version') == 2 and identity.get('host_sha256') == args.expected_host_sha,
          'Host identity does not match independently reviewed v2 bytes')
    check(identity.get('capabilities_exit') == 0, 'Backend capabilities failed')
    if not args.structural_only:
        check(bool(args.expected_head) and identity.get('gui_head') == args.expected_head, 'Native GUI HEAD differs from explicitly expected freeze')
        check(identity.get('gui_status') == '', 'Native GUI checkout not recorded clean')
        check(bool(args.expected_exe_sha) and identity.get('executable_sha256') == args.expected_exe_sha, 'Native executable SHA differs from expected final build')
        check(identity.get('mode') == 'native_observation_pending', 'Offscreen mode cannot count as native')
        check(host_exit.get('exit_code') == 0 and host_exit.get('close_requested') is True and host_exit.get('event_loop_used') is True,
              'Host requested-return receipt missing successful event-loop close')
        check(host_exit.get('exit_code_scope') == 'python_requested_return; launcher_must_verify_actual_process_exit',
              'Host exit receipt must distinguish requested return from actual process exit')
        check(any(row.get('kind') == 'main_window_close_requested' for row in events), 'No main-window close event')
        check(any(row.get('kind') == 'host_finished' and row.get('exit_code') == 0 for row in events), 'No host-finished success event')
        if launcher is not None:
            check(launcher.get('process_exit_code') == 0 and launcher.get('normal_completion') is True,
                  'Independent launcher did not confirm actual normal process exit 0')
            check(launcher.get('commit') == args.expected_head, 'Launcher commit does not match expected freeze')
    else:
        caveats.append('STRUCTURAL ONLY: historical offscreen event corpus; current freeze, native launcher and visible acceptance intentionally not evaluated')

    images = []
    screenshots = args.screenshots_root or evidence / 'native'
    if screenshots.exists():
        for path in sorted(screenshots.rglob('*')):
            if path.is_file() and path.suffix.lower() in ('.png', '.jpg', '.jpeg'):
                images.append({'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path.read_bytes()),
                               'image_content_observed_by_this_script': False})
    caveats.extend([
        '80 ms samples prove only captured before/after equality; long-held or suppressed rapid input needs observed completed target state.',
        'Generic button/control names do not prove Locate versus Source; exact key is not logged, so Enter/Esc gesture identity needs the native action record.',
        'stale/backend deliberately have disabled navigation; do not require a fake successful navigation pair or infer disabled appearance from event counts.',
        'Cell indices/highlights/source-visible flags never prove cell visibility, clipping, readable text, readonly behavior or actual screenshots.',
        'Image inventory is SHA bookkeeping only. Independent image observation remains required for all 13 native states.',
    ])
    return {'schema': 'f4_native_event_independent_audit_v1', 'audit_utc': datetime.now(timezone.utc).isoformat(),
            'scope': 'historical_offscreen_structure_only' if args.structural_only else 'native_mechanical_evidence_only',
            'evidence_root': str(evidence), 'expected_head': args.expected_head, 'identity': identity,
            'event_count': len(events), 'kinds': dict(Counter(row.get('kind') for row in events)),
            'prepared_case_counts': dict(Counter(prepared)), 'matched_pairs': pairs, 'discarded_callbacks': discarded,
            'unmatched_before_sequences': [row['sequence'] for row in pending], 'completed_target_coverage': coverage,
            'inspect_count': len(finished), 'host_requested_return': host_exit, 'actual_launcher': launcher,
            'sources': sources, 'image_inventory': images, 'failures': failures, 'caveats': caveats,
            'mechanical_checks_passed': not failures, 'native_visual_acceptance': 'not_evaluated_requires_actual_image_observation',
            'stage_closure': 'not_claimed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--screenshots-root', type=Path)
    parser.add_argument('--launcher', type=Path)
    parser.add_argument('--expected-head')
    parser.add_argument('--expected-exe-sha')
    parser.add_argument('--expected-host-sha', default=HOST_SHA)
    parser.add_argument('--structural-only', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    target = options.output.resolve()
    assert target.is_relative_to((ROOT / 'out').resolve()), 'Audit outputs must stay in out'
    result = audit(options)
    with target.open('xb') as stream:
        stream.write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({key: result[key] for key in ('scope', 'event_count', 'prepared_case_counts', 'mechanical_checks_passed', 'failures', 'native_visual_acceptance')}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['mechanical_checks_passed'] else 1)
