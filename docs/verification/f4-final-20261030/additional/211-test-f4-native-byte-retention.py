"""F4 native raw streams retained only in explicitly selected native categories."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_retention',Path(__file__).with_name('prepare-f4-archive.py'))
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
work=Path(tempfile.mkdtemp(prefix='f4-native-retention-selfcheck-',dir=ROOT/'out/collab'))
native=work/'native-copy'
native.mkdir()
source=ROOT/'out/verification/f4-visible-7d718d0'
names=('events.jsonl','backend-capabilities.stdout','backend-capabilities.stderr','inspect.stderr')
for name in names:
    shutil.copyfile(source/name,native/name)
(native/'crlf.stderr').write_bytes('原始CRLF测试\r\n第二行\r\n'.encode('utf-8'))
readme=work/'README.md'
readme.write_text('# Helper test only\nNo F4 acceptance or docs publication.\n',encoding='utf-8')
review=work/'review.md'
review.write_text('Test fixture, not acceptance.\n',encoding='utf-8')
additional=work/'same-stream.stderr'
shutil.copyfile(native/'events.jsonl',additional)
args=SimpleNamespace(destination=work/'f4-not-published',ci_receipt=ROOT/'out/verification/f1-gdml-ci/ci-evidence.json',
    windows_report=helper.BASELINE,baseline_report=helper.BASELINE,expected_head='f176d0ed4cea60b7ca5a80ed81017c9404ec1257',
    readme=readme,build_root=[],visible_root=[],review_file=[review],include_file=[additional],
    deepseek_response=None,deepseek_receipt=None,historical_visible_root=[native])
plan=helper.make_plan(args)
assert not plan['preflight_blockers']
selected=[row for row in plan['files'] if row['category']=='historical_visible']
assert len(selected)==5
assert {Path(row['archive_path']).name for row in selected}==set(names)|{'crlf.stderr'}
assert all(Path(row['source']).read_bytes()==(native/Path(row['archive_path']).name).read_bytes() for row in selected)
assert any(row['source']==str(additional) for row in plan['excluded'])
assert not any(row['source']==str(additional) for row in plan['files'])
assert '.jsonl' not in helper.engine.TEXT_SUFFIXES and '.stderr' not in helper.engine.TEXT_SUFFIXES
reviewed=helper.engine.review_plan(plan)
assert reviewed['status']=='review_passed_not_published' and not args.destination.exists()
original=(native/'events.jsonl').read_bytes()
(native/'events.jsonl').write_bytes(original+b'\n')
rejected=helper.engine.review_plan(plan)
assert rejected['status']=='blocked_plan_review'
assert any('Planned source changed' in reason for reason in rejected['blockers'])
(native/'events.jsonl').write_bytes(original)
assert all((source/name).read_bytes()==(native/name).read_bytes() for name in names)
helper.write_out(work/'checks.json',{'status':'passed','native_source':str(source),
    'selected_original_names':list(names),'raw_streams_in_plan':selected,
    'temporary_copy_gates_passed':True,'crlf_raw_bytes_preserved':True,
    'non_native_category_still_excluded':True,'changed_copy_rejected':True,
    'original_native_sources_unchanged':True,'formal_docs_published':False,'phase_acceptance':False})
print(json.dumps({'status':'passed','receipt':str(work/'checks.json'),'raw_files':len(selected)}))
