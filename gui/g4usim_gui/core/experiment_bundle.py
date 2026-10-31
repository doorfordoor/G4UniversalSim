"""Versioned, closed input bundles using the F5 snapshot and existing writer.

This module never runs a backend. ``inspect_bundle`` checks bytes and closure,
not initialization, event completion, redistribution rights or physics.

``resource_policy`` is a mapping from resolved source filename to a mapping
with ``distribution`` (unknown/permitted/restricted) and optionally
``allow_redistribution: True``. Restricted inputs require that explicit opt-in;
unknown is recorded, never interpreted as a licence. Unused policy keys fail.

The manifest's replay_inputs use bundle-root working-directory semantics.
Loading selects no backend unless explicitly supplied and marks all imported
validation history stale in snapshot.transient['bundle'].
"""
from __future__ import annotations

import copy
import ctypes
import errno
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
import sys
import tempfile
from typing import Any
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from g4usim_gui.core.config_migration import digest, load_json_strict
from g4usim_gui.core.config_schema import section_spec, spec
from g4usim_gui.core.edit_snapshot import (
    WorkspaceSnapshot, snapshot_from_dict, snapshot_from_json, snapshot_to_dict,
    snapshot_to_json,
)
from g4usim_gui.core.geometry_migration import TEMPLATE_ALIASES, _scan

BUNDLE_SCHEMA = "g4usim_experiment_bundle"
BUNDLE_VERSION = 1
MAX_MEMBERS = 4096
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
_SPACE = " \t\r\n\v\f"
_PRIVATE = {"executable", "workspaceRoot", "workspace_root", "runsRoot", "runs_root",
            "outputDir", "output_dir", "generated_path"}
_SECRET = re.compile(r"(?:password|passwd|secret|token|api_?key|credential)", re.I)
# Match experiment_identity.safe_environment's *output*, not the raw I1 probe
# or a process environment. Each nested object has its own closed projection.
_ENV_SCALAR = (str, bool, int, float)
_ENV_SELECTED = (str, bool, int, type(None))
_ENV_PROJECTION = {
    **dict.fromkeys(("schema", "version", "status", "available", "geant4_version",
                     "binary_sha256", "source_fingerprint", "platform", "os", "python"), _ENV_SCALAR),
    "dataset_content_identity": (str,), "coverage": (str,),
    "binary": dict.fromkeys(("sha256", "stable"), _ENV_SELECTED),
    "architecture": dict.fromkeys(("format", "machine", "bits"), _ENV_SELECTED),
    "build": dict.fromkeys(("compiler_id", "compiler_version", "geant4_version_number"), _ENV_SELECTED),
    "capabilities": {
        "status": (str,),
        "data": dict.fromkeys(("schema", "version", "geant4_version", "geant4_version_number",
                               "source_fingerprint", "root", "gdml", "multithreaded",
                               "git_commit", "git_source_state", "compiler_id", "compiler_version",
                               "configuration"), _ENV_SELECTED),
    },
    "data": {
        "status": (str,), "required_complete": (bool, type(None)),
        "datasets": [{"env": (str,), "folder": (str, type(None)),
                      "required": (bool, type(None)), "found": (bool, type(None)),
                      "selected_path_sha256": (str, type(None))}],
    },
}
_ROLES = {"main", "materials", "macro", "stl", "spectrum", "niel", "phase_space", "random_state", "copies", "gdml", "reference", "geometry", "field_map"}
_INPUT_COMMANDS = {
    "/control/execute": "macro", "/AIHL/material/load": "materials",
    "/AIHL/geometry/loadConfig": "geometry", "/random/resetEngineFrom": "random_state",
    "/gps/hist/file": "spectrum",
}
# Deliberately finite: unknown commands can load files or execute arbitrary UI
# actions. A prefix whitelist would silently miss future resource consumers.
_VALUE_COMMANDS = set("""
/control/verbose /run/verbose /event/verbose /tracking/verbose
/run/initialize /run/beamOn /random/setSeeds /random/setEngine
/AIHL/app/setNumThreads /AIHL/app/setSeed /AIHL/app/setRunName
/AIHL/app/setCheckOverlaps /AIHL/geometry/setTemplate
/AIHL/geometry/setDefaultWorldMaterial /AIHL/geometry/checkOverlaps
/AIHL/geometry/clear /AIHL/geometry/markModified /AIHL/geometry/print
/AIHL/geometry/printTree /AIHL/geometry/listUserVolumes
/AIHL/source/preset /AIHL/source/particle /AIHL/source/energy
/AIHL/source/position /AIHL/source/direction /AIHL/source/isotropic
/AIHL/source/planeBeam /AIHL/source/reset /AIHL/source/print
/AIHL/physics/setReferenceList /AIHL/physics/setBaseReferenceList
/AIHL/physics/clearReferenceList /AIHL/physics/setEM /AIHL/physics/print
/AIHL/physics/listAvailableReferences /AIHL/physics/listAvailableEMReferences
/gps/particle /gps/energy /gps/position /gps/direction /gps/number
/gps/pos/type /gps/pos/shape /gps/pos/centre /gps/pos/halfx /gps/pos/halfy
/gps/pos/radius /gps/pos/rot1 /gps/pos/rot2 /gps/ang/type
/gps/ang/mintheta /gps/ang/maxtheta /gps/ang/minphi /gps/ang/maxphi
/gps/ene/type /gps/ene/mono /gps/ene/min /gps/ene/max /gps/ene/sigma
/gps/ene/alpha /gps/ene/intercept /gps/ene/gradient /gps/ene/ezero
/gps/hist/type /gps/hist/point /gps/hist/inter /gps/source/add
/gps/source/set /gps/source/intensity /gps/source/multiplevertex
""".split())


