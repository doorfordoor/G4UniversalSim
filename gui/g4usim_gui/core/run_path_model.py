"""Run/path edit actions over the existing workspace; no UI or filesystem state.

Loaded flat/settings differences are intentional. Projection is read-only;
only an explicit action synchronizes its legacy page group.
"""
from __future__ import annotations

import copy

from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, clone_snapshot
from g4usim_gui.models.package_model import PathSettings


PROJECT_FIELDS = {
    'project_name': 'projectName', 'run_input_mode': 'runInputMode',
    'executable': 'executable', 'workspace_root': 'workspaceRoot',
    'config_path': 'configPath', 'macro_path': 'macroPath',
    'output_dir': 'outputDir', 'runs_root': 'runsRoot',
    'threads': 'threads', 'seed': 'seed', 'run_name': 'runName',
}
CONFIG_FIELDS = ('run_name', 'threads', 'seed', 'beam_on', 'check_overlaps',
                 'dry_run', 'materials_config', 'geometry_config')
BINDINGS = frozenset(['project.' + key for key in PROJECT_FIELDS] +
                     ['config.' + key for key in CONFIG_FIELDS])
RAW_BINDINGS = frozenset(key + '.raw' for key in
                         ('project.threads', 'config.threads', 'config.beam_on'))
OWNED_BINDINGS = BINDINGS | RAW_BINDINGS
ASCII_SPACE = ' \t\r\n\v\f'


def run_path_projection(snapshot: WorkspaceSnapshot) -> dict:
    """Defaults follow the two old pages, without reconciling their values."""
    p = snapshot.project
    values = {'project.' + key: getattr(p, attr) for key, attr in PROJECT_FIELDS.items()}
    values['project.seed'] = str(p.seed) if p.seed else ''
    values['project.run_input_mode'] = p.runInputMode or 'generated'
    r = p.runSettings
    values.update({
        'config.run_name': r.run_name or p.runName or p.projectName,
        'config.threads': r.threads or p.threads or 1,
        'config.seed': '' if r.seed is None else str(r.seed),
        'config.beam_on': r.beam_on, 'config.check_overlaps': r.check_overlaps,
        'config.dry_run': r.dry_run,
        'config.materials_config': p.pathSettings.materials_config,
        'config.geometry_config': p.geometrySettings.config_path or p.pathSettings.geometry_config,
    })
    values.update({k: v for k, v in snapshot.state['drafts'].items() if k in OWNED_BINDINGS})
    return values


def _validate(binding, value):
    if binding not in OWNED_BINDINGS:
        raise ValueError(f'Unknown run/path binding: {binding}')
    if binding in ('project.threads', 'config.threads', 'config.beam_on'):
        minimum, maximum = (0, 2_000_000_000) if binding == 'config.beam_on' else (1, 1024)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f'Invalid integer for {binding}: {value!r}')
    elif binding in ('config.check_overlaps', 'config.dry_run'):
        if type(value) is not bool:
            raise ValueError(f'Expected boolean for {binding}')
    elif type(value) is not str:
        raise ValueError(f'Expected text for {binding}')
    if binding == 'project.run_input_mode' and value not in ('generated', 'external'):
        raise ValueError('Invalid run input mode')


def reduce_run_path(snapshot: WorkspaceSnapshot, binding: str, value) -> WorkspaceSnapshot:
    _validate(binding, value)
    result = clone_snapshot(snapshot)
    drafts = result.state['drafts']
    if binding in RAW_BINDINGS:
        drafts[binding] = value
    else:
        view = run_path_projection(result)
        view[binding] = value
        # An effective numeric edit supersedes its previous partial spelling.
        if binding + '.raw' in RAW_BINDINGS:
            view.pop(binding + '.raw', None)
            drafts.pop(binding + '.raw', None)
        p = result.project
        if binding.startswith('project.'):
            for key, attr in PROJECT_FIELDS.items():
                raw = view['project.' + key]
                if key == 'project_name':
                    converted = raw.strip() or 'demo'
                elif key == 'run_name':
                    converted = raw.strip(ASCII_SPACE)
                else:
                    converted = raw.strip() if isinstance(raw, str) else raw
                setattr(p, attr, converted)
            p.pathSettings.executable = p.executable
            p.pathSettings.workspace_root = p.workspaceRoot
            p.pathSettings.runs_root = p.runsRoot
            view['config.run_name'] = p.runName or p.projectName or 'gui_run'
            _mirror_number(view, 'config.threads', p.threads)
            view['config.seed'] = view['project.seed']
        r = p.runSettings
        r.run_name = view['config.run_name'].strip(ASCII_SPACE) or 'gui_run'
        r.threads = view['config.threads']
        text = view['config.seed'].strip()
        try:
            r.seed = int(text) if text else None
        except ValueError:
            r.seed = None
        r.beam_on = view['config.beam_on']
        r.check_overlaps = view['config.check_overlaps']
        r.dry_run = view['config.dry_run']
        if binding.startswith('config.'):
            p.pathSettings.materials_config = view['config.materials_config'].strip()
            p.pathSettings.geometry_config = view['config.geometry_config'].strip()
            p.geometrySettings.config_path = p.pathSettings.geometry_config
            p.runName, p.threads, p.seed = r.run_name, r.threads, text
            # The old Configuration slot projects the entire Project page.
            for key, attr in PROJECT_FIELDS.items():
                target = 'project.' + key
                if key == 'threads':
                    _mirror_number(view, target, getattr(p, attr))
                else:
                    view[target] = getattr(p, attr)
            view['project.seed'] = view['config.seed']
        # Replace only this domain, leaving source/table/selection ownership intact.
        for key in OWNED_BINDINGS:
            drafts.pop(key, None)
        drafts.update(view)
    result.project.editingState = copy.deepcopy(result.state)
    return result


def _mirror_number(view, binding, value):
    # Legacy setValue regenerates the nonactive mirror even for the same value.
    # Omission requests locale formatting by the reader, not a copied raw string.
    view.pop(binding + '.raw', None)
    view[binding] = value


def copy_run_path(target, source):
    """Compatibility adapter for not-yet-migrated capture/reader consumers."""
    for attr in PROJECT_FIELDS.values():
        setattr(target, attr, copy.deepcopy(getattr(source, attr)))
    target.runSettings = copy.deepcopy(source.runSettings)
    target.pathSettings = copy.deepcopy(source.pathSettings)
    target.geometrySettings.config_path = source.geometrySettings.config_path


def path_settings(project) -> PathSettings:
    """Action-local fallback only; never writes runs_root into the editor."""
    return PathSettings(executable=project.executable, workspace_root=project.workspaceRoot,
                        runs_root=project.runsRoot or project.outputDir,
                        materials_config=project.pathSettings.materials_config,
                        geometry_config=project.pathSettings.geometry_config)
