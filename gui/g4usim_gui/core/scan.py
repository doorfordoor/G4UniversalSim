"""Parameter scans and batch runs (roadmap C3), without Qt.

A scan varies one setting of the current generated-mode configuration over a list
of values. Every point is an ordinary run package written by create_run_package
(same validation and writers as Generate & Run) inside one scan directory with a
manifest, scan.json (G4UniversalSimScan v1). Points run one after another (see
core/scan_runner.py); collect() then reads each point's run_status.json /
run_summary.txt and merged scorer_statistics.csv into a results table.

Scannable settings (only what the Configuration page's editors can generate):
  source.energy             value with unit, e.g. "50 MeV"
  source.particle           Geant4 particle name
  physics.reference         reference physics list
  run.seed / run.beam_on    integers
  geometry.<volume>.material
  geometry.<volume>.thickness   z size of a box volume (x, y and position kept)
"""

from __future__ import annotations

import copy
import csv
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from g4usim_gui.core.project import G4USimProject
from g4usim_gui.editors.geometry_editor_model import GeometryDocument
from g4usim_gui.editors.material_editor_model import MaterialDocument
from g4usim_gui.editors.source_physics_scoring_model import (
    PhysicsEditableModel,
    ScoringEditableModel,
    SourceEditableModel,
)
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.validators.config_validator import validate_config_builder
from g4usim_gui.writers.package_writer import create_run_package, safe_name

MANIFEST = "scan.json"
SCHEMA = "G4UniversalSimScan"
VERSION = 1
MAX_POINTS = 200
LENGTH_UNITS = {"nm", "um", "mm", "cm", "m"}
ENERGY_UNITS = {"eV", "keV", "MeV", "GeV", "TeV"}


@dataclass
class ScanBase:
    """A snapshot of everything create_run_package needs (deep-copied per point)."""
    project: G4USimProject
    paths: PathSettings
    run: RunSettings
    geometry_settings: GeometrySettings
    geometry: GeometryDocument
    source: SourceEditableModel
    physics: PhysicsEditableModel
    scoring: ScoringEditableModel
    materials: MaterialDocument | None = None


@dataclass(frozen=True)
class ScanParameter:
    key: str
    label: str          # shown as is (setting names are interface tokens)
    kind: str           # energy | particle | physics | int | material | length


def parameters(base: ScanBase) -> list[ScanParameter]:
    found = [ScanParameter("source.energy", "source energy", "energy"),
             ScanParameter("source.particle", "source particle", "particle"),
             ScanParameter("physics.reference", "physics reference list", "physics"),
             ScanParameter("run.seed", "random seed", "int"),
             ScanParameter("run.beam_on", "events (beamOn)", "int")]
    if base.geometry.mode in {"hierarchical", "hierarchical_boolean", "boolean_hierarchical", "boolean"}:
        for volume in base.geometry.volumes:
            if not volume.enabled or not volume.name.strip():
                continue
            name = volume.name.strip()
            found.append(ScanParameter(f"geometry.{name}.material", f"{name} material", "material"))
            if volume.shape.strip().lower() == "box" and name.lower() != "world":
                found.append(ScanParameter(f"geometry.{name}.thickness", f"{name} thickness (z)", "length"))
    return found


_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def expand_values(text: str) -> list[str]:
    """Scan values from text.

    "1, 2, 5 MeV"            list; a trailing unit applies to entries without one
    "lin(10, 100, 10) MeV"   n linearly spaced values, unit appended
    "log(1, 1000, 4) MeV"    n logarithmically spaced values
    """
    text = text.strip()
    match = re.fullmatch(rf"(lin|log)\(\s*({_NUMBER})\s*,\s*({_NUMBER})\s*,\s*(\d+)\s*\)\s*(\S*)", text)
    if match:
        kind, start, stop, count, unit = match.groups()
        start, stop, count = float(start), float(stop), int(count)
        if count < 2:
            raise ValueError("a range needs at least 2 points")
        if kind == "log" and (start <= 0 or stop <= 0):
            raise ValueError("log ranges need positive limits")
        if kind == "lin":
            numbers = [start + (stop - start) * i / (count - 1) for i in range(count)]
        else:
            numbers = [start * (stop / start) ** (i / (count - 1)) for i in range(count)]
        values = [f"{v:.6g}" + (f" {unit}" if unit else "") for v in numbers]
    else:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        unit = ""
        if parts:
            last = re.fullmatch(rf"({_NUMBER})\s+(\S+)", parts[-1])
            if last:
                unit = last.group(2)
        values = [f"{p} {unit}" if unit and re.fullmatch(_NUMBER, p) else p for p in parts]
    if not values:
        raise ValueError("no scan values")
    if len(values) > MAX_POINTS:
        raise ValueError(f"at most {MAX_POINTS} scan points")
    if len(set(values)) != len(values):
        raise ValueError("scan values must be distinct")
    return values


