from pathlib import Path
import csv,json,statistics,math,hashlib
from scipy.stats import t
ROOT=Path('D:/Geant4/G4UniversalSim/out/collab/q2-biasing-repair-r2')
OUT=Path(__file__).resolve().parent
result={'scope':'independent all-event/dose/statistics/worker/identity and Welch recomputation; full hit reaccumulation belongs to separately reviewed comparator','batches':[],'checks':0}
def check(ok,why):
 result['checks']+=1
 assert ok,why
def near(a,b):return math.isclose(a,b,rel_tol=3e-9,abs_tol=1e-26)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
plan=json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
check(sha(Path('D:/Geant4/G4UniversalSim')/plan['backend']['path'])==plan['backend']['sha256'],'backend hash')
for v in plan['inputs'].values():check(sha(Path('D:/Geant4/G4UniversalSim')/v['path'])==v['sha256'],'input hash')
g={'analog':[],'biased':[]};times={'analog':[],'biased':[]};seeds=[]
for output in sorted((ROOT/'runs').glob('*/output')):
 summary=dict(line.split(' = ',1) for line in (output/'run_summary.txt').read_text(encoding='utf-8').splitlines() if ' = ' in line)
 seed=int(summary['seed']);seeds.append(seed);group='analog' if seed%2 else 'biased'
 check(summary['status']=='completed' and summary['output_failure_status']=='none','status '+str(seed))
 check(int(summary['actual_completed_event_count'])==2000 and int(summary['actual_threads'])==2,'events threads')
 if group=='biased':
  check(summary['biasing_worker_validation_status']=='validated' and summary['biasing_worker_coverage_complete']=='true' and summary['biasing_worker_evidence_count']=='2','worker receipts')
 er=[x for f in output.glob('event_edep_t*.csv') for x in rows(f)]
 check(len(er)==2000 and sorted(int(x['eventID']) for x in er)==list(range(2000)),'unique all events')
 check(all(x['runID']=='0' for x in er),'run identity')
 values=[float(x['weighted_edep_MeV'])*1.602176634e-13/.01135 for x in er]
 check(all(math.isfinite(v) and v>=0 for v in values),'finite event values')
 total=math.fsum(values);sumsq=math.fsum(v*v for v in values);mean=total/2000
 dose=[x for f in output.glob('dose_volume_summary_t*.csv') for x in rows(f)]
 check(len(dose)==2 and all(near(float(x['mass_kg']),.01135) for x in dose),'mass')
 check(near(sum(float(x['weighted_dose_Gy']) for x in dose),total),'dose reconstruction')
 stats=[x for x in rows(output/'scorer_statistics.csv') if x['quantity']=='weighted_dose']
 check(len(stats)==1,'weighted dose row');st=stats[0]
 for key,expected in [('sum',total),('sum_sq',sumsq),('mean_per_event',mean)]:check(near(float(st[key]),expected),'stats '+key)
 rel=math.sqrt(sumsq/(total*total)-1/2000)
 check(near(float(st['rel_error']),rel),'uncorrected event moment statistic')
 wall=float(st['run_wall_time_s']);check(wall>0 and near(float(st['fom_per_s']),1/(rel*rel*wall)),'scorer fom')
 g[group].append(mean);times[group].append(wall)
 result['batches'].append({'seed':seed,'group':group,'mean':mean,'wall':wall,'events':len(er),'event_sha256':{f.name:sha(f) for f in output.glob('event_edep_t*.csv')}})
check(sorted(seeds)==list(range(20261101,20261133)),'fixed seeds all32 exactly')
check(len(g['analog'])==len(g['biased'])==16,'groups16 each')
a,b=[statistics.mean(x) for x in g.values()];va,vb=[statistics.variance(x)/16 for x in g.values()];df=(va+vb)**2/(va*va/15+vb*vb/15);margin=float(t.ppf(.995,df))*math.sqrt(va+vb);ci=[b-a-margin,b-a+margin]
result.update(analog_mean=a,biased_mean=b,ratio=b/a,ci99=ci,df=df,relative_half_width=margin/a,compatible=ci[0]<=0<=ci[1],precision_pass=margin/a<=.05,scorer_wall_total={k:sum(v) for k,v in times.items()},group_efficiency={k:statistics.mean(g[k])**2/(statistics.variance(g[k])/16*sum(times[k])) for k in g})
result['efficiency_ratio']=result['group_efficiency']['biased']/result['group_efficiency']['analog']
(OUT/'independent.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='batches'},indent=2))
