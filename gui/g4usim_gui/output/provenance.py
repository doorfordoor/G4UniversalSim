"""One provenance policy for automatic output-directory consumers; no Qt imports."""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import warnings
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from .identity import strict_object, validate_extension

# An operation-local verified snapshot, never a cross-action file cache.
_operation = ContextVar("g4usim_evidence_operation", default=None)

def evidence_key(path):
    return str(Path(path).resolve())

def verification_active():
    return _operation.get() is not None

@contextmanager
def evidence_operation(seeds=None):
    token = _operation.set(dict(seeds or {}))
    try:
        yield
    finally:
        _operation.reset(token)

def verified_operation(function):
    @wraps(function)
    def call(*args, **kwargs):
        if verification_active():
            return function(*args, **kwargs)
        with evidence_operation():
            return function(*args, **kwargs)
    return call

LEGACY_WARNING = "Legacy/unverified directory: run_metadata.json is absent; file ownership and completeness are unverified."


class ProvenanceError(ValueError):
    pass


@dataclass(frozen=True)
class OutputEvidence:
    root: Path
    files: tuple[Path, ...]
    document: dict | None
    manifest_digest: str | None = None
    records: tuple[dict, ...] = ()

    @property
    def status(self) -> str:
        return "verified" if self.document is not None and "provenance" in self.document else ("registered_manifest" if self.document is not None else "legacy_unverified")

    @property
    def verification_status(self) -> str:
        return "verified" if self.status == "verified" else "legacy"

    @property
    def warnings(self) -> list[str]:
        return (["Legacy metadata: content hashes are not recorded; byte identity is unverified."] if self.document is not None and "provenance" not in self.document else ([] if self.document is not None else [LEGACY_WARNING]))

    def artifact(self, path: str | Path) -> dict | None:
        target = Path(path).resolve()
        return next((record for local, record in zip(self.files, self.records) if local.resolve() == target), None)

    def matching(self, pattern: str) -> list[Path]:
        return sorted(p for p in self.files if fnmatchcase(p.name, pattern))

    def require(self, name: str) -> Path:
        path = self.root / name
        if path not in self.files:
            raise ProvenanceError(f"File is not registered for this output: {name}")
        return path


def _path(value: str):
    return PureWindowsPath(value) if "\\" in value or re.match(r"^[A-Za-z]:", value) else PurePosixPath(value)


def output_evidence(directory: str | Path, *, fresh: bool = False) -> OutputEvidence:
    operation = None if fresh else _operation.get()
    key = evidence_key(directory)
    if operation is not None and key in operation:
        result = operation[key]
        if isinstance(result, Exception):
            raise result
        return result
    try:
        result = _read_output_evidence(directory)
    except (ValueError, OSError) as error:
        if operation is not None: operation[key] = error
        raise
    if operation is not None: operation[key] = result
    return result


def _read_output_evidence(directory: str | Path) -> OutputEvidence:
    root = Path(directory)
    manifest = root / "run_metadata.json"
    if not manifest.exists() and not manifest.is_symlink():
        return OutputEvidence(root, tuple(sorted(p for p in root.glob("*") if p.is_file())), None)
    try:
        manifest_bytes = manifest.read_bytes()
        document = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=strict_object, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"non-finite JSON: {token}")))
        if not isinstance(document, dict) or document.get("schema") != "run_metadata_json_v1":
            raise ValueError("unsupported metadata schema")
        records = document.get("generated_files")
        if not isinstance(records, list):
            raise ValueError("generated_files must be a list")
        values = document.get("values", {})
        if not isinstance(values, dict):
            raise ValueError("metadata values must be an object")
        f1_fields = {"execution_id", "scope", "run_id", "thread_id", "sha256", "size_bytes", "integrity_status"}
        declares_f1 = any(key in values for key in ("output_provenance_schema", "execution_id")) or any(isinstance(row, dict) and f1_fields.intersection(row) for row in records)
        if "provenance" not in document and declares_f1:
            raise ValueError("F1 identity markers require the provenance extension; legacy downgrade is forbidden")
        paths = []
        for row in records:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not row["path"]:
                raise ValueError("invalid generated file record")
            if not isinstance(row.get("schema"), str) or not row["schema"]:
                raise ValueError("missing generated file schema")
            paths.append(_path(row["path"]))
        anchors = [p.parent for p in paths if p.name == "run_metadata.json" and p.is_absolute()]
        if len(anchors) > 1:
            raise ValueError("ambiguous manifest anchor")
        runs = document.get("runs")
        if not isinstance(runs, list):
            raise ValueError("runs must be a list")
        run_ids = set()
        for run in runs:
            if not isinstance(run, dict) or type(run.get("run_id")) is not int or run["run_id"] < 0:
                raise ValueError("invalid run ID")
            if run["run_id"] in run_ids:
                raise ValueError("duplicate run ID")
            if type(run.get("completed_events")) is not int or run["completed_events"] < 0:
                raise ValueError("invalid completed event count")
            run_ids.add(run["run_id"])
        files = []
        seen = set()
        for recorded in paths:
            if recorded.is_absolute():
                if not anchors:
                    raise ValueError("absolute file list lacks its manifest anchor")
                relative = recorded.relative_to(anchors[0])
            else:
                relative = recorded
            if not relative.parts or relative.drive or any(p in {"..", "."} for p in relative.parts):
                raise ValueError("invalid or escaping file path")
            local = root.joinpath(*relative.parts)
            canonical = local.resolve()
            if not canonical.is_relative_to(root.resolve()):
                raise ValueError("file escapes current output directory")
            if canonical in seen:
                raise ValueError("duplicate generated file")
            seen.add(canonical)
            if not local.is_file():
                raise ValueError(f"registered file is missing: {relative}; was listed in run_metadata.json generated_files but is missing")
            name = local.name
            if re.match(r"(?:hits|event_edep|.*_summary|hist_edep_\w+|phase_space|trajectories)_t\d+", name) or name.startswith(("scorer_statistics", "scoring_mesh", "g4usim")):
                suffix = re.search(r"_r(\d+)\.[^.]+$", name)
                run_id = int(suffix.group(1)) if suffix else 0
                if run_id not in run_ids:
                    raise ValueError(f"file references absent run {run_id}: {name}")
            files.append(local)
        for required in ("run_metadata.json", "run_summary.txt"):
            if root / required not in files:
                raise ValueError(f"required generated file is not registered: {required}")
        if "provenance" in document:
            validate_extension(document, files, root, run_ids)
        ordered = sorted(zip(files, records), key=lambda item: item[0])
        return OutputEvidence(root, tuple(item[0] for item in ordered), document, hashlib.sha256(manifest_bytes).hexdigest(), tuple(item[1] for item in ordered))
    except (ValueError, OSError, TypeError) as error:
        raise ProvenanceError(f"Invalid output provenance in {manifest}: {error}") from error


def output_files(directory: str | Path, pattern: str) -> list[Path]:
    evidence = output_evidence(directory)
    for message in evidence.warnings:
        warnings.warn(message, RuntimeWarning, stacklevel=2)
    return evidence.matching(pattern)
