"""Verify exact public inventory and explicitly limited native evidence; no GUI."""
from pathlib import Path
import hashlib,json,zipfile
D=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def main():
 w=read(D/'windows-native-review/review.json');l=read(D/'linux-native-review/review.json')
 assert w['head']==l['head']=='246e4f6f1b97cc5e0651ff01262c85cf2e9c28d3'
 assert not w['confirmed_P0'] and not w['confirmed_P1'] and not w['confirmed_P2']
 assert not l['confirmed_P0'] and not l['confirmed_P1'] and not l['confirmed_P2']
 assert l['HTTP_requests']==l['request_attempts']==l['task_count']==1
 assert l['actual_execution_events']==0 and l['K1_actions']==[] and l['plan_operation_status']=='passed'
 assert l['task_terminal_state']=='failed' and l['task_failure_reason']=='agent.task_timeout'
 assert l['host_exit']==0 and l['slot_released'] and not l['remaining_host_owned'] and not l['remaining_display_owned']
 assert l['display_server_exits']==[0,1,0] and not l['HTTP_worker_alive'] and l['HTTP_listener_closed']
 counts={}
 for folder,n in [('windows-native-review',122),('linux-native-review',16)]:
  a=read(D/folder/'native-assets-metadata.json');assert len(a)==n
  assert all(set(x)=={'scope','path','size_bytes','sha256','mime'} and x['scope'] in ({'private_local_only'} if folder=='windows-native-review' else {'private_local_only_xvnc','private_local_only_historical_WSLg'}) for x in a)
  s=read(D/folder/'source-metadata.json');assert all(set(x)=={'scope','path','size_bytes','sha256','mime'} for x in s)
  v=read(D/folder/'verification.json');assert v['status']=='PASS'
  for row in v['generated_files']:
   p=D/folder/Path(row['path']).name;assert sha(p)==row['sha256'] and p.stat().st_size==row['size_bytes']
  counts[folder]=len(a)
 install=read(D/'linux-dependencies/system-xkbcomp-receipt.json');isolated=read(D/'linux-dependencies/isolated-xcb-receipt.json')
 assert install['package']=='x11-xkb-utils' and install['actual_dpkg_install_exit_code']==0
 assert install['other_Xvnc_twm_packages_system_installed'] is False and isolated['system_installed'] is False
 for row in read(D/'linux-dependencies/manifest.json')['files']:
  p=D/'linux-dependencies'/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes']
 forbidden={'.png','.jpg','.jpeg','.gif','.webp','.bmp','.tiff','.ico','.exe','.dll','.pyd','.deb','.obj','.lib','.pdb','.pyc'}
 for p in D.rglob('*'):
  if p.is_file():assert p.suffix.lower() not in forbidden,str(p)
 with zipfile.ZipFile(D/'nonvisual-evidence.zip') as z:
  assert len(z.namelist())==1284
  assert all(Path(n).suffix.lower() not in forbidden for n in z.namelist())
  manifest=read(D/'manifest.json');source='out/verification/l1-246e4f6/ci-attempt2-windows-install/aggregate-terminal.json'
  name=next(x['archive_path'] for x in manifest['entries'] if x['source']==source);aggregate=json.loads(z.read(name))
  assert aggregate['status']=='passed_with_explicit_retry' and aggregate['effective_job_count']==8
 if (D/'public-files.manifest.json').exists():
  inv=read(D/'public-files.manifest.json');expected={r['path']:r for r in inv['files']};prefix='docs/verification/l1-final-20261102/'
  actual={prefix+p.relative_to(D).as_posix():p for p in D.rglob('*') if p.is_file() and p.name!='public-files.manifest.json'}
  assert set(actual)==set(expected),(set(actual)-set(expected),set(expected)-set(actual))
  for name,p in actual.items():assert sha(p)==expected[name]['sha256'] and p.stat().st_size==expected[name]['bytes'],name
 print('Scope verified: Windows122/Linux16 metadata-only assets; Linux plan passed/task timeout; [0,1,0] retained; Ubuntu xkb install; raw image/UIA payload0')
 return {'status':'PASS_LIMITED_SCOPE_AND_PUBLIC_BYTES','assets':counts,'raw_image_UIA_payloads':0,'Linux_whole_task_failed_retained':True,'display_exits':[0,1,0],'Ubuntu_system_install':'x11-xkb-utils only','WSLg_RAIL_success_claim':False}
if __name__=='__main__':main()