def _json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _no_links(path: Path) -> Path:
    # Inspect lexical parents BEFORE collapsing '..': link/../input must not
    # discard a link component and accidentally change backend path semantics.
    path = Path(path)
    if not path.is_absolute():
        path = Path.cwd() / path
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError(f"Bundle refuses linked path: {part}")
        if part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Bundle refuses reparse point: {part}")
    return Path(os.path.abspath(path))


def _read(path: Path) -> bytes:
    path = _no_links(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError(f"Bundle requires an ordinary unlinked file: {path}")
    if info.st_size > MAX_FILE_BYTES:
        raise ValueError(f"Bundle resource exceeds size limit: {path}")
    with path.open("rb") as handle:
        raw = handle.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"Bundle resource exceeds size limit: {path}")
    return raw


def _member(value: str) -> str:
    if (type(value) is not str or not value or "\\" in value or ":" in value
            or any(ord(c) < 32 for c in value) or PureWindowsPath(value).drive):
        raise ValueError(f"Invalid bundle member: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in {"", ".", ".."} or p.endswith((" ", ".")) for p in value.split("/")):
        raise ValueError(f"Bundle path escapes or is ambiguous: {value!r}")
    if any(p.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(10)}, *{f"LPT{i}" for i in range(10)}} for p in path.parts):
        raise ValueError(f"Reserved bundle path: {value!r}")
    return value


def _resolve(value: str, base: Path) -> Path:
    if (not value or value != value.strip(_SPACE) or any(c in value for c in "\x00\r\n#;{}$\"'")
            or "://" in value or value.startswith(("~", "\\\\"))):
        raise ValueError(f"Unsupported or dynamic resource path: {value!r}")
    candidate = Path(value)
    if PureWindowsPath(value).drive and not candidate.is_absolute():
        raise ValueError(f"Foreign or drive-relative resource path: {value!r}")
    return _no_links(candidate if candidate.is_absolute() else base / candidate)


