"""Small helpers for reading G4UniversalSim ROOT output with uproot.

    import g4usim_io
    mesh = g4usim_io.load_mesh("output/run/g4usim.root", "depthMesh", "eDep")
    mesh.value        # dense numpy array [i0, i1, i2], run total per cell (unit: mesh.unit)
    mesh.rel_error    # relative statistical error of each cell total

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
