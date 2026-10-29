"""Small helpers for reading G4UniversalSim ROOT output with uproot.

    import g4usim_io
    mesh = g4usim_io.load_mesh("output/run/g4usim.root", "depthMesh", "eDep")
    mesh.value        # dense numpy array [i0, i1, i2], run total per cell (unit: mesh.unit)
    mesh.rel_error    # relative statistical error of each cell total

    stats = g4usim_io.load_scorer_statistics("output/run/g4usim.root")
    # edep/dose/fluence totals and LET with relative errors (same as scorer_statistics.csv)

Requires `uproot` and `numpy`.
"""

from __future__ import annotations

import json
import re
from numbers import Integral
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import uproot


@dataclass
class MeshQuantity:
    mesh: str
    quantity: str
    unit: str
    bins: tuple[int, int, int]
    n_events: int
    value: np.ndarray       # sum over events of the per-event cell value
    sum_sq: np.ndarray      # sum over events of the squared per-event value
    entries: np.ndarray     # number of contributing events per cell

    @property
    def uncertainty_estimator(self) -> str:
        return "uncorrected_event_moments_v1"

    @property
    def uncertainty_status(self) -> np.ndarray:
        return np.where(self.n_events < 2, "insufficient_events",
                        np.where(self.value == 0, "zero_total", "approximate"))

    @property
    def uncertainty_available(self) -> np.ndarray:
        return self.uncertainty_status == "approximate"

    @property
    def rel_error(self) -> np.ndarray:
        """R = sqrt(sum_sq / value^2 - 1/N); 0 where the cell is empty."""
        with np.errstate(divide="ignore", invalid="ignore"):
            r2 = (self.sum_sq / self.value) / self.value - 1.0 / max(self.n_events, 1)
        return np.where(self.value != 0, np.sqrt(np.clip(r2, 0.0, None)), 0.0)

    @property
    def mean_per_event(self) -> np.ndarray:
        return self.value / max(self.n_events, 1)


def _mesh_bins_from_metadata(root_path: Path, mesh: str) -> tuple[int, int, int] | None:
    metadata = root_path.with_name("run_metadata.json")
    if not metadata.is_file():
        return None
    values = json.loads(metadata.read_text(encoding="utf-8")).get("values", {})
    text = values.get(f"scoring_mesh_{mesh}_bins")
    if not text:
        return None
    parts = [int(item) for item in text.split(",")]
    return (parts[0], parts[1], parts[2]) if len(parts) == 3 else None


def mesh_names(root_path: str | Path) -> list[tuple[str, str]]:
    """(mesh, quantity) pairs present in the file."""
    with uproot.open(root_path) as root:
        data = root["mesh"].arrays(["mesh", "quantity"], library="np")
    return sorted({(str(m), str(q)) for m, q in zip(data["mesh"], data["quantity"])})


def load_mesh(root_path: str | Path, mesh: str, quantity: str,
              bins: tuple[int, int, int] | None = None, *, n_events: int | None = None) -> MeshQuantity:
    """Merge the per-worker rows of one mesh quantity into dense arrays."""
    root_path = Path(root_path)
    with uproot.open(root_path) as root:
        data = root["mesh"].arrays(library="np")
    selected = (data["mesh"] == mesh) & (data["quantity"] == quantity)
    if not selected.any():
        raise KeyError(f"{root_path}: no rows for mesh '{mesh}' quantity '{quantity}'")
    index = np.stack([data["i0"][selected], data["i1"][selected], data["i2"][selected]], axis=1)
    bins = bins or _mesh_bins_from_metadata(root_path, mesh) or tuple(int(v) + 1 for v in index.max(axis=0))
    value = np.zeros(bins)
    sum_sq = np.zeros(bins)
    entries = np.zeros(bins, dtype=np.int64)
    np.add.at(value, tuple(index.T), data["sum"][selected])
    np.add.at(sum_sq, tuple(index.T), data["sum_sq"][selected])
    np.add.at(entries, tuple(index.T), data["entries"][selected])
    n_events = _resolve_events(root_path, n_events, [data])
    units = set(map(str, data["unit"][selected]))
    return MeshQuantity(mesh, quantity, units.pop() if len(units) == 1 else ",".join(sorted(units)),
                        bins, n_events, value, sum_sq, entries)


# --- Per-volume scorer statistics (roadmap A3) ----------------------------------

