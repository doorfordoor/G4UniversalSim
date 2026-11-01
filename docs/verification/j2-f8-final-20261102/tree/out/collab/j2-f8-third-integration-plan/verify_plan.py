"""Read-only plan verification: standard library only, no apply/import/Qt/tests."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[3]
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

def verify(manifest):
    head=subprocess.check_output(['git','-c','core.longpaths=true','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert head==manifest['base_git_commit']
    entries=manifest['entries']
    assert len(entries)==4 and len({entry['target_relative_path'] for entry in entries})==4
    results=[]
    for entry in entries:
        target=entry['target_relative_path']
        original=(ROOT/target).read_bytes()
        blob=subprocess.check_output(['git','-c','core.longpaths=true','show',head+':'+target],cwd=ROOT)
        assert original==blob
        assert sha(original)==entry['original_tracked_sha256']
        patch=(ROOT/entry['patch_relative_path']).read_bytes()
        assert sha(patch)==entry['patch_sha256']
        projected,hunks=project_patch(original,patch,target)
        candidate=(ROOT/entry['candidate_source_relative_path']).read_bytes()
        assert projected==candidate
        assert sha(projected)==entry['applied_candidate_sha256']
        review=(ROOT/entry['independent_review_relative_path']).read_bytes()
        assert sha(review)==entry['independent_review_sha256']
        assert entry['patch_sha256'] in review.decode('utf-8-sig')
        assert entry['applied_candidate_sha256'] in review.decode('utf-8-sig')
        results.append({'id':entry['id'],'target':target,'base_matches_commit':True,'patch_sha_matches':True,
                        'in_memory_projection_matches_reviewed_candidate':True,'review_identity_matches':True,'hunks':hunks})
    return {'status':'verified','base_git_commit':head,'entries':results,'writes_to_targets':False,
            'patches_applied':False,'qt_or_native_started':False,'tests_rerun':False,'K1_or_docs_included':False}

if __name__=='__main__':
    report=verify(json.loads((PLAN/'manifest.json').read_text(encoding='utf-8')))
    print(json.dumps(report,ensure_ascii=False,indent=2))
