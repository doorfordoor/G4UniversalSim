"""Headless driver for the shielding/coating scenario (roadmap 2B).

The scripts and the GUI share one scenario definition: ``scenarios/shielding_coating``
holds the model (``scenario_model.py``), the CLI (``make_scenario.py``) and the
analysis (``analyze.py``).  This module loads the two files by path (they are not a
Python package and the installed layout copies the ``scenarios`` folder verbatim),
exposes the editable field list the Qt page renders, and runs one scenario through the
real backend so the same code path can be exercised offscreen in tests.

All user-visible strings are English message keys; the Qt page runs them through
``core.i18n.ui_text``/``ui_format``.  Nothing here imports Qt.
"""

from __future__ import annotations

import importlib.util
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import config_schema
from .install_layout import application_root, default_backend_executable

SCENARIO_NAME = "shielding_coating"
_MODULES: dict[str, object] = {}


class ScenarioRunError(RuntimeError):
    """The scenario could not be generated, executed or analysed."""


# --------------------------------------------------------------------------- fields


@dataclass(frozen=True)
class ScenarioField:
    """One editable value of the scenario form (label/help are i18n message keys)."""

    key: str
    label: str
    kind: str
    default: str
    choices: tuple[str, ...] = ()
    help: str = ""
    advanced: bool = False


FIELDS: tuple[ScenarioField, ...] = (
    ScenarioField("mode", "Mode", "choice", "transmission", ("transmission", "albedo"),
                  help="Transmission counts primaries that cross the device layer; "
                       "albedo counts primaries that leave the front face."),
    ScenarioField("particle", "Primary particle", "choice", "proton", ("proton", "e-", "mixed"),
                  help="Mixed needs both spectra; a mono-energetic source cannot be mixed."),
    ScenarioField("energy", "Mono-energetic source", "energy", "",
                  help="Leave empty to use the spectra; a value switches to a mono-energetic source."),
    ScenarioField("layers", "Layers (material:thickness, comma separated)", "layers",
                  "B4C:300um,G4_W:100um,G4_Al:300um",
                  help="Ordered from the source side to the device side; nm/um/mm/cm/m."),
    ScenarioField("events", "Events", "int", "1000", help="Events of one run."),
    ScenarioField("threads", "Threads", "int", "4", help="Geant4 worker threads."),
    ScenarioField("seed", "Random seed", "int", "12345",
                  help="The same parameters and seed reproduce the same result."),
    ScenarioField("size", "Lateral size", "length", "10mm", advanced=True,
                  help="Side length of the layers and the device."),
    ScenarioField("device_thickness", "Device thickness", "length", "300um", advanced=True,
                  help="Thickness of the silicon device layer."),
    ScenarioField("source_half", "Source half size", "length", "4mm", advanced=True,
                  help="Half side length of the square planar source."),
    ScenarioField("junction_density", "Junction density (0..1)", "float", "0", advanced=True,
                  help="0 means no junction copies; > 0 adds junction copies to the device."),
    ScenarioField("pores_layer", "Porous layer index", "int", "-1", advanced=True,
                  help="-1 means no pores; otherwise the layer index (0 based)."),
    ScenarioField("pore_radius", "Pore radius", "length", "20um", advanced=True,
                  help="Pore radius of the porous layer."),
    ScenarioField("pore_fraction", "Pore fraction", "float", "0.01", advanced=True,
                  help="Area fraction of the porous layer."),
    ScenarioField("niel", "NIEL tables", "niel", "", advanced=True,
                  help="PARTICLE=TABLE.csv, comma separated; empty disables displacement damage."),
)

FIELD_BY_KEY = {item.key: item for item in FIELDS}


def default_values() -> dict[str, str]:
    """The values shown when the scenario page opens."""
    return {item.key: item.default for item in FIELDS}


def field_spec(key: str) -> ScenarioField:
    try:
        return FIELD_BY_KEY[key]
    except KeyError:
        raise ScenarioRunError(f"Unknown scenario field '{key}'") from None


def visible_fields(advanced: bool = False) -> tuple[ScenarioField, ...]:
    """Basic fields first; the advanced ones are hidden behind a toggle."""
    return tuple(item for item in FIELDS if item.advanced is advanced)


# ------------------------------------------------------------------------- module load


