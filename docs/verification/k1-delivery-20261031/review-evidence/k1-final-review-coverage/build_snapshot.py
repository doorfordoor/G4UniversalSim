"""Read existing review/version metadata; append a new immutable coverage snapshot."""
from pathlib import Path
from collections import Counter
import copy
import datetime
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COLLAB = ROOT / 'out/collab'

def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def pin(path):
    return dict(path=str(path), sha256=sha(path.read_bytes()), bytes=path.stat().st_size)

def link(relative, label=None):
    return f'[{label or relative}]({(ROOT / relative).as_posix()})'

old_path = COLLAB / 'k1-review-coverage-map.json'
old = read(old_path)
base, fourth = old['base_commit'], old['final_commit']
head = git('rev-parse', 'HEAD').decode().strip()
assert head == 'f9a9ddbfcabe69067707a5a209caff005748f510', 'New freeze requires a new snapshot plan'
assert not git('status', '--porcelain', '--untracked-files=no').strip()
old_pins = [pin(old_path), pin(COLLAB / 'k1-review-coverage-map.md')]
adapters = read(COLLAB / 'k1-final-adapters-independent.json')
frontend = read(COLLAB / 'k1-final-frontend-independent.json')
cancel = read(COLLAB / 'k1-cancel-reason-independent.json')
candidate_path = COLLAB / 'k1-final-ui-candidate-v2/manifest.json'
candidate = read(candidate_path)
reviews = copy.deepcopy(old['reviews'])
new_reviews = {
    'final_adapters': dict(path='out/collab/k1-final-adapters-independent.json', reviewer='Averroes',
        version=adapters['head'], scope=adapters['scope_boundary'], verdict=adapters['judgement'],
        completed_utc=adapters['completed_utc'], kind='independent_limited_code_review'),
    'final_frontend': dict(path='out/collab/k1-final-frontend-independent.json', reviewer='Tesla',
        version=frontend['frozen_commit'], scope='eight final ordinary frontend implementations/tests; full K1 diff and necessary context',
        verdict=frontend['verdict'], completed_utc=frontend['timestamp'], kind='independent_code_review_with_open_findings'),
    'fifth_cancel': dict(path='out/collab/k1-cancel-reason-independent.json', reviewer='Dalton',
        version='final LF SHA per file, transferred into f9a9ddb', scope=cancel['scope'],
        verdict=cancel['status'], completed_utc=cancel['recorded_utc'], kind='independent_limited_code_review'),
}
for key, review in new_reviews.items():
    review['sha256'] = sha((ROOT / review['path']).read_bytes())
    review['report_kind'] = 'existing independent logic review; this map adds version/SHA metadata only'
    reviews[key] = review

bindings = {}
def bind(path, review_id, digest, scope, verdict, **extra):
    r = reviews[review_id]
    bindings.setdefault(path, []).append(dict(review_id=review_id, reviewed_sha256=digest,
        review_path=r['path'], reviewer=r['reviewer'], kind=r['kind'], scope=scope,
        verdict=verdict, **extra))

for row in adapters['files']:
    bind(row['path'], 'final_adapters', row['raw_sha256'], row['scope'], row['judgement'])
for row in frontend['scope_files']:
    bind(row['path'], 'final_frontend', row['sha256'], row['scope'], frontend['verdict'])
for row in cancel['files']:
    bind(row['path'], 'fifth_cancel', row['final_lf_sha256'], cancel['scope'], cancel['status'],
         candidate_CRLF_sha256=row['candidate_sha256'], normalization='candidate CRLF to final LF, independently checked')
for row in cancel['documentation']:
    bind(row['path'], 'fifth_cancel', row['sha256'], 'fifth cancellation contract delta only; not full final documentation',
         row['review'], diff_sha256=row['diff_sha256'])

old_rows = {r['path']: r for r in old['files']}
numstat = [line.split('\t') for line in git('diff', '--numstat', base, head).decode('utf-8').splitlines()]
fifth_delta = {line.split('\t')[-1]: line.split('\t')[:2]
               for line in git('diff', '--numstat', fourth, head).decode('utf-8').splitlines()}
