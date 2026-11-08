"""Finite SPS actions on WorkspaceSnapshot; no widget, IO or random identity owner."""
from __future__ import annotations
import copy
import hashlib
import json
from dataclasses import asdict, fields
from g4usim_gui.core.edit_snapshot import clone_snapshot
from g4usim_gui.core.edit_transactions import TransactionConflict
from g4usim_gui.core.run_editor_model import GPSDefinition, RegionDefinition, FieldDefinition, BiasRuleDefinition

SCALARS = {'config.source_editor_preset': ('sourceEditor', 'preset', 'text', 'advanced'),
 'config.source_editor_particle': ('sourceEditor', 'particle', 'text', 'advanced'),
 'config.source_editor_energy': ('sourceEditor', 'energy', 'text', 'advanced'),
 'config.source_editor_position_type': ('sourceEditor', 'position_mode', 'text', 'advanced'),
 'config.source_editor_shape': ('sourceEditor', 'source_shape', 'text', 'advanced'),
 'config.source_editor_position': ('sourceEditor', 'position', 'text', 'advanced'),
 'config.source_editor_radius': ('sourceEditor', 'radius', 'text', 'advanced'),
 'config.source_editor_inner_radius': ('sourceEditor', 'inner_radius', 'text', 'advanced'),
 'config.source_editor_halfx': ('sourceEditor', 'halfx', 'text', 'advanced'),
 'config.source_editor_halfy': ('sourceEditor', 'halfy', 'text', 'advanced'),
 'config.source_editor_normal': ('sourceEditor', 'normal', 'text', 'advanced'),
 'config.source_editor_confine_volume': ('sourceEditor', 'confine_volume', 'text', 'advanced'),
 'config.source_editor_direction': ('sourceEditor', 'direction', 'text', 'advanced'),
 'config.source_editor_angular_mode': ('sourceEditor', 'angular_mode', 'text', 'advanced'),
 'config.source_editor_theta_min': ('sourceEditor', 'theta_min', 'text', 'advanced'),
 'config.source_editor_theta_max': ('sourceEditor', 'theta_max', 'text', 'advanced'),
 'config.source_editor_phi_min': ('sourceEditor', 'phi_min', 'text', 'advanced'),
 'config.source_editor_phi_max': ('sourceEditor', 'phi_max', 'text', 'advanced'),
 'config.source_editor_cone_half_angle': ('sourceEditor', 'cone_half_angle', 'text', 'advanced'),
 'config.source_editor_focus_point': ('sourceEditor', 'focus_point', 'text', 'advanced'),
 'config.source_editor_preview_rays': ('sourceEditor', 'preview_ray_count', 'int', 'advanced'),
 'config.source_editor_preview_seed': ('sourceEditor', 'random_seed_preview', 'int', 'advanced'),
 'config.physics_editor_mode': ('physicsEditor', 'mode', 'text', 'advanced'),
 'config.physics_editor_reference': ('physicsEditor', 'reference_list', 'text', 'advanced'),
 'config.physics_editor_default_cut': ('physicsEditor', 'default_cut', 'text', 'advanced'),
 'config.physics_editor_biasing': ('physicsEditor', 'enable_biasing_physics', 'bool', 'advanced'),
 'config.scoring_editor_enabled': ('scoringEditor', 'enabled', 'bool', 'advanced'),
 'config.scoring_editor_hits': ('scoringEditor', 'hits', 'bool', 'advanced'),
 'config.scoring_editor_event_edep': ('scoringEditor', 'event_edep', 'bool', 'advanced'),
 'config.scoring_editor_edep': ('scoringEditor', 'edep', 'bool', 'advanced'),
 'config.scoring_editor_dose': ('scoringEditor', 'dose', 'bool', 'advanced'),
 'config.scoring_editor_fluence': ('scoringEditor', 'fluence', 'bool', 'advanced'),
 'config.scoring_editor_trajectories': ('scoringEditor', 'trajectory_events', 'int', 'advanced'),
 'config.scoring_editor_raw_hist': ('scoringEditor', 'raw_histogram', 'bool', 'advanced'),
 'config.scoring_editor_weighted_hist': ('scoringEditor', 'weighted_histogram', 'bool', 'advanced'),
 'config.scoring_editor_bins': ('scoringEditor', 'hist_bins', 'int', 'advanced'),
 'config.scoring_editor_min': ('scoringEditor', 'hist_min', 'text', 'advanced'),
 'config.scoring_editor_max': ('scoringEditor', 'hist_max', 'text', 'advanced'),
 'config.scoring_editor_volume_summary': ('scoringEditor', 'volume_summary', 'bool', 'advanced'),
 'config.scoring_editor_particle_summary': ('scoringEditor', 'particle_summary', 'bool', 'advanced'),
 'config.scoring_editor_auto_create': ('scoringEditor', 'auto_create_default_scorers', 'bool', 'advanced'),
 'config.source_preset': ('sourceEditor', 'preset', 'text', 'quick'),
 'config.source_particle': ('sourceEditor', 'particle', 'text', 'quick'),
 'config.source_energy': ('sourceEditor', 'energy', 'text', 'quick'),
 'config.source_position': ('sourceEditor', 'position', 'text', 'quick'),
 'config.source_direction': ('sourceEditor', 'direction', 'text', 'quick'),
 'config.physics_reference': ('physicsEditor', 'reference_list', 'text', 'quick'),
 'config.default_cut': ('physicsEditor', 'default_cut', 'text', 'quick'),
 'config.enable_biasing': ('physicsEditor', 'enable_biasing_physics', 'bool', 'quick'),
 'config.scoring_enabled': ('scoringEditor', 'enabled', 'bool', 'quick'),
 'config.scoring_hits': ('scoringEditor', 'hits', 'bool', 'quick'),
 'config.scoring_event_edep': ('scoringEditor', 'event_edep', 'bool', 'quick'),
 'config.scoring_edep': ('scoringEditor', 'edep', 'bool', 'quick'),
 'config.hist_bins': ('scoringEditor', 'hist_bins', 'int', 'quick'),
 'config.hist_min': ('scoringEditor', 'hist_min', 'text', 'quick'),
 'config.hist_max': ('scoringEditor', 'hist_max', 'text', 'quick')}
