"""J2 independent CI evidence tools. Default/preparation commands are offline.

Only list-runs performs GET requests, and requires an explicit full candidate SHA.
No dispatch, rerun, push, token storage, or product writes are implemented.
"""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, re, shutil, stat, sys, zipfile
if not __debug__:
    raise RuntimeError('Strict evidence checking cannot run with Python optimization enabled')
from pathlib import Path, PurePosixPath
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
BASELINES = ROOT / 'out/collab/j2-f8-baselines.json'
ARCHIVE = ROOT / 'docs/verification/i2-j1-final-20261101/automated-delivery'
REPO = 'doorfordoor/G4UniversalSim'
WORKFLOWS = {
    'm0-static-gui.yml': ['m0-report-ubuntu-latest', 'm0-report-windows-latest'],
    'linux-geant4.yml': ['linux-evidence-11.3.2', 'linux-evidence-11.4.3'],
    'full-installation.yml': ['full-installation-Linux', 'full-installation-Windows'],
    'desktop-package.yml': ['frozen-desktop-Linux', 'frozen-desktop-Windows'],
}

def read(p): return json.loads(Path(p).read_bytes())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def output_path(p):
    p=Path(p).resolve()
    assert p.is_relative_to((ROOT/'out').resolve()), 'Evidence writes must remain under out/'
    return p
def save(p,value):
    p=output_path(p);p.parent.mkdir(parents=True,exist_ok=True)
    assert not p.exists(), f'Refusing to overwrite evidence: {p}'
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def full_sha(text):
    assert re.fullmatch('[0-9a-f]{40}',text), 'A full, exact candidate commit SHA is required'
    return text
def baseline_id(lane,profile):
    if lane in ('m0-linux','m0-windows'):
        assert profile in ('static','gui')
        return ('linux' if lane=='m0-linux' else 'windows')+'-m0-6310969-'+profile
    assert lane in ('linux113','linux114','windows113','windows114')
    return lane+'-'+profile
def baseline(bid):
    rows=read(BASELINES)['baselines']
    found=[x for x in rows if x['id']==bid]
    assert len(found)==1, f'No unique matching historical baseline: {bid}'
    return found[0]
def baseline_bytes(row):
    original=ROOT/row['original_report']
    if original.is_file(): data=original.read_bytes()
    else:
        with zipfile.ZipFile(ROOT/row['archive_zip']) as z: data=z.read(row['archive_member'])
    assert hashlib.sha256(data).hexdigest()==row['report_sha256']
    value=json.loads(data)
    assert value['profile']==row['profile'] and value['git_head']==row['head']
    assert len(value['results'])==row['cases'] and value['assertions_executed_total']==row['assertions']
    assert value['assert_probe']=='settrace_assert_lines_v3'
    assert value['log_digest_algorithm']=='sha256_raw_bytes_lf_v2'
    assert all(x['status']=='pass' for x in value['results'])
    return data,value
