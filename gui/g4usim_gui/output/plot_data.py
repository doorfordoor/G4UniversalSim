"""Plottable data sets of a simulation output directory (roadmap C1).

Pure Python + numpy (no Qt): the Results "Plots" tab and its smoke test use the same
loaders. Every loader returns arrays exactly as stored by the backend; uncertainties
are the A3 per-event statistical errors (scorer_statistics, mesh rel_error) or
Poisson errors of histogram counts.

Data sets found in an output directory:
  scorer   merged scorer_statistics[_rR].csv: one bar per touchable for each
           (scorer, quantity), value +- std_error
  mesh     native scoring mesh (scoring_mesh[_rR].csv, or the ROOT mesh ntuple of
           g4usim[_rR].root): 1D profile along an axis (summed over the others) or a
           2D map (summed over the remaining axis), value +- statistical error;
           cell centres from run_metadata.json (bins, half sizes, centre)
  edep     per-worker hist_edep_raw/weighted_tN[_rR].csv summed over workers
  pulse    per-event deposits (event_edep_tN[_rR].csv) histogrammed
  phase    phase_space_tN[_rR].csv kinetic energy spectra per particle (log bins)
Values are run totals; normalization="per_event" divides them by the run's completed events
(run_summary.txt), which makes runs with different event counts comparable.
"""

from __future__ import annotations

from .provenance import output_evidence, output_files, verified_operation

import csv
import json
import math
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

RUN_SUFFIX = re.compile(r"_r(\d+)$")


@dataclass
class Series:
    """One curve: bin edges (len n + 1) or points (len n), values and errors."""
    label: str
    x: np.ndarray
    y: np.ndarray
    yerr: np.ndarray | None = None
    edges: bool = False          # x holds bin edges -> step plot


@dataclass
class Plot:
    title: str
    xlabel: str
    ylabel: str
    kind: str                    # "bar" | "step" | "line" | "image"
    series: list[Series] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)       # bar: one label per bar
    image: np.ndarray | None = None                           # image: [ny, nx]
    image_error: np.ndarray | None = None
    extent: tuple[float, float, float, float] | None = None   # image: x0, x1, y0, y1
    log_x: bool = False
    normalization: str = "total"
    value_label: str = ""
    # (message template, values): translated and formatted by the GUI (i18n.ui_format)
    notes: list[tuple[str, dict]] = field(default_factory=list)


@dataclass(frozen=True)
class DataSet:
    kind: str                    # scorer | mesh | edep | pulse | phase
    key: str                     # stable id within the directory
    label: str
    run_id: int
    detail: tuple = ()


def _run_of(stem: str) -> int:
    match = RUN_SUFFIX.search(stem)
    return int(match.group(1)) if match else 0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def _worker_files(output: Path, stem: str, run_id: int) -> list[Path]:
    suffix = "" if run_id == 0 else f"_r{run_id}"
    pattern = re.compile(rf"{re.escape(stem)}_t\d+{suffix}\.csv")
    return sorted(p for p in output_files(output, f"{stem}_t*.csv") if pattern.fullmatch(p.name))


@verified_operation
def metadata_values(output: Path) -> dict[str, str]:
    evidence = output_evidence(output)
    return {str(k): str(v) for k, v in (evidence.document or {}).get("values", {}).items()}