RANGES = {'config.source_editor_preview_rays': (1,512), 'config.source_editor_preview_seed': (0,2147483647),
          'config.scoring_editor_trajectories': (0,1000), 'config.scoring_editor_bins': (0,10000000),
          'config.hist_bins': (1,10000000)}
for scorer in ('dose','fluence','let'):
    for key in ('enabled','particles','energy_min','energy_max'):
        SCALARS[f'config.scoring_filter.{scorer}.{key}'] = ('volume_filters', scorer+'.'+key, 'bool' if key=='enabled' else 'text', 'advanced')
for scorer in ('dose','fluence'):
    for key in ('enabled','bins','min','max'):
        name = f'config.scoring_spectrum.{scorer}.{key}'
        SCALARS[name] = ('volume_spectra', scorer+'.'+key, 'bool' if key=='enabled' else 'int' if key=='bins' else 'text', 'advanced')
        if key=='bins': RANGES[name] = (1,1000000)
BINDINGS = frozenset(SCALARS)
RAW_BINDINGS = frozenset(key+'.raw' for key in RANGES)
OWNED_BINDINGS = BINDINGS | RAW_BINDINGS
EDITORS = ('sourceEditor','physicsEditor','scoringEditor')
SETTINGS = ('sourceSettings','physicsSettings','scoringSettings')
COLLECTIONS = {'gps_sources': ('sourceEditor',GPSDefinition), 'regions': ('physicsEditor',RegionDefinition),
               'fields': ('physicsEditor',FieldDefinition), 'bias_rules': ('physicsEditor',BiasRuleDefinition)}
MODULES = ('extra_modules','replace_modules','manual_modules')


def copy_sps(target, source):
    for name in EDITORS + SETTINGS:
        setattr(target, name, copy.deepcopy(getattr(source, name)))


def _value(project, owner, field):
    if owner in ('volume_filters','volume_spectra'):
        scorer,key = field.split('.')
        defaults = {'enabled':False,'particles':'','energy_min':'','energy_max':'','bins':10,'min':'0 MeV','max':'10 MeV'}
        return getattr(project.scoringEditor,owner).get(scorer,{}).get(key,defaults[key])
    return getattr(getattr(project,owner),field)


def sps_projection(snapshot):
    values = {}
    for key,(owner,field,kind,group) in SCALARS.items():
        value = _value(snapshot.project,owner,field)
        if kind=='int':
            try: value=int(value)
            except (ValueError,TypeError): value=10 if owner=='volume_spectra' else RANGES[key][0]
            value=max(RANGES[key][0],min(RANGES[key][1],value))
        elif kind=='bool': value=bool(value)
        else: value=str(value)
        values[key] = value
    values.update({k:v for k,v in snapshot.state['drafts'].items() if k in OWNED_BINDINGS})
    return values


def _set(project,key,value):
    owner,field,kind,_=SCALARS[key]
    if kind=='text':
        if type(value) is not str: raise TypeError('SPS text action requires text: '+key)
        value=value.strip()
    elif kind=='bool':
        if type(value) is not bool: raise TypeError('SPS boolean action requires bool: '+key)
    elif type(value) is not int or not RANGES[key][0]<=value<=RANGES[key][1]:
        raise ValueError('SPS numeric action outside control range: '+key)
    if owner in ('volume_filters','volume_spectra'):
        scorer,field=field.split('.')
        getattr(project.scoringEditor,owner).setdefault(scorer,{})[field]=value
    else:
        setattr(getattr(project,owner),field,value)
        if owner=='sourceEditor' and field=='position_mode': project.sourceEditor.position_type=value


def _settings(project):
    for editor,settings in zip(EDITORS,SETTINGS):
        setattr(project,settings,getattr(project,editor).to_settings())


