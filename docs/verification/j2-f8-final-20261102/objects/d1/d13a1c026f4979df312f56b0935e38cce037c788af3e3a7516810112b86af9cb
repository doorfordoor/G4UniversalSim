"""Read-only plan verification: standard library only, no apply/import/Qt/tests."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[4]
PLAN=Path(__file__).parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def project_patch(original, patch, target):
    """Strict unified-diff projection in memory; neither git apply nor writes."""
    text=patch.decode('utf-8')
    assert '\r' not in text, 'Reviewed patch must be LF'
    lines=text.splitlines(keepends=True)
    assert lines[0]=='--- a/'+target+'\n'
    assert lines[1]=='+++ b/'+target+'\n'
    source=original.decode('utf-8').splitlines(keepends=True)
    output=[];position=0;index=2;hunks=0
    while index<len(lines):
        match=re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n',lines[index])
        assert match,('Unexpected patch line',index,lines[index])
        old_start,old_count,new_start,new_count=int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')
        start=old_start-1 if old_count else old_start
        assert position<=start<=len(source)
        output.extend(source[position:start]);position=start
        assert len(output)==(new_start-1 if new_count else new_start)
        index+=1;consumed=produced=0
        while index<len(lines) and not lines[index].startswith('@@ '):
            line=lines[index];assert line and line[0] in ' +-',('Unexpected diff payload',index)
            prefix,payload=line[0],line[1:]
            if prefix in ' -':
                assert position<len(source) and source[position]==payload,('Context mismatch',target,position+1)
                position+=1;consumed+=1
            if prefix in ' +':
                output.append(payload);produced+=1
            index+=1
        assert (consumed,produced)==(old_count,new_count)
        hunks+=1
    assert hunks>0
    output.extend(source[position:])
    return ''.join(output).encode('utf-8'),hunks

def split_patch(patch):
    text=patch.decode('utf-8')
    assert '\r' not in text
    headers=list(re.finditer(r'^--- a/([^\n]+)\n\+\+\+ b/\1\n',text,re.M))
    assert headers and headers[0].start()==0
    result={}
    for index,header in enumerate(headers):
        target=header[1]
        assert target not in result
        stop=headers[index+1].start() if index+1<len(headers) else len(text)
        result[target]=text[header.start():stop].encode('utf-8')
    return result

def verify(manifest):
    base=manifest['base_git_commit']
    head=subprocess.check_output(['git','-c','core.longpaths=true','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert head==base
    targets=manifest['targets'];patches=manifest['patches']
    assert len(targets)==6 and len({e['target_relative_path'] for e in targets})==6
    assert len(patches)==5 and len({p['patch_relative_path'] for p in patches})==5
    assert len({p['patch_id'] for p in patches})==5
    assert manifest['application_patch_order']==[p['patch_id'] for p in patches]
    by_id={e['id']:e for e in targets}
    assert len(by_id)==6
    result=[];covered=[]
    for patch in patches:
        assert patch['apply_once'] is True
        raw=(ROOT/patch['patch_relative_path']).read_bytes()
        assert sha(raw)==patch['patch_sha256']
        sections=split_patch(raw)
        entries=[by_id[ident] for ident in patch['target_ids']]
        assert set(sections)=={entry['target_relative_path'] for entry in entries}
        file_results=[]
        for entry in entries:
            assert entry['patch_id']==patch['patch_id']
            assert entry['patch_relative_path']==patch['patch_relative_path']
            assert entry['patch_sha256']==patch['patch_sha256']
            target=entry['target_relative_path']
            original=(ROOT/target).read_bytes()
            blob=subprocess.check_output(['git','-c','core.longpaths=true','show',head+':'+target],cwd=ROOT)
            assert original==blob and sha(original)==entry['original_tracked_sha256']
            projected,hunks=project_patch(original,sections[target],target)
            candidate=(ROOT/entry['candidate_source_relative_path']).read_bytes()
            assert projected==candidate and sha(projected)==entry['applied_candidate_sha256']
            review=(ROOT/entry['independent_review_relative_path']).read_bytes()
            assert sha(review)==entry['independent_review_sha256']
            review_text=review.decode('utf-8-sig')
            assert entry['patch_sha256'] in review_text and entry['applied_candidate_sha256'] in review_text
            if 'independent_execution_relative_path' in entry:
                execution_raw=(ROOT/entry['independent_execution_relative_path']).read_bytes()
                assert sha(execution_raw)==entry['independent_execution_sha256']
                execution=json.loads(execution_raw.decode('utf-8-sig'))
                assert execution['status']=='pass' and execution['patch_sha256']==patch['patch_sha256']
                evidence=next(row for row in execution['files'] if row['path']==target)
                assert evidence['original_sha256']==entry['original_tracked_sha256']
                assert evidence['candidate_sha256']==entry['applied_candidate_sha256']
            file_results.append({'id':entry['id'],'target':target,'hunks':hunks,
                                 'original_matches_commit':True,'projection_matches_candidate':True,'review_identity_matches':True})
            covered.append(entry['id'])
        result.append({'patch_id':patch['patch_id'],'apply_count_planned':1,'file_count':len(file_results),'files':file_results})
    assert len(covered)==len(set(covered))==6
    k1=next(row for row in result if row['patch_id']=='k1_policy_final_v1')
    assert k1['file_count']==2 and k1['apply_count_planned']==1
    parent=manifest['parent_plan']
    assert sha((ROOT/parent['manifest_relative_path']).read_bytes())==parent['manifest_sha256']
    assert sha((ROOT/parent['receipt_relative_path']).read_bytes())==parent['receipt_sha256']
    for name,digest in manifest['v1_original_file_hashes'].items():
        assert sha((PLAN.parent/name).read_bytes())==digest
    return {'status':'verified','base_git_commit':head,'patch_count':5,'target_count':6,
            'patches':result,'K1_multi_file_patch_planned_once':True,'v1_originals_unchanged':True,
            'patches_applied':False,'qt_or_native_started':False,'tests_rerun':False,'pending_main_additions':['docs']}

if __name__=='__main__':
    print(json.dumps(verify(json.loads((PLAN/'manifest.json').read_text(encoding='utf-8'))),ensure_ascii=False,indent=2))