class _Closure:
    def __init__(self, cwd: Path, policy=None, *, root: Path | None = None, reader=None):
        self.cwd = cwd
        self.root = root
        self.policy = dict(policy or {})
        self.used_policy: set[str] = set()
        self.nodes: dict[tuple, dict] = {}
        self.active: set[tuple] = set()
        self.source_receipts: dict[Path, str] = {}
        self.source_bases: dict[Path, Path] = {}
        self.total = 0
        self.read = reader or _read
        self.macro_depth = 0
        self.macro_mode = "hierarchical"
        self.macro_effects = {}

    def add(self, path: Path, role: str, *, raw: bytes | None = None, mode: str = "hierarchical", base: Path | None = None) -> str:
        path = _no_links(path)
        base = self.source_bases.get(path, base)
        if self.root is not None:
            try:
                relative = path.relative_to(self.root).as_posix()
            except ValueError as exc:
                raise ValueError(f"Resource escapes bundle: {path}") from exc
            _member(relative)
        captured = raw is not None
        if raw is None:
            raw = self.read(path)
            sha = digest(raw)
            previous = self.source_receipts.setdefault(path, sha)
            if previous != sha:
                raise ValueError(f"Resource changed during collection: {path}")
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError(f"Resource exceeds size limit: {path}")
        if role == "reference" and path.suffix.lower() not in {".csv", ".tsv", ".txt", ".json"}:
            raise ValueError(f"Unsupported physical reference format: {path}")
        if raw.startswith((b"MZ", b"\x7fELF")):
            raise ValueError(f"Executable binary is not a distributable input: {path}")
        if role not in {"stl", "random_state"}:
            _reject_sensitive_text(raw.decode("utf-8"), role)
        key = (path, role, digest(raw), mode if role in {"geometry", "macro"} else "", base)
        if key in self.active or len(self.active) >= 64:
            raise ValueError(f"Cyclic or excessively deep resource closure: {path}")
        if key in self.nodes:
            if role == "macro" and self.macro_depth:
                self.macro_mode = self.macro_effects[key]
            return self.nodes[key]["path"]
        if len(self.nodes) >= MAX_MEMBERS - 4:
            raise ValueError("Bundle member limit exceeded")
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", path.name).strip("._") or "input"
        relative = relative if self.root is not None else f"resources/r{len(self.nodes):04d}-{name}"
        decision = self.policy.get(str(path), {})
        if str(path) in self.policy:
            self.used_policy.add(str(path))
        if type(decision) is not dict or set(decision) - {"distribution", "allow_redistribution"}:
            raise ValueError(f"Invalid resource policy: {path}")
        distribution = decision.get("distribution", "unknown")
        if distribution not in {"unknown", "permitted", "restricted"} or type(decision.get("allow_redistribution", False)) is not bool:
            raise ValueError(f"Invalid distribution decision: {path}")
        if distribution == "restricted" and decision.get("allow_redistribution") is not True:
            raise ValueError(f"Restricted resource requires explicit redistribution policy: {path}")
        node = {"path": relative, "role": role, "source_sha256": digest(raw),
                "captured_text": captured, "distribution": distribution,
                "redistribution_override": decision.get("allow_redistribution", False)}
        self.nodes[key] = node
        self.active.add(key)
        try:
            if role in {"main", "materials", "geometry"}:
                data = self.ini(raw.decode("utf-8"), path, relative, role, mode, base).encode("utf-8")
            elif role == "macro":
                data = self.macro(raw.decode("utf-8-sig"), path, relative, mode).encode("utf-8")
                self.macro_effects[key] = self.macro_mode
            elif role == "gdml":
                data = self.gdml(raw, path)
            else:
                data = raw
            self.total += len(data)
            if self.total > MAX_TOTAL_BYTES:
                raise ValueError("Bundle total size limit exceeded")
            node["data"] = data
        finally:
            self.active.remove(key)
        return relative

    def ref(self, value: str, base: Path, role: str, owner: str, *, local=False, mode="hierarchical") -> str:
        target = self.add(_resolve(value, base), role, mode=mode)
        # All resources occupy one directory. No '..' is needed for any input.
        return PurePosixPath(target).name if local else target

    def ini(self, text, path, relative, role, mode, base=None):
        lines, sections, fields = _scan(text, str(path))
        values = {(f.section.lower(), f.key.lower()): f.value for f in fields}
        if role == "main":
            mode = values.get(("geometry", "template"), values.get(("geometry", "templatename"), "simple_box"))
            mode = TEMPLATE_ALIASES.get(mode.lower(), mode.lower())
            version = values.get(("general", "schema_version"), "1")
            if version != "1":
                raise ValueError(f"Unsupported main INI version: {path}: {version}")
        schema_file = "main_ini" if role == "main" else "materials_ini" if role == "materials" else f"geometry_{TEMPLATE_ALIASES.get(mode, mode)}_ini"
        if role == "geometry" and values.get(("global", "version"), "1") not in {"1", "2"}:
            raise ValueError(f"Unsupported geometry version: {path}")
        for section, line in sections:
            if not section_spec(section, schema_file):
                raise ValueError(f"Unknown resource grammar: {path}:{line + 1} [{section}]")
        for f in fields:
            section, key, value = f.section.lower(), f.key.lower(), f.value
            descriptor = spec(section, key, schema_file)
            if descriptor is None:
                raise ValueError(f"Unknown resource grammar: {path}:{f.line + 1} [{f.section}]/{f.key}")
            replace = None
            if role == "main":
                if section == "materials" and key in {"file", "materialfile", "config", "configfile"}:
                    replace = self.ref(value, self.cwd, "materials", relative)
                elif section == "geometry" and key in {"config", "configfile"}:
                    replace = self.ref(value, self.cwd, "geometry", relative, mode=mode)
                elif section == "run" and key == "macro":
                    replace = self.ref(value, self.cwd, "macro", relative, mode=mode)
                elif (section == "source" or section.startswith("source.")) and key == "spectrum_file":
                    replace = self.ref(value, path.parent, "spectrum", relative, local=True)
                elif section == "source" and key == "phase_space_file":
                    parts = [part.strip(_SPACE) for part in value.split(",")]
                    if not all(parts):
                        raise ValueError(f"Empty phase-space resource: {path}:{f.line + 1}")
                    replace = ",".join(self.ref(p, path.parent, "phase_space", relative, local=True) for p in parts)
                elif section == "scoring.displacement":
                    replace = self.ref(value, path.parent, "niel", relative, local=True)
                elif (section == "field" or section.startswith("field.")) and key in {"magnetic_map", "electric_map"}:
                    replace = self.ref(value, path.parent, "field_map", relative, local=True)
                elif section == "output" and key in {"dir", "outputdir"}:
                    replace = "output"
            elif role == "geometry" and key in {"file", "copies_file"}:
                child_role = "copies" if key == "copies_file" else "gdml" if section == "gdml" else "stl"
                replace = self.ref(value, base or path.parent, child_role, relative, local=True)
            if replace is None and (descriptor.data.get("type") in {"path", "file", "existing_file"}
                                    or descriptor.data.get("path_base")):
                raise ValueError(f"Unclassified resource field: {path}:{f.line + 1} [{f.section}]/{f.key}")
            if replace is not None:
                raw = lines[f.line]
                lines[f.line] = raw[:f.value_start] + replace + raw[f.value_end:]
        return "".join(lines).replace("\r\n", "\n")

    def macro(self, text, path, relative, mode):
        if not self.macro_depth:
            self.macro_mode = mode
        self.macro_depth += 1
        try:
            return self._macro(text, path, relative)
        finally:
            self.macro_depth -= 1

    def _macro(self, text, path, relative):
        result = []
        for number, line in enumerate(text.split("\n"), 1):
            # Same quote-aware # comment rule as MacroPreflight.
            quote = ""
            end = len(line)
            for i, char in enumerate(line):
                if quote:
                    if char == quote:
                        quote = ""
                elif char in "\"'":
                    quote = char
                elif char == "#":
                    end = i
                    break
            statement = line[:end].strip(_SPACE)
            if not statement:
                result.append(line.rstrip("\r"))
                continue
            parts = re.split(r"[ \t]+", statement, maxsplit=1)
            command, args = parts[0], parts[1].strip(_SPACE) if len(parts) == 2 else ""
            where = f"{path}:{number} {command}"
            if any(c in statement for c in "{}$"):
                raise ValueError(f"Dynamic macro grammar refused: {where}")
            if command in _INPUT_COMMANDS:
                if args[:1] in {"'", '"'}:
                    if len(args) < 2 or args[-1] != args[0] or args[0] in args[1:-1]:
                        raise ValueError(f"Ambiguous macro input: {where}")
                    args = args[1:-1]
                if not args and command == "/random/resetEngineFrom":
                    args = "currentRun.rndm"
                role = _INPUT_COMMANDS[command]
                base = path.parent if command == "/control/execute" else self.cwd
                target = self.ref(args, base, role, relative, local=command == "/control/execute", mode=self.macro_mode)
                result.append(f"{command} {target}")
            elif command in _VALUE_COMMANDS:
                if any(c in args for c in "\\/") or re.search(r"\b\S+\.(?:ini|mac|csv|stl|gdml|rndm|dat|txt)\b", args, re.I):
                    raise ValueError(f"Unclassified macro resource argument: {where}")
                result.append(statement)
                if command == "/AIHL/geometry/setTemplate":
                    self.macro_mode = TEMPLATE_ALIASES.get(args.lower(), args.lower())
            else:
                raise ValueError(f"Unknown resource command grammar: {where}")
        return "\n".join(result)

    def gdml(self, raw, path):
        # Xerces can resolve DTDs, schemas, entities and module files. Only a
        # self-contained document is currently closed without invoking Xerces.
        # Reject unsupported dependency syntax rather than shipping an open set.
        text = raw.decode("utf-8")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I):
            raise ValueError(f"GDML external entity/DTD grammar refused: {path}")
        tree = ET.fromstring(text)
        if tree.tag != "gdml":
            raise ValueError(f"Unsupported GDML root/namespace: {path}")
        for item in tree.iter():
            if item.tag == "file" or "}" in item.tag or any(k.rsplit("}", 1)[-1] in {"schemaLocation", "noNamespaceSchemaLocation", "href"} for k in item.attrib):
                raise ValueError(f"GDML module/schema/include dependency requires unsupported grammar: {path}")
        return raw


