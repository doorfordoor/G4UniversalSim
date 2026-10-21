"""Read and aggregate worker Dose CSV files for display only.

Physical-volume mass is a shared denominator across workers and must never be
added. This view only sums existing CSVs; it does not infer missing threads or
normalize by fluence, time or number of histories.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field
from pathlib import Path


MEV_IN_JOULES = 1.602176634e-13
NAME = re.compile(r"dose_volume_summary_t(?P<thread>\d+)(?:_r(?P<run>\d+))?\.csv$")
COLUMNS = {"runID", "volume_path", "volume_name", "mass_kg", "raw_edep_MeV",
           "weighted_edep_MeV", "raw_dose_Gy", "weighted_dose_Gy"}
# Schema v2 (roadmap A3) appends per-event sum-of-squares columns; v1 files stay readable.
COLUMNS_V2 = COLUMNS | {"raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"}


@dataclass
class DoseVolumeSummary:
    run_id: int
    volume_path: str
    volume_name: str
    mass_kg: float
    raw_edep_MeV: float = 0.0
    weighted_edep_MeV: float = 0.0
    thread_ids: set[int] = field(default_factory=set)

    @property
    def raw_dose_Gy(self) -> float:
        return self.raw_edep_MeV * MEV_IN_JOULES / self.mass_kg

    @property
    def weighted_dose_Gy(self) -> float:
        return self.weighted_edep_MeV * MEV_IN_JOULES / self.mass_kg


def read_dose_summaries(output_dir: str | Path) -> tuple[list[DoseVolumeSummary], list[str]]:
    directory = Path(output_dir)
    combined: dict[tuple[int, str], DoseVolumeSummary] = {}
    warnings: list[str] = []
    if not directory.is_dir():
        return [], []
    for filename in sorted(directory.glob("dose_volume_summary*.csv")):
        match = NAME.fullmatch(filename.name)
        if not match:
            warnings.append(f"Unknown Dose filename: {filename.name}")
            continue
        run_id = int(match.group("run") or 0)
        thread_id = int(match.group("thread"))
        try:
            with filename.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames is None or set(reader.fieldnames) not in (COLUMNS, COLUMNS_V2):
                    raise ValueError("Unexpected CSV column schema")
                file_keys: set[tuple[int, str]] = set()
                pending: list[tuple[tuple[int, str], str, float, float, float]] = []
                for row in reader:
                    if int(row["runID"]) != run_id:
                        raise ValueError("runID differs from the filename")
                    path = row["volume_path"]
                    if not path:
                        raise ValueError("Missing touchable path")
                    key = (run_id, path)
                    if key in file_keys:
                        raise ValueError(f"Duplicate touchable row: {path}")
                    file_keys.add(key)
                    mass = float(row["mass_kg"])
                    raw = float(row["raw_edep_MeV"])
                    weighted = float(row["weighted_edep_MeV"])
                    reported_raw_dose = float(row["raw_dose_Gy"])
                    reported_weighted_dose = float(row["weighted_dose_Gy"])
                    if (not all(math.isfinite(x) for x in
                                (mass, raw, weighted, reported_raw_dose, reported_weighted_dose))
                            or mass <= 0):
                        raise ValueError("Nonfinite dose data or nonpositive mass")
                    for energy, dose in ((raw, reported_raw_dose), (weighted, reported_weighted_dose)):
                        if not math.isclose(dose, energy * MEV_IN_JOULES / mass,
                                            rel_tol=1e-8, abs_tol=1e-15):
                            raise ValueError(f"Dose/energy/mass mismatch: {path}")
                    existing = combined.get(key)
                    if existing and not math.isclose(existing.mass_kg, mass, rel_tol=1e-9):
                        raise ValueError(f"Worker mass mismatch: {path}")
                    if existing and thread_id in existing.thread_ids:
                        raise ValueError(f"Repeated thread {thread_id}: {path}")
                    pending.append((key, row["volume_name"], mass, raw, weighted))
            # A malformed file must not contribute partially to the aggregate.
            for key, name, mass, raw, weighted in pending:
                item = combined.setdefault(key, DoseVolumeSummary(key[0], key[1], name, mass))
                item.raw_edep_MeV += raw
                item.weighted_edep_MeV += weighted
                item.thread_ids.add(thread_id)
        except (ValueError, KeyError, OSError, csv.Error) as error:
            warnings.append(f"Skipped {filename.name}: {error}")
    return sorted(combined.values(), key=lambda x: (x.run_id, x.volume_path)), warnings
