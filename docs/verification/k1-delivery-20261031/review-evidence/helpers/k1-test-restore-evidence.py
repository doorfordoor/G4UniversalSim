"""Ordinary and optimized-mode regression for evidence transport identity."""
from pathlib import Path
import copy, hashlib, json, os, subprocess, sys
root = Path(__file__).resolve().parent
dest = root / 'k1-restore-regression-v2'
dest.mkdir(exist_ok=False)
helper = root / 'k1-delivery-packaged/restore_evidence.py'
payload = b'K1 deterministic transport regression\n'
digest = hashlib.sha256(payload).hexdigest()
base = {'schema':'k1_evidence_transport_parts_v1','archive_name':'evidence.zip',
        'archive_bytes':len(payload),'archive_sha256':digest,
        'parts':[{'file':'part-1','bytes':len(payload),'sha256':digest}]}
results=[]
for mode in ('ordinary', 'optimized', 'env-optimized'):
    for case in ('valid','part-hash','whole-hash','schema','existing'):
        work=dest / (mode+'-'+case);work.mkdir()
        (work/'part-1').write_bytes(payload)
        doc=copy.deepcopy(base)
        if case=='part-hash': doc['parts'][0]['sha256']='0'*64
        if case=='whole-hash': doc['archive_sha256']='0'*64
        if case=='schema': doc['schema']='invalid'
        out=work/'output'
        if case=='existing':
            out.mkdir();(out/'evidence.zip').write_bytes(b'keep original')
        manifest=work/'transport.json';manifest.write_text(json.dumps(doc),encoding='utf-8')
        env=os.environ.copy();env.pop('PYTHONOPTIMIZE',None)
        if mode=='env-optimized':env['PYTHONOPTIMIZE']='1'
        argv=[sys.executable]+(['-O'] if mode=='optimized' else [])+[str(helper),str(manifest),'--output-directory',str(out)]
        run=subprocess.run(argv,capture_output=True,env=env)
        (work/'stdout.log').write_bytes(run.stdout);(work/'stderr.log').write_bytes(run.stderr)
        target=out/'evidence.zip'
        if case=='valid':
            assert run.returncode==0 and target.read_bytes()==payload
            assert json.loads(run.stdout)['sha256']==digest
        else:
            assert run.returncode!=0 and not run.stdout
            if case in ('part-hash','schema'):assert not target.exists()
            if case=='existing':assert target.read_bytes()==b'keep original'
            if case=='whole-hash':assert b'output is unverified' in run.stderr
        results.append({'mode':mode,'case':case,'exit_code':run.returncode,'expected':True})
report={'schema':'k1_restore_regression_v2','helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'results':results,'cases':len(results),'all_expected':True,'whole_mismatch_output':'retained, explicitly unverified; existence is not success'}
(dest/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'cases':len(results),'all_expected':True,'report':str(dest/'report.json')}))
