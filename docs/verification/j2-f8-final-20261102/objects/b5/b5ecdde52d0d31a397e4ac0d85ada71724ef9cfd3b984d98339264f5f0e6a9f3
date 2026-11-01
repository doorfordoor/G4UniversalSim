"""Prepare a byte-preserving documentation candidate in out/, never apply it."""
from pathlib import Path
import difflib, hashlib, json, re, subprocess
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'design-link-proposal'
HEAD='56b689fb9ac920cbb1203b2b94dae2483d25f622'
SOURCE=ROOT/'out/collab/j2-f8-design'
ARCHIVE=Path('docs/collab/reviews/20261101-j2-f8-design-evidence')
OUTBOX=Path('docs/collab/outbox/20261101-deepseek-j2-f8-design.md')
RAW=('request.json','response.json','deepseek-design.md','acceptance-checklist.md')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def emit(path,raw):
    assert path.resolve().is_relative_to((ROOT/'out').resolve())
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
def json_bytes(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def privacy(name,raw):
    text=raw.decode('utf-8-sig')
    patterns={
        'api_key_literal':r'(?i)\bsk-[A-Za-z0-9_-]{16,}\b',
        'bearer_credential':r'(?i)Bearer\s+[A-Za-z0-9_.-]{16,}',
        'windows_absolute_path':r'(?i)\b[A-Z]:[\\/]',
        'private_unix_home':r'/(?:home|Users|root|mnt/[a-z])/[^/\s]+',
        'credential_location':r'(?i)secrets[/\\]|api_key\.txt|credentials',
    }
    hits={k:[n for n,line in enumerate(text.splitlines(),1) if re.search(pattern,line)] for k,pattern in patterns.items()}
    fields=[]
    if name.endswith('.json'):
        def visit(v,path=''):
            if isinstance(v,dict):
                for key,value in v.items():
                    if key.lower() in ('authorization','api_key','apikey','access_token','password','secret') and value:fields.append(path+'/'+key)
                    visit(value,path+'/'+key)
            elif isinstance(v,list):
                for i,item in enumerate(v):visit(item,path+'/'+str(i))
        visit(json.loads(raw))
    assert not any(hits.values()) and not fields,(name,hits,fields)
    return dict(file=name,pattern_hits={k:v for k,v in hits.items() if v},credential_json_fields=fields)

def main():
    assert not OUT.exists(),'Do not overwrite a prior draft'
    raw={name:(SOURCE/name).read_bytes() for name in RAW}
    scans=[privacy(name,value) for name,value in raw.items()]
    request=json.loads(raw['request.json']);response=json.loads(raw['response.json'])
    body=response['raw_response'];content=body['choices'][0]['message']['content']
    assert digest(request['body']['messages'][0]['content'].encode())==request['prompt_sha256']
    assert raw['deepseek-design.md'].decode()==content+'\n'
    assert response['http_status']==200 and body['choices'][0]['finish_reason']=='stop'
    tree=OUT/'candidate-tree'
    files=[]
    for name,value in raw.items():
        target=ARCHIVE/'raw'/name;emit(tree/target,value)
        files.append(dict(source=(Path('out/collab/j2-f8-design')/name).as_posix(),target=target.as_posix(),bytes=len(value),sha256=digest(value)))
    excluded=[]
    for name,reason in [('request_design.py','Local credential-file locator is present; publish only relative code provenance and SHA, never its body.'),
                        ('progress.md','Ephemeral resumable task state is not publication evidence; preserve only relative provenance and SHA.')]:
        value=(SOURCE/name).read_bytes();excluded.append(dict(source=(Path('out/collab/j2-f8-design')/name).as_posix(),bytes=len(value),sha256=digest(value),reason=reason))
    manifest=dict(schema='g4usim_historical_design_evidence_v1',historical_only=True,implementation_acceptance=False,
                  source_candidate_head=HEAD,source_document=OUTBOX.as_posix(),
                  started_utc=response['started_utc'],finished_utc=response['finished_utc'],http_status=response['http_status'],
                  requested_model=response['requested_model'],returned_model=body['model'],response_id=body['id'],
                  finish_reason=body['choices'][0]['finish_reason'],prompt_sha256=request['prompt_sha256'],
                  design_text_relation='Exact choices[0].message.content plus one trailing LF',
                  byte_scope='Byte-identical existing request/response/design/checklist files; not a claim to original HTTP wire serialization',
                  files=files,excluded_local_only=excluded,privacy_scan=scans)
    emit(tree/ARCHIVE/'manifest.json',json_bytes(manifest))
    emit(tree/ARCHIVE/'.gitattributes',b'raw/** -text\n')
    rows='\n'.join(f'| [{Path(x["target"]).name}](raw/{Path(x["target"]).name}) | {x["bytes"]} | `{x["sha256"]}` |' for x in files)
    readme=('''# J2/F8 历史 DeepSeek 设计咨询原件

日期：2026-11-01。此目录只保存真实设计咨询及咨询前独立 checklist，不是实施验收、CI通过或物理正确性的证据。

请求与response文件完整保留既有调用脚本落盘字节；response.json内raw_response为服务返回的JSON对象，不冒称HTTP原始wire字节。设计正文等于choices[0].message.content加末尾一个LF。原件无鉴权头、密钥、凭据定位或私人绝对路径；接口地址、服务响应ID、usage与模型字段原样保留。

| 原件 | 字节数 | SHA-256 |
|---|---:|---|
'''+rows+'''

目录级.gitattributes将raw/**设为-text，避免跨平台checkout改变原件哈希。manifest.json给出完整来源、字节身份和排除项。调用脚本含本机凭据定位，故不发布脚本正文；progress.md为临时续接状态，也不作为当前状态文档发布。两者仅保留仓库相对provenance与SHA，原始out文件仍由本机保管。

checklist原件中的复选框属于当时未执行的计划，不能用后续结果回填或据此宣布阶段完成。人工取舍和后续职责仍见原outbox设计回信；本次只是稳定证据落点与链接修复。
''')
    emit(tree/ARCHIVE/'README.md',readme.encode())
    before=subprocess.check_output(['git','show',HEAD+':'+OUTBOX.as_posix()]).decode('utf-8')
    before=before.replace('\r\n','\n')
    after=re.sub(r'工作区 `[^`]+`，分支','仓库 `G4UniversalSim`，分支',before,count=1)
    excluded_by_name={Path(x['source']).name:x for x in excluded}
    prefix='../../../out/collab/j2-f8-design/'
    pattern=re.compile(r'\[([^\]]+)\]\('+re.escape(prefix)+r'([^\)]+)\)')
    replacements=[]
    def replace(match):
        label,name=match.groups();replacements.append(name)
        if name in raw:return '['+label+'](../reviews/20261101-j2-f8-design-evidence/raw/'+name+')'
        entry=excluded_by_name[name]
        return '`'+entry['source']+'`（仅本地 provenance；SHA-256 `'+entry['sha256']+'`）'
    after=pattern.sub(replace,after)
    assert len(replacements)==7 and prefix not in after,replacements
    assert not re.search(r'(?i)\b[A-Z]:[\\/]',after),'Private absolute workspace path remains'
    emit(tree/OUTBOX,after.encode())
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+OUTBOX.as_posix(),tofile='b/'+OUTBOX.as_posix()))
    emit(OUT/'outbox-only.patch',patch.encode())
    checked=[]
    for p in tree.rglob('*.md'):
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            target=target.split('#',1)[0]
            if not target or re.match(r'^[A-Za-z]+:',target):continue
            resolved=(p.parent/target).resolve();assert resolved.is_file(),(p,target)
            checked.append(dict(source=p.relative_to(tree).as_posix(),target=target))
    inventory=[dict(path=p.relative_to(tree).as_posix(),bytes=p.stat().st_size,sha256=digest(p.read_bytes())) for p in sorted(tree.rglob('*')) if p.is_file()]
    proposal=dict(status='draft_only_not_applied',base_head=HEAD,tracked_files_modified=False,external_calls=0,
                  proposal_directory=ARCHIVE.as_posix(),raw_files=files,candidate_files=inventory,
                  ignored_out_links_replaced=len(replacements),relative_markdown_links_checked=len(checked),
                  original_outbox_sha256=digest(before.encode()),candidate_outbox_sha256=digest(after.encode()),
                  patch_sha256=digest(patch.encode()),privacy='4 published raw files scanned, no credential fields/literals/private absolute paths; script body excluded',
                  exact_tree_publication_requires_main_decision=True)
    emit(OUT/'proposal.json',json_bytes(proposal))
    emit(OUT/'privacy-scan.json',json_bytes(dict(published_files=scans,excluded=excluded,source_secret_file_opened=False)))
    print(json.dumps({k:proposal[k] for k in ('status','ignored_out_links_replaced','relative_markdown_links_checked','patch_sha256','candidate_outbox_sha256')}))
if __name__=='__main__':main()
