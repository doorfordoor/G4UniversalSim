"""F4 pure diagnostic identity, provenance and serialization contracts."""
from dataclasses import dataclass, field, replace
import copy
import hashlib
import json
import os
import operator
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gui'))
from g4usim_gui.core.diagnostics import (
    Diagnostic, EditorLocation, SourceLocation, collect_diagnostics,
    complete_diagnostics, diagnostics_from_dict, diagnostics_from_json,
    diagnostics_to_dict, emit_diagnostic, extend_diagnostics, reset_diagnostics,
    semantic_snapshot, source_location,
)


def rejects(action):
    rejected = False
    try:
        action()
    except (ValueError, TypeError):
        rejected = True
    assert rejected, 'Invalid diagnostic was accepted'


@dataclass
class Owner:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


def main():
    target = EditorLocation('geometry', 'material', 'volumes', 1, 'A|B')
    params = {'particle': 'e-', 'nested': [{'value': 3}]}
    issue = Diagnostic('geometry.material.missing', 'error', 'geometry.editor', 'Missing material',
                       target, params=params, identity_parameters={'material': 'A|B'})
    identity = issue.identity
    translated = replace(issue, message='缺少材料', message_key='Missing material', params={'display': '中文'})
    assert translated.identity == identity
    assert replace(issue, location=replace(target, snapshot_id='new-revision')).identity == identity
    facts = [replace(issue, severity='warning'), replace(issue, origin='materials.source'),
             replace(issue, location=replace(target, field='shape')),
             replace(issue, location=replace(target, row=2)),
             replace(issue, location=replace(target, entity='B|A')),
             replace(issue, identity_parameters={'material': 'other'})]
    assert len({identity, *(item.identity for item in facts)}) == len(facts) + 1
    a = replace(issue, location=EditorLocation('a|b', 'c'))
    b = replace(issue, location=EditorLocation('a', 'b|c'))
    assert a.identity != b.identity
    assert issue.params['nested'][0]['value'] == 3
    params['nested'][0]['value'] = 9
    assert issue.params['nested'][0]['value'] == 3 and issue.identity == identity
    rejects(lambda: operator.setitem(issue.params, 'particle', 'proton'))
    rejects(lambda: operator.setitem(issue.params['nested'][0], 'value', 5))
    rejects(lambda: operator.setitem(issue.identity_parameters, 'material', 'other'))
    assert copy.deepcopy(issue) is issue

    relative = replace(issue, source=SourceLocation('relative.ini', 1))
    before = relative.identity
    cwd = Path.cwd()
    try:
        os.chdir(ROOT / 'gui')
        assert relative.identity == before
    finally:
        os.chdir(cwd)
    text = '[材料]\n密度 = bad\n'
    source = source_location('old-input.ini', text, line=2, section='材料', key='密度', value='bad')
    assert source.text_sha256 == hashlib.sha256(text.encode('utf-8')).hexdigest()
    assert source.text_snapshot == text and Path(source.filename).is_absolute()
    assert source.line == 2
    rejects(lambda: replace(source, text_snapshot=text+'changed'))
    rejects(lambda: SourceLocation('file.ini', 0))
    rejects(lambda: SourceLocation('file.ini', True))
    rejects(lambda: EditorLocation('geometry', 'name', row=1))
    rejects(lambda: EditorLocation('geometry', 'name', 'volumes', -1))
    rejects(lambda: EditorLocation('geometry', 'name', 'volumes', False))
    rejects(lambda: Diagnostic('missing','error','test','No location'))
    rejects(lambda: replace(issue, params={'value':float('nan')}))
    rejects(lambda: replace(issue, params={'value':object()}))
    rejects(lambda: replace(issue, severity=[]))

    owner=Owner()
    reset_diagnostics(owner)
    emit_diagnostic(owner,'run.seed.invalid','error','Bad seed',origin='run',editor='run',field='seed')
    emit_diagnostic(owner,'run.seed.invalid','error','Bad seed',origin='run',editor='run',field='seed')
    assert owner.errors == ['Bad seed'] and len(collect_diagnostics(owner)) == 1
    emit_diagnostic(owner,'run.name.default','warning','Default name',origin='run',editor='run',field='run_name')
    assert owner.warnings == ['Default name']
    other=Owner()
    extend_diagnostics(other, collect_diagnostics(owner), prefix='Run: ')
    assert other.errors == ['Run: Bad seed'] and other.warnings == ['Run: Default name']
    assert [d.identity for d in collect_diagnostics(other)] == [d.identity for d in collect_diagnostics(owner)]
    other.errors.extend(['Opaque error','Opaque error'])
    records=complete_diagnostics(other)
    assert len(records) == 4 and len({d.identity for d in records}) == 4
    assert [d.unavailable_reason for d in records[-2:]] == ['legacy_unstructured'] * 2
    assert all(d.location is None and d.raw_message=='Opaque error' for d in records[-2:])
    payload=diagnostics_to_dict(records,snapshot_id='snapshot-A',channels={
        'errors':other.errors,'warnings':other.warnings,'info':other.info})
    loaded=diagnostics_from_json(json.dumps(payload,ensure_ascii=False))
    assert loaded.errors == tuple(other.errors) and loaded.warnings == tuple(other.warnings)
    assert loaded.snapshot_id == 'snapshot-A' and not loaded.can_run
    assert [d.identity for d in loaded.diagnostics] == [d.identity for d in records]
    source_payload=diagnostics_to_dict([replace(issue,source=source)])
    assert diagnostics_from_dict(source_payload).diagnostics[0].source == source
    assert semantic_snapshot({'b':2,'a':1}) == semantic_snapshot({'a':1,'b':2})
    assert semantic_snapshot({'a':None}) != semantic_snapshot({})
    for mutate in (
        lambda p:p.update(schema='unknown'), lambda p:p.update(can_run=True),
        lambda p:p.update(extra=True), lambda p:p['diagnostics'].append(copy.deepcopy(p['diagnostics'][0])),
        lambda p:p['diagnostics'][0].update(identity='0'*64),
        lambda p:p['diagnostics'][0].update(params=None),
        lambda p:p['diagnostics'][0]['location'].update(row=True,collection='rows'),
        lambda p:p['errors'].append('not in records'),
    ):
        broken=copy.deepcopy(payload);mutate(broken)
        rejects(lambda:diagnostics_from_dict(broken))
    rejects(lambda:diagnostics_from_json('{"schema":"first","schema":"second"}'))
    rejects(lambda:diagnostics_from_json('{"number":NaN}'))
    reset_diagnostics(owner)
    assert collect_diagnostics(owner)==()
    print('F4 diagnostic identity, legacy projection, immutable facts and JSON contracts passed')


if __name__ == '__main__':
    main()