def scenario_directory() -> Path:
    """Directory holding scenario_model.py and analyze.py (source checkout or package)."""
    candidates: list[Path] = []
    override = os.environ.get("G4USIM_SCENARIO_ROOT", "")
    if override:
        candidates.append(Path(override))
    candidates.append(application_root() / "scenarios" / SCENARIO_NAME)
    candidates.append(Path(__file__).resolve().parents[2] / "scenarios" / SCENARIO_NAME)
    for candidate in candidates:
        if (candidate / "scenario_model.py").is_file():
            return candidate
    raise ScenarioRunError(
        "Cannot find scenarios/" + SCENARIO_NAME + " next to the GUI; set "
        "G4USIM_SCENARIO_ROOT to the scenarios folder of the installation."
    )


def _load(name: str) -> object:
    cached = _MODULES.get(name)
    if cached is not None:
        return cached
    path = scenario_directory() / f"{name}.py"
    if not path.is_file():
        raise ScenarioRunError(f"The scenario file {path} is missing.")
    spec = importlib.util.spec_from_file_location(f"g4usim_scenario_{name}", path)
    if spec is None or spec.loader is None:
        raise ScenarioRunError(f"Cannot load {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as a scenario error
        sys.modules.pop(spec.name, None)
        raise ScenarioRunError(f"Cannot load {path}: {exc}") from exc
    _MODULES[name] = module
    return module


def model():
    return _load("scenario_model")


def analysis():
    """The analysis module; it must expose analyze(output_dir) -> dict (roadmap 2B)."""
    module = _load("analyze")
    if not callable(getattr(module, "analyze", None)):
        raise ScenarioRunError(
            "scenarios/shielding_coating/analyze.py does not expose analyze(output_dir); "
            "the GUI driver needs that importable entry point."
        )
    return module


# ------------------------------------------------------------------- values -> spec


def _integer(values: dict[str, str], key: str, minimum: int | None = None) -> int:
    text = values.get(key, field_spec(key).default).strip()
    try:
        number = int(text)
    except ValueError:
        raise ScenarioRunError(
            f"{field_spec(key).label} must be an integer, got '{text}'") from None
    if minimum is not None and number < minimum:
        raise ScenarioRunError(f"{field_spec(key).label} must be at least {minimum}")
    return number


def _number(values: dict[str, str], key: str, *, low: float | None = None,
            high: float | None = None, low_open: bool = False) -> float:
    text = values.get(key, field_spec(key).default).strip()
    try:
        number = float(text)
    except ValueError:
        raise ScenarioRunError(
            f"{field_spec(key).label} must be a number, got '{text}'") from None
    if not math.isfinite(number):
        raise ScenarioRunError(f"{field_spec(key).label} must be finite, got '{text}'")
    if low is not None and (number <= low if low_open else number < low):
        symbol = ">" if low_open else ">="
        raise ScenarioRunError(f"{field_spec(key).label} must be {symbol} {low:g}")
    if high is not None and number >= high:
        raise ScenarioRunError(f"{field_spec(key).label} must be less than {high:g}")
    return number


def energy_mev(text: str) -> float:
    """Parse a mono-energetic source value with the configuration schema grammar."""
    value = config_schema.energy_mev(text)
    if value is None:
        raise ScenarioRunError(
            "[source]/energy must be a finite energy (units eV, keV, MeV, GeV), got '"
            + text + "'")
    return value


def spec_kwargs(values: dict[str, str]) -> dict[str, object]:
    """Validate one form dictionary and return the ShieldingSpec keyword arguments."""
    merged = default_values()
    merged.update({key: str(value) for key, value in values.items()})
    unknown = sorted(set(values) - set(FIELD_BY_KEY))
    if unknown:
        raise ScenarioRunError("Unknown scenario field(s): " + ", ".join(unknown))
    keyword: dict[str, object] = {
        "layers": merged["layers"],
        "size": merged["size"],
        "device_thickness": merged["device_thickness"],
        "source_half": merged["source_half"],
        "particle": merged["particle"],
        "mode": merged["mode"],
        "events": _integer(merged, "events", 1),
        "threads": _integer(merged, "threads", 1),
        "seed": _integer(merged, "seed", 0),
        "pore_radius": merged["pore_radius"],
        "pore_fraction": _number(merged, "pore_fraction", low=0.0, high=1.0),
        "junction_density": _number(merged, "junction_density", low=0.0, high=1.0),
        "pores_layer": _integer(merged, "pores_layer"),
        "niel": tuple(item.strip() for item in merged["niel"].split(",") if item.strip()),
    }
    energy = merged["energy"].strip()
    if energy:
        keyword["energy_MeV"] = energy_mev(energy)
    return keyword


def validate_values(values: dict[str, str]) -> list[str]:
    """Return the reasons the form cannot be generated; empty means it can."""
    try:
        keyword = spec_kwargs(values)
    except ScenarioRunError as exc:
        return [str(exc)]
    try:
        spec = model().ShieldingSpec(**keyword)
    except TypeError as exc:  # pragma: no cover - a field-list bug, not a user error
        return [f"Cannot build the scenario spec: {exc}"]
    problems = list(spec.problems())
    if problems:
        return problems
    # The generated main.ini fields the user can influence are checked with the same
    # schema the configuration editor uses, so the GUI and the backend agree.
    return _schema_problems(keyword)


def _schema_problems(keyword: dict[str, object]) -> list[str]:
    problems: list[str] = []
    problems.extend(filter(None, (
        config_schema.check_value("run", "threads", str(int(keyword["threads"]))),
        config_schema.check_value("run", "seed", str(int(keyword["seed"]))),
    )))
    energy = keyword.get("energy_MeV")
    if energy is not None:
        problems.extend(filter(None, (
            config_schema.check_value("source", "energy", f"{float(energy):g} MeV"),
        )))
    return problems


def build_spec(values: dict[str, str]):
    """Build the ShieldingSpec, raising ScenarioRunError on invalid values."""
    problems = validate_values(values)
    if problems:
        raise ScenarioRunError("; ".join(problems))
    return model().ShieldingSpec(**spec_kwargs(values))


# --------------------------------------------------------------------- generate / run


@dataclass
class GeneratedScenario:
    directory: Path
    spec: object
    files: dict[str, Path]
    meta: dict
    main_ini: str
    main_ini_path: Path
    macro_path: Path

    @property
    def output_directory(self) -> Path:
        return self.directory / "output"


def generate(values: dict[str, str], directory: str | Path, *,
             run_from: str | Path | None = None) -> GeneratedScenario:
    """Write the scenario files and return where they are."""
    target = Path(directory)
    spec = build_spec(values)
    try:
        result = spec.generate(target, run_from=str(run_from) if run_from is not None else None)
    except ScenarioRunError:
        raise
    except Exception as exc:  # the model raises ScenarioError for invalid values
        raise ScenarioRunError(str(exc)) from exc
    files = {name: Path(path) for name, path in result["files"].items()}
    main_ini_path = files["main.ini"]
    return GeneratedScenario(
        directory=target,
        spec=spec,
        files=files,
        meta=result["meta"],
        main_ini=main_ini_path.read_text(encoding="utf-8"),
        main_ini_path=main_ini_path,
        macro_path=files["run.mac"],
    )


@dataclass
class ScenarioOutcome:
    generated: GeneratedScenario
    command: tuple[str, ...]
    exit_code: int
    duration_seconds: float
    log_path: Path
    summary: dict[str, str] = field(default_factory=dict)
    report: dict | None = None
    error: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and self.report is not None and not self.error

    @property
    def output_directory(self) -> Path:
        return self.generated.output_directory


def read_summary(output_directory: Path) -> dict[str, str]:
    path = Path(output_directory) / "run_summary.txt"
    if not path.is_file():
        return {}
    facts: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            facts[key.strip()] = value.strip()
    return facts


def analyse(generated: GeneratedScenario | str | Path) -> dict:
    """Run the scenario analysis and return its report, or raise ScenarioRunError."""
    directory = (generated.directory if isinstance(generated, GeneratedScenario)
                 else Path(generated))
    module = analysis()
    try:
        return module.analyze(directory / "output")
    except Exception as exc:  # EvidenceError carries the reason; anything else is a bug
        raise ScenarioRunError(str(exc)) from exc


def run_scenario(
    values: dict[str, str],
    directory: str | Path,
    *,
    executable: str | Path | None = None,
    timeout: float | None = None,
    run_from: str | Path | None = None,
) -> ScenarioOutcome:
    """Generate the scenario and run it once through the real backend."""
    executable_path = str(executable) if executable else default_backend_executable()
    if not executable_path:
        raise ScenarioRunError("The G4UniversalSim backend executable was not found.")
    if not Path(executable_path).is_file():
        raise ScenarioRunError(f"The backend executable {executable_path} does not exist.")
    generated = generate(values, directory, run_from=run_from)
    command = (executable_path, "--config", "main.ini")
    log_path = generated.directory / "backend.log"
    header = ("$ " + " ".join(command) + "\n").encode("utf-8")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(generated.directory),
            capture_output=True,
            timeout=timeout,
        )
        exit_code = completed.returncode
        log_bytes = header + completed.stdout + completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = -1
        log_bytes = (header + (exc.stdout or b"") + (exc.stderr or b"")
                     + b"\n[timeout] the scenario run was stopped after "
                     + str(timeout).encode("ascii") + b" seconds\n")
    except OSError as exc:
        raise ScenarioRunError(f"Cannot start the backend: {exc}") from exc
    duration = time.monotonic() - started
    log_bytes = log_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    log_path.write_bytes(log_bytes)
    outcome = ScenarioOutcome(
        generated=generated,
        command=command,
        exit_code=exit_code,
        duration_seconds=duration,
        log_path=log_path,
    )
    outcome.summary = read_summary(outcome.output_directory)
    if exit_code != 0:
        outcome.error = describe_failure(outcome.summary, exit_code)
        return outcome
    try:
        outcome.report = analyse(generated)
    except ScenarioRunError as exc:
        outcome.error = str(exc)
        return outcome
    outcome.warnings = list((outcome.report or {}).get("evidence", {}).get("warnings", []))
    if evidence_label(outcome.report) == "no_statistics_file_zero_deposition":
        outcome.warnings.append(
            "No statistics file was written; the result is recorded as zero deposition. "
            "Confirm whether this is a real zero count.")
    return outcome


