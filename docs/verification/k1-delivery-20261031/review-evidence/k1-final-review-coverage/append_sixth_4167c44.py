"""Append only: map existing approvals to actual sixth-freeze bytes, without tests."""
from pathlib import Path
from collections import Counter
import copy
import datetime
import difflib
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COLLAB = ROOT / 'out/collab'
HEAD = '4167c4421b13464dec54213ea7652ee321868c4e'

def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def pin(path):
    return dict(path=str(path), sha256=digest(path.read_bytes()), bytes=path.stat().st_size)

def link(path, label=None):
    path = Path(path)
    absolute = path if path.is_absolute() else ROOT / path
    return f'[{label or path.name}]({absolute.as_posix()})'

assert git('rev-parse', 'HEAD').decode().strip() == HEAD
assert not git('status', '--porcelain', '--untracked-files=no').strip()
prior_path = HERE / 'f9a9ddb-v2-awaiting-independent-r2.json'
prior = read(prior_path)
fifth = prior['observed_fifth_commit']
old_names = ['BUILD-ATTEMPT-1.md', 'build_snapshot.py', 'f9a9ddb-v2-awaiting-independent-r2.json',
             'f9a9ddb-v2-awaiting-independent-r2.md', 'f9a9ddb-v2-awaiting-independent.json',
             'PROGRESS.md', 'verification-r2.json',
             '4167c44-validation-pending.md', '4167c44-validation-pending.json',
             '4167c44-verification.json', '4167c44-PROGRESS.md']
immutable = [pin(HERE / name) for name in old_names]
immutable += [pin(COLLAB / 'k1-review-coverage-map.json'), pin(COLLAB / 'k1-review-coverage-map.md')]
v1_dir = COLLAB / 'k1-final-ui-candidate'
v2_dir = COLLAB / 'k1-final-ui-candidate-v2'
v1_identity = read(v2_dir / 'v1-preserved-identities.json')
assert all(digest((v1_dir / path).read_bytes()) == sha for path, sha in v1_identity.items())
assert set(v1_identity) == {str(p.relative_to(v1_dir)) for p in v1_dir.rglob('*') if p.is_file()}
v2_immutable = [pin(p) for p in v2_dir.rglob('*') if p.is_file()]

ui_path = COLLAB / 'k1-final-ui-independent-v2.json'
parent_path = COLLAB / 'k1-parent-ui-v2-review.json'
receipt_path = COLLAB / 'k1-sixth-integration-receipt.json'
doc_initial_path = COLLAB / 'k1-sixth-display-contract-independent.json'
doc_followup_path = COLLAB / 'k1-sixth-display-contract-independent-followup.json'
draft_path = COLLAB / 'k1-sixth-display-contract.md'
formal_path = ROOT / 'out/verification/k1-4167c44/frozen-case-manifest.json'
ui, parent, receipt = read(ui_path), read(parent_path), read(receipt_path)
initial, followup, formal = read(doc_initial_path), read(doc_followup_path), read(formal_path)
assert ui['findings'] == [] and parent['findings'] == []
assert ui['author_conflict'] is False
assert ui['independent_from_parent_review'] is True
assert formal['head_sha'] == HEAD
assert digest(draft_path.read_bytes()) == receipt['reviewed_contract_sha256'] == followup['draft_sha256']
assert digest(doc_initial_path.read_bytes()) == followup['previous_review_sha256']
assert digest(ui_path.read_bytes()) == initial['v2_review_sha256']
assert digest((v2_dir / 'manifest.json').read_bytes()) == ui['manifest_sha256'] == receipt['candidate_manifest_sha256']
assert parent['user_supplied_hashes_verified']['manifest.json'] == ui['manifest_sha256']
candidate = {r['path']: r for r in ui['files']}
parent_files = {r['path']: r for r in parent['files']}
integrated = {r['path']: r['sha256'] for r in receipt['files']}
assert set(candidate) == set(parent_files) == set(integrated) and len(candidate) == 6

