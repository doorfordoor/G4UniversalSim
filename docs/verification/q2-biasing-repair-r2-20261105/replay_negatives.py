import sys,json,hashlib
from pathlib import Path
r=Path('D:/Geant4/G4UniversalSim/out/collab/q2-biasing-repair-r2');sys.path.insert(0,str(r));import compare
results=json.loads((r/'results.json').read_text(encoding='utf-8'));recs={x['batch']:x for x in results['runs']};tamper=json.loads((r/'tamper-results.json').read_text(encoding='utf-8'));baseline=json.loads((r/'evaluation.json').read_text(encoding='utf-8'));got=[]
for item in tamper['cases']:
 if item['id']=='CE-DROP-BATCH':
  altered=dict(results);altered['runs']=results['runs'][:-1]
  q=compare.evaluation(json.loads((r/'identity.json').read_text(encoding='utf-8')),json.loads((r/'seed-order.json').read_text(encoding='utf-8')),altered,batch_cache={b['batch']:b for b in baseline['batches']});checks=q['checks']
 else:
  batch=item['batches_recomputed'][0];checks=[];compare.compute_batch(recs[batch],checks,r/'tampered'/item['id']/'runs')
 target=[x for x in checks if x['id']==item['target']];assert len(target)==1 and not target[0]['ok'],item['id']
 assert next(x for x in baseline['checks'] if x['id']==item['target'])['ok']
 got.append({'case':item['id'],'target':item['target'],'detected':True});print(item['id'],'detected',flush=True)
(Path(__file__).parent/'independent-negatives.json').write_text(json.dumps({'cases':got,'detected':len(got),'scope':'six mutated batches recomputed directly with delivered comparator; missing-batch gate re-evaluated with verified baseline batch results; no transport rerun'},indent=2),encoding='utf-8')
