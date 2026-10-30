"""Second F4 round: preserve the actual upstream failure and missing stages."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parent
audit=json.loads((BASE/'evidence-integrity-audit.json').read_text(encoding='utf8'))
failures=[r for r in audit['case_logs'] if r['status']!='pass' or r['exit_code']!=0]
summary={k:audit[k] for k in ('head_sha','status','candidate_stage_status','evidence_collection_complete','report_profile_coverage_complete','missing_profiles','problems','runs','jobs','artifacts','reports','case_executions','report_count','source_fingerprint','tests_content_fingerprint','boundary')}
summary.update(expected_reports_for_complete_matrix=12,strict_pass_reports=sum(r['strict_baseline_gate_exit']==0 for r in audit['reports']),
               failed_case_executions=len(failures),failures=failures,skipped_case_executions=sum(r['status']=='skip' for r in audit['case_logs']),
               evidence_integrity_checked=True,official_zip_count=len(audit['artifacts']),decoded_job_log_count=len(audit['jobs']),
               zip_member_count=len(audit['zip_members']),stage_acceptance='not_accepted',audit_sha256=hashlib.sha256((BASE/'evidence-integrity-audit.json').read_bytes()).hexdigest())
text='# F4 第二轮 CI 原始证据：未通过\n\n'
text+='冻结提交 `'+audit['head_sha']+'`。Linux [41050259071](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41050259071)、M0 [41050258833](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41050258833) 均已结束，均为 push 第1次执行；未 rerun、取消或改写工作流。\n\n'
text+='M0 Windows 成功；两个 Linux Geant4 job 和 M0 Ubuntu 在 `gui_f4_layout` 的257断言后 `none_dealloc`、exit -6失败。后端及集成步骤因前置GUI失败而 skipped，官方只产生8份报告，不能称12份完整矩阵。用例报告内部skip为0，与4个未执行profile分开记录。\n\n'
text+='已完整收取4个官方ZIP和4份connector解码job日志。官方ZIP摘要、本地ZIP与解包成员字节、8份报告及284条用例日志SHA/断言marker、逐profile清单和冻结源码/测试指纹已核对。严格同平台F1基线门禁通过5/8，3份GUI报告按失败拒绝；未使用incomplete/legacy放宽。完整清单151项仍为static28/gui43/backend59/integration21，本轮每平台实际只执行static+gui71项。\n\n'
text+='| 官方产物 | Profile | 用例 | 断言 | 严格门禁退出码 | 失败用例 |\n|---|---|---:|---:|---:|---|\n'
for row in audit['reports']:
    text+=f"| {row['artifact']} | [{row['profile']}]({row['path']}) | {row['cases']} | {row['assertions']} | {row['strict_baseline_gate_exit']} | {', '.join(row['failures']) or '无'} |\n"
text+='\n后端/integration未执行，因此本轮不声称完成后端运行或对应build identity验收。job日志为connector解码后UTF-8文本，不冒称GitHub原始压缩日志字节。Windows本机全量和原生实窗状态由root另外验收，本CI收据不代替它们。\n\n'
text+='独立诊断见 `out/collab/f4-ci-independent-diagnosis.md`：现有PySide6.12/Python3.11存在更广的None引用损耗，不能只修改highlighter getter便宣布修复。该目录只保存当前失败轮次，旧5d6f008证据在兄弟目录且未覆盖。\n\n'
text+='[完整逐字节核对](evidence-integrity-audit.json)、[简明机器收据](round-summary.json)、[冻结用例清单](frozen-case-manifest.json)。\n'
for path,raw in ((BASE/'round-summary.json',(json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf8')),(BASE/'README.md',text.encode('utf8'))):
    with path.open('xb') as stream:stream.write(raw)
print(json.dumps({k:summary[k] for k in ('status','evidence_collection_complete','report_profile_coverage_complete','report_count','case_executions','strict_pass_reports','failed_case_executions')},ensure_ascii=False))
