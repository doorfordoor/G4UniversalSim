"""Finite document edits on the existing workspace snapshot; no widgets or IO."""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass

from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, clone_snapshot
from g4usim_gui.core.edit_transactions import TransactionConflict
from g4usim_gui.editors.material_editor_model import (
    MaterialDocument, add_default_row, duplicate_row, delete_row, parse_components_text,
)
from g4usim_gui.editors.geometry_editor_model import (
    HierarchicalVolumeRow, BooleanOperationRow, LayerRow, set_geometry_mode,
    HIERARCHICAL_GEOMETRY_MODES, EDITABLE_GEOMETRY_MODES,
)
from g4usim_gui.core.solid_registry_data import SOLIDS, canonical_solid
from g4usim_gui.parsers.geometry_parser import PLACEMENT_PROPERTY_KEYS

TABLES = {'volume': 'geometry_table', 'boolean': 'boolean_table', 'layer': 'layer_table',
          'material': 'materials_table'}
SIMPLE_FIELDS = ('world_size', 'world_material', 'target_name', 'target_shape', 'target_size',
                 'target_material', 'target_position', 'target_rotation', 'target_sensitive',
                 'target_bias', 'target_region')
LAYERED_FIELDS = ('world_size', 'world_material', 'axis', 'gap', 'z_start', 'auto_stack')
DOCUMENT_BINDINGS = ({'config.simple_' + field for field in SIMPLE_FIELDS}
                     | {'config.layered_' + field for field in LAYERED_FIELDS}
                     | {'config.geometry_template', 'config.geometry_source_copy'})


def is_document_draft(binding):
    return binding in DOCUMENT_BINDINGS or binding.startswith(('detail.material.', 'detail.layer.'))


def table_values(snapshot, collection):
    if collection == 'volume':
        return [[v.enabled, v.name, v.parent, v.shape, v.material, v.position,
                 v.parameters if v.shape.strip().lower() != 'box' and v.parameters else v.size,
                 v.rotation, v.sensitive, v.bias, v.region,
                 *(v.shape_properties.get(k, '') for k in ('dx1','dx2','dy1','dy2','dz'))]
                for v in document_rows(snapshot, collection)]
    if collection == 'boolean':
        return [[v.enabled, v.target_volume, v.index, v.operation, v.tool_shape, v.tool_size,
                 v.tool_parameters, v.position, v.rotation] for v in document_rows(snapshot, collection)]
    raise ValueError('Collection has no editable table')


def _text(value):
    return ('true' if value else 'false') if type(value) is bool else str(value)


def _sync_table(snapshot, collection, columns=None, index=None):
    name = TABLES[collection]
    values = table_values(snapshot, collection)
    previous = snapshot.state['tables'].get(name)
    if previous is None or len(previous) != len(values):
        snapshot.state['tables'][name] = [[_text(v) for v in row] for row in values]
        return
    for i, row in enumerate(values):
        if index is not None and i != index:
            continue
        for col, value in enumerate(row):
            if columns is not None and col not in columns:
                continue
            if (snapshot.state['selections'].get(f'pending_{name}_row') == i
                    and snapshot.state['selections'].get(f'pending_{name}_column') == col):
                continue
            previous[i][col] = _text(value)


