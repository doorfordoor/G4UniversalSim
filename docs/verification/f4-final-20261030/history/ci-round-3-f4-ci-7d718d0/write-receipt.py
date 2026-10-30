"""Final-candidate CI receipt; CI success never substitutes for native/Windows acceptance."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parent
audit=json.loads((BASE/'evidence-integrity-audit.json').read_text(encoding='utf8'))
failures=[r for r in audit['case_logs'] if r['status']!='pass' or r['exit_code']!=0]
keys=('head_sha','status','candidate_stage_status','evidence_collection_complete','report_profile_coverage_complete','missing_profiles','problems','runs','jobs','artifacts','reports','case_executions','report_count','source_fingerprint','tests_content_fingerprint','boundary','qt_runtime','helper_builds','helper_runs')
summary={key:audit[key] for key in keys}
summary.update(expected_reports_for_complete_matrix=12,expected_case_executions=448,
               strict_pass_reports=sum(r['strict_baseline_gate_exit']==0 for r in audit['reports']),
               failed_case_executions=len(failures),failures=failures,
               skipped_case_executions=sum(r['status']=='skip' for r in audit['case_logs']),
               evidence_integrity_checked=True,official_zip_count=len(audit['artifacts']),decoded_job_log_count=len(audit['jobs']),
               zip_member_count=len(audit['zip_members']),stage_acceptance='requires_separate_root_windows_native_receipts',
               audit_sha256=hashlib.sha256((BASE/'evidence-integrity-audit.json').read_bytes()).hexdigest())
passed=summary['status']=='passed' and summary['report_profile_coverage_complete'] and summary['strict_pass_reports']==12 and summary['case_executions']==448 and not failures
summary['ci_acceptance_passed']=passed
text='# F4 最终候选 CI：'+('通过' if passed else '未通过')+'\n\n'
text+='冻结提交 `'+audit['head_sha']+'`。Linux [41054895374](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41054895374)、M0 [41054895506](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41054895506)，本次push第1次执行；未rerun、取消或改写工作流。\n\n'
text+=f"已收取{summary['official_zip_count']}个官方ZIP、{summary['decoded_job_log_count']}份完整connector解码job日志、{summary['report_count']}份实际报告、{summary['case_executions']}次用例执行。官方ZIP摘要、本地ZIP、解包成员字节、报告与用例日志SHA/断言marker、冻结head/source/tests身份及逐profile有序清单均已核对。严格同平台/同Geant4/profile的F1基线门禁通过{summary['strict_pass_reports']}/{summary['report_count']}；fail{len(failures)}，case skip{summary['skipped_case_executions']}。\n\n"
text+='完整预期为Linux每版本152（static28/gui44/backend59/integration21）、M0每平台72，共448次执行。以下报告为实际取得的原件；没有用缺失/失败轮替代完整验收。\n\n'
text+='| 官方产物 | Profile | 用例 | 断言 | 严格门禁退出码 | 失败用例 |\n|---|---|---:|---:|---:|---|\n'
for row in audit['reports']:
    text+=f"| {row['artifact']} | [{row['profile']}]({row['path']}) | {row['cases']} | {row['assertions']} | {row['strict_baseline_gate_exit']} | {', '.join(row['failures']) or '无'} |\n"
text+='\nQt运行身份由实际binding smoke日志提供：\n\n'
for row in audit['qt_runtime']:
    identity=row['identity']
    text+=f"- {row['artifact']}: Python {identity['python'].split()[0]}，PySide6/shiboken6/Qt {identity['PySide6']}/{identity['shiboken6']}/{identity['Qt']}；100次普通void/空属性读取的4组delta均0，且用例正常退出（核查={row['pass']}）。[原日志]({row['log']})\n"
text+='\n辅助程序的实际构建完成记录见机器收据。由于两Linux job在static阶段即失败，本轮effective_gdml/scoring_numeric/random_command_semantics均未执行，篡改日志负对照亦未执行；不能以构建成功替代这些验收。\n\n'
if audit['missing_profiles']:
    text+='未执行/缺失profile：`'+repr(audit['missing_profiles'])+'`。不得据此宣称完整矩阵。\n\n'
if audit['problems']:
    text+='Linux本轮具体失败原因是导入PySide6.QtGui时缺少系统库`libEGL.so.1`，共5种用例×2个Geant4版本，在执行断言前退出1。这是新增的CI系统依赖缺口，与前两轮none_dealloc失败分开记录。M0两个job均成功，实际Qt运行版本均为6.11.3。\n\n'
    text+='未通过项：\n\n'+''.join('- '+problem+'\n' for problem in audit['problems'])+'\n'
text+='这是CI验收收据。Windows本机全量、原生实窗和最终阶段关闭由root独立记录；CI通过不证明物理验证。Job日志保存的是connector解码后的UTF-8文本，不冒称原始GitHub压缩日志字节。旧5d6f008和096f4b3两轮原件保持原样。\n\n'
text+='[逐字节独立检查](evidence-integrity-audit.json)、[机器汇总](round-summary.json)、[冻结清单](frozen-case-manifest.json)、[原始CI收集摘要](ci-evidence.json)。\n'
for path,raw in ((BASE/'round-summary.json',(json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf8')),(BASE/'README.md',text.encode('utf8'))):
    if path.exists():assert path.read_bytes()==raw,'Existing receipt differs'
    else:
        with path.open('xb') as stream:stream.write(raw)
print(json.dumps({key:summary[key] for key in ('status','ci_acceptance_passed','report_count','case_executions','strict_pass_reports','failed_case_executions','skipped_case_executions')},ensure_ascii=False))