def _snapshot_paths(data, closure: _Closure, *, loading=False):
    """Relocate the existing codec payload; do not introduce a project model."""
    p, state = data["project"], data["state"]
    base = closure.cwd

    def resource(value, role, mode="hierarchical"):
        if not value:
            return ""
        target = closure.add(_resolve(value, base), role, mode=mode)
        return str(closure.root / target) if loading else target

    # F5 projects raw path drafts after typed model fields. Keep their
    # association across relocation, without accepting a different/invalid draft.
    def path_bindings():
        return {
            "project.config_path": p["configPath"],
            "project.macro_path": p["macroPath"],
            "config.materials_config": p["pathSettings"]["materials_config"],
            "config.geometry_config": (p["geometrySettings"]["config_path"]
                                       or p["pathSettings"]["geometry_config"]),
        }
    original_paths = path_bindings() if loading else {}
    mode = p["geometrySettings"]["template"]
    for key, role in (("configPath", "main"), ("macroPath", "macro")):
        # generated config/macro are stale run artefacts, not its editable input.
        p[key] = resource(p[key], role, mode) if p["runInputMode"] == "external" else ""
    paths = p["pathSettings"]
    for owner, key, role in ((paths, "materials_config", "materials"), (paths, "geometry_config", "geometry"),
                              (p["geometrySettings"], "config_path", "geometry")):
        owner[key] = resource(owner[key], role, mode)
    for kind, doc in (("materials", p["materialEditor"]), ("geometry", p["geometryEditor"])):
        if doc is None:
            continue
        role = kind
        source = state["sources"].get(kind)
        anchor = doc.get("source_path", "") or (source or {}).get("path", "")
        raw = doc.get("raw_source_text", "")
        if anchor:
            original = _resolve(anchor, base)
            target = closure.add(original, role, raw=raw.encode("utf-8") if raw else None, mode=mode)
            node = next(n for n in closure.nodes.values() if n["path"] == target)
            doc["source_path"] = str(closure.root / target) if loading else target
            if raw:
                doc["raw_source_text"] = node["data"].decode("utf-8")
            if source is not None:
                source["path"] = doc["source_path"]
                source["text"] = doc.get("raw_source_text", "")
        elif raw:
            raise ValueError(f"Captured {kind} source text has no resource anchor")
        # Preview-only STL/copies fields still reference real resources.
        def properties(value):
            if isinstance(value, (dict, list)):
                if id(value) in seen_properties:
                    return
                seen_properties.add(id(value))
            if isinstance(value, dict):
                for key, item in list(value.items()):
                    if key in {"file", "file.resolved", "copies_file"} and isinstance(item, str) and item:
                        origin = _resolve(item, base if loading else original.parent if anchor else base)
                        target = closure.add(origin, "copies" if key == "copies_file" else "stl")
                        value[key] = str(closure.root / target) if loading else target
                    elif key not in {"source_path", "raw_source_text"}:
                        properties(item)
            elif isinstance(value, list):
                for item in value:
                    properties(item)
        if kind == "geometry":
            seen_properties = set()
            properties(doc)
    for key in _PRIVATE:
        if key in p:
            p[key] = ""
        if key in paths:
            paths[key] = ""
    for doc in (p["materialEditor"], p["geometryEditor"]):
        if doc is not None:
            doc["generated_path"] = ""
    state["selections"] = {}
    for key, value in list(state["drafts"].items()):
        token = re.sub(r"[^a-z]", "", key.lower())
        if _SECRET.search(key) and value not in (None, ""):
            raise ValueError(f"Credential raw draft cannot be bundled: {key}")
        if any(x in token for x in ("executable", "workspaceroot", "runsroot", "outputdir")):
            del state["drafts"][key]
        # Remaining raw drafts pass the same logical-path/privacy sanitizer as
        # captured sources and historical evidence after closure is complete.
    if loading:
        relocated_paths = path_bindings()
        for binding, original in original_paths.items():
            raw = state["drafts"].get(binding)
            if not original or not isinstance(raw, str) or not raw.strip():
                continue
            try:
                same_resource = _resolve(raw.strip(), base) == _resolve(original, base)
            except (OSError, ValueError):
                same_resource = False
            if same_resource:
                # Preserve lexical whitespace; only the verified resource anchor
                # moves. Other raw drafts retain their original rejection semantics.
                start, end = len(raw) - len(raw.lstrip()), len(raw.rstrip())
                state["drafts"][binding] = raw[:start] + relocated_paths[binding] + raw[end:]
        p["workspaceRoot"] = paths["workspace_root"] = str(closure.root)
        p["runsRoot"] = paths["runs_root"] = str(closure.root.parent / (closure.root.name + "-runs"))
    return data