@verified_operation
def discover(output_dir: str | Path) -> list[DataSet]:
    output = Path(output_dir)
    if not output.is_dir():
        return []
    found: list[DataSet] = []
    for path in sorted(output_files(output, "scorer_statistics*.csv")):
        if path.stem != "scorer_statistics" and not RUN_SUFFIX.search(path.stem):
            continue
        run_id = _run_of(path.stem)
        pairs = sorted({(r["scorer"], r["quantity"], r["unit"]) for r in _read_csv(path)})
        for scorer, quantity, unit in pairs:
            found.append(DataSet("scorer", f"scorer/{scorer}/{quantity}/r{run_id}",
                                 f"{scorer} {quantity} [{unit}] (run {run_id})", run_id, (scorer, quantity)))
    meshes: dict[tuple[str, str, int], str] = {}
    for path in sorted(output_files(output, "scoring_mesh*.csv")):
        if path.stem != "scoring_mesh" and not RUN_SUFFIX.search(path.stem):
            continue
        run_id = _run_of(path.stem)
        for mesh, quantity in sorted({(r["mesh"], r["quantity"]) for r in _read_csv(path)}):
            meshes[(mesh, quantity, run_id)] = "csv"
    for path in sorted(output_files(output, "g4usim*.root")):
        if path.stem != "g4usim" and not RUN_SUFFIX.search(path.stem):
            continue
        run_id = _run_of(path.stem)
        try:
            import uproot
            with uproot.open(path) as root:
                if "mesh" not in root:
                    continue
                data = root["mesh"].arrays(["mesh", "quantity"], library="np")
            for mesh, quantity in sorted({(str(m), str(q)) for m, q in zip(data["mesh"], data["quantity"])}):
                meshes.setdefault((mesh, quantity, run_id), "root")
        except Exception:   # unreadable ROOT file: the CSV (if any) stays available
            continue
    for (mesh, quantity, run_id), source in sorted(meshes.items()):
        found.append(DataSet("mesh", f"mesh/{mesh}/{quantity}/r{run_id}",
                             f"mesh {mesh} {quantity} (run {run_id}, {source})", run_id, (mesh, quantity, source)))
    for stem, kind, label in (("hist_edep_raw", "edep", "Edep histogram (raw)"),
                              ("hist_edep_weighted", "edep", "Edep histogram (weighted)"),
                              ("event_edep", "pulse", "Per-event deposit"),
                              ("phase_space", "phase", "Phase-space energy spectra")):
        runs = sorted({_run_of(p.stem) for p in output_files(output, f"{stem}_t*.csv")})
        for run_id in runs:
            if _worker_files(output, stem, run_id):
                found.append(DataSet(kind, f"{stem}/r{run_id}", f"{label} (run {run_id})", run_id, (stem,)))
    return found


# --- loaders -----------------------------------------------------------------------

def uncertainty(row: dict[str, str]) -> tuple[str, str]:
    """Explicit v2 status, or conservative v1 inference without inventing N."""
    ratio = row.get("estimator") == "ratio" or row.get("scorer") == "let"
    method = "uncorrected_delta_ratio_v1" if ratio else "uncorrected_event_moments_v1"
    try:
        count = int(row["n_events"])
        value = float(row.get("value", row.get("sum", "0")))
    except (KeyError, ValueError, TypeError):
        return method, "insufficient_events"
    if count < 2:
        return method, "insufficient_events"
    explicit = row.get("uncertainty_status")
    if explicit and explicit != "approximate":
        return row.get("uncertainty_estimator", method), explicit
    if value == 0:
        return method, "undefined_ratio" if ratio else "zero_total"
    if not math.isfinite(value):
        raise ValueError("Non-finite scorer value")
    return row.get("uncertainty_estimator", method), "approximate"


@verified_operation
def statistic_uncertainty(output_dir: str | Path, metric: tuple[str, str, str]) -> tuple[str, str]:
    path = Path(output_dir) / "scorer_statistics.csv"
    if path in output_evidence(output_dir).files:
        for row in _read_csv(path):
            if (row.get("scorer"), row.get("quantity"), row.get("key")) == metric:
                return uncertainty(row)
    return "unknown", "insufficient_events"


