"""Read-only visible-host identity audit. Never starts Qt or supplies visual approval."""
import argparse,json,hashlib,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
BUILD='f176d0ed4cea60b7ca5a80ed81017c9404ec1257'
DOC='ede037f26db63f606e3ca086d5d586f222f428df'
SOURCE='db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc'
TEST='57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35'
EXE='f02d3bdc94121dcf35de05e152773fdec8c87f5c8759e53fd1f95d3f51f43ea8'
def main():
 p=argparse.ArgumentParser();p.add_argument('--state',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert a.output.resolve().parent==Path(__file__).resolve().parent and a.output.name.startswith('f1-visible-final-audit-')
 sys.path.insert(0,str(ROOT/'scripts'));import run_m0_tests as runner
 changes=subprocess.check_output(['git','diff','--name-only','-z',BUILD,DOC],cwd=ROOT).decode().split('\0');changes=[s for s in changes if s]
 assert all(s.startswith('docs/') or s in ('AGENTS.md','README.md','ROADMAP.md','STATUS.md','CHANGELOG.md') for s in changes)
 current={'head':runner.git_value('rev-parse','HEAD'),'source':runner.workspace_source_fingerprint(),'tests':runner.tests_content_fingerprint()}
 assert current=={'head':DOC,'source':SOURCE,'tests':TEST}
 assert hashlib.sha256((ROOT/'out/build-f1/Release/G4UniversalSim.exe').read_bytes()).hexdigest()==EXE
 receipt={'status':'prepared_pending_observation','current':current,'product_build_commit':BUILD,'exe_sha256':EXE,'documentation_only_changed_paths':len(changes),'visual_acceptance':'pending_root_observations','close_acceptance':'pending_root_native_close_and_process_exit','archive_policy':'Old automated archive remains byte unchanged and pending. New visible archive must be separate.','state':None}
 if a.state:
  raw=a.state.read_bytes();s=json.loads(raw);assert s['ready'] is True
  for key in ('identity_before_import','identity_at_load'):
   i=s[key];assert i['git_head']==DOC and i['source_fingerprint']==SOURCE and i['tests_content_fingerprint']==TEST
  expected=s['expected_identity'];assert expected['git_head']==DOC and expected['source_fingerprint']==SOURCE and expected['tests_content_fingerprint']==TEST
  reals=s['real_output_records'];assert reals
  for r in reals:
   assert r['identity_status']=='verified' and r['source_matches_loaded_code'] is True
   assert r['recorded_build']['git_commit']==BUILD and r['recorded_build']['source_fingerprint']==SOURCE
   assert r['build_commit_matches_expected_head'] is False
   assert r['output_format_requested']=='auto' and r['output_format_actual']=='root' and r['explicit_auto_recorded'] is True
  closed=s.get('closed') is True
  if closed:
   i=s['identity_at_exit'];assert i['git_head']==DOC and i['source_fingerprint']==SOURCE and i['tests_content_fingerprint']==TEST
  receipt.update(status='host_identity_checked_visual_pending',state={'path':str(a.state.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'closed':closed,'real_records':reals,'commit_mismatch_explanation':'Expected false: host docs HEAD ede037f differs from unchanged tested product build f176d0e; source/tests match. Do not rewrite boolean.'})
 raw=(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode()
 with a.output.open('xb') as f:f.write(raw)
 assert a.output.read_bytes()==raw
 print(json.dumps({'status':receipt['status'],'output':str(a.output.resolve()),'visual_acceptance':receipt['visual_acceptance']}))
if __name__=='__main__':main()
