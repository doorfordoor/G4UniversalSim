from __future__ import annotations

import copy
from dataclasses import dataclass
import json
import re
from datetime import datetime
from pathlib import Path

from g4usim_gui.core.config_migration import digest, load_json_strict
from g4usim_gui.core.project import load_project_snapshot

_SPACE = " \t\r\v\f"
_PATHS = {
    "package_dir": "", "config_dir": "config", "macro_dir": "macros", "logs_dir": "logs",
    "output_dir": "output", "main_ini_path": "config/main.ini", "run_macro_path": "macros/run.mac",
    "validation_report_path": "validation_report.txt", "project_snapshot_path": "project_snapshot.json",
    "materials_ini_path": "config/materials/material.ini", "geometry_ini_path": "config/geometry/geometry.ini",
}
_MAIN_KEYS = {
    "general": {"schema_version"},
    "run": {"name", "threads", "seed", "interactive", "verbose", "check_overlaps", "dry_run"},
    "output": {"dir", "trajectories"}, "materials": {"file"},
    "geometry": {"template", "config", "check_overlaps", "default_world_material"},
    "physics": {"reference", "default_cut", "biasing", "verbose"},
    "source": {"preset", "particle", "energy", "position_type", "direction", "center", "shape",
               "halfx", "halfy", "radius", "position", "isotropic"},
    "scoring": {"enabled", "hits", "event_edep", "edep", "let", "dose", "fluence",
                "auto_create_default_scorers", "verbose"},
    "scoring.edep": {"raw_histogram", "weighted_histogram", "bins", "min", "max", "volume_summary", "particle_summary"},
    "biasing": {"enabled"},
}
_MACRO_COMMANDS = {"/control/verbose", "/run/verbose", "/event/verbose", "/tracking/verbose",
                   "/run/initialize", "/run/beamOn"}


@dataclass(frozen=True)
class GeneratedRunSettings:
    threads: int
    seed: int | None
    run_name: str


def _run_integer(value: str, key: str, minimum: int) -> int:
    if re.fullmatch(r"[+-]?[0-9]+", value) is None:
        raise ValueError(f"config/main.ini [run]/{key} must be a complete decimal integer")
    negative = value.startswith("-")
    digits = value.lstrip("+-").lstrip("0") or "0"
    # Bound before int(): arbitrarily many leading zeroes remain valid while
    # huge nonzero JSON/INI integers cannot hit Python's conversion limit.
    if len(digits) > 10:
        raise ValueError(f"config/main.ini [run]/{key} is outside [{minimum}, 2147483647]")
    result = int(digits) * (-1 if negative else 1)
    if not minimum <= result <= 2147483647:
        raise ValueError(f"config/main.ini [run]/{key} is outside [{minimum}, 2147483647]")
    return result


def _startup_settings(entries) -> GeneratedRunSettings:
    values = {identity: value for identity, value, *_ in entries}
    if ("run", "threads") not in values:
        raise ValueError("config/main.ini [run]/threads is required for standard package duplication")
    threads = _run_integer(values[("run", "threads")], "threads", 1)
    seed = _run_integer(values[("run", "seed")], "seed", 0) if ("run", "seed") in values else None
    return GeneratedRunSettings(threads, seed, values.get(("run", "name"), ""))


def read_generated_run_settings(package_dir: str | Path) -> GeneratedRunSettings:
    """Read only the validated package's current main.ini run identity.

    This is not a general INI importer: the same closed-input/path checks used
    by duplication must pass. Snapshot flat/runSettings fields are not used.
    """
    return _prepare_duplicate(Path(package_dir).expanduser().resolve(strict=True))[-1]