@verified_operation
def scorer_plot(output_dir: str | Path, dataset: DataSet) -> Plot:
    output = Path(output_dir)
    name = "scorer_statistics.csv" if dataset.run_id == 0 else f"scorer_statistics_r{dataset.run_id}.csv"
    scorer, quantity = dataset.detail
    rows = [r for r in _read_csv(output_evidence(output).require(name)) if r["scorer"] == scorer and r["quantity"] == quantity]
    rows.sort(key=lambda r: r["key"])
    values = np.array([float(r["value"]) for r in rows])
    evidence = [uncertainty(row) for row in rows]
    raw_errors = np.array([float(r["std_error"]) for r in rows])
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(raw_errors)) or np.any(raw_errors < 0):
        raise ValueError("Scorer values/errors must be finite and errors non-negative")
    errors = np.ma.array(raw_errors,
                         mask=[status != "approximate" for _, status in evidence])
    unit = rows[0]["unit"] if rows else ""
    plot = Plot(f"{scorer} / {quantity}", "volume", f"{quantity} [{unit}]", "bar",
                categories=[r["key"] for r in rows])
    plot.series.append(Series(output.name, np.arange(len(rows)), values, errors))
    plot.notes.append(("Approximate uncertainty: {methods}; unavailable error bars are hidden ({statuses}).",
                       {"methods": ", ".join(sorted({m for m, _ in evidence})),
                        "statuses": ", ".join(sorted({v for _, v in evidence}))}))
    return plot


@dataclass
class MeshData:
    mesh: str
    quantity: str
    unit: str
    bins: tuple[int, int, int]
    value: np.ndarray
    error: np.ndarray            # absolute statistical error per cell
    axes: tuple[str, str, str]
    centres: list[np.ndarray]    # cell centres per axis: mm (box meshes) or bin indices
    coordinate_unit: str = "bin" # "mm" when the centres are positions


@verified_operation
def load_mesh(output_dir: str | Path, dataset: DataSet) -> MeshData:
    output = Path(output_dir)
    mesh, quantity, source = dataset.detail
    meta = metadata_values(output)
    prefix = f"scoring_mesh_{mesh}_"
    bins = tuple(int(v) for v in meta[prefix + "bins"].split(",")) if prefix + "bins" in meta else None
    if source == "csv":
        name = "scoring_mesh.csv" if dataset.run_id == 0 else f"scoring_mesh_r{dataset.run_id}.csv"
        rows = [r for r in _read_csv(output_evidence(output).require(name)) if r["mesh"] == mesh and r["quantity"] == quantity]
        index = np.array([[int(r["i0"]), int(r["i1"]), int(r["i2"])] for r in rows], dtype=int).reshape(-1, 3)
        sums = np.array([float(r["sum"]) for r in rows])
        rel = np.array([float(r["rel_error"]) for r in rows])
        unit = rows[0]["unit"] if rows else ""
        bins = bins or tuple(int(v) + 1 for v in index.max(axis=0))
        value = np.zeros(bins)
        error = np.ma.masked_all(bins)
        value[tuple(index.T)] = sums
        error[tuple(index.T)] = np.ma.array(np.abs(sums) * rel,
            mask=[uncertainty(r)[1] != "approximate" for r in rows])
    else:
        import sys
        from g4usim_gui.core import install_layout
        sys.path.insert(0, str(install_layout.scripts_dir()))
        import g4usim_io   # noqa: E402  (repository helper, needs uproot)
        name = "g4usim.root" if dataset.run_id == 0 else f"g4usim_r{dataset.run_id}.root"
        data = g4usim_io.load_mesh(output_evidence(output).require(name), mesh, quantity, bins)
        bins, unit, value = data.bins, data.unit, data.value
        error = np.ma.array(np.abs(value) * data.rel_error, mask=~data.uncertainty_available)
    axes = tuple(meta.get(prefix + "axes", "i0,i1,i2").split(","))
    centres = []
    coordinate_unit = "bin"
    if prefix + "size_mm" in meta and prefix + "center_mm" in meta and meta.get(prefix + "shape") == "box":
        half = [float(v) for v in meta[prefix + "size_mm"].split(",")]
        centre = [float(v) for v in meta[prefix + "center_mm"].split(",")]
        for axis in range(3):
            width = 2 * half[axis] / bins[axis]
            centres.append(centre[axis] - half[axis] + (np.arange(bins[axis]) + 0.5) * width)
        coordinate_unit = "mm"
    else:
        centres = [np.arange(n, dtype=float) for n in bins]
    return MeshData(mesh, quantity, unit, bins, value, error, axes, centres, coordinate_unit)


