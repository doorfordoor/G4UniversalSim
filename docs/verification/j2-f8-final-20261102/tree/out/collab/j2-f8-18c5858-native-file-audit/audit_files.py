"""Pure file audit only. No Qt imports, image rendering, launcher or profile runs."""
from pathlib import Path
import hashlib,json,struct,collections,datetime,subprocess,re
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
HEAD='18c5858fd6e80a5cb6096beacebfef69c479ad49'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def image_info(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        assert raw[12:16]==b'IHDR'
        width,height=struct.unpack('>II',raw[16:24]);return 'image/png',width,height
    if raw.startswith(b'\xff\xd8\xff'):
        pos=2
        while pos<len(raw):
            assert raw[pos]==255
            while raw[pos]==255:pos+=1
            marker=raw[pos];pos+=1
            if marker in (0xd8,0xd9,0x01) or 0xd0<=marker<=0xd7:continue
            if marker==0xda:break
            length=int.from_bytes(raw[pos:pos+2],'big');assert length>=2
            if marker in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
                height=int.from_bytes(raw[pos+3:pos+5],'big');width=int.from_bytes(raw[pos+5:pos+7],'big')
                return 'image/jpeg',width,height
            pos+=length
        raise ValueError('JPEG has no supported SOF dimensions')
    raise ValueError('Unsupported image signature '+raw[:16].hex())
def ui_names(text):
    result=[]
    for line in text.splitlines():
        stripped=line.strip()
        if stripped.endswith(('RunHistoryPage.QLineEdit','RunHistoryPage.QComboBox')):
            description=stripped.split(' ID:',1)[0]
            match=re.match(r'^\d+\s+(.+?)\s+\(settable, string\)\s*(.*)$',description)
            if match:result.append({'role':match[1],'name':match[2].split(' Value:',1)[0].strip()})
    return result

def audit(scale,session):
    source=ROOT/('out/verification/j2-f8-18c5858/native'+scale)
    destination=OUT/('native'+scale);destination.mkdir(exist_ok=True)
    raw_files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    index=[{'name':name,'bytes':len(raw),'sha256_raw_bytes':sha(raw)} for name,raw in sorted(raw_files.items())]
    load=lambda name:json.loads(raw_files[name].decode('utf-8-sig'))
    launch=load('launch.json');identity=load('identity.json');exit_record=load('exit.json');visual=load('visual-observations.json')
    observations=[json.loads(line) for line in raw_files['observations.jsonl'].decode('utf-8-sig').splitlines()]
    issues=[]
    def check(condition,label):
        if not condition:issues.append(label)
    check(launch['head']==launch['ending_head']==identity['head']==HEAD,'head mismatch')
    check(launch['status']=='exited' and launch['process_exit_code']==0,'launcher not normal exit0')
    check(exit_record['exit_code']==0 and exit_record['visible'] is False,'host exit record abnormal')
    check(launch['ending_git_status']=='','ending git status not clean')
    check(launch['exe_sha256']==identity['exe_sha256']==launch['ending_exe_sha256']=='01e0fb795f93772ccfa818d625fee145d8da1ad3ad80894372a9a855f0af108a','exe identity drift')
    check(launch['host_sha256']==identity['host_sha256']=='b9c216045a478a5bffd503371405cf767b290ff87e811da3623dcbc89dad334a','host identity drift')
    check(launch['qpa']=='windows','qpa is not windows')
    check(all(row['dpr']==({'150':1.5,'125':1.25}[scale]) for row in observations),'DPR mismatch')
    expected_size={'150':[760,640],'125':[1200,800]}[scale]
    check(all(row['size']==expected_size for row in observations),'window size changed')
    check(all(row['runner_state']=='ProcessState.NotRunning' for row in observations),'main runner active in passive sample')
    check(all(row['edit_history']=={'undo':False,'redo':False,'modified':False} for row in observations),'cached edit history changed')
    runtime=launch['runtime'];prefix=Path(runtime['prefix']).resolve()
    check(prefix!=Path(runtime['base_prefix']).resolve(),'venv prefix equals base prefix')
    check(Path(runtime['executable']).resolve().parent==Path(identity['python']).resolve().parent,'host/runtime interpreter directories differ')
    check(all(Path(module['file']).resolve().is_relative_to(prefix) for module in runtime['modules'].values()),'module outside recorded venv')
    check(identity['pyvista']==runtime['modules']['pyvista'],'host/runtime PyVista identity mismatch')
    gui_differences=[path for path,digest in identity['gui_files'].items() if not (ROOT/path).is_file() or sha((ROOT/path).read_bytes())!=digest]
    check(not gui_differences,'GUI source identity differs from current frozen bytes')
    image_rows=[];references=collections.Counter();visual_rows=[]
    for row in visual:
        matched=[(n+1,state) for n,state in enumerate(observations) if state['time']<=row['time']/1000]
        preceding=matched[-1] if matched else None
        visual_rows.append({'label':row['label'],'time_ms':row['time'],'note_from_main':row['note'],'preceding_passive_row':preceding[0] if preceding else None,'preceding_passive_focus':preceding[1]['focus'] if preceding else None,'images':[Path(image['path']).name for image in row['images']]})
        for image in row['images']:
            path=Path(image['path']).resolve();check(path.is_relative_to(source.resolve()),'image reference outside native root')
            raw=path.read_bytes();mime,width,height=image_info(raw);name=path.name;references[name]+=1
            matches={'sha256':sha(raw)==image['sha256'],'mime':mime==image['mime'],'width':width==image['width'],'height':height==image['height']}
            check(all(matches.values()),'image metadata mismatch '+name)
            image_rows.append({'name':name,'sha256_raw_bytes':sha(raw),'bytes':len(raw),'detected_mime':mime,'recorded_mime':image['mime'],'width':width,'height':height,'extension':path.suffix,'metadata_matches':matches,'visual_label':row['label'],'origin':[image.get('originX'),image.get('originY')],'z_index':image.get('zIndex')})
    actual_images={name for name in raw_files if Path(name).suffix.lower() in ('.jpg','.jpeg','.png')}
    check(actual_images==set(references),'unreferenced/missing image file')
    check(all(value==1 for value in references.values()),'same image path referenced more than once')
    check(all(a['time']<=b['time'] for a,b in zip(observations,observations[1:])),'passive times nonmonotonic')
    check(all(a['time']<=b['time'] for a,b in zip(visual,visual[1:])),'visual times nonmonotonic')
    snapshot_rows=[]
    for name,raw in sorted(raw_files.items()):
        if name.endswith('.txt'):
            text=raw.decode('utf-8-sig');names=ui_names(text)
            if names:snapshot_rows.append({'file':name,'history_control_names':names})
    hash_transitions=[]
    previous=None
    for n,row in enumerate(observations,1):
        if row['project_sha']!=previous:
            hash_transitions.append({'row':n,'time':row['time'],'page':row['page'],'title':row['title'],'project_sha':row['project_sha'],'edit_history':row['edit_history']})
            previous=row['project_sha']
    project_name_rows=[{'row':n,'focus':row['focus'],'all_recorded_name_label_rects_contained':all(item['field_contained'] and item['label_contained'] for item in row['project_viewports']),'geometry':row['project_viewports']} for n,row in enumerate(observations,1) if row['page']==1]
    modal_rows=[(n,row)for n,row in enumerate(observations,1) if row['modal']]
    wizard=None
    if modal_rows:
        first=modal_rows[0][0];last=modal_rows[-1][0];start=first-1;end=min(last+1,len(observations))
        span=observations[start-1:end]
        wizard={'passive_span_rows_inclusive':[start,end],'modal_rows':[n for n,row in modal_rows],'unique_project_hashes':sorted({r['project_sha']for r in span}),'unique_cached_F5_states':[json.loads(s)for s in sorted({json.dumps(r['edit_history'],sort_keys=True)for r in span})],'all_titles':sorted({r['title']for r in span}),'full_F5_snapshot_or_fingerprint_recorded':False}
        check(len(wizard['unique_project_hashes'])==1,'wizard span raw project hash changed')
    phases={'raw_hash_transitions':hash_transitions,'wizard_span':wizard,'visited_pages_zero_based':sorted({r['page']for r in observations})}
    preserved=all(sha((source/name).read_bytes())==sha(raw) for name,raw in raw_files.items())
    check(preserved,'source evidence changed during audit')
    result={'result':'file_integrity_checked_with_scope_limits' if not issues else 'file_review_has_issues','scale':scale,'source_root':str(source.relative_to(ROOT)).replace('\\','/'),'main_reported_original_session':session,'main_reported_session_exit_code':0,'file_recorded_process_exit_code':launch['process_exit_code'],'host_exit':exit_record,'launcher_pid':launch['pid'],'host_pid':identity['pid'],'pid_values_equal':launch['pid']==identity['pid'],'process_ancestry_not_collected_by_this_file_review':True,'dpr':observations[0]['dpr'],'size':expected_size,'passive_rows':len(observations),'visual_records':len(visual),'image_references':len(image_rows),'mime_counts':dict(collections.Counter(i['detected_mime']for i in image_rows)),'all_image_recorded_hashes_and_dimensions_match':all(all(r['metadata_matches'].values())for r in image_rows),'empty_text_snapshots':[name for name,raw in raw_files.items() if name.endswith('.txt') and not raw],'gui_files_count':len(identity['gui_files']),'gui_identity_differences':gui_differences,'phases':phases,'project_name_geometry_records':project_name_rows,'recorded_History_UIA_names':snapshot_rows,'issues':issues,'original_files_preserved':preserved,'privacy':{'raw_local_only':True,'images_copied_or_uploaded':False,'no_new_visual_pixel_inspection':True,'QQ_overlay_pixels_excluded_by_main_not_masked_by_auditor':True},'scope_limits':['cached F5 only undo/redo/modified; no full snapshot/fingerprint','passive main-runner state does not monitor every preview/helper process','project_viewports always measures project_name, not focused EXE','visual pixel conclusions are main observations, this reviewer checked files only','300ms passive samples are not an exhaustive input/action trace']}
    (destination/'file-index.json').write_bytes(json.dumps(index,ensure_ascii=False,indent=2).encode('utf-8'))
    (destination/'image-index.json').write_bytes(json.dumps(image_rows,ensure_ascii=False,indent=2).encode('utf-8'))
    (destination/'visual-passive-links.json').write_bytes(json.dumps(visual_rows,ensure_ascii=False,indent=2).encode('utf-8'))
    (destination/'receipt.json').write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8'))
    return result

if __name__=='__main__':
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==HEAD
    results=[audit('150',68494),audit('125',17970)]
    summary={'scope':'pure local file audit; no Qt/native/profile/build/launcher execution','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'profiles':[{'scale':r['scale'],'result':r['result'],'images':r['image_references'],'mime_counts':r['mime_counts'],'passive_rows':r['passive_rows'],'visual_records':r['visual_records'],'issues':r['issues'],'empty_text_snapshots':r['empty_text_snapshots'],'pid_values_equal':r['pid_values_equal']}for r in results]}
    (OUT/'summary.json').write_bytes(json.dumps(summary,ensure_ascii=False,indent=2).encode('utf-8'))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