def _geometry_structure(snapshot, action, revision):
    collection = action['collection']
    if collection not in {'volume', 'boolean', 'layer'}:
        raise ValueError('Invalid geometry collection')
    rows = document_rows(snapshot, collection)
    operation = action['operation']
    index = _check_ref(snapshot, action['ref'], revision) if operation != 'add' else len(rows)
    if operation != 'add' and action['ref'].collection != collection:
        raise ValueError('Mismatched geometry row reference')
    if collection in ('volume', 'boolean') and TABLES[collection] not in snapshot.state['tables']:
        _sync_table(snapshot, collection)
    permutation = list(range(len(rows)))
    def unique(base):
        names = {v.name for v in rows}
        value, suffix = base, 2
        while value in names:
            value = f'{base}_{suffix}'
            suffix += 1
        return value
    if operation == 'add':
        if collection == 'volume':
            row = HierarchicalVolumeRow(name=unique('Volume'), parent='world' if any(
                v.name.lower() == 'world' for v in rows) else '', shape='box', size='1 mm,1 mm,1 mm',
                material='G4_Si', position='0 mm,0 mm,0 mm', rotation='0 deg,0 deg,0 deg')
        elif collection == 'layer':
            row = LayerRow(name=f'Layer{len(rows)+1}', material='G4_Si', thickness='1 um', xy='10 mm, 10 mm')
        else:
            volumes = snapshot.project.geometryEditor.volumes
            target = next((v.name.strip() for v in volumes if v.enabled and v.name.strip().lower() != 'world'),
                          volumes[0].name.strip() if volumes else '')
            number = sum(v.target_volume == target for v in rows)
            row = BooleanOperationRow(target_volume=target, index=number, operation='subtraction', tool_shape='box',
                tool_size='1 mm,1 mm,1 mm', position='0 mm,0 mm,0 mm', rotation='0 deg,0 deg,0 deg',
                name=f'{target}_cut_{number}' if target else '')
            if snapshot.project.geometryEditor.mode == 'hierarchical':
                snapshot.project.geometryEditor.mode = 'hierarchical_boolean'
        rows.append(row)
        permutation.append(None)
    elif operation == 'duplicate':
        row = copy.deepcopy(rows[index])
        row.name = unique(f'{row.name}_copy') if collection == 'volume' else (
            f'{row.name}_copy' if collection == 'layer' or row.name else '')
        row.errors = []
        if hasattr(row, 'warnings'):
            row.warnings = []
        rows.insert(index+1, row)
        permutation.insert(index+1, index)
        index += 1
    elif operation == 'delete':
        if collection == 'volume' and rows[index].name.strip().lower() == 'world':
            raise ValueError('World volume cannot be deleted')
        del rows[index]
        permutation.pop(index)
        index = min(index, len(rows)-1)
    elif operation == 'move':
        direction = action['direction']
        if type(direction) is not int or direction not in (-1, 1):
            raise ValueError('Move requires an adjacent direction')
        target = index + direction
        if not 0 <= target < len(rows):
            return False
        rows[index], rows[target] = rows[target], rows[index]
        permutation[index], permutation[target] = permutation[target], permutation[index]
        index = target
    else:
        raise ValueError('Invalid geometry structure action')
    _remap_details(snapshot.state, collection, permutation)
    name = TABLES[collection]
    selection = snapshot.state['selections']
    old_pending = selection.get(f'pending_{name}_row')
    if old_pending is not None:
        # Duplicate does not duplicate the active editor; keep it on the original entity.
        destination = next((i for i, old in enumerate(permutation) if old == old_pending
                            and not (operation == 'duplicate' and i == index)), None)
        if destination is None:
            selection.pop(f'pending_{name}_row', None)
            selection.pop(f'pending_{name}_column', None)
        else:
            selection[f'pending_{name}_row'] = destination
    if collection in ('volume', 'boolean'):
        old = snapshot.state['tables'][name]
        typed = table_values(snapshot, collection)
        snapshot.state['tables'][name] = [copy.deepcopy(old[source]) if source is not None
                                         else [_text(v) for v in typed[i]] for i, source in enumerate(permutation)]
        if operation == 'duplicate':
            _sync_table(snapshot, collection, {1} if collection == 'volume' else set(), index)
    if collection == 'boolean':
        counts = {}
        for row in rows:
            key = row.target_volume.strip()
            row.index = counts.get(key, 0)
            counts[key] = row.index + 1
        _sync_table(snapshot, collection, {2})
    selection[name] = index