def checker():
    spec=importlib.util.spec_from_file_location('j2_strict_gate',ROOT/'scripts/check_report_evidence.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def local_projection(path,raw):
    value=copy.deepcopy(raw)
    for row in value['results']:
        name=row['log'].replace('\\','/').rsplit('/',1)[-1]
        candidates=[path.parent/name,path.parent/'logs'/name]
        found=[p for p in candidates if p.is_file()]
        assert found, f'Artifact-local log missing: {row["name"]}; never fall back to original machine paths'
        assert all(p.resolve().is_relative_to(path.parent.resolve()) for p in found), 'Log symlink escapes artifact report directory'
        if len(found)>1: assert sha(found[0])==sha(found[1]), 'Ambiguous local log copies'
        row['log']=str(found[0].resolve())
    return value
def materialize_baseline(row,destination):
    destination=output_path(destination);destination.mkdir(parents=True,exist_ok=False)
    archive=ROOT/row['archive_zip'];manifest_path=archive.parent/'manifest.json'
    catalog=read(ARCHIVE/'increments.json')
    item=next(i for i in catalog['increments'] if i['id']==row['archive_increment'])
    assert sha(manifest_path)==item['manifest_sha256']
    manifest=read(manifest_path);entries={x['path']:x for x in manifest['entries']}
    assert len(entries)==len(manifest['entries'])
    data,report=baseline_bytes(row)
    needed=[row['archive_logical_report']]
    parent=PurePosixPath(row['archive_logical_report']).parent
    needed += [str(parent/(r['log'].replace('\\','/').rsplit('/',1)[-1])) for r in report['results']]
    with zipfile.ZipFile(archive) as z:
        for logical in dict.fromkeys(needed):
            entry=entries[logical];raw=z.read(entry['archive_member'])
            assert len(raw)==entry['bytes']
            assert hashlib.sha256(raw).hexdigest()==entry['copy_sha256']==entry['source_sha256']
            target=destination/PurePosixPath(logical).name
            assert not target.exists();target.write_bytes(raw)
    assert (destination/'report.json').read_bytes()==data
    return destination/'report.json'
def gate_report(path,lane,head,source_fp,tests_fp,out):
    path=Path(path).resolve();raw=read(path);head=full_sha(head)
    assert raw['git_head']==head and raw['source_fingerprint']==source_fp
    assert raw['tests_content_fingerprint']==tests_fp
    assert raw.get('tracked_source_gate')=='pass', 'Tracked source gate was not passed'
    assert not raw.get('untracked_source_files'), 'Untracked product source evidence'
    os_name='Linux' if lane.startswith('linux') or lane=='m0-linux' else 'Windows'
    assert raw['platform'].startswith(os_name), f'Wrong platform for lane {lane}'
    if lane.endswith(('113','114')) and raw['profile'] in ('backend','integration'):
        expected=1132 if lane.endswith('113') else 1143
        assert raw['backend_build_identity']['geant4_version_number']==expected
    bid=baseline_id(lane,raw['profile']);row=baseline(bid)
    out=output_path(out);out.mkdir(parents=True,exist_ok=False)
    bp=materialize_baseline(row,out/'historical')
    historical=read(bp);current=local_projection(path,raw);gate=checker()
    gate.validate_report(local_projection(bp,historical),report_path=bp)
    gate.validate_report(current,report_path=path,baseline=historical)
    old={r['name']:r['assertions_executed'] for r in historical['results']}
    new={r['name']:r['assertions_executed'] for r in raw['results']}
    comparison=[dict(name=k,before=v,after=new.get(k),delta=new[k]-v) for k,v in old.items()]
    result=dict(status='strict_pass',candidate_head=head,lane=lane,profile=raw['profile'],
                report_path=str(path),report_sha256=sha(path),baseline_id=bid,baseline_sha256=row['report_sha256'],
                assertions_before=historical['assertions_executed_total'],assertions_after=raw['assertions_executed_total'],
                old_cases=comparison,new_cases=sorted(set(new)-set(old)),
                projection='Only log locations remapped in memory to verified artifact-local files; raw report untouched')
    save(out/'gate.json',result);return result
def extract_zip(archive,destination):
    destination=output_path(destination);assert not destination.exists()
    with zipfile.ZipFile(archive) as z:
        names=set()
        for i in z.infolist():
            name=i.filename.replace('\\','/');path=PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts and ':' not in name
            assert path.parts and path.parts[0] not in ('','.')
            normalized=name.casefold().rstrip('/')
            assert normalized not in names,'Duplicate/case-colliding ZIP entry';names.add(normalized)
            assert not stat.S_ISLNK(i.external_attr>>16),'ZIP symlink forbidden'
            assert (destination/Path(*path.parts)).resolve().is_relative_to(destination)
        destination.mkdir(parents=True)
        for i in z.infolist():
            target=destination/Path(*PurePosixPath(i.filename.replace('\\','/')).parts)
            if i.is_dir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(i) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst)
    return dict(archive=str(Path(archive).resolve()),sha256=sha(archive),destination=str(destination))
