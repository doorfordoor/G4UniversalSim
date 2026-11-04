from pathlib import Path
import sys,json,traceback
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
import test_session_replay as m
base=Path(__file__).resolve().parent;exe=ROOT/'out/collab/f2-independent-build/Release/G4UniversalSim.exe'
original=m.set_energy;count=0
def omit_first(session,text):
 global count
 count+=1
 if count>1:original(session,text)
m.set_energy=omit_first
try:
 s=m.run_source_session(exe,base,'source',threads=1,rounds=[('100 MeV',100),('200 MeV',200)],events=5)
 r=m.replay_session(exe,base,'replay',s['session_dir'],threads=1)
 cases=[]
 for pattern,keys in [('event_edep_t*.csv',('runID','eventID')),('hits_t*.csv',('runID','eventID','trackID'))]:
  a=m.collect_table(s['output'],pattern,keys);b=m.collect_table(r['output'],pattern,keys)
  try:m.compare_tables(a,b,pattern);equal=True;error=''
  except AssertionError as e:equal=False;error=str(e)
  cases.append({'pattern':pattern,'equal':equal,'error':error})
 result={'source_steps':s['manifest']['steps'],'replay_exit':r['exit_code'],'cases':cases}
 (base/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(cases),flush=True); assert all(c['equal'] for c in cases), cases
except Exception:
 traceback.print_exc();raise