reviews = copy.deepcopy(prior['reviews'])
for r in reviews.values():
    assert digest((ROOT / r['path']).read_bytes()) == r['sha256'], 'Existing report drift requires separate append'
reviews['sixth_parent_ui'] = dict(path=str(parent_path.relative_to(ROOT)), sha256=digest(parent_path.read_bytes()),
    reviewer='父任务（非候选作者）', kind='parent_independent_increment_review',
    scope=parent['scope'], verdict=parent['status'], timestamp=parent['time_utc'])
reviews['sixth_averroes_ui'] = dict(path=str(ui_path.relative_to(ROOT)), sha256=digest(ui_path.read_bytes()),
    reviewer='Averroes（独立于作者与父审查）', kind='independent_limited_code_review',
    scope='six-file UI v2 scope; real logic review, original assertions and retained receipts',
    verdict=ui['judgement'], timestamp=ui['completed_utc'])
reviews['sixth_doc_followup'] = dict(path=str(doc_followup_path.relative_to(ROOT)),
    sha256=digest(doc_followup_path.read_bytes()), reviewer='Dalton', kind='independent_approved_draft_review',
    scope='narrow display documentation consistency; parent-authored draft only, not entire final documents',
    verdict=followup['status'], timestamp=followup['recorded_utc'],
    draft=pin(draft_path), earlier_review=pin(doc_initial_path))

delta = {p: dict(added=int(a), removed=int(d)) for a, d, p in
         (line.split('\t') for line in git('diff', '--numstat', fifth, HEAD).decode('utf-8').splitlines())}
docs = {'AGENTS.md', 'gui/AGENTS.md', 'docs/agent-history.md', 'docs/可信实验工作流.md'}
assert set(delta) == set(candidate) | docs
draft_text = draft_path.read_text(encoding='utf-8').replace('\r\n', '\n')
doc_projection = {}
for path in sorted(docs):
    before = git('show', fifth + ':' + path).decode('utf-8').splitlines(True)
    after = git('show', HEAD + ':' + path).decode('utf-8').splitlines(True)
    ops = difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
    assert all(tag in ('equal', 'insert') for tag, *_ in ops), 'Contract integration should only add context'
    added = ''.join(''.join(after[b0:b1]) for tag, a0, a1, b0, b1 in ops if tag == 'insert')
    narrative = [p for p in added.strip().split('\n\n') if p and not p.startswith('#')]
    copied = [p in draft_text for p in narrative]
    if path != 'AGENTS.md':
        assert all(copied), 'Non-index narrative must be copied from approved draft'
    doc_projection[path] = dict(author='父任务', frozen_commit=HEAD,
        final_worktree_sha256=digest((ROOT / path).read_bytes()),
        final_git_sha256=digest(git('show', HEAD + ':' + path)),
        approved_draft_sha256=followup['draft_sha256'],
        added_text_sha256=digest(added.encode('utf-8')), added_lines=delta[path]['added'],
        no_prior_document_content_removed=True,
        mapping='parent condensed root-index summary, contextual integration reported by user' if path == 'AGENTS.md'
                else 'narrative paragraphs exactly copied from approved draft; heading adapted to context',
        narrative_paragraphs_exactly_in_approved_draft=copied,
        direct_final_whole_file_SHA_signed_by_Dalton=False,
        scope='approved draft consistency + actual section/version projection; not full final document approval')

