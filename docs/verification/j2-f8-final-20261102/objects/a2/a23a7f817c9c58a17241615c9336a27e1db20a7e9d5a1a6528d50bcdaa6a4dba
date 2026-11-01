from pathlib import Path
import hashlib,json,re,datetime

out=Path(__file__).resolve().parent
root=out.parents[3]
before=json.loads((out/'source-before.json').read_text(encoding='utf-8-sig'))
after={'gui149':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in before['gui149']},
       'test_sha256':hashlib.sha256((root/'gui/smoke_tests/smoke_f8_accessibility.py').read_bytes()).hexdigest(),
       'probe_sha256':hashlib.sha256((root/'tools/test_assert_probe.py').read_bytes()).hexdigest()}
assert before==after,'Product/test/probe bytes changed during tests'
(out/'source-after.json').write_text(json.dumps(after,indent=2)+'\n',encoding='utf-8')
runs=[]
for suffix,scale,session in [('125','1.25',38339),('150','1.5',27515)]:
    status=json.loads((out/f'scale{suffix}-exit.json').read_text(encoding='utf-8-sig'))
    raw=(out/f'scale{suffix}.log').read_bytes()
    encoding='utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
    log=raw.decode(encoding)
    markers=re.findall(r'^G4USIM_ASSERTS=(\d+)\s*$',log,re.M)
    assert len(markers)==1,(suffix,markers)
    count=int(markers[0])
    assert status['exit_code']==0 and count>=595,(suffix,status,count)
    assert 'F8 keyboard/start/environment/wizard/layout offscreen checks passed' in log
    assert f'F8 window DPR: {scale}' in log,(suffix,'DPR mismatch')
    artifacts=[{'path':p.relative_to(out).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size} for p in sorted((out/f'scale{suffix}').rglob('*')) if p.is_file()]
    runs.append(dict(scale=scale,qt_platform='offscreen',command=['D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe','-B','tools/test_assert_probe.py','gui/smoke_tests/smoke_f8_accessibility.py','--output',f'out/collab/j2-f8-fourth-repair-applied/f8/scale{suffix}'],exit_code=status['exit_code'],assertions_v3=count,log=f'scale{suffix}.log',log_raw_sha256=hashlib.sha256(raw).hexdigest(),log_encoding=encoding,exec_session=session,exec_session_completion='polled process exit0',finished_utc=status['finished_utc'],artifacts=artifacts))
receipt=dict(scope='actual tracked permanent F8 under original v3 probe; no outloader or external monkeypatch; offscreen only; not formal/native/backend acceptance',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_before_equals_after=True,test_sha256=after['test_sha256'],gui149_unchanged=True,gui149_count=len(after['gui149']),processes_all_finished=True,runs=runs)
(out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
readme='''# Actual tracked F8第四修复应用后专项

实际工作树原永久入口、原v3 probe，D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe，Qt offscreen；125/150各执行一次，各独立--output。无OUT loader、无外部monkeypatch、未改tracked。测试原有受控fixture保留，不声称全部为自然路径。

运行前后F8 SHA均5f234e69c00d602039cb8f2ebc7daadb4f69edc860e6010989628d06253b3814，149 GUI产品逐字节与tests-apply-receipt一致；原probe SHA也不变。source-before/after.json、runtime.json、两原日志、独立输出及receipt.json保留。

'''
for run in runs:
    readme+=f"- {run['scale']}: exit0，v3 {run['assertions_v3']}，原session {run['exec_session']}已实际poll终态；log SHA {run['log_raw_sha256']}。\n"
readme+='\n两个测试进程均已结束，无待poll会话；没有formal/native/backend/build执行或阶段状态判定。595是此前with-output入口基线，增加的provider/真实Label关系及丢buddy负向产生新计数，不降低旧判据。新增截图仅offscreen测试产物，未冒称本任务独立目视验收。\n'
(out/'README.md').write_text(readme,encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k!='runs'},ensure_ascii=False))
print(json.dumps([{'scale':r['scale'],'exit_code':r['exit_code'],'assertions_v3':r['assertions_v3'],'session':r['exec_session']} for r in runs]))
