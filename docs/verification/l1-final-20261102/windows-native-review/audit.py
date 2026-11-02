"""Local metadata-only review. Never decode native images or read UIA text."""
import collections
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
HEAD = '246e4f6f1b97cc5e0651ff01262c85cf2e9c28d3'
EXE = '1cb8dc7267f8191792969ba1ab280f1a4936d05799b9a98991a2517fb358a758'
HOST = ROOT / 'out/collab/l1-native-resume-246-attempt2'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def relative(p):
    return Path(p).resolve().relative_to(ROOT).as_posix()

def metadata(p, scope, mime=None):
    p = Path(p)
    return dict(scope=scope, path=relative(p), size_bytes=p.stat().st_size,
                sha256=digest(p), mime=mime or ('application/json' if p.suffix == '.json' else 'text/plain'))

def write(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

def obj(v):
    return v if isinstance(v, dict) else {}

def inside(rect, viewport):
    x,y,w,h = rect
    a,b,c,d = viewport
    return x >= a and y >= b and x+w <= a+c and y+h <= b+d

def union(a,b):
    if b is None:
        return a
    x,y = min(a[0], b[0]), min(a[1], b[1])
    return [x,y,max(a[0]+a[2],b[0]+b[2])-x,max(a[1]+a[3],b[1]+b[3])-y]

def fits(a,b):
    return a[2] <= b[2] and a[3] <= b[3]

config = load(HOST/'launch-config.json')
review = load(HOST/'review.json')
protocol = load(ROOT/'out/collab/l1-native-246-layout-protocol.json')
provenance_path = ROOT/'out/collab/l1-whole-acceptance/readonly-recovery/provenance.json'
provenance = load(provenance_path)
source_journal_path = ROOT/provenance['source']
assert digest(source_journal_path) == provenance['source_sha256']
historical = load(source_journal_path)['payload']
assert historical['usage'] == {'calls':6,'events':4}
assert len(historical['operations']) == 6
assert review['status'] == 'PASS'
for name, sha in review['files_sha256'].items():
    assert digest(HOST/name) == sha, name
assert protocol['head'] == HEAD and protocol['exe_sha256'] == EXE
assert protocol['business_actions_authorized_for_this_native_recheck'] == []
assert protocol['actual_model_requests_expected'] == protocol['new_run_export_events_expected'] == 0
build_path = ROOT/config['build_receipt']
assert digest(build_path) == config['build_receipt_sha256']
build = load(build_path)
assert build['head'] == HEAD and build['exit_codes'] == [0,0]
assert build['capabilities_exit'] == 0 and build['executable_sha256'] == EXE

assets, sources, lanes = [], [], []
source_paths = [HOST/n for n in ('host.py','launch.py','launch-config.json','review.json','source-gui-identity.json')]
source_paths += [build_path,provenance_path,source_journal_path,ROOT/'out/collab/l1-native-246-layout-protocol.json',
                 ROOT/'gui/g4usim_gui/agent/controller.py',ROOT/'gui/g4usim_gui/window/config_agent.py']
all_start_hashes = {}
for scale in (125,150):
    folder = ROOT/f'out/verification/l1-246e4f6/resumed-acceptance/native{scale}-agent'
    identity, launch, exit_, fixture = [load(folder/n) for n in ('identity.json','launch.json','exit.json','fixture.json')]
    observations = [json.loads(x) for x in (folder/'observations.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    signals = [json.loads(x) for x in (folder/'signals.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    assert identity['head'] == launch['head'] == launch['ending_head'] == HEAD
    assert identity['exe_sha256'] == launch['exe_sha256'] == launch['ending_exe_sha256'] == EXE
    assert digest(identity['exe']) == EXE
    assert len(identity['GUI_files']) == 157
    for name, sha in identity['GUI_files'].items():
        assert digest(ROOT/name) == sha, name
    for key, name in (('host_sha256','host.py'),('launcher_sha256','launch.py'),('config_sha256','launch-config.json')):
        assert launch[key] == digest(HOST/name)
    assert identity['host_sha256'] == launch['host_sha256']
    assert identity['config_sha256'] == launch['config_sha256']
    assert launch['independent_review_sha256'] == digest(HOST/'review.json')
    assert launch['build_receipt_sha256'] == digest(build_path)
    assert identity['DPR'] == scale/100
    assert all(o['DPR'] == scale/100 for o in observations)
    assert launch['scale_env'] == config['profiles'][str(scale)]['scale_env']
    assert launch['qpa'] == 'windows'
    assert launch['status'] == 'exited' and launch['process_exit_code'] == exit_['exit_code'] == 0
    assert launch['ending_git_status'] == ''
    assert launch['owned_cleanup_remaining'] == launch['process_observation_errors'] == []
    assert launch['no_process_termination_or_global_cleanup'] is True
    assert exit_['visible'] is False and exit_['not_a_user_task_timing'] is True
    assert fixture['prompt_or_permissions_prefilled'] is False
    assert fixture['automatic_task_or_K1_execution'] is False
    assert fixture['automatic_backend_preview'] is False

    journal_path = ROOT/f'out/collab/l1-whole-acceptance/readonly-recovery/task-{scale}.json'
    journal = load(journal_path)['payload']
    assert journal['state'] == 'cancelled'
    assert journal['authorization'] == historical['authorization']
    assert journal['operations'] == historical['operations']
    assert journal['usage'] == historical['usage']
    assert journal['records'][:len(historical['records'])] == historical['records']
    assert len(journal['records']) == len(historical['records'])+1
    assert journal['records'][-1]['kind'] == 'state'
    agent_signals = [s['value'] for s in signals if s['kind']=='agent']
    assert len(signals) == 3 and len(agent_signals) == 2
    assert [s['sequence'] for s in signals] == [1,2,3]
    assert signals[0]['kind'] == 'experiment'
    caches = [obj(o['controller_signals_cache']).get('agent') for o in observations]
    agents = agent_signals+[a for a in caches if isinstance(a,dict)]+[exit_['agent_cache']]
    for a in agents:
        assert a['state'] == 'interrupted' and a['busy'] is False and a['provider_alive'] is False
        assert a['calls'] == 6 and a['events'] == 4 and a['recovery_observed'] is True
        assert [x['operation_id'] for x in a['operations']] == [x['operation_id'] for x in historical['operations']]
    assert all(o['cached_F5_flags'] == {'undo':False,'redo':False,'modified':False} for o in observations)
    recovered = [o for o in observations if isinstance(obj(o['controller_signals_cache']).get('agent'),dict)]
    blocked_roles = ['submit','apply','continue','run','cancel','confirm','export']
    assert recovered
    for o in recovered:
        for role in blocked_roles:
            assert o['panel']['footer'][role]['enabled'] is False, (scale,role)

    numeric_focus_rows=[]
    fitting_checks=0
    nonfitting=[]
    for i,o in enumerate(observations,1):
        if o['modal']:
            continue
        views=o['focus_viewports']
        if not views:
            continue
        closest_union=union(views[0]['control'],views[0]['label'])
        eligible=fits(closest_union,views[0]['viewport'])
        if not eligible:
            # An oversized editor/checkbox is not a fully contained target assertion.
            nonfitting.append(dict(observation=i,widget_class=obj(o['focus']).get('class'),
                                  target_rect=closest_union,nearest_viewport=views[0]['viewport']))
        for j,v in enumerate(views):
            rect=union(v['control'],v['label'])
            actual=inside(rect,v['viewport'])
            assert v['control_contained'] == inside(v['control'],v['viewport'])
            if eligible:
                assert actual, (scale,i,j)
                fitting_checks += 1
            numeric_focus_rows.append(dict(observation=i,ancestor=j,widget_class=obj(o['focus']).get('class'),
                viewport=v['viewport'],target_rect=rect,contained=actual,
                full_target_contract_applicable=eligible,scroll_offset=[v['h'],v['v']]))
    button_rows=[x for x in numeric_focus_rows if x['widget_class']=='QPushButton']
    assert button_rows and all(x['contained'] for x in button_rows)

    lane_assets=[]
    for p in sorted(folder.rglob('*')):
        if p.is_file() and (p.suffix.lower()=='.png' or p.name.endswith('.uia.txt')):
            lane_assets.append(metadata(p,'private_local_only', 'image/png' if p.suffix.lower()=='.png' else 'text/plain'))
    assets.extend(lane_assets)
    source_paths.extend(folder/n for n in ('identity.json','launch.json','exit.json','fixture.json','history.json','observations.jsonl','signals.jsonl'))
    source_paths.append(journal_path)
    anchors = [7,17,24,25,36,37,39,41] if scale==125 else [9,19,26,27,34,36,38]
    anchor_paths=[]
    for n in anchors:
        matches=[a['path'] for a in lane_assets if a['mime']=='image/png' and Path(a['path']).name.startswith(f'{n:02d}-')]
        assert len(matches)==1,(scale,n)
        anchor_paths.extend(matches)
    lanes.append(dict(scale_label_percent=scale,head=HEAD,exe_sha256=EXE,
        host_sha256=identity['host_sha256'],launcher_sha256=launch['launcher_sha256'],config_sha256=launch['config_sha256'],
        gui_files_verified=157,gui_identity_sha256=hashlib.sha256(json.dumps(identity['GUI_files'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        DPR=identity['DPR'],logical_dpi=identity['logical_dpi'],screen=identity['screen'],available=identity['available'],
        qpa=launch['qpa'],scale_environment=launch['scale_env'],
        scaling_scope='Measured Qt DPR; 150% uses inherited desktop125% times explicit QT_SCALE_FACTOR1.2; no physical display change claimed.',
        launcher_exit=launch['process_exit_code'],host_exit=exit_['exit_code'],ending_git_clean=True,
        owned_cleanup_remaining=[],process_observation_errors=[],no_process_termination_or_global_cleanup=True,
        observations=len(observations),signal_records=len(signals),historical_calls=6,historical_events=4,
        historical_operations_unchanged=True,historical_authorization_preserved_in_journal_but_not_restored_to_controller=True,
        original_records_retained=len(historical['records']),isolated_journal_added_state_records=1,
        old_source_journal_unchanged=True,observed_new_model_calls=0,observed_new_operations=0,observed_new_run_export_events=0,
        no_network_telemetry_claim=True,passive_signal_caches_not_full_network_audit=True,
        busy_or_provider_alive_observations=0,mutating_footer_roles_disabled_after_recovery=blocked_roles,
        plan_and_resume_buttons_enabled_scope='Plan starts a separately authorized future task; Resume reads a saved journal. Neither restores saved authority.',
        cached_f5_flags_stable=dict(undo=False,redo=False,modified=False),
        prompt_or_permissions_prefilled=False,automatic_task_or_K1_execution=False,automatic_backend_preview=False,
        focused_button_geometry_checks=len(button_rows),fitting_focus_ancestor_checks=fitting_checks,
        nonfitting_target_observations=nonfitting,focus_geometry=numeric_focus_rows,
        parent_visual_observation=dict(attribution='Parent /root observed actual native images; this reviewer did not decode images or read UIA.',
            image_paths=anchor_paths,reported=['focused buttons readable','natural F6/Tab','en-zh-en retained focus','Task interrupted read-only recovery']),
        png_files=sum(a['mime']=='image/png' for a in lane_assets),uia_files=sum(a['mime']=='text/plain' for a in lane_assets)))

old=ROOT/'out/verification/l1-246e4f6/native125-agent'
source_paths.extend(old/n for n in ('identity.json','launch.json','exit.json','fixture.json'))
for p in dict.fromkeys(source_paths):
    sources.append(metadata(p,'source_metadata_only_no_payload_copy'))
source_snapshot={s['path']:s['sha256'] for s in sources+assets}
assert digest(source_journal_path)==provenance['source_sha256']
controller=(ROOT/'gui/g4usim_gui/agent/controller.py').read_text(encoding='utf-8-sig')
assert 'self._authorization = {}  # A saved authorization never grants new execution.' in controller
assert 'self._scheduled_serial = None' in controller and 'self._recovered = True' in controller
head=subprocess.check_output(['git','-c','core.longpaths=true','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
status=subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain=v1'],cwd=ROOT,text=True).strip()
assert head == HEAD and not status
write('native-assets-metadata.json',assets)
write('source-metadata.json',sources)
receipt=dict(schema='l1_windows_native_independent_file_review_v1',
    created_utc=datetime.now(timezone.utc).isoformat(),status='PASS_WITH_EXPLICIT_SCOPE_LIMITS',
    reviewer_scope='Read structured files, hash raw local evidence; no Qt process, desktop control, PNG decoding or UIA text reading.',
    head=HEAD,current_source_clean=True,lanes=lanes,confirmed_P0=[],confirmed_P1=[],confirmed_P2=[],
    public_images=0,public_UIA_payloads=0,original_assets_copied=0,
    asset_metadata_whitelist=['scope','path','size_bytes','sha256','mime'],
    public_receipt_policy='Explicit fields only; no prompt, task text, credentials, endpoint/model configuration, journal authorization payload, UI strings, screenshots or UIA contents.',
    recovery_code_scope=dict(path='gui/g4usim_gui/agent/controller.py',function='recover',
        resets=['scheduled callback','current plan','pending steps','execution authorization'],
        behavior='Read-only historical workflow query; recovered tasks guarded from approve/queue/timeout; saved authorization is never reused.'),
    limits=[
        'Parent visual observations are attributed, not a second independent pixel observation.',
        'Focused fitting target/label union only; oversized editors and wider-than-nearest-viewport controls excluded from full-control visibility assertions.',
        'Nested editor rectangles extending past outer viewport are preserved numerically; nearest viewport clips oversized content. No whole-viewport or all-footer simultaneity support claim.',
        'Observed zero new dispatch is based on historical identity/count closure, signal caches and recovery code; not independently captured network traffic.',
        'Read-only recovery may persist a terminal state to isolated copies. It does not mean journal bytes never change.',
        'No task speed, participant reliability, general NLP, new cloud execution or physical validation claim.'
    ],historical_failed_125=dict(path=relative(old),preserved=True,
        status_scope='Earlier125 attempt remains separate as requested by parent; its launcher exit0 does not erase its failed observation/setup scope.',
        raw_assets_not_relabelled=True,not_replaced_or_deleted=True),
    historical_EE150_layout_failure_preserved=True,
    raw_asset_inventory='native-assets-metadata.json',structured_source_metadata='source-metadata.json')
write('review.json',receipt)
(OUT/'README.md').write_text('''# Windows125/150 原生文件独立复核

结论：限定范围通过，无新确认 P0/P1/P2。此收据只审结构化文件和原始字节哈希；没有开启 Qt、接管桌面、解码图片或读取 UIA 正文。实际可读性、自然 F6/Tab、英→中→英及 Task interrupted 显示由主线程视觉观察，锚点在 review.json。

两份会话均为冻结246e4f6；EXE、157个GUI包文件及审过的host/config/launcher/build收据吻合。实际DPR分别1.25/1.5，150使用桌面125%×显式Qt1.2，不能写成另改物理显示设置。两个launcher与host都正常exit0，结束Git clean，owned remaining为空，无进程强杀或全局清理。

恢复读取旧任务6 calls/4 events/6 operations，授权、operations及旧18条record前缀未变；两份隔离journal各仅追加一条终态state记录。旧源journal SHA仍与provenance相同。Controller recover清空执行授权和待调度步骤，所有观察中的provider/busy均false，变更类按钮禁用，未观察到新增模型请求/运行/导出。保存的历史授权不是新授权；这不是独立网络抓包，也不称恢复完全不写journal。

焦点按钮几何在两层工作区视口内；可容纳的最近视口焦点目标及祖先矩形检查通过。长文本编辑器和部分宽复选框超出最近视口的数值原样留在收据，不能扩成全控件、全视口或全部非焦点footer同屏保证。初次失败125与旧EE150失败按原身份保留，不因本轮正常退出被改记通过。

native-assets-metadata.json严格只有scope/path/size_bytes/SHA256/MIME五字段：125为24PNG+40UIA，150为20PNG+38UIA，共122项。原件严格本地保留，复制/上传/解码数量均为0。source-metadata.json只给结构化原件的元数据；review.json是显式白名单投影，无prompt、凭据、UIA正文、任务文本或授权payload。
''',encoding='utf-8',newline='\n')
assert all(set(a)=={'scope','path','size_bytes','sha256','mime'} for a in assets)
assert len(assets)==122
for path,sha in source_snapshot.items():
    assert digest(ROOT/path)==sha,path
generated=[metadata(OUT/n,'public_whitelisted_review') for n in ('review.json','README.md','native-assets-metadata.json','source-metadata.json','audit.py')]
write('verification.json',dict(status='PASS',original_metadata_entries_verified=len(source_snapshot),
    asset_entries=122,PNG_total=44,UIA_total=78,raw_asset_payloads_copied=0,images_decoded=0,UIA_texts_opened=0,
    metadata_exact_whitelist_verified=True,source_unchanged_after_review=True,git_head=head,git_status_clean=True,
    generated_files=generated))
print(json.dumps(dict(status='PASS_WITH_EXPLICIT_SCOPE_LIMITS',lanes=len(lanes),assets=len(assets),
    fitting_focus_checks=[l['fitting_focus_ancestor_checks'] for l in lanes],button_checks=[l['focused_button_geometry_checks'] for l in lanes],output=str(OUT))))