def _check_value(parameter: ScanParameter, value: str) -> None:
    if parameter.kind in {"energy", "length"}:
        match = re.fullmatch(rf"({_NUMBER})\s+(\S+)", value)
        units = ENERGY_UNITS if parameter.kind == "energy" else LENGTH_UNITS
        if not match or match.group(2) not in units or not (math.isfinite(float(match.group(1)))
                                                             and float(match.group(1)) > 0):
            raise ValueError(f"'{value}' is not a positive {parameter.kind} with a unit ({', '.join(sorted(units))})")
    elif parameter.kind == "int":
        if not re.fullmatch(r"\d+", value) or (parameter.key == "run.beam_on" and int(value) < 1):
            raise ValueError(f"'{value}' is not a valid integer for {parameter.key}")
    elif not re.fullmatch(r"[A-Za-z0-9_+\-]+", value):
        raise ValueError(f"'{value}' is not a valid name for {parameter.key}")


def apply_value(base: ScanBase, parameter: ScanParameter, value: str) -> ScanBase:
    """A deep copy of the base with one setting changed."""
    _check_value(parameter, value)
    point = copy.deepcopy(base)
    key = parameter.key
    if key == "source.energy":
        point.source.energy = value
    elif key == "source.particle":
        point.source.particle = value
    elif key == "physics.reference":
        point.physics.reference_list = value
    elif key == "run.seed":
        point.run.seed = int(value)
    elif key == "run.beam_on":
        point.run.beam_on = int(value)
    elif key.startswith("geometry."):
        name, setting = key[len("geometry."):].rsplit(".", 1)
        volume = next((v for v in point.geometry.volumes if v.enabled and v.name.strip() == name), None)
        if volume is None:
            raise ValueError(f"volume {name} is not in the geometry")
        if setting == "material":
            volume.material = value
        else:
            sizes = [s.strip() for s in volume.size.split(",")]
            if volume.shape.strip().lower() != "box" or len(sizes) != 3:
                raise ValueError(f"volume {name} is not a box with a 3-component size")
            volume.size = f"{sizes[0]}, {sizes[1]}, {value}"
        point.geometry.is_dirty = True
    else:
        raise ValueError(f"unknown scan parameter {key}")
    for model in (point.source, point.physics, point.scoring):
        model.is_dirty = True
    return point


@dataclass
class ScanPoint:
    index: int
    value: str
    package_dir: str = ""
    output_dir: str = ""
    main_ini: str = ""
    macro: str = ""
    seed: int | None = None     # the point's own seed (passed on the command line when it runs)


@dataclass
class ScanManifest:
    name: str
    parameter: str
    parameter_label: str
    values: list[str]
    scan_dir: str
    created: str
    threads: int = 1
    seed: int | None = None
    points: list[ScanPoint] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return Path(self.scan_dir) / MANIFEST


def validate_scan(base: ScanBase, parameter: ScanParameter, values: list[str]) -> list[str]:
    """Problems of every point, found before anything is written."""
    problems: list[str] = []
    for value in values:
        try:
            point = apply_value(base, parameter, value)
        except ValueError as error:
            problems.append(f"{value}: {error}")
            continue
        report = validate_config_builder(
            paths=point.paths, run=point.run, geometry=point.geometry_settings, source=point.source.to_settings(),
            physics=point.physics.to_settings(), scoring=point.scoring.to_settings(),
            material_document=point.materials if point.materials and point.materials.is_dirty else None,
            geometry_document=point.geometry, source_model=point.source, physics_model=point.physics,
            scoring_model=point.scoring)
        if not report.can_run:
            problems.extend(f"{value}: {error}" for error in report.errors)
    return problems


def create_scan(base: ScanBase, parameter: ScanParameter, values: list[str], name: str,
                runs_root: str | Path) -> ScanManifest:
    problems = validate_scan(base, parameter, values)
    if problems:
        raise ValueError("\n".join(problems))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scan_dir = Path(runs_root).expanduser() / f"{stamp}_scan_{safe_name(name)}"
    suffix = 1
    while scan_dir.exists():
        scan_dir = Path(runs_root).expanduser() / f"{stamp}_scan_{safe_name(name)}_{suffix}"
        suffix += 1
    scan_dir.mkdir(parents=True)
    manifest = ScanManifest(name=name, parameter=parameter.key, parameter_label=parameter.label, values=values,
                            scan_dir=str(scan_dir.resolve()), created=datetime.now().isoformat(timespec="seconds"),
                            threads=base.run.threads, seed=base.run.seed)
    for index, value in enumerate(values):
        point = apply_value(base, parameter, value)
        point.paths.runs_root = str(scan_dir)
        point.run.run_name = f"{safe_name(name)}_p{index:03d}"
        package, _ = create_run_package(
            project=point.project, paths=point.paths, run=point.run, geometry=point.geometry_settings,
            source=point.source.to_settings(), physics=point.physics.to_settings(),
            scoring=point.scoring.to_settings(),
            material_document=point.materials if point.materials and point.materials.is_dirty else None,
            geometry_document=point.geometry, source_model=point.source, physics_model=point.physics,
            scoring_model=point.scoring)
        manifest.points.append(ScanPoint(index, value, package.package_dir, package.output_dir,
                                         package.main_ini_path, package.run_macro_path, point.run.seed))
    save_manifest(manifest)
    return manifest


