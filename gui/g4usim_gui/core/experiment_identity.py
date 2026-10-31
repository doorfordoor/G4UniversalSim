"""K1 identities. Resource syntax belongs exclusively to experiment_bundle.

Call these functions on private snapshots in an EvidenceJob, never on a live
EditSession. F1 output/provenance remains the owner of backend byte evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.output.identity import hash_file


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def file_identity(path) -> dict:
    digest, size = hash_file(Path(path))
    return {"sha256": digest, "size_bytes": size}


def resource_identity(snapshot, *, resource_policy=None) -> dict:
    # Shared with export: do not create a second, inevitably divergent parser.
    from g4usim_gui.core.experiment_bundle import collect_bundle_resources
    try:
        closure = collect_bundle_resources(snapshot, resource_policy=resource_policy)
    except ValueError as error:
        project = snapshot.project
        cwd = Path(project.workspaceRoot or project.pathSettings.workspace_root or Path.cwd())
        value = project.geometrySettings.config_path or project.pathSettings.geometry_config
        geometry = (Path(value) if Path(value).is_absolute() else cwd / value).absolute()
        # Only this geometry producer's unknown grammar permits the explicitly
        # requested local copy. A material/macro failure cannot borrow it.
        if (resource_policy is not None or project.runInputMode != "generated" or
                not project.geometryEditor.source_copy_mode or
                not str(error).startswith(f"Unknown resource grammar: {geometry}:")):
            raise
        declared = (("materials", project.pathSettings.materials_config), ("geometry", value))
        records, receipts = [], {}
        for role, name in declared:
            path = Path(name).expanduser()
            path = (path if path.is_absolute() else cwd / path).absolute()
            for part in (path, *path.parents):
                if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                    raise ValueError("Local source copy refuses linked paths") from error
                if part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400:
                    raise ValueError("Local source copy refuses reparse paths") from error
            if not path.is_file() or path.stat().st_nlink != 1:
                raise ValueError("Local source copy requires ordinary declared files") from error
            identity = file_identity(path)
            receipts[str(path.resolve())] = identity
            records.append({"path": f"declared/{role}", "role": role, "sha256": identity["sha256"],
                            "source_sha256": identity["sha256"], "captured_text": False,
                            "distribution": "unknown"})
        return {"coverage": "local_source_copy_compatibility", "coverage_reason": str(error),
                "recursive_closure": "unverified_export_not_qualified", "resources": records,
                "declared_source_receipts": receipts, "resource_fingerprint": canonical_digest(records),
                "configuration_fingerprint": snapshot_fingerprint(snapshot)}
    resources = closure["resources"]
    if not isinstance(resources, list):
        raise ValueError("Resource collector did not return a resources list")
    records = []
    for row in resources:
        record = {key: row[key] for key in
                  ("path", "sha256", "source_sha256", "role", "distribution", "captured_text") if key in row}
        if not all(isinstance(record.get(key), str) and record[key]
                   for key in ("path", "sha256", "role")):
            raise ValueError("Invalid resource identity")
        if Path(record["path"]).is_absolute() or ".." in Path(record["path"]).parts:
            raise ValueError("Resource identity requires a logical relative path")
        records.append(record)
    records.sort(key=lambda row: (row["path"], row["role"]))
    # Raw source SHA is a read/capture receipt. Relocating paths may legitimately
    # change it; it must not change the portable semantic content identity.
    portable = [{key: row[key] for key in ("path", "sha256", "role")} for row in records]
    return {"coverage": "closed_resource_tree", "resources": records, "resource_fingerprint": canonical_digest(portable),
            "configuration_fingerprint": canonical_digest(closure["snapshot"])}


def capture_identity(snapshot, revision: int, *, environment=None, resource_policy=None) -> dict:
    identity = resource_identity(snapshot, resource_policy=resource_policy)
    executable = snapshot.project.executable or snapshot.project.pathSettings.executable
    try:
        backend = {"status": "recorded", **file_identity(executable)} if executable else {"status": "unknown"}
    except OSError:
        backend = {"status": "unknown"}
    identity.update({"schema": "g4usim_experiment_identity_v1", "revision": revision,
                     "snapshot_fingerprint": snapshot_fingerprint(snapshot),
                     "backend": backend,
                     "environment": environment if environment is not None else {"status": "unknown"}})
    # Revision is checked separately; it must never be confused with a content hash.
    identity["fingerprint"] = canonical_digest({key: identity[key] for key in
        ("configuration_fingerprint", "resource_fingerprint")})
    identity["execution_fingerprint"] = canonical_digest({key: identity[key] for key in
        ("fingerprint", "backend", "environment")})
    return identity


def safe_environment(probe: dict, *, cwd=None) -> dict:
    """Keep relevant facts, never arbitrary environment variables or credentials.

    Binary/capability and data probes are evidence, not a physical pass flag.
    The allowlist deliberately excludes diagnostics containing private paths.
    """
    result = {"status": "unknown", "dataset_content_identity": "unknown",
              "coverage": "observed_selection_and_presence_not_dataset_bytes"}
    if not isinstance(probe, dict):
        return result
    for key in ("schema", "version", "status", "available", "geant4_version",
                "binary_sha256", "source_fingerprint", "platform"):
        value = probe.get(key)
        if type(value) in (str, bool, int, float) and (not isinstance(value, str)
                or ("\\" not in value and ":/" not in value)):
            result[key] = value
    def select(value, names):
        return {key: value[key] for key in names if isinstance(value, dict) and key in value
                and (value[key] is None or type(value[key]) in (str, int, bool))}
    result["binary"] = select(probe.get("identity"), ("sha256", "stable"))
    result["architecture"] = select(probe.get("architecture"), ("format", "machine", "bits"))
    result["build"] = select(probe.get("build"), ("compiler_id", "compiler_version", "geant4_version_number"))
    capabilities = probe.get("capabilities", {})
    result["capabilities"] = {"status": capabilities.get("status", "unknown"),
        "data": select(capabilities.get("data"), ("schema", "version", "geant4_version", "geant4_version_number",
            "source_fingerprint", "root", "gdml", "multithreaded"))}
    protocol = capabilities.get("data") or {}
    for wire, canonical in (("build_git_commit", "git_commit"), ("build_git_source_state", "git_source_state"),
                            ("build_compiler_id", "compiler_id"), ("build_compiler_version", "compiler_version"),
                            ("build_configuration", "configuration")):
        if isinstance(protocol.get(wire), str):
            result["capabilities"]["data"][canonical] = protocol[wire]
    data = probe.get("data", {})
    report = data.get("report") or {}
    probe_cwd = cwd or data.get("probe", {}).get("working_directory")
    def selected(row):
        value = row.get("path")
        if not value:
            return None
        path = Path(value)
        if not path.is_absolute():
            if not probe_cwd:
                return None
            path = Path(probe_cwd) / path
        return canonical_digest(str(path.resolve()))
    result["data"] = {"status": data.get("status", "unknown"),
        "required_complete": data.get("required_complete"),
        "datasets": [{**select(row, ("env", "folder", "required", "found")),
            "selected_path_sha256": selected(row)}
            for row in report.get("datasets", [])]}
    return result
