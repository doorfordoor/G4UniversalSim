"""Refresh derived navigation across immutable increments; no original-source reads."""
import hashlib
import json
from pathlib import Path
import zipfile

BASE=Path(__file__).resolve().parent
def dump(name,value):
    (BASE/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())
def main():
    catalog=json.loads((BASE/'increments.json').read_text(encoding='utf-8'))
    external={};delivery=[];reports=[]
    for increment in catalog['increments']:
        folder=BASE/increment['path'];manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        assert hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest()==increment['manifest_sha256']
        gates=json.loads((folder/'strict-gates.json').read_text(encoding='utf-8'))
        gate_by_path={g['logical_path']:g for g in gates['reports']}
        for artifact in manifest['external_original_artifacts']:
            if artifact['artifact_id'] in external:assert external[artifact['artifact_id']]['sha256']==artifact['sha256']
            external[artifact['artifact_id']]=artifact
        with zipfile.ZipFile(folder/manifest['archive']['path']) as archive:
            for entry in manifest['entries']:
                path=entry['path']
                if entry['role']=='original_test_report':
                    report=json.loads(archive.read(entry['archive_member']))
                    expected={'static':44,'gui':59,'backend':61,'integration':29}.get(report['profile'])
                    reports.append(dict(increment=increment['id'],path=path,source=entry['source'],source_sha256=entry['source_sha256'],
                                        head=report['git_head'],git_dirty=report['git_dirty'],profile=report['profile'],cases=len(report['results']),
                                        assertions=report['assertions_executed_total'],strict_gate=gate_by_path[path]['strict_gate'],
                                        selection_scope='full_profile_inventory_size' if len(report['results'])==expected else 'targeted_selection_not_full_profile'))
                if path.startswith('delivery/') and path.endswith(('install-receipt.json','flow-report.json','fetch-report.json')):
                    value=json.loads(archive.read(entry['archive_member']))
                    delivery.append(dict(increment=increment['id'],path=path,source=entry['source'],source_sha256=entry['source_sha256'],derived_navigation_only=True,
                                         receipt={k:v for k,v in value.items() if k in ('schema','status','profile','version','geant4_version','platform','architecture','artifacts','catalog_sha256','scope','completed_events','verified_files','md5_note','integrity_note','source')}))
    dump('external-original-artifacts.json',list(external.values()))
    dump('delivery-index.json',delivery)
    dump('reports-index.json',dict(note='All retained historical/current reports; not a single-head release total. Targeted selections are labelled separately. Inventory size alone is not complete case-name matching.',reports=reports))
    files=[]
    for path in sorted(BASE.rglob('*')):
        if path.is_file() and path.name!='package-manifest.json':
            files.append(dict(path=path.relative_to(BASE).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size))
    dump('package-manifest.json',dict(schema='g4usim_candidate_package_files_v1',files=files,note='Archive integrity only; historical failing reports remain failures'))
    print(json.dumps(dict(increments=len(catalog['increments']),indexed_reports=len(reports),targeted_selections=sum(r['selection_scope'].startswith('targeted') for r in reports),official_artifacts=len(external),files=len(files),bytes=sum(f['bytes'] for f in files)),indent=2))
if __name__=='__main__':main()
