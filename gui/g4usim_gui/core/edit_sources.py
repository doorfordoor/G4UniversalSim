"""Rebuild immutable source constraints from captured text, never current files.

Serialized diagnostic lists are display caches. They cannot authorize an editor
to discard unsupported source fields. Only the source parser can establish those
constraints; editable rows and raw drafts are deliberately left untouched.
"""
from __future__ import annotations

from types import SimpleNamespace

from g4usim_gui.core.diagnostics import SourceLocation, collect_diagnostics, emit_diagnostic
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.parsers.materials_parser import parse_materials_text


def _union(existing, derived):
    return list(dict.fromkeys([*existing, *derived]))


def restore_source_evidence(project, state=None) -> None:
    """Close the project/transaction boundary without replacing edited models.

    A legacy document with no captured text is left for the existing legacy
    source-loading path. A captured failed read is never parsed as an empty file.
    Existing extra blockers are retained conservatively; a cleared cache is
    replenished from the same captured text that accompanies the editor model.
    """
    sources = (state or {}).get('sources', {})
    for kind, document in (('materials', project.materialEditor),
                           ('geometry', project.geometryEditor)):
        source = sources.get(kind)
        if document is None:
            if source is not None:
                raise ValueError(f'Captured {kind} source has no editor document')
            continue
        # Wizard/template replacement deliberately creates an independent editor
        # document. Its previous source preview can still be visible, but is not
        # the provenance of these new rows.
        if not document.source_path and not document.raw_source_text:
            continue
        if source is None:
            if not document.raw_source_text:
                continue
            source = {'path': document.source_path, 'text': document.raw_source_text,
                      'read_success': True,
                      'template': document.mode if kind == 'geometry' else ''}
        elif source['text'] != document.raw_source_text:
            raise ValueError(f'Captured {kind} source disagrees with editor source text')

        if not source['read_success']:
            owner = SimpleNamespace(errors=[], warnings=[])
            errors = document.source_errors or [
                f"Captured {kind} source was not successfully read: {source['path']}"]
            for message in errors:
                emit_diagnostic(owner, 'ini.read_failed', 'error', message,
                                origin='ini.source', source=SourceLocation(source['path']),
                                unavailable_reason='source_unavailable')
            document.source_errors = list(errors)
            document.errors = _union(document.errors, errors)
            document._f4_source_diagnostics = collect_diagnostics(owner)
            if kind == 'geometry':
                document._f4_source_snapshot = SourceLocation(source['path'])
            continue

        if kind == 'materials':
            summary = parse_materials_text(source['text'], source_path=source['path'])
        else:
            summary = parse_geometry_text(source['text'], source_path=source['path'],
                                          template_name=source['template'])
            document.round_trip_blockers = _union(document.round_trip_blockers, summary.round_trip_blockers)
            document.source_warnings = _union(document.source_warnings, summary.warnings)
            document._f4_source_snapshot = summary._f4_source_snapshot
        document.source_errors = _union(document.source_errors, summary.errors)
        document.errors = _union(document.errors, document.source_errors)
        document._f4_source_diagnostics = collect_diagnostics(summary)
