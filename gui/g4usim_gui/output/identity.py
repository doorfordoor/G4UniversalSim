"""Strict F1 extension validation. Hashes describe byte consistency, not physics."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from contextvars import ContextVar

cancelled = ContextVar("g4usim_hash_cancelled", default=lambda: False)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            if cancelled.get()():
                raise ValueError('Output verification cancelled')
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def validate_extension(document: dict, files: list[Path], root: Path, run_ids: set[int]) -> None:
    p = document['provenance']
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    def text(obj, key):
        require(isinstance(obj.get(key), str) and bool(obj[key]), f"invalid {key}")
    def digest(value):
        return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None
    require(isinstance(p, dict), 'provenance must be an object')
    require(p.get('schema') == 'g4usim_provenance_v1', 'unsupported provenance schema')
    execution = p.get('execution_id')
    require(isinstance(execution, str) and re.fullmatch('[0-9a-f]{32}', execution) is not None, 'invalid execution_id')
    values = document.get('values', {})
    require(isinstance(values, dict), 'metadata values must be an object')
    if 'output_provenance_schema' in values:
        require(values['output_provenance_schema'] == p['schema'], 'metadata provenance schema declaration mismatch')
    if 'execution_id' in values:
        require(values['execution_id'] == execution, 'metadata execution identity declaration mismatch')
    build = p.get('build')
    require(isinstance(build, dict), 'invalid build identity')
    commit = build.get('git_commit')
    require(isinstance(commit, str) and (commit == 'unknown' or re.fullmatch('(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})', commit)), 'invalid git_commit')
    require(build.get('source_fingerprint') == 'unknown' or digest(build.get('source_fingerprint')), 'invalid source_fingerprint')
    require(build.get('git_source_state') in ('clean', 'dirty', 'unknown'), 'invalid git_source_state')
    for key in ('source_fingerprint', 'compiler_id', 'compiler_version', 'configuration', 'geant4_version'):
        text(build, key)
    require(p.get('input_coverage') == 'project_readers_observed', 'invalid input_coverage')
    require(p.get('input_observation') == 'bytes_read_not_semantic_acceptance', 'invalid input_observation')
    exclusions = p.get('input_exclusions')
    require(isinstance(exclusions, list) and len(exclusions) >= 2 and all(isinstance(x, str) and x for x in exclusions), 'invalid input_exclusions')
    inputs = p.get('inputs')
    require(isinstance(inputs, list), 'inputs must be a list')
    for sequence, row in enumerate(inputs, 1):
        require(isinstance(row, dict), 'invalid input record')
        require(type(row.get('sequence')) is int and row['sequence'] == sequence, 'invalid input sequence')
        for key in ('path', 'kind', 'role', 'capture_method'):
            text(row, key)
        require(isinstance(row.get('reason'), str), 'invalid input reason')
        if row.get('status') == 'recorded':
            require(digest(row.get('sha256')) and type(row.get('size_bytes')) is int and row['size_bytes'] >= 0, 'invalid recorded input digest')
        else:
            require(row.get('status') == 'unobserved' and 'sha256' in row and row['sha256'] is None and 'size_bytes' in row and row['size_bytes'] is None and bool(row['reason']), 'invalid unobserved input')
    for row, local in zip(document['generated_files'], files):
        require(row.get('execution_id') == execution, f"execution identity mismatch: {local.name}")
        require('run_id' in row and 'thread_id' in row, 'missing artifact scope identity')
        scope, run, thread = row.get('scope'), row['run_id'], row['thread_id']
        if scope == 'process':
            require(run is None and thread is None, 'invalid process scope')
        elif scope in ('run', 'thread'):
            require(type(run) is int and run in run_ids, 'artifact references absent run')
            require((thread is None) if scope == 'run' else (type(thread) is int and thread >= 0), 'invalid thread scope')
        else:
            require(False, 'invalid artifact scope')
        if local.name in {'run_summary.txt','effective_config_configure.json','effective_config_finalization.json'}:
            require(scope == 'process' and run is None and thread is None, 'process artifact scope conflicts with its role')
        effective = re.fullmatch(r'effective_config_(?:run_|final_r)(\d+)_t(-?\d+)\.json', local.name)
        if effective:
            named_run, named_thread = map(int, effective.groups())
            require(run == named_run, 'effective snapshot run identity conflicts with filename')
            require((scope == 'run' and thread is None) if named_thread < 0 else (scope == 'thread' and thread == named_thread), 'effective snapshot thread identity conflicts with filename')
        else:
            filename_thread = re.fullmatch(r'(?:hits|event_edep|hist_.+|.+_summary|phase_space|trajectories)_t(\d+)(?:_r(\d+))?\.[^.]+', local.name)
            filename_run = re.search(r'_r(\d+)\.[^.]+$', local.name)
            if filename_thread:
                named_thread, named_run = filename_thread.groups()
                require(scope == 'thread' and thread == int(named_thread), 'artifact thread identity conflicts with filename')
                require(run == int(named_run or 0), 'artifact run identity conflicts with filename')
            elif re.fullmatch(r'(?:g4usim|scorer_statistics|scoring_mesh)(?:_r\d+)?\.(?:root|csv)', local.name):
                require(scope == 'run' and run == (int(filename_run.group(1)) if filename_run else 0), 'run artifact lacks matching explicit run scope')
        status = row.get('integrity_status')
        if local == root / 'run_metadata.json':
            require(scope == 'process' and status == 'self_reference_excluded' and 'sha256' in row and row['sha256'] is None and 'size_bytes' in row and row['size_bytes'] is None, 'invalid metadata self reference exclusion')
            continue
        require(status == 'hashed', f"artifact integrity unavailable: {local.name}")
        require(digest(row.get('sha256')) and type(row.get('size_bytes')) is int and row['size_bytes'] >= 0, 'invalid artifact digest')
        actual, size = hash_file(local)
        require(actual == row['sha256'] and size == row['size_bytes'], f"artifact bytes mismatch: {local.name}; expected {row['sha256']}, observed {actual}")