def _ini_entries(raw: bytes, label: str):
    """ASCII trim and LF parsing, retaining exact lines for targeted edits."""
    lines = raw.decode("utf-8").split("\n")
    section, sections, keys = "global", set(), set()
    result = []
    for number, line in enumerate(lines):
        comment = min((i for marker in ("#", ";") if (i := line.find(marker)) >= 0), default=len(line))
        content = line[:comment]
        clean = content.strip(_SPACE)
        if not clean:
            continue
        if clean.startswith("["):
            if not clean.endswith("]") or not clean[1:-1].strip(_SPACE):
                raise ValueError(f"{label}:{number + 1}: invalid INI section")
            section = clean[1:-1].strip(_SPACE).lower()
            if section in sections:
                raise ValueError(f"{label}:{number + 1}: duplicate section [{section}] is ambiguous for duplication")
            sections.add(section)
            continue
        if "=" not in content:
            raise ValueError(f"{label}:{number + 1}: expected key = value")
        key, value = (part.strip(_SPACE) for part in content.split("=", 1))
        identity = section, key.lower()
        if not key or identity in keys:
            raise ValueError(f"{label}:{number + 1}: duplicate or empty key [{section}]/{key}")
        keys.add(identity)
        result.append((identity, value, number, content.index("="), comment))
    return lines, result, sections


def _standard_path(value: str, expected: Path, label: str) -> None:
    if not isinstance(value, str) or not Path(value).is_absolute() or Path(value).resolve() != expected.resolve():
        raise ValueError(f"{label} must reference the original generated package target: {expected}")


def _prepare_duplicate(old: Path):
    inputs = {}
    for relative in ("config/main.ini", "config/materials/material.ini", "config/geometry/geometry.ini",
                     "macros/run.mac", "project_snapshot.json", "validation_report.txt"):
        source = old / relative
        if not source.is_file() or source.is_symlink() or any(parent.is_symlink() for parent in source.parents):
            raise ValueError(f"Generated package duplication requires a regular package input: {source}")
        inputs[relative] = source.read_bytes()
    for directory, expected in (("config", {"main.ini", "materials/material.ini", "geometry/geometry.ini"}),
                                ("macros", {"run.mac"})):
        actual = {p.relative_to(old / directory).as_posix() for p in (old / directory).rglob("*") if p.is_file()}
        if actual != expected:
            raise ValueError(f"Only standard generated {directory} inputs can be duplicated; additional resources require a resource bundle")
    data = load_json_strict(inputs["project_snapshot.json"])
    # The dedicated adapter owns all envelope/nested structure semantics. Reuse
    # its read-only validation instead of maintaining another metadata schema.
    validated = load_project_snapshot(old / "project_snapshot.json")
    if not validated.package_root or Path(validated.package_root).resolve() != old:
        raise ValueError("Duplication requires a complete standard generated-package snapshot")
    if validated.snapshot_sha256 != digest(inputs["project_snapshot.json"]):
        raise ValueError("Package snapshot changed during duplication preparation")
    package = data["runPackage"]
    for key, relative in _PATHS.items():
        _standard_path(package[key], old / relative, "runPackage." + key)
    main = inputs["config/main.ini"]
    if not main.startswith(b"# Generated by G4UniversalSim PySide6 Runner."):
        raise ValueError("Only a standard GUI-generated main.ini can be safely duplicated")
    lines, entries, sections = _ini_entries(main, "config/main.ini")
    if sections - _MAIN_KEYS.keys():
        raise ValueError("Unsupported generated main.ini sections; only standard generated inputs can be duplicated")
    replacements = {}
    expected = {("materials", "file"): "config/materials/material.ini", ("geometry", "config"): "config/geometry/geometry.ini",
                ("output", "dir"): "output"}
    for identity, value, number, equal, comment in entries:
        section, key = identity
        if key not in _MAIN_KEYS.get(section, set()):
            raise ValueError(f"Unsupported generated main.ini field [{section}]/{key}; external input duplication needs an explicit resource bundle")
        if identity == ("general", "schema_version") and value != "1":
            raise ValueError("Generated main.ini schema_version must be the exact supported string 1")
        if identity in expected:
            _standard_path(value, old / expected[identity], f"[{section}]/{key}")
            replacements[number] = (expected[identity], equal, comment)
    if len(replacements) != 3:
        raise ValueError("Generated main.ini requires exactly one materials/file, geometry/config and output/dir declaration")
    startup = _startup_settings(entries)
    _, geometry_entries, _ = _ini_entries(inputs["config/geometry/geometry.ini"], "config/geometry/geometry.ini")
    if any(identity[1] in {"file", "copies_file"} for identity, *_ in geometry_entries):
        raise ValueError("Geometry with external file/copies_file resources cannot be duplicated without a resource bundle")
    macro = inputs["macros/run.mac"].decode("utf-8")
    if not macro.startswith("# Generated by G4UniversalSim PySide6 Runner."):
        raise ValueError("Only a standard GUI-generated run.mac can be safely duplicated")
    for line in macro.split("\n"):
        clean = line.split("#", 1)[0].split(";", 1)[0].strip(_SPACE)
        if clean and clean.split()[0] not in _MACRO_COMMANDS:
            raise ValueError("Macro contains unsupported commands or external resource dependencies")
    for relative, captured in inputs.items():
        if (old / relative).read_bytes() != captured:
            raise ValueError("Package input changed during duplication preparation: " + relative)
    return inputs, data, lines, replacements, startup