def list_runs(head,output):
    # Deliberately GET-only public API. Never invoked by prepare/self-test.
    from urllib.request import Request,urlopen
    head=full_sha(head);pages=[];runs=[]
    for page in range(1,11):
        url=f'https://api.github.com/repos/{REPO}/actions/runs?head_sha={head}&event=push&per_page=100&page={page}'
        request=Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'G4UniversalSim-J2-independent-review'})
        with urlopen(request,timeout=30) as response:body=json.load(response)
        pages.append(body)
        batch=body['workflow_runs'];runs.extend(r for r in batch if r['head_sha']==head and r['event']=='push')
        if len(batch)<100:break
    selected={name:[r for r in runs if r['path'].split('@',1)[0].endswith('/'+name)] for name in WORKFLOWS}
    save(output,dict(candidate_head=head,repository=REPO,raw_pages=pages,runs_by_workflow=selected,
                     note='No automatic success claim or rerun choice; inspect all attempts and collect connector jobs/logs/artifacts'))
def receipt_check(path,head,output):
    value=read(path);head=full_sha(head)
    assert value['candidate_head']==head
    runs=value['workflows'];assert set(runs)==set(WORKFLOWS)
    run_ids=set();artifact_ids=set()
    for workflow,expected_names in WORKFLOWS.items():
        entry=runs[workflow];run=entry['run']
        assert run['id'] not in run_ids;run_ids.add(run['id'])
        assert run['head_sha']==head and run['event']=='push'
        assert run['status']=='completed' and run['conclusion']=='success'
        assert run['path'].split('@',1)[0].endswith('/'+workflow)
        jobs=entry['jobs'];assert len(jobs)>=2
        assert all(j['run_id']==run['id'] and j['head_sha']==head and j['status']=='completed' and j['conclusion']=='success' for j in jobs)
        assert Path(entry['logs_zip']).is_file() and sha(entry['logs_zip'])==entry['logs_sha256']
        artifacts=entry['artifacts'];assert sorted(a['name'] for a in artifacts)==sorted(expected_names)
        for a in artifacts:
            assert a['id'] not in artifact_ids;artifact_ids.add(a['id'])
            assert not a['expired'] and a['run_id']==run['id']
            assert Path(a['zip']).is_file() and sha(a['zip'])==a['download_sha256']
            digest=a.get('github_digest')
            if digest:assert digest=='sha256:'+a['download_sha256']
    save(output,dict(status='workflow_receipts_verified',candidate_head=head,
                     note='Four successful exact-head push runs, jobs, logs and artifact ownership verified; report/installation/desktop semantic gates remain separate'))
def prepare(output):
    rows=read(BASELINES)['baselines'];checked=[]
    for row in rows:
        baseline_bytes(row)
        checked.append(dict(id=row['id'],profile=row['profile'],report_sha256=row['report_sha256'],cases=row['cases'],assertions=row['assertions']))
    save(output,dict(status='offline_prepared_not_candidate_acceptance',baseline_count=len(checked),baselines=checked,
                     workflows=WORKFLOWS,repository=REPO,remote_requests=0,
                     archive_route=str(ARCHIVE/'verify_archive.py'),
                     note='Metadata/report bytes checked; raw log strict replay runs when each matching baseline is materialized'))
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('list-runs');a.add_argument('--head',required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('receipt-check');a.add_argument('--head',required=True);a.add_argument('--receipt',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('extract');a.add_argument('--zip',type=Path,required=True);a.add_argument('--destination',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('gate');a.add_argument('--head',required=True);a.add_argument('--source-fingerprint',required=True);a.add_argument('--tests-fingerprint',required=True);a.add_argument('--report',type=Path,required=True);a.add_argument('--lane',required=True);a.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    if args.command=='prepare':prepare(args.output)
    elif args.command=='list-runs':list_runs(args.head,args.output)
    elif args.command=='receipt-check':receipt_check(args.receipt,args.head,args.output)
    elif args.command=='extract':save(args.output,extract_zip(args.zip,args.destination))
    elif args.command=='gate':gate_report(args.report,args.lane,args.head,args.source_fingerprint,args.tests_fingerprint,args.output_dir)
if __name__=='__main__':main()
