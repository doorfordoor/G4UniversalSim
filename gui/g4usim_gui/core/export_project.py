"""K2-2: export a supported Geant4 project as a standalone source tree.

This module is deliberately Qt-free: the desktop window and the command line
call the same implementation.  It solves one narrow problem and refuses
everything else:

* two supported project shapes (S-A: the repository's example 07 external
  project; S-B: the current generated single-target package);
* a self-describing payload (template source tree, project inputs, licenses,
  notices, README and manifest) that builds and runs from the export root;
* an auditable identity (template manifest digest, exported file list and a
  content identity over those files).

It is not a general project generator, packaging pipeline or physics checker.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable

from g4usim_gui.core import experiment_bundle as _bundle
from g4usim_gui.core.install_layout import application_root


# ---------------------------------------------------------------------------
# Contract constants and error codes
# ---------------------------------------------------------------------------

TEMPLATE_MANIFEST_SCHEMA = "g4usim_export_template_manifest"
TEMPLATE_MANIFEST_VERSION = 1
TEMPLATE_MANIFEST_NAME = "export_template_manifest.json"
TEMPLATE_MANIFEST_COPY = "export-template-manifest.json"

MANIFEST_SCHEMA = "g4usim_export_project"
MANIFEST_VERSION = 1
MANIFEST_NAME = "export-manifest.json"

TOOL_NAME = "G4UniversalSim"
TEMPLATE_IDENTITY_ALGORITHM = "sha256_sorted_sha256_path_lines_v1"
IDENTITY_ALGORITHM = "sha256_sorted_sha256_path_lines_v1"
INPUT_REWRITE_VALUES = ("verbatim", "path_rewrite", "generated")
FILE_ROLES = ("source", "header", "cmake", "tool", "schema", "doc",
              "license", "notice", "template_config", "template_macro",
              "project_config", "project_macro", "readme_export", "example")

ERROR_CODES = {
    "destination_exists": "R1",
    "destination_parent_missing": "R2",
    "linked_or_ambiguous_path": "R3",
    "selection_unavailable": "R4",
    "external_or_missing_input": "R5",
    "unsupported_feature": "R6",
    "absolute_path_remaining": "R7",
    "export_template_unavailable": "R8",
    "destination_inside_source": "R9",
    "input_changed_during_export": "R10",
    "template_identity_mismatch": "R11",
    "write_failed": "R12",
}

OUTPUT_DIRECTORY = "runs/default/output"
PROJECT_MAIN = "project/main.ini"
PROJECT_MATERIALS = "project/config/materials.ini"
PROJECT_GEOMETRY = "project/config/geometry.ini"
PROJECT_PARALLEL = "project/config/parallel.ini"
# ParallelWorldConfig resolves this value against the directory of the
# main INI, so the exported main.ini must say config/parallel.ini even
# though the copied file itself lives at project/config/parallel.ini.
PROJECT_PARALLEL_REF = "config/parallel.ini"
PROJECT_MACRO = "project/macros/run.mac"
PROJECT_README = "project/README.md"
EXPORT_README = "README-EXPORT.md"
NOTICE_FILE = "THIRD_PARTY_NOTICES.md"

GEANT4_REFERENCES = ("FTFP_BERT", "FTFP_BERT_EMZ")
ALLOWED_THREADS = (1, 2)
MAX_EVENTS = 1_000_000
MAX_INPUT_BYTES = 32 * 1024 * 1024

# main.ini whitelist.  Anything else is refused before a single byte is
# written; this is how the export stays inside the frozen S-A/S-B subset.
_MAIN_KEYS = {
    "general": {"schema_version"},
    "run": {"name", "threads", "seed", "interactive", "verbose",
            "check_overlaps", "dry_run", "macro"},
    "output": {"dir", "format"},
    "materials": {"file"},
    "geometry": {"template", "config", "check_overlaps",
                 "default_world_material"},
    "physics": {"reference", "default_cut", "biasing", "verbose"},
    "biasing": {"enabled"},
    "source": {"preset", "particle", "energy", "position_type", "position",
               "direction", "isotropic", "center", "halfx", "halfy", "radius", "shape"},
    "scoring": {"enabled", "hits", "event_edep", "edep", "let", "dose",
                "fluence", "auto_create_default_scorers", "verbose"},
    "scoring.edep": {"raw_histogram", "weighted_histogram", "bins", "min",
                     "max", "volume_summary", "particle_summary"},
    "parallel_world": {"enabled", "name", "geometry_config"},
}

_GEOMETRY_KEYS = {"shape", "size", "material", "parent", "position",
                  "rotation", "sensitive"}
_PARALLEL_KEYS = {"shape", "size", "material", "parent", "position",
                  "rotation", "sensitive"}
_MACRO_DIRECTIVES = (
    "/control/verbose",
    "/run/verbose",
    "/event/verbose",
    "/tracking/verbose",
    "/run/initialize",
    "/run/beamOn",
)

_NUMBER_RE = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")
_LENGTH_RE = re.compile(
    r"^\s*[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\s*(?:nm|um|mm|cm|m|km)\s*$",
    re.IGNORECASE,
)
_ROTATION_RE = re.compile(
    r"^\s*[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\s*(?:deg|degree|degrees|rad|mrad)?\s*$",
    re.IGNORECASE,
)
_ENERGY_RE = re.compile(
    r"^\s*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)\s*"
    r"(eV|keV|MeV|GeV)\s*$",
    re.IGNORECASE,
)
_ABSOLUTE_SCAN = (
    re.compile(r"(?i)(?:^|[\s\"'(=,:])(?:[A-Za-z]:[\\/])"),
    re.compile(r"(?i)(?:^|[\s\"'(=,:])[\\/]{2}[^\\/\s]+"),
    re.compile(r"(?i)(?:^|[\s\"'(=,:])(?:out/collab|docs/verification|"
               r"build_vs2026|build_linux|/tmp/|/home/|/root/|/Users/)"),
    re.compile(r"(?i)(?:^|[\s\"'(=,:])packaging/"),
)
_ENCODING = "utf-8"
_COMPONENT_FORBIDDEN = (
    "temperature", "pressure", "type", "components", "fraction", "density",
    "atom_count", "mass_fraction", "volume_fraction",
)
_BOOLEAN_TRUE = {"true", "yes", "on", "1"}
_BOOLEAN_FALSE = {"false", "no", "off", "0"}


def _error_code(name: str) -> str:
    return f"{ERROR_CODES[name]}-{name}".upper()


class ExportError(Exception):
    """A refusal with a stable code from the frozen contract (R1-R12)."""

    def __init__(self, kind: str, message: str, details: Iterable[str] = ()) -> None:
        if kind not in ERROR_CODES:
            raise AssertionError(f"unknown export error kind: {kind}")
        self.kind = kind
        self.code = ERROR_CODES[kind]
        self.message = message
        self.details = tuple(str(item) for item in details)
        super().__init__(f"{self.code} {kind}: {message}")


# ---------------------------------------------------------------------------
# Small, strict helpers
# ---------------------------------------------------------------------------

def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _posix(path: str | PurePosixPath) -> str:
    value = str(path)
    try:
        return _bundle._member(value)  # type: ignore[attr-defined]
    except ValueError as exc:
        raise ExportError("linked_or_ambiguous_path",
                          f"invalid exported path: {value!r}: {exc}") from exc


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       sort_keys=True, indent=2) + "\n").encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _template_member_path(value: str) -> str:
    return _posix(value)


def _read_regular(path: Path, *, kind: str, label: str) -> bytes:
    try:
        return _bundle._read(path)  # type: ignore[attr-defined]
    except ValueError as exc:
        text = str(exc)
        if "linked" in text or "reparse" in text:
            raise ExportError("linked_or_ambiguous_path", f"{label}: {path}: {text}") from exc
        raise ExportError(kind, f"{label}: {path}: {text}") from exc
    except OSError as exc:
        raise ExportError(kind, f"{label}: {path}: {exc.strerror or exc}") from exc


def _decode(raw: bytes, *, label: str) -> str:
    try:
        return raw.decode(_ENCODING)
    except UnicodeDecodeError as exc:
        raise ExportError("unsupported_feature", f"{label} is not valid UTF-8") from exc


def _no_links(path: Path, *, label: str) -> Path:
    try:
        return _bundle._no_links(path)  # type: ignore[attr-defined]
    except ValueError as exc:
        raise ExportError("linked_or_ambiguous_path", f"{label}: {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Loose INI reader used for validation and path rewriting only
# ---------------------------------------------------------------------------

@dataclass
class IniSection:
    name: str
    entries: list[tuple[str, str, int]] = None  # key(lower), value, line index

    def get(self, key: str, default: str | None = None) -> str | None:
        for entry_key, value, _line in self.entries or []:
            if entry_key == key:
                return value
        return default

    def keys(self) -> list[str]:
        return [key for key, _value, _line in self.entries or []]


@dataclass
class IniDocument:
    label: str
    lines: list[str]
    sections: dict[str, IniSection]

    def get(self, section: str, key: str, default: str | None = None) -> str | None:
        chunk = self.sections.get(section.lower())
        if chunk is None:
            return default
        return chunk.get(key, default)

    def require(self, section: str, key: str, *, kind: str = "unsupported_feature") -> str:
        value = self.get(section, key)
        if value is None or not str(value).strip():
            raise ExportError(kind, f"{self.label}: [{section}] {key} is required")
        return str(value).strip()


_KEY_LINE = re.compile(r"^(?P<prefix>[^#;=\[\]]*?)=(?P<value>.*)$")
_VALUE_LINE = re.compile(
    r"^(?P<head>[ \t]*)(?P<key>[A-Za-z0-9_.\-]+)(?P<sep>[ \t]*=[ \t]*)"
    r"(?P<value>[^#;\r\n]*?)"
    r"(?P<tail>[ \t]*(?:[#;].*)?)(?P<eol>\r?\n)?$")


def parse_ini(text: str, *, label: str) -> IniDocument:
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("\ufeff"):
        lines[0] = lines[0][1:]
    sections: dict[str, IniSection] = {}
    order: list[str] = []
    for index, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if not stripped or stripped.startswith((";", "#")):
            continue
        if stripped.startswith("["):
            if not stripped.endswith("]"):
                raise ExportError("unsupported_feature",
                                  f"{label}: malformed section header on line {index + 1}")
            name = stripped[1:-1].strip()
            if not name:
                raise ExportError("unsupported_feature",
                                  f"{label}: empty section name on line {index + 1}")
            key = name.lower()
            if key in sections:
                raise ExportError("unsupported_feature",
                                  f"{label}: duplicate declaration of section [{name}] "
                                  f"on line {index + 1}")
            sections[key] = IniSection(name, [])
            order.append(key)
            continue
        match = _KEY_LINE.match(line)
        if match is None:
            raise ExportError("unsupported_feature",
                              f"{label}: malformed setting on line {index + 1}")
        if not order:
            raise ExportError("unsupported_feature",
                              f"{label}: setting outside a section on line {index + 1}")
        section = sections[order[-1]]
        key = match.group("prefix").strip().lower()
        value = re.split(r"[#;]", match.group("value"), maxsplit=1)[0].strip()
        if not key or not re.match(r"^[a-z0-9_.-]+$", key):
            raise ExportError("unsupported_feature",
                              f"{label}: invalid key on line {index + 1}")
        if any(existing == key for existing, _v, _l in section.entries):
            raise ExportError("unsupported_feature",
                              f"{label}: duplicate key [{section.name}] {key} "
                              f"on line {index + 1}")
        section.entries.append((key, value, index))
    return IniDocument(label, lines, sections)


def _boolean(document: IniDocument, section: str, key: str, *,
             default: bool | None = None) -> bool:
    raw = document.get(section, key)
    if raw is None:
        if default is None:
            raise ExportError("unsupported_feature",
                              f"{document.label}: [{section}] {key} is required")
        return default
    value = raw.strip().lower()
    if value in _BOOLEAN_TRUE:
        return True
    if value in _BOOLEAN_FALSE:
        return False
    raise ExportError("unsupported_feature",
                      f"{document.label}: [{section}] {key} must be true or false")


def _integer(document: IniDocument, section: str, key: str, *,
             minimum: int | None = None, maximum: int | None = None,
             default: int | None = None) -> int:
    raw = document.get(section, key)
    if raw is None:
        if default is None:
            raise ExportError("unsupported_feature",
                              f"{document.label}: [{section}] {key} is required")
        return default
    if not _NUMBER_RE.match(raw.strip()):
        raise ExportError("unsupported_feature",
                          f"{document.label}: [{section}] {key} must be an integer")
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ExportError("unsupported_feature",
                          f"{document.label}: [{section}] {key} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise ExportError("unsupported_feature",
                          f"{document.label}: [{section}] {key} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ExportError("unsupported_feature",
                          f"{document.label}: [{section}] {key} must be at most {maximum}")
    return value


# ---------------------------------------------------------------------------
# Template manifest (identity source)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TemplateMember:
    path: str
    source_path: str
    role: str
    sha256: str
    bytes: int

    def to_dict(self) -> dict:
        return {"path": self.path, "source_path": self.source_path,
                "role": self.role, "sha256": self.sha256, "bytes": self.bytes}


@dataclass
class TemplateLayout:
    root: Path
    manifest_path: Path
    manifest: dict
    members: list[TemplateMember]

    @property
    def checkout(self) -> bool:
        return self.manifest_path.parent.name == "packaging"

    @property
    def identity(self) -> dict:
        return template_identity(self.members)

    def source_path(self, member: TemplateMember) -> Path:
        return self.root / (member.source_path if self.checkout else member.path)

    @property
    def label(self) -> str:
        return "repository-checkout" if self.checkout else "installed-package"


_TEMPLATE_IGNORED_PARTS = {"__pycache__", ".git", ".mypy_cache", ".pytest_cache"}
_TEMPLATE_IGNORED_SUFFIXES = (".pyc", ".pyo")


def _template_ignored(path: Path) -> bool:
    if any(part in _TEMPLATE_IGNORED_PARTS for part in path.parts):
        return True
    return path.suffix.lower() in _TEMPLATE_IGNORED_SUFFIXES


def _canonical_template_bytes(raw: bytes) -> bytes:
    """Canonical bytes of the controlled template text closure.

    The template is a text-only closure.  A checkout may materialise the same
    Git blob with CRLF or LF, so the identity and the copied bytes are defined
    over the CRLF->LF normalised content.  This applies to template members
    only: project inputs, README copies and exported output are verified as
    the raw bytes on disk.
    """
    # Universal newlines: CRLF and lone CR both become LF so checkout
    # copies, packaged copies and verify_export agree on the same bytes.
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def read_template_member_bytes(path: Path, *, kind: str, label: str) -> bytes:
    """Read one template member and return the bytes actually copied."""
    return _canonical_template_bytes(_read_regular(path, kind=kind, label=label))


def _template_root_files(root: Path) -> list[tuple[str, str, str]]:
    """(export path, repository-relative source path, role) for the template."""
    entries: list[tuple[str, str, str]] = [
        ("main.cc", "main.cc", "source"),
        ("CMakeLists.txt", "CMakeLists.txt", "cmake"),
        ("CMakePresets.json", "CMakePresets.json", "cmake"),
        ("README.md", "README.md", "doc"),
    ]
    groups = (
        ("cmake", "cmake/*.cmake"),
        ("include", "include"),
        ("src", "src"),
        ("tools", "tools"),
        ("schema", "schema"),
        ("config", "config"),
        ("macros", "macros"),
    )
    doc_files = (
        "docs/中文使用手册.md",
        "docs/Linux构建与验证.md",
        "docs/功能支持矩阵.md",
        "docs/输出数据契约.md",
    )
    license_source = Path("packaging") / "licenses"
    for export_dir, pattern in groups:
        base = root / pattern
        if pattern.endswith("*.cmake"):
            files = sorted(base.parent.glob(base.name))
        elif pattern == "tools":
            # tools/ contributes its direct members only; the repository may
            # contain local collaboration helpers under tools/<subdir>/ that
            # are not part of the portable template.
            files = sorted(path for path in base.iterdir() if path.is_file())
        else:
            files = sorted(base.rglob("*"))
        for path in files:
            if not path.is_file():
                continue
            if _template_ignored(path):
                continue
            relative = path.relative_to(root)
            role = {
                "cmake": "cmake",
                "include": "header",
                "src": "source",
                "tools": "tool",
                "schema": "schema",
                "config": "template_config",
                "macros": "template_macro",
            }[export_dir]
            entries.append((relative.as_posix(), relative.as_posix(), role))
    for name in doc_files:
        entries.append((name, name, "doc"))
    # The h2 volume-scoring component test reads this SR-NIEL table directly.
    # It is the single non-project data member of the portable template; the
    # rest of scenarios/ stays out of the closure.
    scenario_fixture = "scenarios/semiconductor/niel/si_proton.csv"
    if not (root / scenario_fixture).is_file():
        raise ExportError("export_template_unavailable",
                          f"template is missing {scenario_fixture}")
    entries.append((scenario_fixture, scenario_fixture, "example"))
    licenses = root / license_source
    if licenses.is_dir():
        for path in sorted(licenses.rglob("*")):
            if path.is_file():
                export = f"licenses/{path.name}"
                entries.append((export, (license_source / path.name).as_posix(), "license"))
    return entries


def collect_template_members(template_root: Path) -> list[TemplateMember]:
    root = Path(template_root).resolve()
    if not (root / "CMakeLists.txt").is_file():
        raise ExportError("export_template_unavailable",
                          f"template root has no CMakeLists.txt: {root}")
    members: list[TemplateMember] = []
    seen: set[str] = set()
    for export_path, source_path, role in _template_root_files(root):
        export = _template_member_path(export_path)
        if export in seen:
            raise ExportError("template_identity_mismatch",
                              f"duplicate template member: {export}")
        source = root / source_path
        raw = read_template_member_bytes(source, kind="export_template_unavailable",
                                         label="template file")
        seen.add(export)
        members.append(TemplateMember(export, source_path, role,
                                      sha256_bytes(raw), len(raw)))
    members.sort(key=lambda member: member.path)
    return members


def template_identity(members: Iterable[TemplateMember]) -> dict:
    ordered = sorted(members, key=lambda member: member.path)
    text = "".join(f"{member.sha256}  {member.path}\n" for member in ordered)
    return {
        "algorithm": TEMPLATE_IDENTITY_ALGORITHM,
        "value": sha256_bytes(text.encode("utf-8")),
        "file_count": len(ordered),
        "bytes_total": sum(member.bytes for member in ordered),
    }


def template_manifest(members: Iterable[TemplateMember]) -> dict:
    ordered = sorted(members, key=lambda member: member.path)
    return {
        "schema": TEMPLATE_MANIFEST_SCHEMA,
        "version": TEMPLATE_MANIFEST_VERSION,
        "algorithm": {
            "name": TEMPLATE_IDENTITY_ALGORITHM,
            "path_base": "export-root",
            "path_order": "ascending UTF-8 POSIX path",
            "line_format": "{sha256}  {path}\\n",
        },
        "members": [member.to_dict() for member in ordered],
        "identity": template_identity(ordered),
    }


def load_template_layout(template_root: Path | None = None) -> TemplateLayout:
    if template_root is not None:
        candidates = [Path(template_root)]
    else:
        candidates = [Path(application_root()) / "export-template",
                      Path(application_root())]
    last = None
    for candidate in candidates:
        candidate = _no_links(Path(candidate), label="export template root")
        for layout_kind, manifest_path in (
            ("packaged", candidate / TEMPLATE_MANIFEST_NAME),
            ("checkout", candidate / "packaging" / TEMPLATE_MANIFEST_NAME),
        ):
            _no_links(manifest_path, label="template manifest")
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(_read_regular(manifest_path, kind="export_template_unavailable",
                                                    label="template manifest").decode("utf-8"))
            except (OSError, ValueError) as exc:
                raise ExportError("export_template_unavailable",
                                  f"template manifest is unreadable: {manifest_path}: {exc}") from exc
            try:
                members = _validate_manifest(manifest, manifest_path)
            except ExportError as exc:
                raise
            root = candidate if layout_kind == "packaged" else manifest_path.parents[1]
            layout = TemplateLayout(root, manifest_path, manifest, members)
            _verify_template_files(layout)
            return layout
        last = candidate
    raise ExportError("export_template_unavailable",
                      f"no export template manifest under {last}")


def _validate_manifest(manifest, manifest_path: Path) -> list[TemplateMember]:
    if not isinstance(manifest, dict):
        raise ExportError("template_identity_mismatch",
                          f"template manifest is not an object: {manifest_path}")
    if manifest.get("schema") != TEMPLATE_MANIFEST_SCHEMA:
        raise ExportError("template_identity_mismatch",
                          f"unexpected template manifest schema: {manifest.get('schema')!r}")
    if manifest.get("version") != TEMPLATE_MANIFEST_VERSION:
        raise ExportError("template_identity_mismatch",
                          f"unsupported template manifest version: {manifest.get('version')!r}")
    raw_members = manifest.get("members")
    if not isinstance(raw_members, list) or not raw_members:
        raise ExportError("template_identity_mismatch",
                          "template manifest has no members")
    members: list[TemplateMember] = []
    for raw in raw_members:
        if not isinstance(raw, dict):
            raise ExportError("template_identity_mismatch",
                              "template manifest member is not an object")
        try:
            member = TemplateMember(
                path=_template_member_path(str(raw["path"])),
                source_path=_template_member_path(str(raw["source_path"])),
                role=str(raw["role"]),
                sha256=str(raw["sha256"]),
                bytes=int(raw["bytes"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExportError("template_identity_mismatch",
                              f"template manifest member is malformed: {raw!r}") from exc
        if not re.fullmatch(r"[0-9a-f]{64}", member.sha256):
            raise ExportError("template_identity_mismatch",
                              f"template manifest SHA is malformed: {member.path}")
        if member.role not in {"source", "header", "cmake", "tool", "schema",
                               "template_config", "template_macro", "doc", "license",
                               "example"}:
            raise ExportError("template_identity_mismatch",
                              f"unknown template role: {member.role}")
        members.append(member)
    if len({member.path for member in members}) != len(members):
        raise ExportError("template_identity_mismatch",
                          "template manifest repeats a path")
    ordered = sorted(members, key=lambda member: member.path)
    identity = template_identity(ordered)
    declared = manifest.get("identity") or {}
    if declared.get("value") != identity["value"]:
        raise ExportError("template_identity_mismatch",
                          "template manifest identity does not match its members")
    if declared.get("file_count") != identity["file_count"]:
        raise ExportError("template_identity_mismatch",
                          "template manifest file count does not match its members")
    return ordered


def _verify_template_files(layout: TemplateLayout) -> None:
    for member in layout.members:
        path = layout.source_path(member)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ExportError("template_identity_mismatch",
                              f"template file is missing or unreadable: "
                              f"{member.path}: {exc}") from exc
        raw = _canonical_template_bytes(raw)
        if len(raw) != member.bytes or sha256_bytes(raw) != member.sha256:
            raise ExportError("template_identity_mismatch",
                              f"template file does not match its manifest: {member.path}")


# ---------------------------------------------------------------------------
# Selections: an external project directory or the current generated project
# ---------------------------------------------------------------------------

@dataclass
class ExportSelection:
    kind: str  # "external" | "generated"
    label: str
    project_root: Path | None = None
    project: object | None = None


def select_external_project(path: Path) -> ExportSelection:
    root = Path(path).expanduser()
    if not root.is_dir():
        raise ExportError("selection_unavailable", f"project directory not found: {root}")
    root = _no_links(root, label="project directory")
    if not (root / "main.ini").is_file():
        raise ExportError("selection_unavailable",
                          f"project directory has no main.ini: {root}")
    return ExportSelection("external", root.name, project_root=root)


def select_generated_project(project) -> ExportSelection:
    if project is None:
        raise ExportError("selection_unavailable", "no current project to export")
    if getattr(project, "runInputMode", "") != "generated":
        raise ExportError("unsupported_feature",
                          "S-B export requires a generated (not external) project")
    editors = getattr(project, "geometryEditor", None)
    volumes = getattr(editors, "volumes", None)
    if not volumes:
        raise ExportError("unsupported_feature",
                          "the generated project has no geometry to export")
    if getattr(editors, "mode", "") not in {"", "hierarchical"}:
        raise ExportError("unsupported_feature",
                          "only the hierarchical single-target project is supported")
    return ExportSelection("generated", "single_target", project=project)


def selection_from_path(value: str | Path) -> ExportSelection:
    path = Path(value).expanduser()
    if path.is_dir():
        return select_external_project(path)
    if path.is_file() and path.suffix.lower() == ".json":
        from g4usim_gui.core.project import load_project
        try:
            project = load_project(path)
        except (OSError, ValueError) as exc:
            raise ExportError("selection_unavailable",
                              f"project files cannot be loaded: {path}: {exc}") from exc
        return selection_from_project(project)
    raise ExportError("selection_unavailable",
                      f"project selection must be a directory or a project JSON file: {path}")


def selection_from_project(project) -> ExportSelection:
    """Map the GUI's current project onto one of the two supported subsets."""
    if project is None:
        raise ExportError("selection_unavailable", "no current project to export")
    if getattr(project, "runInputMode", "") == "generated":
        return select_generated_project(project)
    config = getattr(project, "configPath", "") or ""
    if config:
        return select_external_project(Path(config).expanduser().parent)
    root = getattr(project, "workspaceRoot", "") or ""
    if root:
        return select_external_project(Path(root).expanduser())
    raise ExportError("selection_unavailable",
                      "the project has no input folder to export")


