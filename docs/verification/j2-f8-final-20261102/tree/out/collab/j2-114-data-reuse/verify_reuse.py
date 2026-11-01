from pathlib import Path
import concurrent.futures,hashlib,json,os,re,subprocess,sys,time
sys.path.insert(0,str(Path('packaging').resolve()))
from ci_fetch_geant4_data import parse_config
base=Path.cwd().resolve(); out=base/'out/collab/j2-114-data-reuse'
prefix=base/'out/i2-controlled/windows114-data'; data=prefix/'data'
sdk=base/'out/dependencies/geant4-11.4.3/geant4-11.4.3-win64'
config=sdk/'lib/cmake/Geant4/Geant4Config.cmake'
exe=Path(sys.argv[1]) if len(sys.argv)>1 else base/'out/build-i2-windows114/Release/G4UniversalSim.exe'
receipt={'schema':'j2_geant4_114_data_reuse_v1','status':'running','started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'prefix':str(prefix),'data_root':str(data),'sdk_config':str(config),'dataset_matching_basis':'SDK dataset versions/canonical folders AND full published payload hashes; required_complete is not the version proof','source_authentication':'Local I2 published artifact/receipt reuse; observed hashes are not independent upstream source authentication','steps':[]}
def save():
    temp=out/'receipt.json.tmp'; temp.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8'); os.replace(temp,out/'receipt.json')
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()
def checked(row):
    path=prefix/row['path']; resolved=path.resolve(strict=True)
    if not resolved.is_relative_to(prefix.resolve()): raise ValueError('payload escapes prefix: '+row['path'])
    size=path.stat().st_size
    actual=digest(path)
    if size!=row['size_bytes'] or actual!=row['sha256']: raise ValueError('payload mismatch: '+row['path'])
    return row['path'],size,actual
try:
    save()
    expected=parse_config(config.read_text(encoding='utf-8-sig'))
    receipt['sdk_config_sha256']=digest(config)
    manifest_path=prefix/'.g4usim-install.json'; install_path=base/'out/collab/i2-windows114-data-install.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig')); installation=json.loads(install_path.read_text(encoding='utf-8-sig'))
    if manifest['status']!='published' or installation['status']!='published' or manifest['files']!=installation['files'] or manifest['artifacts']!=installation['artifacts']: raise ValueError('published install receipts disagree')
    receipt['published_receipts']=[{'path':str(p),'sha256':digest(p)} for p in (manifest_path,install_path)]
    receipt['datasets']=[{**item,'required':None,'present':(data/item['folder']).is_dir()} for i,item in enumerate(expected)]
    actual_folders={p.name for p in data.iterdir() if p.is_dir()}; expected_folders={x['folder'] for x in expected}
    if actual_folders!=expected_folders: raise ValueError('dataset folder/version set differs from verified SDK')
    receipt['canonical_folder_versions_match_sdk']=True
    receipt['steps'].append({'stage':'sdk_folder_versions','status':'passed','count':len(expected)})
    save(); print('SDK dataset folder/version match:',len(expected),flush=True)
    groups={name:[] for name in expected_folders}; other=[]
    for row in manifest['files']:
        parts=Path(row['path']).parts
        if len(parts)>1 and parts[0]=='data' and parts[1] in groups: groups[parts[1]].append(row)
        else: other.append(row)
    completed=0; total_bytes=0; summary=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for item in expected:
            rows=groups[item['folder']]
            if not rows: raise ValueError('dataset missing manifest payload: '+item['folder'])
            tree=hashlib.sha256(); count=0; size=0
            for relative,length,sha in pool.map(checked,sorted(rows,key=lambda x:x['path'])):
                tree.update((relative+'\0'+str(length)+'\0'+sha+'\n').encode('utf-8')); count+=1; size+=length
            summary.append({'folder':item['folder'],'version':item['version'],'file_count':count,'size_bytes':size,'manifest_payload_sha256_verified':True,'ordered_tree_sha256':tree.hexdigest()})
            completed+=count; total_bytes+=size
            receipt['verified_datasets']=summary; receipt['verified_files']=completed; receipt['verified_bytes']=total_bytes
            save(); print('VERIFIED',item['folder'],count,'files',size,'bytes',flush=True)
        for relative,length,sha in pool.map(checked,other): completed+=1; total_bytes+=length
    receipt['full_payload_verified']=True; receipt['verified_files']=completed; receipt['verified_bytes']=total_bytes
    expected_paths={Path(row['path']).as_posix() for row in manifest['files']}
    extras=[p.relative_to(prefix).as_posix() for p in prefix.rglob('*') if p.is_file() and p.relative_to(prefix).as_posix() not in expected_paths and p.name!='.g4usim-install.json']
    receipt['unregistered_files']=extras
    if extras: raise ValueError('unexpected files in published prefix')
    artifact=manifest['artifacts'][0]; artifact_path=Path(artifact['source']['path'])
    receipt['artifact']={'path':str(artifact_path),'expected_sha256':artifact['sha256'],'expected_size_bytes':artifact['size_bytes'],'available':artifact_path.is_file()}
    if artifact_path.is_file():
        observed=digest(artifact_path); receipt['artifact'].update(observed_sha256=observed,observed_size_bytes=artifact_path.stat().st_size)
        if observed!=artifact['sha256'] or artifact_path.stat().st_size!=artifact['size_bytes']: raise ValueError('published archive hash mismatch')
    receipt['steps'].append({'stage':'full_published_payload','status':'passed','files':completed,'size_bytes':total_bytes}); save()
    inherited=dict(os.environ); environment=dict(inherited)
    removed=sorted(key for key in environment if (key.startswith('G4') and key.endswith('DATA')) or key=='GEANT4_DATA_DIR')
    for key in removed: environment.pop(key,None)
    environment['GEANT4_DATA_DIR']=str(data)
    environment['PATH']=str(sdk/'bin')+os.pathsep+environment.get('PATH','')
    receipt['discovery_launch']={'executable':str(exe),'executable_sha256':digest(exe),'removed_keys':removed,'only_data_setting':{'GEANT4_DATA_DIR':str(data)},'path_prefix':str(sdk/'bin')}
    proc=subprocess.run([str(exe),'--check-geant4-data'],env=environment,cwd=base,capture_output=True,timeout=90)
    (out/'discovery.stdout.json').write_bytes(proc.stdout); (out/'discovery.stderr.log').write_bytes(proc.stderr)
    report=json.loads(proc.stdout.decode('utf-8-sig'))
    receipt['discovery_exit_code']=proc.returncode; receipt['discovery_geant4_version']=report.get('geant4_version'); receipt['discovery_required_complete']=report.get('required_complete')
    if proc.returncode or not report.get('required_complete') or 'geant4-11-04-patch-03' not in report.get('geant4_version',''): raise ValueError('clean-environment 11.4.3 discovery failed')
    observed={row['folder'] for row in report['datasets']}
    if observed!=expected_folders: raise ValueError('backend dataset folder table differs from 11.4.3 SDK metadata')
    receipt['discovery_folder_versions_match_sdk']=True
    backend_rows={row['folder']:row for row in report['datasets']}
    for item in receipt['datasets']: item['required']=backend_rows[item['folder']]['required']
    if not all(row['found'] and Path(row['path']).resolve()==(data/row['folder']).resolve() for row in report['datasets']): raise ValueError('discovery did not use the verified root for every dataset')
    receipt['required_flags_source']='actual backend discovery, not SDK declaration order'
    receipt['discovery_paths_all_under_verified_root']=True
    receipt['parent_environment_unchanged']=dict(os.environ)==inherited
    receipt['status']='passed'; receipt['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); save()
    print('PASSED',completed,'files;',len(expected),'datasets;',report['geant4_version'],flush=True)
except BaseException as exc:
    receipt['status']='failed'; receipt['error']={'type':type(exc).__name__,'message':str(exc)}; save(); raise
