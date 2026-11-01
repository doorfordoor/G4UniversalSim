"""Select immutable automation/delivery evidence. No source edits or test/simulation launches."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=next(parent for parent in Path(__file__).resolve().parents
          if (parent/'scripts/check_report_evidence.py').is_file() and (parent/'main.cc').is_file())
SOURCE=ROOT/'out/verification/i2-j1-5fe0a10'
HEAD='5fe0a1052e33c96d033375d0920f29b15d432dcc'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())
def load(path):return json.loads(path.read_text(encoding='utf-8'))

def main():
    global HEAD,SOURCE
    p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,default=ROOT/'out/verification/i2-j1-final-candidate')
    p.add_argument('--source-root',type=Path,default=SOURCE)
    p.add_argument('--head',default=HEAD)
    p.add_argument('--ci-only',action='store_true',help='Do not mark absent local suites pending when appending a CI-only head')
    p.add_argument('--m0-only',action='store_true',help='Adopt only M0 reports/artifacts from this CI head')
    a=p.parse_args();destination=a.destination.absolute();SOURCE=a.source_root.absolute();HEAD=a.head
    assert len(HEAD)==40 and all(c in '0123456789abcdef' for c in HEAD)
    assert SOURCE.is_relative_to(ROOT/'out/verification') and SOURCE.is_dir()
    assert destination.is_relative_to(ROOT/'out/verification') and destination.name.startswith('i2-j1-final-candidate')
    portable=destination/'automated-delivery'
    portable.mkdir(parents=True,exist_ok=True)
    # Every execution is a new increment. Previous archives/manifests are retained.
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    increment=portable/'increments'/stamp
    increment.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('archive_gate',ROOT/'scripts/check_report_evidence.py')
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    selected={};reports=[];omissions=[]
    m0_run_ids=set();m0_job_ids=set();m0_artifact_ids=set()
    if a.m0_only:
        for meta in (SOURCE/'ci').glob('terminal-run-*.json'):
            value=load(meta)
            if value['name']=='M0 static and GUI regression':
                run_id=value['id'];m0_run_ids.add(run_id)
                m0_job_ids.update(j['id'] for j in load(SOURCE/'ci'/f'terminal-jobs-{run_id}.json')['jobs'])
                m0_artifact_ids.update(x['id'] for x in load(SOURCE/'ci'/f'terminal-artifacts-{run_id}.json'))
        assert len(m0_run_ids)==1 and len(m0_job_ids)==2 and len(m0_artifact_ids)==2
    def select(path,logical,role):
        path=Path(path)
        assert path.is_file() and not path.is_symlink(),str(path)
        logical=str(logical).replace('\\','/')
        if a.m0_only:
            name=Path(logical).name
            if logical.startswith(('identity/frozen-desktop/','delivery/')):return
            if logical.startswith('automated/ci/') and not logical.split('/')[2].startswith('m0-report-'):return
            if logical.startswith('automated/ci-metadata/'):
                if name.startswith('terminal-') and not any(str(i) in name for i in m0_run_ids):return
                if name.startswith('job-') and not any(str(i) in name for i in m0_job_ids):return
                if name.endswith('-verified.json') and int(name.split('-')[0]) not in m0_artifact_ids:return
        assert not logical.startswith('/') and '..' not in Path(logical).parts
        if logical in selected:
            assert selected[logical]['source']==path
            return
        selected[logical]=dict(source=path,role=role)
    def add_report(path,logical_root,accepted_heads=None):
        report=load(path)
        assert report['git_head'] in (accepted_heads or {HEAD})
        base=Path(logical_root)/path.parent.name
        select(path,base/'report.json','original_test_report')
        for record in report['results']:
            if record.get('log'):
                name=record['log'].replace('\\','/').split('/')[-1]
                log=path.parent/name
                assert log.is_file(),str(log)
                select(log,base/name,'report_referenced_raw_log')
        try:
            gate.validate_report(report,report_path=path)
            status='pass';error=None
        except AssertionError as exception:
            assert any(r['status']!='pass' for r in report['results']),str(exception)
            status='fail';error=str(exception)
            gate.validate_report(report,report_path=path,allow_incomplete=True)
        reports.append(dict(logical_path=str(base/'report.json').replace('\\','/'),source=str(path.relative_to(ROOT)),
                            profile=report['profile'],cases=len(report['results']),assertions=report['assertions_executed_total'],
                            strict_gate=status,strict_gate_error=error,triage_integrity='pass' if status=='fail' else None,
                            git_head=report['git_head'],source_fingerprint=report['source_fingerprint'],
                            tests_content_fingerprint=report['tests_content_fingerprint']))
    pending=[]
    for profile in ('windows-static','windows-gui','windows113-backend','windows114-backend','windows113-integration','windows114-integration'):
        files=list((SOURCE/profile).rglob('report.json'))
        if not files and not a.ci_only:pending.append(profile)
        for path in sorted(files):add_report(path,Path('automated/local')/profile)
    repairs=ROOT/'out/verification/i2-j1-gdml-explicit-helper-selection-final'
    if repairs.is_dir():
        for path in sorted(repairs.rglob('report.json')):
            repaired=load(path)
            assert repaired['source_fingerprint']=='890635b6d521659e43cf735d07f862c6ebd5959e6c5ea68d023d55332a8a930a'
            add_report(path,Path('automated/local-repair')/repaired['git_head'][:7]/'windows114-integration',
                       {'5fe0a1052e33c96d033375d0920f29b15d432dcc','03d2c483afc0082ad464d2d9a1750fd2e4415a3a',HEAD})
    ci=SOURCE/'ci'
    for path in sorted((ci/'extracted').rglob('report.json')):
        data=load(path)
        if data.get('schema')=='g4usim_test_report' or ('profile' in data and 'results' in data):
            relative=path.relative_to(ci/'extracted')
            add_report(path,Path('automated/ci')/relative.parts[0]/Path(*relative.parts[1:-2]))
    for pattern in ('terminal-*.json','job-*.log','analysis-*-reports.json','installation-analysis-*.json','ci-summary.json','README.md','*-strict.log','*-triage.log','m0-windows-failure.md'):
        for path in ci.glob(pattern):select(path,Path('automated/ci-metadata')/path.name,'original_ci_metadata_or_job_log')
    for path in (ci/'artifacts').glob('*-verified.json'):
        select(path,Path('automated/ci-metadata/artifact-digests')/path.name,'artifact_sha_verification_receipt')
    for path in (SOURCE/'identity').glob('*'):
        if path.is_file():select(path,Path('identity/local')/path.name,'formal_identity_or_original_gate')
    for directory in (ci/'extracted').glob('frozen-desktop-*'):
        for path in directory.rglob('*'):
            if path.is_file() and path.suffix in ('.json','.log'):
                select(path,Path('identity/frozen-desktop')/directory.name/path.relative_to(directory),'frozen_desktop_identity_or_log')
    for directory in (ci/'extracted').glob('full-installation-*'):
        for path in directory.rglob('*'):
            if not path.is_file():continue
            relative=path.relative_to(directory)
            # Separate full plans duplicate inventory embedded in restart inspection.
            # Data install receipt preserves canonical data files; no binary data payload is copied.
            if path.name in ('data-plan.json','plan.json'):
                omissions.append(dict(source=str(path.relative_to(ROOT)),sha256=sha(path),bytes=path.stat().st_size,
                                      reason='Redundant complete plan inventory; restart inspection retains runtime/SDK plan, data install receipt retains dataset inventory'))
                continue
            if path.suffix not in ('.json','.jsonl','.log','.cmake','.txt','.ini','.mac','.csv'):
                omissions.append(dict(source=str(path.relative_to(ROOT)),sha256=sha(path),bytes=path.stat().st_size,
                                      reason='Binary runtime output excluded; no complete run tree or install payload'))
                continue
            select(path,Path('delivery')/directory.name/relative,'original_delivery_receipt_identity_or_build_log')
    # Preserve the old failure independently from subsequent successful increments.
    for name in ('job-124853904289.log','terminal-run-41308545540.json','terminal-jobs-41308545540.json'):
        if (ci/name).is_file():select(ci/name,Path('history/5fe0a10-windows-m0-failure')/name,'original_failed_ci_evidence')
    for name in ('i2-platform-layout-shortname-diagnosis.md','i2-platform-layout-shortname-evidence.json'):
        path=ROOT/'out/collab'/name
        if path.exists():select(path,Path('history/5fe0a10-windows-m0-failure')/name,'independent_failure_diagnosis')
    for name in ('i2-path-fix-independent-review.md','i2-path-fix-independent-strict.log','i2-j1-short-temp-postfix.log','i2-j1-short-temp-postfix-cdrive.log','i2-check-platform-layout-short-temp.py'):
        path=ROOT/'out/collab'/name
        if path.is_file():select(path,Path('independent/path-fixture')/name,'targeted_fixture_evidence_not_full_profile')
    for directory in (ROOT/'out/collab/i2-platform-layout-short-temp-validation',ROOT/'out/verification/i2-j1-path-fix-candidate'):
        if directory.is_dir():
            for path in directory.rglob('*'):
                if path.is_file():select(path,Path('independent/path-fixture')/directory.name/path.relative_to(directory),'targeted_fixture_evidence_not_full_profile')
    select(ROOT/'scripts/test_platform_install_layout.py','independent/path-fixture/test_platform_install_layout.py','targeted_fixture_source_snapshot')
    for pattern in ('i2-k1-windows113-v3-baseline*','i2-k1-windows-baseline-strict-gate.log','*gdml*final*review*','*gdml*final*strict*','i2-j1-03d2c48-windows114-*.log','i2-j1-03d2c48-windows114-final-review.md'):
        for path in (ROOT/'out/collab').glob(pattern):
            if path.is_file():select(path,Path('independent/baseline-and-repair')/path.name,'independent_baseline_or_repair_review')
    for name in ('check_report_evidence.py','run_m0_tests.py'):
        select(ROOT/'scripts'/name,Path('identity/checker-snapshot')/name,'checker_or_registry_snapshot_not_product_patch')
    external=[]
    for receipt in sorted((ci/'artifacts').glob('*-verified.json')):
        info=load(receipt);original=ci/info['archive']
        if a.m0_only and info['id'] not in m0_artifact_ids:continue
        assert original.is_file() and sha(original)==info['github_digest'][7:]==info['actual_sha256']
        assert original.stat().st_size==info['size']
        external.append(dict(artifact_id=info['id'],name=info['name'],source=str(original.relative_to(ROOT)),
                             source_absolute=str(original),sha256=info['actual_sha256'],bytes=info['size'],
                             github_digest=info['github_digest'],included=False,
                             durability='Local long-term original retained, not fully committed; required judgment evidence selected into candidate'))
    assert external,'No local official artifact bytes/receipts found'
    catalog_path=portable/'increments.json'
    catalog=load(catalog_path) if catalog_path.exists() else dict(schema='g4usim_evidence_increments_v1',increments=[])
    prior={}
    for old in catalog['increments']:
        for entry in load(portable/old['path']/'manifest.json')['entries']:
            prior.setdefault(entry['path'],set()).add(entry['source_sha256'])
    fresh_reports=[r for r in reports if sha(selected[r['logical_path']]['source']) not in prior.get(r['logical_path'],set())]
    fresh_directories=[str(Path(r['logical_path']).parent).replace('\\','/')+'/' for r in fresh_reports]
    retained={};reused=0
    for logical,item in selected.items():
        digest=sha(item['source'])
        if digest in prior.get(logical,set()) and item['role']!='checker_or_registry_snapshot_not_product_patch' and not any(logical.startswith(prefix) for prefix in fresh_directories):
            reused+=1
        else:retained[logical]=item
    selected=retained;reports=fresh_reports
    dump(increment/'strict-gates.json',dict(head=HEAD,reports=reports,pending_local_profiles=pending,
                                           source='Current strict validate_report, no legacy flags; known failing report only gets additional incomplete triage'))
    (increment/'strict-gates.log').write_text('\n'.join(f"{r['strict_gate'].upper()} {r['logical_path']}: {r['cases']} cases / {r['assertions']} asserts"+(f"; {r['strict_gate_error']}" if r['strict_gate_error'] else '') for r in reports)+'\n',encoding='utf-8')
    members=[];written={};archive=increment/'evidence.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for logical,item in sorted(selected.items()):
            source=item['source'];size=source.stat().st_size;before=sha(source)
            object_path='objects/'+before[:2]+'/'+before
            if before not in written:
                z.write(source,object_path);written[before]=object_path
            assert source.stat().st_size==size and sha(source)==before,'Source changed during archive'
            members.append(dict(path=logical,archive_member=object_path,source=str(source.relative_to(ROOT)),
                                source_absolute=str(source),source_sha256=before,copy_sha256=before,bytes=size,role=item['role']))
    with zipfile.ZipFile(archive) as z:
        for member in members:
            raw=z.read(member['archive_member'])
            assert len(raw)==member['bytes'] and hashlib.sha256(raw).hexdigest()==member['copy_sha256']
    manifest=dict(schema='g4usim_minimal_evidence_archive_v1',created_at=stamp,head=HEAD,
                  archive=dict(path='evidence.zip',sha256=sha(archive),bytes=archive.stat().st_size),
                  entries=members,external_original_artifacts=external,omissions=omissions,
                  pending_local_profiles=pending,unchanged_prior_entries_reused=reused,strict_gate_summary=dict(pass_count=sum(r['strict_gate']=='pass' for r in reports),
                  fail_count=sum(r['strict_gate']=='fail' for r in reports),reports=len(reports)),
                  boundaries=['No native evidence selected; root owns native integration',
                              'No application executables, DLLs, dataset payloads, SDK installation tree or complete run tree',
                              'Official CI ZIPs are local long-term originals, not fully committed; required judgment evidence selected',
                              'Original catalog/license-text payload absent from CI artifact is not recreated; receipt license hashes/origins retained',
                              'Known Windows M0 failure is preserved; later CI must be a separate increment, never overwrite old evidence'])
    dump(increment/'manifest.json',manifest)
    catalog['increments'].append(dict(id=stamp,path='increments/'+stamp,head=HEAD,manifest_sha256=sha(increment/'manifest.json'),
                                      archive_sha256=sha(archive),archive_bytes=archive.stat().st_size))
    dump(catalog_path,catalog)
    builder_target=portable/'archive_candidate.py'
    if Path(__file__).resolve()!=builder_target.resolve():
        shutil.copyfile(__file__,builder_target)
    package_files=[]
    for path in sorted(portable.rglob('*')):
        if path.is_file() and path.name!='package-manifest.json':
            package_files.append(dict(path=path.relative_to(portable).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
    dump(portable/'package-manifest.json',dict(schema='g4usim_candidate_package_files_v1',files=package_files,
                                              note='Candidate archive integrity only; retained failing reports remain failures'))
    if (portable/'refresh_indexes.py').is_file():
        subprocess.run([sys.executable,str(portable/'refresh_indexes.py')],check=True)
    print(json.dumps(dict(portable=str(portable),increment=stamp,entries=len(members),unique_objects=len(written),
                         original_selected_bytes=sum(m['bytes'] for m in members),unique_raw_bytes=sum(next(m['bytes'] for m in members if m['source_sha256']==s) for s in written),
                         archive_bytes=archive.stat().st_size,external_original_zip_bytes=sum(a['bytes'] for a in external),
                         strict=manifest['strict_gate_summary'],pending=pending),indent=2))

if __name__=='__main__':main()
