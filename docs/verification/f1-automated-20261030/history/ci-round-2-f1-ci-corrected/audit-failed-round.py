"""Read-only audit of this collected failed CI round; never modifies original receipts."""
from pathlib import Path,PurePosixPath
import hashlib,json,re,sys,importlib.util
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3]
FOLDER=Path(__file__).resolve().parent
HEAD='3d1faf1b256a945ac800c08bacf51db57f8ca416'
EXPECTED={'linux-evidence-11.3.2':{'static','gui','backend','integration'},'linux-evidence-11.4.3':{'static','gui','backend','integration'},'m0-report-ubuntu-latest':{'static','gui'},'m0-report-windows-latest':{'static','gui'}}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,data):
    raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    if path.exists():assert path.read_bytes()==raw,'refusing changed existing receipt';return
    with path.open('xb') as f:f.write(raw)


def main():
    frozen=read(FOLDER/'frozen-case-manifest.json');assert frozen['head_sha']==HEAD
    ci=read(FOLDER/'ci-evidence.json');assert ci['head_sha']==HEAD and ci['status']=='not_passed' and ci['complete'] is True
    spec=importlib.util.spec_from_file_location('ci_case_evidence_gate',ROOT/'scripts/check_report_evidence.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    artifacts=[];jobs=[]
    for run_id in (41024949824,41024949832):
        raw=read(FOLDER/f'{run_id}-run.json');assert raw['id']==run_id and raw['head_sha']==HEAD and raw['status']=='completed'
        assert raw['conclusion']==('failure' if run_id==41024949824 else 'success')
        for job in read(FOLDER/f'{run_id}-jobs.json')['jobs']:
            assert job['run_id']==run_id and job['status']=='completed'
            log=FOLDER/f"job-{job['id']}.log";assert log.is_file()
            jobs.append({'id':job['id'],'run_id':run_id,'name':job['name'],'status':job['status'],'conclusion':job['conclusion'],'log':log.relative_to(FOLDER).as_posix(),'log_bytes':log.stat().st_size,'log_sha256':sha(log)})
        for item in read(FOLDER/f'{run_id}-artifacts.json')['artifacts']:
            assert item['workflow_run']['id']==run_id and item['workflow_run']['head_sha']==HEAD
            archive=FOLDER/(item['name']+'.zip');actual='sha256:'+sha(archive);assert actual==item['digest']
            artifacts.append({'name':item['name'],'id':item['id'],'run_id':run_id,'official_digest':item['digest'],'actual_sha256':actual,'zip_bytes':archive.stat().st_size})
    assert len(artifacts)==4 and {row['name'] for row in artifacts}==set(EXPECTED)
    assert len(jobs)==4 and sum(row['conclusion']=='failure' for row in jobs)==2
    records=[];case_logs=[];identities=set();failures=[]
    for path in sorted(FOLDER.rglob('report.json')):
        report=read(path);artifact=path.relative_to(FOLDER).parts[0];profile=report['profile']
        assert artifact in EXPECTED and profile in EXPECTED[artifact] and (artifact,profile) not in identities
        identities.add((artifact,profile));assert report['git_head']==HEAD and report['tracked_source_gate']=='pass'
        for key in ('source_fingerprint','tests_content_fingerprint'):assert report[key]==frozen[key]
        assert {row['name'] for row in report['results']}==set(frozen['profiles'][profile])
        nonpass=[row for row in report['results'] if row['status']!='pass']
        matching=[row for row in ci['reports'] if row['path'].replace('\\','/')==path.relative_to(FOLDER).as_posix()];assert len(matching)==1
        if nonpass:
            assert profile=='integration' and artifact.startswith('linux-evidence-') and [row['name'] for row in nonpass]==['effective_gdml']
            assert matching[0]['strict_gate_exit_code']!=0
            # Explicit triage structural check, never a release green: original
            # report/statuses are untouched; all failed log hashes are checked below.
            gate.validate_report(report,report_path=path,allow_incomplete=True)
        else:
            assert matching[0]['strict_gate_exit_code']==0
            gate.validate_report(report,report_path=path)
        for row in report['results']:
            name=PurePosixPath(row['log'].replace('\\','/')).name
            choices=[path.parent/name,path.parent/'logs'/name]
            log=next((p for p in choices if p.is_file()),None)
            assert log is not None and log.resolve().is_relative_to(FOLDER.resolve())
            actual=sha(log);assert actual==row['log_sha256']
            marker=re.findall(rb'^G4USIM_ASSERTS=(\d+)\r?$',log.read_bytes(),re.M)
            assert marker and int(marker[-1])==row['assertions_executed']
            assert row['assert_probe']==report['assert_probe'] and type(row['exit_code']) is int
            if row['status']=='pass':assert row['exit_code']==0 and row['assertions_executed']>0
            else:assert row['status']=='fail' and row['exit_code']!=0
            item={'artifact':artifact,'profile':profile,'case':row['name'],'status':row['status'],'exit_code':row['exit_code'],'assertions':row['assertions_executed'],'path':log.relative_to(FOLDER).as_posix(),'log_sha256':actual,'log_bytes':log.stat().st_size}
            case_logs.append(item)
            if row['status']=='fail':
                failures.append({**item,'diagnostic':"helper terminated after throwing xercesc_3_3::OutOfMemoryException; script assertion run.returncode==0 failed; this is a failure receipt, not proof of physical-memory exhaustion"})
        records.append({'artifact':artifact,'profile':profile,'path':path.relative_to(FOLDER).as_posix(),'report_sha256':sha(path),'cases':len(report['results']),'assertions':report['assertions_executed_total'],'failures':[row['name'] for row in nonpass],'strict_gate_exit_code':matching[0]['strict_gate_exit_code'],'triage_integrity_only':bool(nonpass),'release_accepted':not bool(nonpass),'git_dirty':report['git_dirty']})
    expected_pairs={(name,profile) for name,profiles in EXPECTED.items() for profile in profiles}
    assert identities==expected_pairs and len(records)==12
    assert len(case_logs)==2*sum(len(frozen['profiles'][p]) for p in ('static','gui','backend','integration'))+2*sum(len(frozen['profiles'][p]) for p in ('static','gui'))
    assert len(failures)==2
    audit={'scope':'Complete byte/assertion/probe/case-set integrity audit, including failed cases; not release acceptance','head_sha':HEAD,'reports':records,'artifacts':artifacts,'job_logs':jobs,'case_logs':case_logs,'case_log_count':len(case_logs),'all_case_log_sha256_matched':True,'failed_case_digests_checked':True,'source_fingerprint':frozen['source_fingerprint'],'tests_content_fingerprint':frozen['tests_content_fingerprint']}
    save(FOLDER/'evidence-integrity-audit.json',audit)
    summary={'head_sha':HEAD,'status':'failed','stage_acceptance':'not_passed','evidence_collection_complete':True,'linux_run':41024949824,'m0_run':41024949832,'reports_total':len(records),'strict_pass_reports':sum(not row['failures'] for row in records),'strict_rejected_reports':sum(bool(row['failures']) for row in records),'case_executions':len(case_logs),'passed_case_executions':sum(row['status']=='pass' for row in case_logs),'failed_case_executions':len(failures),'artifacts':artifacts,'job_logs':jobs,'reports':records,'failures':failures,'boundary':'Both Linux integrations failed effective_gdml. Original reports/logs remain unchanged. Integrity-complete is not a passing report gate, not a passed frozen stage, and not UI or physics validation.'}
    save(FOLDER/'failed-round-summary.json',summary)
    text='# F1第二冻结CI：未通过\n\n冻结提交：`'+HEAD+'`。本轮证据收集完整，阶段验收未通过。Linux run41024949824的11.3.2/11.4.3两个job均failure；M0 run41024949832两job成功。未重跑CI、未构建或运行主全量、未更改tracked或旧证据。\n\n四个官方原ZIP摘要均匹配，安全解包拒绝绝对/盘符/上溯/重复/符号链接成员；12份原报告均保留，所有'+str(len(case_logs))+'条case日志raw SHA与断言marker已核对，包括失败日志。10份成功报告严格门禁exit0；两份失败integration严格门禁非零，另做allow_incomplete仅triage结构检查及全日志哈希检查，不能将其称为绿色。`ci-evidence.json` status=not_passed、complete=true仅指集合完整。\n\n## 两个失败\n\n'
    for row in failures:text+='- '+row['artifact']+'：`effective_gdml` exit '+str(row['exit_code'])+'，已执行'+str(row['assertions'])+'条入口；[原case日志]('+row['path']+')，SHA `'+row['log_sha256']+'`。helper抛`xercesc_3_3::OutOfMemoryException`后终止，脚本`run.returncode==0`断言失败；不据异常类名认定机器物理内存耗尽。\n'
    text+='\n## 报告清单\n\n| Artifact | Profile | Cases | 非pass | Strict gate |\n|---|---|---:|---|---:|\n'
    for row in records:text+='| '+row['artifact']+' | ['+row['profile']+']('+row['path']+') | '+str(row['cases'])+' | '+(','.join(row['failures']) or '无')+' | '+str(row['strict_gate_exit_code'])+' |\n'
    text+='\n原始job日志：[Linux11.4](job-123960735990.log)、[Linux11.3](job-123960736266.log)，以及两份M0日志见evidence-integrity-audit.json。GitHub connector的decoded文本日志按原返回UTF-8保存（含BOM）；原ZIP按二进制保存，官方digest来自对应artifact metadata。未保存临时下载URL或任何凭据。verify helper只执行verify模式，未执行collect或credential fallback。\n\n[汇总](failed-round-summary.json)、[完整逐日志校验](evidence-integrity-audit.json)、[收集与门禁记录](ci-evidence.json)、[verify命令收据](verify-only-receipt.json)。CI通用git_dirty字段按报告原样保留，不以其代替tracked-source gate/双指纹，也不推断其具体来源。可见UI和物理验证均不由本次CI收集完成。\n'
    readme=FOLDER/'README.md'
    if readme.exists():assert readme.read_bytes()==text.encode('utf-8')
    else:
        with readme.open('xb') as f:f.write(text.encode('utf-8'))
    print(json.dumps({key:summary[key] for key in ('status','evidence_collection_complete','reports_total','strict_pass_reports','strict_rejected_reports','case_executions','failed_case_executions')}))

if __name__=='__main__':main()
