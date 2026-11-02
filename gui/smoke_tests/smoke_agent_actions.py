"""L1 explicit write surface and model-input rejection; no model/network/backend."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gui'))

from g4usim_gui.agent.actions import (
    SCHEMA, PlanError, build_candidate, enforce_scope, parse_plan, planner_messages, planning_context, requires_review,
)
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_fingerprint
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core import wizard


def fixture():
    project = G4USimProject()
    wizard.apply_to_project(project, wizard.build(wizard.default_spec('single_target')))
    project.runSettings.beam_on = 100
    return WorkspaceSnapshot(project)


def plan(snapshot, changes=None):
    return {'schema': SCHEMA, 'base_fingerprint': snapshot_fingerprint(snapshot),
            'summary': 'bounded test', 'clarifications': [], 'changes': changes or []}


def rejected(callback, reason):
    try:
        callback()
    except PlanError as error:
        assert str(error) == reason, str(error)
    else:
        assert False, 'Expected rejection: ' + reason


def main():
    snapshot = fixture()
    original = snapshot_fingerprint(snapshot)
    target = next(r.name for r in snapshot.project.geometryEditor.volumes if r.sensitive)
    changes = [dict(domain='volume', target=target, field='material', value='G4_Si'),
               dict(domain='source', target='source', field='particle', value='e-'),
               dict(domain='source', target='source', field='energy', value='1 GeV'),
               dict(domain='run', target='', field='beam_on', value=4)]
    data = plan(snapshot, changes)
    accepted = parse_plan(json.dumps(data), snapshot)
    candidate = build_candidate(snapshot, accepted)
    assert candidate.project.sourceEditor.particle == 'e-'
    assert candidate.project.sourceEditor.energy == '1 GeV'
    assert candidate.project.runSettings.beam_on == 4
    assert next(r for r in candidate.project.geometryEditor.volumes if r.name == target).material == 'G4_Si'
    assert snapshot_fingerprint(snapshot) == original
    assert not requires_review(accepted)
    enforce_scope(accepted, [dict(domain='volume', target=target, fields=['material']),
                             dict(domain='source', target='source', fields=['particle', 'energy']),
                             dict(domain='run', target='', fields=['beam_on'])])
    rejected(lambda: enforce_scope(accepted, [dict(domain='source', target='source', fields=['energy'])]),
             'agent.change_outside_authorization')
    snapshot.state['drafts'].update({'config.beam_on': 100, 'config.beam_on.raw': '100'})
    spin_plan = plan(snapshot, [dict(domain='run', target='', field='beam_on', value=4)])
    spin_candidate = build_candidate(snapshot, spin_plan)
    assert spin_candidate.state['drafts']['config.beam_on.raw'] == '4'
    assert snapshot.state['drafts']['config.beam_on.raw'] == '100'
    snapshot.state['drafts'].clear()
    physical = plan(snapshot, [dict(domain='physics', target='', field='reference_list', value='FTFP_BERT')])
    assert requires_review(parse_plan(json.dumps(physical), snapshot))
    context = planning_context(snapshot)
    assert context['max_events'] == 100
    assert 'executable' not in json.dumps(context)
    assert 'workspaceRoot' not in json.dumps(context)
    assert len(planner_messages('Use this configuration', snapshot)) == 2
    for domain, field in [('run', 'executable'), ('source', '__class__'), ('process', 'command')]:
        bad = plan(snapshot, [dict(domain=domain, target='', field=field, value='do something')])
        rejected(lambda: parse_plan(json.dumps(bad), snapshot), 'agent.change_not_allowed')
        rejected(lambda: build_candidate(snapshot, bad), 'agent.change_not_allowed')
    for field, value in [('beam_on', 101), ('beam_on', 0), ('threads', 65), ('seed', -1)]:
        bad = plan(snapshot, [dict(domain='run', target='', field=field, value=value)])
        rejected(lambda: parse_plan(json.dumps(bad), snapshot), 'agent.run_budget')
    for value in [True, '4', 4.0]:
        bad = plan(snapshot, [dict(domain='run', target='', field='beam_on', value=value)])
        rejected(lambda: parse_plan(json.dumps(bad), snapshot), 'agent.change_value_type')
    bad = plan(snapshot, [changes[0], changes[0]])
    rejected(lambda: parse_plan(json.dumps(bad), snapshot), 'agent.duplicate_change')
    bad = plan(snapshot)
    bad['base_fingerprint'] = '0' * 64
    rejected(lambda: parse_plan(json.dumps(bad), snapshot), 'agent.plan_stale')
    bad = plan(snapshot, [dict(domain='volume', target='guess', field='material', value='G4_Si')])
    rejected(lambda: parse_plan(json.dumps(bad), snapshot), 'agent.volume_target_ambiguous')
    bad = plan(snapshot)
    bad['shell'] = 'never execute'
    rejected(lambda: parse_plan(json.dumps(bad), snapshot), 'agent.plan_fields')
    raw = json.dumps(plan(snapshot))
    rejected(lambda: parse_plan(raw[:-1] + ',"schema":"duplicate"}', snapshot), 'agent.plan_json_invalid')
    bad = plan(snapshot)
    bad['clarifications'] = ['Which target?']
    assert parse_plan(json.dumps(bad), snapshot)['clarifications']
    rejected(lambda: build_candidate(snapshot, bad), 'agent.clarification_required')
    external = copy.deepcopy(snapshot)
    external.project.runInputMode = 'external'
    rejected(lambda: planning_context(external), 'agent.generated_input_required')
    advanced = fixture()
    advanced.project.sourceEditor.angular_mode = 'isotropic'
    bad = plan(advanced, [dict(domain='source', target='source', field='energy', value='2 MeV')])
    rejected(lambda: build_candidate(advanced, bad), 'agent.source_distribution_requires_manual_editor')
    copied = fixture()
    copied.project.geometryEditor.source_copy_mode = True
    bad = plan(copied, [dict(domain='volume', target=target, field='material', value='G4_Al')])
    assert planning_context(copied)['geometry_source_copy_mode'] is True
    rejected(lambda: build_candidate(copied, bad), 'agent.original_geometry_copy_is_read_only')
    excessive = fixture()
    excessive.project.runSettings.threads = 65
    rejected(lambda: build_candidate(excessive, plan(excessive)), 'agent.thread_budget')
    print('L1 action boundary passed')


if __name__ == '__main__':
    main()