def project_export_problem(project) -> str:
    """Empty string when the current project can be exported, else a reason."""
    try:
        return selection_problem(selection_from_project(project))
    except ExportError as exc:
        return exc.message


def selection_problem(selection: ExportSelection) -> str:
    """Cheap, user-facing reason why the current selection cannot be exported."""
    try:
        if selection.kind == "external":
            root = selection.project_root
            assert root is not None
            for required in ("main.ini",):
                if not (root / required).is_file():
                    return f"The project folder has no {required}."
            return ""
        if selection.kind == "generated":
            editors = getattr(selection.project, "geometryEditor", None)
            if not getattr(editors, "volumes", None):
                return "Create or generate a geometry before exporting."
            if getattr(editors, "mode", "") not in {"", "hierarchical"}:
                return "Only the hierarchical single-target project can be exported."
            return ""
    except (AttributeError, OSError):
        return "The current project cannot be read."
    return "The current selection cannot be exported."


# ---------------------------------------------------------------------------
# Reading the external project (S-A)
# ---------------------------------------------------------------------------

@dataclass
class ProjectPayload:
    """Canonical project files (POSIX target paths) plus input audit entries."""

    files: dict[str, bytes]
    inputs: list[dict]
    main_text: str
    materials_text: str
    geometry_text: str
    parallel_text: str | None
    macro_text: str
    readme_text: str | None
    source_paths: dict[str, Path]