def _reduce_geometry(candidate, action, *, revision):
    kind = action.get('kind')
    document = candidate.project.geometryEditor
    if kind == 'geometry_structure':
        if _geometry_structure(candidate, action, revision) is False:
            return candidate
    elif kind in ('geometry_cell', 'geometry_buffer'):
        ref = action['ref']
        index = _check_ref(candidate, ref, revision)
        if ref.collection not in ('volume', 'boolean'):
            raise ValueError('Invalid editable table')
        column, raw = action['column'], action['raw']
        count = 16 if ref.collection == 'volume' else 9
        if type(column) is not int or not 0 <= column < count or type(raw) is not str:
            raise ValueError('Invalid table cell')
        name = TABLES[ref.collection]
        if name not in candidate.state['tables']:
            _sync_table(candidate, ref.collection)
        candidate.state['tables'][name][index][column] = raw
        if kind == 'geometry_buffer':
            candidate.state['selections'].update({f'pending_{name}_row': index, f'pending_{name}_column': column})
            candidate.project.editingState = copy.deepcopy(candidate.state)
            return candidate
        row = document_rows(candidate, ref.collection)[index]
        value = raw.strip()
        if ref.collection == 'volume':
            fields = ('enabled','name','parent','shape','material','position','size','rotation','sensitive','bias','region')
            if column >= 11:
                key = ('dx1','dx2','dy1','dy2','dz')[column-11]
                if value:
                    row.shape_properties[key] = value
                else:
                    row.shape_properties.pop(key, None)
            else:
                field = fields[column]
                if column in (0, 8, 9):
                    value = value.lower() in ('true','yes','on','1')
                elif column == 3:
                    display_size = row.parameters if row.shape.strip().lower() != 'box' and row.parameters else row.size
                    value = value or 'box'
                    setattr(row, 'size' if canonical_solid(value) == 'box' else 'parameters', display_size)
                elif column == 6 and canonical_solid(row.shape) != 'box':
                    field = 'parameters'
                setattr(row, field, value)
        else:
            field = ('enabled','target_volume','index','operation','tool_shape','tool_size','tool_parameters','position','rotation')[column]
            if column == 0:
                value = value.lower() in ('true','yes','on','1')
            elif column == 2:
                try:
                    value = int(value)
                except ValueError:
                    value = index
            elif column in (3,4):
                value = value or ('subtraction' if column == 3 else 'box')
            setattr(row, field, value)
        candidate.state['selections'].pop(f'pending_{name}_row', None)
        candidate.state['selections'].pop(f'pending_{name}_column', None)
    elif kind == 'geometry_scalar':
        binding, value = action['binding'], action['value']
        if binding not in DOCUMENT_BINDINGS:
            raise ValueError('Unknown geometry binding')
        if binding == 'config.geometry_template':
            if type(value) is not str:
                raise ValueError('Template must be text')
            candidate.project.geometrySettings.template = value
            set_geometry_mode(document, value)
            if document.mode in HIERARCHICAL_GEOMETRY_MODES and not document.volumes:
                document.volumes.append(HierarchicalVolumeRow(name='world', shape='box', size='10 cm,10 cm,10 cm',
                    material='G4_AIR', position='0 mm,0 mm,0 mm', rotation='0 deg,0 deg,0 deg'))
                _sync_table(candidate, 'volume')
        else:
            name = binding.removeprefix('config.')
            owner, field = (document, 'source_copy_mode') if name == 'geometry_source_copy' else (
                (document.simple_box, name[7:]) if name.startswith('simple_') else (document.layered_device, name[8:]))
            if type(value) is not type(getattr(owner, field)):
                raise ValueError('Geometry field type mismatch')
            setattr(owner, field, value.strip() if type(value) is str else value)
        candidate.state['drafts'][binding] = value
    elif kind in ('layer_detail', 'geometry_detail'):
        ref = action['ref']
        index = _check_ref(candidate, ref, revision)
        if ref.collection not in ('volume','boolean','layer'):
            raise ValueError('Invalid geometry detail collection')
        row = document_rows(candidate, ref.collection)[index]
        candidate.state['selections'][TABLES[ref.collection]] = index
        values = action['values']
        if type(values) is not dict:
            raise ValueError('Geometry details require data fields')
        if kind == 'layer_detail':
            fields = {'enabled','name','material','thickness','xy','sensitive','bias','region','copy_no','position','rotation'}
            if ref.collection != 'layer' or set(values) != fields:
                raise ValueError('Invalid layer fields')
            for key, value in values.items():
                if type(value) is not type(getattr(row,key)):
                    raise ValueError('Layer field type mismatch')
                setattr(row, key, value.strip() if type(value) is str else value)
                if key in {'name','thickness','xy','region','copy_no','position','rotation'}:
                    binding = f'detail.layer.{index}.{key}'
                    if value != value.strip(): candidate.state['drafts'][binding] = value
                    else: candidate.state['drafts'].pop(binding, None)
        else:
            properties = {p['name'] for spec in SOLIDS.values() for p in spec['properties']}
            allowed = ({'shape','size','parameters'} | {'prop.'+p for p in properties}) if ref.collection != 'layer' else set()
            allowed |= ({'name'} if ref.collection == 'boolean' else {'metadata','vis.color','vis.alpha','vis.visible','vis.wireframe',
                                                                          'cut.gamma','cut.e-','cut.e+','cut.proton'})
            if ref.collection == 'volume': allowed |= set(PLACEMENT_PROPERTY_KEYS) | {'copy_no'}
            if set(values) - allowed or any(type(v) is not str for v in values.values()):
                raise ValueError('Invalid geometry backend detail fields')
            for key, value in values.items():
                if key.startswith(('prop.','vis.','cut.')) or key in PLACEMENT_PROPERTY_KEYS:
                    target = row.shape_properties if key.startswith('prop.') else row.visual if key.startswith('vis.') else (
                        row.production_cuts if key.startswith('cut.') else row.preview_properties)
                    name = key[5:] if key.startswith('prop.') else key
                    if value: target[name] = value
                    else: target.pop(name, None)
                    if key.startswith('prop.') and ref.collection == 'volume': row.preview_properties.pop(name, None)
                else:
                    field = 'tool_'+key if ref.collection == 'boolean' and key in ('shape','size','parameters') else key
                    setattr(row,field,value)
            if ref.collection in ('volume','boolean'):
                _sync_table(candidate, ref.collection, {4,5,6} if ref.collection == 'boolean' else {3,6,11,12,13,14,15}, index)
    else:
        raise ValueError('Unknown document action')
    document.is_dirty = document.mode in EDITABLE_GEOMETRY_MODES
    candidate.project.editingState = copy.deepcopy(candidate.state)
    return candidate


