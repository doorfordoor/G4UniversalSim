from pathlib import Path
import sys,json,shutil,os
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
import test_session_replay as m
base=Path(__file__).resolve().parent;exe=ROOT/'out/collab/f2-independent-build/Release/G4UniversalSim.exe'
cases=[];sessions=[]
try:
 source=m.run_source_session(exe,base,'mt-aba',threads=2,rounds=[('100 MeV',100),('200 MeV',200),('100 MeV',100)],events=5)
 sessions.append(source)
 replay=m.replay_session(exe,base,'mt-aba-replay',source['session_dir'],threads=2);sessions.append(replay)
 for pattern,keys in [('event_edep_t*.csv',('runID','eventID')),('hits_t*.csv',('runID','eventID','trackID'))]:
  a=m.collect_table(source['output'],pattern,keys);b=m.collect_table(replay['output'],pattern,keys);m.compare_tables(a,b,pattern)
 cases.append({'case':'independent_MT_ABA','passed':replay['exit_code']==0,'rounds':3,'events_each':5})
 for name,op,field,value in [('first-cancel','run','status','cancelled'),('last-cancel','run','status','cancelled'),('last-energy','set_source','value','banana MeV')]:
  bad=base/name;shutil.copytree(source['session_dir'],bad)
  f=bad/'replay-manifest.json';mft=json.loads(f.read_text());selected=[x for x in mft['steps'] if x['op']==op];step=selected[0 if name=='first-cancel' else -1]
  if field=='value':step['params'][field]=value
  else:step[field]=value
  f.write_text(json.dumps(mft),encoding='utf-8')
  process=m.start_replay(exe,base,name+'-replay',bad,threads=2);sessions.append({'session':process})
  rc=process.process.wait(timeout=90);process.thread.join(3)
  runs=[x for x in process.frames if x.get('event')=='run_started']
  cases.append({'case':name,'exit_code':rc,'run_started_count':len(runs),'passed':rc!=0 and not runs})

finally:
 for idx,s in enumerate(sessions):
  session=s.get('session')
  if session: (base/f'process-{idx}.log').write_text('\n'.join(session.raw_lines)+'\n',encoding='utf-8')
 (base/'report.json').write_text(json.dumps({'candidate':__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'cases':cases},indent=2)+'\n',encoding='utf-8')
 print(json.dumps(cases),flush=True)