rows = copy.deepcopy(prior['files'])
for row in rows:
    path = row['path']
    raw, blob = (ROOT / path).read_bytes(), git('show', HEAD + ':' + path)
    raw_sha, blob_sha = digest(raw), digest(blob)
    row['fifth_sha256'] = row['final_worktree_sha256']
    row['final_worktree_sha256'], row['final_git_sha256'] = raw_sha, blob_sha
    row['final_git_worktree_raw_equal'] = raw == blob
    row['LF_normalized_equal'] = raw.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n')
    row['fifth_to_sixth_numstat'] = delta.get(path)
    row['historical_fifth_status'] = row['status']
    row['historical_fifth_remaining'] = row['remaining_delta_or_scope']
    row['historical_frontend_findings'] = row['open_frontend_findings']
    if path in candidate:
        expected = candidate[path]['candidate_sha256']
        assert raw_sha == blob_sha == expected == integrated[path] == parent_files[path]['v2_sha256']
        assert b'\r' not in raw
        row['sixth_delta_author'] = 'Tesla（候选唯一写者）；父任务仅集成'
        if 'Tesla' not in row['authors']:
            row['authors'] = [*row['authors'], 'Tesla（第六UI候选）']
        for key in ('sixth_parent_ui', 'sixth_averroes_ui'):
            r = reviews[key]
            row['review_chain'].append(dict(review_id=key, reviewed_sha256=expected,
                review_path=r['path'], reviewer=r['reviewer'], kind=r['kind'], scope=r['scope'],
                verdict=r['verdict'], final_frozen_commit=HEAD,
                parent_semantic_increment_only=(key == 'sixth_parent_ui'),
                parent_changed_file_in_increment=path in ui['changed_since_v1'] if key == 'sixth_parent_ui' else None))
        row['open_frontend_findings'] = []
        row['historical_findings_resolution'] = dict(status='closed within independently approved UI code scope',
            independent_review='sixth_averroes_ui', formal_sixth_validation='pending, separate from code review')
        row['remaining_delta_or_scope'] = ['第六正式矩阵与原生观察待证；不重新要求已完成的六文件独审。']
    elif path in docs:
        row['sixth_delta_author'] = '父任务（四份显示契约；非Franklin）'
        row['doc_narrow_projection'] = doc_projection[path]
        row['review_chain'].append(dict(review_id='sixth_doc_followup', reviewed_sha256=None,
            mapped_final_sha256=raw_sha, approved_draft_sha256=followup['draft_sha256'],
            review_path=reviews['sixth_doc_followup']['path'], reviewer='Dalton',
            kind='independent_approved_draft_review',
            scope='approved display draft wording; actual document sections projected by mapper, not whole-file signoff',
            verdict=followup['status'], final_frozen_commit=HEAD))
        row['remaining_delta_or_scope'] = ['第六新增显示契约有Dalton草稿窄签字和父集成绑定；最终文档/状态整体仍待最终数据后的父任务+Dalton审查。']
    else:
        assert raw_sha == row['fifth_sha256'], 'Unexpected change outside sixth scope'
    if row['open_frontend_findings']:
        assert all(f['relation'] == 'related call-chain context' and f['id'] in ('F1', 'F2')
                   for f in row['open_frontend_findings'])
        row['open_frontend_findings'] = []
        row['historical_findings_resolution'] = dict(
            status='consumer display issue closed by independently approved six-file UI fix; producer unchanged',
            independent_review='sixth_averroes_ui', no_new_producer_review=True)
        row['remaining_delta_or_scope'] = [note for note in row['remaining_delta_or_scope']
            if '第六v2修复待独审' not in note]
    for r in row['review_chain']:
        r['final_worktree_bytes_match'] = r.get('reviewed_sha256') == raw_sha
        r['final_git_blob_bytes_match'] = r.get('reviewed_sha256') == blob_sha
    exact = [r for r in row['review_chain'] if r['final_worktree_bytes_match']]
    row['exact_independent_review_ids'] = [r['review_id'] for r in exact if r['kind'] in
        ('independent_limited_code_review', 'independent_code_review_with_open_findings')]
    row['exact_functional_review_ids'] = [r['review_id'] for r in exact if r['kind'] == 'ordinary_functional_review']
    if path in docs:
        row['status'] = 'narrow_approved_draft_bound_to_sixth_document_section'
        row['last_reviewed_version_binding'] = row['review_chain'][-1]
    else:
        row['last_reviewed_version_binding'] = exact[-1] if exact else next(
            (r for r in reversed(row['review_chain']) if r.get('reviewed_sha256')), None)
        if row['exact_independent_review_ids']:
            row['status'] = 'exact_limited_independent_review'
    row['whole_file_or_stage_approval'] = 'not inferred from final SHA, independent limited review or approved draft'

