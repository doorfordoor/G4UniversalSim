"""Explicit resource fields in J2 editor documents; no recursive guessing."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class _ResourceField:
    line: int
    section: str
    key: str
    value: str
    value_start: int
    value_end: int


def _geometry_resource_fields(text: str, source: str):
    """Relocation is not migration: legacy duplicate declarations stay intact.

    Only the final backend-effective resource value is materialized. A shadowed
    missing path must not invalidate an otherwise valid v1 input. Strict v2
    still goes through the existing migration scanner before any copy occurs.
    """
    if "\r" in text.replace("\r\n", "") or any(char in text for char in "\x85\u2028\u2029\x1c\x1d\x1e"):
        raise ValueError(f"{source}: unsupported geometry line separator")
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    section = "global"
    fields = []
    for index, raw in enumerate(lines):
        clean = re.split(r"[#;]", raw, maxsplit=1)[0].strip(" \t\r\n\v\f")
        if not clean:
            continue
        if clean.startswith("[") and clean.endswith("]"):
            section = clean[1:-1].strip(" \t\r\n\v\f")
            if not section:
                raise ValueError(f"{source}:{index + 1}: empty geometry section")
            continue
        if "=" not in clean:
            raise ValueError(f"{source}:{index + 1}: invalid geometry INI line")
        equal = raw.index("=")
        key = raw[:equal].strip(" \t\r\n\v\f")
        if not key or any(char.isspace() and ord(char) > 127 for char in section + key):
            raise ValueError(f"{source}:{index + 1}: invalid geometry section/key")
        tail = raw[equal + 1:]
        comment = re.search(r"[#;\r\n]", tail)
        start, end = equal + 1, equal + 1 + (comment.start() if comment else len(tail))
        while start < end and raw[start] in " \t\r\n\v\f": start += 1
        while end > start and raw[end - 1] in " \t\r\n\v\f": end -= 1
        fields.append(_ResourceField(index, section, key, raw[start:end], start, end))
    versions = [field for field in fields if field.section.lower() == "global" and field.key.lower() == "version"]
    if len(versions) > 1:
        raise ValueError(f"{source}: duplicate geometry version declaration")
    if versions and versions[0].value not in {"1", "2"}:
        raise ValueError(f"{source}: supported geometry versions are 1 and 2")
    if versions and versions[0].value == "2":
        from g4usim_gui.core.geometry_migration import _scan
        lines, _, fields = _scan(text, source)
    final = {}
    for field in fields:
        final[(field.section.lower(), field.key.lower())] = field
    return lines, sorted(final.values(), key=lambda field: field.line)


def materialize_geometry_file(path: Path, *, source_base: Path, destination: Path):
    """Copy explicitly referenced STL/copy tables without rewriting other lines."""
    raw = path.read_bytes()
    if not re.search(rb'(?mi)^[ \t]*(?:file|copies_file)[ \t]*=', raw):
        return
    lines, fields = _geometry_resource_fields(raw.decode('utf-8-sig'), str(path))
    copied = {}
    changed = False
    for field in fields:
        if field.key.lower() not in {'file', 'copies_file'} or not (
                field.section.lower() == 'world' or field.section.lower().startswith('volume.')):
            continue
        original = Path(field.value).expanduser()
        original = (original if original.is_absolute() else source_base / original).resolve(strict=True)
        if not original.is_file():
            raise ValueError(f'Geometry resource is not a file: {original}')
        if original not in copied:
            content = original.read_bytes()
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / f'g{len(copied):04d}{original.suffix}'
            with target.open('xb') as stream:
                stream.write(content)
            copied[original] = str(target.resolve()).replace('\\', '/')
        line = lines[field.line]
        lines[field.line] = line[:field.value_start] + copied[original] + line[field.value_end:]
        changed = True
    if changed:
        bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
        path.write_bytes(bom + ''.join(lines).encode('utf-8'))


def resource_fields(source, physics):
    """Yield mutable owner/key/role triples from the project JSON projection."""
    yield source, 'phase_space_file', 'phase_space'
    for item in source.get('gps_sources', []):
        yield item, 'spectrum_file', 'spectrum'
    for item in physics.get('fields', []):
        yield item, 'magnetic_map', 'field_map'
        yield item, 'electric_map', 'field_map'


def materialize_run_resources(source, physics, *, workspace: Path, destination: Path):
    """Copy selected runtime resources and return private models with new paths.

    Draft models are not changed. The run-package snapshot records these actual
    copied paths; the original editor snapshot remains owned by F5/K1.
    """
    source, physics = copy.deepcopy(source), copy.deepcopy(physics)
    pending = []
    if source.phase_space_file:
        pending.append((source, 'phase_space_file'))
    for item in source.gps_sources:
        if item.energy_type in {'histogram', 'points'} and item.spectrum_file:
            pending.append((item, 'spectrum_file'))
    for item in physics.fields:
        for key in ('magnetic_map', 'electric_map'):
            if getattr(item, key):
                pending.append((item, key))
    copied = {}
    def copy_path(value):
        original = Path(value.strip()).expanduser()
        original = original if original.is_absolute() else workspace / original
        original = original.resolve(strict=True)
        if not original.is_file():
            raise ValueError(f'Runtime resource is not a file: {original}')
        if original not in copied:
            raw = original.read_bytes()
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / f'r{len(copied):04d}{original.suffix}'
            with target.open('xb') as stream:
                stream.write(raw)
            copied[original] = str(target.resolve())
        return copied[original]
    for owner, key in pending:
        value = getattr(owner, key)
        relocated = ','.join(copy_path(part) for part in value.split(',')) if key == 'phase_space_file' else copy_path(value)
        setattr(owner, key, relocated)
    return source, physics
