"""Language-independent diagnostics and transient producer records (no Qt).

Locations describe evidence, not inferred matches in translated display strings.
Source hashes below explicitly cover the supplied logical text, not original IO bytes.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any

SCHEMA = 'g4usim_diagnostics_v1'
SEVERITIES = {'error', 'warning', 'info', 'blocker'}
_CHANNELS = {'error': 'errors', 'blocker': 'errors', 'warning': 'warnings', 'info': 'info'}
_CODE = re.compile(r'^[A-Za-z0-9_.-]+$')
_HASH = re.compile(r'^[0-9a-f]{64}$')


def _json_value(value: Any) -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError('Diagnostic JSON values must be finite')
        return value
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError('Diagnostic JSON object keys must be strings')
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise ValueError(f'Unsupported diagnostic JSON type: {type(value).__name__}')


def _canonical(value: Any) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _string(value: Any, name: str, *, required: bool = False) -> None:
    if type(value) is not str or (required and not value):
        raise ValueError(f'{name} must be {"a nonempty" if required else "a"} string')


@dataclass(frozen=True)
class SourceLocation:
    filename: str
    line: int | None = None
    section: str = ''
    key: str = ''
    value: str = ''
    text_sha256: str = ''
    text_snapshot: str | None = None

    def __post_init__(self) -> None:
        _string(self.filename, 'source filename', required=True)
        if self.line is not None and (type(self.line) is not int or self.line < 1):
            raise ValueError('Source line must be a positive integer or null')
        for name in ('section', 'key', 'value', 'text_sha256'):
            _string(getattr(self, name), name)
        if self.text_sha256 and not _HASH.fullmatch(self.text_sha256):
            raise ValueError('Invalid source text SHA-256')
        if self.text_snapshot is not None:
            _string(self.text_snapshot, 'text_snapshot')
            expected = hashlib.sha256(self.text_snapshot.encode('utf-8')).hexdigest()
            if self.text_sha256 != expected:
                raise ValueError('Source snapshot and text SHA-256 differ')


@dataclass(frozen=True)
class EditorLocation:
    editor: str
    field: str = ''
    collection: str = ''
    row: int | None = None
    entity: str = ''
    snapshot_id: str = ''

    def __post_init__(self) -> None:
        _string(self.editor, 'editor', required=True)
        for name in ('field', 'collection', 'entity', 'snapshot_id'):
            _string(getattr(self, name), name)
        if self.row is not None:
            if type(self.row) is not int or self.row < 0 or not self.collection:
                raise ValueError('Editor row needs a nonnegative index and a collection')


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    origin: str
    message: str
    location: EditorLocation | None = None
    source: SourceLocation | None = None
    message_key: str = ''
    params: Mapping[str, Any] | None = None
    identity_parameters: Mapping[str, Any] | None = None
    raw_message: str = ''
    unavailable_reason: str = ''
    related_locations: tuple[EditorLocation, ...] = ()

    def __post_init__(self) -> None:
        if type(self.code) is not str or not _CODE.fullmatch(self.code):
            raise ValueError('Diagnostic code must be a nonempty machine identifier')
        if type(self.severity) is not str or self.severity not in SEVERITIES:
            raise ValueError('Invalid diagnostic severity')
        for name in ('origin', 'message', 'message_key', 'raw_message', 'unavailable_reason'):
            _string(getattr(self, name), name, required=name == 'origin')
        if self.location is not None and not isinstance(self.location, EditorLocation):
            raise ValueError('Invalid editor location')
        if self.source is not None and not isinstance(self.source, SourceLocation):
            raise ValueError('Invalid source location')
        if self.location is None and self.source is None and not self.unavailable_reason:
            raise ValueError('Diagnostic without a location needs an explicit reason')
        if any(not isinstance(item, EditorLocation) for item in self.related_locations):
            raise ValueError('Invalid related editor location')
        params = {} if self.params is None else self.params
        if not isinstance(params, Mapping):
            raise ValueError('Diagnostic params must be an object')
        identity_params = params if self.identity_parameters is None else self.identity_parameters
        if not isinstance(identity_params, Mapping):
            raise ValueError('Diagnostic identity_parameters must be an object')
        object.__setattr__(self, 'params', _freeze(_json_value(params)))
        object.__setattr__(self, 'identity_parameters', _freeze(_json_value(identity_params)))
        object.__setattr__(self, 'related_locations', tuple(self.related_locations))

    @property
    def identity(self) -> str:
        def target(location):
            if location is None:
                return None
            value = asdict(location)
            value.pop('snapshot_id')
            return value
        source = None if self.source is None else asdict(self.source)
        if source is not None:
            source.pop('text_snapshot')
        facts = dict(code=self.code, severity=self.severity, origin=self.origin,
                     location=target(self.location), source=source,
                     related_locations=[target(item) for item in self.related_locations],
                     identity_parameters=self.identity_parameters)
        return hashlib.sha256(_canonical(facts).encode('utf-8')).hexdigest()

    def __deepcopy__(self, memo):
        # Nested facts are immutable; project/scan copies may safely share them.
        memo[id(self)] = self
        return self

    def to_dict(self) -> dict[str, Any]:
        return dict(identity=self.identity, code=self.code, severity=self.severity,
                    origin=self.origin, message=self.message, message_key=self.message_key,
                    params=_json_value(self.params), identity_parameters=_json_value(self.identity_parameters),
                    raw_message=self.raw_message, unavailable_reason=self.unavailable_reason,
                    location=None if self.location is None else asdict(self.location),
                    source=None if self.source is None else asdict(self.source),
                    related_locations=[asdict(item) for item in self.related_locations])


def source_location(filename: str | Path, text: str, *, line: int | None = None,
                    section: str = '', key: str = '', value: str = '') -> SourceLocation:
    return SourceLocation(str(Path(filename).resolve()), line, section, key, value,
                          hashlib.sha256(text.encode('utf-8')).hexdigest(), text)


def semantic_snapshot(value: Any) -> str:
    if is_dataclass(value):
        value = asdict(value)
    return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def reset_diagnostics(owner: Any) -> None:
    owner._f4_diagnostics = []


def collect_diagnostics(owner: Any) -> tuple[Diagnostic, ...]:
    return tuple(getattr(owner, '_f4_diagnostics', ()))


def _append_record(owner: Any, record: Diagnostic, *, channel: str | None, append: bool) -> Diagnostic:
    if not hasattr(owner, '_f4_diagnostics'):
        reset_diagnostics(owner)
    if any(item.identity == record.identity for item in owner._f4_diagnostics):
        return record
    owner._f4_diagnostics.append(record)
    if append:
        name = channel or _CHANNELS[record.severity]
        if not hasattr(owner, name):
            setattr(owner, name, [])
        getattr(owner, name).append(record.message)
    return record


def emit_diagnostic(owner: Any, code: str, severity: str, message: str, *, origin: str,
                    location: EditorLocation | None = None, source: SourceLocation | None = None,
                    editor: str = '', field: str = '', collection: str = '', row: int | None = None,
                    entity: str = '', message_key: str = '', params: Mapping | None = None,
                    identity_parameters: Mapping | None = None, raw_message: str = '',
                    unavailable_reason: str = '', related_locations=(), channel: str | None = None,
                    append: bool = True) -> Diagnostic:
    if location is not None and editor:
        raise ValueError('Use location or editor arguments, not both')
    if editor:
        location = EditorLocation(editor, field, collection, row, entity)
    record = Diagnostic(code, severity, origin, message, location, source, message_key,
                        params, identity_parameters, raw_message or message,
                        unavailable_reason, tuple(related_locations))
    return _append_record(owner, record, channel=channel, append=append)


def extend_diagnostics(owner: Any, records, *, prefix: str = '', append: bool = True) -> None:
    for item in records:
        _append_record(owner, replace(item, message=prefix + item.message), channel=None, append=append)


def complete_diagnostics(owner: Any, *, origin: str = 'legacy') -> tuple[Diagnostic, ...]:
    """Wrap unmatched legacy text without guessing locations from that text.

    The slot is producer-channel order, never the UI's filtered/sorted row.
    Migrated producers should leave no error/warning fallback records here.
    """
    records = list(collect_diagnostics(owner))
    available = {(_CHANNELS[item.severity], item.message) for item in records}
    for channel in ('errors', 'warnings', 'info'):
        for slot, message in enumerate(getattr(owner, channel, ())):
            key = (channel, message)
            if key in available:
                continue
            records.append(Diagnostic('legacy.unstructured',
                {'errors':'error','warnings':'warning','info':'info'}[channel], origin,
                str(message), identity_parameters={'channel':channel,'producer_slot':slot},
                raw_message=str(message), unavailable_reason='legacy_unstructured'))
    return tuple(records)


@dataclass(frozen=True)
class DiagnosticBundle:
    diagnostics: tuple[Diagnostic, ...]
    snapshot_id: str = ''
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    info: tuple[str, ...] = ()

    @property
    def can_run(self) -> bool:
        return not self.errors


def diagnostics_to_dict(records, *, snapshot_id: str = '', channels: Mapping | None = None) -> dict:
    _string(snapshot_id, 'snapshot_id')
    records = tuple(records)
    ids = [item.identity for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate diagnostic identity')
    projected = {name: [] for name in ('errors','warnings','info')}
    for item in records:
        projected[_CHANNELS[item.severity]].append(item.message)
    if channels is not None:
        if set(channels) != set(projected):
            raise ValueError('Invalid diagnostic channels')
        for name in projected:
            values = channels[name]
            if not isinstance(values, (list,tuple)) or any(type(v) is not str for v in values):
                raise ValueError('Diagnostic channels must contain strings')
            # Legacy editors deduplicate equal display strings while structured
            # records retain distinct rows/fields. Text multiplicity is the
            # legacy channel's contract, not a count of diagnostic identities.
            if set(values) != set(projected[name]):
                raise ValueError('Diagnostic records and legacy channels disagree')
            projected[name] = list(values)
    return dict(schema=SCHEMA, snapshot_id=snapshot_id, can_run=not projected['errors'],
                **projected, diagnostics=[item.to_dict() for item in records])


def _strict_object(value: Any, fields: set[str], name: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise ValueError(f'Invalid {name} fields')
    return value


def diagnostics_from_dict(payload: Any) -> DiagnosticBundle:
    payload = _strict_object(payload, {'schema','snapshot_id','can_run','errors','warnings','info','diagnostics'}, 'diagnostic report')
    if payload['schema'] != SCHEMA or type(payload['can_run']) is not bool:
        raise ValueError('Unsupported diagnostic schema or invalid can_run')
    _string(payload['snapshot_id'], 'snapshot_id')
    if type(payload['diagnostics']) is not list:
        raise ValueError('Diagnostics must be a list')
    records=[]
    fields={'identity','code','severity','origin','message','message_key','params','identity_parameters',
            'raw_message','unavailable_reason','location','source','related_locations'}
    for raw in payload['diagnostics']:
        row=dict(_strict_object(raw,fields,'diagnostic'))
        identity=row.pop('identity')
        if type(row['params']) is not dict or type(row['identity_parameters']) is not dict:
            raise ValueError('Diagnostic parameter fields must be JSON objects')
        if row['location'] is not None:
            row['location']=EditorLocation(**_strict_object(row['location'],set(EditorLocation.__dataclass_fields__),'editor location'))
        if row['source'] is not None:
            row['source']=SourceLocation(**_strict_object(row['source'],set(SourceLocation.__dataclass_fields__),'source location'))
        if type(row['related_locations']) is not list:
            raise ValueError('Related locations must be a list')
        row['related_locations']=tuple(EditorLocation(**_strict_object(item,set(EditorLocation.__dataclass_fields__),'related location')) for item in row['related_locations'])
        record=Diagnostic(**row)
        if type(identity) is not str or record.identity != identity:
            raise ValueError('Diagnostic identity does not match its facts')
        records.append(record)
    channels={name:payload[name] for name in ('errors','warnings','info')}
    normalized=diagnostics_to_dict(records,snapshot_id=payload['snapshot_id'],channels=channels)
    if normalized['can_run'] != payload['can_run']:
        raise ValueError('Diagnostic can_run does not match errors')
    return DiagnosticBundle(tuple(records),payload['snapshot_id'],*(tuple(payload[name]) for name in ('errors','warnings','info')))


def diagnostics_from_json(raw: str | bytes) -> DiagnosticBundle:
    """Strict JSON entry point; duplicate object keys must not disappear in parsing."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate diagnostic JSON key: {key}')
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f'Non-finite diagnostic JSON number: {value}')

    return diagnostics_from_dict(json.loads(raw, object_pairs_hook=pairs, parse_constant=constant))