actual_scope = [line.split('\t')[-1] for line in git('diff', '--numstat', prior['base_commit'], HEAD).decode('utf-8').splitlines()]
assert sorted(actual_scope) == sorted(row['path'] for row in rows)
frozen_products = {path: formal['gui_files'][path] == candidate[path]['candidate_sha256']
                   for path in candidate if path in formal['gui_files']}
assert len(frozen_products) == 4 and all(frozen_products.values())
modules = []
for old in prior['modules']:
    selected = [r for r in rows if r['module'] == old['id']]
    modules.append(dict(id=old['id'], label=old['label'],
        authors=sorted({a for r in selected for a in r['authors']}), files=[r['path'] for r in selected],
        status_counts=dict(Counter(r['status'] for r in selected)),
        sixth_reviews=sorted({r['review_id'] for row in selected for r in row['review_chain'] if r['review_id'].startswith('sixth_')})))

current_evidence = [pin(p) for p in [ui_path, parent_path, receipt_path, doc_initial_path, doc_followup_path,
    draft_path, formal_path, COLLAB/'k1-final-ui-independent-v2.md', COLLAB/'k1-parent-ui-v2-review.md',
    COLLAB/'k1-sixth-display-contract-independent-followup.md']]
snapshot = dict(schema='k1_append_only_sixth_review_coverage_v1', timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    mapping_only=True, actual_final_head=HEAD, tracked_clean=True,
    local_upstream_ref=git('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}').decode().strip(),
    local_tracking_ahead_behind=git('rev-list', '--left-right', '--count', 'HEAD...@{upstream}').decode().strip(),
    remote_fetched_or_queried=False, push='user-reported pushed; local tracking matches, no network verification',
    base_commit=prior['base_commit'], previous_fifth_commit=fifth, historical_fourth_commit=prior['historical_fourth_commit'],
    actual_base_to_sixth_file_count=len(rows), actual_fifth_to_sixth_delta=delta,
    reviews=reviews, files=rows, modules=modules, status_counts_not_stage_approval=dict(Counter(r['status'] for r in rows)),
    six_files_exact_candidate_commit_worktree_receipt=True, six_files_all_LF=True,
    sixth_averroes_exact_files=6, sixth_parent_increment_semantic_files=ui['changed_since_v1'],
    sixth_parent_all_six_identity_bindings=6, doc_narrow_followup=doc_projection,
    formal_manifest=dict(**pin(formal_path), head_sha=formal['head_sha'],
        source_fingerprint=formal['source_fingerprint'], tests_content_fingerprint=formal['tests_content_fingerprint'],
        registered_profile_counts={p: len(cases) for p, cases in formal['profiles'].items()},
        four_product_file_SHA_matches=frozen_products,
        two_smoke_SHA_scope='not listed in gui_files; bound directly by Git, candidate, independent review and integration receipt'),
    validation_status='sixth formal matrix/native validation pending per user; no result/status probes performed',
    remaining_required_ordinary_scope=[
        dict(scope='sixth frozen formal matrix/native acceptance and final result identity', owner='parent and assigned evidence reviewers', status='pending'),
        dict(scope='final evidence/report documents authored by Franklin after final data', reviewers=['父任务', 'Dalton'], status='pending final data; distinct from four parent-authored display contracts')],
    completed_ordinary_scope='six-file v2 independent approval and actual sixth integration identity; narrow display draft followup resolved',
    blocked_resource_gap=copy.deepcopy(prior['blocked_resource_gap']),
    blocked_resource_gap_handling=prior['blocked_resource_gap_handling'],
    author_conflict='Tesla only maps signatures/bytes for own six authored candidates; Averroes independent logic review supplies approval',
    evidence=current_evidence, immutable_previous_artifacts=immutable,
    candidate_v1_39_files_unchanged=True, candidate_v2_files_immutable=v2_immutable,
    no_source_changes=True, no_tests_or_matrices_started=True, no_old_report_or_map_edits=True,
    no_resource_review_or_refused_operation=True, K1_completion_decision='not made; resource gap and sixth validation remain separate', usage='unknown')

