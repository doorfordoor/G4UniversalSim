"""Strict offline collection; preserves failures and always runs independent review."""
from pathlib import Path
import hashlib,json,subprocess,sys

def main():
    ci=Path(__file__).resolve().parent;root=ci.parents[3]
    config=json.loads((ci/'watch-config.json').read_bytes());head=config['head']
    assert head!='8213ced419c8c6bca512bf8413b674c1265cf3bf'
    assert str(ci)==config['destination']
    frozen=Path(config['frozen'])
    assert hashlib.sha256(frozen.read_bytes()).hexdigest()==config['frozen_sha256']
    online=[]
    for label in ['linux','m0']:
        run=json.loads((ci/(label+'-run.json')).read_bytes());jobs=json.loads((ci/(label+'-jobs.json')).read_bytes())['jobs']
        assert run['head_sha']==head and run['event']=='push' and run['run_attempt']==1 and run['status']=='completed'
        assert len(jobs)==2 and all(j['run_id']==run['id'] and j['status']=='completed' for j in jobs)
        online.append(dict(label=label,run_id=run['id'],conclusion=run['conclusion'],jobs=[dict(id=j['id'],conclusion=j['conclusion']) for j in jobs]))
    helper=ci/'ci_helper.py'
    commands=[('prepare',[sys.executable,'-B',str(helper),'prepare','--head',head,'--artifact-root',str(ci),'--frozen',str(frozen),'--artifact-metadata',str(ci/'linux-artifacts.json'),'--artifact-metadata',str(ci/'m0-artifacts.json'),'--output',str(ci/'plan.json')]),('collect',[sys.executable,'-B',str(helper),'collect','--head',head,'--plan',str(ci/'plan.json'),'--destination',str(ci/'collection')]),('audit',[sys.executable,'-B',str(helper),'audit','--head',head,'--plan',str(ci/'plan.json'),'--collection',str(ci/'collection'),'--output',str(ci/'audit.json')])]
    receipts=[]
    for name,command in commands:
        log=ci/(name+'.log')
        print('Starting '+name,flush=True)
        with log.open('xb') as stream:result=subprocess.run(command,cwd=root,stdout=stream,stderr=subprocess.STDOUT)
        receipts.append(dict(operation=name,command=command,exit_code=result.returncode,log=str(log),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
        if name!='audit' and result.returncode:break
    log=ci/'independent-profiles.log'
    with log.open('xb') as stream:ind=subprocess.run([sys.executable,'-B',str(ci/'independent_profiles.py'),'independent-profiles.json'],cwd=root,stdout=stream,stderr=subprocess.STDOUT)
    independent=json.loads((ci/'independent-profiles.json').read_bytes()) if (ci/'independent-profiles.json').is_file() else {}
    passed=(all(r['conclusion']=='success' and all(j['conclusion']=='success' for j in r['jobs']) for r in online) and len(receipts)==3 and all(r['exit_code']==0 for r in receipts) and ind.returncode==0 and independent.get('checks_passed') is True and independent.get('report_count')==12 and independent.get('case_executions')==config['expected_case_executions'])
    result=dict(head=head,official_runs=online,operations=receipts,independent_exit_code=ind.returncode,independent_semantic_pass=independent.get('checks_passed',False),checks_passed=passed,no_allow_incomplete=True,stage_acceptance=config['stage_acceptance'],CI_pass_does_not_close_stage=True)
    with (ci/'pipeline-result.json').open('xb') as stream:stream.write((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0 if passed else 1

if __name__=='__main__':sys.exit(main())
