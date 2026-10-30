"""Write a concise historical-round receipt from audited bytes; never alter originals."""
from pathlib import Path
import hashlib, json

BASE = Path(__file__).resolve().parent
audit = json.loads((BASE / 'evidence-integrity-audit.json').read_text(encoding='utf8'))
failures = [row for row in audit['case_logs'] if row['status'] != 'pass' or row['exit_code'] != 0]
summary = {key: audit[key] for key in ('head_sha', 'status', 'candidate_stage_status', 'evidence_collection_complete', 'problems', 'runs', 'jobs', 'artifacts', 'reports', 'case_executions', 'report_count', 'source_fingerprint', 'tests_content_fingerprint', 'boundary')}
summary.update(strict_pass_reports=sum(row['strict_baseline_gate_exit'] == 0 for row in audit['reports']), failed_case_executions=len(failures), failures=failures,
               evidence_integrity_checked=True, official_zip_count=len(audit['artifacts']), decoded_job_log_count=len(audit['jobs']),
               zip_member_count=len(audit['zip_members']), skipped_case_executions=sum(row['status'] == 'skip' for row in audit['case_logs']),
               stage_acceptance='not_accepted', audit_sha256=hashlib.sha256((BASE / 'evidence-integrity-audit.json').read_bytes()).hexdigest())
text = '# F4 首轮 CI 原始证据：未通过\n\n'
text += '冻结提交 `' + audit['head_sha'] + '`。候选状态 `historical_candidate_pending_or_failed_native`，不得据此关闭 F4。\n\n'
text += 'Linux [run 41047666520](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41047666520)；M0 [run 41047666580](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41047666580)。全部为本次 push 的第 1 次执行，未 rerun、取消或改写 CI。\n\n'
text += f"已核对 {len(audit['artifacts'])} 个官方 ZIP 摘要和全部解包成员字节、{len(audit['jobs'])} 份 connector 解码 job 日志、{len(audit['reports'])} 份报告与 {len(audit['case_logs'])} 个用例日志原始 SHA/断言 marker。冻结清单每个 profile 的顺序及数目精确匹配 static28/gui43/backend59/integration21；Linux 各151、M0 各71。Job 日志保存的是 connector 解码后 UTF-8 文本，不冒称 GitHub 原始压缩日志字节。\n\n"
text += f"严格同平台、同 Geant4、同 profile 的 F1 基线门禁通过 {summary['strict_pass_reports']}/12；失败用例 {len(failures)}，skip {summary['skipped_case_executions']}。失败报告保持原样，无 incomplete/legacy 放宽。后台实际构建身份及源码/测试指纹均核对；git_dirty 原值保留。\n\n"
text += '| 官方产物 | Profile | 用例 | 断言 | 严格门禁退出码 | 失败用例 |\n|---|---|---:|---:|---:|---|\n'
for row in audit['reports']:
    text += f"| {row['artifact']} | [{row['profile']}]({row['path']}) | {row['cases']} | {row['assertions']} | {row['strict_baseline_gate_exit']} | {', '.join(row['failures']) or '无'} |\n"
text += '\n失败详情：\n\n'
for row in failures:
    text += f"- {row['artifact']} / [{row['case']}]({row['path']}): exit `{row['exit_code']}`，断言 `{row['assertions']}`；日志 `none_dealloc` 发生于解释器 finalizing，不能以打印 OK/断言通过替代正常退出。\n"
text += '\n本轮另有 root 报告的实窗几何目标未绘制缺陷，证据位于 `out/verification/f4-visible-5d6f008/native/06-geometry-painted.png`。旧 Windows 全量已由 root 主动中断，CI 收集者未中断任何工作流。此文件只记录这两个官方 CI 运行，不代替 Windows 全量、原生实窗或物理验收。\n\n'
text += '[逐 ZIP 成员/报告/日志证据检查](evidence-integrity-audit.json)；[简明机器收据](round-summary.json)；[冻结用例清单](frozen-case-manifest.json)。失败诊断线索见 `out/collab/f4-ci-failure-notification.md`，未经实验证实的线索不得写作原因。\n'

for path, raw in ((BASE / 'round-summary.json', (json.dumps(summary, ensure_ascii=False, indent=2) + '\n').encode('utf8')), (BASE / 'README.md', text.encode('utf8'))):
    if path.exists():
        assert path.read_bytes() == raw, 'Refusing changed existing receipt'
    else:
        with path.open('xb') as stream:
            stream.write(raw)
print(json.dumps({key: summary[key] for key in ('status', 'candidate_stage_status', 'evidence_collection_complete', 'report_count', 'case_executions', 'strict_pass_reports', 'failed_case_executions', 'skipped_case_executions')}, ensure_ascii=False))