def _inside_project(root: Path, value: str, *, label: str) -> Path:
    candidate = (root / value).expanduser()
    # Guard the unfolded path first: link/../input must be refused, not folded.
    guarded = _no_links(candidate, label=label)
    try:
        guarded.relative_to(root)
    except ValueError as exc:
        raise ExportError("external_or_missing_input",
                          f"{label}: path escapes the project directory: {value}") from exc
    return guarded


def _read_external_payload(selection: ExportSelection) -> ProjectPayload:
    root = selection.project_root
    assert root is not None
    main_path = _no_links(root / "main.ini", label="main.ini")
    try:
        main_raw = main_path.read_bytes()
    except OSError as exc:
        raise ExportError("selection_unavailable",
                          f"main.ini cannot be read: {main_path}: {exc}") from exc
    if len(main_raw) > MAX_INPUT_BYTES:
        raise ExportError("external_or_missing_input", "main.ini is too large")
    main_text = _decode(main_raw, label="main.ini")
    document = parse_ini(main_text, label="main.ini")
    if "materials" not in document.sections or "geometry" not in document.sections:
        raise ExportError("selection_unavailable",
                          "main.ini must declare [materials] and [geometry]")
    if document.get("materials", "file") is None:
        raise ExportError("selection_unavailable", "main.ini has no [materials] file")
    if document.get("geometry", "config") is None:
        raise ExportError("selection_unavailable", "main.ini has no [geometry] config")

    def load(relative: str, label: str) -> tuple[str, Path, bytes]:
        path = _inside_project(root, relative, label=label)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ExportError("external_or_missing_input",
                              f"{label} cannot be read: {path}: {exc}") from exc
        if len(raw) > MAX_INPUT_BYTES:
            raise ExportError("external_or_missing_input", f"{label} is too large")
        return _decode(raw, label=label), path, raw

    materials_text, materials_path, materials_raw = load(
        str(document.get("materials", "file")).strip(), "materials file")
    geometry_text, geometry_path, geometry_raw = load(
        str(document.get("geometry", "config")).strip(), "geometry file")
    parallel_text = None
    parallel_path = None
    parallel_raw = b""
    if document.get("parallel_world", "geometry_config") is not None:
        parallel_text, parallel_path, parallel_raw = load(
            str(document.get("parallel_world", "geometry_config")).strip(),
            "parallel geometry file")
    macro_value = document.get("run", "macro")
    if macro_value is None:
        macro_relative = "run.mac"
    else:
        macro_relative = str(macro_value).strip()
    macro_text, macro_path, macro_raw = load(macro_relative, "run macro")
    readme_text = None
    readme_path = None
    readme_raw = b""
    if (root / "README.md").is_file():
        readme_text, readme_path, readme_raw = load("README.md", "project README")
    source_paths = {
        "main.ini": main_path,
        "materials.ini": materials_path,
        "geometry.ini": geometry_path,
        "run.mac": macro_path,
    }
    if parallel_path is not None:
        source_paths["parallel.ini"] = parallel_path
    if readme_path is not None:
        source_paths["README.md"] = readme_path

    files: dict[str, bytes] = {
        PROJECT_MAIN: main_raw,
        PROJECT_MATERIALS: materials_raw,
        PROJECT_GEOMETRY: geometry_raw,
        PROJECT_MACRO: macro_raw,
    }
    inputs = [
        {"role": "main", "source_kind": "opened_project",
         "original_path": str(main_path), "copied_to": PROJECT_MAIN,
         "sha256_before": sha256_bytes(main_raw),
         "sha256_after": sha256_bytes(main_raw),
         "rewrite": "path_rewrite"},
        {"role": "materials", "source_kind": "opened_project",
         "original_path": str(materials_path), "copied_to": PROJECT_MATERIALS,
         "sha256_before": sha256_bytes(materials_raw),
         "sha256_after": sha256_bytes(materials_raw),
         "rewrite": "verbatim"},
        {"role": "geometry", "source_kind": "opened_project",
         "original_path": str(geometry_path), "copied_to": PROJECT_GEOMETRY,
         "sha256_before": sha256_bytes(geometry_raw),
         "sha256_after": sha256_bytes(geometry_raw),
         "rewrite": "verbatim"},
        {"role": "macro", "source_kind": "opened_project",
         "original_path": str(macro_path), "copied_to": PROJECT_MACRO,
         "sha256_before": sha256_bytes(macro_raw),
         "sha256_after": sha256_bytes(macro_raw),
         "rewrite": "verbatim"},
    ]
    if parallel_text is not None and parallel_path is not None:
        files[PROJECT_PARALLEL] = parallel_raw
        inputs.append({
            "role": "parallel_geometry", "source_kind": "opened_project",
            "original_path": str(parallel_path), "copied_to": PROJECT_PARALLEL,
            "sha256_before": sha256_bytes(parallel_raw),
            "sha256_after": sha256_bytes(parallel_raw),
            "rewrite": "verbatim",
        })
    if readme_text is not None and readme_path is not None:
        files[PROJECT_README] = readme_raw
        inputs.append({
            "role": "example", "source_kind": "opened_project",
            "original_path": str(readme_path), "copied_to": PROJECT_README,
            "sha256_before": sha256_bytes(readme_raw),
            "sha256_after": sha256_bytes(readme_raw),
            "rewrite": "verbatim",
        })
    return ProjectPayload(files, inputs, main_text, materials_text,
                          geometry_text, parallel_text, macro_text, readme_text,
                          source_paths)


