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
    def rel_error(self) -> np.ndarray:
        """R = sqrt(sum_sq / value^2 - 1/N); 0 where the cell is empty."""
        with np.errstate(divide="ignore", invalid="ignore"):
            r2 = self.sum_sq / self.value**2 - 1.0 / max(self.n_events, 1)
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
              bins: tuple[int, int, int] | None = None) -> MeshQuantity:
    """Merge the per-worker rows of one mesh quantity into dense arrays."""
    root_path = Path(root_path)
    with uproot.open(root_path) as root:
        data = root["mesh"].arrays(library="np")
        events = root["events"].arrays(["threadID"], library="np") if "events" in root else None
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
    # n_events is per worker; count each worker once.
    per_thread = {}
    for thread, n in zip(data["threadID"][selected], data["n_events"][selected]):
        per_thread[int(thread)] = int(n)
    n_events = sum(per_thread.values())
    if events is not None and len(events["threadID"]) and n_events < len(events["threadID"]):
        # Workers with no mesh hits wrote no rows; the events ntuple has every event.
        n_events = len(events["threadID"])
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
    rel_error: float        # relative statistical error of value

    @property
    def std_error(self) -> float:
        return abs(self.value) * self.rel_error


def _rel_error(total: float, sum_sq: float, n_events: int) -> float:
    if n_events <= 0 or total == 0:
        return 0.0
    return float(np.sqrt(max(sum_sq / total**2 - 1.0 / n_events, 0.0)))


def _ratio_rel_error(num: float, num_sq: float, den: float, den_sq: float, cross: float) -> float:
    if num == 0 or den == 0:
        return 0.0
    return float(np.sqrt(max(num_sq / num**2 + den_sq / den**2 - 2.0 * cross / (num * den), 0.0)))


def _run_events(root_path: Path) -> int | None:
    stem = root_path.stem
    run_id = 0 if stem == "g4usim" else int(stem.rsplit("_r", 1)[-1])
    metadata = root_path.with_name("run_metadata.json")
    if metadata.is_file():
        for run in json.loads(metadata.read_text(encoding="utf-8")).get("runs", []):
            if int(run.get("run_id", -1)) == run_id:
                return int(run["completed_events"])
    return None


def load_scorer_statistics(root_path: str | Path, n_events: int | None = None) -> list[ScorerStatistic]:
    """Merge the per-worker rows of edep_volume, edep_particle, dose, fluence and let.

    Mirrors scorer_statistics[_rR].csv (written by the backend for every output
    format). n_events defaults to the run's completed events in run_metadata.json.
    """
    root_path = Path(root_path)
    n_events = n_events if n_events is not None else _run_events(root_path)
    tables: dict[str, dict] = {}
    with uproot.open(root_path) as root:
        for tree in ("edep_volume", "edep_particle", "dose", "fluence", "let"):
            if tree in root:
                tables[tree] = root[tree].arrays(library="np")
    if n_events is None:
        threads: dict[int, int] = {}
        for data in tables.values():
            for thread, n in zip(data["threadID"], data["n_events"]):
                threads[int(thread)] = int(n)
        n_events = sum(threads.values())

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
                                     r["sum_wl_x_wSl_MeV_mm"])))
            if r["sum_wSl_MeV"] > 0:
                result.append(ScorerStatistic(
                    "let", "let_d", key, names.get(key, key), "keV/um", "ratio", n_events,
                    r["sum_wS2l_MeV2_per_mm"] / r["sum_wSl_MeV"],
                    _ratio_rel_error(r["sum_wS2l_MeV2_per_mm"], r["sum_sq_wS2l_MeV4_per_mm2"], r["sum_wSl_MeV"],
                                     r["sum_sq_wSl_MeV2"], r["sum_wSl_x_wS2l_MeV3_per_mm"])))
    return result


def read_scorer_statistics_csv(csv_path: str | Path) -> list[dict[str, str]]:
    """Rows of the backend's merged scorer_statistics[_rR].csv."""
    import csv
    with open(csv_path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