@dataclass(frozen=True)
class RowRef:
    collection: str
    revision: int
    index: int
    row: dict


def document_rows(snapshot, collection):
    if type(collection) is not str or collection not in {'material', 'layer', 'volume', 'boolean'}:
        raise ValueError('Unknown document collection')
    if collection == 'material':
        document = snapshot.project.materialEditor
        return document.rows if document is not None else []
    document = snapshot.project.geometryEditor
    return {'layer': document.layered_device.layers, 'volume': document.volumes,
            'boolean': document.boolean_ops}[collection]


def row_ref(snapshot, collection, index, revision):
    if type(revision) is not int:
        raise TransactionConflict('Document reference requires an integer revision')
    rows = document_rows(snapshot, collection)
    if type(index) is not int or not 0 <= index < len(rows):
        raise TransactionConflict('Document row is no longer available')
    return RowRef(collection, revision, index, copy.deepcopy(asdict(rows[index])))


def _check_ref(snapshot, ref, revision):
    if (type(revision) is not int or type(ref) is not RowRef or type(ref.revision) is not int
            or ref.revision != revision or type(ref.index) is not int or type(ref.row) is not dict
            or type(ref.collection) is not str or ref.collection not in {'material', 'layer', 'volume', 'boolean'}):
        raise TransactionConflict('Document row belongs to another revision')
    rows = document_rows(snapshot, ref.collection)
    if not 0 <= ref.index < len(rows) or not _same_data(asdict(rows[ref.index]), ref.row):
        raise TransactionConflict('Document row changed before the edit')
    return ref.index


def _same_data(left, right):
    if type(left) is not type(right): return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same_data(v,right[k]) for k,v in left.items())
    if type(left) is list:
        return len(left)==len(right) and all(_same_data(a,b) for a,b in zip(left,right))
    return left == right


def _remap_details(state, collection, permutation):
    prefix = f'detail.{collection}.'
    previous = {k: v for k, v in state['drafts'].items() if k.startswith(prefix)}
    for key in previous:
        del state['drafts'][key]
    for new, old in enumerate(permutation):
        if old is None:
            continue
        for key, value in previous.items():
            parts = key.split('.')
            if int(parts[2]) == old:
                state['drafts'][f'{prefix}{new}.{parts[3]}'] = value


def copy_materials(target, source):
    target.materialEditor = copy.deepcopy(source.materialEditor)