stem = '4167c44-validation-pending-r2'
json_path, md_path = HERE/(stem+'.json'), HERE/(stem+'.md')
with json_path.open('x', encoding='utf-8', newline='\n') as out:
    json.dump(snapshot, out, ensure_ascii=False, indent=2); out.write('\n')
md = ['# K1 第六冻结审查覆盖追加图', '',
    f'实际HEAD `{HEAD}`，tracked干净；本地跟踪引用与HEAD为0/0，推送事实另据用户通知，未联网查询。实际 `{prior["base_commit"][:7]}..4167c44` 仍为{len(rows)}文件；相对第五仅六个UI/回归文件与四份父任务契约。旧第四图、第五r2/v1图、候选与原审查报告全部保持原字节。', '',
    '本图只核版本、签字和字节关系。Tesla是六候选作者，不自审；独立逻辑签字来自Averroes，父任务另有两文件增量审查。第六正式矩阵/实窗验证仍待完成，本图不把代码批准或manifest登记当运行通过，不裁决K1完成。消耗未知。', '',
    '## 第六六文件签字与实际SHA', '',
    link(ui_path, 'Averroes六文件独审') + ' / ' + link(parent_path, '父任务增量审查') + ' / ' + link(receipt_path, '集成收据') + '。父签字语义范围是v1→v2两文件及必要上下文，另四文件身份保持v1限定认可；Averroes最终六文件签字独立于父审查。', '',
    '| 文件 | 第六Git/工作区/v2/收据共同SHA256 | 独审 |', '|---|---|---|']
for path, row in candidate.items():
    md.append(f'| `{path}` | `{row["candidate_sha256"]}` | Averroes六文件；父任务' +
              ('增量代码审查' if path in ui['changed_since_v1'] else '身份绑定/沿用v1限定范围') + ' |')
md += ['', '六文件全部LF、实际Git blob与工作区原字节一致；原F1/F2及v1 external漏投影在独审UI代码范围已关闭，第四/第五原发现报告和v1 REQUEST_CHANGES仍保留历史，不回写。正式验收状态仍待证。', '',
    '## 四份父任务显示契约：窄范围跟进', '',
    'Dalton后续签字 ' + link(doc_followup_path) + ' 审定草稿SHA `' + followup['draft_sha256'] + '`，关闭两项P3措辞发现。' +
    '四份文档由父任务写入，不是Franklin。这里映射审定草稿到实际新增上下文：GUI段落、人类段落、历史正文逐段相同（标题层级适配）；root索引是父任务压缩摘要，按用户确认的上下文集成记证。Dalton报告未逐一列最终四份整文件SHA，故下列是落盘身份/段落绑定，不扩张为整文件终审。', '',
    '| 文件 | 第六原字节SHA256 | 绑定范围 |', '|---|---|---|']
for path, r in doc_projection.items():
    md.append(f'| `{path}` | `{r["final_worktree_sha256"]}` | {r["mapping"]} |')
