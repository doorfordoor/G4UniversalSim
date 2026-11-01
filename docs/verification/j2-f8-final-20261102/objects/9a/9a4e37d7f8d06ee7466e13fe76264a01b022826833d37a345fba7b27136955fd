"""Independent checks of retained CI installation artifacts; no simulation/build."""
import argparse, hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
HEAD='18c5858fd6e80a5cb6096beacebfef69c479ad49'
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def h(raw):return hashlib.sha256(raw).hexdigest()
def git_blobs(names):
    result=subprocess.run(['git','-c','core.longpaths=true','cat-file','--batch'],input=('\n'.join(HEAD+':'+n for n in names)+'\n').encode(),capture_output=True,check=True)
    pos=0;blobs={}
    for name in names:
        end=result.stdout.index(b'\n',pos);header=result.stdout[pos:end].split()
        assert header[1]==b'blob',(name,header)
        size=int(header[2]);blobs[name]=result.stdout[end+1:end+1+size];pos=end+1+size+1
    assert pos==len(result.stdout)
    return blobs
def checkout_identities(expected):
    names=list(expected);blobs=git_blobs(names)
    # Attribute evaluation is read-only; pin its owning file to the candidate.
    attrs=subprocess.check_output(['git','-c','core.longpaths=true','show',HEAD+':.gitattributes'])
    assert attrs.replace(b'\r\n',b'\n')==Path('.gitattributes').read_bytes().replace(b'\r\n',b'\n')
    r=subprocess.run(['git','-c','core.longpaths=true','check-attr','-z','text','eol','--stdin'],input=('\0'.join(names)+'\0').encode(),capture_output=True,check=True)
    parts=r.stdout.split(b'\0');rules={}
    for i in range(0,len(parts)-1,3):rules.setdefault(parts[i].decode(),{})[parts[i+1].decode()]=parts[i+2].decode()
    raw_matches=0;converted=[]
    for name in names:
        raw=blobs[name]
        if h(raw)==expected[name]:raw_matches+=1;continue
        rule=rules[name]
        assert rule.get('text') in ('set','auto') and rule.get('eol')!='lf' and b'\0' not in raw,(name,rule)
        assert h(raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))==expected[name],name
        converted.append(dict(path=name,attributes=rule))
    return dict(files=len(names),raw_git_blob_matches=raw_matches,declared_text_checkout_crlf_matches=converted,
                note='Only candidate checkout text EOL is modeled; evidence logs are always hashed as raw bytes')
def main():
    p=argparse.ArgumentParser();p.add_argument('artifact_directory',type=Path);args=p.parse_args()
    base=args.artifact_directory/'acceptance';delivery=load(base/'delivery-report.json')
    assert delivery['status']=='verified' and delivery['origin_git_commit']==HEAD
    assert delivery['geant4_version']=='11.4.3',delivery['geant4_version']
    snapshot=load(base/'source-snapshot.json')
    assert sha(base/'source-snapshot.json')==delivery['source_snapshot_sha256']
    assert len(snapshot['files'])==delivery['snapshot_file_count']
    source_identity=checkout_identities(snapshot['files'])
    workflow='.github/workflows/full-installation.yml'
    workflow_identity=checkout_identities({workflow:delivery['workflow_sha256']})
    for stage in delivery['stages']:
        assert stage['exit_code']==0 and stage['log_finalized'] is True
        name=stage['log'].replace('\\','/').rsplit('/',1)[-1]
        assert sha(base/'logs'/name)==stage['log_sha256'],name
    index=load(base/'evidence/index.json')
    for entry in index:
        path=base/entry['path'];assert path.resolve().is_relative_to(base.resolve())
        assert path.stat().st_size==entry['size_bytes'] and sha(path)==entry['sha256']
        assert entry['source_stable_during_copy'] is True
    for profile in ('runtime','sdk'):
        flow=load(base/(profile+'-evidence/flow-report.json'))
        assert flow['status']=='verified' and flow['profile']==profile
        assert all(cmd['exit_code']==0 for cmd in flow['commands'])
        assert load(base/(profile+'-evidence/uninstall-receipt.json'))['status']=='uninstalled'
        if profile=='runtime':
            assert flow['completed_events']==5
            assert [c['stage'] for c in flow['commands']]==['data-discovery','simulation','root-csv','root-roundtrip','frozen-gui']
        else:
            for label in ('sdk-consumer','sdk-application'):
                probe=load(base/('sdk-evidence/'+label+'.json'))
                assert probe['status']=='verified'
                assert [c['stage'] for c in probe['commands']]==['configure','build','run']
                assert all(c['exit_code']==0 for c in probe['commands'])
                for role,identity in delivery['host_tools'].items():
                    assert probe['host_tools'][role]['sha256']==identity['sha256']
    summary={}
    for line in (base/'runtime-evidence/result/run_summary.txt').read_text(encoding='utf-8').splitlines():
        if '=' in line:
            key,value=line.split('=',1);summary[key.strip()]=value.strip()
    assert summary['status']==summary['summary_write_status']=='completed'
    assert summary['planned_event_count']==summary['actual_completed_event_count']=='5'
    assert summary['output_failure_status']=='none'
    result=dict(candidate_head=HEAD,platform=delivery['platform'],status='independently_verified',
                stages=len(delivery['stages']),stage_raw_logs_sha_verified=True,retained_index_objects_sha_verified=len(index),
                source_checkout_identity=source_identity,workflow_checkout_identity=workflow_identity,
                runtime_actual_summary_completed_events=5,sdk_consumer_and_full_application_verified=True,
                host_tool_identity_consistent=True,runtime_and_sdk_uninstalled=True)
    out=ROOT/('installation-'+delivery['platform']+'-checked.json')
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status=result['status'],platform=result['platform'],stages=result['stages'],sources=source_identity['files'],completed_events=5)))
if __name__=='__main__':main()
