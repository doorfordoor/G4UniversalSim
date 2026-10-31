"""Finalize only already-collected official seventh evidence; no execution/reruns."""
from pathlib import Path
import collections,datetime,hashlib,json
ci=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):
    with (ci/name).open('xb') as stream:stream.write((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())
cfg=read(ci/'watch-config.json');head=cfg['head'];frozen=read(Path(cfg['frozen']))
if head!='2914b3962167325628ede699b1c14a9d224dec41':raise ValueError('Wrong freeze')
if sha(Path(cfg['frozen']))!=cfg['frozen_sha256']:raise ValueError('Frozen bytes changed')
pipeline=read(ci/'pipeline-result.json');audit=read(ci/'audit.json');ind=read(ci/'independent-profiles.json')
if not (pipeline['checks_passed'] and audit['checks_passed'] and ind['checks_passed']):raise ValueError('Strict or independent gates not passed')
if [r['exit_code'] for r in pipeline['operations']]!=[0,0,0]:raise ValueError('Pipeline not complete')
if head!=audit['head_sha'] or head!=ind['head']:raise ValueError('Audit head mismatch')
if audit['report_count']!=12 or ind['report_count']!=12 or audit['case_executions']!=548 or ind['case_executions']!=548:raise ValueError('Incomplete coverage')
runs=[];archives=[]
for label,rid in [('linux',41189260366),('m0',41189260331)]:
    r=read(ci/(label+'-run.json'));jobs=read(ci/(label+'-jobs.json'))['jobs'];api=read(ci/(label+'-artifacts.json'))
    if (r['id'],r['head_sha'],r['event'],r['run_attempt'],r['status'],r['conclusion'])!=(rid,head,'push',1,'completed','success'):raise ValueError('Run identity/terminal mismatch')
    if len(jobs)!=2 or not all(j['run_id']==rid and j['status']=='completed' and j['conclusion']=='success' for j in jobs):raise ValueError('Jobs incomplete')
    if api['total_count']!=len(api['artifacts']) or len(api['artifacts'])!=2:raise ValueError('Artifact coverage incomplete')
    for j in jobs:
        if (ci/('job-'+str(j['id'])+'.log')).stat().st_size<100:raise ValueError('Missing decoded job log')
    runs.append(dict(label=label,id=rid,url=r['html_url'],conclusion=r['conclusion'],jobs=[dict(id=j['id'],name=j['name'],conclusion=j['conclusion']) for j in jobs]))
    for a in api['artifacts']:
        p=ci/(a['name']+'.zip');sealed=ci/'collection/archives'/p.name
        if a['expired'] or a['workflow_run']['id']!=rid or a['workflow_run']['head_sha']!=head:raise ValueError('Artifact identity mismatch')
        if p.stat().st_size!=a['size_in_bytes'] or 'sha256:'+sha(p)!=a['digest'] or sha(sealed)!=sha(p):raise ValueError('Artifact byte mismatch')
        archives.append(dict(name=a['name'],id=a['id'],run_id=rid,bytes=p.stat().st_size,official_digest=a['digest'],path=p.name))
counts=collections.Counter();sealed_checks=0
for r in ind['reports']:
    p=Path(r['path']);sealed=ci/'collection/artifacts'/r['artifact']/p.relative_to(ci/r['artifact'])
    if sha(p)!=r['report_sha256'] or sha(sealed)!=sha(p):raise ValueError('Sealed report changed')
    sealed_checks+=1;counts.update(r['counts'])
    if r['strict_gate']!='passed' or r['baseline_strict_gate']!='passed' or any(r[k] for k in ['raw_log_errors','identity_errors','assertion_regressions','failures']):raise ValueError('Profile failed')
    for row in r['logs']:
        p=Path(row['path']);sealed=ci/'collection/artifacts'/r['artifact']/p.relative_to(ci/r['artifact'])
        if sha(p)!=row['sha256'] or sha(sealed)!=sha(p):raise ValueError('Sealed log changed')
        sealed_checks+=1
if dict(counts)!={'pass':548}:raise ValueError('Failed/skipped case')
if len(audit['case_logs'])!=548 or sum(r['assertions'] for r in ind['reports'])!=audit['assertions_executed_total']:raise ValueError('Count mismatch')
if not all(r['per_case_and_total_baseline']=='passed' for r in audit['reports']):raise ValueError('Baseline comparison failed')
v2=read(ci/'v2-formal-evidence.json');p3=read(ci/'p3-evidence.json')
if not(v2['checks_passed'] and p3['checks_passed'] and v2['head']==p3['head']==head):raise ValueError('Component receipt mismatch')
result=dict(schema='k1_seventh_ci_independent_review_v1',head=head,terminal=True,evidence_complete=True,automation_review_passed=True,runs=runs,archives=archives,report_count=12,unique_frozen_cases=182,case_executions=548,counts=dict(counts),assertions_executed_total=audit['assertions_executed_total'],strict_gate_passed=12,F5_same_platform_per_case_and_total_passed=12,assertion_regressions=[],raw_log_errors=[],identity_errors=[],zip_members_verified=len(audit['zip_members']),sealed_report_and_log_sha_checks=sealed_checks,source_fingerprint=frozen['source_fingerprint'],tests_content_fingerprint=frozen['tests_content_fingerprint'],integrated_UI_v2_formal_evidence='v2-formal-evidence.json',external_completion_observations=v2['external_completion_observations'],terminal_component_evidence='p3-evidence.json',terminal_controlled_observations=p3['controlled_mode_observations'],no_allow_incomplete=True,no_reruns=True,no_tracked_source_test_edits=True,stage_acceptance=cfg['stage_acceptance'],phase_complete=False,CI_pass_does_not_close_stage=True,model='gpt-6.1-sol',reasoning_effort='medium',consumption='unknown',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
save('review-result.json',result)
text=['# 第七冻结官方 CI 终态审核','',f'冻结 `{head}`：4 jobs、4 官方 ZIP、12 reports、548/0/0 执行通过；{result["assertions_executed_total"]} 断言。12 份报告严格门禁与 F5 同平台逐例/总量比较全部通过。','']
text += [f'- [{r["label"]} {r["id"]}]({r["url"]})：普通 push / attempt 1 / success。' for r in runs]
text += ['',f'官方 ZIP 大小/SHA、{result["zip_members_verified"]} 个文件成员、12 份报告及 548 个日志在直接展开与 sealed 副本间全部一致；完整列表见 audit.json，联网身份及汇总见 review-result.json。','', '第七仅单行将诊断序列化改为 ASCII 安全输出。UI v2 的 4 平台40条 external 无 package 完成观察均通过；终态组件四平台各11模式和8份 cancel/edit 观察通过。两者均为自动组件证据，不能冒 native 或物理验收。','', '报告内原 git dirty/status 如实保留：指纹和 tracked source gate 不代表所有工作目录完全 clean。原官方 ZIP、报告和日志未改写，未重试 job，未使用 allow-incomplete。decoded job logs 是 connector 解码文本保存，不能称 HTTP 原始压缩字节。','', '本收据只确认第七 CI；本机 Windows/原生映射由 root 另收。required 资源边界独审缺口保持，K1 不阶段关闭。第六 cp1252 失败历史保持原件，不回写为通过。','']
with (ci/'REVIEW.md').open('xb') as stream:stream.write(('\n'.join(text)).encode())
checkpoint=read(ci/'checkpoint.json');checkpoint.update(state='Official four jobs / four ZIPs / twelve reports passed strict and F5 audit',whole_CI_evidence='complete_passed',next='Ready for archival; root owns Windows/native mapping and final delivery',completed_utc=result['completed_utc'])
(ci/'checkpoint.json').write_text(json.dumps(checkpoint,indent=2)+'\n',encoding='utf-8')
paths=[p for p in ci.iterdir() if p.is_file() and p.name!='evidence-manifest.json']+[Path(cfg['frozen'])]
save('evidence-manifest.json',dict(head=head,files=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)],note='Self-excluded; detailed ZIP members and original report/log inventory in audit.json'))
print(json.dumps(result,ensure_ascii=True))