def reduce_sps(snapshot, binding, value):
    result=clone_snapshot(snapshot)
    drafts=result.state['drafts']
    if binding in RAW_BINDINGS:
        if type(value) is not str: raise TypeError('Numeric raw draft requires text')
        drafts[binding[:-4]]=sps_projection(result)[binding[:-4]]
        drafts[binding]=value
        return result
    if binding not in SCALARS: raise ValueError('Unknown SPS binding: '+binding)
    group=SCALARS[binding][3]
    values=sps_projection(result); values[binding]=value
    for key,spec in SCALARS.items():
        if spec[3]==group:
            _set(result.project,key,values[key])
            drafts[key]=values[key]
    for owner in EDITORS: getattr(result.project,owner).is_dirty=True
    _settings(result.project)
    # The old quick slot repopulates both groups; advanced only mirrors quick.
    reset=OWNED_BINDINGS if group=='quick' else {k for k in OWNED_BINDINGS if SCALARS.get(k.removesuffix('.raw'),(None,None,None,None))[3]=='quick'}
    for key in reset: drafts.pop(key,None)
    drafts[binding]=value
    return result


def row_digest(row):
    return hashlib.sha256(json.dumps(asdict(row),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def row_reference(snapshot,collection,index,revision):
    owner,_=COLLECTIONS[collection]; row=getattr(getattr(snapshot.project,owner),collection)[index]
    return {'revision':revision,'collection':collection,'index':index,'digest':row_digest(row),
            'editor_id':row.editor_id if collection=='gps_sources' else None}


def reduce_sps_structure(snapshot, action, *, revision):
    """Explicit bounded actions; IDs are supplied by the caller, never generated here."""
    if action.get('revision') != revision: raise TransactionConflict('SPS action revision changed')
    result=clone_snapshot(snapshot); p=result.project; kind=action['kind']; key=action['key']
    if kind=='top':
        owner,field=key.split('.',1)
        if (owner,field) not in {('source','multiple_vertex'),('source','phase_space_file'),('source','phase_space_recycle')}:
            raise ValueError('Unknown SPS top-level action')
        value=action['value']; expected=str if field=='phase_space_file' else bool
        if type(value) is not expected: raise TypeError('Invalid top-level value')
        setattr(p.sourceEditor,field,value); p.sourceEditor.is_dirty=True
    elif kind=='cut':
        if key not in ('gamma','e-','e+','proton') or type(action['value']) is not str: raise ValueError('Invalid cut action')
        if action['value']: p.physicsEditor.particle_cuts[key]=action['value']
        else: p.physicsEditor.particle_cuts.pop(key,None)
        p.physicsEditor.is_dirty=True
    elif kind=='module':
        if key not in MODULES: raise ValueError('Unknown module list')
        rows=getattr(p.physicsEditor,key)
        if action['op']=='add':
            if type(action['value']) is not str: raise TypeError('Module must be text')
            rows.append(action['value'])
        elif action['op']=='remove' and type(action['index']) is int and 0<=action['index']<len(rows): rows.pop(action['index'])
        else: raise ValueError('Invalid module operation')
        p.physicsEditor.is_dirty=True
    elif kind=='row':
        if key not in COLLECTIONS: raise ValueError('Unknown row collection')
        owner,cls=COLLECTIONS[key]; model=getattr(p,owner); rows=getattr(model,key); op=action['op']; index=action.get('index',-1)
        if op!='add':
            ref=action['reference']
            if ref['revision']!=revision or ref['collection']!=key or ref['index']!=index or not 0<=index<len(rows): raise TransactionConflict('Stale SPS row reference')
            if ref['digest']!=row_digest(rows[index]) or (key=='gps_sources' and ref['editor_id']!=rows[index].editor_id): raise TransactionConflict('SPS row identity changed')
        if op=='set':
            field=action['field']; value=action['value']
            if field=='editor_id' or field not in {f.name for f in fields(cls)}: raise ValueError('Unknown/immutable row field')
            if type(value) is not type(getattr(rows[index],field)): raise TypeError('Invalid row value type')
            setattr(rows[index],field,value)
        elif op in ('add','duplicate'):
            row=copy.deepcopy(rows[index]) if op=='duplicate' else (cls(editor_id=action['new_id']) if key=='gps_sources' else cls())
            if key=='gps_sources':
                identity=action['new_id']
                if type(identity) is not str or not identity or any(r.editor_id==identity for r in rows): raise ValueError('GPS ID must be fresh')
                row.editor_id=identity
            if hasattr(row,'name') and cls is not BiasRuleDefinition:
                used={r.name.lower() for r in rows}; base=row.name or ('local' if rows else ''); name,count=base,2
                while name.lower() in used: name,count=(base or 'local')+str(count),count+1
                row.name=name
            rows.append(row); index=len(rows)-1
        elif op=='remove':
            rows.pop(index); index=min(index,len(rows)-1)
        elif op=='move':
            target=action['target']
            if type(target) is not int or not 0<=target<len(rows) or abs(target-index)!=1: raise ValueError('Invalid row move')
            rows[index],rows[target]=rows[target],rows[index]; index=target
        else: raise ValueError('Unknown row operation')
        result.state['selections'][f'j2.{key}.selection']=index
        model.is_dirty=True
    else: raise ValueError('Unknown SPS structural action')
    _settings(p)
    return result
