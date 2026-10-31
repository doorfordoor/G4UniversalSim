"""Copy final seventh evidence using established byte-copy primitives; no tests or UI."""
from pathlib import Path
import argparse,collections,datetime,hashlib,importlib.util,json
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--windows-audit',required=True,type=Path)
p.add_argument('--native-mapping',required=True,type=Path)
p.add_argument('--i1-receipt',required=True,type=Path)
p.add_argument('--receipt',action='append',default=[],type=Path)
args=p.parse_args();root=Path.cwd();c=root/'out/collab';src=root/'out/verification/k1-2914b39';ci=src/'ci';dst=c/'k1-delivery-staging/verification-2914b39'
spec=importlib.util.spec_from_file_location('established_archive',c/'k1-archive-8213ced.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.HEAD='2914b3962167325628ede699b1c14a9d224dec41';m.GENERATION=7;m.SOURCE=src;m.DEST=dst
load=m.load;require=m.require;sha=m.digest
w=load(args.windows_audit.resolve());review=load(ci/'review-result.json');frozen=load(src/'frozen-case-manifest.json');build=load(src/'build-identity.json')
require(w['head']==review['head']==frozen['head_sha']==build['head']==m.HEAD,'Frozen identity mismatch')
require(w['status']=='passed_strict_report_and_baseline_audit' and not w['failed_checks'],'Windows final audit failed')
require(review['terminal'] and review['evidence_complete'] and review['automation_review_passed'],'CI final audit incomplete')
require(review['report_count']==12 and review['case_executions']==548,'CI count incomplete')
require(w['case_total']==182 and sha(Path(w['report']))==w['report_sha256'],'Windows final report changed')
for path in [args.native_mapping,args.i1_receipt,*args.receipt]:require(path.resolve().is_file(),'Final receipt missing')
native=load(args.native_mapping.resolve());i1=load(args.i1_receipt.resolve())
require(native.get('status')=='passed_identity_mapping_only' and native.get('seventh_frozen_head')==m.HEAD,'Native mapping not final seventh identity receipt')
require(native.get('sixth_source_fingerprint')==native.get('seventh_source_fingerprint')==frozen['source_fingerprint'],'Native product mapping differs')
require(i1.get('seventh_frozen_head')==m.HEAD and i1.get('all_I1_bytes_unchanged') is True and i1.get('I1_decision')=='defined_scope_complete','I1 seventh mapping not complete')
require(not dst.exists(),'Exclusive new archive only; never overwrite/resume')
dst.mkdir(parents=True);a=m.Archive()
a.write('archive-started.json',m.raw_json(dict(head=m.HEAD,archive_execution_completed=False,phase_complete=False)))
for n in ['frozen-case-manifest.json','build-identity.json','capabilities.json']:a.copy(src/n,'identity/'+n)
require(sha(src/'frozen-binary/G4UniversalSim.exe')==build['backend_sha256'],'Backend identity mismatch')
a.excluded.append(dict(source=(src/'frozen-binary/G4UniversalSim.exe').relative_to(root).as_posix(),sha256=build['backend_sha256'],reason='Frozen EXE identity only; original remains at source'))
win=Path(w['report']).parent;files,dirs=m.files_below(win)
for path in files:
    if path.parent==win:a.copy(path,'windows/'+path.name)
a.zip_files([(path,path.relative_to(win).as_posix()) for path in files if path.parent!=win],'windows/case-originals.zip')
a.copy(src/'windows-run.log','windows/driver/windows-run.log')
gates=load(c/'k1-seventh-windows-review-gates.json')
for ix,g in enumerate(gates):
    require(g['exit_code']==0 and sha(Path(g['log']))==g['log_sha256'],'Windows gate differs')
    a.copy(Path(g['log']),f'windows/gates/{ix:02d}-'+Path(g['log']).name)
a.copy(c/'k1-seventh-windows-review-gates.json','windows/gates/original-gate-receipt.json')
for path in sorted(ci.iterdir()):
    if path.is_file():a.copy(path,'ci/control/'+path.name)
ind=load(ci/'independent-profiles.json')
for r in ind['reports']:
    parent=Path(r['path']).parent
    for path in sorted(parent.iterdir()):
        if path.is_file():a.copy(path,'ci/reports/'+r['artifact']+'/'+r['profile']+'/'+path.name)
for path in [args.windows_audit,args.native_mapping,args.i1_receipt,*args.receipt]:a.copy(path.resolve(),'review/'+path.name)
for path in [c/'k1-seventh-window-case-status.json',c/'k1-resume-i1-seventh-mapping.json']:
    if path.exists() and path.name not in {x.name for x in [args.windows_audit,args.native_mapping,args.i1_receipt,*args.receipt]}:a.copy(path,'review/'+path.name)
a.copy(Path(__file__).resolve(),'archive-builder.py')
a.copy(c/'k1-archive-8213ced.py','archive-primitives-original.py')
historical=[]
for generation in ['8213ced','f9a9ddb','4167c44']:
    path=c/('k1-delivery-staging/verification-'+generation+'/archive-manifest.json')
    historical.append(dict(path=path.relative_to(root).as_posix(),sha256=sha(path),scope='historical evidence only, not seventh reruns'))
a.write('historical-native-references.json',m.raw_json(dict(native_mapping=args.native_mapping.as_posix(),prior_archives=historical,no_claim_of_repeated_native_runs=True)))
a.final_source_check()
text=f'''# K1 第七冻结证据

冻结 `{m.HEAD}`。本机 Windows {w['case_total']}/0/0、{w['assertions_summed']} 断言；官方 CI 4 jobs、4 原 ZIP、12 reports、548/0/0、{review['assertions_executed_total']} 断言。严格/F5逐例及总量门禁通过，原字节未改写。

原生观察按 review 中 native mapping 的历史提交适用性解释；本归档不把第四/第五/第六观察称为第七重新运行。第六 cp1252 failure 及 native 勘误留在独立六代归档。

I1 以其独立收据及第七映射限定范围。required 资源边界独审缺口保持；K1 phase_complete=false。root 主审另以独立补充件加入，本归档未纳入更新中的主审草稿。

官方原 ZIP 位于 ci/control/；原报告和逐例日志另列 ci/reports/。本机深层 case evidence 在 windows/case-originals.zip，逐成员 source→destination SHA 见 selection.json。旧报告绝对路径保持原文，由外层交付 manifest 定位。无新增独立 EXE，官方 ZIP 内原有 EXE 字节保持。
'''
a.write('README.md',text.encode())
a.write('selection.json',m.raw_json(a.records));a.write('excluded-executable-inventory.json',m.raw_json(a.excluded))
a.write('archive-manifest.json',m.raw_json(dict(schema='k1_seventh_archive_v1',head=m.HEAD,evidence_generation=7,phase_complete=False,automation_verification_passed=True,selection_records=len(a.records),original_backend_sha256=build['backend_sha256'],source_fingerprint=frozen['source_fingerprint'],tests_content_fingerprint=frozen['tests_content_fingerprint'],native_scope='historical applicability mapping; no invented seventh observations',draft_not_completion_receipt=True,generated_files=list(a.generated),required_resource_review='upstream_refused_incomplete_not_retried')))
files,_=m.files_below(dst);require(not any(x.stat().st_size>=100*1024*1024 for x in files),'Oversized archive file; preserve partial output, do not stage')
index=[dict(path=x.relative_to(dst).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in files]
a.write('final-files.json',m.raw_json(dict(files=index,excluded_self=['final-files.json','archive-verification.json'])))
for x in index:require(sha(dst/x['path'])==x['sha256'],'Final archive bytes changed')
a.write('archive-verification.json',m.raw_json(dict(head=m.HEAD,archive_execution_completed=True,phase_complete=False,source_entries_verified=len(a.records),original_bytes_compared=sum(x['bytes'] for x in a.records),archive_manifest_sha256=sha(dst/'archive-manifest.json'),final_index_sha256=sha(dst/'final-files.json'),independent_archive_review='not_performed_by_author')))
print(json.dumps(dict(destination=str(dst),source_entries=len(a.records),bytes=sum(x['bytes'] for x in a.records),phase_complete=False)))
