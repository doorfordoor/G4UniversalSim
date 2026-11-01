from pathlib import Path
import json,sys,subprocess,os
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'resources-round'
r=json.loads((OUT/'results.json').read_text(encoding='utf-8'));work=Path(r['runtime_root']);env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'gui');env['QT_QPA_PLATFORM']='offscreen';results=[]
for c in r['cases']:
 if c['case'] not in ('portable-gps-and-both-field-maps','portable-single-phase-and-both-field-maps'):continue
 bundle=Path(c['detail']['moved_bundle']);name='gps' if 'gps' in c['case'] else 'phase'
 for action in ('generate','validate'):
  cmd=[sys.executable,str(bundle/'replay.py'),'--executable',sys.executable,'--runs-root',str(work/(name+'-cli-runs')),'--records',str(work/(name+'-cli-records')),'--timeout','30',action]
  p=subprocess.run(cmd,cwd=work,env=env,capture_output=True,timeout=45)
  (OUT/f'{name}-{action}.stdout.json').write_bytes(p.stdout);(OUT/f'{name}-{action}.stderr.log').write_bytes(p.stderr)
  d=json.loads(p.stdout);rec=d.get('record') or {};result={'case':name+'-'+action,'exit_code':p.returncode,'ok':d.get('ok'),'status':rec.get('status'),'reason':rec.get('reason'),'error':d.get('error')};results.append(result);print(json.dumps(result,ensure_ascii=False))
(OUT/'cli-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert all(x['exit_code']==0 and x['ok'] for x in results)