def _reject_sensitive_text(value, key):
    # Geant4's public build version is a literal expanded source keyword, not
    # an environment substitution. Preserve that exact, closed numeric form.
    if key.rsplit(".", 1)[-1] == "geant4_version" and re.fullmatch(
            r"\$Name: geant4-[0-9]{2}-[0-9]{2}(?:-patch-[0-9]{2})?(?: \[MT\])?\$", value):
        return
    if (re.search(r"%[A-Za-z_][A-Za-z0-9_]*%|\$(?:env:|\{|[A-Za-z_])|os\.environ", value)
            or re.search(r"(?:password|passwd|api[_-]?key|(?:access[_-]?)?token|secret|credential)\s*[:=]\s*\S+", value, re.I)
            or re.search(r"https?://[^/\s]+@|\bBearer\s+\S+|BEGIN (?:[A-Z]+ )?PRIVATE KEY", value, re.I)):
        raise ValueError(f"Environment/credential text cannot be bundled: {key}")


def _environment_facts(value, shape=_ENV_PROJECTION, *, key="environment"):
    """Project safe historical facts without accepting arbitrary env mappings."""
    if isinstance(shape, dict):
        if type(value) is not dict or any(type(name) is not str for name in value):
            raise ValueError(f"Invalid environment fact object: {key}")
        return {name: _environment_facts(value[name], child, key=f"{key}.{name}")
                for name, child in shape.items() if name in value}
    if isinstance(shape, list):
        if type(value) is not list:
            raise ValueError(f"Invalid environment fact list: {key}")
        return [_environment_facts(item, shape[0], key=f"{key}[]") for item in value]
    if type(value) not in shape:
        raise ValueError(f"Invalid environment fact scalar: {key}")
    # Even allowlisted strings are untrusted. No host path is needed here, so
    # unlike input resources they must not be mapped into logical filenames.
    value = _privacy(value, [], key=key)
    if key.endswith(".env") and not re.fullmatch(r"[A-Z_][A-Z0-9_]*", value):
        raise ValueError("Invalid dataset environment identifier")
    if key.endswith(".selected_path_sha256") and value is not None and not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Invalid dataset selected path SHA256")
    return value


def _mask_source_url(match):
    """Hide only a complete HTTP(S) URL from the path-detection copy."""
    value = match.group(0)
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port  # Invalid port syntax/range must not be masked.
    except ValueError:
        return value
    if (not host or parsed.username is not None or parsed.password is not None
            or re.search(r"[\\\x00-\x20\x7f]|%(?![0-9a-fA-F]{2})", value)
            or re.search(r"[A-Za-z]:[\\/]", value.split("://", 1)[1])
            or not re.fullmatch(r"[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]+", value)):
        return value
    if ":" not in host and not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
                                     for label in host.rstrip(".").split(".")):
        return value
    return "<source-url>"


def _privacy(value, mapping, *, key="", environment=False):
    """Map known resources; reject unknown private text rather than guessing."""
    if environment:
        return _environment_facts(value)
    if isinstance(value, dict):
        result = {}
        for name, item in value.items():
            if not isinstance(name, str):
                raise ValueError("Bundle records require string object keys")
            if _SECRET.search(name) and item not in (None, "", {}, []):
                raise ValueError(f"Credential field cannot be bundled: {name}")
            if name in _PRIVATE or name in {"env", "environ", "environment_variables", "environmentVariables", "QSettings", "user_settings", "userSettings"}:
                # Fixed project fields retain their types; history fields are
                # visibly removed, never exported verbatim.
                result[name] = "" if isinstance(item, str) else {} if isinstance(item, dict) else [] if isinstance(item, list) else None
            else:
                result[name] = _privacy(item, mapping, key=name,
                    environment=name in {"environment", "environment_facts"})
        return result
    if isinstance(value, (list, tuple)):
        return [_privacy(item, mapping, key=key, environment=environment) for item in value]
    if not isinstance(value, str):
        return value
    for original, logical in mapping:
        value = re.sub(re.escape(original) + r"(?=$|[\s\"'#;,<>\]\):}])", lambda _: logical, value)
    _reject_sensitive_text(value, key)
    # Keep the exported text intact. URL scheme suffixes such as 's:/' are
    # not drive paths; credentials have already been checked on the full text.
    path_text = re.sub(r"(?<![\w:/\\])https?://[^\s<>\"']+", _mask_source_url, value, flags=re.I)
    if re.search(r"[A-Za-z]:[\\/]|\\\\[^\\\s]+\\", path_text):
        raise ValueError(f"Private path cannot be bundled: {key}")
    # Geant4 commands are logical protocol names, not host paths. Other absolute
    # strings (including an unclassified raw path draft) must be identified first.
    without_commands = path_text.replace("</", "<closing-tag-")
    without_commands = re.sub(r"\[[A-Za-z_][A-Za-z0-9_.+-]*\]/[A-Za-z_][A-Za-z0-9_.+-]*", "<ini-field>", without_commands)
    for command in sorted(_VALUE_COMMANDS | set(_INPUT_COMMANDS), key=len, reverse=True):
        without_commands = without_commands.replace(command, "<geant4-command>")
    if re.search(r"(?<![\w./])/(?:[^\s\"'<>:;,=)]+)", without_commands):
        raise ValueError(f"Unclassified absolute private path in bundled text: {key}")
    return value