files = []
for added, removed, path in numstat:
    prior = old_rows.get(path)
    raw, blob = (ROOT / path).read_bytes(), git('show', head + ':' + path)
    raw_sha, blob_sha = sha(raw), sha(blob)
    chain = copy.deepcopy(prior['review_chain']) if prior else []
    for review in chain:
        if 'version_delta_from_this_review_to_final' in review:
            review['historical_version_delta_to_8213ced'] = review.pop('version_delta_from_this_review_to_final')
        review['inherited_from_fourth_map'] = True
    chain += copy.deepcopy(bindings.get(path, []))
    for review in chain:
        review['final_worktree_bytes_match'] = review['reviewed_sha256'] == raw_sha
        review['final_git_blob_bytes_match'] = review['reviewed_sha256'] == blob_sha
    exact = [r for r in chain if r['final_worktree_bytes_match']]
    functional = [r for r in exact if r['kind'] == 'ordinary_functional_review']
    independent = [r for r in exact if r['kind'] in ('independent_limited_code_review', 'independent_code_review_with_open_findings')]
    findings = [dict(id=f['id'], priority=f['priority'], title=f['title'],
                     relation='primary' if f['file'] == path else 'related call-chain context')
                for f in frontend['findings'] if f['file'] == path or
                any(loc['file'] == path for loc in f.get('related_locations', []))]
    is_doc = path.endswith('.md')
    remaining = []
    if is_doc:
        remaining.append('最终文档数据/第六显示契约定稿后，父任务+Dalton审Franklin交付；已有窄契约签字不代替最终文档审查。')
        if '/collab/inbox/' in path or '/collab/outbox/' in path:
            remaining = ['历史任务/作者交付记录，仅作来源；不由缺SHA推导新一轮全文代码审查要求。']
    elif any(f['relation'] == 'primary' for f in findings):
        remaining.append('本冻结字节仍有F1/F2显示发现；第六v2候选待独审/冻结，作者测试不关闭发现。')
    elif findings:
        remaining.append('F1相关完成绑定链；第六v2修复待独审，不由原适配器窄签字关闭该后续发现。')
    elif prior and not bindings.get(path):
        remaining += prior['uncovered_delta_or_scope']
    if path in ('gui/g4usim_gui/core/experiment_bundle.py', 'gui/smoke_tests/smoke_k1_relocation.py', 'scripts/test_k1_staging_alias.py'):
        remaining.append('Plato/Bohr资源边界专项独审缺口独立保留；普通功能/测试签字不能替代，本任务不承接或重试。')
    status = ('reviewed_with_open_findings' if any(f['relation'] == 'primary' for f in findings)
              else 'exact_limited_independent_review' if independent
              else 'ordinary_functional_only' if functional
              else 'no_exact_final_binding_in_existing_records')
    files.append(dict(path=path, module=prior['module'] if prior else 'docs',
        authors=prior['authors'] if prior else ['父任务'],
        attribution='inherited recorded ownership; shared git identity is not author evidence',
        fifth_delta_author='父任务' if path in fifth_delta else None,
        base_to_fifth_numstat=dict(added=added, removed=removed),
        fourth_to_fifth_numstat=fifth_delta.get(path),
        fourth_sha256=prior['final_worktree_sha256'] if prior else None,
        final_git_sha256=blob_sha, final_worktree_sha256=raw_sha,
        final_git_worktree_raw_equal=raw_sha == blob_sha,
        LF_normalized_equal=raw.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n'),
        review_chain=chain, last_reviewed_version_binding=exact[-1] if exact else next(
            (r for r in reversed(chain) if r.get('reviewed_sha256')), None),
        exact_independent_review_ids=[r['review_id'] for r in independent],
        exact_functional_review_ids=[r['review_id'] for r in functional],
        status=status, open_frontend_findings=findings, remaining_delta_or_scope=remaining,
        whole_file_or_stage_approval='not inferred from SHA or limited scope'))

candidate_rows = []
for row in candidate['files']:
    assert sha(Path(row['candidate_path']).read_bytes()) == row['candidate_sha256']
    candidate_rows.append(dict(path=row['path'], writer='Tesla', base_sha256=row['base_sha256'],
        v1_sha256=row['v1_sha256'], v2_sha256=row['candidate_sha256'],
        changed_since_v1=row['changed_since_v1'], independent_review='pending; writer excluded from self-review',
        integrated_into_fifth=False))

modules = []
for old_module in old['modules']:
    rows = [f for f in files if f['module'] == old_module['id']]
    modules.append(dict(id=old_module['id'], label=old_module['label'], authors=old_module['authors'],
        files=[r['path'] for r in rows], status_counts=dict(Counter(r['status'] for r in rows)),
        new_review_ids=sorted({r['review_id'] for row in rows for r in row['review_chain'] if r['review_id'] in new_reviews}),
        scope_warning='结合逐文件限定scope和发现，非模块整体通过'))

