"""Aggregate existing worker track-length Fluence CSVs for display.

Lengths are additive across workers; each physical touchable volume is a
shared denominator. Missing files are never treated as zero measurements.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field
from pathlib import Path


NAME = re.compile(r"fluence_volume_summary_t(?P<thread>\d+)(?:_r(?P<run>\d+))?\.csv$")
COLUMNS = {"runID", "volume_path", "volume_name", "volume_mm3", "raw_track_length_mm",
           "weighted_track_length_mm", "raw_fluence_mm-2", "weighted_fluence_mm-2"}
# Schema v2 (roadmap A3) appends per-event sum-of-squares columns; v1 files stay readable.
COLUMNS_V2 = COLUMNS | {"raw_track_length_sum_sq_mm2", "weighted_track_length_sum_sq_mm2", "n_events"}


@dataclass
class FluenceVolumeSummary:
    run_id: int
    volume_path: str
    volume_name: str
    volume_mm3: float
    raw_track_length_mm: float = 0.0
    weighted_track_length_mm: float = 0.0
    thread_ids: set[int] = field(default_factory=set)

    @property
    def raw_fluence_mm2(self) -> float:
        return self.raw_track_length_mm / self.volume_mm3

    @property
    def weighted_fluence_mm2(self) -> float:
        return self.weighted_track_length_mm / self.volume_mm3


def read_fluence_summaries(output_dir: str | Path) -> tuple[list[FluenceVolumeSummary], list[str]]:
    directory = Path(output_dir)
    combined: dict[tuple[int, str], FluenceVolumeSummary] = {}
    warnings: list[str] = []
    if not directory.is_dir():
        return [], []
    for filename in sorted(directory.glob("fluence_volume_summary*.csv")):
        match = NAME.fullmatch(filename.name)
        if not match:
            warnings.append(f"Unknown Fluence filename: {filename.name}")
            continue
        run_id = int(match.group("run") or 0)
        thread_id = int(match.group("thread"))
        try:
            pending = []
            seen = set()
            with filename.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames is None or set(reader.fieldnames) not in (COLUMNS, COLUMNS_V2):
                    raise ValueError("Unexpected CSV column schema")
                for row in reader:
                    if int(row["runID"]) != run_id:
                        raise ValueError("runID differs from filename")
                    path = row["volume_path"]
                    name = row["volume_name"]
                    if not path or not name or path in seen:
                        raise ValueError("Missing or repeated physical touchable")
                    seen.add(path)
                    v = float(row["volume_mm3"])
                    raw = float(row["raw_track_length_mm"])
                    weighted = float(row["weighted_track_length_mm"])
                    reported_raw = float(row["raw_fluence_mm-2"])
                    reported_weighted = float(row["weighted_fluence_mm-2"])
                    if not all(map(math.isfinite, (v, raw, weighted, reported_raw, reported_weighted))) or v <= 0 or raw < 0:
                        raise ValueError("Nonfinite data, negative raw length, or nonpositive volume")
                    derived_raw, derived_weighted = raw / v, weighted / v
                    if not all(map(math.isfinite, (derived_raw, derived_weighted))):
                        raise ValueError("Nonfinite derived fluence")
                    if not (math.isclose(reported_raw, derived_raw, rel_tol=1e-8, abs_tol=1e-12) and
                            math.isclose(reported_weighted, derived_weighted, rel_tol=1e-8, abs_tol=1e-12)):
                        raise ValueError("Track-length/volume/fluence mismatch")
                    key = (run_id, path)
                    existing = combined.get(key)
                    if existing and (not math.isclose(existing.volume_mm3, v, rel_tol=1e-9) or
                                     existing.volume_name != name or thread_id in existing.thread_ids):
                        raise ValueError("Worker volume/name/thread mismatch")
                    pending.append((key, name, v, raw, weighted))
            # Validate complete file and cross-worker totals before accepting any rows.
            for key, name, v, raw, weighted in pending:
                prior = combined.get(key)
                if prior:
                    total_raw = prior.raw_track_length_mm + raw
                    total_weighted = prior.weighted_track_length_mm + weighted
                    if not all(map(math.isfinite, (total_raw, total_weighted,
                                                   total_raw / v, total_weighted / v))):
                        raise ValueError("Nonfinite accumulated track length or fluence")
            for key, name, v, raw, weighted in pending:
                item = combined.setdefault(key, FluenceVolumeSummary(key[0], key[1], name, v))
                item.raw_track_length_mm += raw
                item.weighted_track_length_mm += weighted
                item.thread_ids.add(thread_id)
        except (ValueError, TypeError, KeyError, OSError, csv.Error) as error:
            warnings.append(f"Skipped {filename.name}: {error}")
    return sorted(combined.values(), key=lambda x: (x.run_id, x.volume_path)), warnings
