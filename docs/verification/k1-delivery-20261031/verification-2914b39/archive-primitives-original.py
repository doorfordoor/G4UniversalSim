"""Prepare/copy separately identified fourth/fifth/sixth history, never decide K1 acceptance.

No arguments: print the plan only.  Archive ONLY after the parent supplies the
final pinned source list and explicitly invokes --execute --release-spec FILE,
or --execute --fourth-ready-selection for the named final fourth receipts.
This file does not run tests, gates, browsers or reviewers; it reads existing
receipts and copies evidence into one new, exclusive destination. A failed copy
is retained as incomplete; it is never deleted, resumed or overwritten.

Release-spec schema k1_archive_release_v1 (all paths workspace-relative):
  head: HEAD; final_inputs_ready: true
  audits: {windows, ci, native, i1, review_coverage: PIN plus
           complete: true, outcome: passed|pending|failed|gap_retained}
  windows_report: PIN
  windows_gates: [PIN plus exit_code]             # three existing strict gates
  ci_artifact_apis: [PIN, PIN]                    # final Linux and M0 APIs
  ci_official_zips: [PIN, PIN, PIN, PIN]           # original official ZIP bytes
  ci_control_files: [PIN plus run_group, role]     # linux/m0 run_api/jobs_api/logs
  ci_reports: [PIN plus suite, profile, ...]       # exactly twelve report.json
  ci_gates: [PIN, ...]                           # original aggregate or per-profile gate receipts
  ci_gate_coverage: [[suite, profile], ...]        # twelve covered strict/F5 profiles; no invented exits
  extra_files: [PIN plus destination, ...]        # final explicit review selections
  extra_trees: [{path, destination, scope}, ...]   # explicit I1/reference raw trees
  diagnostic_files: [PIN plus destination, scope:fourth_original_failure]
  next_candidate_references: [PIN plus scope]      # references ONLY, no source/result copy
  native_records: [PIN plus role, record_id]      # mandatory for generation 5/6; exact actions coverage
  final_delivery_report: PIN plus final:true      # OPTIONAL; draft excluded otherwise
PIN = {path: "...", sha256: "64 raw-byte hex", bytes: optional integer}.
Final reviewer/audit names need not be guessed now: the parent pins their exact
files after their writers finish. See PLAN, REQUIRED_SELECTION and main().
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BUILDER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
HEAD = '8213ced419c8c6bca512bf8413b674c1265cf3bf'
GENERATION = 4
KNOWN_HEADS = {4: HEAD, 5: 'f9a9ddbfcabe69067707a5a209caff005748f510'}
SOURCE = ROOT / 'out/verification/k1-8213ced'
DEST = ROOT / 'out/collab/k1-delivery-staging/verification-8213ced'
CHUNK = 2 * 1024 * 1024
LARGE = 16 * 1024 * 1024
READ_PINS = {}
LAYERS = ('static', 'gui', 'backend', 'integration')
CI_COMBINATIONS = {(suite, layer) for suite in ('linux-11.3.2', 'linux-11.4.3') for layer in LAYERS} | {
    (suite, layer) for suite in ('m0-windows', 'm0-ubuntu') for layer in ('static', 'gui')}
AUDITS = ('windows', 'ci', 'native', 'i1', 'review_coverage')
DRAFT = 'out/collab/k1-delivery-report-draft.md'
REQUIRED_SELECTION = {
    'out/collab/k1-model-ledger.json': 'review/model-ledger.json',
    'out/collab/k1-checkout-boundary-8213ced.json': 'identity/checkout-boundary.json',
    'out/collab/k1-fourth-integration-receipt.json': 'identity/integration-receipt.json',
    'out/collab/k1-fourth-new-test-integration.json': 'identity/new-test-integration.json',
    'out/collab/k1-fourth-windows-review-freeze-receipt.json': 'identity/independent-freeze-receipt.json',
    'out/collab/k1-8213ced-build.log': 'build/build-original.log',
    'out/collab/k1-review-coverage-map.json': 'review/coverage-map.json',
    'out/collab/k1-review-coverage-map.md': 'review/coverage-map.md',
    'out/collab/k1-bundle-review-upstream-incident.json': 'review/gaps/bundle-upstream-incident.json',
    'out/collab/k1-relocation-candidate/independent-review-incident.json': 'review/gaps/relocation-upstream-incident.json',
    'out/collab/k1-relocation-independent-validation/late-reparse-exits.json': 'review/gaps/partial-evidence/late-reparse-exits.json',
    'out/collab/k1-relocation-independent-validation/late-reparse-base.log': 'review/gaps/partial-evidence/late-reparse-base.log',
    'out/collab/k1-relocation-independent-validation/late-reparse-candidate.log': 'review/gaps/partial-evidence/late-reparse-candidate.log',
    'out/collab/k1-contract-independent.md': 'review/scoped-history/contract-independent.md',
    'out/collab/k1-core-independent-review.md': 'review/scoped-history/core-independent.md',
    'out/collab/k1-bundle-independent-review.md': 'review/scoped-history/bundle-partial-review.md',
    'out/collab/k1-final-adapter-test-diff-independent.md': 'review/scoped-history/adapter-test-diff.md',
    'out/collab/k1-cpp-launch-portability-independent.md': 'review/scoped-history/cpp-launch-portability.md',
    'out/collab/k1-c644bb1-windows-independent-history-scope-review.md': 'review/scoped-history/history-display.md',
    'out/collab/k1-cancel-ownership-independent.md': 'review/scoped-history/cancel-ownership.md',
    'out/collab/k1-terminal-test-defaults-independent.md': 'review/scoped-history/terminal-defaults.md',
    'out/collab/k1-win-ci-three-smokes-independent-review.md': 'review/scoped-history/three-smokes.md',
    'out/collab/k1-i1-independent.md': 'review/scoped-history/i1-independent.md',
    'out/collab/k1-i1-delivery.md': 'review/scoped-history/i1-delivery.md',
    'out/collab/k1-panel-delivery.md': 'design/panel-delivery.md',
    'out/collab/k1-workflow-delivery.md': 'design/scoped-history/workflow-delivery.md',
    'out/collab/k1-bundle-delivery.md': 'design/scoped-history/bundle-delivery.md',
    'out/collab/k1-cli-delivery.md': 'design/scoped-history/cli-delivery.md',
    'out/collab/k1-adapters-delivery.md': 'design/scoped-history/adapters-delivery.md',
    'out/collab/k1-deepseek-response.json': 'design/deepseek-response-original.json',
    'docs/collab/outbox/20261031-deepseek-k1-panel.md': 'design/deepseek-k1-panel.md',
    'docs/collab/outbox/20261031-k1-panel-delivery.md': 'design/panel-integration-receipt.md',
    'docs/collab/inbox/20261031-k1-execution.md': 'design/execution-contract.md',
}
PLAN = {
    'head': HEAD, 'destination': str(DEST), 'mode_now': 'preparation_only',
    'permitted_overall_states': ['pending', 'verification_complete_but_K1_unaccepted'],
    'resource_boundary_independent_review_gap': 'upstream_refused; remains open; not retried',
    'phase_complete': False,
    'windows': 'original report/top-level logs plus all nested case originals in ZIP',
    'ci': 'four unmodified official ZIPs, APIs/run/jobs/logs, twelve reports/top-level logs and existing gates',
    'visible': 'entire tree; all 17 images/actions/identity/exit/records/F1 inputs and outputs',
    'large_data': '>=16MiB native/replay files losslessly zipped, including cancelled-run CSV; small CSV stays in its original tree',
    'replay': 'formal replay-cli.log, replay-cli-receipt.json and entire replay-cli tree',
    'identity': 'build/cap/frozen manifest, full frozen Git tree/blob SHA256 index, checkout receipt',
    'reviews': 'exact required selection plus final pinned audits/I1/native/coverage and explicit supplements',
    'draft_delivery_report': 'excluded until parent explicitly marks updated report final in release spec',
    'failed_archives': 'three existing archives are read-only references; never copied/changed by this tool',
    'exe_policy': 'no new standalone EXE or new ZIP EXE member; original official ZIP bytes preserved',
    'required_selection': REQUIRED_SELECTION,
    'no_execution_now': 'Wait for parent final Windows/CI/native/I1/audit readiness; then --execute with pinned release spec',
    'generation_scope': 'fourth freeze evidence, not the final K1 version; fifth frozen, sixth pending',
    'archive_kind': 'historical_fourth_freeze_not_final_K1',
    'known_fourth_finding': 'accepted P3: cancelled action may expose inputs_changed reason; fix/regression planned out-only, not applied to frozen 8213ced',
    'next_candidate_sources': 'excluded; fourth-original failed diagnostics can be copied, next candidate receipts can only be explicitly referenced',
    'latest_final_target': 'sixth freeze pending; fifth is not the final K1 release',
    'fifth_known_forced_end': '576efbdcf8434907bf0206d1de976f16: cancelled, killed, exit62097, no summary; never count as successful events',
}


def configure_generation(spec):
    """One builder, disjoint immutable destinations; no history relabelling."""
    global HEAD, SOURCE, DEST, GENERATION, REQUIRED_SELECTION
    head = spec.get('head', '')
    generation = spec.get('generation', 4 if head == KNOWN_HEADS[4] else 5 if head == KNOWN_HEADS[5] else 6)
    require(generation in (4, 5, 6) and re.fullmatch(r'[0-9a-f]{40}', head), 'Explicit frozen generation/head required')
    if generation in KNOWN_HEADS:
        require(head == KNOWN_HEADS[generation], 'Known generation identity mismatch')
    else:
        require(head not in KNOWN_HEADS.values(), 'Sixth identity must not relabel a fourth/fifth frozen head')
    HEAD, GENERATION = head, generation
    SOURCE = ROOT / ('out/verification/k1-' + head[:7])
    DEST = ROOT / ('out/collab/k1-delivery-staging/verification-' + head[:7])
    if generation != 4:
        REQUIRED_SELECTION = {path: dest for path, dest in REQUIRED_SELECTION.items()
            if not any(token in path for token in ('k1-checkout-boundary-8213ced', 'k1-fourth-integration',
                'k1-fourth-new-test', 'k1-fourth-windows-review-freeze', 'k1-8213ced-build'))}
        prefix = 'fifth' if generation == 5 else 'sixth'
        REQUIRED_SELECTION['out/collab/k1-' + prefix + '-windows-review-freeze-receipt.json'] = 'identity/independent-freeze-receipt.json'
        REQUIRED_SELECTION['out/collab/k1-' + head[:7] + '-build.log'] = 'build/build-original.log'
        REQUIRED_SELECTION['out/collab/k1-cancel-reason-independent.json'] = 'review/scoped-history/cancel-reason-independent.json'
        REQUIRED_SELECTION['out/collab/k1-cancel-reason-independent.md'] = 'review/scoped-history/cancel-reason-independent.md'
        REQUIRED_SELECTION['out/collab/k1-parent-fourth-addendum-review.json'] = 'review/historical-fourth/parent-addendum-review.json'


def native_records(spec):
    """Preserve actual records and absence facts, never synthesize a summary."""
    selected = []
    items = spec.get('native_records', [])
    roots = [no_link(SOURCE / 'visible')]
    for tree in spec.get('extra_trees', []):
        if tree.get('scope') == 'native_observation_supplement':
            base = source(tree['path'])
            require(base.is_relative_to(SOURCE.resolve()) and base not in roots,
                    'Native supplement must be a distinct explicitly selected generation subtree')
            identity = load(base / 'identity.json')
            require(identity['head'] == HEAD and identity['backend_sha256'] == load(SOURCE / 'build-identity.json')['backend_sha256'],
                    'Supplement native identity differs from frozen generation')
            roots.append(base)
    if GENERATION >= 5:
        require(isinstance(items, list) and items, 'Fifth/sixth archive requires explicit pinned native_records; no empty derived index')
    for item in items:
        path = pin(item)
        matching_roots = [base for base in roots if path.is_relative_to(base)]
        require(len(matching_roots) == 1, 'Native record must belong to one explicit ordinary/supplement root')
        data = load(path)
        require(item.get('role') and item.get('record_id') == data.get('record_id'), 'Explicit native role/record identity required')
        fact = {'record': item['path'], 'record_sha256': item['sha256'], 'role': item['role'], 'record_id': data['record_id'],
            'source_root': matching_roots[0].relative_to(ROOT).as_posix(),
            'run_id': data.get('run_id'), 'action': data.get('action'), 'level': data.get('level'), 'revision': data.get('revision'),
            'status': data.get('status'), 'reason': data.get('reason'), 'exit_code': data.get('exit_code'),
            'result_original': data.get('result')}
        if GENERATION == 5 and item['role'] == 'forced_end':
            require(data['record_id'] == '576efbdcf8434907bf0206d1de976f16' and data['status'] == 'cancelled'
                and data.get('exit_code') == 62097 and data.get('result', {}).get('state') == 'killed',
                'Fifth forced-end original facts differ')
            summary = no_link(Path(data['output_dir']) / 'run_summary.txt')
            require(summary.is_relative_to(SOURCE.resolve()) and not summary.exists(), 'Forced end must not acquire a fabricated summary')
            fact.update(summary_observed='absent', count_as_completed_run=False)
        selected.append(fact)
    if GENERATION >= 5:
        ids = [row['record_id'] for row in selected]
        require(len(ids) == len(set(ids)), 'Duplicate native record identity')
        for base in roots:
            group = [item for item in items if pin(item).is_relative_to(base)]
            actions_path = no_link(base / 'actions.jsonl')
            raw = actions_path.read_bytes()
            actions_sha = hashlib.sha256(raw).hexdigest()
            require(READ_PINS.get(str(actions_path), actions_sha) == actions_sha, 'Native actions changed during selection')
            READ_PINS[str(actions_path)] = actions_sha
            actions = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
            require(group and len(actions) == len(group)
                    and {row['record_id'] for row in actions} == {item['record_id'] for item in group},
                    'Explicit native_records must cover every root terminal action exactly once')
            for item in group:
                data = load(pin(item))
                require(next(row for row in actions if row['record_id'] == data['record_id']) == data,
                        'Native actions projection differs from pinned original record')
    if GENERATION == 5:
        require({'forced_end', 'normal_cancel', 'recovery'}.issubset({item['role'] for item in items}),
                'Fifth final selection needs explicit forced-end, normal-cancellation and recovery records')
    return selected


def fourth_ready_selection(generation=4):
    """Pin named final fourth/fifth receipts only after all writers finish."""
    require(generation in (4, 5), 'Sixth selection needs an explicit release-spec with its final identity')
    configure_generation({'generation': generation, 'head': KNOWN_HEADS[generation]})
    prefix = 'fourth' if generation == 4 else 'fifth'
    def item(value, **fields):
        path = no_link(Path(value) if Path(value).is_absolute() else ROOT / value)
        return {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path),
                'bytes': path.stat().st_size, **fields}
    collab, ci = ROOT / 'out/collab', SOURCE / 'ci'
    audit_paths = {
        'windows': collab / ('k1-' + prefix + '-windows-review-audit.json'),
        'ci': ci / 'review-result.json', 'native': collab / ('k1-' + prefix + '-native-audit.json'),
        'i1': collab / ('k1-i1-acceptance-' + prefix + '.json'), 'review_coverage': collab / 'k1-review-coverage-map.json'}
    data = {name: load(path) for name, path in audit_paths.items()}
    require(data['windows'].get('status') == 'passed_strict_report_and_baseline_audit'
        and data['windows'].get('failed_checks') == [], 'Windows final audit is not ready')
    require(data['ci'].get('automation_review_passed') is True and data['ci'].get('terminal') is True,
            'CI final audit is not ready')
    if generation == 4:
        require(data['native'].get('status') == 'ordinary_evidence_verified_with_P3_public_reason_finding'
            and data['native'].get('failed_checks') == [], 'Fourth ordinary native audit is not ready')
    else:
        require(data['native'].get('status') == 'targeted_native_evidence_verified_P3_normal_delivery_fixed_not_overall_acceptance'
            and data['native'].get('head') == HEAD, 'Fifth targeted native audit is not ready')
    expected_i1 = ('fourth_I1_defined_scope_evidence_verified_not_K1_overall_acceptance' if generation == 4
                   else 'fifth_I1_defined_scope_evidence_verified_not_K1_acceptance')
    require(data['i1'].get('status') == expected_i1,
            prefix + ' I1 final receipt is not ready; pin its actual scope before execution')
    audits = {name: item(path, complete=True, outcome='gap_retained' if name == 'review_coverage' else 'passed')
              for name, path in audit_paths.items()}
    reports = sorted((SOURCE / 'windows').glob('*/report.json'))
    require(len(reports) == 1, 'Select the unique ' + prefix + ' Windows report explicitly')
    windows_gates = load(collab / ('k1-' + prefix + '-windows-review-gates.json'))
    win = [item(row['log'], exit_code=row['exit_code'], gate_name=row['name']) for row in windows_gates]
    require(all(selected['sha256'] == row['log_sha256'] for selected, row in zip(win, windows_gates)),
            'Existing Windows gate-log SHA differs from its recorded receipt')
    independent = load(ci / 'independent-profiles.json')
    require(independent.get('checks_passed') is True and independent.get('report_count') == 12,
            'CI aggregate strict/F5 record incomplete')
    suites = {'linux-evidence-11.3.2': 'linux-11.3.2', 'linux-evidence-11.4.3': 'linux-11.4.3',
              'm0-report-windows-latest': 'm0-windows', 'm0-report-ubuntu-latest': 'm0-ubuntu'}
    ci_reports = []
    for row in independent['reports']:
        require(row['strict_gate'] == row['baseline_strict_gate'] == 'passed', 'CI aggregate gate did not pass')
        selected = item(row['path'], suite=suites[row['artifact']], profile=row['profile'])
        require(selected['sha256'] == row['report_sha256'], 'CI report SHA differs from final independent receipt')
        ci_reports.append(selected)
    apis = [item(ci / name) for name in ('linux-artifacts.json', 'm0-artifacts.json')]
    zips = [item(ci / (row['name'] + '.zip')) for api in apis for row in load(pin(api))['artifacts']]
    controls = []
    for run in ('linux', 'm0'):
        controls.extend([item(ci / (run + '-run.json'), run_group=run, role='run_api'),
                         item(ci / (run + '-jobs.json'), run_group=run, role='jobs_api')])
        for job in load(ci / (run + '-jobs.json'))['jobs']:
            controls.append(item(ci / ('job-' + str(job['id']) + '.log'), run_group=run, role='logs'))
    for name in ('audit.json', 'audit.log', 'independent-profiles.json', 'independent-profiles.log',
                 'pipeline-result.json', 'review-result.json', 'REVIEW.md', 'evidence-manifest.json',
                 'prepare.log', 'collect.log', 'plan.json') + (('previous-failure-transitions.json',)
                 if generation == 4 else ('p3-evidence.json', 'p3-final-two-files.diff')):
        controls.append(item(ci / name, role='aggregate_original', run_group='both'))
    audit_operation = next(r for r in load(ci / 'pipeline-result.json')['operations'] if r['operation'] == 'audit')
    require(audit_operation['exit_code'] == 0, 'Recorded aggregate CI audit process failed')
    gates = [item(ci / 'audit.json', exit_code=audit_operation['exit_code'], scope='actual aggregate audit process; not invented per-profile exits'),
             item(ci / 'independent-profiles.json', scope='existing aggregate strict and F5 profile results')]
    extra_names = ('k1-' + prefix + '-windows-review-audit.md', 'k1-' + prefix + '-windows-review-gates.json',
        'k1-' + prefix + '-windows-review-method.md', 'k1-' + prefix + '-native-audit.md', 'k1-i1-acceptance-' + prefix + '.md',
        'k1-final-adapters-independent.json', 'k1-final-adapters-independent.md',
        'k1-final-frontend-independent.json', 'k1-final-frontend-independent.md')
    extras = [item(collab / name, destination='review/final/' + name) for name in extra_names]
    diagnostics = [item(collab / 'k1-cancel-reason-candidate/old-negative.log',
        destination='review/diagnostics/fourth-cancel-reason-old-negative.log', scope='fourth_original_failure')]
    for path in sorted((collab / 'k1-cancel-reason-candidate/old-negative').rglob('*')):
        if path.is_file() and path.suffix.lower() in ('.json', '.log', '.txt', '.md'):
            rel = path.relative_to(collab / 'k1-cancel-reason-candidate/old-negative').as_posix()
            diagnostics.append(item(path, destination='review/diagnostics/fourth-cancel-reason/' + rel,
                                    scope='fourth_original_failure'))
    spec = {'schema': 'k1_archive_release_v1', 'generation': generation, 'head': HEAD, 'final_inputs_ready': True,
        'selection_authority': 'parent historical generation selection; execute only with final inputs and explicit --execute',
        'audits': audits, 'windows_report': item(reports[0]), 'windows_gates': win,
        'ci_artifact_apis': apis, 'ci_official_zips': zips, 'ci_control_files': controls,
        'ci_reports': ci_reports, 'ci_gates': gates,
        'ci_gate_coverage': [[r['suite'], r['profile']] for r in ci_reports],
        'extra_files': extras, 'diagnostic_files': diagnostics,
        'next_candidate_references': [item(collab / 'k1-cancel-reason-independent.json',
            scope='fifth narrow cancellation fix; not fourth verification or candidate source')],
        'known_findings': [{'severity': 'P2', 'scope': 'fourth frontend review', 'fact': 'completed command preview can show editor cwd', 'next': 'sixth freeze pending'},
            {'severity': 'P3', 'scope': 'fourth frontend review', 'fact': 'producer pending shown as unobserved', 'next': 'sixth freeze pending'}]}
    if generation == 5:
        roles = {'576efbdcf8434907bf0206d1de976f16': 'forced_end',
                 '4aec0e6cd38a47e3a286be9e5693aaf2': 'normal_cancel',
                 '5528e27cb3f94c70bf3e16a9de88d8b4': 'recovery'}
        require(len(data['native']['records']) == 3 and {row['record_id'] for row in data['native']['records']} == set(roles),
                'Fifth independent audit must identify the three exact original records')
        spec['native_records'] = []
        for row in data['native']['records']:
            selected = item(row['record_path'], record_id=row['record_id'], role=roles[row['record_id']])
            require(selected['sha256'] == row['record_sha256'], 'Fifth native record differs from independent audit')
            spec['native_records'].append(selected)
        spec['native_screenshot_count'] = 6
        spec['windows_gate_receipt'] = item(collab / 'k1-fifth-windows-review-gates.json')
        spec['prior_replay_reference'] = item(ROOT / 'out/collab/k1-delivery-staging/verification-8213ced/replay/replay-cli-receipt.json',
            scope='fourth actual GUI package replay only; not rerun for fifth')
        spec['next_candidate_references'] = []
    return spec


def require(value, message):
    if not value:
        raise ValueError(message)


def raw_json(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode('utf-8')


def relative(value):
    require(isinstance(value, str) and value and '\\' not in value and ':' not in value,
            'Expected portable relative path: ' + str(value))
    require(not PurePosixPath(value).is_absolute() and all(p not in ('', '.', '..') for p in value.split('/')),
            'Unsafe relative path: ' + value)
    return Path(*PurePosixPath(value).parts)


def no_link(path):
    path = Path(path)
    require(path.is_absolute(), 'Expected absolute evidence path')
    # Inspect lexical parents before canonicalizing, including on Windows aliases.
    for node in (path, *path.parents):
        if node.exists() or node.is_symlink():
            info = node.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    'Linked/reparse evidence is not copied: ' + str(node))
    result = path.resolve()
    require(result.is_relative_to(ROOT), 'Evidence outside owning workspace: ' + str(path))
    return result


def source(value):
    return no_link(ROOT / relative(value))


def digest(path):
    checksum = hashlib.sha256()
    with no_link(path).open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            checksum.update(block)
    return checksum.hexdigest()


def load(path):
    path = no_link(path)
    raw = path.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    require(READ_PINS.get(str(path), checksum) == checksum, 'Previously read evidence changed: ' + str(path))
    READ_PINS[str(path)] = checksum
    return json.loads(raw)


def pin(item):
    require(isinstance(item, dict) and re.fullmatch(r'[0-9a-f]{64}', str(item.get('sha256', ''))), 'Missing raw SHA pin')
    path = source(item['path'])
    require(path.is_file() and digest(path) == item['sha256'], 'Pinned source changed/missing: ' + str(path))
    require(READ_PINS.get(str(path), item['sha256']) == item['sha256'], 'Conflicting evidence pin')
    READ_PINS[str(path)] = item['sha256']
    if 'bytes' in item:
        require(path.stat().st_size == item['bytes'], 'Pinned source size mismatch')
    return path


def files_below(base):
    base = no_link(base)
    require(base.is_dir(), 'Missing selected tree: ' + str(base))
    files, directories = [], []
    for directory, dirs, leaves in os.walk(base, followlinks=False):
        directories.append(no_link(Path(directory)))
        for name in dirs:
            no_link(Path(directory) / name)
        for name in leaves:
            path = no_link(Path(directory) / name)
            require(path.is_file() and stat.S_ISREG(path.stat().st_mode), 'Nonregular evidence file')
            files.append(path)
    return sorted(files), sorted(directories)


def compare(first, second):
    checksum, size = hashlib.sha256(), 0
    while True:
        left, right = first.read(CHUNK), second.read(CHUNK)
        require(left == right, 'Archive/source byte comparison failed')
        if not left:
            return checksum.hexdigest(), size
        checksum.update(left)
        size += len(left)


class Archive:
    def __init__(self, allow_final_report=False):
        self.records, self.excluded, self.generated = [], [], []
        self.targets, self.trees = set(), []
        self.allow_final_report = allow_final_report

    def target(self, name):
        path = DEST / relative(name)
        no_link(path.parent)
        require(path.resolve().is_relative_to(DEST.resolve()), 'Destination escaped archive')
        require(name not in self.targets and not path.exists(), 'Refusing overwrite/collision: ' + name)
        require(path.suffix.lower() != '.exe', 'No new standalone EXE destination')
        self.targets.add(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write(self, name, raw):
        path = self.target(name)
        with path.open('xb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        require(path.read_bytes() == raw, 'Generated archive metadata verification failed')
        self.generated.append({'destination': name, 'bytes': len(raw), 'sha256': digest(path)})

    def copy(self, path, name):
        path = no_link(path)
        require(path != source(DRAFT) or self.allow_final_report, 'Pending delivery draft is not in final selection')
        if path.suffix.lower() == '.exe':
            self.excluded.append({'source': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size,
                'sha256': digest(path), 'reason': 'no additional EXE copy; original retained at source'})
            return
        target = self.target(name)
        checksum = hashlib.sha256()
        with path.open('rb') as original, target.open('xb') as output:
            for block in iter(lambda: original.read(CHUNK), b''):
                checksum.update(block)
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        with path.open('rb') as original, target.open('rb') as archived:
            actual, size = compare(original, archived)
        require(actual == checksum.hexdigest(), 'Source changed during copy: ' + str(path))
        require(actual == READ_PINS.get(str(path), actual), 'Copied bytes differ from an earlier identity/pin')
        self.records.append({'source': path.relative_to(ROOT).as_posix(), 'destination': name,
            'storage': 'file', 'sha256_raw': actual, 'bytes': size})
        if len(self.records) % 50 == 0:
            print('Verified copied evidence entries:', len(self.records), flush=True)

    def zip_files(self, pairs, name):
        if not pairs:
            return
        path, members, names = self.target(name), [], set()
        with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for original, member in pairs:
                original = no_link(original)
                require(original != source(DRAFT) or self.allow_final_report, 'Pending draft must not enter a ZIP')
                relative(member)
                require(member not in names, 'Duplicate ZIP member: ' + member)
                names.add(member)
                if original.suffix.lower() == '.exe':
                    self.excluded.append({'source': original.relative_to(ROOT).as_posix(),
                        'bytes': original.stat().st_size, 'sha256': digest(original),
                        'reason': 'no new ZIP EXE member; source retained'})
                    continue
                checksum, size = hashlib.sha256(), 0
                with original.open('rb') as input_file, archive.open(member, 'w', force_zip64=True) as output:
                    for block in iter(lambda: input_file.read(CHUNK), b''):
                        output.write(block)
                        checksum.update(block)
                        size += len(block)
                members.append({'source': original.relative_to(ROOT).as_posix(), 'destination': name,
                    'member': member, 'storage': 'zip_member', 'bytes': size, 'sha256_raw': checksum.hexdigest()})
        with zipfile.ZipFile(path) as archive:
            require(archive.namelist() == [m['member'] for m in members], 'ZIP member list/order mismatch')
            for item in members:
                with source(item['source']).open('rb') as original, archive.open(item['member']) as archived:
                    actual, size = compare(original, archived)
                require(actual == item['sha256_raw'] and size == item['bytes'], 'ZIP member/source mismatch')
                require(actual == READ_PINS.get(str(source(item['source'])), actual), 'ZIP differs from an earlier identity/pin')
        self.records.extend(members)
        self.generated.append({'destination': name, 'bytes': path.stat().st_size, 'sha256': digest(path),
                               'uncompressed_members_verified': len(members)})

    def tree(self, base, prefix, large_members):
        files, directories = files_below(base)
        self.trees.append({'source': base.relative_to(ROOT).as_posix(), 'destination': prefix,
            'files': [p.relative_to(base).as_posix() for p in files],
            'directories': [p.relative_to(base).as_posix() for p in directories]})
        for path in files:
            name = (PurePosixPath(prefix) / path.relative_to(base).as_posix()).as_posix()
            if path.stat().st_size >= LARGE:
                large_members.append((path, name))
            else:
                self.copy(path, name)

    def final_source_check(self):
        for item in self.records + self.excluded:
            require(digest(source(item['source'])) == item.get('sha256_raw', item.get('sha256')),
                    'Original evidence changed before archive completion: ' + item['source'])
        for tree in self.trees:
            current, directories = files_below(source(tree['source']))
            require([p.relative_to(source(tree['source'])).as_posix() for p in current] == tree['files'],
                    'Selected tree member set changed')
            require([p.relative_to(source(tree['source'])).as_posix() for p in directories] == tree['directories'],
                    'Selected directory set changed')


def git_identity():
    """Hash frozen Git objects, not the possibly later-edited live checkout."""
    listing = subprocess.check_output(['git', 'ls-tree', '-rz', '--full-tree', HEAD], cwd=ROOT)
    entries = []
    process = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in listing.split(b'\0'):
            if not row:
                continue
            header, path = row.split(b'\t', 1)
            mode, kind, oid = header.decode('ascii').split()
            process.stdin.write(oid.encode('ascii') + b'\n')
            process.stdin.flush()
            response = process.stdout.readline().decode('ascii').strip().split()
            require(len(response) == 3 and response[0] == oid, 'Git object read failed')
            remaining, checksum = int(response[2]), hashlib.sha256()
            size = remaining
            while remaining:
                block = process.stdout.read(min(CHUNK, remaining))
                require(block, 'Incomplete Git object stream')
                checksum.update(block)
                remaining -= len(block)
            require(process.stdout.read(1) == b'\n', 'Git object framing mismatch')
            entries.append({'path': path.decode('utf-8', errors='surrogateescape'), 'mode': mode,
                'git_object_type': kind, 'git_object': oid, 'bytes': size, 'sha256_raw_git_object': checksum.hexdigest()})
        process.stdin.close()
        require(process.wait() == 0, 'git cat-file failed')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    return {'head': HEAD, 'scope': 'complete tracked tree with object IDs, sizes and raw-object SHA256 only; no object payloads embedded; not a standalone source backup; LFS pointers remain pointers',
        'ls_tree_raw_sha256': hashlib.sha256(listing).hexdigest(), 'entries': entries,
        'live_head_observed': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'live_status_observed': subprocess.check_output(['git', '--no-optional-locks', 'status', '--porcelain'], cwd=ROOT, text=True)}


def inspect_official(apis, zips):
    artifacts = [row for item in apis for row in load(pin(item))['artifacts']]
    require(len(artifacts) == 4 and len(zips) == 4, 'Exactly four official artifacts required')
    by_name = {pin(item).name: pin(item) for item in zips}
    require(len(by_name) == 4, 'Duplicate official ZIP names')
    result = []
    for item in artifacts:
        require(item['workflow_run']['head_sha'] == HEAD, 'Official API artifact head mismatch')
        filename = item['name'] + '.zip'
        require(filename in by_name and '/' not in filename and '\\' not in filename, 'Official ZIP/API selection mismatch')
        path = by_name[filename]
        require(path.stat().st_size == item['size_in_bytes'] and 'sha256:' + digest(path) == item['digest'],
                'Official ZIP bytes/API digest mismatch')
        members = []
        with zipfile.ZipFile(path) as archive:
            for index, entry in enumerate(archive.infolist()):
                checksum, size = hashlib.sha256(), 0
                with archive.open(entry) as stream:
                    for block in iter(lambda: stream.read(CHUNK), b''):
                        checksum.update(block)
                        size += len(block)
                require(size == entry.file_size, 'Official ZIP member length mismatch')
                members.append({'index': index, 'member': entry.filename, 'bytes': size,
                    'sha256_raw': checksum.hexdigest(), 'embedded_exe_preserved': entry.filename.lower().endswith('.exe')})
        result.append({'source': path.relative_to(ROOT).as_posix(), 'name': item['name'], 'artifact_id': item['id'],
            'run_id': item['workflow_run']['id'], 'sha256': digest(path), 'original_zip_unmodified': True, 'members': members})
    return result


def report_facts(path, frozen, suite=None):
    document = load(path)
    require(document['git_head'] == HEAD, 'Report is not the frozen head')
    require(document['source_fingerprint'] == frozen['source_fingerprint'] and
            document['tests_content_fingerprint'] == frozen['tests_content_fingerprint'], 'Report fingerprint mismatch')
    if suite is None:
        expected = [name for layer in LAYERS for name in frozen['profiles'][layer]]
    else:
        expected = frozen['profiles'][document['profile']]
    actual = [row['name'] for row in document['results']]
    # The all-profile runner keeps global registration order, whereas the
    # frozen manifest groups registrations by profile. Neither original order
    # is rewritten; require the exact complete set, including uniqueness.
    require(len(actual) == len(expected) == len(set(actual)) == len(set(expected))
            and set(actual) == set(expected), 'Report frozen case set/uniqueness mismatch')
    for row in document['results']:
        # Reports retain their original absolute OS paths. Copy the original
        # colocated log bytes without editing that report path or its SHA.
        name = PurePosixPath(str(row['log']).replace('\\', '/')).name
        require(name and name not in ('.', '..'), 'Invalid report log name')
        log = no_link(path.parent / name)
        require(digest(log) == row['log_sha256'], 'Report/log raw SHA mismatch while selecting archive')
        READ_PINS[str(log)] = row['log_sha256']
    return {'source': path.relative_to(ROOT).as_posix(), 'suite': suite, 'profile': document['profile'],
        'cases': len(document['results']), 'original_case_order': actual,
        'all_pass': all(r['status'] == 'pass' and r['exit_code'] == 0 for r in document['results']),
        'assertions_executed_total': document['assertions_executed_total']}


def preflight(spec):
    require(spec.get('schema') == 'k1_archive_release_v1' and spec.get('head') == HEAD, 'Wrong release-spec schema/head')
    require(spec.get('final_inputs_ready') is True, 'Wait for parent final evidence readiness')
    require(spec.get('phase_complete') is not True, 'This archive must not declare K1 phase completion')
    require(not DEST.exists(), 'Destination already exists; no overwrite, resume or cleanup is permitted')
    for name in AUDITS:
        audit = spec['audits'][name]
        require(audit.get('complete') is True, 'Final independent receipt not yet complete: ' + name)
        require(audit.get('outcome') in ('passed', 'failed', 'pending', 'gap_retained'), 'Audit outcome missing')
        pin(audit)
    for group in ('windows_gates', 'ci_gates', 'ci_artifact_apis', 'ci_official_zips', 'ci_control_files', 'ci_reports'):
        require(spec.get(group), 'Required final source group missing: ' + group)
        for item in spec[group]:
            pin(item)
    if GENERATION == 4:
        require(len(spec['windows_gates']) == 3, 'All three existing fourth Windows gate receipts required')
    else:
        # Later generations may retain additional same-platform historical
        # baseline gates. Select every recorded gate, without truncating to 3.
        gate_rows = load(pin(spec['windows_gate_receipt']))
        require(len(gate_rows) == len(spec['windows_gates']) and gate_rows,
                'Select every Windows gate from its pinned final receipt')
        require({'strict', 'baseline-strict', 'strict-baseline'}.issubset({row['name'] for row in gate_rows}),
                'Current strict/F5 baseline gates missing')
        for original, selected in zip(gate_rows, spec['windows_gates']):
            require(selected['gate_name'] == original['name'] and selected['exit_code'] == original['exit_code']
                    and selected['sha256'] == original['log_sha256']
                    and pin(selected) == no_link(Path(original['log'])),
                    'Selected Windows gate differs from original final receipt')
    require(len(spec['ci_reports']) == 12 and spec['ci_gates'], 'All twelve CI report/gate families required')
    require({tuple(pair) for pair in spec.get('ci_gate_coverage', [])} == CI_COMBINATIONS,
            'Original aggregate/per-profile gates must cover all twelve profiles')
    expected_controls = {(run, role) for run in ('linux', 'm0') for role in ('run_api', 'jobs_api', 'logs')}
    require(expected_controls.issubset({(i.get('run_group'), i.get('role')) for i in spec['ci_control_files']}),
            'CI control selection must explicitly include run API, jobs API and existing logs for both runs')
    require({(item['suite'], item['profile']) for item in spec['ci_reports']} == CI_COMBINATIONS, 'CI suite/profile coverage incomplete')
    for name in REQUIRED_SELECTION:
        require(source(name).is_file(), 'Explicit selected evidence missing: ' + name)
    for item in spec.get('extra_files', []):
        pin(item)
        require(source(item['path']) != source(DRAFT), 'Draft is excluded; use explicit final_delivery_report after parent updates it')
        relative(item['destination'])
    for item in spec.get('extra_trees', []):
        require(item.get('scope'), 'Supplement tree needs an explicit scope')
        relative(item['destination'])
        base = source(item['path'])
        require(not DEST.resolve().is_relative_to(base) and not base.is_relative_to(DEST.resolve()),
                'Selected tree must not contain or be inside this archive destination')
        paths, _ = files_below(base)
        require(source(DRAFT) not in paths, 'Draft report cannot be swept into an extra tree')
    for item in spec.get('diagnostic_files', []):
        path = pin(item)
        require(item.get('scope') == 'fourth_original_failure', 'Fourth archive diagnostic scope must be explicit')
        require(path.suffix.lower() in ('.json', '.log', '.txt', '.md'), 'Copy receipts/diagnostics, not next candidate source')
        relative(item['destination'])
    for item in spec.get('next_candidate_references', []):
        path = pin(item)
        require(item.get('scope'), 'Next-generation reference needs an explicit scope')
        require(path.suffix.lower() in ('.json', '.log', '.txt', '.md'), 'Do not copy/reference future candidate source code here')
    if spec.get('final_delivery_report'):
        require(spec['final_delivery_report'].get('final') is True, 'Draft report is not final')
        pin(spec['final_delivery_report'])
    frozen = load(SOURCE / 'frozen-case-manifest.json')
    build = load(SOURCE / 'build-identity.json')
    cap = load(SOURCE / 'capabilities.json')
    require(frozen['head_sha'] == build['head'] == HEAD and cap['build_git_commit'] == HEAD, 'Frozen identity mismatch')
    count = sum(len(frozen['profiles'][layer]) for layer in LAYERS)
    require(count == (182 if GENERATION == 4 else spec.get('expected_frozen_cases', count)), 'Wrong frozen case set')
    backend = SOURCE / 'frozen-binary/G4UniversalSim.exe'
    require(digest(backend) == build['backend_sha256'], 'Frozen original EXE/hash mismatch (hash only, never copied)')
    identity = load(SOURCE / 'visible/identity.json')
    require(identity['head'] == HEAD and identity['backend_sha256'] == build['backend_sha256'], 'Native identity mismatch')
    require(identity['gui_files'] == frozen['gui_files'], 'Native/frozen GUI SHA inventory differs')
    require(load(SOURCE / 'visible/host-exit.json')['event_loop_exit'] == 0, 'Native normal-exit receipt absent')
    images = [p for p in (SOURCE / 'visible').iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png')]
    expected_images = 17 if GENERATION == 4 else spec.get('native_screenshot_count')
    require(isinstance(expected_images, int) and expected_images > 0 and len(images) == expected_images,
            'Explicit complete native screenshot set required')
    replay_path = SOURCE / 'replay-cli-receipt.json'
    if replay_path.exists():
        require(load(replay_path)['head'] == HEAD, 'Replay receipt identity mismatch')
        replay_r2 = SOURCE / 'replay-cli-receipt-r2.json'
        if replay_r2.exists():
            corrected = load(replay_r2)
            require(corrected['head'] == HEAD and corrected['original_receipt_sha256'] == digest(replay_path),
                    'Replay postcheck supplement/original identity mismatch')
            returned_record = no_link(Path(corrected['record_file']))
            require(returned_record.is_relative_to((SOURCE / 'replay-cli').resolve())
                    and digest(returned_record) == corrected['record_sha256'], 'Returned CLI record SHA/path mismatch')
            returned = load(returned_record)
            require(returned['record_id'] == corrected['record_id'] and returned['result'] == corrected['result'],
                    'Replay supplement must bind the actual returned record, not imported historical runs')
    else:
        require(GENERATION != 4 and spec.get('prior_replay_reference'), 'Current or explicitly historical replay receipt required')
        pin(spec['prior_replay_reference'])
    native_records(spec)
    if GENERATION >= 5:
        addendum = ROOT / 'out/collab/k1-delivery-staging/verification-8213ced-addendum'
        review = load(ROOT / 'out/collab/k1-parent-fourth-addendum-review.json')
        require(review.get('status') == 'approved_derived_index_addendum_original_archive_unchanged'
                and review.get('findings') == [] and review.get('index_sha256') == digest(addendum / 'index.json')
                and review.get('receipt_sha256') == digest(addendum / 'addendum-receipt.json'),
                'Fourth addendum/parent separate review identity differs')
    windows = pin(spec['windows_report'])
    facts = [report_facts(windows, frozen)]
    for item in spec['ci_reports']:
        fact = report_facts(pin(item), frozen, item['suite'])
        require(fact['profile'] == item['profile'], 'Pinned CI profile differs from original report')
        facts.append(fact)
    official = inspect_official(spec['ci_artifact_apis'], spec['ci_official_zips'])
    return frozen, build, windows, facts, official


def execute(spec_path=None, prepared_spec=None):
    spec_path = no_link(Path(spec_path).absolute()) if spec_path is not None else None
    spec_bytes = spec_path.read_bytes() if spec_path is not None else raw_json(prepared_spec)
    spec = json.loads(spec_bytes)
    configure_generation(spec)
    require(spec.get('builder_sha256', BUILDER_SHA256) == BUILDER_SHA256, 'Selected archive-builder SHA differs')
    READ_PINS[str(Path(__file__).resolve())] = BUILDER_SHA256
    frozen, build, windows, facts, official = preflight(spec)
    DEST.mkdir(parents=True, exist_ok=False)
    archive = Archive(allow_final_report=bool(spec.get('final_delivery_report')))
    archive.write('archive-started.json', raw_json({'head': HEAD, 'overall_state': 'pending', 'phase_complete': False,
        'meaning': 'incomplete until archive-verification.json exists', 'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}))
    try:
        archive.write('release-spec-original.json', spec_bytes)
        for name in ('build-identity.json', 'capabilities.json', 'frozen-case-manifest.json'):
            archive.copy(SOURCE / name, 'identity/' + name)
        archive.copy(SOURCE / 'windows-run.log', 'windows/driver/windows-run.log')
        win_files, win_dirs = files_below(windows.parent)
        archive.trees.append({'source': windows.parent.relative_to(ROOT).as_posix(), 'destination': 'windows',
            'files': [p.relative_to(windows.parent).as_posix() for p in win_files],
            'directories': [p.relative_to(windows.parent).as_posix() for p in win_dirs]})
        for path in win_files:
            if path.parent == windows.parent:
                archive.copy(path, 'windows/' + path.name)
        archive.zip_files([(p, p.relative_to(windows.parent).as_posix()) for p in win_files if p.parent != windows.parent],
                          'windows/case-originals.zip')
        for index, item in enumerate(spec['windows_gates']):
            archive.copy(pin(item), f'windows/gates/{index:02d}-' + Path(item['path']).name)
        for group in ('ci_artifact_apis', 'ci_official_zips', 'ci_control_files', 'ci_gates'):
            for index, item in enumerate(spec[group]):
                archive.copy(pin(item), f'ci/{group}/{index:02d}-' + Path(item['path']).name)
        for item in spec['ci_reports']:
            path = pin(item)
            prefix = 'ci/reports/' + item['suite'] + '/' + item['profile']
            for original in sorted(path.parent.iterdir()):
                if original.is_file():
                    archive.copy(original, prefix + '/' + original.name)
        large_members = []
        for subtree in ('visible', 'replay-cli'):
            if subtree == 'replay-cli' and not (SOURCE / subtree).exists() and GENERATION != 4:
                continue
            archive.tree(SOURCE / subtree, subtree, large_members)
        for name in ('replay-cli.log', 'replay-cli-receipt.json', 'replay-cli-receipt-r2.json',
                     'replay-cli-postcheck-attempt1.md'):
            if (SOURCE / name).exists():
                archive.copy(SOURCE / name, 'replay/' + name)
        if spec.get('prior_replay_reference'):
            pin(spec['prior_replay_reference'])
            archive.write('replay/historical-reference.json', raw_json({**spec['prior_replay_reference'],
                'scope': 'earlier native GUI export replay, not rerun on this generation'}))
        for original, destination in REQUIRED_SELECTION.items():
            archive.copy(source(original), destination)
        for name, item in spec['audits'].items():
            archive.copy(pin(item), 'review/final/' + name + '-' + Path(item['path']).name)
        for item in spec.get('extra_files', []):
            archive.copy(pin(item), item['destination'])
        for item in spec.get('extra_trees', []):
            archive.tree(source(item['path']), item['destination'], large_members)
        for item in spec.get('diagnostic_files', []):
            archive.copy(pin(item), item['destination'])
        next_references = [{'source': i['path'], 'sha256': i['sha256'], 'scope': i['scope'],
            'operation': 'reference_only_not_copied', 'not_fourth_verification': True}
            for i in spec.get('next_candidate_references', [])]
        archive.zip_files(large_members, 'native-replay-data-originals.zip')
        if spec.get('final_delivery_report'):
            archive.copy(pin(spec['final_delivery_report']), 'review/final/parent-delivery-report.md')
        # Prior failures are another writer's completed, immutable archives.
        history = []
        for name in ('failed-e5ff800', 'failed-c644bb1', 'failed-11c92d3'):
            path = DEST.parent / name / 'archive-manifest.json'
            require(path.is_file(), 'Prior failure archive reference missing')
            history.append({'source': path.relative_to(ROOT).as_posix(), 'sha256': digest(path), 'operation': 'reference_only_not_modified'})
        if GENERATION >= 5:
            for rel in ('verification-8213ced/archive-manifest.json', 'verification-8213ced/archive-verification.json',
                        'verification-8213ced-addendum/index.json', 'verification-8213ced-addendum/addendum-receipt.json'):
                path = no_link(DEST.parent / rel)
                history.append({'source': path.relative_to(ROOT).as_posix(), 'sha256': digest(path),
                    'operation': 'reference_only_not_modified', 'scope': 'fourth history and separately parent-approved derived-index supplement'})
        archive.write('identity/full-tracked-source-and-test-objects.json', raw_json(git_identity()))
        archive.copy(Path(__file__).resolve(), 'archive-builder.py')
        archive.final_source_check()
        for item in history:
            require(digest(source(item['source'])) == item['sha256'], 'Immutable history reference changed')
        for group in ('windows_gates', 'ci_gates', 'ci_artifact_apis', 'ci_official_zips', 'ci_control_files', 'ci_reports'):
            for item in spec[group]:
                pin(item)
        for item in spec['audits'].values():
            pin(item)
        pin(spec['windows_report'])
        for item in spec.get('extra_files', []):
            pin(item)
        if spec.get('final_delivery_report'):
            pin(spec['final_delivery_report'])
        for item in spec.get('diagnostic_files', []) + spec.get('next_candidate_references', []):
            pin(item)
        if spec_path is not None:
            require(spec_path.read_bytes() == spec_bytes, 'Release source selection changed during archive')
        verification_ready = (all(f['all_pass'] for f in facts)
            and all(spec['audits'][name]['outcome'] == 'passed' for name in ('windows', 'ci', 'native', 'i1'))
            and all(item.get('exit_code') == 0 for item in spec['windows_gates'])
            and all('exit_code' not in item or item['exit_code'] == 0 for item in spec['ci_gates']))
        state = 'verification_complete_but_K1_unaccepted' if verification_ready else 'pending'
        archive.write('selection.json', raw_json(archive.records))
        archive.write('source-trees.json', raw_json(archive.trees))
        archive.write('excluded-executable-inventory.json', raw_json(archive.excluded))
        archive.write('official-archives.json', raw_json(official))
        archive.write('report-original-facts.json', raw_json(facts))
        archive.write('history-references.json', raw_json(history))
        archive.write('next-generation-references.json', raw_json(next_references))
        archive.write('native-record-facts.json', raw_json(native_records(spec)))
        title = '第四' if GENERATION == 4 else '第五' if GENERATION == 5 else '第六'
        archive.write('README.md', ('# K1 ' + title + '冻结历史证据归档\n\n'
            + '冻结：' + HEAD + '\n\n整体状态：`' + state + '`。K1未完成阶段验收，phase_complete=false。\n\n'
            + ('此代自动化验证失败；原失败收据/日志保留，本机或原生通过不能覆盖CI失败。\n\n'
               if spec.get('frozen_verification_outcome') == 'failed' else '')
            + '资源边界专项独立审查被上游拒绝且未完成；普通功能、CI和实窗不能代替该缺口。\n\n'
            + '本归档按原冻结身份保留，不自动称最终K1版本；取消与前端发现按各代收据解释，后继冻结不回写前代结论。\n\n'
            + '原件不改写、不删除。selection.json索引普通副本与ZIP每个原始成员；小CSV保持原树，大文件在native-replay-data-originals.zip内，未静默省略取消运行的大CSV。\n\n'
            + '不新增独立EXE或新ZIP的EXE成员，排除路径/大小/SHA显式列出；官方原ZIP逐字节保留，包含其中原有EXE。\n\n'
            + '本工具仅归档既有证据，不运行测试/门禁/浏览器或独立复审，不替父任务裁决阶段；默认Windows系统chooser未验，Qt变体范围以原身份和独立收据为准。\n\n'
            + '三轮失败归档只作只读引用。计划最终人类README为docs/verification/k1-final-20261031/README.md，第六冻结仍待定；后续由父任务按协议复制，另人独立审查。\n').encode('utf-8'))
        manifest = {'schema': 'k1_historical_verification_archive_v1', 'head': HEAD, 'overall_state': state, 'phase_complete': False,
            'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'resource_boundary_independent_review': 'upstream_refused_incomplete_not_retried',
            'evidence_generation': GENERATION,
            'frozen_verification_outcome': spec.get('frozen_verification_outcome', 'not_claimed'),
            'archive_kind': 'historical_generation_not_automatic_K1_acceptance',
            'next_candidate_receipts_are_not_fourth_verification': next_references,
            'known_findings': ([{'severity': 'P3', 'fact': 'cancelled public reason can incorrectly be inputs_changed',
                'disposition': 'present in fourth; separate fifth narrow fix approved; no retroactive rewrite'}]
                if GENERATION == 4 else []) + spec.get('known_findings', []),
            'release_spec_sha256': hashlib.sha256(spec_bytes).hexdigest(), 'original_backend_sha256': build['backend_sha256'],
            'archive_builder_sha256': BUILDER_SHA256,
            'backend_binary_copied': False, 'all_scientific_data_selected': 'all selected visible/replay/case non-EXE files, including cancelled-run CSV',
            'standalone_executables_excluded': archive.excluded, 'selection_records': len(archive.records),
            'parent_audit_attestations': spec['audits'], 'prior_archives_not_modified': history,
            'generated_files': list(archive.generated), 'tool_does_not_decide_phase_acceptance': True}
        size_files, _ = files_below(DEST)
        sizes = sorted(({'path': p.relative_to(DEST).as_posix(), 'bytes': p.stat().st_size}
                        for p in size_files), key=lambda row: (-row['bytes'], row['path']))
        archive.write('size-and-push-planning.json', raw_json({
            'head': HEAD, 'scope': 'local archive planning, not a remote policy check or push',
            'bytes_before_final_metadata': sum(row['bytes'] for row in sizes),
            'files_before_final_metadata': len(sizes), 'largest_files': sizes[:30],
            'planning_thresholds_bytes': {'large_file_attention': 50 * 1024 * 1024,
                                         'single_file_block_assumption': 100 * 1024 * 1024},
            'thresholds_are_local_assumptions_not_live_verified_hosting_policy': True,
            'files_over_50MiB': [row for row in sizes if row['bytes'] > 50 * 1024 * 1024],
            'files_over_100MiB': [row for row in sizes if row['bytes'] > 100 * 1024 * 1024],
            'ordinary_push_under_100MiB_file_assumption': not any(row['bytes'] > 100 * 1024 * 1024 for row in sizes),
            'official_zip_policy': 'original bytes unchanged, including their existing embedded EXE',
            'if_large': 'parent chooses external artifact storage or approved large-file mechanism; do not silently omit or split official ZIP',
            'network_push_or_remote_probe_performed': False}))
        archive.write('archive-manifest.json', raw_json(manifest))
        # Final archive index explicitly excludes its own index/verification receipts.
        files, _ = files_below(DEST)
        index = [{'path': p.relative_to(DEST).as_posix(), 'bytes': p.stat().st_size, 'sha256_raw': digest(p)} for p in files]
        archive.write('final-files.json', raw_json({'files': index, 'file_count_without_self': len(index),
            'bytes_without_self': sum(row['bytes'] for row in index),
            'excluded_self': ['final-files.json', 'archive-verification.json']}))
        for row in index:
            require(digest(DEST / row['path']) == row['sha256_raw'], 'Final archive file digest mismatch')
        archive.write('archive-verification.json', raw_json({'head': HEAD, 'overall_state': state, 'phase_complete': False,
            'original_bytes_compared': sum(r['bytes'] for r in archive.records), 'source_entries_verified': len(archive.records),
            'archive_bytes_before_this_receipt': sum(p.stat().st_size for p in files_below(DEST)[0]),
            'archive_manifest_sha256': digest(DEST / 'archive-manifest.json'), 'final_index_sha256': digest(DEST / 'final-files.json'),
            'archive_execution_completed': True, 'independent_archive_review': 'not_performed_by_this_tool'}))
        print(json.dumps({'destination': str(DEST), 'overall_state': state, 'phase_complete': False}, ensure_ascii=False))
    except BaseException as error:
        failure = DEST / ('archive-failure-' + uuid4().hex + '.json')
        with failure.open('xb') as handle:
            handle.write(raw_json({'head': HEAD, 'overall_state': 'pending', 'phase_complete': False,
                'error_type': type(error).__name__, 'error': str(error), 'partial_archive_retained': True}))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Only after parent final readiness notification')
    parser.add_argument('--release-spec', type=Path, help='Final explicitly selected/pinned existing sources')
    parser.add_argument('--fourth-ready-selection', action='store_true',
                        help='Pin the named final fourth audit receipts; only used with explicit --execute')
    parser.add_argument('--fifth-ready-selection', action='store_true',
                        help='Pin final fifth audits and three explicit original native records; needs --execute')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps(PLAN, ensure_ascii=False, indent=2))
        return
    require(sum((bool(args.release_spec), args.fourth_ready_selection, args.fifth_ready_selection)) == 1,
            '--execute needs exactly one of --release-spec, --fourth-ready-selection or --fifth-ready-selection')
    if args.fourth_ready_selection or args.fifth_ready_selection:
        execute(prepared_spec=fourth_ready_selection(5 if args.fifth_ready_selection else 4))
    else:
        execute(args.release_spec)


if __name__ == '__main__':
    main()