def _references(records, closure):
    records = copy.deepcopy(list(records))
    def visit(value, reference=False):
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if (key in {"reference_file", "reference_path"} or reference and key in {"path", "file"}) and isinstance(item, str) and item:
                    path = _resolve(item, closure.cwd)
                    logical = closure.add(path, "reference")
                    raw_sha = digest(closure.read(path))
                    recorded = value.get("sha256", value.get("reference_sha256"))
                    if recorded is not None and recorded != raw_sha:
                        raise ValueError(f"Physical reference hash changed: {path}")
                    value[key] = logical
                    value["reference_sha256" if key.startswith("reference_") else "sha256"] = raw_sha
                else:
                    visit(item, reference or key in {"reference", "reference_data", "reference_input"})
        elif isinstance(value, list):
            for item in value:
                visit(item, reference)
    visit(records)
    return records


def _collected(snapshot, validation_records, resource_policy):
    data = snapshot_to_dict(snapshot)
    p = snapshot.project
    cwd = _no_links(Path(p.workspaceRoot or p.pathSettings.workspace_root or Path.cwd()))
    closure = _Closure(cwd, resource_policy)
    data = _snapshot_paths(data, closure)
    records = _references(validation_records, closure)
    return data, records, closure


def _finish_collection(data, records, closure):
    mapping = []
    for (path, *_), node in closure.nodes.items():
        for spelling in {str(path), path.as_posix()}:
            mapping.append((spelling, node["path"]))
    mapping.sort(key=lambda pair: len(pair[0]), reverse=True)
    for node in closure.nodes.values():
        if node["role"] not in {"stl", "random_state"}:
            cleaned = _privacy(node["data"].decode("utf-8"), mapping, key=node["role"]).encode("utf-8")
            if node["role"] not in {"main", "materials", "geometry", "macro", "gdml"} and cleaned != node["data"]:
                raise ValueError(f"Data resource contains private paths; bytes must not be rewritten: {node['path']}")
            node["data"] = cleaned
    data = _privacy(data, mapping)
    records = _privacy(records, mapping)
    if set(closure.policy) != closure.used_policy:
        raise ValueError("Unused resource policy entries: " + ", ".join(sorted(set(closure.policy) - closure.used_policy)))
    return data, records


def collect_bundle_resources(snapshot: WorkspaceSnapshot, *, validation_records=(), resource_policy=None) -> dict:
    """Read the shared resource grammar, without publishing or running anything.

    ``resources`` records have logical path, role, source_sha256, sha256 (relocated
    bytes), distribution and captured_text. Absolute filenames are intentionally
    absent; use sha256/role for content identity. ``snapshot`` is the portable F5
    codec object. Physical reference records use reference_file/reference_path,
    or reference: {path/file, sha256}; supplied SHA must match the actual file.
    """
    data, records, closure = _collected(snapshot, validation_records, resource_policy)
    data, records = _finish_collection(data, records, closure)
    for path, sha in closure.source_receipts.items():
        if digest(_read(path)) != sha:
            raise ValueError(f"Resource changed during identity collection: {path}")
    return {"snapshot": data, "validation_records": records,
            "resources": [{**{k: v for k, v in node.items() if k != "data"},
                           "sha256": digest(node["data"]), "bytes": len(node["data"])}
                          for node in closure.nodes.values()]}


