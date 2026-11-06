"""Read-only view of the external ``[parallel_world]`` section (roadmap H3-3).

The GUI does not regenerate ``[parallel_world]``: the section lives in the external
main INI, and the backend resolves ``geometry_config`` against that INI's directory.
This module reports what the current external configuration means for the Project
page and the project validator, so the section is neither dropped nor presented as
GUI-editable. It only describes the file; the backend remains the source of truth
for acceptance, construction and run behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.parsers.ini_light_parser import IniLightDocument, parse_ini_light

TRUE_VALUES = {"true", "yes", "on", "1"}
FALSE_VALUES = {"false", "no", "off", "0"}
DEFAULT_NAME = "ScoringWorld"

# Combinations the backend refuses for a parallel scoring world (H3-2 contract).
ROOT_OUTPUT = "Parallel world: ROOT output is not supported with a parallel scoring world."
BIASING = "Parallel world: biasing is not supported with a parallel scoring world."
FIELDS = "Parallel world: electromagnetic fields are not supported with a parallel scoring world."
NATIVE_MESH = "Parallel world: native scoring meshes are not supported with a parallel scoring world."
LET_DISPLACEMENT = "Parallel world: LET and displacement damage scoring are not supported with a parallel scoring world."
GEOMETRY_REQUIRED = "Parallel world: [parallel_world] geometry_config is required when enabled=true."
DISABLED_WITH_KEYS = "Parallel world: [parallel_world] with enabled=false must not declare name or geometry_config."
GENERATED_MODE = (
    "Parallel world: the project uses generated inputs, so [parallel_world] in the "
    "external main INI would not be used; switch Inputs to External or configure the "
    "run package externally.")
BAD_BOOLEAN = "Parallel world: invalid boolean for [parallel_world]/enabled: {value}"
MISSING_FILE = "Parallel world: geometry file does not exist: {path}"
NOT_A_FILE = "Parallel world: geometry path is not a file: {path}"


@dataclass(frozen=True)
class ParallelWorldIssue:
    code: str
    message: str
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ParallelWorldScope:
    status: str = "none"           # none | unreadable | disabled | enabled | incompatible
    name: str = DEFAULT_NAME
    geometry_config: str = ""
    geometry_path: Path | None = None
    issues: tuple[ParallelWorldIssue, ...] = ()

    @property
    def configured(self) -> bool:
        return self.status in {"disabled", "enabled"}


def read_scope(project) -> ParallelWorldScope:
    """The parallel-world view for an existing project, whatever its input mode."""
    return read_inputs_scope(
        getattr(project, "runInputMode", ""), getattr(project, "configPath", ""))


def read_inputs_scope(run_input_mode: str, config_path: str) -> ParallelWorldScope:
    """The scope for a text input, so the Project page need not build a project."""
    if not config_path.strip():
        return ParallelWorldScope()
    path = Path(config_path.strip()).expanduser()
    if not path.exists() or not path.is_file():
        return ParallelWorldScope()          # the config-file checks own this message
    document = _document(path)
    if not getattr(document, "_f4_read_success", False):
        return ParallelWorldScope(status="unreadable")
    section = _find_section(document, "parallel_world")
    if section is None:
        return ParallelWorldScope()
    values = {key.lower(): value for key, value in section.values.items()}
    issues: list[ParallelWorldIssue] = []

    enabled_text = values.get("enabled", "false")
    enabled = enabled_text.strip().lower() in TRUE_VALUES
    if run_input_mode != "external":
        if enabled:
            return ParallelWorldScope(
                status="incompatible",
                name=values.get("name", "").strip() or DEFAULT_NAME,
                geometry_config=values.get("geometry_config", "").strip(),
                issues=(ParallelWorldIssue("parallel_world_generated_mode", GENERATED_MODE),))
        return ParallelWorldScope()
    if enabled_text.strip().lower() not in TRUE_VALUES | FALSE_VALUES:
        issues.append(ParallelWorldIssue("parallel_world_boolean", BAD_BOOLEAN, {"value": enabled_text}))
        enabled = False
    name = values.get("name", "").strip() or DEFAULT_NAME
    geometry = values.get("geometry_config", "").strip()
    scope = ParallelWorldScope(
        status="enabled" if enabled else "disabled", name=name, geometry_config=geometry)
    geometry_path: Path | None = None
    if enabled:
        if not geometry:
            issues.append(ParallelWorldIssue("parallel_world_geometry_required", GEOMETRY_REQUIRED))
        else:
            geometry_path = (path.parent / geometry).expanduser()
            if not geometry_path.exists():
                issues.append(ParallelWorldIssue(
                    "parallel_world_geometry_missing", MISSING_FILE,
                    {"path": geometry_path.as_posix()}))
            elif not geometry_path.is_file():
                issues.append(ParallelWorldIssue(
                    "parallel_world_geometry_not_file", NOT_A_FILE,
                    {"path": geometry_path.as_posix()}))
        # Backend ParallelWorldConfig::CompatibilityProblems returns early when
        # [parallel_world] is disabled, so incompatible combinations only matter
        # for an actually enabled world (LET/DDD etc. do not reach the ghost step).
        issues.extend(_unsupported_combinations(document))
    elif "name" in values or geometry:
        issues.append(ParallelWorldIssue("parallel_world_disabled_with_keys", DISABLED_WITH_KEYS))
    return ParallelWorldScope(scope.status, name, geometry, geometry_path, tuple(issues))


def status_line(scope: ParallelWorldScope) -> str:
    """One status line for the Project page; never claims edit support."""
    if scope.status == "none":
        return ui_text("Parallel world: not configured")
    if scope.status == "unreadable":
        return ui_text("Parallel world: cannot read the external main INI")
    if scope.status == "incompatible":
        return ui_text(
            "Parallel world: enabled in the external main INI but not carried by "
            "generated inputs; switch Inputs to External")
    if scope.status == "disabled":
        return ui_text("Parallel world: disabled (external [parallel_world])")
    label = ui_text("Parallel world: enabled, name {name}").format(name=scope.name)
    if scope.geometry_config:
        label += ui_text("; ghost geometry {path}").format(path=scope.geometry_config)
    if any(issue.code == "parallel_world_geometry_missing" for issue in scope.issues):
        label += ui_text("; geometry file missing")
    return label


def _document(path: Path) -> IniLightDocument:
    try:
        return parse_ini_light(path)
    except Exception:  # noqa: BLE001 - a broken preview must not kill the page.
        document = IniLightDocument(str(path), [], [], [], "")
        document._f4_read_success = False
        return document


def _find_section(document: IniLightDocument, wanted: str):
    for section in document.sections:
        if section.name.strip().lower() == wanted:
            return section
    return None


def _unsupported_combinations(document: IniLightDocument) -> list[ParallelWorldIssue]:
    issues: list[ParallelWorldIssue] = []
    for section in document.sections:
        name = section.name.strip().lower()
        values = {key.lower(): value.strip() for key, value in section.values.items()}
        if name == "output" and values.get("format", "").lower() == "root":
            issues.append(ParallelWorldIssue("parallel_world_root_output", ROOT_OUTPUT))
        elif name == "biasing" and values.get("enabled", "").lower() in TRUE_VALUES:
            issues.append(ParallelWorldIssue("parallel_world_biasing", BIASING))
        elif name == "field" and values or name.startswith("field."):
            issues.append(ParallelWorldIssue("parallel_world_fields", FIELDS))
        elif name.startswith("scoring.mesh"):
            issues.append(ParallelWorldIssue("parallel_world_native_mesh", NATIVE_MESH))
        elif name == "scoring" and (
                values.get("let", "").lower() in TRUE_VALUES
                or values.get("displacement", "").lower() in TRUE_VALUES):
            issues.append(ParallelWorldIssue("parallel_world_let_displacement", LET_DISPLACEMENT))
    return _unique(issues)


def _unique(issues: list[ParallelWorldIssue]) -> list[ParallelWorldIssue]:
    seen, result = set(), []
    for issue in issues:
        if issue.code in seen:
            continue
        seen.add(issue.code)
        result.append(issue)
    return result