def mesh_profile(data: MeshData, axis: int, label: str = "") -> Plot:
    others = tuple(a for a in range(3) if a != axis)
    value = data.value.sum(axis=others)
    # No cross-cell event products are stored: projection covariance is unknown.
    error = (np.ma.sqrt((data.error ** 2).sum(axis=others))
             if all(data.bins[a] == 1 for a in others) else None)
    plot = Plot(f"{data.mesh} / {data.quantity}", f"{data.axes[axis]} [{data.coordinate_unit}]",
                f"{data.quantity} [{data.unit}]", "line")
    plot.series.append(Series(label or data.mesh, data.centres[axis], value, error))
    plot.notes.append(("Projection uncertainty unavailable when combining cells: cross-cell event covariance is not stored.", {}))
    plot.notes.append(("Approximate uncertainty: {methods}; unavailable error bars are hidden ({statuses}).",
                       {"methods": "uncorrected_event_moments_v1", "statuses": "cell evidence / covariance"}))
    return plot


def mesh_map(data: MeshData, axis_x: int, axis_y: int) -> Plot:
    other = ({0, 1, 2} - {axis_x, axis_y}).pop()
    value = data.value.sum(axis=other)
    error = np.ma.sqrt((data.error ** 2).sum(axis=other)) if data.bins[other] == 1 else None
    if axis_x < axis_y:   # array is [ax_low, ax_high]; image wants [y, x]
        image, image_error = value.T, None if error is None else error.T
    else:
        image, image_error = value, error
    cx, cy = data.centres[axis_x], data.centres[axis_y]

    def span(c):
        step = c[1] - c[0] if len(c) > 1 else 1.0
        return c[0] - step / 2, c[-1] + step / 2
    unit = f" [{data.coordinate_unit}]"
    plot = Plot(f"{data.mesh} / {data.quantity}", data.axes[axis_x] + unit, data.axes[axis_y] + unit, "image",
                image=image, image_error=image_error, extent=(*span(cx), *span(cy)),
                value_label=f"{data.quantity} [{data.unit}]")
    plot.notes.append(("Summed over {axis}; colour = {quantity} [{unit}].",
                       {"axis": data.axes[other], "quantity": data.quantity, "unit": data.unit}))
    plot.notes.append(("Approximate uncertainty: {methods}; unavailable error bars are hidden ({statuses}).",
                       {"methods": "uncorrected_event_moments_v1", "statuses": "cell evidence / covariance"}))
    if error is None:
        plot.notes.append(("Projection uncertainty unavailable when combining cells: cross-cell event covariance is not stored.", {}))
    return plot


@verified_operation
def edep_plot(output_dir: str | Path, dataset: DataSet) -> Plot:
    output = Path(output_dir)
    stem = dataset.detail[0]
    counts = None
    edges = None
    for path in _worker_files(output, stem, dataset.run_id):
        rows = _read_csv(path)
        low = np.array([float(r.get("low_edge_MeV", r.get("low_edge", 0))) for r in rows])
        high = np.array([float(r.get("high_edge_MeV", r.get("high_edge", 0))) for r in rows])
        c = np.array([float(r["count"]) for r in rows])
        if counts is None:
            counts, edges = c, np.append(low, high[-1:])
        elif len(c) != len(counts) or not np.allclose(low, edges[:-1]):
            raise ValueError(f"{path.name}: binning differs between workers")
        else:
            counts = counts + c
    plot = Plot(stem, "energy deposit per event [MeV]", "events per bin", "step")
    plot.series.append(Series(output.name, edges, counts, np.sqrt(counts), edges=True))
    plot.notes.append(("Summed over worker files; error bars: Poisson sqrt(N).", {}))
    return plot


