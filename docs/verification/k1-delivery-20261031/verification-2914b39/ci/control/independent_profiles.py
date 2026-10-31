from pathlib import Path
import collections,copy,hashlib,importlib.util,json,sys
BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('third_ci_helper',BASE/'ci_helper.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
gate,gate_identity=h.gate_module()
frozen=h.load(BASE.parent/'frozen-case-manifest.json');baseline=h.load(h.F5/'ci-evidence.json')
index={(r['artifact'],r['profile']):r for r in baseline['reports']}
reports=[];missing=[]
for name,matrix in h.DEFAULT_MATRIX.items():
    artifact=BASE/name
    paths=list(artifact.rglob('report.json')) if artifact.exists() else []
    present=set()
    for path in sorted(paths):
        raw=path.read_bytes();r=h.decode(raw);profile=r['profile'];present.add(profile)
        normalized=copy.deepcopy(r);raw_errors=[];logs=[]
        for row,nrow in zip(r['results'],normalized['results']):
            try:
                log=h.local_log(row,path);payload=h.read(log);h.raw_log_check(payload,row);nrow['log']=log.name
                logs.append({'case':row['name'],'sha256':h.sha(payload),'assertions':row['assertions_executed'],'path':str(log)})
            except Exception as exc:raw_errors.append({'case':row.get('name'),'error':str(exc)})
        identity_errors=[]
        if r.get('git_head')!=frozen['head_sha']:identity_errors.append('head mismatch')
        for key in ['source_fingerprint','tests_content_fingerprint']:
            if r.get(key)!=frozen[key]:identity_errors.append(key+' mismatch')
        if [x['name'] for x in r['results']]!=frozen['profiles'].get(profile):identity_errors.append('frozen case names/order mismatch')
        if not r.get('platform','').startswith(matrix['platform']+'-'):identity_errors.append('OS mismatch')
        total=sum(x['assertions_executed'] for x in r['results'])
        if total!=r.get('assertions_executed_total'):identity_errors.append('assertion sum mismatch')
        if r.get('cases_with_assertion_counts')!=len(r['results']):identity_errors.append('assertion-count records mismatch')
        zero=sorted(x['name'] for x in r['results'] if x['assertions_executed']==0)
        if sorted(r.get('cases_with_zero_assertions',[]))!=zero:identity_errors.append('zero-assertion declaration mismatch')
        if r.get('log_digest_algorithm')!='sha256_raw_bytes_lf_v2':identity_errors.append('non-current digest algorithm')
        if r.get('skip_policy')!='failure':identity_errors.append('non-strict skip policy')
        if r.get('tracked_source_gate')!='pass' or r.get('untracked_source_files')!=[]:identity_errors.append('tracked source gate failed')
        if type(r.get('git_dirty')) is not bool or r['git_dirty']!=bool(r.get('git_status_porcelain')):identity_errors.append('git status inconsistency')
        if profile in ('backend','integration') and r.get('backend_build_identity',{}).get('geant4_version_number')!=matrix['geant4_version_number']:identity_errors.append('Geant4 version mismatch')
        try:gate.validate_report(normalized,report_path=path);strict='passed'
        except Exception as exc:strict=str(exc)
        br=index[(matrix.get('baseline_artifact',name),profile)];bp=h.F5/br['path']
        base,bnorm,blogs,bsha=h.checked_report(bp,gate)
        assert bsha==br['sha256']
        before={x['name']:x['assertions_executed'] for x in base['results']};after={x['name']:x['assertions_executed'] for x in r['results']}
        regressions=[{'case':k,'baseline':v,'actual':after.get(k)} for k,v in before.items() if k not in after or after[k]<v]
        if r['assertions_executed_total']<base['assertions_executed_total']:regressions.append({'case':'PROFILE_TOTAL','baseline':base['assertions_executed_total'],'actual':r['assertions_executed_total']})
        try:h.compare_baseline(normalized,bnorm,gate,path);baseline_gate='passed'
        except Exception as exc:baseline_gate=str(exc)
        counts=collections.Counter(x['status'] for x in r['results'])
        bad=[{k:x.get(k) for k in ['name','status','exit_code','assertions_executed','log']} for x in r['results'] if x['status']!='pass']
        reports.append({'artifact':name,'profile':profile,'path':str(path),'report_sha256':h.sha(raw),'cases':len(r['results']),'assertions':r['assertions_executed_total'],'counts':dict(counts),'strict_gate':strict,'raw_log_errors':raw_errors,'identity_errors':identity_errors,'baseline_strict_gate':baseline_gate,'baseline_report_sha256':bsha,'baseline_cases':len(base['results']),'baseline_assertions':base['assertions_executed_total'],'assertion_regressions':regressions,'failures':bad,'git_dirty':r.get('git_dirty'),'git_status_porcelain':r.get('git_status_porcelain'),'logs':logs})
    missing.extend({'artifact':name,'profile':p} for p in matrix['profiles'] if p not in present)
result={'scope':'all present official profiles; missing profiles explicitly fail coverage','head':frozen['head_sha'],'expected_reports':12,'expected_unique_cases':sum(len(v) for v in frozen['profiles'].values()),'report_count':len(reports),'case_executions':sum(r['cases'] for r in reports),'missing_profiles':missing,'gate_identity':gate_identity,'checks_passed':not missing and all(r['strict_gate']=='passed' and r['baseline_strict_gate']=='passed' and not r['identity_errors'] and not r['raw_log_errors'] and not r['assertion_regressions'] for r in reports),'k1_ci_verified':False,'reports':reports}
output=BASE/sys.argv[1];assert not output.exists();output.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({k:v for k,v in result.items() if k!='reports'},ensure_ascii=False))
for r in reports:print(json.dumps({k:r[k] for k in ['artifact','profile','cases','counts','strict_gate','baseline_strict_gate','raw_log_errors','identity_errors','assertion_regressions']},ensure_ascii=False))