@dataclass
class ScorerStatistic:
    scorer: str
    quantity: str
    key: str
    name: str
    unit: str
    estimator: str          # "total" (run total) or "ratio" (LET)
    n_events: int
    value: float            # run total (total) or ratio value (ratio)
    rel_error: float        # compatibility value; consult uncertainty_available
    ratio_denominator: float | None = None

    @property
    def uncertainty_estimator(self) -> str:
        return "uncorrected_delta_ratio_v1" if self.estimator == "ratio" else "uncorrected_event_moments_v1"

    @property
    def uncertainty_status(self) -> str:
        if self.n_events < 2:
            return "insufficient_events"
        if self.estimator == "ratio" and self.ratio_denominator == 0:
            return "undefined_ratio"
        return "zero_total" if self.value == 0 else "approximate"

    @property
    def uncertainty_available(self) -> bool:
        return self.uncertainty_status == "approximate"

    @property
    def std_error(self) -> float:
        return abs(self.value) * self.rel_error


def _rel_error(total: float, sum_sq: float, n_events: int) -> float:
    if n_events <= 0 or total == 0:
        return 0.0
    return float(np.sqrt(max((sum_sq / total) / total - 1.0 / n_events, 0.0)))


def _ratio_rel_error(num: float, num_sq: float, den: float, den_sq: float, cross: float) -> float:
    if num == 0 or den == 0:
        return 0.0
    return float(np.sqrt(max((num_sq / num) / num + (den_sq / den) / den -
                            2.0 * ((cross / num) / den), 0.0)))