# ---------------------------------------------------------------------------
# Generating the current project (S-B) through the existing writers
# ---------------------------------------------------------------------------

def _generated_payload(selection: ExportSelection, staging: Path) -> ProjectPayload:
    from g4usim_gui.core.project import G4USimProject  # noqa: F401  (type only)
    from g4usim_gui.writers.package_writer import (PackageValidationError,
                                                   create_run_package)

    if selection.project is None:
        raise ExportError("selection_unavailable", "no generated project is selected")
    project = copy.deepcopy(selection.project)
    if not isinstance(project, G4USimProject):
        raise ExportError("selection_unavailable",
                          "the generated selection is not a project")
    writer_root = Path(tempfile.mkdtemp(prefix=".k2-writer-",
                                        dir=str(staging.parent)))
    try:
        placeholder = writer_root / ".writer-placeholder-backend"
        placeholder.write_bytes(b"")
        project.executable = str(placeholder)
        project.pathSettings.executable = str(placeholder)
        project.runsRoot = str(writer_root / "runs")
        project.pathSettings.runs_root = str(writer_root / "runs")
        package, _report = create_run_package(
            project=project,
            paths=project.pathSettings,
            run=project.runSettings,
            geometry=project.geometrySettings,
            source=project.sourceSettings,
            physics=project.physicsSettings,
            scoring=project.scoringSettings,
            material_document=getattr(project, "materialEditor", None),
            geometry_document=project.geometryEditor,
            source_model=project.sourceEditor,
            physics_model=project.physicsEditor,
            scoring_model=project.scoringEditor,
        )
    except PackageValidationError as exc:
        failures = []
        report = getattr(exc, "report", None)
        for item in getattr(report, "errors", []) or []:
            failures.append(str(getattr(item, "message", item)))
        raise ExportError("unsupported_feature",
                          "the current generated project cannot be exported",
                          failures) from exc
    except (OSError, ValueError) as exc:
        raise ExportError("unsupported_feature",
                          f"the generated project cannot be packaged: {exc}") from exc
    else:
        root = Path(package.package_dir)
        try:
            main_raw = Path(package.main_ini_path).read_bytes()
            materials_raw = Path(package.materials_ini_path).read_bytes()
            geometry_raw = Path(package.geometry_ini_path).read_bytes()
            macro_raw = Path(package.run_macro_path).read_bytes()
        except OSError as exc:
            raise ExportError("write_failed",
                              f"generated package files cannot be read: {exc}") from exc
    finally:
        shutil.rmtree(writer_root, ignore_errors=True)
    main_text = _decode(main_raw, label="generated main.ini")
    materials_text = _decode(materials_raw, label="generated materials")
    geometry_text = _decode(geometry_raw, label="generated geometry")
    macro_text = _decode(macro_raw, label="generated macro")
    files = {
        PROJECT_MAIN: main_raw,
        PROJECT_MATERIALS: materials_raw,
        PROJECT_GEOMETRY: geometry_raw,
        PROJECT_MACRO: macro_raw,
    }
    inputs = [
        {"role": "main", "source_kind": "generated",
         "original_path": "generated:main.ini", "copied_to": PROJECT_MAIN,
         "sha256_before": None, "sha256_after": sha256_bytes(main_raw),
         "rewrite": "generated"},
        {"role": "materials", "source_kind": "generated",
         "original_path": "generated:materials.ini", "copied_to": PROJECT_MATERIALS,
         "sha256_before": None, "sha256_after": sha256_bytes(materials_raw),
         "rewrite": "generated"},
        {"role": "geometry", "source_kind": "generated",
         "original_path": "generated:geometry.ini", "copied_to": PROJECT_GEOMETRY,
         "sha256_before": None, "sha256_after": sha256_bytes(geometry_raw),
         "rewrite": "generated"},
        {"role": "macro", "source_kind": "generated",
         "original_path": "generated:run.mac", "copied_to": PROJECT_MACRO,
         "sha256_before": None, "sha256_after": sha256_bytes(macro_raw),
         "rewrite": "generated"},
    ]
    return ProjectPayload(files, inputs, main_text, materials_text, geometry_text,
                          None, macro_text, None, {})


# ---------------------------------------------------------------------------
# Validation of the supported subset
# ---------------------------------------------------------------------------

@dataclass
class ProjectSummary:
    name: str
    mode: str
    particle: str
    energy_mev: float
    events: int
    threads: int
    seed: int | None
    parallel_world: bool
    features: list[str]


def _number_triplet(value: str, *, label: str) -> tuple[float, ...]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise ExportError("unsupported_feature",
                          f"{label} must be three numbers: {value!r}")
    numbers = []
    for part in parts:
        try:
            number = float(part)
        except ValueError as exc:
            raise ExportError("unsupported_feature",
                              f"{label} must be three numbers: {value!r}") from exc
        if not math.isfinite(number):
            raise ExportError("unsupported_feature",
                              f"{label} must be finite: {value!r}")
        numbers.append(number)
    return tuple(numbers)


_LENGTH_FACTORS = {"nm": 1e-6, "um": 1e-3, "mm": 1.0, "cm": 10.0, "m": 1000.0,
                   "km": 1e6}


def _length_triplet(value: str, *, label: str) -> tuple[float, ...]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise ExportError("unsupported_feature",
                          f"{label} must be three lengths (x,y,z): {value!r}")
    numbers = []
    for part in parts:
        if _NUMBER_RE.match(part):
            # The backend reads a unit-less component as Geant4's native unit.
            numbers.append(float(part))
            continue
        if not _LENGTH_RE.match(part):
            raise ExportError("unsupported_feature",
                              f"{label} must be three lengths: {value!r}")
        match = re.match(
            r"^\s*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)\s*([A-Za-z]+)\s*$",
            part)
        assert match is not None
        numbers.append(float(match.group(1)) * _LENGTH_FACTORS[match.group(2).lower()])
    if not all(math.isfinite(number) for number in numbers):
        raise ExportError("unsupported_feature", f"{label} must be finite: {value!r}")
    return tuple(numbers)


def _rotation_triplet(value: str, *, label: str) -> tuple[float, ...]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3 or any(not _ROTATION_RE.match(part) for part in parts):
        raise ExportError("unsupported_feature",
                          f"{label} must be three angles: {value!r}")
    numbers = []
    for part in parts:
        match = re.match(r"^\s*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)",
                         part)
        assert match is not None
        numbers.append(float(match.group(1)))
    return tuple(numbers)


def _energy_mev(value: str, *, label: str) -> float:
    match = _ENERGY_RE.match(value)
    if match is None:
        raise ExportError("unsupported_feature",
                          f"{label} must be an energy with units eV/keV/MeV/GeV: {value!r}")
    number = float(match.group(1))
    unit = match.group(2).lower()
    factor = {"ev": 1e-6, "kev": 1e-3, "mev": 1.0, "gev": 1e3}[unit]
    result = number * factor
    if not (result >= 0 and result < float("inf")):
        raise ExportError("unsupported_feature", f"{label} must be a finite energy")
    return result


def _validate_materials(text: str) -> dict[str, str]:
    document = parse_ini(text, label="project/config/materials.ini")
    aliases: dict[str, str] = {}
    for section in document.sections.values():
        keys = section.keys()
        unknown = [key for key in keys if key not in {"material"}]
        if unknown:
            raise ExportError("unsupported_feature",
                              f"materials.ini [{section.name}] uses unsupported keys: "
                              f"{', '.join(unknown)}")
        if "material" not in keys:
            raise ExportError("unsupported_feature",
                              f"materials.ini [{section.name}] has no material target")
        target = section.get("material")
        assert target is not None
        if not re.fullmatch(r"G4_[A-Za-z0-9_]+", target.strip()):
            raise ExportError("unsupported_feature",
                              f"materials.ini [{section.name}] must alias a G4_ material: "
                              f"{target!r}")
        aliases[section.name.strip().lower()] = target.strip()
    return aliases


def _validate_geometry(text: str, *, label: str, aliases: dict[str, str],
                       parallel: bool) -> dict[str, object]:
    document = parse_ini(text, label=label)
    if "world" not in document.sections:
        raise ExportError("unsupported_feature", f"{label} has no [world]")
    volumes: dict[str, list[str]] = {}
    sensitive: list[str] = []
    world = document.sections["world"]
    world_keys = world.keys()
    if parallel:
        allowed = {"material"}
        if set(world_keys) - allowed:
            raise ExportError("unsupported_feature",
                              f"{label} [world] uses unsupported keys: "
                              f"{', '.join(sorted(set(world_keys) - allowed))}")
        world_material = world.get("material")
        if world_material is None:
            raise ExportError("unsupported_feature", f"{label} [world] needs a material")
    else:
        for key in ("shape", "size", "material"):
            if world.get(key) is None:
                raise ExportError("unsupported_feature",
                                  f"{label} [world] needs {key}")
        unknown = [key for key in world_keys if key not in _GEOMETRY_KEYS]
        if unknown:
            raise ExportError("unsupported_feature",
                              f"{label} [world] uses unsupported keys: {', '.join(unknown)}")
        if world.get("shape") != "box":
            raise ExportError("unsupported_feature",
                              f"{label} [world] shape must be box")
        _length_triplet(str(world.get("size")), label=f"{label} [world] size")
        world_material = world.get("material")
    for name in _materials_used([str(world_material)], aliases):
        del name

    for section_name, section in document.sections.items():
        if section_name == "world":
            continue
        if not section_name.startswith("volume."):
            raise ExportError("unsupported_feature",
                              f"{label} uses unsupported section [{section.name}]")
        volume_name = section.name[len("volume."):].strip()
        if not volume_name:
            raise ExportError("unsupported_feature", f"{label} has an empty volume name")
        if volume_name in volumes:
            raise ExportError("unsupported_feature",
                              f"{label} repeats volume {volume_name}")
        allowed = _PARALLEL_KEYS if parallel else _GEOMETRY_KEYS
        unknown = [key for key in section.keys() if key not in allowed]
        if unknown:
            raise ExportError("unsupported_feature",
                              f"{label} [{section.name}] uses unsupported keys: "
                              f"{', '.join(unknown)}")
        if section.get("parent") is None:
            raise ExportError("unsupported_feature",
                              f"{label} [{section.name}] needs parent")
        parent = str(section.get("parent")).strip()
        if parent != "world" and parent not in volumes:
            raise ExportError("unsupported_feature",
                              f"{label} [{section.name}] parent {parent!r} is not "
                              f"declared before it")
        if section.get("shape") != "box":
            raise ExportError("unsupported_feature",
                              f"{label} [{section.name}] shape must be box")
        _length_triplet(str(section.get("size")), label=f"{label} [{section.name}] size")
        if section.get("position") is not None:
            _length_triplet(str(section.get("position")),
                            label=f"{label} [{section.name}] position")
        if section.get("rotation") is not None:
            _rotation_triplet(str(section.get("rotation")),
                              label=f"{label} [{section.name}] rotation")
        material = section.get("material")
        if material is None:
            raise ExportError("unsupported_feature",
                              f"{label} [{section.name}] needs a material")
        _materials_used([str(material)], aliases)
        is_sensitive = _boolean(document, section_name, "sensitive", default=False)
        if is_sensitive:
            sensitive.append(volume_name)
        volumes[volume_name] = [parent]
    if parallel and not sensitive:
        raise ExportError("unsupported_feature",
                          f"{label} declares no sensitive scoring volume")
    return {"world_material": str(world_material).strip(),
            "volumes": sorted(volumes), "sensitive": sorted(sensitive)}


