"""Verify selected original bytes and replay the archived strict gate; stdlib only.

Does not read source_absolute, source checkout logs or external CI ZIPs.
Reports remain byte-identical. A copy of the parsed report gets only its log
location remapped in memory to the selected sibling file for cross-OS replay.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--replay-dir',type=Path,required=True)
    parser.add_argument('--increment',help='Default: all increments in increments.json')
    parser.add_argument('--extract-prefix',action='append',default=[],help='Also extract selected raw delivery/identity paths under this logical prefix')
    args=parser.parse_args();base=Path(__file__).resolve().parent
    package=json.loads((base/'package-manifest.json').read_text(encoding='utf-8'))
    for item in package['files']:
        path=base/item['path']
        assert path.resolve().is_relative_to(base.resolve())
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
    replay=args.replay_dir.absolute();replay.mkdir(parents=True,exist_ok=False)
    catalog=json.loads((base/'increments.json').read_text(encoding='utf-8'))
    results=[]
    for increment in catalog['increments']:
        if args.increment and increment['id']!=args.increment:continue
        folder=base/increment['path'];manifest_path=folder/'manifest.json'
        assert sha(manifest_path)==increment['manifest_sha256']
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        archive=folder/manifest['archive']['path']
        assert sha(archive)==manifest['archive']['sha256']==increment['archive_sha256']
        entries=manifest['entries'];logical={e['path']:e for e in entries}
        assert len(logical)==len(entries)
        objects={e['archive_member']:(e['source_sha256'],e['bytes']) for e in entries}
        target=replay/increment['id'];target.mkdir()
        with zipfile.ZipFile(archive) as z:
            assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(objects)
            for name,(expected,size) in objects.items():
                assert name=='objects/'+expected[:2]+'/'+expected
                h=hashlib.sha256();total=0
                with z.open(name) as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk);total+=len(chunk)
                assert total==size and h.hexdigest()==expected
            for entry in entries:
                assert entry['source_sha256']==entry['copy_sha256']
                path=Path(entry['path'])
                assert not path.is_absolute() and '..' not in path.parts
                if entry['role'] in ('original_test_report','report_referenced_raw_log','checker_or_registry_snapshot_not_product_patch') or any(entry['path'].startswith(prefix) for prefix in args.extract_prefix):
                    output=target/path
                    assert output.resolve().is_relative_to(target.resolve())
                    output.parent.mkdir(parents=True,exist_ok=True)
                    output.write_bytes(z.read(entry['archive_member']))
                    assert sha(output)==entry['copy_sha256']
        checker=target/'identity/checker-snapshot/check_report_evidence.py'
        spec=importlib.util.spec_from_file_location('archived_gate_'+increment['id'],checker)
        gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
        gates=[]
        for entry in entries:
            if entry['role']!='original_test_report':continue
            path=target/entry['path'];raw=json.loads(path.read_text(encoding='utf-8'));report=copy.deepcopy(raw)
            # Sole projection is archival file location; raw report and all
            # identity/count/status/digest fields remain unmodified.
            for record in report['results']:
                if record.get('log'):
                    record['log']=record['log'].replace('\\','/').split('/')[-1]
                    assert (path.parent/record['log']).is_file()
            try:
                gate.validate_report(report,report_path=path)
                status='pass';error=None
            except AssertionError as exception:
                assert any(r['status']!='pass' for r in raw['results']),str(exception)
                status='fail';error=str(exception)
                gate.validate_report(report,report_path=path,allow_incomplete=True)
            gates.append(dict(path=entry['path'],strict_gate=status,error=error))
        summary=dict(pass_count=sum(g['strict_gate']=='pass' for g in gates),fail_count=sum(g['strict_gate']=='fail' for g in gates),reports=len(gates))
        assert summary==manifest['strict_gate_summary']
        results.append(dict(increment=increment['id'],original_sources_read=False,zip_sha256=sha(archive),objects_verified=len(objects),entries_verified=len(entries),strict=summary,gates=gates))
    assert results
    (replay/'archive-verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(increment=r['increment'],objects=r['objects_verified'],entries=r['entries_verified'],strict=r['strict']) for r in results],indent=2))

if __name__=='__main__':main()