def _event_count(value, source: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(f"{source}: event count must be a non-negative integer (not bool)")
    return int(value)


def _run_events(root_path: Path) -> int | None:
    metadata = root_path.with_name("run_metadata.json")
    if not metadata.is_file():
        return None
    match = re.fullmatch(r"g4usim(?:_r([0-9]+))?", root_path.stem)
    if match is None:
        raise ValueError(f"{root_path}: cannot identify the run for adjacent metadata")
    run_id = int(match.group(1) or 0)
    try:
        document = json.loads(metadata.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema") != "run_metadata_json_v1":
            raise ValueError("unsupported or missing metadata schema")
        runs = document.get("runs")
        if not isinstance(runs, list):
            raise ValueError("metadata runs must be a list")
        counts = {}
        for run in runs:
            if not isinstance(run, dict):
                raise ValueError("invalid metadata run")
            identifier = _event_count(run.get("run_id"), "metadata run_id")
            if identifier in counts:
                raise ValueError("duplicate metadata run_id")
            counts[identifier] = _event_count(run.get("completed_events"), "metadata completed_events")
        return counts.get(run_id)
    except (OSError, ValueError, TypeError) as error:
        raise ValueError(f"{metadata}: invalid event-count metadata: {error}") from error


def _resolve_events(root_path: Path, explicit, tables) -> int:
    supplied = None if explicit is None else _event_count(explicit, "n_events")
    recorded = _run_events(root_path)
    if supplied is not None and recorded is not None and supplied != recorded:
        raise ValueError(f"n_events={supplied} conflicts with metadata completed_events={recorded}")
    count = supplied if supplied is not None else recorded
    if count is None:
        raise ValueError(f"{root_path}: no reliable completed event count; provide n_events or "
                         "same-run run_metadata.json. Sparse scorer rows cannot count zero-contribution workers.")
    # Sparse rows provide a lower bound and consistency checks, never the denominator.
    workers = {}
    has_rows = False
    for data in tables:
        for thread, value in zip(data["threadID"], data["n_events"]):
            has_rows = True
            # G4Analysis stores these counters in double columns in ROOT v4.
            # Accept only exactly integral finite values there; the public API
            # and JSON metadata still require actual integer types.
            if isinstance(value, (float, np.floating)) and np.isfinite(value) and value.is_integer():
                value = int(value)
            value = _event_count(value, "ROOT worker n_events")
            thread = int(thread)
            if thread in workers and workers[thread] != value:
                raise ValueError(f"inconsistent ROOT n_events for worker {thread}")
            workers[thread] = value
    if sum(workers.values()) > count:
        raise ValueError("completed event count is smaller than the contributing workers' event counts")
    if count == 0 and has_rows:
        raise ValueError("zero completed events require empty scorer/mesh rows")
    return count


def load_scorer_statistics(root_path: str | Path, n_events: int | None = None) -> list[ScorerStatistic]:
    """Merge the per-worker rows of edep_volume, edep_particle, dose, fluence and let.

    Mirrors scorer_statistics[_rR].csv (written by the backend for every output
    format). n_events defaults to the run's completed events in run_metadata.json.
    Without same-run metadata an explicit non-negative integer is required; sparse
    scorer rows and optional event ntuples are not proof of all completed histories.
    """
    root_path = Path(root_path)
    tables: dict[str, dict] = {}
    with uproot.open(root_path) as root:
        for tree in ("edep_volume", "edep_particle", "dose", "fluence", "let"):
            if tree in root:
                tables[tree] = root[tree].arrays(library="np")
    n_events = _resolve_events(root_path, n_events, tables.values())

    def grouped(data, key_column, columns):
        sums: dict[str, dict[str, float]] = {}
        names: dict[str, str] = {}
        for index, key in enumerate(map(str, data[key_column])):
            row = sums.setdefault(key, {c: 0.0 for c in columns})
            for c in columns:
                row[c] += float(data[c][index])
            if "volume_name" in data:
                names[key] = str(data["volume_name"][index])
        return sums, names

    # tree -> key column, unit, [(quantity, value column, per-event base column, base sum_sq column)].
    # Dose/fluence sum_sq is stored in edep / track-length units; the relative
    # error is scale-free, so it is computed from the base column.
    specs = {
        "edep_volume": ("name", "MeV", [("raw_edep", "raw_edep_MeV", "raw_edep_MeV", "raw_edep_sum_sq_MeV2"),
                                        ("weighted_edep", "weighted_edep_MeV", "weighted_edep_MeV",
                                         "weighted_edep_sum_sq_MeV2")]),
        "edep_particle": ("name", "MeV", [("raw_edep", "raw_edep_MeV", "raw_edep_MeV", "raw_edep_sum_sq_MeV2"),
                                          ("weighted_edep", "weighted_edep_MeV", "weighted_edep_MeV",
                                           "weighted_edep_sum_sq_MeV2")]),
        "dose": ("volume_path", "Gy", [("raw_dose", "raw_dose_Gy", "raw_edep_MeV", "raw_edep_sum_sq_MeV2"),
                                       ("weighted_dose", "weighted_dose_Gy", "weighted_edep_MeV",
                                        "weighted_edep_sum_sq_MeV2")]),
        "fluence": ("volume_path", "mm-2",
                    [("raw_fluence", "raw_fluence_mm-2", "raw_track_length_mm", "raw_track_length_sum_sq_mm2"),
                     ("weighted_fluence", "weighted_fluence_mm-2", "weighted_track_length_mm",
                      "weighted_track_length_sum_sq_mm2")]),
    }
    result: list[ScorerStatistic] = []
    for tree, (key_column, unit, quantities) in specs.items():
        if tree not in tables:
            continue
        columns = sorted({c for _, value, base, sq in quantities for c in (value, base, sq)})
        sums, names = grouped(tables[tree], key_column, columns)
        for key, row in sums.items():
            for quantity, value, base, sq in quantities:
                result.append(ScorerStatistic(tree, quantity, key, names.get(key, key), unit, "total", n_events,
                                              row[value], _rel_error(row[base], row[sq], n_events)))
    if "let" in tables:
        columns = ["sum_wl_mm", "sum_wSl_MeV", "sum_wS2l_MeV2_per_mm", "sum_sq_wl_mm2", "sum_sq_wSl_MeV2",
                   "sum_sq_wS2l_MeV4_per_mm2", "sum_wl_x_wSl_MeV_mm", "sum_wSl_x_wS2l_MeV3_per_mm"]
        sums, names = grouped(tables["let"], "volume_path", columns)
        for key, r in sums.items():
            if r["sum_wl_mm"] > 0:
                result.append(ScorerStatistic(
                    "let", "let_t", key, names.get(key, key), "keV/um", "ratio", n_events,
                    r["sum_wSl_MeV"] / r["sum_wl_mm"],
                    _ratio_rel_error(r["sum_wSl_MeV"], r["sum_sq_wSl_MeV2"], r["sum_wl_mm"], r["sum_sq_wl_mm2"],
                                     r["sum_wl_x_wSl_MeV_mm"]), ratio_denominator=r["sum_wl_mm"]))
            if r["sum_wSl_MeV"] > 0:
                result.append(ScorerStatistic(
                    "let", "let_d", key, names.get(key, key), "keV/um", "ratio", n_events,
                    r["sum_wS2l_MeV2_per_mm"] / r["sum_wSl_MeV"],
                    _ratio_rel_error(r["sum_wS2l_MeV2_per_mm"], r["sum_sq_wS2l_MeV4_per_mm2"], r["sum_wSl_MeV"],
                                     r["sum_sq_wSl_MeV2"], r["sum_wSl_x_wS2l_MeV3_per_mm"]), ratio_denominator=r["sum_wSl_MeV"]))
    return result


def read_scorer_statistics_csv(csv_path: str | Path) -> list[dict[str, str]]:
    """Rows of the backend's merged scorer_statistics[_rR].csv."""
    import csv
    with open(csv_path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