remaining = [
    dict(id='sixth_ui', owner='Averroes independent review; parent integration/freeze',
         scope='v2 same six files and existing generated/F5 regressions; external no-package completion fix',
         status='ready, sent to parent+Averroes; pending independent signoff/freeze',
         evidence=str(candidate_path), writer_excluded_from_self_review=True),
    dict(id='final_docs', author='Franklin', reviewers=['父任务', 'Dalton'],
         scope='final evidence/data and user/agent contract/status documents after sixth identity is final',
         status='await final data and author delivery; narrow fifth cancel contract review already exists'),
]
snapshot = dict(schema='k1_append_only_review_coverage_v1', timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    mapping_only=True, base_commit=base, historical_fourth_commit=fourth, observed_fifth_commit=head,
    sixth_freeze='not observed; v2 candidate pending independent review', historical_fourth_map=old_pins,
    actual_base_to_fifth_file_count=len(files), actual_fourth_to_fifth_delta=fifth_delta,
    reviews=reviews, modules=modules, files=files,
    status_counts_not_approval=dict(Counter(r['status'] for r in files)),
    new_reviews_exact_match={key: sum(key in f['exact_independent_review_ids'] for f in files) for key in new_reviews},
    candidate_layer=dict(manifest=pin(candidate_path), patch=pin(candidate_path.parent/'candidate.patch'),
        version='v2', files=candidate_rows, old_request_changes=pin(COLLAB/'k1-final-ui-independent.json'),
        v1_directory_immutable=True, independent_review='pending; original v1 REQUEST_CHANGES remains historical'),
    remaining_required_ordinary_scope=remaining,
    blocked_resource_gap=copy.deepcopy(old['resource_boundary_review_gaps']),
    blocked_resource_gap_handling='unresolved, not assigned to this mapper; no retry/rephrase/delegation; parent functional review not substitution',
    previously_reported_gaps_now_superseded=dict(adapters='14 final files covered by explicit final K1 adapter/registry/test review',
        frontend='8 final files logically reviewed independently, with F1/P2 and F2/P3 still open on fifth bytes',
        fifth_cancel='2 final LF files and 3 narrow documentation deltas bound to independent review'),
    author_conflict=dict(three_old_smokes='only other reviewer/parent signoff inherited',
        new_six_candidate='author Tesla cannot independently sign own v1/v2; pending Averroes',
        frontend_eight='Tesla review predates authoring candidate; applies to original fourth/fifth bytes only'),
    no_new_tests=True, no_source_logic_review=True, no_blocked_scope_work=True,
    no_tracked_or_old_report_edits=True, no_matrix_process_operations=True,
    K1_completion_decision='not made', usage='unknown')
stem = 'f9a9ddb-v2-awaiting-independent-r2'
json_path, md_path = HERE/(stem+'.json'), HERE/(stem+'.md')
with json_path.open('x', encoding='utf-8', newline='\n') as handle:
    json.dump(snapshot, handle, ensure_ascii=False, indent=2); handle.write('\n')

md = ['# K1 最终审查覆盖追加快照：第五冻结 / 第六v2待独审', '',
    f'实际HEAD `{head}`，tracked干净；范围 `{base[:7]}..{head[:7]}` 共{len(files)}文件。第四历史图原件与SHA保留，本文件只整理既有签字与版本关系，不作新代码审查或阶段裁决。消耗未知。', '',
    '新增签字依照报告末尾实际scope读取：Averroes最终14文件适配/登记/测试，Tesla八文件普通前端，Dalton第五取消原因2文件及3项窄文档delta。早期适配器报告“剩余前端范围”已由后续八文件审查接续；该前端报告留下F1/P2与F2/P3，不能改记为全绿。', '',
    '当前f9字节仍有完成cwd错投与pending回退；新v2已交父/Averroes待独审、未集成。本图不独审自己的六候选，也不把178/1629等作者自测当独立签字。v1原REQUEST_CHANGES保持历史；后续第六冻结须另追加快照，不能覆写本份。', '',
    '## 仅剩必要普通范围', '',
    '1. Averroes审v2六文件（重点external无package完成投影及新增回归），父任务接收后冻结；随后由父按正式流程绑定最终验证身份。',
    '2. Franklin等最终数据完成文档，父任务与Dalton审最终文档/状态/契约。第五取消的三项窄文档审查已存在，不代替最终文档。', '',
    '无需仅因旧图缺SHA而重开已签的14文件适配器、八文件普通前端或第五reason逻辑审查。历史inbox/outbox是任务/作者来源，未找到SHA签字不自动产生新的全文代码审查要求。正式矩阵/native验证由父任务另管，本图未轮询或启动。', '',
    '## 保留的资源专项缺口（不承接）', '',
    'Plato原bundle广审与Bohr后续资源边界审查均被上游拒绝，缺口未关闭；父普通功能/测试审查不能替代。未重试、改名、换代理或运行late-reparse。事件原件：' + link('out/collab/k1-bundle-review-upstream-incident.json') + '、' + link('out/collab/k1-relocation-candidate/independent-review-incident.json') + '。', '',
    '## 新签字与版本绑定', '',
    '| 审查 | 原报告及身份 | 本第五字节匹配 | scope |', '|---|---|---:|---|']
