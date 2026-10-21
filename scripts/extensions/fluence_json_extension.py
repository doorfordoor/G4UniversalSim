"""Reference M5 postprocessor for completed track-length Fluence CSVs."""
from __future__ import annotations

from pathlib import Path

from gui.g4usim_gui.output.fluence_summary import read_fluence_summaries


EXTENSION = {
    "id": "fluence_json", "version": "0.1.0", "api_version": 1,
    "description": "Aggregate per-run/physical-touchable track-length Fluence from worker CSVs",
}


def process(input_dir: Path) -> dict:
    volumes, warnings = read_fluence_summaries(input_dir)
    if not volumes:
        raise ValueError("No valid fluence_volume_summary worker records found")
    return {
        "kind": "fluence_volume_aggregate",
        "units": {"volume": "mm^3", "track_length": "mm", "fluence": "mm^-2"},
        "physical_validation": "not_established",
        "normalization": "simulated histories only; no source strength, time or event normalization",
        "definition": "track_length / sensitive_solid_volume; not surface-crossing fluence",
        "warnings": warnings,
        "volumes": [
            {"runID": item.run_id, "volume_path": item.volume_path,
             "volume_name": item.volume_name, "thread_ids": sorted(item.thread_ids),
             "volume_mm3": item.volume_mm3,
             "raw_track_length_mm": item.raw_track_length_mm,
             "weighted_track_length_mm": item.weighted_track_length_mm,
             "raw_fluence_mm-2": item.raw_fluence_mm2,
             "weighted_fluence_mm-2": item.weighted_fluence_mm2}
            for item in volumes
        ],
    }