def duplicate_package(old_package_dir: str, new_runs_root: str) -> str:
    """Copy a closed standard generated input set; never inherit run results."""
    old = Path(old_package_dir).expanduser().resolve(strict=True)
    inputs, snapshot, lines, replacements, _ = _prepare_duplicate(old)
    runs_root = Path(new_runs_root).expanduser().resolve()
    if runs_root.is_relative_to(old):
        raise ValueError("Duplicate destination must be outside the source package and its old output/log directories")
    run_name = old.name.split("_", 2)[-1] if "_" in old.name else old.name
    target = _allocate(runs_root, f"{run_name}_copy")
    for number, (relative, equal, comment) in replacements.items():
        line = lines[number]
        value = line[equal + 1:comment]
        leading = value[:len(value) - len(value.lstrip(_SPACE))]
        trailing = value[len(value.rstrip(_SPACE)):]
        lines[number] = line[:equal + 1] + leading + str(target / relative) + trailing + line[comment:]
    inputs["config/main.ini"] = "\n".join(lines).encode("utf-8")
    inputs["project_snapshot.json"] = _snapshot_for_duplicate(snapshot, target)
    inputs["validation_report.txt"] += (f"\n[duplication]\nduplicated_from = {old}\n"
        "execution_performed = false\nThis copy contains inputs only; previous results are not new-run evidence.\n").encode("utf-8")
    for relative, data in inputs.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(data)
    (target / "logs").mkdir()
    (target / "output").mkdir()
    return str(target)


def _allocate(runs_root: Path, suffix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{timestamp}_{_safe(suffix)}"
    target = runs_root / base
    index = 1
    while target.exists():
        target = runs_root / f"{base}_{index}"
        index += 1
    target.mkdir(parents=True, exist_ok=False)
    return target


def _safe(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text).strip("._") or "run_copy"


def _snapshot_for_duplicate(original: dict, target: Path) -> bytes:
    data = copy.deepcopy(original)
    data["configPath"] = str(target / "config/main.ini")
    data["macroPath"] = str(target / "macros/run.mac")
    data["outputDir"] = str(target / "output")
    data["workspaceRoot"], data["runsRoot"] = str(target), str(target.parent)
    data["runPackage"] = {key: str(target / relative) for key, relative in _PATHS.items()}
    paths = data.setdefault("pathSettings", {})
    paths.update(workspace_root=str(target), runs_root=str(target.parent),
                 materials_config=str(target / "config/materials/material.ini"), geometry_config=str(target / "config/geometry/geometry.ini"))
    data.setdefault("geometrySettings", {})["config_path"] = str(target / "config/geometry/geometry.ini")
    for key, relative in (("materialsSummary", "config/materials/material.ini"), ("geometrySummary", "config/geometry/geometry.ini")):
        if key in data:
            data[key]["path"] = str(target / relative)
    # Documents retain historical provenance; the dedicated snapshot adapter
    # reconstructs actual materials/geometry from these package input files.
    return (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
