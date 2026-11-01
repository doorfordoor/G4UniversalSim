from pathlib import Path
import os,sys,json,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
work=OUT/'runtime'; env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'gui');env['QT_QPA_PLATFORM']='offscreen'
results=[]
for label,bundle in [('valid',work/'moved-bundle'),('invalid',work/'dirty-export'/'bundle')]:
    for command in ['generate','validate']:
        cmd=[sys.executable,str(bundle/'replay.py'),'--executable',sys.executable,'--runs-root',str(work/(label+'-replay-runs')),'--records',str(work/(label+'-records')),'--timeout','30',command]
        p=subprocess.run(cmd,cwd=work/'elsewhere',env=env,capture_output=True,timeout=45)
        (OUT/f'{label}-{command}.stdout.json').write_bytes(p.stdout)
        (OUT/f'{label}-{command}.stderr.log').write_bytes(p.stderr)
        try: data=json.loads(p.stdout)
        except Exception:data={}
        r={'case':label+'-'+command,'exit_code':p.returncode,'ok':data.get('ok'),'error':data.get('error'),'status':(data.get('record') or {}).get('status'),'reason':(data.get('record') or {}).get('reason'),'diagnostics':(data.get('record') or {}).get('diagnostics')}
        results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
(OUT/'replay-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