@verified_operation
def pulse_plot(output_dir: str | Path, dataset: DataSet, bins: int = 200, top: float | None = None) -> Plot:
    output = Path(output_dir)
    values = []
    for path in _worker_files(output, "event_edep", dataset.run_id):
        values.extend(float(r["raw_edep_MeV"]) for r in _read_csv(path))
    values = np.array(values)
    events = len(values)
    evidence = output_evidence(output)
    if evidence.document is not None:
        run = next(r for r in evidence.document["runs"] if r["run_id"] == dataset.run_id)
        expected = run.get("completed_events")
        if type(expected) is not int or expected < 0 or events != expected:
            raise ValueError(f"Event rows ({events}) conflict with recorded completed events ({expected})")
    positive = values[values > 0]
    top = top or (float(positive.max()) * 1.05 if len(positive) else 1.0)
    counts, edges = np.histogram(positive, bins=bins, range=(0.0, top))
    plot = Plot("per-event energy deposit", "deposit [MeV]", "fraction of events per bin", "step")
    norm = 1.0 / max(events, 1)
    plot.series.append(Series(output.name, edges, counts * norm, np.sqrt(counts) * norm, edges=True))
    plot.notes.append(("{events} events, {empty} without deposit (not shown).",
                       {"events": events, "empty": events - len(positive)}))
    return plot


@verified_operation
def phase_plot(output_dir: str | Path, dataset: DataSet, per_decade: int = 10) -> Plot:
    output = Path(output_dir)
    energies: dict[str, list[tuple[float, float]]] = {}
    for path in _worker_files(output, "phase_space", dataset.run_id):
        for r in _read_csv(path):
            energies.setdefault(r["particle"], []).append((float(r["kineticEnergy_MeV"]), float(r["weight"])))
    plot = Plot("phase-space kinetic energy", "kinetic energy [MeV]", "weighted entries per bin", "step", log_x=True)
    positive = [e for values in energies.values() for e, _ in values if e > 0]
    if not positive:
        return plot
    lo, hi = math.floor(math.log10(min(positive))), math.ceil(math.log10(max(positive)) + 1e-12)
    edges = np.logspace(lo, hi, (hi - lo) * per_decade + 1)
    for particle in sorted(energies):
        e = np.array([v for v, _ in energies[particle]])
        w = np.array([w for _, w in energies[particle]])
        counts, _ = np.histogram(e, bins=edges, weights=w)
        sq, _ = np.histogram(e, bins=edges, weights=w * w)
        plot.series.append(Series(particle, edges, counts, np.sqrt(sq), edges=True))
    plot.notes.append(("Entries crossing the recorded volume; error bars: sqrt(sum w^2).", {}))
    return plot


@verified_operation
def run_events(output_dir: str | Path, run_id: int) -> int | None:
    """Completed events of a run from run_summary.txt (run_<R>_completed_events)."""
    evidence = output_evidence(output_dir)
    if evidence.document is not None:
        return next((r["completed_events"] for r in evidence.document["runs"] if r["run_id"] == run_id), None)
    path = Path(output_dir) / "run_summary.txt"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, _, value = line.partition(" = ")
        if key.strip() == f"run_{run_id}_completed_events":
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