def _write(path: Path, raw: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _publish_directory(source: Path, destination: Path):
    """Exclusive atomic directory rename; fail closed on unsupported systems."""
    if sys.platform == "win32":
        os.rename(source, destination)  # Windows refuses even an empty target.
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            raise OSError(errno.ENOSYS, "Atomic no-replace directory publication unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(destination))
    else:
        raise OSError(errno.ENOSYS, "Atomic no-replace directory publication unavailable")


_REPLAY = b'''"""Delegate replay to the installed unified CLI; no backend orchestration here."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "g4usim_gui.experiment_cli",
        "--bundle", str(Path(__file__).resolve().parent), *sys.argv[1:]]))
'''


def export_bundle(snapshot: WorkspaceSnapshot, destination: Path, *, validation_records=(), resource_policy=None) -> dict:
    """Export to a new directory. No overwrite, backend execution or input writes.

    Generated mode calls create_run_package in private staging; it retains that
    writer's existing validation and selected-executable requirement. Temporary
    run-package snapshots/logs/outputs are discarded; only selected input files
    and validation records are included.
    """
    # Capture this before creating staging so failure has no durable side effects.
    portable, records, closure = _collected(snapshot, validation_records, resource_policy)
    target = _no_links(Path(destination).absolute())
    if os.path.lexists(target):
        raise FileExistsError(f"Bundle destination already exists: {target}")
    if not target.parent.is_dir():
        raise ValueError(f"Bundle destination parent does not exist: {target.parent}")
    p = snapshot.project
    cwd = closure.cwd
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.k1-", dir=target.parent))
    committed = False
    try:
        replay_inputs = {"config": portable["project"]["configPath"], "macro": portable["project"]["macroPath"], "working_directory": "."}
        if p.runInputMode == "generated":
            from g4usim_gui.writers.package_writer import create_run_package
            writer = copy.deepcopy(p)
            writer.pathSettings.runs_root = str(staging / "writer")
            package, _ = create_run_package(project=writer, paths=writer.pathSettings, run=writer.runSettings,
                geometry=writer.geometrySettings, source=writer.sourceSettings, physics=writer.physicsSettings,
                scoring=writer.scoringSettings, material_document=writer.materialEditor,
                geometry_document=writer.geometryEditor, source_model=writer.sourceEditor,
                physics_model=writer.physicsEditor, scoring_model=writer.scoringEditor)
            # Copied geometry's relative children retain the ORIGINAL file base.
            geom_base = _resolve(p.geometrySettings.config_path or p.pathSettings.geometry_config, cwd).parent
            original_geom = Path(package.geometry_ini_path)
            closure.source_bases[original_geom] = geom_base
            main = closure.add(Path(package.main_ini_path), "main")
            macro = closure.add(Path(package.run_macro_path), "macro", mode=p.geometrySettings.template)
            replay_inputs.update(config=main, macro=macro)
            shutil.rmtree(staging / "writer")
        elif not (replay_inputs["config"] or replay_inputs["macro"]):
            raise ValueError("External bundle needs a config or macro input")
        portable, records = _finish_collection(portable, records, closure)
        files = [(node["path"], node["data"], {k: v for k, v in node.items() if k != "data"}) for node in closure.nodes.values()]
        files += [("workspace.json", snapshot_to_json(snapshot_from_dict(portable)), {"role": "snapshot"}),
                  ("validation_records.json", _json({"schema": "g4usim_bundle_validation_history_v1", "records": records}), {"role": "validation_history"}),
                  ("replay.py", _REPLAY, {"role": "replay_entry"})]
        members = []
        for name, raw, details in files:
            _member(name)
            _write(staging / name, raw)
            members.append({**details, "path": name, "sha256": digest(raw), "bytes": len(raw)})
        manifest = {"schema": BUNDLE_SCHEMA, "version": BUNDLE_VERSION, "snapshot": "workspace.json",
                    "validation_history": "validation_records.json", "replay_entry": "replay.py",
                    "replay_inputs": replay_inputs, "replay_verified": False,
                    "members": members, "integrity": "sha256_not_signature",
                    "history_trust": "stale_requires_revalidation", "outputs_included": False}
        _write(staging / "manifest.json", _json(manifest))
        result = inspect_bundle(staging)
        for path, sha in closure.source_receipts.items():
            # Writer intermediates were deliberately discarded above.
            # Check lexical components before resolving the 8.3/long spellings;
            # an external receipt replaced by a link must still be rejected.
            if _no_links(path).resolve().is_relative_to(_no_links(staging).resolve()):
                continue
            if digest(_read(path)) != sha:
                raise ValueError(f"Resource changed before publication: {path}")
        _publish_directory(staging, target)
        committed = True
        result["path"] = str(target)
        return result
    finally:
        if not committed and staging.exists():
            shutil.rmtree(staging)


def _verified_bundle(path):
    """Read each member once; all parsing consumes those exact verified bytes."""
    root = _no_links(Path(path).absolute())
    manifest_raw = _read(root / "manifest.json")
    manifest = load_json_strict(manifest_raw)
    expected = {"schema", "version", "snapshot", "validation_history", "replay_entry", "replay_inputs",
                "replay_verified", "members", "integrity", "history_trust", "outputs_included"}
    if (type(manifest) is not dict or set(manifest) != expected or manifest["schema"] != BUNDLE_SCHEMA
            or type(manifest["version"]) is not int or manifest["version"] != BUNDLE_VERSION):
        raise ValueError("Unsupported bundle manifest schema/version/fields")
    if (manifest["snapshot"] != "workspace.json" or manifest["validation_history"] != "validation_records.json"
            or manifest["replay_entry"] != "replay.py" or manifest["replay_verified"] is not False
            or manifest["outputs_included"] is not False or manifest["history_trust"] != "stale_requires_revalidation"
            or manifest["integrity"] != "sha256_not_signature"):
        raise ValueError("Invalid bundle trust or entry contract")
    entries = manifest["members"]
    if type(entries) is not list or not 3 <= len(entries) <= MAX_MEMBERS:
        raise ValueError("Invalid bundle member count")
    names, folded, roles, contents = set(), set(), {}, {}
    total = 0
    for entry in entries:
        if type(entry) is not dict or set(entry) - {"path", "role", "source_sha256", "captured_text", "distribution", "redistribution_override", "sha256", "bytes"}:
            raise ValueError("Invalid bundle member fields")
        name = _member(entry.get("path"))
        if name not in {"workspace.json", "validation_records.json", "replay.py"} and not name.startswith("resources/"):
            raise ValueError(f"Member outside the allowed input/entry whitelist: {name}")
        if name == "manifest.json" or name.casefold() in folded:
            raise ValueError("Duplicate/colliding bundle member")
        folded.add(name.casefold())
        names.add(name)
        roles[name] = entry.get("role")
        size = entry.get("bytes")
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            raise ValueError(f"Invalid resource size: {name}")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Bundle total size limit exceeded")
        raw = _read(root / name)
        if len(raw) != size or digest(raw) != entry.get("sha256"):
            raise ValueError(f"Bundle hash/size mismatch: {name}")
        contents[name] = raw
        if name.startswith("resources/"):
            if (entry.get("role") not in _ROLES or entry.get("distribution") not in {"unknown", "permitted", "restricted"}
                    or type(entry.get("redistribution_override")) is not bool
                    or (entry["distribution"] == "restricted" and not entry["redistribution_override"])
                    or not re.fullmatch("[0-9a-f]{64}", entry.get("source_sha256", ""))
                    or type(entry.get("captured_text")) is not bool):
                raise ValueError(f"Invalid resource distribution/source receipt: {name}")
    actual = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            _no_links(Path(directory) / name)
        for name in files:
            actual.add((Path(directory) / name).relative_to(root).as_posix())
    if actual != names | {"manifest.json"}:
        raise ValueError("Bundle contains missing or unlisted files")
    if not {"workspace.json", "validation_records.json", "replay.py"} <= names:
        raise ValueError("Bundle required members missing")
    def frozen_read(path):
        try:
            name = _no_links(path).relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Resource escapes verified bundle: {path}") from exc
        if name not in contents:
            raise ValueError(f"Resource absent from verified bundle members: {name}")
        return contents[name]
    if contents["replay.py"] != _REPLAY:
        raise ValueError("Bundle replay entry is not the unified CLI delegate")
    data = snapshot_to_dict(snapshot_from_json(contents["workspace.json"]))
    portable = copy.deepcopy(data)
    if _privacy(data, []) != data:
        raise ValueError("Bundle snapshot contains private machine fields")
    replay = manifest["replay_inputs"]
    if type(replay) is not dict or set(replay) != {"config", "macro", "working_directory"} or replay["working_directory"] != ".":
        raise ValueError("Invalid bundle replay inputs")
    closure = _Closure(root, root=root, reader=frozen_read)
    for key, role in (("config", "main"), ("macro", "macro")):
        if replay[key]:
            name = _member(replay[key])
            if name not in names or roles[name] != role:
                raise ValueError("Invalid replay input member/role")
            closure.add(root / name, role, mode=data["project"]["geometrySettings"]["template"])
    _snapshot_paths(data, closure, loading=True)
    history = load_json_strict(contents["validation_records.json"])
    if (type(history) is not dict or set(history) != {"schema", "records"}
            or history["schema"] != "g4usim_bundle_validation_history_v1" or type(history["records"]) is not list):
        raise ValueError("Invalid bundle validation history")
    if _privacy(history, []) != history:
        raise ValueError("Bundle history contains private environment/credential fields")
    _references(history["records"], closure)
    for node in closure.nodes.values():
        if node["path"] not in names or roles[node["path"]] != node["role"]:
            raise ValueError(f"Resource not registered with its actual role: {node['path']}")
        raw = contents[node["path"]]
        if node["data"] != raw:
            raise ValueError(f"Captured source or resource closure disagrees with member bytes: {node['path']}")
        if node["role"] not in {"stl", "random_state"}:
            if _privacy(raw.decode("utf-8"), []) != raw.decode("utf-8"):
                raise ValueError(f"Resource contains private fields: {node['path']}")
    registered = {name for name in names if name.startswith("resources/")}
    if registered != {node["path"] for node in closure.nodes.values()}:
        raise ValueError("Bundle contains resources outside the referenced closure")
    for name, role in {"workspace.json": "snapshot", "validation_records.json": "validation_history", "replay.py": "replay_entry"}.items():
        if roles[name] != role:
            raise ValueError(f"Incorrect required member role: {name}")
    return {"path": str(root), "manifest": manifest, "manifest_sha256": digest(manifest_raw),
            "validation_records": [{"record": r, "stale": True, "stale_reason": "bundle_loaded_requires_revalidation"} for r in history["records"]],
            "replay_inputs": copy.deepcopy(replay), "replay_verified": False}, portable, contents


def inspect_bundle(path) -> dict:
    """Verify all members and supported input closure; return stale history."""
    return _verified_bundle(path)[0]


def load_bundle(path, *, executable="") -> WorkspaceSnapshot:
    """Load an integrity-checked F5 snapshot, with historical evidence stale."""
    result, data, contents = _verified_bundle(path)
    root = Path(result["path"])
    def frozen_read(path):
        name = _no_links(path).relative_to(root).as_posix()
        if name not in contents:
            raise ValueError(f"Resource absent from verified load: {name}")
        return contents[name]
    _snapshot_paths(data, _Closure(root, root=root, reader=frozen_read), loading=True)
    data["project"]["executable"] = data["project"]["pathSettings"]["executable"] = str(executable)
    snapshot = snapshot_from_dict(data)
    snapshot.transient["bundle"] = result
    return snapshot