def _materials_used(values: Iterable[str], aliases: dict[str, str]) -> list[str]:
    used = []
    for value in values:
        name = value.strip()
        if not name:
            raise ExportError("unsupported_feature", "empty material reference")
        if name.lower() in aliases:
            used.append(name)
            continue
        if re.fullmatch(r"G4_[A-Za-z0-9_]+", name):
            used.append(name)
            continue
        raise ExportError("unsupported_feature",
                          f"material {name!r} is neither an alias nor a G4_ material")
    return used


def _validate_macro(text: str) -> int:
    events: int | None = None
    initialized = False
    beam_on = False
    for number, raw in enumerate(text.splitlines(keepends=True), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        tokens = line.split()
        directive = tokens[0]
        if directive not in _MACRO_DIRECTIVES:
            raise ExportError("unsupported_feature",
                              f"macro line {number}: unsupported directive {directive!r}")
        if directive == "/run/initialize":
            if initialized or beam_on:
                raise ExportError("unsupported_feature",
                                  "the macro must run /run/initialize once before /run/beamOn")
            initialized = True
        elif directive == "/run/beamOn":
            if not initialized:
                raise ExportError("unsupported_feature",
                                  "the macro must run /run/initialize before /run/beamOn")
            if beam_on:
                raise ExportError("unsupported_feature",
                                  "the macro must contain exactly one /run/beamOn")
            if len(tokens) != 2 or not tokens[1].isdigit():
                raise ExportError("unsupported_feature",
                                  f"macro line {number}: /run/beamOn needs one event count")
            events = int(tokens[1])
            if not 1 <= events <= MAX_EVENTS:
                raise ExportError("unsupported_feature",
                                  f"macro line {number}: event count is out of range")
            beam_on = True
        elif len(tokens) != 2:
            raise ExportError("unsupported_feature",
                              f"macro line {number}: {directive} needs one value")
    if not initialized:
        raise ExportError("unsupported_feature",
                          "the macro must contain exactly one /run/initialize")
    if not beam_on or events is None:
        raise ExportError("unsupported_feature",
                          "the macro must contain exactly one /run/beamOn")
    return events


def _validate_source_token_whitespace(text: str) -> None:
    """Check the new source grammar before Unicode strip/splitlines can hide bytes.

    This is a raw-token guard, not a second INI schema. Other values, names,
    paths and comments retain their existing policy. No input is rewritten.
    """
    section = ""
    fields = {"position_type", "shape", "halfx", "halfy"}
    # Backend getline uses LF, unlike Python splitlines (NEL/LS/PS also split).
    for index, physical in enumerate(text.split("\n")):
        if index == 0 and physical.startswith("\ufeff"):
            physical = physical[1:]
        content = re.split(r"[#;]", physical, maxsplit=1)[0]
        stripped = content.strip()
        target = None
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip().lower()
            if section == "source":
                target = "section header"
        elif section == "source" and "=" in content:
            key = content.split("=", 1)[0].strip().lower()
            if key in fields:
                target = key
        if target is not None:
            invalid = next((c for c in content if ord(c) > 127 and c.isspace()), None)
            if invalid is not None:
                raise ExportError(
                    "unsupported_feature",
                    f"project/main.ini: [source] {target} contains non-ASCII "
                    f"whitespace U+{ord(invalid):04X} on physical line {index + 1}")


def _validate_main_text(text: str, *, mode: str, events: int) -> ProjectSummary:
    _validate_source_token_whitespace(text)
    document = parse_ini(text, label="project/main.ini")
    for section_name, section in document.sections.items():
        allowed = _MAIN_KEYS.get(section_name)
        if allowed is None:
            raise ExportError("unsupported_feature",
                              f"main.ini uses unsupported section [{section.name}]")
        unknown = [key for key in section.keys() if key not in allowed]
        if unknown:
            raise ExportError("unsupported_feature",
                              f"main.ini [{section.name}] uses unsupported keys: "
                              f"{', '.join(unknown)}")
    name = document.require("run", "name")
    threads = _integer(document, "run", "threads", minimum=1, maximum=60, default=1)
    if threads not in ALLOWED_THREADS:
        raise ExportError("unsupported_feature",
                          f"main.ini threads must be one of {list(ALLOWED_THREADS)}")
    seed_raw = document.get("run", "seed")
    seed = None
    if seed_raw is not None:
        seed = _integer(document, "run", "seed", minimum=0)
        if seed > 2_147_483_647:
            raise ExportError("unsupported_feature", "main.ini seed is out of range")
    if _boolean(document, "run", "interactive", default=False):
        raise ExportError("unsupported_feature", "main.ini interactive must be false")
    if _boolean(document, "run", "dry_run", default=False):
        raise ExportError("unsupported_feature", "main.ini dry_run must be false")
    _integer(document, "run", "verbose", minimum=0, maximum=2, default=1)
    _boolean(document, "run", "check_overlaps", default=True)
    macro_value = document.get("run", "macro")
    if macro_value is not None and str(macro_value).strip() != PROJECT_MACRO:
        raise ExportError("unsupported_feature",
                          f"main.ini [run] macro must be {PROJECT_MACRO}")
    if document.get("output", "format") is not None:
        format_value = str(document.get("output", "format")).strip().lower()
        if format_value != "csv":
            raise ExportError("unsupported_feature",
                              "main.ini [output] format must be csv when present")
    template = document.require("geometry", "template").strip().lower()
    if template != "hierarchical":
        raise ExportError("unsupported_feature",
                          "main.ini [geometry] template must be hierarchical")
    _boolean(document, "geometry", "check_overlaps", default=True)
    reference = document.require("physics", "reference").strip()
    if reference not in GEANT4_REFERENCES:
        raise ExportError("unsupported_feature",
                          f"main.ini physics reference must be one of "
                          f"{list(GEANT4_REFERENCES)}")
    if document.get("physics", "default_cut") is not None:
        cut = str(document.get("physics", "default_cut")).strip()
        if not _LENGTH_RE.match(cut):
            raise ExportError("unsupported_feature",
                              f"main.ini default_cut must be a length: {cut!r}")
    if document.get("physics", "biasing") is not None:
        if _boolean(document, "physics", "biasing"):
            raise ExportError("unsupported_feature",
                              "physics biasing is not part of the supported subset")
    if document.get("physics", "verbose") is not None:
        _integer(document, "physics", "verbose", minimum=0, maximum=2, default=1)
    if "biasing" in document.sections:
        if _boolean(document, "biasing", "enabled", default=False):
            raise ExportError("unsupported_feature",
                              "biasing is not part of the supported subset")
        if set(document.sections["biasing"].keys()) - {"enabled"}:
            raise ExportError("unsupported_feature",
                              "main.ini [biasing] only accepts enabled=false")
    particle = document.require("source", "particle").strip().lower()
    if particle != "proton":
        raise ExportError("unsupported_feature",
                          "only a proton source is part of the supported subset")
    energy = _energy_mev(document.require("source", "energy"),
                         label="main.ini source energy")
    if energy <= 0:
        raise ExportError("unsupported_feature",
                          "main.ini source energy must be positive")
    position_type = (document.get("source", "position_type") or "point").strip().lower()
    if position_type not in {"point", "plane"}:
        raise ExportError("unsupported_feature",
                          "main.ini position_type must be point or plane")
    if position_type == "point":
        if document.get("source", "position") is None:
            raise ExportError("unsupported_feature", "a point source needs [source] position")
        for key in ("shape", "center", "radius", "halfx", "halfy"):
            if document.get("source", key) is not None:
                raise ExportError("unsupported_feature", f"a point source conflicts with [source] {key}")
    if position_type == "plane":
        if (document.get("source", "shape") or "").strip().lower() != "rectangle":
            raise ExportError("unsupported_feature", "a plane source requires explicit shape=rectangle")
        for key in ("position", "radius"):
            if document.get("source", key) is not None:
                raise ExportError("unsupported_feature", f"a rectangle source conflicts with [source] {key}")
        for key in ("center", "halfx", "halfy"):
            if document.get("source", key) is None:
                raise ExportError("unsupported_feature", f"a plane source needs [source] {key}")
        for key in ("halfx", "halfy"):
            raw = document.require("source", key)
            # Deliberately narrower than general exporter lengths: UnitParser's
            # case-sensitive units, with explicit units required in this subset.
            match = re.fullmatch(r"\s*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)\s*(nm|um|mm|cm|m)\s*", raw, flags=re.ASCII)
            value = float(match[1]) * {"nm": 1e-6, "um": 1e-3, "mm": 1., "cm": 10., "m": 1000.}[match[2]] if match else float("nan")
            if not math.isfinite(value) or value <= 0:
                raise ExportError("unsupported_feature", f"[source] {key} needs a positive finite length with lowercase nm/um/mm/cm/m")
    for key in ("position", "center"):
        if document.get("source", key) is not None:
            _length_triplet(str(document.get("source", key)),
                            label=f"main.ini source {key}")
    if document.get("source", "direction") is not None:
        _number_triplet(str(document.get("source", "direction")),
                        label="main.ini source direction")
    if document.get("source", "isotropic") is not None:
        _boolean(document, "source", "isotropic", default=False)
    if document.get("source", "preset") is not None:
        preset = str(document.get("source", "preset")).strip()
        if preset not in {"proton_beam"}:
            raise ExportError("unsupported_feature",
                              f"source preset {preset!r} is not supported")
    if _boolean(document, "scoring", "enabled", default=True) is False:
        raise ExportError("unsupported_feature",
                          "main.ini scoring must stay enabled")
    hits = _boolean(document, "scoring", "hits", default=False)
    if hits:
        raise ExportError("unsupported_feature",
                          "hits output is not part of the supported subset")
    for key in ("event_edep", "edep", "dose", "fluence",
                "auto_create_default_scorers"):
        _boolean(document, "scoring", key, default=False)
    if document.get("scoring", "let") is not None:
        if _boolean(document, "scoring", "let"):
            raise ExportError("unsupported_feature",
                              "LET scoring is not part of the supported subset")
    if document.get("scoring", "verbose") is not None:
        _integer(document, "scoring", "verbose", minimum=0, maximum=2, default=1)
    if "scoring.edep" in document.sections:
        section = document.sections["scoring.edep"]
        for key in ("raw_histogram", "weighted_histogram", "volume_summary",
                    "particle_summary"):
            _boolean(document, "scoring.edep", key, default=False)
        if section.get("bins") is not None:
            _integer(document, "scoring.edep", "bins", minimum=1,
                     maximum=1_000_000)
        for key in ("min", "max"):
            if section.get(key) is not None:
                value = str(section.get(key)).strip()
                if not _ENERGY_RE.match(value):
                    raise ExportError("unsupported_feature",
                                      f"main.ini [{section.name}] {key} must be a "
                                      f"length: {value!r}")
    parallel = False
    if "parallel_world" in document.sections:
        enabled = _boolean(document, "parallel_world", "enabled", default=False)
        if enabled:
            parallel = True
            name_value = document.require("parallel_world", "name").strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name_value):
                raise ExportError("unsupported_feature",
                                  "parallel world name is not a valid identifier")
            document.require("parallel_world", "geometry_config")
    features = ["hierarchical_box_geometry", "proton_source",
                "scoring_dose_fluence"]
    if _boolean(document, "scoring", "event_edep", default=False):
        features.append("scoring_event_edep")
    if "scoring.edep" in document.sections:
        features.append("edep_histograms")
    if parallel:
        features.append("parallel_world_scoring")
    return ProjectSummary(name=name, mode="external_project" if mode == "external"
                          else "generated_single_target", particle=particle,
                          energy_mev=energy, events=events, threads=threads,
                          seed=seed, parallel_world=parallel, features=features)