def save_manifest(manifest: ScanManifest) -> None:
    data = {"schema": SCHEMA, "version": VERSION, **asdict(manifest)}
    manifest.path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_manifest(path: str | Path) -> ScanManifest:
    path = Path(path)
    if path.is_dir():
        path = path / MANIFEST
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or data.get("version") != VERSION:
        raise ValueError(f"{path} is not a {SCHEMA} v{VERSION} manifest")
    points = [ScanPoint(**p) for p in data.pop("points")]
    for key in ("schema", "version"):
        data.pop(key)
    manifest = ScanManifest(**data, points=points)
    old_dir = Path(manifest.scan_dir) if manifest.scan_dir else None
    manifest.scan_dir = str(path.parent.resolve())   # the scan directory may have moved
    for point in points:   # relative paths (bundled examples) and moved scans resolve in the new folder
        for name in ("package_dir", "output_dir", "main_ini", "macro"):
            setattr(point, name, _rebase(getattr(point, name), old_dir, path.parent.resolve()))
    return manifest


def _rebase(value: str, old_dir: Path | None, new_dir: Path) -> str:
    if not value:
        return value
    target = Path(value)
    if not target.is_absolute():
        return str(new_dir / target)
    if not target.exists() and old_dir is not None:
        # CI hands out short (8.3) temporary paths: the manifest may spell the base
        # one way while resolve() expands it, so accept either spelling.
        for candidate, base in ((target, old_dir), (target.resolve(), old_dir.resolve())):
            try:
                return str(new_dir / candidate.relative_to(base))
            except ValueError:
                continue
    return value


@dataclass
class PointResult:
    index: int
    value: str
    state: str                       # success / failed / incomplete / ... / not_run
    reason: str = ""
    completed_events: int | None = None
    metrics: dict[tuple[str, str, str], tuple[float, float, str]] = field(default_factory=dict)


def _summary_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return dict(line.split(" = ", 1) for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                if " = " in line)


def collect(manifest: ScanManifest) -> list[PointResult]:
    """State, completed events and every scorer_statistics quantity of each point."""
    results = []
    for point in manifest.points:
        output = Path(point.output_dir)
        status_file = Path(point.package_dir) / "logs" / "run_status.json"
        summary = _summary_values(output / "run_summary.txt")
        state, reason = "not_run", ""
        if status_file.is_file():
            try:
                status = json.loads(status_file.read_text(encoding="utf-8"))
                state = str(status.get("state", "unknown"))
                reason = str(status.get("resultReason", status.get("errorMessage", "")))
            except ValueError:
                state, reason = "unknown", "run_status.json is unreadable"
        elif summary:
            # run outside the GUI runner: trust only a completed summary with all events
            done = summary.get("status") == "completed" and summary.get("planned_event_count") == \
                summary.get("actual_completed_event_count") and summary.get("simulation_executed") == "true"
            state = "success" if done else "incomplete"
            reason = "judged from run_summary.txt (no run_status.json)"
        try:
            events = int(summary["actual_completed_event_count"])
        except (KeyError, ValueError):
            events = None
        metrics = {}
        stats = output / "scorer_statistics.csv"
        if stats.is_file():
            with stats.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    if row.get("runID", "0") != "0":
                        continue
                    metrics[(row["scorer"], row["quantity"], row["key"])] = (
                        float(row["value"]), float(row["rel_error"]), row["unit"])
        results.append(PointResult(point.index, point.value, state, reason, events, metrics))
    return results


def metric_keys(results: list[PointResult]) -> list[tuple[str, str, str]]:
    return sorted({key for result in results for key in result.metrics})


def numeric_value(value: str) -> float | None:
    match = re.match(rf"\s*({_NUMBER})", value)
    return float(match.group(1)) if match else None


def write_results_csv(manifest: ScanManifest, results: list[PointResult], path: str | Path,
                      metric: tuple[str, str, str] | None) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        header = ["point", manifest.parameter, "state", "completed_events"]
        if metric:
            header += [f"{metric[0]}/{metric[1]}", "unit", "rel_error", "key"]
        writer.writerow(header)
        for result in results:
            row = [result.index, result.value, result.state, "" if result.completed_events is None
                   else result.completed_events]
            if metric:
                value = result.metrics.get(metric)
                row += [f"{value[0]:.9g}", value[2], f"{value[1]:.6g}", metric[2]] if value else ["", "", "", metric[2]]
            writer.writerow(row)