def describe_failure(summary: dict[str, str], exit_code: int) -> str:
    status = summary.get("status", "unknown")
    run_count = summary.get("run_count", "?")
    completed = summary.get("run_0_completed_events", "?")
    detail = (summary.get("output_failure_message", "")
              or summary.get("interactive_command_failure_message", ""))
    message = (f"The backend run failed (exit code {exit_code}, status={status}, "
               f"run_count={run_count}, completed events={completed})")
    return message + ": " + detail if detail else message


# ---------------------------------------------------------------------- result view


def evidence_label(report: dict | None) -> str:
    return str((report or {}).get("evidence", {}).get("scorer_statistics", ""))


def result_rows(report: dict | None) -> list[dict[str, str]]:
    """Flatten the analysis report into rows for the result table."""
    rows: list[dict[str, str]] = []
    if not report:
        return rows
    statistics = evidence_label(report)
    for group, key, unit in (("TID", "tid", "Gy"), ("DDD", "ddd", "MeV/g")):
        quantity = report.get(key) or {}
        if quantity.get("total") is None:
            continue
        evidence = quantity.get("evidence", statistics)
        rows.append({"group": group, "label": "Total", "value": format_number(quantity.get("total")),
                     "unit": quantity.get("unit", unit), "evidence": evidence})
        rows.append({"group": group, "label": "Per primary",
                     "value": format_number(quantity.get("per_primary")),
                     "unit": f"{quantity.get('unit', unit)}/primary", "evidence": evidence})
        for name, value in sorted((quantity.get("per_fluence") or {}).items()):
            rows.append({"group": group, "label": f"Per fluence ({name})",
                         "value": format_number(value),
                         "unit": f"{quantity.get('unit', unit)}/({name})", "evidence": evidence})
    phase_files = (report.get("evidence") or {}).get("phase_space_files") or []
    phase = "phase_space" if phase_files else "no_phase_space"
    for group, key, label in (("Transmission", "primary_transmission", "Primary transmission"),
                              ("Albedo", "primary_albedo", "Primary albedo")):
        value = report.get(key)
        if value is not None:
            rows.append({"group": group, "label": label, "value": format_number(value),
                         "unit": "fraction", "evidence": phase})
    return rows


def format_number(value: object) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == 0.0:
        return "0"
    if abs(number) >= 1e4 or abs(number) < 1e-3:
        return f"{number:.6e}"
    return f"{number:.6g}"


def evidence_summary(report: dict | None) -> list[str]:
    """Evidence statements for the results panel (rendered through ui_format)."""
    if not report:
        return []
    evidence = report.get("evidence", {})
    return [
        f"Run status: {evidence.get('run_status', 'unknown')}",
        f"Completed events: {evidence.get('completed_events', 'unknown')}",
        f"Statistics evidence: {evidence.get('scorer_statistics', 'unknown')}",
        f"Run metadata schema: {evidence.get('run_metadata_schema', 'unknown')}",
    ] + [f"Warning: {item}" for item in evidence.get("warnings", [])]


def cleanup_directory(directory: str | Path) -> None:
    """Remove a scenario working directory (tests; the page re-runs into a fresh one)."""
    shutil.rmtree(directory, ignore_errors=True)