# ---------------------------------------------------------------------------
# Rewriting the main INI for the export root
# ---------------------------------------------------------------------------

def rewrite_main_ini(text: str) -> tuple[str, list[dict[str, str]]]:
    """Rewrite existing whitelisted values only.

    The frozen contract only allows replacing the value spans of the selected
    keys.  Indentation, inline comments, CRLF line endings, a UTF-8 BOM and a
    missing final newline must all survive byte for byte, and keys that the
    source does not have are never inserted (the frozen run commands pass
    --macro and --output explicitly).
    """
    replacements = {
        ("output", "dir"): OUTPUT_DIRECTORY,
        ("materials", "file"): PROJECT_MATERIALS,
        ("geometry", "config"): PROJECT_GEOMETRY,
        ("parallel_world", "geometry_config"): PROJECT_PARALLEL_REF,
        ("run", "macro"): PROJECT_MACRO,
    }
    changes: list[dict[str, str]] = []
    output: list[str] = []
    section = None
    first = True
    for raw in text.splitlines(keepends=True):
        probe = raw
        if first:
            first = False
            if probe.startswith("\ufeff"):
                probe = probe[1:]
        stripped = probe.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip().lower()
            output.append(raw)
            continue
        if section is None:
            output.append(raw)
            continue
        match = _VALUE_LINE.match(probe)
        if match is None:
            output.append(raw)
            continue
        key = match.group("key").strip().lower()
        replacement = replacements.get((section, key))
        if replacement is None:
            output.append(raw)
            continue
        before = match.group("value").strip()
        if before == replacement:
            output.append(raw)
            continue
        rewritten = (match.group("head") + match.group("key")
                     + match.group("sep") + replacement + match.group("tail")
                     + (match.group("eol") or ""))
        if probe is not raw:
            rewritten = "\ufeff" + rewritten
        output.append(rewritten)
        changes.append({"section": section, "key": key,
                        "before": before, "after": replacement})
    return "".join(output), changes


def _scan_absolute_paths(files: dict[str, bytes]) -> None:
    for relative, raw in sorted(files.items()):
        if not relative.startswith("project/"):
            continue
        text = _decode(raw, label=relative)
        for pattern in _ABSOLUTE_SCAN:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                raise ExportError("absolute_path_remaining",
                                  f"{relative} line {line} still contains an "
                                  f"absolute or host-specific path: "
                                  f"{match.group(0).strip()!r}")


# ---------------------------------------------------------------------------
# Building the export payload
# ---------------------------------------------------------------------------

def _standalone_readme(summary: ProjectSummary, *, identity: str | None = None) -> bytes:
    lines = [
        "# G4UniversalSim exported project",
        "",
        "This directory is a self-contained Geant4 application exported by "
        "G4UniversalSim. It was produced from a narrowly supported project "
        "subset; it is not a general simulator bundle.",
        "",
        f"- Project: `{summary.name}`",
        f"- Selection: {'opened project' if summary.mode == 'external' else 'generated package'}",
        f"- Particle: {summary.particle}, {summary.energy_mev:g} MeV",
        f"- Events in the macro: {summary.events}",
        f"- Threads: {summary.threads}",
        f"- Parallel-world scoring: {'yes' if summary.parallel_world else 'no'}",
        "",
        "## Build",
        "",
        "Requirements: CMake 3.21+, a C++17 compiler, Geant4 11.3.2 or 11.4.3 "
        "built with the same compiler ABI, and the Geant4 data variables "
        "described in `docs/Linux构建与验证.md`.",
        "",
        "Windows (Visual Studio 2026 generator, from this directory):",
        "",
        "```powershell",
        "cmake --preset vs2026-x64 -DG4USIM_STANDALONE_EXPORT=ON -DGeant4_DIR=<geant4-prefix>/lib/cmake/Geant4",
        "cmake --build --preset vs2026-release",
        "```",
        "",
        "Linux:",
        "",
        "```bash",
        "cmake -S . -B build_linux -DCMAKE_BUILD_TYPE=Release -DG4USIM_STANDALONE_EXPORT=ON -DCMAKE_PREFIX_PATH=<geant4-prefix>",
        "cmake --build build_linux --parallel",
        "```",
        "",
        "## Run",
        "",
        "Run from this directory so the relative paths in `project/main.ini` "
        "resolve against the export root:",
        "",
        "```bash",
        f"<build>/G4UniversalSim --config {PROJECT_MAIN} --macro {PROJECT_MACRO} "
        f"--output {OUTPUT_DIRECTORY}",
        "```",
        "",
        "Dry run (configuration and macro preflight only):",
        "",
        "```bash",
        f"<build>/G4UniversalSim --config {PROJECT_MAIN} --macro {PROJECT_MACRO} "
        f"--output {OUTPUT_DIRECTORY} --dry-run",
        "```",
        "",
        f"Outputs are written to `{OUTPUT_DIRECTORY}`.",
        "",
        "## Test",
        "",
        "The exported tree keeps the C++ component tests; the Python m0 regression "
        "suite is checkout-only and is not registered here:",
        "",
        "```powershell",
        'ctest --test-dir build_vs2026 -C Release -L "^component$"',
        "```",
        "",
        "```bash",
        'ctest --test-dir build_linux -L "^component$"',
        "```",
        "",
        "Exactly two component tests are expected: `h2_volume_scoring_check` and "
        "`parallel_scoring_component`.",
        "",
        "## Contents",
        "",
        "- `CMakeLists.txt`, `CMakePresets.json`, `main.cc`, `cmake/`, `include/`, "
        "`src/`, `tools/`, `schema/`: the standalone C++ application source.",
        "- `config/`, `macros/`: the template's runtime resource defaults.",
        "- `project/`: the exported project inputs (`main.ini`, `config/materials.ini`, "
        "`config/geometry.ini`, optional `config/parallel.ini`, `macros/run.mac`).",
        "- `licenses/`, `THIRD_PARTY_NOTICES.md`: Geant4 and Xerces-C license terms.",
        "- `docs/`: build and usage documents copied from the template.",
        "- `export-manifest.json`: file list, input hashes and identity evidence.",
        "- `export-template-manifest.json`: the exact template identity used here.",
        "",
        "## Limits",
        "",
        "Only the S-A/S-B subset is supported: box hierarchical geometry, proton "
        "source, CSV output, reference physics, dose/fluence scoring and optional "
        "box parallel-world scoring. Field, biasing, LET, displacement damage, "
        "phase-space input, non-box shapes and mesh scoring are refused.",
        "Sources are points without shape keys or explicit plane rectangles. Rectangle "
        "halfx/halfy require positive finite values with lowercase nm/um/mm/cm/m. "
        "Legacy NIST aliases are case-insensitive; duplicate normalized section "
        "declarations are refused even with identical targets.",
    ]
    if identity:
        lines.extend(["", f"Payload identity: `{identity}`"])
    return ("\n".join(lines) + "\n").encode("utf-8")


def _third_party_notices(license_paths: list[str]) -> bytes:
    lines = [
        "# Third-party notices",
        "",
        "This exported project is built against Geant4. Geant4 and its optional "
        "Xerces-C dependency are not bundled into this source export; their "
        "license texts are copied below for reference.",
        "",
    ]
    mapping = (
        ("Geant4", "licenses/Geant4-LICENSE.txt"),
        ("Apache Xerces-C", "licenses/Xerces-C-LICENSE.txt"),
        ("Apache Xerces-C notice", "licenses/Xerces-C-NOTICE.txt"),
    )
    for title, path in mapping:
        if path in license_paths:
            lines.append(f"## {title}")
            lines.append("")
            lines.append(f"See `{path}`.")
            lines.append("")
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def _generated_project_readme(summary: ProjectSummary) -> bytes:
    lines = [
        "# " + summary.name,
        "",
        "This project was generated by the G4UniversalSim single-target wizard "
        "and exported together with the standalone application source. The "
        "export root contains the complete build tree; this folder only holds "
        "the project inputs.",
        "",
        "| File | Purpose |",
        "|---|---|",
        "| `main.ini` | main configuration used by the exported binary |",
        "| `config/materials.ini` | material aliases or an empty default set |",
        "| `config/geometry.ini` | hierarchical box geometry |",
        "| `macros/run.mac` | initialization and beam-on macro |",
        "",
        "Run from the export root:",
        "",
        "```bash",
        "./build/G4UniversalSim --config project/main.ini",
        "```",
        "",
    ]
    return ("\n".join(lines)).encode("utf-8")


