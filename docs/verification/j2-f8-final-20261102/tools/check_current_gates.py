"""Run only archived evidence checker: current6Windows+12CI and one historical failure control."""
import argparse,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent.parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve();assert out.is_relative_to(ROOT.parent.resolve()) and not out.is_relative_to(ROOT.resolve());assert not out.exists(),'refuse overwrite evidence output'
 p=ROOT/'current-gates.plan.json';plan=json.loads(p.read_text());assert plan['ready_for_final_current18'] and len(plan['current'])==18
 assert sum(x['group']=='Windows' for x in plan['current'])==6 and sum(x['group']=='CI' for x in plan['current'])==12
 m=json.loads((ROOT/'manifest.json').read_text());paths={(ROOT/x['public_path']).resolve():x for x in m['entries']};checker=ROOT/'tree/scripts/check_report_evidence.py';assert sha(checker)==plan['checker_sha256'];sp=importlib.util.spec_from_file_location('_frozen_report_gate',checker);ck=importlib.util.module_from_spec(sp);sp.loader.exec_module(ck)
 out.mkdir();runs=[]
 for item in plan['current']+[plan['historical_failure_control']]:
  report=(ROOT/item['report_path']).resolve();baseline=(ROOT/item['baseline_path']).resolve();assert report.is_relative_to(ROOT) and baseline.is_relative_to(ROOT);assert sha(report)==item['report_sha256'] and sha(baseline)==item['baseline_sha256']
  data=json.loads(report.read_text(encoding='utf-8-sig'))
  for q in [report,baseline]:
   for row in json.loads(q.read_text(encoding='utf-8-sig'))['results']:
    lp=ck.resolve_log(row,q);assert lp and lp.resolve().is_relative_to(ROOT),('old absolute fallback forbidden',item['id'],row['name']);assert lp.resolve() in paths and paths[lp.resolve()]['sha256']==row['log_sha256']
  if item['expected_exit']==0:
   exact=item['identity_exact']
   for field,value in exact.items():assert data.get(field)==value,('original identity field mismatch',item['id'],field)
   assert exact['git_head']==plan['tested_build_HEAD'] and exact['tracked_source_gate']=='pass' and exact['untracked_source_files']==[]
   if exact['git_dirty']:
    assert item['group']=='CI' and item['id'].startswith('CI-linux-evidence-11.')
    version='11.4.3' if '11.4.3' in item['id'] else '11.3.2'
    assert exact['git_status_porcelain'].replace('\\n','\n').splitlines()==['?? .g4env-'+version+'/','?? .micromamba/','?? bin/']
   else:assert exact['git_status_porcelain']==''
  cmd=[sys.executable,'-B',str(checker),'--report',str(report),'--baseline',str(baseline)];r=subprocess.run(cmd,cwd=ROOT,capture_output=True);log=out/(item['id']+'.log');log.write_bytes(r.stdout+r.stderr)
  runs.append({'id':item['id'],'group':item['group'],'command':cmd,'report_path':item['report_path'],'report_sha256':item['report_sha256'],'baseline_path':item['baseline_path'],'baseline_sha256':item['baseline_sha256'],'expected_exit':item['expected_exit'],'actual_exit':r.returncode,'log_sha256':sha(log),'log_file':log.name})
  (out/'progress.json').write_bytes((json.dumps({'runs':runs},ensure_ascii=False,indent=2)+'\n').encode())
  if r.returncode!=item['expected_exit']:
   (out/'first-failure.json').write_bytes((json.dumps(runs[-1],ensure_ascii=False,indent=2)+'\n').encode());raise AssertionError(('archived gate unexpected exit; first failure retained',item['id'],r.returncode))
 receipt={'schema':'j2_f8_current18_archived_strict_gates_v1','status':'current18_strict_pass_and_historical_failure_preserved','tested_build_HEAD':plan['tested_build_HEAD'],'current_windows':6,'current_CI':12,'current_expected0_actual0':18,'historical_representative_expected1_actual1':1,'all_historical_expected1_plan_count':len(plan['historical_failures']),'runs':runs,'checker_sha256':plan['checker_sha256'],'plan_sha256':sha(p),'all_report_log_bindings_inside_this_relocated_archive':True,'no_allow_incomplete_or_legacy_flags':True,'formal_product_CI_or_native_execution':False,'old39_22_17_full_sequence_reexecuted':False,'documentation_commit':'containing Git tree plus main three-lock mapping; never retag reports','identity_scope':'6Windows/4M0 exactclean;8Linux exactoriginal3untracked environment lines and fingerprints/trackedsource verified'}
 (out/'receipt.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in receipt.items() if k!='runs'},ensure_ascii=False))
if __name__=='__main__':main()
