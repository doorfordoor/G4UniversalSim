"""Offline tool self-check using immutable historical bytes, not candidate CI."""
import copy, json, tempfile, zipfile
from pathlib import Path
import ci_review as c

def rejects(call):
    try:call()
    except AssertionError:return
    raise AssertionError('Expected refusal did not occur')

def main():
    record=c.baseline('linux113-static')
    with tempfile.TemporaryDirectory(prefix='offline-selftest-',dir=c.BASE) as temp:
        root=Path(temp)
        p=c.materialize_baseline(record,root/'baseline')
        raw=c.read(p);projected=c.local_projection(p,raw);gate=c.checker()
        gate.validate_report(projected,report_path=p)
        assert c.sha(p)==record['report_sha256']
        # Strict same-probe comparison and raw sibling-log hashing execute.
        gate.validate_report(projected,report_path=p,baseline=raw)
        bad=copy.deepcopy(projected);bad['assertions_executed_total']+=1
        rejects(lambda:gate.validate_report(bad,report_path=p))
        bad_baseline=copy.deepcopy(raw);bad_baseline['results'][0]['assertions_executed']+=1
        rejects(lambda:gate.validate_report(projected,report_path=p,baseline=bad_baseline))
        bad_baseline=copy.deepcopy(raw);bad_baseline['results'].append(dict(raw['results'][0],name='missing_old_case'))
        rejects(lambda:gate.validate_report(projected,report_path=p,baseline=bad_baseline))
        rejects(lambda:c.gate_report(p,'windows113',raw['git_head'],raw['source_fingerprint'],raw['tests_content_fingerprint'],root/'wrong-platform'))
        rejects(lambda:c.gate_report(p,'linux113','0'*40,raw['source_fingerprint'],raw['tests_content_fingerprint'],root/'wrong-head'))
        result=c.gate_report(p,'linux113',raw['git_head'],raw['source_fingerprint'],raw['tests_content_fingerprint'],root/'same-history-gate')
        assert result['status']=='strict_pass' and not result['new_cases']
        # Hash tampering must fail, with no fallback to original checkout logs.
        log=Path(projected['results'][0]['log']);before=log.read_bytes();log.write_bytes(before+b'tampered\n')
        rejects(lambda:gate.validate_report(projected,report_path=p))
        log.write_bytes(before)
        oldlog=raw['results'][0]['log'];raw['results'][0]['log']='/missing/original/'+log.name
        log.unlink()
        rejects(lambda:c.local_projection(p,raw))
        good=root/'good.zip'
        with zipfile.ZipFile(good,'w') as z:z.writestr('reports/file.json','{}')
        c.extract_zip(good,root/'extracted')
        assert (root/'extracted/reports/file.json').read_text()=='{}'
        unsafe=root/'bad.zip'
        with zipfile.ZipFile(unsafe,'w') as z:z.writestr('../escape.txt','bad')
        rejects(lambda:c.extract_zip(unsafe,root/'rejected'))
    out=c.BASE/'self-test.json'
    c.save(out,dict(status='offline_tool_selftest_passed',remote_requests=0,
                   historical_report=record['id'],historical_report_sha256=record['report_sha256'],
                   current_candidate_results=False,
                   checks=['archive selected report/log byte hashes','historical strict gate','same-v3 per-case baseline comparison',
                           'total/per-case/missing-case negative controls','wrong head/platform refusal','raw log tampering refusal',
                           'no original-path fallback','safe extraction and traversal refusal']))
    print(json.dumps(c.read(out)))

if __name__=='__main__':main()