def _staging_target(staging: Path, relative: str) -> Path:
    safe = _posix(relative)
    root = os.path.abspath(str(staging))
    candidate = os.path.abspath(os.path.join(root, *safe.split("/")))
    if candidate == root or os.path.commonpath([root, candidate]) != root:
        raise ExportError("linked_or_ambiguous_path",
                          f"exported path escapes the staging directory: {relative!r}")
    return Path(candidate)


def _write_payload_file(staging: Path, relative: str, raw: bytes) -> None:
    target = _staging_target(staging, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ExportError("write_failed", f"refusing to overwrite {relative}")
    with target.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _copy_template(layout: TemplateLayout, staging: Path) -> None:
    for member in layout.members:
        source = layout.source_path(member)
        raw = read_template_member_bytes(source, kind="export_template_unavailable",
                                         label="template file")
        if len(raw) != member.bytes or sha256_bytes(raw) != member.sha256:
            raise ExportError("template_identity_mismatch",
                              f"template file changed while exporting: {member.path}")
        _write_payload_file(staging, member.path, raw)


def _git_state(root: Path) -> tuple[str, str]:
    """Best effort: exported content never depends on a Git checkout."""
    try:
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10)
        if head.returncode != 0:
            return "unknown", "unknown"
        commit = head.stdout.strip() or "unknown"
        status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                                capture_output=True, text=True, timeout=20)
        if status.returncode != 0:
            return commit, "unknown"
        return commit, "dirty" if status.stdout.strip() else "clean"
    except (OSError, subprocess.SubprocessError):
        return "unknown", "unknown"


def _tool_version(template_root: Path) -> str:
    text = ""
    try:
        text = (template_root / "CMakeLists.txt").read_text(encoding="utf-8",
                                                            errors="replace")
    except OSError:
        pass
    match = re.search(r"project\s*\(\s*G4UniversalSim\s+VERSION\s+([0-9][0-9A-Za-z.\-]*)",
                      text)
    return match.group(1) if match else "unknown"


def _project_files(payload: ProjectPayload, *, mode: str) -> dict[str, bytes]:
    """Project files after the main.ini rewrite, with audit SHA updates."""
    rewritten, changes = rewrite_main_ini(payload.main_text)
    rewritten_bytes = rewritten.encode("utf-8")
    document = parse_ini(rewritten, label="project/main.ini")
    events = _validate_macro(payload.macro_text)
    summary = _validate_main_text(rewritten, mode=mode, events=events)
    aliases = _validate_materials(payload.materials_text)
    mass = _validate_geometry(payload.geometry_text,
                              label="project/config/geometry.ini",
                              aliases=aliases, parallel=False)
    parallel = None
    if "parallel_world" in document.sections and _boolean(
            document, "parallel_world", "enabled", default=False):
        if payload.parallel_text is None:
            raise ExportError("unsupported_feature",
                              "main.ini enables a parallel world but no geometry "
                              "file was selected")
        parallel = _validate_geometry(payload.parallel_text,
                                      label="project/config/parallel.ini",
                                      aliases=aliases, parallel=True)
    files = dict(payload.files)
    files[PROJECT_MAIN] = rewritten_bytes
    if PROJECT_README in files:
        readme_bytes = files[PROJECT_README]
    else:
        readme_bytes = _generated_project_readme(summary)
        files[PROJECT_README] = readme_bytes
    for entry in payload.inputs:
        if entry["role"] == "main":
            entry["sha256_after"] = sha256_bytes(rewritten_bytes)
        elif entry.get("copied_to") == PROJECT_README:
            entry["sha256_after"] = sha256_bytes(readme_bytes)
    _scan_absolute_paths({key: value for key, value in files.items()
                          if key == PROJECT_MAIN
                          or key.startswith("project/config/")
                          or key.startswith("project/macros/")})
    return {"files": files, "summary": summary, "rewrites": changes,
            "mass": mass, "parallel": parallel}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _check_destination(destination: Path, selection: ExportSelection,
                       layout: TemplateLayout) -> Path:
    target = Path(destination).expanduser()
    if not target.name or target.name in {".", ".."}:
        raise ExportError("destination_parent_missing",
                          f"destination has no usable name: {target}")
    parent = target.parent
    if not parent.is_dir():
        raise ExportError("destination_parent_missing",
                          f"destination parent is missing: {parent}")
    if target.exists() or target.is_symlink():
        raise ExportError("destination_exists",
                          f"destination already exists: {target}")
    # Reuse the K1 path guard on the raw destination. abspath()/resolve() would
    # fold a link component (link/../x) before the guard could see it.
    guarded = _no_links(target, label="destination")
    resolved = Path(guarded)
    if selection.kind == "external" and selection.project_root is not None:
        source_root = selection.project_root.resolve()
        try:
            resolved.relative_to(source_root)
        except ValueError:
            pass
        else:
            raise ExportError("destination_inside_source",
                              f"destination is inside the source project: {target}")
    template_root = layout.root.resolve()
    try:
        resolved.relative_to(template_root)
    except ValueError:
        pass
    else:
        raise ExportError("destination_inside_source",
                          f"destination is inside the export template tree: {target}")
    return resolved


STAGING_ALLOCATION_ATTEMPTS = 5


def _allocate_staging(target: Path) -> Path:
    """Create the private staging directory for one export.

    ``tempfile.mkdtemp`` treats a Windows permission error like a random-name
    collision and keeps trying up to ``TMP_MAX``; a denied parent then burns
    minutes without producing a target or a staging directory.  This allocator
    uses one UUID name per export, retries only genuine name collisions a
    bounded number of times, and turns every other ``OSError`` into R12
    immediately.
    """
    parent = target.parent
    for _ in range(STAGING_ALLOCATION_ATTEMPTS):
        candidate = parent / f".{target.name}.k2-{uuid.uuid4().hex[:16]}"
        try:
            os.mkdir(candidate, 0o700)
        except FileExistsError:
            continue
        except OSError as exc:
            raise ExportError(
                "write_failed",
                f"cannot create the export staging directory: {exc}") from exc
        try:
            _no_links(candidate, label="export staging")
        except ExportError:
            _cleanup(candidate)
            raise
        return candidate
    raise ExportError(
        "write_failed",
        "cannot allocate a unique export staging directory: "
        f"{STAGING_ALLOCATION_ATTEMPTS} name collisions")


def export_project(destination: str | Path, selection: ExportSelection, *,
                   template_root: Path | None = None,
                   created_utc: str | None = None) -> dict:
    """Create one standalone project export at *destination*.

    The destination must not exist. All work happens in a private sibling
    staging directory; failures clean it and never leave a partial destination.
    """
    layout = load_template_layout(template_root)
    target = _check_destination(Path(destination), selection, layout)
    staging = _allocate_staging(target)
    try:
        if selection.kind == "external":
            if selection.project_root is None:
                raise ExportError("selection_unavailable",
                                  "external selection has no project directory")
            payload = _read_external_payload(selection)
            _verify_sources_unchanged(payload)
            mode = "external"
        elif selection.kind == "generated":
            payload = _generated_payload(selection, staging)
            mode = "generated"
        else:
            raise ExportError("selection_unavailable",
                              f"unknown selection kind: {selection.kind}")
        prepared = _project_files(payload, mode=mode)
        prepared["inputs"] = payload.inputs
        files: dict[str, bytes] = {}
        _copy_template(layout, staging)
        for relative, raw in prepared["files"].items():
            _write_payload_file(staging, relative, raw)
            files[relative] = raw
        template_paths = {member.path for member in layout.members}
        license_paths = [member.path for member in layout.members
                         if member.role == "license"]
        notices = _third_party_notices(license_paths)
        _write_payload_file(staging, NOTICE_FILE, notices)
        files[NOTICE_FILE] = notices
        readme = _standalone_readme(prepared["summary"])
        _write_payload_file(staging, EXPORT_README, readme)
        files[EXPORT_README] = readme
        template_manifest_copy = _staging_target(staging, TEMPLATE_MANIFEST_COPY)
        _write_payload_file(staging, TEMPLATE_MANIFEST_COPY,
                            _json_bytes(layout.manifest))
        files[TEMPLATE_MANIFEST_COPY] = template_manifest_copy.read_bytes()
        if selection.kind == "external":
            _verify_sources_unchanged(payload)
        # Template files are part of the payload; their manifest identity was
        # verified before copying, and the copy re-checked each file.
        payload_files: dict[str, bytes] = dict(files)
        for path in sorted(staging.rglob("*")):
            if path.is_file() and path.relative_to(staging).as_posix() not in payload_files:
                relative = path.relative_to(staging).as_posix()
                payload_files[relative] = path.read_bytes()
        all_files = {str(key): value for key, value in payload_files.items()}
        identity = _files_identity(all_files)
        manifest = _manifest(layout, prepared, all_files, identity,
                             selection=selection, created_utc=created_utc)
        manifest_bytes = _json_bytes(manifest)
        _write_payload_file(staging, MANIFEST_NAME, manifest_bytes)
        _publish(staging, target)
        return {
            "destination": str(target),
            "manifest": manifest,
            "export_manifest_sha256": sha256_bytes(manifest_bytes),
            "payload_identity": identity,
            "template_identity": manifest["template_identity"],
            "template_paths": sorted(template_paths),
        }
    except ExportError:
        _cleanup(staging)
        raise
    except (OSError, ValueError) as exc:
        _cleanup(staging)
        raise ExportError("write_failed", f"export failed: {exc}") from exc
    except BaseException:
        _cleanup(staging)
        raise


def _verify_sources_unchanged(payload: ProjectPayload) -> None:
    for path in payload.source_paths.values():
        try:
            raw = _bundle._read(path)  # type: ignore[attr-defined]
        except (OSError, ValueError) as exc:
            raise ExportError("input_changed_during_export",
                              f"input cannot be re-read: {path}: {exc}") from exc
        expected = None
        candidate = os.path.normcase(os.path.abspath(str(path)))
        for entry in payload.inputs:
            original = entry.get("original_path")
            if original is None or str(original).startswith("generated:"):
                continue
            if os.path.normcase(os.path.abspath(str(original))) == candidate:
                expected = entry.get("sha256_before")
                break
        if expected is not None and sha256_bytes(raw) != expected:
            raise ExportError("input_changed_during_export",
                              f"input changed during export: {path}")


def _files_identity(files: dict[str, bytes]) -> dict:
    ordered = sorted(files)
    text = "".join(f"{sha256_bytes(files[key])}  {key}\n" for key in ordered)
    return {
        "algorithm": IDENTITY_ALGORITHM,
        "file_count": len(ordered),
        "digest": sha256_bytes(text.encode("utf-8")),
    }