def reduce_documents(snapshot: WorkspaceSnapshot, action: dict, *, revision: int):
    """Return a candidate; the caller alone publishes through EditSession."""
    if type(action) is not dict:
        raise ValueError('Document action must be data')
    if type(revision) is not int:
        raise TransactionConflict('Document action requires an integer revision')
    candidate = clone_snapshot(snapshot)
    kind = action.get('kind')
    if kind == 'replace_document':
        domain = action['domain']
        if domain not in ('materials', 'geometry'):
            raise ValueError('Unknown document source domain')
        source = action['source']
        if type(source) is not dict or set(source) != {'path','text','read_success','template'} or source['read_success'] is not True:
            raise ValueError('Document replacement requires a successful captured read')
        document = copy.deepcopy(action['document'])
        if document.source_path != source['path'] or document.raw_source_text != source['text']:
            raise ValueError('Document and captured source disagree')
        if domain == 'materials':
            candidate.project.materialEditor = document
            prefixes = ('detail.material.',)
            candidate.state['selections']['materials_table'] = -1
        else:
            candidate.project.geometryEditor = document
            prefixes = ('detail.layer.','config.simple_','config.layered_')
            for collection in ('volume','boolean','layer'):
                name = TABLES[collection]
                candidate.state['selections'][name] = -1
                candidate.state['selections'].pop(f'pending_{name}_row',None)
                candidate.state['selections'].pop(f'pending_{name}_column',None)
            for collection in ('volume','boolean'):
                candidate.state['tables'].pop(TABLES[collection],None)
                _sync_table(candidate,collection)
            candidate.state['drafts']['config.geometry_source_copy'] = document.source_copy_mode
        for key in list(candidate.state['drafts']):
            if key.startswith(prefixes): del candidate.state['drafts'][key]
        candidate.state['sources'][domain] = copy.deepcopy(source)
        candidate.transient[domain] = copy.deepcopy(action.get('summary'))
        candidate.project.editingState = copy.deepcopy(candidate.state)
        return candidate
    if kind not in {'material_detail', 'material_add', 'material_duplicate', 'material_delete'}:
        return _reduce_geometry(candidate, action, revision=revision)
    document = candidate.project.materialEditor
    if document is None:
        if kind != 'material_add':
            raise ValueError('There is no material document to edit')
        document = candidate.project.materialEditor = MaterialDocument()
    if kind == 'material_add':
        if action['mode'] not in {'nist', 'mass_fraction', 'volume_fraction', 'atom_count'}:
            raise ValueError('Unknown material mode')
        add_default_row(document, action['mode'])
        index = len(document.rows) - 1
    else:
        ref = action['ref']
        index = _check_ref(snapshot, ref, revision)
        if ref.collection != 'material':
            raise ValueError('Expected material row reference')
        if kind == 'material_detail':
            values = action['values']
            if type(values) is not dict or set(values) != {'name', 'mode', 'density', 'enabled', 'components_text'}:
                raise ValueError('Invalid material detail fields')
            if type(values['enabled']) is not bool or any(type(v) is not str for k, v in values.items() if k != 'enabled'):
                raise ValueError('Invalid material detail types')
            row = document.rows[index]
            for field, value in values.items():
                setattr(row, field, value.strip() if isinstance(value, str) else value)
            for field in ('name', 'density', 'components_text'):
                key = f'detail.material.{index}.{field}'
                if values[field] != values[field].strip():
                    candidate.state['drafts'][key] = values[field]
                else:
                    candidate.state['drafts'].pop(key, None)
            if row.mode == 'nist' and row.name.startswith('G4_'):
                row.nist_name = row.name
            row.components = parse_components_text(row.components_text, row.mode)
            row.is_dirty = document.is_dirty = True
        else:
            permutation = list(range(len(document.rows)))
            if kind == 'material_duplicate':
                duplicate_row(document, index)
                permutation.insert(index + 1, None)  # Existing helper copies typed values, not raw drafts.
                index += 1
            else:
                delete_row(document, index)
                permutation.pop(index)
                index = min(index, len(document.rows) - 1)
            _remap_details(candidate.state, 'material', permutation)
    candidate.state['selections']['materials_table'] = index
    candidate.project.editingState = copy.deepcopy(candidate.state)
    return candidate
