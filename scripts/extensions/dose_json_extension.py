"""Reference M5 output extension: export worker-combined Dose CSVs as JSON."""
from __future__ import annotations

from pathlib import Path
from gui.g4usim_gui.output.provenance import output_evidence

from gui.g4usim_gui.output.dose_summary import read_dose_summaries

EXTENSION = {
    "id": "dose_json", "version": "0.1.0", "api_version": 1,
    "description": "Read completed Dose worker CSVs and export totals per run/touchable",
}


def process(input_dir: Path) -> dict:
    volumes, warnings = read_dose_summaries(input_dir)
    if not volumes:
        raise ValueError("No valid dose_volume_summary worker records found")
    return {
        "provenance": output_evidence(input_dir).status,
        "kind": "dose_volume_aggregate", "units": {"mass": "kg", "edep": "MeV", "dose": "Gy"},
        "physical_validation": "not_established",
        "normalization": "simulated histories only; no time/fluence/source strength",
        "warnings": warnings,
        "volumes": [
            {"runID": item.run_id, "volume_path": item.volume_path,
             "volume_name": item.volume_name, "thread_ids": sorted(item.thread_ids),
             "mass_kg": item.mass_kg, "raw_edep_MeV": item.raw_edep_MeV,
             "weighted_edep_MeV": item.weighted_edep_MeV,
             "raw_dose_Gy": item.raw_dose_Gy,
             "weighted_dose_Gy": item.weighted_dose_Gy}
            for item in volumes
        ],
    }
