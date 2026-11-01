"""Offline artifact provenance, strict gates and matching historical comparison."""
from pathlib import Path
import datetime, hashlib, importlib.util, json, sys
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
sys.path.insert(0,str(REPO/'out/collab/j2-ci-review'))
import ci_review as c

HEAD='2901f4254303c3a9089c9025717908c0d77ff190'
identity=c.read(ROOT/'frozen-local-identity.json')
lanes={'m0-report-ubuntu-latest':'m0-linux','m0-report-windows-latest':'m0-windows',
       'linux-evidence-11.3.2':'linux113','linux-evidence-11.4.3':'linux114'}
catalog={}
for p in ROOT.glob('artifacts-*.json'):
    for a in (c.read(p).get('structuredContent') or c.read(p)).get('artifacts',[]):
        if a['id'] in catalog: assert catalog[a['id']]['digest']==a['digest']
        catalog[a['id']]=a
checker_path=ROOT/'checker-2901f42.py'
assert c.sha(checker_path)==c.read(ROOT/'checker-identity.json')['sha256']
spec=importlib.util.spec_from_file_location('j2_candidate_2901f42_gate',checker_path)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
out=[]
for a in catalog.values():
    assert a['workflow_run']['head_sha']==HEAD and not a['expired']
    name=f'{a["name"]}-{a["id"]}';archive=ROOT/'artifacts'/(name+'.zip')
    if not archive.exists():continue
    assert archive.stat().st_size==a['size_in_bytes']
    assert 'sha256:'+c.sha(archive)==a['digest']
    directory=ROOT/'extracted'/name
    if not directory.exists():c.extract_zip(archive,directory)
    entry=dict(artifact_id=a['id'],name=a['name'],run_id=a['workflow_run']['id'],zip_sha256=c.sha(archive),reports=[])
    for p in directory.rglob('report.json'):
        report=c.read(p)
        if report.get('schema')!=gate.REPORT_SCHEMA:continue
        lane=lanes[a['name']];bid=c.baseline_id(lane,report['profile']);b=c.baseline(bid)
        assert report['git_head']==HEAD
        assert report['source_fingerprint']==identity['source_fingerprint']
        assert report['tests_content_fingerprint']==identity['tests_content_fingerprint']
        assert report['platform'].startswith('Windows' if lane=='m0-windows' else 'Linux')
        assert report.get('tracked_source_gate')=='pass' and not report.get('untracked_source_files')
        if lane in ('linux113','linux114') and report['profile'] in ('backend','integration'):
            assert report['backend_build_identity']['geant4_version_number']==(1132 if lane=='linux113' else 1143)
        bp=ROOT/'historical'/bid/'report.json'
        if not bp.exists():c.materialize_baseline(b,bp.parent)
        assert c.sha(bp)==b['report_sha256']
        old=c.read(bp);gate.validate_report(c.local_projection(bp,old),report_path=bp)
        current=c.local_projection(p,report)
        # A strict failure status must stay failed; independently hash every
        # retained log even though strict validation stops at the first fail.
        for record in current['results']:
            assert gate.log_digest(Path(record['log']),legacy=False)==record['log_sha256']
        assert sum(r['assertions_executed'] for r in current['results'])==report['assertions_executed_total']
        try:gate.validate_report(current,report_path=p,baseline=old);status='pass';error=None
        except AssertionError as exc:status='fail';error=str(exc)
        oldcases={r['name']:r for r in old['results']};newcases={r['name']:r for r in report['results']}
        comparison=[dict(name=n,before=r['assertions_executed'],after=newcases.get(n,{}).get('assertions_executed'),
                         status=newcases.get(n,{}).get('status')) for n,r in oldcases.items()]
        failures=[]
        for r in current['results']:
            if r['status']=='pass':continue
            log=Path(r['log']);lines=log.read_text(encoding='utf-8',errors='replace').splitlines()
            failures.append(dict(name=r['name'],log=str(log.relative_to(ROOT)),sha256=c.sha(log),tail=lines[-18:]))
        result=dict(report=str(p.relative_to(ROOT)),report_sha256=c.sha(p),lane=lane,profile=report['profile'],
                    strict_gate=status,strict_error=error,baseline_id=bid,baseline_report_sha256=b['report_sha256'],
                    every_raw_log_sha_verified=True,
                    assertions_before=old['assertions_executed_total'],assertions_after=report['assertions_executed_total'],
                    old_case_comparison=comparison,new_cases=sorted(set(newcases)-set(oldcases)),failures=failures)
        entry['reports'].append(result)
        print(a['name'],report['profile'],status,len(failures),'failures',report['assertions_executed_total'],'baseline',old['assertions_executed_total'])
    out.append(entry)
summary=dict(candidate_head=HEAD,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             source_fingerprint=identity['source_fingerprint'],tests_content_fingerprint=identity['tests_content_fingerprint'],
             strict_pass=sum(r['strict_gate']=='pass' for a in out for r in a['reports']),
             strict_fail=sum(r['strict_gate']=='fail' for a in out for r in a['reports']),
             artifacts=out,release_accepted=False,
             note='No allow-incomplete/legacy flags; non-pass reports remain failed. Only available report profiles compared; absent downstream profiles are not success.')
(ROOT/'report-gates-current.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