md += ['', '最终数据后的完整证据报告、状态和文档仍由父任务+Dalton审Franklin交付；与上述四份父任务窄契约分开。', '',
    '## 剩余必要范围与保留缺口', '',
    '- 第六冻结正式矩阵、实窗和对应最终身份验收，交由父任务及已分派审计者；本图不轮询进程或报告。',
    '- 最终数据完成后的Franklin文档，由父任务+Dalton审查。六文件代码独审和集成绑定不再列为待审。',
    '- Plato原bundle广审及Bohr后续资源边界独审的上游拒绝缺口未关闭；普通功能审查不能替代。本图未重试、改名、换代理或执行被拒范围。', '',
    '## 冻结manifest身份（非测试结果）', '',
    link(formal_path) + f'，source `{formal["source_fingerprint"]}`，tests `{formal["tests_content_fingerprint"]}`。', '',
    '登记static36/gui56/backend61/integration29，共182项；gui_files核对四个产品文件SHA一致，两个smoke不在该清单，其最终SHA直接由Git/工作区/v2/两审查/收据绑定。未声称182项已运行或通过。', '',
    '## 模块与逐文件覆盖', '',
    '| 模块 | 当前作者来源 | 文件数 | 第六新增签字 |', '|---|---|---:|---|']
for m in modules:
    md.append(f'| {m["label"]} | {" / ".join(m["authors"])} | {len(m["files"])} | {", ".join(m["sixth_reviews"]) or "沿用此前限定链，字节未变"} |')
md += ['', '| 文件 | 最后范围签字 | 第六SHA前12位 | 未覆盖delta/范围 |', '|---|---|---|---|']
for row in rows:
    r = row['last_reviewed_version_binding']
    signing = (link(r['review_path'], r['review_id']) + ('（草稿→段落绑定）' if r['kind'] == 'independent_approved_draft_review'
              else '（字节匹配）' if r['final_worktree_bytes_match'] else '（旧字节）')) if r else '无最终字节独签；历史来源范围'
    md.append(f'| `{row["path"]}` | {signing} | `{row["final_worktree_sha256"][:12]}` | ' +
              ('；'.join(row['remaining_delta_or_scope']) or '无新未覆盖delta；仍限原审查scope') + ' |')
md += ['', '完整继承审查链、Git/工作区SHA、草稿段落SHA、旧图不变收据及独审边界见 ' + link(json_path) + '。']
with md_path.open('x', encoding='utf-8', newline='\n') as out:
    out.write('\n'.join(md)+'\n')
assert not git('status', '--porcelain', '--untracked-files=no').strip()
assert git('rev-parse', 'HEAD').decode().strip() == HEAD
assert all(digest(Path(p['path']).read_bytes()) == p['sha256'] for p in immutable + v2_immutable + current_evidence)
assert all(row['LF_normalized_equal'] for row in rows)
verification = dict(head=HEAD, tracked_clean=True, output=[pin(md_path), pin(json_path)],
    old_artifact_count=len(immutable), old_artifacts_unchanged=True, v1_all_39_unchanged=True,
    v2_all_files_unchanged=True, six_source_byte_bindings=True, four_doc_projection_bindings=True,
    formal_validation='pending', no_tests=True, no_source_or_old_map_writes=True, K1_completion='not_decided')
with (HERE/'4167c44-verification-r2.json').open('x', encoding='utf-8', newline='\n') as out:
    json.dump(verification, out, ensure_ascii=False, indent=2); out.write('\n')
with (HERE/'4167c44-PROGRESS-r2.md').open('x', encoding='utf-8', newline='\n') as out:
    out.write('Sixth 4167c44 append-only r2 map complete. Six v2 files match Git/worktree/Averroes/parent identities/integration receipt and LF; doc e0829 draft followup maps four parent-authored contexts narrowly (root index summarized). Fifth maps and v1/v2 all immutable. r2 also closes inherited related-producer F2 display metadata without changing/re-reviewing producer source; initial sixth map retained as historical build output. Formal sixth matrix/native pending; final Franklin docs parent+Dalton pending final data. Blocked resource gap untouched; no new tests/source changes/K1 acceptance. Outputs 4167c44-validation-pending-r2.md/json and 4167c44-verification-r2.json. Usage unknown.\n')
print(json.dumps(verification, ensure_ascii=False))