@verified_operation
def build_plot(output_dir: str | Path, dataset: DataSet, per_primary: bool | None = None,
               *, normalization: str | None = None, **options) -> Plot:
    """Normalize by completed events, never by an assumed primary-particle count.

    per_primary is a deprecated compatibility alias with its historical numbers.
    """
    if per_primary is not None:
        if type(per_primary) is not bool:
            raise ValueError("per_primary must be a boolean")
        legacy = "per_event" if per_primary else "total"
        if normalization is not None and normalization != legacy:
            raise ValueError("per_primary conflicts with normalization")
        warnings.warn("per_primary is deprecated; use normalization='per_event' or 'total'. "
                      "The denominator is completed events, not primary particles.",
                      DeprecationWarning, stacklevel=2)
        normalization = legacy
    normalization = "total" if normalization is None else normalization
    if normalization not in {"total", "per_event"}:
        raise ValueError("normalization must be 'total' or 'per_event'")
    if normalization == "per_event" and dataset.kind == "scorer" and dataset.detail[0] == "let":
        raise ValueError("LET is a ratio estimator; per-event normalization is not defined.")
    plot = _build_plot(output_dir, dataset, **options)
    if normalization == "per_event" and dataset.kind != "pulse":
        events = run_events(output_dir, dataset.run_id)
        if events is None or events <= 0:
            raise ValueError(f"no positive completed event count for run {dataset.run_id} in run_summary.txt")
        for series in plot.series:
            series.y = series.y / events
            if series.yerr is not None:
                series.yerr = series.yerr / events
        if plot.image is not None:
            plot.image = plot.image / events
            if plot.image_error is not None:
                plot.image_error = plot.image_error / events
        if plot.kind != "image":
            plot.ylabel += " / event"
        plot.notes.append(("Divided by the {events} completed events of run {run} (run_summary.txt).",
                           {"events": events, "run": dataset.run_id}))
    for warning in output_evidence(output_dir).warnings:
        plot.notes.append((warning, {}))
    plot.normalization = "per_event" if dataset.kind == "pulse" else normalization
    if normalization == "per_event" and plot.kind == "image":
        plot.value_label += " / event"
    if per_primary is not None:
        plot.notes.append(("Deprecated per_primary option: normalization is per event, not per primary particle.", {}))
    return plot


def _build_plot(output_dir: str | Path, dataset: DataSet, **options) -> Plot:
    if dataset.kind == "scorer":
        return scorer_plot(output_dir, dataset)
    if dataset.kind == "mesh":
        data = load_mesh(output_dir, dataset)
        if options.get("map"):
            return mesh_map(data, *options["map"])
        axis = options.get("axis")
        if axis is None:   # default: the axis with the most bins
            axis = int(np.argmax(data.bins))
        return mesh_profile(data, axis, Path(output_dir).name)
    if dataset.kind == "edep":
        return edep_plot(output_dir, dataset)
    if dataset.kind == "pulse":
        return pulse_plot(output_dir, dataset, bins=options.get("bins", 200), top=options.get("top"))
    if dataset.kind == "phase":
        return phase_plot(output_dir, dataset)
    raise ValueError(f"unknown data set kind {dataset.kind}")


def matching(datasets: list[DataSet], key: str) -> DataSet | None:
    """The data set with the same key in another output directory (run comparison)."""
    return next((d for d in datasets if d.key == key), None)


def write_plot_csv(plot: Plot, path: str | Path) -> None:
    """The plotted numbers, one row per point/bin (image: one row per cell)."""
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if plot.kind == "image":
            writer.writerow(["x_index", "y_index", "value", "error", "normalization", "value_label"])
            for (iy, ix), value in np.ndenumerate(plot.image):
                writer.writerow([ix, iy, f"{value:.9g}", "" if plot.image_error is None or np.ma.is_masked(plot.image_error[iy, ix]) else f"{plot.image_error[iy, ix]:.9g}", plot.normalization, plot.value_label])
            return
        writer.writerow(["series", "x_low_or_x", "x_high", "label", "value", "error", "normalization", "value_label"])
        for series in plot.series:
            for i, value in enumerate(series.y):
                low = series.x[i]
                high = series.x[i + 1] if series.edges else ""
                label = plot.categories[i] if plot.categories else ""
                error = "" if series.yerr is None or np.ma.is_masked(series.yerr[i]) else f"{series.yerr[i]:.9g}"
                writer.writerow([series.label, f"{low:.9g}", high if high == "" else f"{high:.9g}", label,
                                 f"{value:.9g}", error, plot.normalization, plot.ylabel])