def _file_roles(layout: TemplateLayout, extra_roles: dict[str, str]) -> dict[str, str]:
    roles = {member.path: member.role for member in layout.members}
    roles.update(extra_roles)
    return roles


def _manifest(layout: TemplateLayout, prepared: dict, files: dict[str, bytes],
              identity: dict, *, selection: ExportSelection,
              created_utc: str | None) -> dict:
    summary = prepared["summary"]
    extra_roles = {
        PROJECT_MAIN: "project_config",
        PROJECT_MATERIALS: "project_config",
        PROJECT_GEOMETRY: "project_config",
        PROJECT_MACRO: "project_macro",
        PROJECT_README: "example",
        EXPORT_README: "readme_export",
        NOTICE_FILE: "notice",
        TEMPLATE_MANIFEST_COPY: "doc",
    }
    if PROJECT_PARALLEL in files:
        extra_roles[PROJECT_PARALLEL] = "project_config"
    roles = _file_roles(layout, extra_roles)
    unknown = [path for path in files if path not in roles]
    if unknown:
        raise ExportError("write_failed",
                          f"exported files have no role: {unknown}")
    bad_roles = sorted({roles[path] for path in files} - set(FILE_ROLES))
    if bad_roles:
        raise ExportError("write_failed", f"unknown file roles: {bad_roles}")
    files_block = [
        {"path": path, "role": roles[path],
         "sha256": sha256_bytes(files[path]), "bytes": len(files[path])}
        for path in sorted(files)
    ]
    template_identity_block = template_identity(layout.members)
    manifest_digest = str(layout.manifest["identity"]["value"])
    computed_digest = str(template_identity_block["value"])
    matched = manifest_digest == computed_digest
    if not matched:
        raise ExportError(
            "template_identity_mismatch",
            "the template manifest digest does not match the copied template files")
    git_head, git_state = _git_state(layout.root) if layout.checkout else ("unknown", "unknown")
    if layout.checkout:
        template_manifest_path = f"packaging/{TEMPLATE_MANIFEST_NAME}"
    else:
        template_manifest_path = TEMPLATE_MANIFEST_NAME
    opened = selection.kind == "external"
    selection_kind = "opened_project" if opened else "generated_package"
    project_root_audit = str(selection.project_root) if opened and selection.project_root else None
    windows_commands = [
        "cmake --preset vs2026-x64 -DG4USIM_STANDALONE_EXPORT=ON "
        "-DGeant4_DIR=<geant4-prefix>/lib/cmake/Geant4",
        "cmake --build --preset vs2026-release",
        'ctest --test-dir build_vs2026 -C Release -L "^component$"',
        f"build_vs2026\\Release\\G4UniversalSim.exe --config {PROJECT_MAIN} "
        f"--macro {PROJECT_MACRO} --output {OUTPUT_DIRECTORY}",
    ]
    linux_commands = [
        "cmake -S . -B build_linux -DCMAKE_BUILD_TYPE=Release "
        "-DG4USIM_STANDALONE_EXPORT=ON -DCMAKE_PREFIX_PATH=<geant4-prefix>",
        "cmake --build build_linux --parallel",
        'ctest --test-dir build_linux -L "^component$"',
        f"build_linux/G4UniversalSim --config {PROJECT_MAIN} "
        f"--macro {PROJECT_MACRO} --output {OUTPUT_DIRECTORY}",
    ]
    smoke_runs = [
        {"name": "dry_run",
         "command": f"build_linux/G4UniversalSim --config {PROJECT_MAIN} "
                    f"--macro {PROJECT_MACRO} --output {OUTPUT_DIRECTORY} --dry-run"},
        {"name": "beam_on",
         "command": f"build_linux/G4UniversalSim --config {PROJECT_MAIN} "
                    f"--macro {PROJECT_MACRO} --output {OUTPUT_DIRECTORY}"},
    ]
    license_entries = [
        {"component": "Geant4", "kind": "host_dependency_not_bundled",
         "files": ["licenses/Geant4-LICENSE.txt"],
         "origin": "packaging/licenses"},
        {"component": "Apache Xerces-C",
         "kind": "optional_host_dependency_not_bundled",
         "files": ["licenses/Xerces-C-LICENSE.txt", "licenses/Xerces-C-NOTICE.txt"],
         "origin": "packaging/licenses"},
    ]
    inputs = sorted(prepared["inputs"],
                    key=lambda entry: (entry["role"], entry["copied_to"]))
    for entry in inputs:
        if entry.get("rewrite") not in INPUT_REWRITE_VALUES:
            raise ExportError("write_failed",
                              f"input rewrite is not in the frozen set: {entry}")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "version": MANIFEST_VERSION,
        "created_utc": created_utc or _utc_now(),
        "tool": {
            "name": TOOL_NAME,
            "version": _tool_version(layout.root),
            "git_head": git_head,
            "git_source_state": git_state,
            "template_origin": "checkout" if layout.checkout else "packaged",
            "template_root_label": layout.label,
            "template_manifest_digest": manifest_digest,
            "template_digest": computed_digest,
            "template_file_count": len(layout.members),
        },
        "identity": identity,
        "template_identity": {
            "manifest_path": template_manifest_path,
            "manifest_digest": manifest_digest,
            "computed_digest": computed_digest,
            "matched": matched,
        },
        "project": {
            "name": summary.name,
            "selection": selection_kind,
            "entry": {
                "config": PROJECT_MAIN,
                "macro": PROJECT_MACRO,
                "output": OUTPUT_DIRECTORY,
            },
            "original_project_root_audit": project_root_audit,
        },
        "files": files_block,
        "inputs": inputs,
        "build": {
            "requirements": [
                "CMake 3.21 or newer (CMakeLists.txt declares 3.10 as its minimum)",
                "a C++17 compiler",
                "Geant4 11.3.2 or 11.4.3 built with the same compiler ABI",
                "Qt 5 development files required by Geant4 UI and visualization",
                "Xerces-C++ when Geant4 GDML support is enabled",
                "the Geant4 data-set environment variables (GEANT4_DATA_DIR or G4...DATA)",
            ],
            "standalone_flag": "G4USIM_STANDALONE_EXPORT=ON",
            "docs": [
                EXPORT_README,
                "docs/Linux构建与验证.md",
                "docs/中文使用手册.md",
                "docs/功能支持矩阵.md",
                "docs/输出数据契约.md",
            ],
            "commands": {"windows": windows_commands, "linux": linux_commands},
        },
        "tests": {
            "component_ctest_label_regex": "^component$",
            "component_ctest_names": [
                "h2_volume_scoring_check",
                "parallel_scoring_component",
            ],
            "smoke_runs": smoke_runs,
        },
        "licenses": {
            "project_code": "not_declared_in_repository",
            "entries": license_entries,
        },
        "limits": {
            "subset_modes": ["opened_project", "generated_package"],
            "threads": list(ALLOWED_THREADS),
            "max_events": MAX_EVENTS,
            "format": "csv",
            "macro_commands": list(_MACRO_DIRECTIVES),
            "geometry_shapes": ["box"],
            "reference_physics": list(GEANT4_REFERENCES),
            "source_particle": "proton",
            "source_positions": ["point without shape", "plane with explicit shape=rectangle"],
            "rectangle_halfwidth_units": ["nm", "um", "mm", "cm", "m"],
            "scoring": ["dose", "fluence", "event_edep", "edep_histograms"],
            "parallel_world": "optional box geometry with dose/fluence scoring",
            "external_inputs": ["main.ini", "materials", "geometry", "parallel geometry",
                                "run.mac", "README.md"],
        },
        "not_included": [
            "the Geant4 runtime, headers and data sets",
            "the Qt runtime and Qt development files",
            "a C++ compiler",
            "the Python and PySide6 GUI",
            "scenarios/ and examples/ other than the exported project and the "
            "single NIEL fixture scenarios/semiconductor/niel/si_proton.csv "
            "required by the parallel-scoring component test",
            "test framework scripts (scripts/, gui/)",
            "docs/verification and docs/collab evidence trees",
            "the project's own repository license (none is declared)",
        ],
    }
    return manifest


def _cleanup(staging: Path) -> None:
    try:
        shutil.rmtree(staging, ignore_errors=True)
    except OSError:
        pass


def _publish(staging: Path, target: Path) -> None:
    try:
        _bundle._publish_directory(staging, target)  # type: ignore[attr-defined]
    except OSError as exc:
        raise ExportError("write_failed",
                          f"cannot publish export atomically: {exc}") from exc


# ---------------------------------------------------------------------------
# Identity verification of an existing export (K2-3 consumer)
# ---------------------------------------------------------------------------

def verify_export(destination: Path) -> dict:
    root = _no_links(Path(destination), label="export root")
    root = Path(root)
    manifest_path = root / MANIFEST_NAME
    _no_links(manifest_path, label="export manifest")
    if not manifest_path.exists():
        raise ExportError("selection_unavailable",
                          f"not an export: no {MANIFEST_NAME} in {root}")
    try:
        manifest = json.loads(_read_regular(manifest_path, kind="selection_unavailable",
                                            label="export manifest").decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise ExportError("selection_unavailable",
                          f"manifest is unreadable: {exc}") from exc
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ExportError("selection_unavailable", "unexpected export manifest schema")
    claimed = manifest.get("identity") or {}
    listed: dict[str, dict] = {}
    for entry in manifest.get("files") or []:
        relative = _posix(str(entry.get("path")))
        listed[relative] = entry
    actual: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        guarded = _no_links(path, label=f"export entry {relative}")  # type: ignore[arg-type]
        guarded = Path(guarded)
        if guarded.is_dir():
            continue
        if not guarded.is_file():
            raise ExportError("input_changed_during_export",
                              f"export contains a non-file entry: {relative}")
        actual[relative] = guarded.read_bytes()
    extra = sorted(set(actual) - set(listed))
    missing = sorted(set(listed) - set(actual))
    if extra or missing:
        raise ExportError(
            "input_changed_during_export",
            f"export closure differs from the manifest (extra={extra}, missing={missing})")
    for relative, entry in listed.items():
        raw = actual[relative]
        if len(raw) != entry.get("bytes") or sha256_bytes(raw) != entry.get("sha256"):
            raise ExportError("input_changed_during_export",
                              f"file does not match the manifest: {relative}")
    identity = _files_identity(actual)
    if identity["digest"] != claimed.get("digest") or \
            identity["file_count"] != claimed.get("file_count"):
        raise ExportError("input_changed_during_export",
                          "export identity does not match the manifest")
    return {"manifest": manifest, "identity": identity}