for key, r in new_reviews.items():
    md.append(f"| {r['reviewer']} / {key} | {link(r['path'])} / `{r['version']}` | {snapshot['new_reviews_exact_match'][key]} | {r['scope']}；{r['verdict']} |")
md += ['', '## 模块索引', '', '| 模块 | 作者来源 | 文件数 | 新签字 |', '|---|---|---:|---|']
for m in modules:
    md.append(f"| {m['label']} | {' / '.join(m['authors'])} | {len(m['files'])} | {', '.join(m['new_review_ids']) or '沿用第四限定链'} |")
md += ['', '## 逐文件最终字节、最后签字与未覆盖项', '',
    'SHA列为第五工作区原字节SHA前12位，JSON保留完整Git/工作区SHA、继承审查链、作者与版本delta。`linux-geant4.yml`仅CRLF工作区与LF blob不同，归一化一致。有限签字不扩张成整文件/模块验收。', '',
    '| 文件 | 作者 / 第五delta作者 | 第五SHA | 最后版本签字 | 未覆盖项或范围 |', '|---|---|---|---|---|']
for row in files:
    latest = row['last_reviewed_version_binding']
    signing = (link(latest['review_path'], latest['review_id']) + ' / `' + latest['reviewed_sha256'][:12] + '`' +
               (' 匹配' if latest['final_worktree_bytes_match'] else '旧版本不同')) if latest else '未找到最终字节签字'
    authors = ' / '.join(row['authors']) + ('；第五delta父任务' if row['fifth_delta_author'] else '')
    left = '；'.join(row['remaining_delta_or_scope']) or '无新增未覆盖delta（仅既有scope）'
    md.append(f"| `{row['path']}` | {authors} | `{row['final_worktree_sha256'][:12]}` | {signing} | {left} |")
md += ['', '## 第六v2候选层：不能自签', '',
    link('out/collab/k1-final-ui-candidate-v2/README.md', '交付说明') + '；' + link('out/collab/k1-final-ui-candidate-v2/manifest.json', 'manifest') +
    f"，manifest SHA `{snapshot['candidate_layer']['manifest']['sha256']}`。六文件均由Tesla写候选；Averroes独审待收据，未替换第五字节。", '',
    '| 文件 | v2完整SHA | v1→v2 | 独审 |', '|---|---|---|---|']
for row in candidate_rows:
    md.append(f"| `{row['path']}` | `{row['v2_sha256']}` | {'改变' if row['changed_since_v1'] else '相同'} | 待Averroes；作者不自审 |")
md += ['', '全部旧map、报告、manifest、产品和测试未修改。没有新测试/矩阵/实窗动作。完整机器可读证据：' +
       f'[{json_path.name}]({json_path.as_posix()})' + '。']
with md_path.open('x', encoding='utf-8', newline='\n') as handle:
    handle.write('\n'.join(md)+'\n')
assert head == git('rev-parse', 'HEAD').decode().strip()
assert not git('status', '--porcelain', '--untracked-files=no').strip()
assert all(sha(Path(p['path']).read_bytes()) == p['sha256'] for p in old_pins)
assert all(f['LF_normalized_equal'] for f in files)
print(json.dumps(dict(json=pin(json_path), markdown=pin(md_path), files=len(files),
    new_review_exact=snapshot['new_reviews_exact_match'], status_counts=snapshot['status_counts_not_approval']), ensure_ascii=False))
