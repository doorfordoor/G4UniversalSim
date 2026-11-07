from pathlib import Path
import json,sys,statistics,math
sys.stdout.reconfigure(encoding='utf-8')
r=Path('D:/Geant4/G4UniversalSim');base=Path(json.loads((r/'out/collab/f3-preflight-independent/r2/active-baseline.json').read_text(encoding='utf-8'))['root']);timing=json.loads((base/'timing/report.json').read_bytes());memory=json.loads((base/'memory/report.json').read_bytes());rows=[]
for workload in ['hits','mesh']:
 for fmt in ['csv','root']:
  a=[x for x in timing['samples'] if x['workload']==workload and x['format']==fmt];assert len(a)==5 and sorted(x['repeat'] for x in a)==list(range(5));times=[x['total_elapsed_s'] for x in a];med=statistics.median(times);mad=statistics.median(abs(x-med) for x in times)/med;mem=[x for x in memory['memory_samples'] if x['workload']==workload and x['format']==fmt];assert len(mem)==3;rss=[max(x['memory']['peak_working_set_bytes'],x['memory']['os_peak_working_set_bytes']) for x in mem];rows.append({'combo':workload+'/'+fmt,'elapsed_median_s':med,'run_wall_median_s':statistics.median(x['run_wall']['max'] for x in a),'relative_MAD':mad,'noise_pass':mad<=.05,'sampled_rss_median_bytes':statistics.median(rss),'registered_bytes_median':statistics.median(x['registered_bytes'] for x in a),'timing_values':times})
(base/'resource-independent.json').write_text(json.dumps({'status':'pass' if all(x['noise_pass'] for x in rows) else 'inconclusive','rows':rows,'scope':'resource observation only,science pending'},indent=2),encoding='utf-8');print(json.dumps(rows,indent=2))
